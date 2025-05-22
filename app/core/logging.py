# app/core/logging.py
import os
import logging
import logging.handlers
from pathlib import Path
from datetime import datetime
from flask import current_app
from app import db

class DatabaseLogHandler(logging.Handler):
    """Custom log handler that stores logs in database"""
    
    def emit(self, record):
        """Store log record in database"""
        try:
            from app.core.models import SystemLog
            
            # Create log entry
            log_entry = SystemLog(
                level=record.levelname,
                message=record.getMessage(),
                module=record.module if hasattr(record, 'module') else record.name,
                function=record.funcName,
                line_number=record.lineno,
                pathname=record.pathname,
                timestamp=datetime.fromtimestamp(record.created),
                thread_id=record.thread,
                process_id=record.process,
                exception_text=self.format(record) if record.exc_info else None
            )
            
            # Add extra context if available
            if hasattr(record, 'user_id'):
                log_entry.user_id = record.user_id
            if hasattr(record, 'session_id'):
                log_entry.session_id = record.session_id
            if hasattr(record, 'ip_address'):
                log_entry.ip_address = record.ip_address
            
            db.session.add(log_entry)
            db.session.commit()
            
        except Exception as e:
            # Prevent logging errors from breaking the application
            # Fall back to console logging
            print (f"Database logging error: {e}")
            
class EnhancedFormatter(logging.Formatter):
    """Enhanced formatter with color support for console output"""
    
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green  
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
        'ENDC': '\033[0m'       # End color
    }
    
    def format(self, record):
        # Add color for console output
        if hasattr(record, 'add_color') and record.add_color:
            color = self.COLORS.get(record.levelname, '')
            record.levelname = f"{color}{record.levelname}{self.COLORS['ENDC']}"
        
        # Format the record
        formatted = super().format(record)
        
        # Add extra context
        extras = []
        if hasattr(record, 'user_id'):
            extras.append(f"user_id={record.user_id}")
        if hasattr(record, 'session_id'):
            extras.append(f"session_id={record.session_id}")
        if hasattr(record, 'ip_address'):
            extras.append(f"ip={record.ip_address}")
            
        if extras:
            formatted += f" [{', '.join(extras)}]"
            
        return formatted

class SecurityLogFilter(logging.Filter):
    """Filter to identify and flag security-related events"""
    
    SECURITY_KEYWORDS = [
        'authentication', 'login', 'logout', 'unauthorized', 'forbidden',
        'csrf', 'xss', 'injection', 'attack', 'malicious', 'exploit',
        'breach', 'intrusion', 'suspicious', 'failed_login', 'brute_force'
    ]
    
    def filter(self, record):
        # Check if this is a security-related log
        message_lower = record.getMessage().lower()
        record.is_security = any(keyword in message_lower for keyword in self.SECURITY_KEYWORDS)
        return True

