# app/config.py
import os
from pathlib import Path

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-replace-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + str(Path(__file__).parent.parent / 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Application specific paths
    BASE_DIR = Path(__file__).parent.parent
    MODULES_DIR = BASE_DIR / 'modules'
    LOGS_DIR = BASE_DIR / 'logs'
    
    # Security settings
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    
    # File upload settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload