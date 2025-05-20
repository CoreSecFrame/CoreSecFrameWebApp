# app/__init__.py
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_socketio import SocketIO
from flask_wtf.csrf import CSRFProtect
from pathlib import Path
import os
from app.config import Config

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
socketio = SocketIO()
csrf = CSRFProtect()

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
    
    # Register blueprints
    from app.auth.routes import auth_bp
    from app.core.routes import core_bp
    from app.modules.routes import modules_bp
    from app.sessions.routes import sessions_bp
    from app.terminal.routes import terminal_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(core_bp)
    app.register_blueprint(modules_bp)
    app.register_blueprint(sessions_bp)
    app.register_blueprint(terminal_bp)
    
    # Initialize socketio with app
    socketio.init_app(app, cors_allowed_origins="*")
    
    # Register error handlers
    register_error_handlers(app)
    
    return app

def register_error_handlers(app):
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404
        
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('errors/500.html'), 500