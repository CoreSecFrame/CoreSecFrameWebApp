# app/__init__.py - Fixed version with proper error handling
from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, current_user
from flask_socketio import SocketIO
from flask_wtf.csrf import CSRFProtect, CSRFError
import traceback
import importlib.util
from pathlib import Path
import os
import sys
from app.config import Config

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()
socketio = SocketIO()

# Setup module import handling
def setup_module_imports():
    """Custom import handler for modules"""
    class CoreImportFinder:
        """Custom import finder to handle 'core' imports"""
        
        @classmethod
        def find_spec(cls, fullname, path=None, target=None):
            # Check if this is a 'core' import
            if fullname == 'core' or fullname.startswith('core.'):
                # Get the modules directory
                modules_dir = Path(Config.MODULES_DIR)
                
                # If it's 'core' module directly
                if fullname == 'core':
                    core_init = modules_dir / 'core' / '__init__.py'
                    if core_init.exists():
                        return importlib.util.spec_from_file_location(
                            fullname, str(core_init),
                            submodule_search_locations=[str(modules_dir / 'core')]
                        )
                # If it's a submodule of 'core'
                else:
                    submodule = fullname.split('.', 1)[1]
                    core_submodule = modules_dir / 'core' / f"{submodule}.py"
                    if core_submodule.exists():
                        return importlib.util.spec_from_file_location(
                            fullname, str(core_submodule)
                        )
            
            return None
    
    # Register the custom finder
    sys.meta_path.insert(0, CoreImportFinder)

def create_app(config_class=Config):
    # Initialize Flask application
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    try:
        # Initialize extensions with app
        db.init_app(app)
        migrate.init_app(app, db)
        login_manager.init_app(app)
        csrf.init_app(app)
        setup_module_imports()
        
        # Configure login
        login_manager.login_view = 'auth.login'
        login_manager.login_message_category = 'info'
        
        # Ensure required directories exist
        os.makedirs(app.config['MODULES_DIR'], exist_ok=True)
        os.makedirs(app.config['LOGS_DIR'], exist_ok=True)
        
        # Setup comprehensive logging FIRST
        from app.core.logging import setup_logging, log_system_event
        setup_logging(app)
        
        # Log application startup
        log_system_event('application_startup', 'CoreSecFrame application starting up')
        
        # Register blueprints
        from app.auth.routes import auth_bp
        from app.core.routes import core_bp
        from app.modules.routes import modules_bp
        from app.sessions.routes import sessions_bp
        from app.terminal.routes import terminal_bp
        from app.admin.routes import admin_bp
        from app.gui.routes import gui_bp
        from app.file_manager import bp as file_manager_bp # Import file_manager blueprint
        from app.notes import notes_bp
        from app.metaspidey import metaspidey_bp
        from app.bettermitm import bettermitm_bp
        
        app.register_blueprint(auth_bp)
        app.register_blueprint(core_bp)
        app.register_blueprint(modules_bp)
        app.register_blueprint(sessions_bp)
        app.register_blueprint(terminal_bp)
        app.register_blueprint(admin_bp)
        app.register_blueprint(gui_bp)
        app.register_blueprint(file_manager_bp, url_prefix='/file_manager') # Register file_manager blueprint
        app.register_blueprint(notes_bp, url_prefix='/notes')
        app.register_blueprint(metaspidey_bp, url_prefix='/metaspidey')
        app.register_blueprint(bettermitm_bp, url_prefix='/bettermitm')
        
        try:
            from app.gui import init_gui_module, register_gui_commands, gui_context_processor
            
            # Check if GUI blueprint is already registered
            blueprint_names = [bp.name for bp in app.blueprints.values()]
            if 'gui' not in blueprint_names:
                init_gui_module(app)
                register_gui_commands(app)
                
                # Add GUI context processor
                app.context_processor(gui_context_processor)
                
                log_system_event('gui_module_loaded', 'GUI module initialized successfully')
            else:
                app.logger.warning("GUI blueprint already registered, skipping initialization")
                
        except Exception as e:
            app.logger.warning(f"GUI module initialization failed: {e}")
            # Continue without GUI module if it fails
            log_system_event('gui_module_error', f'GUI module failed to load: {e}')
                 
        # Initialize socketio with app
        socketio.init_app(app, cors_allowed_origins="*")
        
        # Register terminal socket handlers
        register_terminal_handlers(socketio)
        
        # Register enhanced error handlers with logging
        register_error_handlers(app)
        
        # Register request logging
        register_request_logging(app)
        
        try:
            from app.gui.routes import gui_bp
            app.logger.info("GUI blueprint registered successfully")
        except ImportError as e:
            app.logger.warning(f"GUI blueprint not available: {e}")
        except Exception as e:
            app.logger.error(f"Error registering GUI blueprint: {e}")
        
        # Register security event handlers (with error handling)
        try:
            register_security_handlers(app)
        except Exception as e:
            app.logger.warning(f"Could not register security handlers (blinker may be missing): {e}")
            # Continue without security event handlers if blinker is not available
        
        # Log successful initialization (This will be moved to run.py to ensure app context)
        # log_system_event('application_ready', 'CoreSecFrame application initialized successfully')
        
        return app
        
    except Exception as e:
        print(f"Error creating Flask application: {e}")
        import traceback
        traceback.print_exc()
        return None  # Return None if app creation fails

