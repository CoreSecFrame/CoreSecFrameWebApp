# app/gui/manager.py
import os
import signal
import subprocess
import psutil
import time
import random
import tempfile
import shutil
from datetime import datetime
from flask import current_app
from app import db
from app.gui.models import GUISession, GUIApplication, GUISessionLog
import traceback

class GUISessionManager:
    """Manager for GUI sessions with Xvfb + Fluxbox + x11vnc + noVNC"""
    
    # Configuration
    DISPLAY_START = 99  # Start display numbers from :99
    DISPLAY_END = 199   # End display numbers at :199
    VNC_PORT_START = 5900  # Standard VNC port range
    VNC_PORT_END = 6000
    NOVNC_PORT_START = 6080  # noVNC web interface ports
    NOVNC_PORT_END = 6200
    
    # Default settings
    DEFAULT_RESOLUTION = "1024x768"
    DEFAULT_COLOR_DEPTH = 24
    XVFB_TIMEOUT = 10
    X11VNC_TIMEOUT = 10
    NOVNC_PATH = None  # Will be detected
    
    @classmethod
    def create_session(cls, application_id, user_id, session_name=None, 
                      resolution=None, color_depth=None):
        """Create a new GUI session with full stack"""
        try:
            # Get application
            application = GUIApplication.query.get(application_id)
            if not application:
                return False, "Application not found"
            
            if not application.enabled:
                return False, "Application is disabled"
            
            # Set defaults
            if not session_name:
                session_name = f"{application.display_name} - {datetime.now().strftime('%H:%M:%S')}"
            
            resolution = resolution or cls.DEFAULT_RESOLUTION
            color_depth = color_depth or cls.DEFAULT_COLOR_DEPTH
            
            # Find available ports
            display_number = cls._find_available_display()
            if display_number is None:
                return False, "No available X11 displays"
            
            vnc_port = cls._find_available_vnc_port()
            if vnc_port is None:
                return False, "No available VNC ports"
                
            novnc_port = cls._find_available_novnc_port()
            if novnc_port is None:
                return False, "No available noVNC ports"
            
            # Create session record
            session = GUISession(
                name=session_name,
                application_id=application_id,
                user_id=user_id,
                display_number=display_number,
                vnc_port=vnc_port,
                screen_resolution=resolution,
                color_depth=color_depth
            )
            
            # Add noVNC port to session (we'll need to add this field)
            if not hasattr(session, 'novnc_port'):
                # For now, we'll store it in a way that works
                session.novnc_port = novnc_port
            
            db.session.add(session)
            db.session.commit()
            
            current_app.logger.info(f"Creating GUI session {session.session_id} for application {application.name}")
            
            try:
                # 1. Start Xvfb
                xvfb_pid = cls._start_xvfb(display_number, resolution, color_depth)
                if not xvfb_pid:
                    raise Exception("Failed to start Xvfb")
                
                session.xvfb_pid = xvfb_pid
                db.session.commit()
                
                # 2. Start Fluxbox window manager
                fluxbox_pid = cls._start_fluxbox(display_number)
                if not fluxbox_pid:
                    current_app.logger.warning("Failed to start Fluxbox, continuing without window manager")
                
                # 3. Start x11vnc
                x11vnc_pid = cls._start_x11vnc(display_number, vnc_port)
                if not x11vnc_pid:
                    raise Exception("Failed to start x11vnc")
                
                session.x11vnc_pid = x11vnc_pid
                db.session.commit()
                
                # 4. Start noVNC proxy
                novnc_pid = cls._start_novnc_proxy(vnc_port, novnc_port)
                if not novnc_pid:
                    current_app.logger.warning("Failed to start noVNC proxy")
                
                # 5. Start application
                app_pid = cls._start_application(application, display_number)
                if not app_pid:
                    raise Exception("Failed to start application")
                
                session.app_pid = app_pid
                db.session.commit()
                
                # Log session start
                cls._log_session_event(session, 'session_start', 
                                     f'GUI session started successfully',
                                     {
                                         'display': display_number,
                                         'vnc_port': vnc_port,
                                         'novnc_port': novnc_port,
                                         'resolution': resolution,
                                         'xvfb_pid': xvfb_pid,
                                         'fluxbox_pid': fluxbox_pid,
                                         'x11vnc_pid': x11vnc_pid,
                                         'novnc_pid': novnc_pid,
                                         'app_pid': app_pid
                                     })
                
                # Update application last used
                application.last_used = datetime.utcnow()
                db.session.commit()
                
                current_app.logger.info(f"GUI session {session.session_id} created successfully")
                current_app.logger.info(f"noVNC URL: http://localhost:{novnc_port}/vnc.html")
                
                return True, session
                
            except Exception as e:
                current_app.logger.error(f"Error starting processes for session {session.session_id}: {e}")
                
                # Clean up any started processes
                cls._cleanup_session_processes(session)
                
                # Mark session as inactive
                session.active = False
                session.end_time = datetime.utcnow()
                db.session.commit()
                
                cls._log_session_event(session, 'error', 
                                     f'Failed to start session: {str(e)}')
                
                return False, f"Failed to start session: {str(e)}"
                
        except Exception as e:
            current_app.logger.error(f"Error creating GUI session: {e}")
            current_app.logger.error(traceback.format_exc())
            return False, f"Error creating session: {str(e)}"
    
    @classmethod
    def close_session(cls, session_id, user_id=None):
        """
        Close a GUI session
        
        Args:
            session_id: Session ID to close
            user_id: Optional user ID for permission check
            
        Returns:
            tuple: (success, message)
        """
        try:
            # Get session
            query = GUISession.query.filter_by(session_id=session_id)
            if user_id:
                query = query.filter_by(user_id=user_id)
            
            session = query.first()
            if not session:
                return False, "Session not found"
            
            if not session.active:
                return True, "Session already closed"
            
            current_app.logger.info(f"Closing GUI session {session_id}")
            
            # Clean up processes
            cls._cleanup_session_processes(session)
            
            # Update session
            session.active = False
            session.end_time = datetime.utcnow()
            db.session.commit()
            
            # Log session end
            cls._log_session_event(session, 'session_end', 
                                 'GUI session closed successfully')
            
            current_app.logger.info(f"GUI session {session_id} closed successfully")
            return True, "Session closed successfully"
            
        except Exception as e:
            current_app.logger.error(f"Error closing GUI session {session_id}: {e}")
            current_app.logger.error(traceback.format_exc())
            return False, f"Error closing session: {str(e)}"
    
    @classmethod
    def get_session_status(cls, session_id):
        """
        Get detailed status of a GUI session
        
        Args:
            session_id: Session ID to check
            
        Returns:
            dict: Session status information
        """
        try:
            session = GUISession.query.filter_by(session_id=session_id).first()
            if not session:
                return {'exists': False}
            
            status = {
                'exists': True,
                'active': session.active,
                'session_data': session.to_dict(),
                'processes': {}
            }
            
            if session.active:
                # Check process status
                status['processes'] = {
                    'xvfb': cls._check_process(session.xvfb_pid),
                    'x11vnc': cls._check_process(session.x11vnc_pid),
                    'application': cls._check_process(session.app_pid)
                }
                
                # Update CPU/Memory usage
                try:
                    cpu_total = 0
                    memory_total = 0
                    process_count = 0
                    
                    for pid in [session.xvfb_pid, session.x11vnc_pid, session.app_pid]:
                        if pid and cls._check_process(pid)['running']:
                            try:
                                process = psutil.Process(pid)
                                cpu_total += process.cpu_percent()
                                memory_total += process.memory_percent()
                                process_count += 1
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                pass
                    
                    if process_count > 0:
                        session.cpu_usage = cpu_total / process_count
                        session.memory_usage = memory_total / process_count
                        session.update_activity()
                        
                        status['session_data']['cpu_usage'] = session.cpu_usage
                        status['session_data']['memory_usage'] = session.memory_usage
                        
                except Exception as e:
                    current_app.logger.warning(f"Error updating session stats: {e}")
            
            return status
            
        except Exception as e:
            current_app.logger.error(f"Error getting session status: {e}")
            return {'exists': False, 'error': str(e)}
    
    @classmethod
    def cleanup_inactive_sessions(cls):
        """Clean up sessions with dead processes"""
        try:
            active_sessions = GUISession.query.filter_by(active=True).all()
            cleaned_count = 0
            
            for session in active_sessions:
                # Check if any critical process is dead
                xvfb_alive = cls._check_process(session.xvfb_pid)['running']
                x11vnc_alive = cls._check_process(session.x11vnc_pid)['running']
                app_alive = cls._check_process(session.app_pid)['running']
                
                if not xvfb_alive or not x11vnc_alive:
                    current_app.logger.info(f"Cleaning up dead session {session.session_id}")
                    
                    cls._cleanup_session_processes(session)
                    session.active = False
                    session.end_time = datetime.utcnow()
                    
                    cls._log_session_event(session, 'session_end', 
                                         'Session cleaned up due to dead processes')
                    
                    cleaned_count += 1
            
            if cleaned_count > 0:
                db.session.commit()
                current_app.logger.info(f"Cleaned up {cleaned_count} inactive sessions")
            
            return cleaned_count
            
        except Exception as e:
            current_app.logger.error(f"Error cleaning up sessions: {e}")
            return 0
    
    # Private helper methods
    
    @classmethod
    def _find_available_display(cls):
        """Find an available X11 display number"""
        used_displays = set()
        
        # Get displays from active sessions
        active_sessions = GUISession.query.filter_by(active=True).all()
        for session in active_sessions:
            if session.display_number:
                used_displays.add(session.display_number)
        
        # Check for available display
        for display_num in range(cls.DISPLAY_START, cls.DISPLAY_END + 1):
            if display_num not in used_displays:
                # Double-check by trying to connect
                if not cls._is_display_in_use(display_num):
                    return display_num
        
        return None
    
    @classmethod
    def _find_available_vnc_port(cls):
        """Find an available VNC port"""
        used_ports = set()
        
        # Get ports from active sessions
        active_sessions = GUISession.query.filter_by(active=True).all()
        for session in active_sessions:
            if session.vnc_port:
                used_ports.add(session.vnc_port)
        
        # Check for available port
        for port in range(cls.VNC_PORT_START, cls.VNC_PORT_END + 1):
            if port not in used_ports and cls._is_port_available(port):
                return port
        
        return None
    
    @classmethod
    def _is_display_in_use(cls, display_number):
        """Check if an X11 display is in use"""
        try:
            # Try to connect to the display
            result = subprocess.run(['xdpyinfo', '-display', f':{display_number}'], 
                                  capture_output=True, timeout=2)
            return result.returncode == 0
        except:
            return False
    
    @classmethod
    def _is_port_available(cls, port):
        """Check if a port is available"""
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('localhost', port))
            sock.close()
            return result != 0
        except:
            return False
    
    @classmethod
    def _start_x11vnc(cls, display_number, vnc_port):
        """Start x11vnc server with proper input handling"""
        try:
            # Wait more time for Xvfb to be fully ready
            time.sleep(5)
                        
            cmd = [
                'x11vnc',
                '-display', f':{display_number}',
                '-rfbport', str(vnc_port),
                '-forever',
                '-shared',
                '-nopw',
                '-noxdamage',
                '-quiet',
                '-o', '/dev/null'
            ]

            
            current_app.logger.info(f"Starting x11vnc: {' '.join(cmd)}")
            
            # Start x11vnc
            process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, 
                                    stderr=subprocess.PIPE)
            
            # Wait for x11vnc to start
            time.sleep(4)
            
            # Check if process is still running
            if process.poll() is None:
                # Verify port is actually open
                if not cls._is_port_available(vnc_port):
                    current_app.logger.info(f"x11vnc started successfully on port {vnc_port} (PID: {process.pid})")
                    return process.pid
                else:
                    current_app.logger.error(f"x11vnc process running but port {vnc_port} not accessible")
                    process.terminate()
                    return None
            else:
                # Process died, check stderr
                try:
                    stderr_output = process.stderr.read().decode('utf-8', errors='replace')
                    current_app.logger.error(f"x11vnc process died. Error: {stderr_output}")
                except:
                    current_app.logger.error("x11vnc process died without readable error output")
                return None
                
        except Exception as e:
            current_app.logger.error(f"Error starting x11vnc: {e}")
            return None
            
    @classmethod
    def _start_xvfb(cls, display_number, resolution, color_depth):
        """Start Xvfb server with input device support"""
        try:
            cmd = [
                'Xvfb',
                f':{display_number}',
                '-screen', '0', f'{resolution}x{color_depth}',
                '-ac',  # Disable access control
                '-nolisten', 'tcp',  # Don't listen on TCP
                '-dpi', '96',  # Set DPI
                # EXTENSIONES PARA INPUT
                '+extension', 'GLX',
                '+extension', 'RANDR',
                '+extension', 'RENDER',
                '+extension', 'XFIXES',  # Habilitar XFIXES para cursor
                '+extension', 'DAMAGE',  # Habilitar DAMAGE para actualizaciones
                '+extension', 'COMPOSITE', # Habilitar compositing
                # CONFIGURACIÓN DE INPUT
                '-retro',  # Enable old-style cursor
                # DESHABILITAR PROBLEMÁTICAS
                '-extension', 'DPMS',
                '-extension', 'SCREENSAVER'
            ]
            
            current_app.logger.info(f"Starting Xvfb: {' '.join(cmd)}")
            
            process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, 
                                    stderr=subprocess.DEVNULL)
            
            # Wait for Xvfb to start
            time.sleep(4)
            
            # Check if process is still running
            if process.poll() is None:
                # Verify display is working
                time.sleep(2)
                if cls._is_display_in_use(display_number):
                    current_app.logger.info(f"Xvfb started successfully on :{display_number} (PID: {process.pid})")
                    
                    # Test input capabilities
                    cls._test_display_input(display_number)
                    
                    return process.pid
                else:
                    current_app.logger.error(f"Xvfb process started but display :{display_number} not accessible")
                    process.terminate()
                    return None
            else:
                current_app.logger.error(f"Xvfb process died immediately")
                return None
                
        except Exception as e:
            current_app.logger.error(f"Error starting Xvfb: {e}")
            return None

    @classmethod
    def _test_display_input(cls, display_number):
        """Test if display supports input events"""
        try:
            env = os.environ.copy()
            env['DISPLAY'] = f':{display_number}'
            
            # Test if we can send a simple input event
            result = subprocess.run(['xset', '-display', f':{display_number}', 'q'], 
                                capture_output=True, timeout=5, env=env)
            
            if result.returncode == 0:
                current_app.logger.info(f"Display :{display_number} input test passed")
            else:
                current_app.logger.warning(f"Display :{display_number} input test failed")
                
        except Exception as e:
            current_app.logger.warning(f"Could not test display input: {e}")
    
    @classmethod
    def _start_application(cls, application, display_number):
        """Start the GUI application with optimized settings"""
        try:
            # Prepare environment
            env = os.environ.copy()
            env['DISPLAY'] = f':{display_number}'
            
            # CONFIGURACIÓN PARA MEJOR INTERACCIÓN
            env['XLIB_SKIP_ARGB_VISUALS'] = '1'  # Evitar problemas visuales
            env['QT_X11_NO_MITSHM'] = '1'       # Fix para Qt apps
            env['GTK_THEME'] = 'Default'         # Tema GTK básico
            env['GDK_SYNCHRONIZE'] = '1'         # Sincronización X11
            
            # Add application-specific environment variables
            app_env = application.get_environment_dict()
            env.update(app_env)
            
            # Prepare command
            cmd = application.command.split()
            
            # Set working directory
            cwd = application.working_directory if application.working_directory else None
            
            current_app.logger.info(f"Starting application: {' '.join(cmd)} on display :{display_number}")
            
            process = subprocess.Popen(cmd, env=env, cwd=cwd,
                                    stdout=subprocess.DEVNULL, 
                                    stderr=subprocess.DEVNULL)
            
            # Wait a moment and check if process is still running
            time.sleep(2)
            
            if process.poll() is None:
                current_app.logger.info(f"Application started successfully (PID: {process.pid})")
                return process.pid
            else:
                current_app.logger.error(f"Application process died immediately")
                return None
                
        except Exception as e:
            current_app.logger.error(f"Error starting application: {e}")
            return None

    @classmethod
    def _find_available_novnc_port(cls):
        """Find an available noVNC port"""
        used_ports = set()
        
        # Get ports from active sessions (this would need to be stored)
        # For now, check system ports
        for port in range(cls.NOVNC_PORT_START, cls.NOVNC_PORT_END + 1):
            if cls._is_port_available(port):
                return port
        
        return None

    @classmethod
    def _start_fluxbox(cls, display_number):
        """Start Fluxbox window manager"""
        try:
            # Check if fluxbox is available
            if not shutil.which('fluxbox'):
                current_app.logger.warning("Fluxbox not found, sessions will run without window manager")
                return None
            
            env = os.environ.copy()
            env['DISPLAY'] = f':{display_number}'
            
            current_app.logger.info(f"Starting Fluxbox on display :{display_number}")
            
            process = subprocess.Popen(['fluxbox'], env=env,
                                     stdout=subprocess.DEVNULL, 
                                     stderr=subprocess.DEVNULL)
            
            # Wait a moment for fluxbox to start
            time.sleep(2)
            
            if process.poll() is None:
                current_app.logger.info(f"Fluxbox started successfully (PID: {process.pid})")
                return process.pid
            else:
                current_app.logger.warning("Fluxbox process died immediately")
                return None
                
        except Exception as e:
            current_app.logger.error(f"Error starting Fluxbox: {e}")
            return None

    @classmethod
    def _detect_novnc_path(cls):
        """Detect noVNC installation path"""
        if cls.NOVNC_PATH:
            return cls.NOVNC_PATH
            
        possible_paths = [
            '/usr/share/novnc',
            './novnc',
            '/opt/novnc',
            os.path.expanduser('~/novnc')
        ]
        
        for path in possible_paths:
            if os.path.exists(os.path.join(path, 'utils', 'novnc_proxy')):
                cls.NOVNC_PATH = path
                return path
                
        return None

    @classmethod
    def _start_novnc_proxy(cls, vnc_port, novnc_port):
        """Start noVNC proxy with optimized settings"""
        try:
            novnc_path = cls._detect_novnc_path()
            if not novnc_path:
                current_app.logger.error("noVNC not found")
                return None
            
            proxy_script = os.path.join(novnc_path, 'utils', 'novnc_proxy')
            if not os.path.exists(proxy_script):
                current_app.logger.error(f"noVNC proxy script not found: {proxy_script}")
                return None
            
            cmd = [
                proxy_script,
                '--vnc', f'localhost:{vnc_port}',
                '--listen', str(novnc_port),
                '--web', novnc_path,  # Serve noVNC files
                # '--cert', 'cert.pem',  # Uncomment for HTTPS
                # '--key', 'key.pem'     # Uncomment for HTTPS
            ]
            
            current_app.logger.info(f"Starting noVNC proxy: {' '.join(cmd)}")
            
            process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, 
                                    stderr=subprocess.DEVNULL,
                                    cwd=novnc_path)
            
            # Wait for noVNC to start
            time.sleep(3)
            
            if process.poll() is None and not cls._is_port_available(novnc_port):
                current_app.logger.info(f"noVNC proxy started successfully on port {novnc_port} (PID: {process.pid})")
                return process.pid
            else:
                current_app.logger.error("noVNC proxy failed to start properly")
                if process.poll() is None:
                    process.terminate()
                return None
                
        except Exception as e:
            current_app.logger.error(f"Error starting noVNC proxy: {e}")
            return None

    @classmethod
    def _cleanup_session_processes(cls, session):
        """Clean up all processes for a session including noVNC"""
        processes_to_kill = []
        
        # Add all process types
        if session.app_pid:
            processes_to_kill.append(('Application', session.app_pid))
        if hasattr(session, 'novnc_pid') and session.novnc_pid:
            processes_to_kill.append(('noVNC', session.novnc_pid))
        if hasattr(session, 'fluxbox_pid') and session.fluxbox_pid:
            processes_to_kill.append(('Fluxbox', session.fluxbox_pid))
        if session.x11vnc_pid:
            processes_to_kill.append(('x11vnc', session.x11vnc_pid))
        if session.xvfb_pid:
            processes_to_kill.append(('Xvfb', session.xvfb_pid))
        
        for process_name, pid in processes_to_kill:
            try:
                if cls._check_process(pid)['running']:
                    current_app.logger.info(f"Terminating {process_name} process (PID: {pid})")
                    os.kill(pid, signal.SIGTERM)
                    
                    # Wait a moment for graceful shutdown
                    time.sleep(1)
                    
                    # Force kill if still running
                    if cls._check_process(pid)['running']:
                        current_app.logger.info(f"Force killing {process_name} process (PID: {pid})")
                        os.kill(pid, signal.SIGKILL)
                        
            except (ProcessLookupError, OSError) as e:
                current_app.logger.debug(f"Process {pid} ({process_name}) already dead: {e}")
            except Exception as e:
                current_app.logger.error(f"Error killing {process_name} process {pid}: {e}")
    
    @classmethod
    def _check_process(cls, pid):
        """Check if a process is running"""
        if not pid:
            return {'running': False, 'pid': None}
        
        try:
            process = psutil.Process(pid)
            return {
                'running': process.is_running(),
                'pid': pid,
                'status': process.status(),
                'cpu_percent': process.cpu_percent(),
                'memory_percent': process.memory_percent(),
                'create_time': process.create_time()
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return {'running': False, 'pid': pid}
        except Exception as e:
            current_app.logger.error(f"Error checking process {pid}: {e}")
            return {'running': False, 'pid': pid, 'error': str(e)}
    
    @classmethod
    def _log_session_event(cls, session, event_type, message, details=None):
        """Log a session event"""
        try:
            log_entry = GUISessionLog(
                session_id=session.session_id,
                event_type=event_type,
                message=message
            )
            
            if details:
                log_entry.set_details_dict(details)
            
            db.session.add(log_entry)
            db.session.commit()
            
        except Exception as e:
            current_app.logger.error(f"Error logging session event: {e}")