# app/gui/__init__.py
"""
GUI module for CoreSecFrame

This module provides functionality for running GUI applications in virtual X11 displays
with VNC access through web browsers using noVNC.

Features:
- Launch GUI applications in isolated X11 displays using Xvfb
- Provide VNC access to GUI sessions using x11vnc
- Web-based GUI access through noVNC integration
- Session management and monitoring
- Process lifecycle management
"""

from flask import current_app
from app.gui.models import GUIApplication, GUISession, GUICategory, GUISessionLog
from app.gui.manager import GUISessionManager
from app.gui.routes import gui_bp

def init_gui_module(app):
    """Initialize the GUI module"""
    try:
        # Check if blueprint is already registered
        if 'gui' not in [bp.name for bp in app.blueprints.values()]:
            # Register blueprint
            app.register_blueprint(gui_bp)
            app.logger.info("GUI blueprint registered successfully")
        else:
            app.logger.warning("GUI blueprint already registered, skipping")
            return
        
        # Check system requirements
        check_system_requirements()
        
        # Set up cleanup scheduler if needed
        setup_cleanup_scheduler(app)
        
        app.logger.info("GUI module initialized successfully")
        
    except Exception as e:
        app.logger.error(f"Failed to initialize GUI module: {e}")
        raise

def check_system_requirements():
    """Check if required system tools are available"""
    import shutil
    
    required_tools = {
        'Xvfb': 'xvfb',
        'x11vnc': 'x11vnc',
        'xdpyinfo': 'x11-utils'
    }
    
    missing_tools = []
    
    for tool, package in required_tools.items():
        if not shutil.which(tool):
            missing_tools.append(f"{tool} (install package: {package})")
    
    if missing_tools:
        error_msg = f"Missing required system tools: {', '.join(missing_tools)}"
        current_app.logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    current_app.logger.info("All required system tools are available")

def setup_cleanup_scheduler(app):
    """Set up automatic cleanup of inactive sessions"""
    try:
        # This could be extended to use APScheduler or similar
        # For now, we'll rely on the API endpoint for scheduled cleanup
        app.logger.info("GUI session cleanup can be scheduled via /gui/api/maintenance/cleanup")
        
    except Exception as e:
        app.logger.warning(f"Could not set up cleanup scheduler: {e}")

def create_default_applications():
    """Create default GUI applications if none exist"""
    from app import db
    
    try:
        # Check if we already have applications
        if GUIApplication.query.count() > 0:
            return
        
        # Create default categories
        categories = [
            GUICategory(
                name='browsers',
                display_name='Web Browsers',
                description='Web browsing applications',
                icon_class='bi-globe',
                sort_order=1
            ),
            GUICategory(
                name='editors',
                display_name='Text Editors',
                description='Text and code editors',
                icon_class='bi-file-text',
                sort_order=2
            ),
            GUICategory(
                name='terminals',
                display_name='Terminal Emulators',
                description='Terminal applications',
                icon_class='bi-terminal',
                sort_order=3
            ),
            GUICategory(
                name='utilities',
                display_name='Utilities',
                description='System utilities and tools',
                icon_class='bi-tools',
                sort_order=4
            )
        ]
        
        for category in categories:
            db.session.add(category)
        
        # Create default applications
        default_apps = [
            {
                'name': 'firefox',
                'display_name': 'Firefox Browser',
                'description': 'Mozilla Firefox web browser',
                'category': 'browsers',
                'command': 'firefox',
                'icon_path': '/static/icons/firefox.png'
            },
            {
                'name': 'xterm',
                'display_name': 'XTerm',
                'description': 'Classic X terminal emulator',
                'category': 'terminals',
                'command': 'xterm',
                'icon_path': '/static/icons/xterm.png'
            },
            {
                'name': 'gedit',
                'display_name': 'Text Editor',
                'description': 'GNOME text editor',
                'category': 'editors',
                'command': 'gedit',
                'icon_path': '/static/icons/gedit.png'
            },
            {
                'name': 'calculator',
                'display_name': 'Calculator',
                'description': 'Desktop calculator',
                'category': 'utilities',
                'command': 'gnome-calculator',
                'icon_path': '/static/icons/calculator.png'
            }
        ]
        
        for app_data in default_apps:
            # Check if command exists before creating application
            import shutil
            if shutil.which(app_data['command'].split()[0]):
                app = GUIApplication(
                    name=app_data['name'],
                    display_name=app_data['display_name'],
                    description=app_data['description'],
                    category=app_data['category'],
                    command=app_data['command'],
                    icon_path=app_data['icon_path'],
                    installed=True,
                    enabled=True
                )
                db.session.add(app)
        
        db.session.commit()
        current_app.logger.info("Default GUI applications created")
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating default applications: {e}")