def register_request_logging(app):
    """Register comprehensive request logging"""
    try:
        from app.core.logging import log_user_action, log_security_event
        
        @app.before_request
        def log_request():
            """Log incoming requests with security context"""
            # Skip logging for static files and health checks
            if (request.endpoint and 
                (request.endpoint.startswith('static') or 
                 request.path.startswith('/health') or
                 request.path.startswith('/favicon.ico'))):
                return
            
            # Get user context
            user_id = current_user.id if current_user.is_authenticated else None
            ip_address = request.remote_addr
            user_agent = request.headers.get('User-Agent', '')
            
            # Log the request
            app.logger.info(
                f"Request: {request.method} {request.path} from {ip_address}",
                extra={
                    'user_id': user_id,
                    'ip_address': ip_address,
                    'user_agent': user_agent[:100],  # Truncate long user agents
                    'method': request.method,
                    'path': request.path,
                    'endpoint': request.endpoint
                }
            )
            
            # Check for suspicious patterns
            suspicious_patterns = [
                '/admin', '/.env', '/config', '/backup', '/database',
                'eval(', 'exec(', '<script', 'javascript:', 'vbscript:',
                'union select', 'drop table', 'delete from',
                '../', '..\\', '/etc/passwd', '/proc/', '/sys/'
            ]
            
            request_data = f"{request.path} {request.query_string.decode()}"
            if any(pattern in request_data.lower() for pattern in suspicious_patterns):
                log_security_event(
                    f"Suspicious request detected: {request.method} {request.path}",
                    user_id=user_id,
                    ip_address=ip_address
                )
    except ImportError:
        app.logger.warning("Request logging not available - core.logging module not found")

def register_security_handlers(app):
    """Register security event handlers (requires blinker)"""
    try:
        from app.core.logging import log_security_event
        from flask_login import user_logged_in, user_logged_out
        
        @user_logged_in.connect_via(app)
        def on_user_logged_in(sender, user, **extra):
            """Log successful user login"""
            log_security_event(
                f"User login successful: {user.username}",
                user_id=user.id,
                ip_address=request.remote_addr if request else None
            )
        
        @user_logged_out.connect_via(app)
        def on_user_logged_out(sender, user, **extra):
            """Log user logout"""
            log_security_event(
                f"User logout: {user.username}",
                user_id=user.id,
                ip_address=request.remote_addr if request else None
            )
        
        @app.before_request
        def check_security_headers():
            """Check for missing security headers and log warnings"""
            if request.endpoint and not request.endpoint.startswith('static'):
                # Check for common security headers
                if not request.headers.get('X-Requested-With'):
                    if request.method == 'POST' and not request.is_json:
                        app.logger.warning(
                            f"POST request without X-Requested-With header: {request.path}",
                            extra={
                                'user_id': current_user.id if current_user.is_authenticated else None,
                                'ip_address': request.remote_addr,
                                'is_security': True
                            }
                        )
                        
        app.logger.info("Security event handlers registered successfully")
        
    except ImportError as e:
        raise RuntimeError(f"Security handlers require blinker library: {e}")

