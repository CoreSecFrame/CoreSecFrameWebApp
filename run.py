#!/usr/bin/env python3
"""
CoreSecFrame - Professional Cybersecurity Framework
Main application entry point
"""

import os
import sys
import logging
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def setup_logging():
    """Configure application logging"""
    logs_dir = os.path.join(os.path.dirname(__file__), 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(logs_dir, 'app.log')),
            logging.StreamHandler(sys.stdout)
        ]
    )

def create_application():
    """Create and configure Flask application"""
    try:
        from app import create_app
        app = create_app()
        
        if app is None:
            logging.error("Failed to create Flask application")
            return None
            
        logging.info(f"Application created successfully")
        logging.info(f"Logs Directory: {os.path.join(os.path.dirname(__file__), 'logs')}")
        
        # Check if running in Docker
        if os.path.exists('/.dockerenv'):
            logging.info("🐳 Running in Docker container")
        else:
            logging.info("🖥️  Running in local environment")
            
        return app
        
    except Exception as e:
        logging.error(f"Error creating application: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """Main application entry point"""
    setup_logging()
    
    logging.info("=" * 50)
    logging.info("🚀 Starting CoreSecFrame")
    logging.info(f"Python Version: {sys.version}")
    logging.info(f"Working Directory: {os.getcwd()}")
    logging.info("=" * 50)
    
    # Create Flask application
    app = create_application()
    if app is None:
        logging.error("❌ Failed to create application")
        sys.exit(1)
    
    # Import socketio after app creation
    try:
        from app import socketio
    except ImportError:
        logging.warning("SocketIO not available, using regular Flask server")
        socketio = None
    
    # Determine host and port
    host = os.environ.get('FLASK_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    logging.info(f"Server will start on: http://{host}:{port}")
    logging.info("=" * 50)
    
    try:
        if socketio is not None:
            # Use SocketIO server with gevent
            logging.info("🔌 Starting with SocketIO support (gevent)")
            socketio.run(
                app,
                host=host,
                port=port,
                debug=debug,
                use_reloader=False,  # Disable reloader to avoid conflicts
                log_output=True
            )
        else:
            # Fallback to regular Flask server
            logging.info("🌐 Starting regular Flask server")
            if debug:
                logging.info("🔧 Starting in development mode")
                app.run(
                    host=host,
                    port=port,
                    debug=True,
                    use_reloader=True,
                    threaded=True
                )
            else:
                logging.info("🚀 Starting in production mode")
                app.run(
                    host=host,
                    port=port,
                    debug=False,
                    threaded=True
                )
            
    except Exception as e:
        logging.error(f"Application startup error: {e}")
        
        # Log the error to database if possible
        try:
            with app.app_context():
                from app.core.models import SystemLog
                from app import db
                
                system_log = SystemLog(
                    level='ERROR',
                    message=f'Application startup failed: {str(e)}',
                    source='run.py',
                    timestamp=datetime.utcnow()
                )
                db.session.add(system_log)
                db.session.commit()
        except Exception as db_error:
            logging.error(f"Database logging error: {db_error}")
        
        sys.exit(1)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logging.info("\n👋 Application stopped by user")
        sys.exit(0)
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)