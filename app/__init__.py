# app/__init__.py
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_socketio import SocketIO
from flask_wtf.csrf import CSRFProtect, CSRFError
import traceback
from pathlib import Path
import os
from app.config import Config

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()
socketio = SocketIO()

def create_app(config_class=Config):
    # Initialize Flask application
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize extensions with app
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    
    # Configure login
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'
    
    # Ensure required directories exist
    os.makedirs(app.config['MODULES_DIR'], exist_ok=True)
    os.makedirs(app.config['LOGS_DIR'], exist_ok=True)
    
    try:
        # Register blueprints
        from app.auth.routes import auth_bp
        from app.core.routes import core_bp
        from app.modules.routes import modules_bp
        from app.sessions.routes import sessions_bp
        from app.terminal.routes import terminal_bp
        from app.admin.routes import admin_bp
        
        app.register_blueprint(auth_bp)
        app.register_blueprint(core_bp)
        app.register_blueprint(modules_bp)
        app.register_blueprint(sessions_bp)
        app.register_blueprint(terminal_bp)
        app.register_blueprint(admin_bp)
        
        # Initialize socketio with app
        socketio.init_app(app, cors_allowed_origins="*")
        
        # Register terminal socket handlers
        register_terminal_handlers(socketio)
        
        # Register error handlers
        register_error_handlers(app)

        return app
        
    except Exception as e:
        print(f"Error creating Flask application: {e}")
        import traceback
        traceback.print_exc()
        return None  # Return None if app creation fails

def register_terminal_handlers(socketio):
    @socketio.on('terminal_connect')
    def terminal_connect(data):
        """Connect to terminal session"""
        from flask_login import current_user
        from flask_socketio import emit, join_room
        from app.terminal.models import TerminalSession
        from app.terminal.manager import TerminalManager
        
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
        
        # Check if session is active
        if session.active:
            # Create or get terminal session
            terminal = TerminalManager.create_session(session_id, socketio)
            
            # Send welcome message
            emit('terminal_output', '\r\nWelcome to CoreSecFrame Terminal\r\n', room=session_id)
        else:
            # For inactive sessions, send a read-only message
            emit('terminal_output', '\r\n[This session is inactive and in read-only mode]\r\n', room=session_id)

    @socketio.on('terminal_input')
    def terminal_input(data):
        """Handle terminal input"""
        from flask_login import current_user
        from app.terminal.models import TerminalSession
        from app.terminal.manager import TerminalManager
        from datetime import datetime
        
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
        
        # Send key to terminal
        TerminalManager.send_input(session_id, key)

    @socketio.on('terminal_command')
    def terminal_command(data):
        """Handle terminal command"""
        from flask_login import current_user
        from flask_socketio import emit
        from app.terminal.models import TerminalSession, TerminalLog
        from app.terminal.manager import TerminalManager
        from datetime import datetime
        
        if not current_user.is_authenticated:
            return
        
        session_id = data.get('session_id')
        command = data.get('command', '')
        
        print(f"Received command: '{command}' for session {session_id}")
        
        session = TerminalSession.query.filter_by(
            session_id=session_id, 
            user_id=current_user.id
        ).first()
        
        if not session:
            return
        
        # Update session activity
        session.last_activity = datetime.utcnow()
        db.session.commit()
        
        # Log the command
        log_command = TerminalLog(
            session_id=session_id,
            event_type='command',
            command=command,
            output=None
        )
        db.session.add(log_command)
        db.session.commit()
        
        # Debug log to confirm successful logging
        print(f"Logged command '{command}' for session {session_id}")
        
        # Send command to terminal
        TerminalManager.send_command(session_id, command, socketio)

    @socketio.on('terminal_newline')
    def terminal_newline(data):
        """Handle empty line submission"""
        from flask_login import current_user
        from app.terminal.manager import TerminalManager
        
        if not current_user.is_authenticated:
            return
        
        session_id = data.get('session_id')
        TerminalManager.send_input(session_id, '\n')
        
    @socketio.on('disconnect')
    def on_disconnect():
        """Handle client disconnect"""
        # We don't close the terminals when the client disconnects
        # because they may reconnect later
        print(f"Client disconnected")

    @socketio.on('terminal_get_buffer')
    def terminal_get_buffer(data):
        """Get terminal buffer for session restoration"""
        from flask_login import current_user
        from flask_socketio import emit
        from app.terminal.models import TerminalSession
        from app.terminal.manager import TerminalManager
        
        if not current_user.is_authenticated:
            return
        
        session_id = data.get('session_id')
        session = TerminalSession.query.filter_by(
            session_id=session_id, 
            user_id=current_user.id
        ).first()
        
        if not session:
            return
        
        print(f"Getting buffer for session {session_id}, active: {session.active}")
        
        # Handle differently based on session status
        if session.active:
            # Get buffer and history from terminal manager for active session
            buffer = TerminalManager.get_buffer(session_id)
            history = TerminalManager.get_history(session_id)
            
            print(f"Active session buffer length: {len(buffer) if buffer else 0}")
            
            # Send buffer to client
            emit('terminal_buffer', {
                'buffer': buffer if buffer else '\r\n$ ',
                'history': history,
                'read_only': False
            })
        else:
            # For inactive sessions, get logs from database
            buffer, history = TerminalManager.get_session_logs(session_id)
            
            print(f"Inactive session buffer length: {len(buffer) if buffer else 0}")
            
            # Send buffer to client with read-only flag
            emit('terminal_buffer', {
                'buffer': buffer,
                'history': history,
                'read_only': True
            })
def register_error_handlers(app):
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404
        
    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error('Server Error: %s', str(error))
        app.logger.error(traceback.format_exc())  # Log the full traceback
        db.session.rollback()
        return render_template('errors/500.html'), 500
        
    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        return render_template('errors/csrf_error.html', reason=error.description), 400