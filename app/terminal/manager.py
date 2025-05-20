# app/terminal/manager.py (optimized version)
import os
import pty
import select
import signal
import subprocess
import threading
import time
from datetime import datetime
from flask_socketio import emit

# Store active terminal sessions
active_terminals = {}

class TerminalManager:
    """Manages terminal sessions"""
    
    @staticmethod
    def create_session(session_id, socketio):
        """Create a new terminal session or return existing one"""
        # If session exists, return it
        if session_id in active_terminals:
            # Check if process is still running
            process = active_terminals[session_id]['process']
            if process.poll() is None:
                return active_terminals[session_id]
            else:
                # Process ended, clean up
                TerminalManager.close_session(session_id)
        
        try:
            # Create PTY
            master, slave = pty.openpty()
            
            # Start shell process
            process = subprocess.Popen(
                ['/bin/bash'],
                stdin=slave,
                stdout=slave,
                stderr=slave,
                start_new_session=True,  # Start in a new process group
                env=os.environ.copy(),   # Copy current environment
                close_fds=True           # Close other file descriptors
            )
            
            # Close slave FD in parent
            os.close(slave)
            
            # Store terminal info
            active_terminals[session_id] = {
                'fd': master,
                'process': process,
                'thread': None,
                'last_activity': datetime.utcnow(),
                'buffer': '',  # Store output buffer for persistence
                'history': []  # Command history
            }
            
            # Start reader thread
            thread = threading.Thread(
                target=TerminalManager._read_output,
                args=(session_id, master, socketio)
            )
            thread.daemon = True
            thread.start()
            
            active_terminals[session_id]['thread'] = thread
            
            print(f"Created terminal session {session_id}")
            return active_terminals[session_id]
        except Exception as e:
            print(f"Error creating terminal session: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    @staticmethod
    def send_input(session_id, data):
        """Send input to terminal session"""
        if session_id not in active_terminals:
            return False
        
        fd = active_terminals[session_id]['fd']
        try:
            os.write(fd, data.encode())
            active_terminals[session_id]['last_activity'] = datetime.utcnow()
            return True
        except Exception as e:
            print(f"Error writing to terminal: {e}")
            return False
    
    @staticmethod
    def send_command(session_id, command, socketio):
        """Send a complete command to terminal session"""
        if session_id not in active_terminals:
            return False
        
        # Store command in history
        if command.strip() and (not active_terminals[session_id]['history'] or 
                               active_terminals[session_id]['history'][-1] != command):
            active_terminals[session_id]['history'].append(command)
            # Limit history size
            if len(active_terminals[session_id]['history']) > 100:
                active_terminals[session_id]['history'] = active_terminals[session_id]['history'][-100:]
        
        # Send command and newline
        result = TerminalManager.send_input(session_id, command + '\n')
        active_terminals[session_id]['last_activity'] = datetime.utcnow()
        return result
    
    @staticmethod
    def close_session(session_id):
        """Close terminal session"""
        if session_id not in active_terminals:
            return False
        
        try:
            # Close file descriptor
            fd = active_terminals[session_id]['fd']
            try:
                os.close(fd)
            except OSError:
                pass
            
            # Terminate process
            process = active_terminals[session_id]['process']
            if process.poll() is None:
                try:
                    # Send SIGTERM
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    
                    # Wait briefly for process to terminate
                    time.sleep(0.5)
                    
                    # If still running, force kill
                    if process.poll() is None:
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                except Exception as e:
                    print(f"Error terminating process: {e}")
            
            # Remove from active terminals
            del active_terminals[session_id]
            print(f"Closed terminal session {session_id}")
            return True
        except Exception as e:
            print(f"Error closing terminal session: {e}")
            return False
    
    @staticmethod
    def _read_output(session_id, fd, socketio):
        """Read output from terminal and send to client"""
        max_read_bytes = 1024 * 4  # 4KB buffer
        
        while True:
            try:
                # Check if terminal session still exists
                if session_id not in active_terminals:
                    break
                
                # Select to wait for data with timeout
                ready_to_read, _, _ = select.select([fd], [], [], 0.1)
                
                if not ready_to_read:
                    # Check if process is still alive
                    process = active_terminals[session_id]['process']
                    if process.poll() is not None:
                        # Process ended, wait a moment then clean up
                        time.sleep(1)
                        if process.poll() is not None:
                            TerminalManager.close_session(session_id)
                            break
                    continue
                
                # Read data from terminal
                try:
                    output = os.read(fd, max_read_bytes)
                    if not output:
                        time.sleep(0.1)
                        continue
                    
                    # Convert to string and store in buffer
                    output_str = output.decode('utf-8', errors='replace')
                    if session_id in active_terminals:
                        active_terminals[session_id]['buffer'] += output_str
                        
                        # Limit buffer size (keep last 50KB)
                        if len(active_terminals[session_id]['buffer']) > 50000:
                            active_terminals[session_id]['buffer'] = active_terminals[session_id]['buffer'][-50000:]
                    
                    # Send to client
                    socketio.emit('terminal_output', output_str, room=session_id)
                    
                except OSError as e:
                    if e.errno == 5:  # Input/output error
                        break
                    time.sleep(0.1)
            
            except Exception as e:
                print(f"Error in terminal reader: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(0.5)
        
        print(f"Reader thread exiting for session {session_id}")
    
    @staticmethod
    def get_buffer(session_id):
        """Get terminal output buffer"""
        if session_id not in active_terminals:
            return None
        return active_terminals[session_id]['buffer']
    
    @staticmethod
    def get_history(session_id):
        """Get command history"""
        if session_id not in active_terminals:
            return []
        return active_terminals[session_id]['history']