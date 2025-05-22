import os
import pty
import select
import struct
import fcntl
import termios
import signal
import threading
import subprocess
import time
from flask_socketio import emit, join_room, leave_room
from flask_login import current_user
from app import socketio, db
from app.terminal.models import TerminalSession, TerminalLog
from datetime import datetime
import sys

# Store active terminal processes
terminal_processes = {}

@socketio.on('join_terminal')
def on_join_terminal(data):
    """Join a terminal session"""
    if not current_user.is_authenticated:
        return
    
    session_id = data.get('session_id')
    print(f"User {current_user.username} joining terminal session {session_id}")
    
    # Get session from database
    session = TerminalSession.query.filter_by(session_id=session_id, user_id=current_user.id).first()
    
    if not session:
        emit('terminal_error', {'error': 'Session not found'})
        return
    
    # Join room
    join_room(session_id)
    emit('terminal_joined', {'session_id': session_id})
    
    # Create terminal process if not exists
    if session_id not in terminal_processes:
        print(f"Creating new terminal process for session {session_id}")
        create_terminal_process(session_id)
    else:
        print(f"Using existing terminal process for session {session_id}")
    
@socketio.on('terminal_input')
def on_terminal_input(data):
    """Handle terminal input"""
    if not current_user.is_authenticated:
        return
    
    session_id = data.get('session_id')
    input_data = data.get('data')
    
    print(f"Received terminal input for session {session_id}: {repr(input_data)}")
    
    # Get session
    session = TerminalSession.query.filter_by(session_id=session_id, user_id=current_user.id).first()
    
    if not session:
        emit('terminal_error', {'error': 'Session not found'})
        return
    
    # Update last activity
    session.last_activity = datetime.utcnow()
    db.session.commit()
    
    # Get terminal process
    if session_id in terminal_processes and terminal_processes[session_id].get('fd'):
        # Write to terminal
        fd = terminal_processes[session_id]['fd']
        try:
            os.write(fd, input_data.encode())
            print(f"Wrote {len(input_data)} bytes to terminal")
        except Exception as e:
            print(f"Error writing to terminal: {e}")
            emit('terminal_error', {'error': f'Failed to send input: {str(e)}'})
    else:
        print(f"No terminal process found for session {session_id}")
        # Try to create a new process
        if create_terminal_process(session_id):
            # Retry writing
            try:
                fd = terminal_processes[session_id]['fd']
                os.write(fd, input_data.encode())
                print(f"Wrote {len(input_data)} bytes to terminal after recreating")
            except Exception as e:
                print(f"Error writing to terminal after recreating: {e}")
                emit('terminal_error', {'error': f'Failed to send input: {str(e)}'})
        else:
            emit('terminal_error', {'error': 'Terminal process not available'})

def create_terminal_process(session_id):
    """Create a new terminal process"""
    try:
        # Create PTY
        master_fd, slave_fd = pty.openpty()
        
        # Set terminal size
        term_size = struct.pack("HHHH", 24, 80, 0, 0)
        fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, term_size)
        
        # Start bash process
        process = subprocess.Popen(
            ['bash'],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            preexec_fn=os.setsid,
            close_fds=True
        )
        
        # Close slave FD
        os.close(slave_fd)
        
        # Store process info
        terminal_processes[session_id] = {
            'fd': master_fd,
            'process': process,
            'thread': None
        }
        
        # Start reader thread
        thread = threading.Thread(target=read_terminal_output, args=(session_id, master_fd))
        thread.daemon = True
        thread.start()
        
        terminal_processes[session_id]['thread'] = thread
        
        print(f"Terminal process created for session {session_id}")
        return True
        
    except Exception as e:
        print(f"Error creating terminal process: {e}")
        import traceback
        traceback.print_exc()
        return False

def read_terminal_output(session_id, fd):
    """Read output from terminal and send to client"""
    try:
        max_read_bytes = 1024 * 8  # 8KB buffer
        
        while True:
            try:
                ready_to_read, _, _ = select.select([fd], [], [], 0.1)
                
                if not ready_to_read:
                    # Check if process is still running
                    if session_id not in terminal_processes:
                        print(f"Terminal process no longer exists for session {session_id}")
                        break
                    
                    process = terminal_processes[session_id]['process']
                    if process.poll() is not None:
                        print(f"Terminal process has ended for session {session_id}")
                        close_terminal_process(session_id)
                        break
                    
                    continue
                
                # Read from terminal
                output = os.read(fd, max_read_bytes)
                if not output:
                    print(f"No output from terminal for session {session_id}, exiting reader thread")
                    break
                
                # Send to client
                output_text = output.decode('utf-8', errors='replace')
                socketio.emit('terminal_output', {
                    'session_id': session_id,
                    'data': output_text
                }, room=session_id)
                
                # Log output
                log = TerminalLog(
                    session_id=session_id,
                    event_type='output',
                    command=None,
                    output=output_text
                )
                db.session.add(log)
                db.session.commit()
                
            except OSError as e:
                print(f"OSError in terminal reader: {e}")
                if e.errno == 5:  # Input/output error
                    print(f"Terminal file descriptor is invalid for session {session_id}")
                    break
                raise
                
            except Exception as e:
                print(f"Error reading terminal output: {e}")
                import traceback
                traceback.print_exc()
                break
                
    except Exception as e:
        print(f"Error in terminal reader thread: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print(f"Terminal reader thread exiting for session {session_id}")
        close_terminal_process(session_id)

def close_terminal_process(session_id):
    """Close a terminal process"""
    if session_id in terminal_processes:
        try:
            # Close FD
            fd = terminal_processes[session_id]['fd']
            try:
                os.close(fd)
                print(f"Closed terminal FD for session {session_id}")
            except OSError:
                pass
            
            # Kill process
            process = terminal_processes[session_id]['process']
            if process.poll() is None:
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    print(f"Sent SIGTERM to process group for session {session_id}")
                    
                    # Wait for process to terminate
                    time.sleep(0.5)
                    
                    if process.poll() is None:
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                        print(f"Sent SIGKILL to process group for session {session_id}")
                except Exception as e:
                    print(f"Error killing process for session {session_id}: {e}")
                    
        except Exception as e:
            print(f"Error closing terminal process for session {session_id}: {e}")
            
        # Remove from active processes
        del terminal_processes[session_id]
        print(f"Removed terminal process for session {session_id}")
        
        # Update session in database
        try:
            session = TerminalSession.query.filter_by(session_id=session_id).first()
            if session and session.active:
                session.active = False
                session.last_activity = datetime.utcnow()
                db.session.commit()
                print(f"Updated session status in database for session {session_id}")
        except Exception as e:
            print(f"Error updating session in database for session {session_id}: {e}")

@socketio.on('disconnect')
def on_disconnect():
    """Handle client disconnect"""
    # We don't automatically close terminal processes on disconnect
    # because the user might reconnect later
    print(f"Client disconnected")