# app/gui/__init__.py - Versión con lazy loading

from flask import current_app

def init_gui_module(app):
    """Initialize the GUI module with lazy environment detection"""
    try:
        # Check if blueprint is already registered
        if 'gui' not in [bp.name for bp in app.blueprints.values()]:
            # Import here to avoid circular imports
            from app.gui.routes import gui_bp
            
            # Register blueprint
            app.register_blueprint(gui_bp)
            app.logger.info("GUI blueprint registered successfully")
        else:
            app.logger.warning("GUI blueprint already registered, skipping")
            return
        
        # Import GUISessionManager here (lazy loading)
        from app.gui.manager import GUISessionManager
        
        # Force initialization now that Flask context is available
        GUISessionManager._ensure_initialized()
        
        # Check system requirements based on detected environment
        env_info = GUISessionManager.get_environment_info()
        check_system_requirements(env_info)
        
        # Set up cleanup scheduler if needed
        setup_cleanup_scheduler(app)
        
        app.logger.info("GUI module initialized successfully")
        app.logger.info(f"Display method: {env_info['display_method']}")
        
    except Exception as e:
        app.logger.error(f"Failed to initialize GUI module: {e}")
        raise

def check_system_requirements(env_info):
    """Check system requirements based on detected environment"""
    import shutil
    
    if env_info['has_wslg']:
        # WSLg requirements - much simpler!
        current_app.logger.info("=== WSLg Environment Detected ===")
        current_app.logger.info("✓ Using native Windows GUI integration")
        current_app.logger.info("✓ No VNC or Xvfb required")
        
        # Check basic tools
        missing_tools = []
        basic_tools = ['python3', 'ps', 'pkill']
        
        for tool in basic_tools:
            if not shutil.which(tool):
                missing_tools.append(tool)
        
        if missing_tools:
            error_msg = f"Missing basic tools for WSLg: {', '.join(missing_tools)}"
            current_app.logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        # Test WSLg functionality
        if not test_wslg_functionality():
            current_app.logger.warning("WSLg may not be fully functional")
            
        current_app.logger.info("✓ WSLg requirements satisfied")
        
    else:
        # Traditional VNC requirements
        current_app.logger.info("=== Traditional VNC Environment ===")
        
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
            if not env_info['is_wsl']:
                # En Linux nativo, estos son críticos
                raise RuntimeError(error_msg)
            else:
                # En WSL sin WSLg, advertir pero continuar
                current_app.logger.warning("VNC tools missing in WSL - consider upgrading to WSLg")
        
        current_app.logger.info("Traditional VNC requirements checked")

def test_wslg_functionality():
    """Test if WSLg is working properly"""
    try:
        import subprocess
        import os
        
        # Check if we can access the display
        env = os.environ.copy()
        
        if 'WAYLAND_DISPLAY' in env:
            # Test Wayland
            result = subprocess.run(['echo', '$WAYLAND_DISPLAY'], 
                                  capture_output=True, timeout=5, env=env)
            current_app.logger.info(f"Wayland display: {env.get('WAYLAND_DISPLAY')}")
            
        if 'DISPLAY' in env:
            # Test X11
            try:
                result = subprocess.run(['xset', 'q'], 
                                      capture_output=True, timeout=5, env=env)
                if result.returncode == 0:
                    current_app.logger.info("X11 display accessible")
                    return True
            except:
                pass
        
        # Test if we can run a simple GUI command
        try:
            result = subprocess.run(['which', 'xcalc'], 
                                  capture_output=True, timeout=5)
            if result.returncode == 0:
                current_app.logger.info("Basic GUI applications available")
                return True
        except:
            pass
        
        return False
        
    except Exception as e:
        current_app.logger.warning(f"Could not test WSLg functionality: {e}")
        return False

def setup_cleanup_scheduler(app):
    """Set up automatic cleanup of inactive sessions"""
    try:
        # This could be extended to use APScheduler or similar
        # For now, we'll rely on the API endpoint for scheduled cleanup
        app.logger.info("GUI session cleanup can be scheduled via /gui/api/maintenance/cleanup")
        
    except Exception as e:
        app.logger.warning(f"Could not set up cleanup scheduler: {e}")