def setup_logging(app):
    """Setup comprehensive logging for the application"""
    
    # Create logs directory
    logs_dir = Path(app.config['LOGS_DIR'])
    logs_dir.mkdir(exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if app.debug else logging.INFO)
    
    # Clear existing handlers to avoid duplicates
    root_logger.handlers.clear()
    
    # 1. Console Handler (with colors in debug mode)
    console_handler = logging.StreamHandler()
    console_formatter = EnhancedFormatter(
        '%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.DEBUG if app.debug else logging.INFO)
    root_logger.addHandler(console_handler)
    
    # 2. File Handler - Application Logs
    app_log_file = logs_dir / 'coresecframe.log'
    file_handler = logging.handlers.RotatingFileHandler(
        app_log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s:%(funcName)s:%(lineno)d - %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    
    # 3. Error Handler - Error Logs Only
    error_log_file = logs_dir / 'errors.log'
    error_handler = logging.handlers.RotatingFileHandler(
        error_log_file,
        maxBytes=5*1024*1024,   # 5MB
        backupCount=3
    )
    error_handler.setFormatter(file_formatter)
    error_handler.setLevel(logging.ERROR)
    root_logger.addHandler(error_handler)
    
    # 4. Security Handler - Security Events
    security_log_file = logs_dir / 'security.log'
    security_handler = logging.handlers.RotatingFileHandler(
        security_log_file,
        maxBytes=5*1024*1024,   # 5MB
        backupCount=5
    )
    security_formatter = logging.Formatter(
        '%(asctime)s [SECURITY-%(levelname)s] %(name)s:%(funcName)s:%(lineno)d - %(message)s'
    )
    security_handler.setFormatter(security_formatter)
    security_handler.addFilter(SecurityLogFilter())
    # Custom filter to only log security events
    security_handler.addFilter(lambda record: getattr(record, 'is_security', False))
    root_logger.addHandler(security_handler)
    
    # 5. Database Handler (if enabled)
    if app.config.get('ENABLE_DATABASE_LOGGING', True):
        db_handler = DatabaseLogHandler()
        db_formatter = logging.Formatter('%(message)s')
        db_handler.setFormatter(db_formatter)
        db_handler.setLevel(logging.WARNING)  # Only store warnings and above
        root_logger.addHandler(db_handler)
    
    # Configure specific loggers
    
    # Flask request logging
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.setLevel(logging.WARNING)  # Reduce noise
    
    # SQLAlchemy logging (debug only)
    if app.debug:
        sql_logger = logging.getLogger('sqlalchemy.engine')
        sql_logger.setLevel(logging.INFO)
    
    # Security-specific logger
    security_logger = logging.getLogger('security')
    security_logger.setLevel(logging.INFO)
    
    # Terminal manager logging
    terminal_logger = logging.getLogger('terminal_manager')
    terminal_logger.setLevel(logging.INFO)
    
    app.logger.info("Comprehensive logging system initialized")
    
    return root_logger

def log_security_event(message, level=logging.WARNING, **kwargs):
    """Log a security-related event"""
    logger = logging.getLogger('security')
    
    # Add security flag
    extra = {'is_security': True}
    extra.update(kwargs)
    
    logger.log(level, message, extra=extra)

def log_user_action(user_id, action, details=None, session_id=None, ip_address=None):
    """Log user actions for audit trail"""
    logger = logging.getLogger('user_actions')
    
    message = f"User {user_id} performed action: {action}"
    if details:
        message += f" - {details}"
    
    extra = {
        'user_id': user_id,
        'session_id': session_id,
        'ip_address': ip_address,
        'is_security': True
    }
    
    logger.info(message, extra=extra)

def log_system_event(event_type, message, level=logging.INFO, **kwargs):
    """Log system events"""
    logger = logging.getLogger('system')
    
    formatted_message = f"[{event_type}] {message}"
    
    logger.log(level, formatted_message, extra=kwargs)

# Context managers for structured logging
class LogContext:
    """Context manager for adding context to logs"""
    
    def __init__(self, **context):
        self.context = context
        self.old_factory = logging.getLogRecordFactory()
    
    def __enter__(self):
        def record_factory(*args, **kwargs):
            record = self.old_factory(*args, **kwargs)
            for key, value in self.context.items():
                setattr(record, key, value)
            return record
        
        logging.setLogRecordFactory(record_factory)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        logging.setLogRecordFactory(self.old_factory)

# Decorators for automatic logging
def log_function_call(logger_name='function_calls', level=logging.DEBUG):
    """Decorator to automatically log function calls"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger = logging.getLogger(logger_name)
            logger.log(level, f"Calling {func.__name__} with args={args}, kwargs={kwargs}")
            
            try:
                result = func(*args, **kwargs)
                logger.log(level, f"{func.__name__} completed successfully")
                return result
            except Exception as e:
                logger.error(f"{func.__name__} failed with error: {e}")
                raise
                
        return wrapper
    return decorator

def log_execution_time(logger_name='performance', level=logging.INFO):
    """Decorator to log function execution time"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            import time
            logger = logging.getLogger(logger_name)
            
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                logger.log(level, f"{func.__name__} executed in {execution_time:.3f}s")
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                logger.error(f"{func.__name__} failed after {execution_time:.3f}s with error: {e}")
                raise
                
        return wrapper
    return decorator