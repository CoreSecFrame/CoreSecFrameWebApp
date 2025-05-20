# app/config.py
import os
from datetime import timedelta
from pathlib import Path

class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'development-key-do-not-use-in-production'
    
    # Set the correct paths
    BASE_DIR = Path(__file__).parent.parent  # This points to the project root
    MODULES_DIR = os.path.join(BASE_DIR, 'modules')  # This points to /modules in project root
    
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + str(BASE_DIR / 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Logs directory
    LOGS_DIR = os.path.join(BASE_DIR, 'logs')
    
    # Modules repository URL
    MODULES_REPOSITORY_URL = os.environ.get('MODULES_REPOSITORY_URL') or \
        'https://github.com/CoreSecFrame/CoreSecFrame-Modules'
    
    # Security settings
    SESSION_COOKIE_SECURE = False  # Set to True in production
    REMEMBER_COOKIE_SECURE = False  # Set to True in production
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    
    # File upload settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload

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