def create_default_applications():
    """Create default GUI applications based on environment"""
    from app import db
    from app.gui.models import GUIApplication, GUICategory
    from app.gui.manager import GUIEnvironmentDetector
    
    try:
        # Check if we already have applications
        if GUIApplication.query.count() > 0:
            return
        
        # Detect environment
        env_info = GUIEnvironmentDetector.detect_environment()
        
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
        
        # Create applications based on environment
        if env_info['has_wslg']:
            # WSLg applications - pueden usar apps más nativas
            default_apps = [
                {
                    'name': 'firefox',
                    'display_name': 'Firefox Browser',
                    'description': 'Mozilla Firefox web browser (WSLg native)',
                    'category': 'browsers',
                    'command': 'firefox',
                    'icon_path': '/usr/share/pixmaps/firefox.png'
                },
                {
                    'name': 'gedit',
                    'display_name': 'Text Editor',
                    'description': 'GNOME text editor (WSLg native)',
                    'category': 'editors', 
                    'command': 'gedit',
                    'icon_path': '/usr/share/pixmaps/gedit.png'
                },
                {
                    'name': 'calculator',
                    'display_name': 'Calculator',
                    'description': 'Desktop calculator (WSLg native)',
                    'category': 'utilities',
                    'command': 'gnome-calculator',
                    'icon_path': '/usr/share/pixmaps/calculator.png'
                },
                {
                    'name': 'code',
                    'display_name': 'VS Code',
                    'description': 'Visual Studio Code (if installed)',
                    'category': 'editors',
                    'command': 'code',
                    'icon_path': '/usr/share/pixmaps/code.png'
                }
            ]
        else:
            # Traditional VNC applications
            default_apps = [
                {
                    'name': 'xterm',
                    'display_name': 'XTerm Terminal',
                    'description': 'Classic X terminal emulator',
                    'category': 'terminals',
                    'command': 'xterm',
                    'icon_path': '/usr/share/pixmaps/xterm.png'
                },
                {
                    'name': 'xcalc',
                    'display_name': 'X Calculator',
                    'description': 'Basic X11 calculator',
                    'category': 'utilities',
                    'command': 'xcalc',
                    'icon_path': '/usr/share/pixmaps/xcalc.png'
                }
            ]
        
        for app_data in default_apps:
            # Check if command exists before creating application
            import shutil
            command_name = app_data['command'].split()[0]
            if shutil.which(command_name):
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
                current_app.logger.info(f"Added default application: {app_data['name']}")
        
        db.session.commit()
        current_app.logger.info("Default GUI applications created")
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating default applications: {e}")

# Utility functions for templates
def get_session_count():
    """Get total number of sessions"""
    from app.gui.models import GUISession
    return GUISession.query.count()

def get_active_session_count():
    """Get number of active sessions"""
    from app.gui.models import GUISession
    return GUISession.query.filter_by(active=True).count()

def get_application_count():
    """Get total number of applications"""
    from app.gui.models import GUIApplication
    return GUIApplication.query.filter_by(enabled=True).count()

def get_user_active_sessions(user_id):
    """Get active sessions for a specific user"""
    from app.gui.models import GUISession
    return GUISession.query.filter_by(user_id=user_id, active=True).all()

# Template context processors
def gui_context_processor():
    """Add GUI-related variables to template context"""
    try:
        from app.gui.manager import GUIEnvironmentDetector
        env_info = GUIEnvironmentDetector.detect_environment()
        
        return {
            'gui_session_count': get_session_count(),
            'gui_active_session_count': get_active_session_count(),
            'gui_application_count': get_application_count(),
            'gui_environment': env_info['display_method'],
            'gui_uses_wslg': env_info['has_wslg']
        }
    except:
        # Fallback si hay problemas
        return {
            'gui_session_count': 0,
            'gui_active_session_count': 0,
            'gui_application_count': 0,
            'gui_environment': 'unknown',
            'gui_uses_wslg': False
        }

