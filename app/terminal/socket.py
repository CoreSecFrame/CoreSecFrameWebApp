# app/terminal/socket.py
from flask_socketio import emit, join_room, leave_room
from app import socketio, db
from flask_login import current_user
from app.terminal.models import TerminalSession, TerminalLog
import subprocess
from datetime import datetime
import os

@socketio.on('join')
def on_join(data):
    if not current_user.is_authenticated:
        return
        
    session_id = data.get('session_id')
    session = TerminalSession.query.filter_by(session_id=session_id, user_id=current_user.id).first()
    
    if not session:
        emit('error', {'message': 'Session not found'})
        return
        
    join_room(session_id)
    emit('status', {'message': f'Joined terminal session: {session.name}'}, room=session_id)

@socketio.on('leave')
def on_leave(data):
    if not current_user.is_authenticated:
        return
        
    session_id = data.get('session_id')
    leave_room(session_id)

@socketio.on('send_command')
def on_send_command(data):
    if not current_user.is_authenticated:
        return
        
    session_id = data.get('session_id')
    command = data.get('command')
    
    session = TerminalSession.query.filter_by(session_id=session_id, user_id=current_user.id).first()
    
    if not session or not session.active:
        emit('error', {'message': 'Session inactive or not found'})
        return
    
    # Update last activity
    session.last_activity = datetime.utcnow()
    db.session.commit()
    
    # Log the command
    log = TerminalLog(
        session_id=session.session_id,
        event_type='command',
        command=command,
        output=None
    )
    db.session.add(log)
    db.session.commit()
    
    # Send command to tmux session
    try:
        subprocess.run([
            'tmux', 'send-keys', '-t', session.session_id,
            command, 'C-m'  # C-m is Enter key
        ], check=True)
        
        # Wait a moment for command to execute
        # Then capture output (this is a simplified approach)
        import time
        time.sleep(0.5)
        
        # Capture output
        result = subprocess.run([
            'tmux', 'capture-pane', '-p', '-t', session.session_id
        ], check=True, capture_output=True, text=True)
        
        output = result.stdout
        
        # Log the output
        log = TerminalLog(
            session_id=session.session_id,
            event_type='output',
            command=None,
            output=output
        )
        db.session.add(log)
        db.session.commit()
        
        # Emit output to clients
        emit('terminal_output', {
            'session_id': session_id,
            'output': output,
            'timestamp': datetime.utcnow().isoformat()
        }, room=session_id)
        
    except subprocess.CalledProcessError as e:
        # Log error
        log = TerminalLog(
            session_id=session.session_id,
            event_type='system',
            command=None,
            output=f"Error executing command: {e}"
        )
        db.session.add(log)
        db.session.commit()
        
        emit('error', {'message': f'Failed to execute command: {str(e)}'}, room=session_id)