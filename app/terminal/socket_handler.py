# Create the file app/terminal/socket_handlers.py with this content
import os
import pty
import select
import subprocess
import threading
from flask_socketio import emit, join_room
from flask_login import current_user
from datetime import datetime
from app import db
from app.terminal.models import TerminalSession

# Store terminal processes
terminals = {}

def register_socket_handlers(socketio):
    @socketio.on('terminal_connect')
    def terminal_connect(data):
        """Connect to terminal session"""
        if not current_user.is_authenticated:
            return
        
        session_id = data.get('session_id')
        session = TerminalSession.query.filter_by(
            session_id=session_id, 
            user_id=current_user.id
        ).first()
        
        if not session:
            return
        
        # Join session room
        join_room(session_id)
        
        # Create terminal process if not exists
        if session_id not in terminals:
            create_terminal_session(session_id, socketio)
        else:
            # Send initial prompt
            emit('terminal_output', '\r\n$ ')

    @socketio.on('terminal_input')
    def terminal_input(data):
        """Handle terminal input"""
        if not current_user.is_authenticated:
            return
        
        session_id = data.get('session_id')
        key = data.get('key')
        
        session = TerminalSession.query.filter_by(
            session_id=session_id, 
            user_id=current_user.id
        ).first()
        
        if not session:
            return
        
        # Update session activity
        session.last_activity = datetime.utcnow()
        db.session.commit()
        
        # Process input
        if session_id in terminals:
            fd = terminals[session_id]['fd']
            try:
                os.write(fd, key.encode())
            except:
                create_terminal_session(session_id, socketio)
                fd = terminals[session_id]['fd']
                os.write(fd, key.encode())

def create_terminal_session(session_id, socketio):
    """Create a new terminal session"""
    # Create PTY
    master, slave = pty.openpty()
    
    # Start shell process
    process = subprocess.Popen(
        ['/bin/bash'],
        stdin=slave,
        stdout=slave,
        stderr=slave,
        close_fds=True
    )
    
    # Close slave FD
    os.close(slave)
    
    # Store terminal info
    terminals[session_id] = {
        'fd': master,
        'process': process
    }
    
    # Start reader thread
    thread = threading.Thread(
        target=read_terminal_output,
        args=(session_id, master, socketio)
    )
    thread.daemon = True
    thread.start()
    
    # Send initial prompt
    socketio.emit('terminal_output', '\r\n$ ', room=session_id)

def read_terminal_output(session_id, fd, socketio):
    """Read output from terminal and send to client"""
    max_read_bytes = 1024
    
    while True:
        try:
            # Check if ready to read
            ready, _, _ = select.select([fd], [], [], 0.1)
            
            if not ready:
                # Check if process is still running
                if session_id not in terminals:
                    break
                
                process = terminals[session_id]['process']
                if process.poll() is not None:
                    close_terminal_session(session_id, socketio)
                    break
                
                continue
            
            # Read output
            output = os.read(fd, max_read_bytes)
            
            if not output:
                close_terminal_session(session_id, socketio)
                break
            
            # Send to client
            socketio.emit(
                'terminal_output',
                output.decode('utf-8', errors='replace'),
                room=session_id
            )
            
        except Exception as e:
            print(f"Error reading terminal output: {e}")
            close_terminal_session(session_id, socketio)
            break

def close_terminal_session(session_id, socketio):
    """Close terminal session"""
    if session_id in terminals:
        # Close FD
        try:
            os.close(terminals[session_id]['fd'])
        except:
            pass
        
        # Kill process
        try:
            terminals[session_id]['process'].kill()
        except:
            pass
        
        # Remove from terminals
        del terminals[session_id]
        
        # Update session in database
        session = TerminalSession.query.filter_by(session_id=session_id).first()
        if session:
            session.active = False
            db.session.commit()