# Utility functions for templates
def get_session_count():
    """Get total number of sessions"""
    return GUISession.query.count()

def get_active_session_count():
    """Get number of active sessions"""
    return GUISession.query.filter_by(active=True).count()

def get_application_count():
    """Get total number of applications"""
    return GUIApplication.query.filter_by(enabled=True).count()

def get_user_active_sessions(user_id):
    """Get active sessions for a specific user"""
    return GUISession.query.filter_by(user_id=user_id, active=True).all()

# Template context processors
def gui_context_processor():
    """Add GUI-related variables to template context"""
    return {
        'gui_session_count': get_session_count(),
        'gui_active_session_count': get_active_session_count(),
        'gui_application_count': get_application_count()
    }

# CLI commands for GUI module
def register_gui_commands(app):
    """Register CLI commands for GUI module management"""
    
    @app.cli.command("gui-init")
    def init_gui():
        """Initialize GUI module with default applications"""
        print("Initializing GUI module...")
        
        try:
            check_system_requirements()
            print("✓ System requirements check passed")
            
            create_default_applications()
            print("✓ Default applications created")
            
            print("GUI module initialization completed successfully!")
            
        except Exception as e:
            print(f"✗ Error initializing GUI module: {e}")
            return 1
    
    @app.cli.command("gui-cleanup")
    def cleanup_gui_sessions():
        """Clean up inactive GUI sessions"""
        print("Cleaning up inactive GUI sessions...")
        
        try:
            cleaned_count = GUISessionManager.cleanup_inactive_sessions()
            print(f"✓ Cleaned up {cleaned_count} inactive sessions")
            
        except Exception as e:
            print(f"✗ Error during cleanup: {e}")
            return 1
    
    @app.cli.command("gui-status")
    def gui_status():
        """Show GUI module status"""
        print("GUI Module Status")
        print("=" * 30)
        
        try:
            # Check system requirements
            print("System Requirements:")
            check_system_requirements()
            print("  ✓ All required tools available")
            
            # Show statistics
            total_apps = get_application_count()
            total_sessions = get_session_count()
            active_sessions = get_active_session_count()
            
            print(f"\nStatistics:")
            print(f"  Applications: {total_apps}")
            print(f"  Total Sessions: {total_sessions}")
            print(f"  Active Sessions: {active_sessions}")
            
            # Show active sessions details
            if active_sessions > 0:
                print(f"\nActive Sessions:")
                sessions = GUISession.query.filter_by(active=True).all()
                for session in sessions:
                    print(f"  - {session.name} (Display: :{session.display_number}, VNC: {session.vnc_port})")
            
        except Exception as e:
            print(f"✗ Error getting status: {e}")
            return 1

# Export main components
__all__ = [
    'gui_bp',
    'GUISessionManager',
    'GUIApplication',
    'GUISession',
    'GUICategory',
    'GUISessionLog',
    'init_gui_module',
    'check_system_requirements',
    'create_default_applications',
    'register_gui_commands',
    'gui_context_processor'
]