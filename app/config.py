# app/config.py
import os
from datetime import timedelta
from pathlib import Path

class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'development-key-do-not-use-in-production'
    
    # Set the correct paths
    BASE_DIR = Path(__file__).parent.parent  # This points to the project root
    MODULES_DIR = str(BASE_DIR / 'modules')  # This points to /modules in project root
    
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + str(BASE_DIR / 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Logs directory
    LOGS_DIR = str(BASE_DIR / 'logs')
    
    # Modules repository URL
    MODULES_REPOSITORY_URL = os.environ.get('MODULES_REPOSITORY_URL') or \
        'https://github.com/CoreSecFrame/CoreSecFrame-Modules'

    # Log retention settings
    SECURITY_LOG_RETENTION_DAYS = int(os.environ.get('SECURITY_LOG_RETENTION_DAYS', 90))
    
    # Security settings
    SESSION_COOKIE_SECURE = False  # Set to True in production
    REMEMBER_COOKIE_SECURE = False  # Set to True in production
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    
    # File upload settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload

    # File Manager Path Settings
    # These can be overridden by environment variables in a future enhancement
    # e.g., FILE_MANAGER_ALLOWED_PATHS_JSON = os.environ.get('FILE_MANAGER_ALLOWED_PATHS_JSON', '[]')
    # and then json.loads(FILE_MANAGER_ALLOWED_PATHS_JSON)
    FILE_MANAGER_ALLOWED_PATHS = [
        '/home',
        '/tmp',
        '/var/log',
        '/opt',
        '/usr/local',
        '/etc',
        '/'
    ]
    FILE_MANAGER_RESTRICTED_PATHS = [
        '/proc',
        '/sys',
        '/dev',
        '/run',
        '/boot',
        # '/root' is handled by ADMIN_ONLY_PATHS logic.
        # Restricting it here by default is safer.
        # If an admin truly needs access to /root via file manager,
        # it should be an explicit override or a very conscious decision.
        '/root'
    ]
    # Paths that are generally allowed but require admin privileges
    FILE_MANAGER_ADMIN_ONLY_PATHS = [
        '/',
        '/etc',
        '/root'
    ]
    # Default user path if no path is specified and user is not admin
    # This will be processed with os.path.expanduser('~')
    FILE_MANAGER_DEFAULT_USER_PATH = '~'

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    
    # Use more secure settings
    PERMANENT_SESSION_LIFETIME = timedelta(days=1)
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')

class DevelopmentConfig(Config):
   """Development configuration"""
   DEBUG = True
   TESTING = False
   
   # Development settings
   PERMANENT_SESSION_LIFETIME = timedelta(days=7)
   
   # Development database
   SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
       'sqlite:///' + str(Path(__file__).parent / 'dev.db')

class TestingConfig(Config):
   """Testing configuration"""
   DEBUG = True
   TESTING = True
   
   # Use in-memory database for tests
   SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
   
   # Disable CSRF for testing
   WTF_CSRF_ENABLED = False