# CLI commands for GUI module
def register_gui_commands(app):
    """Register CLI commands for GUI module management"""
    
    @app.cli.command("gui-init")
    def init_gui():
        """Initialize GUI module with default applications"""
        print("Initializing GUI module...")
        
        try:
            from app.gui.manager import GUIEnvironmentDetector
            env_info = GUIEnvironmentDetector.detect_environment()
            print(f"✓ Environment detected: {env_info['display_method']}")
            
            if env_info['has_wslg']:
                print("✓ Using WSLg for native Windows GUI integration")
            else:
                print("✓ Using traditional VNC approach")
                check_system_requirements(env_info)
            
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
            from app.gui.manager import GUISessionManager
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
            # Detect environment
            from app.gui.manager import GUIEnvironmentDetector
            env_info = GUIEnvironmentDetector.detect_environment()
            
            print("Environment Information:")
            print(f"  Environment Type: {env_info['display_method']}")
            print(f"  Is WSL: {env_info['is_wsl']}")
            print(f"  Has WSLg: {env_info['has_wslg']}")
            print(f"  Is Linux Native: {env_info['is_linux_native']}")
            
            if env_info['wayland_display']:
                print(f"  Wayland Display: {env_info['wayland_display']}")
            if env_info['x11_display']:
                print(f"  X11 Display: {env_info['x11_display']}")
            
            # Check system requirements
            print("\nSystem Requirements:")
            if env_info['has_wslg']:
                print("  ✓ Using WSLg - minimal requirements")
                if test_wslg_functionality():
                    print("  ✓ WSLg functionality test passed")
                else:
                    print("  ⚠ WSLg functionality test failed")
            else:
                check_system_requirements(env_info)
                print("  ✓ Traditional VNC requirements checked")
            
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
                from app.gui.models import GUISession
                sessions = GUISession.query.filter_by(active=True).all()
                for session in sessions:
                    if env_info['has_wslg']:
                        print(f"  - {session.name} (WSLg native, PID: {session.app_pid})")
                    else:
                        print(f"  - {session.name} (Display: :{session.display_number}, VNC: {session.vnc_port})")
            
            # Show available GUI applications
            if total_apps > 0:
                print(f"\nAvailable Applications:")
                from app.gui.models import GUIApplication
                apps = GUIApplication.query.filter_by(enabled=True).limit(5).all()
                for app in apps:
                    status = "✓" if app.installed else "✗"
                    print(f"  {status} {app.display_name} ({app.command})")
                
                if total_apps > 5:
                    print(f"  ... and {total_apps - 5} more")
            
        except Exception as e:
            print(f"✗ Error getting status: {e}")
            return 1
    
    @app.cli.command("gui-test")
    def gui_test():
        """Test GUI functionality"""
        print("Testing GUI Module Functionality")
        print("=" * 35)
        
        try:
            from app.gui.manager import GUIEnvironmentDetector
            env_info = GUIEnvironmentDetector.detect_environment()
            print(f"Environment: {env_info['display_method']}")
            
            if env_info['has_wslg']:
                print("\n=== WSLg Functionality Test ===")
                
                # Test 1: Check environment variables
                import os
                print("Environment Variables:")
                for var in ['WAYLAND_DISPLAY', 'DISPLAY', 'XDG_RUNTIME_DIR']:
                    value = os.environ.get(var, 'Not set')
                    print(f"  {var}: {value}")
                
                # Test 2: Check if we can run GUI apps
                print("\nTesting GUI application availability:")
                test_apps = ['xcalc', 'gedit', 'firefox', 'gnome-calculator']
                
                import shutil
                for app in test_apps:
                    if shutil.which(app):
                        print(f"  ✓ {app} is available")
                    else:
                        print(f"  ✗ {app} is not available")
                
                # Test 3: Try to get display info
                print("\nTesting display access:")
                try:
                    import subprocess
                    result = subprocess.run(['xset', 'q'], capture_output=True, timeout=5)
                    if result.returncode == 0:
                        print("  ✓ X11 display is accessible")
                    else:
                        print("  ⚠ X11 display test failed")
                except Exception as e:
                    print(f"  ⚠ Could not test X11 display: {e}")
                
            else:
                print("\n=== Traditional VNC Test ===")
                
                # Test VNC components
                import shutil
                components = {
                    'Xvfb': 'Virtual X server',
                    'x11vnc': 'VNC server',
                    'xdpyinfo': 'X11 utilities'
                }
                
                print("Required components:")
                all_good = True
                for component, description in components.items():
                    if shutil.which(component):
                        print(f"  ✓ {component} ({description})")
                    else:
                        print(f"  ✗ {component} ({description}) - MISSING")
                        all_good = False
                
                if all_good:
                    print("\n=== VNC Functionality Test ===")
                    print("All required components are available")
                    print("Note: Full VNC test requires running application")
                else:
                    print("\n⚠ Some required components are missing")
                    print("Install with: sudo apt install xvfb x11vnc x11-utils")
            
            print(f"\n{'✓ GUI module test completed' if env_info['has_wslg'] or all_good else '⚠ GUI module has issues'}")
            
        except Exception as e:
            print(f"✗ Error during GUI test: {e}")
            return 1

# Export main components
__all__ = [
    'init_gui_module',
    'check_system_requirements', 
    'create_default_applications',
    'register_gui_commands',
    'gui_context_processor'
]