def register_terminal_handlers(socketio):
    @socketio.on('terminal_connect')
    def terminal_connect(data):
        """Connect to terminal session"""
        from flask_login import current_user
        from flask_socketio import emit, join_room
        from flask import current_app
        from app.terminal.models import TerminalSession
        from app.terminal.manager import TerminalManager
        
        try:
            from app.core.logging import log_user_action
        except ImportError:
            log_user_action = None
        
        if not current_user.is_authenticated:
            current_app.logger.warning(
                "Unauthenticated terminal connection attempt",
                extra={'is_security': True, 'ip_address': request.remote_addr if request else None}
            )
            return
        
        session_id = data.get('session_id')
        session = TerminalSession.query.filter_by(
            session_id=session_id, 
            user_id=current_user.id
        ).first()
        
        if not session:
            current_app.logger.warning(
                f"Terminal connection attempt to non-existent session: {session_id}",
                extra={
                    'user_id': current_user.id,
                    'session_id': session_id,
                    'is_security': True
                }
            )
            return
        
        # Join session room
        join_room(session_id)
        
        # Log terminal connection
        if log_user_action:
            log_user_action(
                current_user.id,
                'terminal_connect',
                f'Connected to terminal session {session_id}',
                session_id=session_id,
                ip_address=request.remote_addr if request else None
            )
        
        # Check if session is active
        if session.active:
            # Create or get terminal session
            terminal = TerminalManager.create_session(current_app._get_current_object(), session_id, socketio)
            
            # Send welcome message
            emit('terminal_output', '\r\nConnected to CoreSecFrame Terminal\r\n', room=session_id)
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
        input_data = data.get('data')
        
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
        TerminalManager.send_input(session_id, input_data)

    @socketio.on('terminal_command')
    def terminal_command(data):
        """Handle terminal command"""
        from flask_login import current_user
        from flask_socketio import emit
        from app.terminal.models import TerminalSession
        from app.terminal.manager import TerminalManager
        from datetime import datetime
        
        try:
            from app.core.logging import log_user_action
        except ImportError:
            log_user_action = None
        
        if not current_user.is_authenticated:
            return
        
        session_id = data.get('session_id')
        command = data.get('command', '')
        
        session = TerminalSession.query.filter_by(
            session_id=session_id, 
            user_id=current_user.id
        ).first()
        
        if not session:
            return
        
        # Log command execution
        if log_user_action:
            log_user_action(
                current_user.id,
                'terminal_command',
                f'Executed command in session {session_id}: {command[:100]}',
                session_id=session_id
            )
        
        # Update session activity
        session.last_activity = datetime.utcnow()
        db.session.commit()
        
        # Send command to terminal
        TerminalManager.send_command(session_id, command, socketio)

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
        
        # Handle differently based on session status
        if session.active:
            # Get buffer and history from terminal manager for active session
            buffer = TerminalManager.get_buffer(session_id)
            history = TerminalManager.get_history(session_id)
            
            # Send buffer to client
            emit('terminal_buffer', {
                'buffer': buffer if buffer else '\r\n$ ',
                'history': history,
                'read_only': False
            })
        else:
            # For inactive sessions, get logs from database
            buffer, history = TerminalManager.get_session_logs(session_id)
            
            # Send buffer to client with read-only flag
            emit('terminal_buffer', {
                'buffer': buffer,
                'history': history,
                'read_only': True
            })
    
    @socketio.on('terminal_resize')
    def terminal_resize(data):
        """Handle terminal resize events"""
        from flask_login import current_user
        from app.terminal.models import TerminalSession
        from app.terminal.manager import TerminalManager
        
        if not current_user.is_authenticated:
            return
        
        session_id = data.get('session_id')
        rows = data.get('rows', 24)
        cols = data.get('cols', 80)
        
        session = TerminalSession.query.filter_by(
            session_id=session_id, 
            user_id=current_user.id
        ).first()
        
        if not session or not session.active:
            return
        
        # Resize the terminal
        TerminalManager.resize_terminal(session_id, rows, cols)

    @socketio.on('disconnect')
    def on_disconnect():
        """Handle client disconnect"""
        from flask_login import current_user
        
        try:
            from app.core.logging import log_user_action
            if current_user.is_authenticated:
                log_user_action(
                    current_user.id,
                    'socket_disconnect',
                    'Socket.IO client disconnected'
                )
        except ImportError:
            pass  # Logging not available

def register_error_handlers(app):
    try:
        from app.core.logging import log_system_event, log_security_event
    except ImportError:
        log_system_event = None
        log_security_event = None
    
    @app.errorhandler(404)
    def not_found_error(error):
        if request.path == '/favicon.ico':
            # Optionally, you can return a 204 No Content response for favicons
            # or just return the standard 404 page without logging.
            # For now, just return the 404 page without logging.
            return render_template('errors/404.html'), 404

        # Log other 404 errors as they might indicate reconnaissance
        app.logger.warning(
            f"404 Not Found: {request.path}",
            extra={
                'user_id': current_user.id if current_user.is_authenticated else None,
                'ip_address': request.remote_addr,
                'user_agent': request.headers.get('User-Agent', '')[:100],
                'is_security': True
            }
        )
        return render_template('errors/404.html'), 404
        
    @app.errorhandler(500)
    def internal_error(error):
        # Log 500 errors as system issues
        app.logger.error(
            f'Server Error: {str(error)}',
            extra={
                'user_id': current_user.id if current_user.is_authenticated else None,
                'ip_address': request.remote_addr,
                'exception_text': traceback.format_exc()
            }
        )
        db.session.rollback()
        return render_template('errors/500.html'), 500
        
    @app.errorhandler(403)
    def forbidden_error(error):
        # Log 403 errors as potential security issues
        if log_security_event:
            log_security_event(
                f"Access forbidden: {request.path}",
                user_id=current_user.id if current_user.is_authenticated else None,
                ip_address=request.remote_addr
            )
        return render_template('errors/403.html'), 403
        
    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        # Log CSRF errors as security events
        if log_security_event:
            log_security_event(
                f"CSRF error: {error.description}",
                user_id=current_user.id if current_user.is_authenticated else None,
                ip_address=request.remote_addr
            )
        return render_template('errors/csrf_error.html', reason=error.description), 400
    
    @app.errorhandler(429)
    def ratelimit_handler(error):
        # Log rate limiting events
        if log_security_event:
            log_security_event(
                f"Rate limit exceeded: {request.path}",
                user_id=current_user.id if current_user.is_authenticated else None,
                ip_address=request.remote_addr
            )
        return render_template('errors/429.html'), 429