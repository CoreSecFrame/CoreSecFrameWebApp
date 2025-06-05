# app/gui/manager.py - Optimized version with better error handling and structure
import os
import signal
import subprocess
import psutil
import time
import shutil
import shlex
from datetime import datetime
from flask import current_app
from app import db
from app.gui.models import GUISession, GUIApplication, GUISessionLog
import traceback

class GUIEnvironmentDetector:
    """Detector for GUI execution environment"""
    
    @staticmethod
    def detect_environment():
        """Detect WSL, WSLg, or native Linux environment"""
        env_info = {
            'is_wsl': False,
            'has_wslg': False,
            'is_linux_native': False,
            'display_method': 'unknown',
            'wayland_display': None,
            'x11_display': None
        }
        
        try:
            # Detect WSL
            env_info['is_wsl'] = GUIEnvironmentDetector._detect_wsl()
            
            # Detect WSLg (Wayland display)
            wayland_display = os.environ.get('WAYLAND_DISPLAY')
            if wayland_display:
                env_info['has_wslg'] = True
                env_info['wayland_display'] = wayland_display
                env_info['display_method'] = 'wslg'
                GUIEnvironmentDetector._log_info(f"Detected WSLg with Wayland display: {wayland_display}")
            
            # Detect X11 display
            x11_display = os.environ.get('DISPLAY')
            if x11_display and not env_info['has_wslg']:
                env_info['x11_display'] = x11_display
                env_info['display_method'] = 'wsl_x11' if env_info['is_wsl'] else 'native_x11'
                GUIEnvironmentDetector._log_info(f"Detected X11 display: {x11_display}")
            
            # Set Linux native flag
            if not env_info['is_wsl']:
                env_info['is_linux_native'] = True
                env_info['display_method'] = 'native_x11' if x11_display else 'headless'
                GUIEnvironmentDetector._log_info("Detected native Linux environment")
            
            return env_info
            
        except Exception as e:
            GUIEnvironmentDetector._log_error(f"Error detecting environment: {e}")
            return env_info
    
    @staticmethod
    def _detect_wsl():
        """Detect if running in WSL"""
        try:
            if os.path.exists('/proc/version'):
                with open('/proc/version', 'r') as f:
                    proc_version = f.read().lower()
                    return 'microsoft' in proc_version or 'wsl' in proc_version
        except Exception:
            pass
        return False
    
    @staticmethod
    def _log_info(message):
        """Log info message if possible"""
        if current_app:
            current_app.logger.info(message)
        else:
            print(f"INFO: {message}")
    
    @staticmethod
    def _log_error(message):
        """Log error message if possible"""
        if current_app:
            current_app.logger.error(message)
        else:
            print(f"ERROR: {message}")

class ProcessManager:
    """Utility class for process management"""
    
    @staticmethod
    def check_process(pid):
        """Check process status with comprehensive information"""
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
            ProcessManager._log_error(f"Error checking process {pid}: {e}")
            return {'running': False, 'pid': pid, 'error': str(e)}
    
    @staticmethod
    def terminate_process(pid, process_name="Process", force_kill_delay=1):
        """Terminate process gracefully, then force kill if needed"""
        if not pid or pid == 99999:  # Skip invalid/placeholder PIDs
            return
        
        try:
            if ProcessManager.check_process(pid)['running']:
                ProcessManager._log_info(f"Terminating {process_name} (PID: {pid})")
                os.kill(pid, signal.SIGTERM)
                time.sleep(force_kill_delay)
                
                if ProcessManager.check_process(pid)['running']:
                    ProcessManager._log_info(f"Force killing {process_name} (PID: {pid})")
                    os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, OSError):
            pass  # Process already dead
        except Exception as e:
            ProcessManager._log_error(f"Error killing {process_name} {pid}: {e}")
    
    @staticmethod
    def _log_info(message):
        """Log info message if possible"""
        if current_app:
            current_app.logger.info(message)
    
    @staticmethod
    def _log_error(message):
        """Log error message if possible"""
        if current_app:
            current_app.logger.error(message)

class SessionLogger:
    """Utility class for session logging"""
    
    @staticmethod
    def log_event(session, event_type, message, details=None):
        """Log session event with error handling"""
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
            if current_app:
                current_app.logger.error(f"Error logging session event: {e}")

class WSLgGUIManager:
    """Manager for WSLg native GUI applications"""
    
    @staticmethod
    def create_session(application, user_id, session_name, **kwargs):
        """Create WSLg GUI session"""
        try:
            current_app.logger.info(f"Creating WSLg GUI session for {application.name}")
            
            # Create session record
            session = GUISession(
                name=session_name,
                application_id=application.id,
                user_id=user_id,
                display_number=0,  # WSLg handles this
                vnc_port=None,     # Not needed for WSLg
                screen_resolution="native",
                color_depth=32
            )
            
            db.session.add(session)
            db.session.commit()
            
            # Prepare environment
            env = WSLgGUIManager._prepare_environment(application)
            
            # Start application
            process = WSLgGUIManager._start_application(application, env)
            
            if process and process.poll() is None:
                session.app_pid = process.pid
                db.session.commit()
                
                current_app.logger.info(f"WSLg application started successfully (PID: {process.pid})")
                SessionLogger.log_event(session, 'session_start', 
                                      f'WSLg GUI session started for {application.name}',
                                      {'display_method': 'wslg', 'pid': process.pid})
                
                return True, session
            else:
                error_msg = WSLgGUIManager._get_process_error(process)
                current_app.logger.error(f"Application failed to start: {error_msg}")
                
                session.active = False
                session.end_time = datetime.utcnow()
                db.session.commit()
                
                return False, error_msg
                
        except Exception as e:
            current_app.logger.error(f"Error creating WSLg session: {e}")
            return False, f"Error creating WSLg session: {str(e)}"
    
    @staticmethod
    def close_session(session):
        """Close WSLg session"""
        try:
            if session.app_pid:
                current_app.logger.info(f"Closing WSLg session {session.session_id}")
                ProcessManager.terminate_process(session.app_pid, "WSLg Application")
                
                session.active = False
                session.end_time = datetime.utcnow()
                db.session.commit()
                
                SessionLogger.log_event(session, 'session_end', 'WSLg GUI session closed successfully')
                return True, "Session closed successfully"
            
        except Exception as e:
            current_app.logger.error(f"Error closing WSLg session: {e}")
            return False, f"Error closing session: {str(e)}"
    
    @staticmethod
    def get_session_status(session):
        """Get WSLg session status"""
        try:
            status = {
                'exists': True,
                'active': session.active,
                'session_data': session.to_dict(),
                'display_method': 'wslg',
                'processes': {}
            }
            
            if session.active and session.app_pid:
                process_status = ProcessManager.check_process(session.app_pid)
                status['processes']['application'] = process_status
                
                if process_status['running']:
                    WSLgGUIManager._update_session_stats(session, session.app_pid)
                    status['session_data']['cpu_usage'] = session.cpu_usage
                    status['session_data']['memory_usage'] = session.memory_usage
                else:
                    session.active = False
                    session.end_time = datetime.utcnow()
                    db.session.commit()
                    status['active'] = False
            
            return status
            
        except Exception as e:
            current_app.logger.error(f"Error getting WSLg session status: {e}")
            return {'exists': False, 'error': str(e)}
    
    @staticmethod
    def _prepare_environment(application):
        """Prepare WSLg environment variables"""
        env = os.environ.copy()
        
        # WSLg specific environment
        env.update({
            'LIBGL_ALWAYS_INDIRECT': '1',
            'PULSE_SERVER': 'unix:/mnt/wslg/PulseServer',
            'WAYLAND_DISPLAY': env.get('WAYLAND_DISPLAY', 'wayland-0'),
            'XDG_RUNTIME_DIR': '/mnt/wslg/runtime-dir',
            'GTK_THEME': 'Default',
            'QT_X11_NO_MITSHM': '1'
        })
        
        # Add application-specific environment variables
        app_env = application.get_environment_dict()
        env.update(app_env)
        
        return env
    
    @staticmethod
    def _start_application(application, env):
        """Start WSLg application"""
        cmd = shlex.split(application.command)
        cwd = application.working_directory if application.working_directory else None
        
        current_app.logger.info(f"Starting WSLg application: {' '.join(cmd)}")
        
        return subprocess.Popen(
            cmd, 
            env=env, 
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid
        )
    
    @staticmethod
    def _get_process_error(process):
        """Get error message from failed process"""
        if process:
            try:
                stdout, stderr = process.communicate(timeout=1)
                error_parts = []
                if stderr:
                    error_parts.append(f"Error: {stderr.decode(errors='ignore')}")
                if stdout: # Also capture stdout
                    error_parts.append(f"Output: {stdout.decode(errors='ignore')}")
                
                if not error_parts:
                    return "Application failed to start with no specific error output."
                return "Application failed to start. " + " | ".join(error_parts)
            except subprocess.TimeoutExpired:
                pass
        return "Application failed to start."
    
    @staticmethod
    def _update_session_stats(session, pid):
        """Update session statistics"""
        try:
            process = psutil.Process(pid)
            session.cpu_usage = process.cpu_percent()
            session.memory_usage = process.memory_percent()
            session.update_activity()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

class VNCGUIManager:
    """Manager for traditional VNC GUI sessions"""
    
    @staticmethod
    def create_session(application, user_id, session_name, resolution=None, color_depth=None):
        """Create VNC GUI session with simplified process management"""
        try:
            current_app.logger.info(f"Creating VNC GUI session for {application.name}")
            
            resolution = resolution or "1024x768"
            color_depth = color_depth or 24
            
            # Find available ports
            display_number = VNCGUIManager._find_available_display()
            vnc_port = VNCGUIManager._find_available_vnc_port()
            
            if display_number is None or vnc_port is None:
                return False, "No available display numbers or VNC ports"
            
            # Create session record
            session = GUISession(
                name=session_name,
                application_id=application.id,
                user_id=user_id,
                display_number=display_number,
                vnc_port=vnc_port,
                screen_resolution=resolution,
                color_depth=color_depth
            )
            
            db.session.add(session)
            db.session.commit()
            
            try:
                # Start VNC components
                xvfb_pid = VNCGUIManager._start_xvfb(display_number, resolution, color_depth)
                x11vnc_pid = VNCGUIManager._start_x11vnc(display_number, vnc_port)
                app_pid = VNCGUIManager._start_vnc_application(application, display_number)
                
                if not all([xvfb_pid, x11vnc_pid, app_pid]):
                    raise Exception("Failed to start VNC components")
                
                # Update session with PIDs
                session.xvfb_pid = xvfb_pid
                session.x11vnc_pid = x11vnc_pid
                session.app_pid = app_pid
                db.session.commit()
                
                SessionLogger.log_event(session, 'session_start',
                                      f'VNC GUI session started for {application.name}',
                                      {'display': display_number, 'vnc_port': vnc_port,
                                       'xvfb_pid': xvfb_pid, 'x11vnc_pid': x11vnc_pid, 'app_pid': app_pid})
                
                current_app.logger.info(f"VNC session {session.session_id} created successfully")
                return True, session
                
            except Exception as e:
                current_app.logger.error(f"Error starting VNC processes: {e}")
                VNCGUIManager._cleanup_session_processes(session)
                session.active = False
                session.end_time = datetime.utcnow()
                db.session.commit()
                return False, f"Failed to start VNC session: {str(e)}"
                
        except Exception as e:
            current_app.logger.error(f"Error creating VNC session: {e}")
            return False, f"Error creating VNC session: {str(e)}"
    
    @staticmethod
    def close_session(session):
        """Close VNC session and cleanup processes"""
        try:
            if not session.active:
                return True, "Session already closed"
            
            current_app.logger.info(f"Closing VNC session {session.session_id}")
            VNCGUIManager._cleanup_session_processes(session)
            
            session.active = False
            session.end_time = datetime.utcnow()
            db.session.commit()
            
            SessionLogger.log_event(session, 'session_end', 'VNC session closed successfully')
            return True, "Session closed successfully"
            
        except Exception as e:
            current_app.logger.error(f"Error closing VNC session: {e}")
            return False, f"Error closing session: {str(e)}"
    
    @staticmethod
    def get_session_status(session):
        """Get VNC session status"""
        try:
            status = {
                'exists': True,
                'active': session.active,
                'session_data': session.to_dict(),
                'display_method': 'vnc',
                'processes': {}
            }
            
            if session.active:
                status['processes'] = {
                    'xvfb': ProcessManager.check_process(session.xvfb_pid),
                    'x11vnc': ProcessManager.check_process(session.x11vnc_pid),
                    'application': ProcessManager.check_process(session.app_pid)
                }
                
                # Update session stats if app is running
                if session.app_pid and status['processes']['application']['running']:
                    WSLgGUIManager._update_session_stats(session, session.app_pid)
                    status['session_data']['cpu_usage'] = session.cpu_usage
                    status['session_data']['memory_usage'] = session.memory_usage
            
            return status
            
        except Exception as e:
            current_app.logger.error(f"Error getting VNC session status: {e}")
            return {'exists': False, 'error': str(e)}
    
    # VNC helper methods (simplified versions of existing methods)
    @staticmethod
    def _find_available_display():
        """Find available X11 display number"""
        used_displays = {s.display_number for s in GUISession.query.filter_by(active=True).all() if s.display_number}
        
        for display_num in range(99, 150):
            if display_num not in used_displays:
                try:
                    result = subprocess.run(['xdpyinfo', '-display', f':{display_num}'], 
                                          capture_output=True, timeout=1)
                    if result.returncode != 0:
                        return display_num
                except:
                    return display_num
        return None
    
    @staticmethod
    def _find_available_vnc_port():
        """Find available VNC port"""
        used_ports = {s.vnc_port for s in GUISession.query.filter_by(active=True).all() if s.vnc_port}
        
        for port in range(5900, 6000):
            if port not in used_ports and VNCGUIManager._is_port_available(port):
                return port
        return None
    
    @staticmethod
    def _is_port_available(port):
        """Check if port is available"""
        try:
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(1)
                return sock.connect_ex(('localhost', port)) != 0
        except:
            return False
    
    @staticmethod
    def _start_xvfb(display_number, resolution, color_depth):
        """Start Xvfb server and wait for display to be ready."""
        cmd = ['Xvfb', f':{display_number}', '-screen', '0', f'{resolution}x{color_depth}',
               '-ac', '-nolisten', 'tcp', '-dpi', '96']
        
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            max_wait_time = 3  # seconds
            check_interval = 0.5  # seconds
            elapsed_time = 0
            
            while elapsed_time < max_wait_time:
                if VNCGUIManager._test_display(display_number):
                    if process.poll() is None: # Check if Xvfb is still running
                        current_app.logger.info(f"Xvfb on display :{display_number} started successfully (PID: {process.pid}).")
                        return process.pid
                    else:
                        # Xvfb process died after display test was positive once, this is unlikely but possible
                        current_app.logger.error(f"Xvfb on display :{display_number} (PID: {process.pid}) died after starting.")
                        return None # Xvfb died
                
                # Check if Xvfb process died before display was ready
                if process.poll() is not None:
                    current_app.logger.error(f"Xvfb on display :{display_number} (PID: {process.pid}) failed to start or died. Exit code: {process.returncode}")
                    return None

                time.sleep(check_interval)
                elapsed_time += check_interval
            
            # Timeout reached
            current_app.logger.error(f"Xvfb on display :{display_number} (PID: {process.pid}) failed to become ready within {max_wait_time}s.")
            if process.poll() is None: # If process is still running, terminate it
                try:
                    process.terminate()
                    process.wait(timeout=2) # Wait for termination
                except subprocess.TimeoutExpired:
                    process.kill() # Force kill if it doesn't terminate
                except Exception as term_exc:
                    current_app.logger.error(f"Error terminating unresponsive Xvfb (PID: {process.pid}): {term_exc}")
            return None
            
        except FileNotFoundError:
            current_app.logger.error(f"Xvfb command not found. Is it installed and in PATH?")
            return None
        except Exception as e:
            current_app.logger.error(f"An unexpected error occurred while starting Xvfb: {e}\n{traceback.format_exc()}")
            # Ensure cleanup if Popen object 'process' exists and is running
            if 'process' in locals() and process.poll() is None:
                 try:
                     process.terminate()
                     process.wait(timeout=2)
                 except subprocess.TimeoutExpired:
                     process.kill()
                 except Exception as term_exc:
                    current_app.logger.error(f"Error during cleanup of Xvfb (PID: {process.pid if hasattr(process, 'pid') else 'unknown'}): {term_exc}")
            return None
    
    @staticmethod
    def _start_x11vnc(display_number, vnc_port):
        """Start x11vnc server with better compatibility"""
        
        # Crear directorio temporal si no existe
        pid_dir = "/tmp/coresecframe"
        if not os.path.exists(pid_dir):
            os.makedirs(pid_dir, exist_ok=True)
        
        # Primera versión: intentar sin -pidfile
        cmd = ['x11vnc', '-display', f':{display_number}', '-rfbport', str(vnc_port),
            '-forever', '-shared', '-nopw', '-noshm', '-noxdamage', '-quiet', '-bg']
        
        try:
            current_app.logger.info(f"Starting x11vnc: {' '.join(cmd)}")
            
            # Intentar arrancar x11vnc
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Esperar a que el puerto esté disponible
            max_wait_time = 7
            check_interval = 0.5
            elapsed_time = 0
            
            while elapsed_time < max_wait_time:
                # Verificar si el puerto está siendo usado (esto indica que x11vnc está funcionando)
                if not VNCGUIManager._is_port_available(vnc_port):
                    current_app.logger.info(f"x11vnc port {vnc_port} is now listening after {elapsed_time:.1f}s")
                    
                    # Buscar el PID del proceso x11vnc usando ps
                    try:
                        # Buscar procesos x11vnc que estén usando este display
                        ps_cmd = ['ps', 'aux']
                        ps_process = subprocess.run(ps_cmd, capture_output=True, text=True, timeout=2)
                        
                        if ps_process.returncode == 0:
                            lines = ps_process.stdout.split('\n')
                            for line in lines:
                                # Buscar líneas que contengan x11vnc y nuestro display
                                if 'x11vnc' in line and f':{display_number}' in line and str(vnc_port) in line:
                                    # Extraer PID (segunda columna en ps aux)
                                    parts = line.split()
                                    if len(parts) >= 2 and parts[1].isdigit():
                                        pid = int(parts[1])
                                        current_app.logger.info(f"Found x11vnc PID {pid} using ps command")
                                        return pid
                    except Exception as e:
                        current_app.logger.warning(f"Could not find x11vnc PID using ps: {e}")
                    
                    # Si no podemos encontrar el PID exacto, intentar usar el PID del proceso Popen
                    # (aunque puede no ser el del daemon background)
                    if process.poll() is None:
                        current_app.logger.info(f"Using x11vnc process PID {process.pid} as fallback")
                        return process.pid
                    else:
                        # El proceso inicial ya terminó (modo background), pero el puerto funciona
                        # Retornar un PID placeholder que será validado después
                        current_app.logger.info(f"x11vnc running in background, using placeholder PID")
                        return 99999  # PID placeholder, será ignorado en cleanup si es necesario
                
                # Verificar si el proceso falló
                if process.poll() is not None:
                    stdout, stderr = process.communicate()
                    current_app.logger.error(f"x11vnc process failed. Exit code: {process.returncode}")
                    current_app.logger.error(f"stderr: {stderr.decode()}")
                    return None
                
                time.sleep(check_interval)
                elapsed_time += check_interval
            
            # Timeout alcanzado
            current_app.logger.error(f"x11vnc failed to start within {max_wait_time}s")
            if process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
            return None
            
        except FileNotFoundError:
            current_app.logger.error("x11vnc command not found. Is it installed?")
            return None
        except Exception as e:
            current_app.logger.error(f"Unexpected error starting x11vnc: {e}")
            if 'process' in locals() and process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
            return None
    
    @staticmethod
    def _start_vnc_application(application, display_number):
        """Start application in VNC session with enhanced error handling"""
        env = os.environ.copy()
        env.update({
            'DISPLAY': f':{display_number}',
            'XLIB_SKIP_ARGB_VISUALS': '1',
            'QT_X11_NO_MITSHM': '1',
            'GTK_THEME': 'Default'
        })
        
        app_env = application.get_environment_dict()
        env.update(app_env)
        
        # Parse command properly
        cmd_string = application.command.strip()
        cmd_parts = shlex.split(cmd_string)
        cwd = application.working_directory
        
        current_app.logger.info(f"Starting VNC application '{application.name}' with command: {cmd_string}")
        
        try:
            # First, let's validate the command
            if not cmd_parts:
                raise ValueError("Empty command")
            
            base_command = cmd_parts[0]
            
            # Check if the base command exists and is executable
            command_path = shutil.which(base_command)
            if not command_path:
                # Try to find it with absolute path
                if os.path.isabs(base_command):
                    if not os.path.exists(base_command):
                        raise FileNotFoundError(f"Command file not found: {base_command}")
                    if not os.access(base_command, os.X_OK):
                        raise PermissionError(f"Command file is not executable: {base_command}")
                    command_path = base_command
                else:
                    raise FileNotFoundError(f"Command '{base_command}' not found in PATH")
            
            current_app.logger.info(f"Using command path: {command_path}")
            
            # Create the command list with full path
            if len(cmd_parts) > 1:
                cmd = [command_path] + cmd_parts[1:]
            else:
                cmd = [command_path]
            
            # Log the final command
            current_app.logger.info(f"Final command: {' '.join(cmd)}")
            
            # Check if it's a script that needs special handling
            if command_path.endswith(('.sh', '.py', '.pl', '.rb')):
                current_app.logger.info(f"Detected script file: {command_path}")
                
                # For shell scripts
                if command_path.endswith('.sh'):
                    cmd = ['bash'] + cmd
                # For Python scripts
                elif command_path.endswith('.py'):
                    cmd = ['python3'] + cmd
                # For Perl scripts
                elif command_path.endswith('.pl'):
                    cmd = ['perl'] + cmd
                # For Ruby scripts
                elif command_path.endswith('.rb'):
                    cmd = ['ruby'] + cmd
                
                current_app.logger.info(f"Modified command for script: {' '.join(cmd)}")
            
            # Try to detect if it's a Java application (common for security tools)
            if 'java' in cmd_string.lower() or base_command.endswith('.jar'):
                current_app.logger.info("Detected Java application")
                if not cmd_string.startswith('java'):
                    # If it's a .jar file, prepend java -jar
                    if base_command.endswith('.jar'):
                        cmd = ['java', '-jar'] + cmd
                    else:
                        # Try to find if there's a wrapper script
                        wrapper_script = f"{base_command}.sh"
                        if os.path.exists(wrapper_script):
                            cmd = ['bash', wrapper_script] + cmd_parts[1:]
                            current_app.logger.info(f"Using wrapper script: {wrapper_script}")
            
            # Special handling for common security tools
            if base_command == 'burpsuitepro':
                current_app.logger.info("Detected Burp Suite Pro - looking for proper launcher")
                
                # Common Burp Suite Pro locations
                burp_locations = [
                    '/opt/BurpSuitePro/BurpSuitePro',
                    '/usr/local/bin/burpsuitepro',
                    '/home/*/BurpSuitePro/BurpSuitePro',
                    os.path.expanduser('~/BurpSuitePro/BurpSuitePro'),
                    '/opt/burpsuite_pro/BurpSuitePro'
                ]
                
                found_burp = None
                for location in burp_locations:
                    expanded_location = os.path.expanduser(location)
                    if '*' in expanded_location:
                        # Handle wildcard in home directory
                        import glob
                        matches = glob.glob(expanded_location)
                        for match in matches:
                            if os.path.exists(match) and os.access(match, os.X_OK):
                                found_burp = match
                                break
                        if found_burp:
                            break
                    elif os.path.exists(expanded_location) and os.access(expanded_location, os.X_OK):
                        found_burp = expanded_location
                        break
                
                if found_burp:
                    current_app.logger.info(f"Found Burp Suite Pro at: {found_burp}")
                    cmd = [found_burp] + cmd_parts[1:]
                else:
                    # Try to find burp jar files
                    jar_locations = [
                        '/opt/burpsuite_pro/burpsuite_pro.jar',
                        os.path.expanduser('~/burpsuite_pro.jar'),
                        '/usr/local/share/burpsuite_pro/burpsuite_pro.jar'
                    ]
                    
                    for jar_location in jar_locations:
                        if os.path.exists(jar_location):
                            current_app.logger.info(f"Found Burp Suite Pro JAR at: {jar_location}")
                            cmd = ['java', '-jar', jar_location] + cmd_parts[1:]
                            break
                    else:
                        raise FileNotFoundError(
                            "Burp Suite Pro not found. Please ensure it's installed in one of the standard locations:\n" +
                            "\n".join(burp_locations + jar_locations)
                        )
            
            current_app.logger.info(f"Final command to execute: {' '.join(cmd)}")
            
            # Start the process
            process = subprocess.Popen(
                cmd, 
                env=env, 
                cwd=cwd,
                stdout=subprocess.PIPE,  # Capture output for debugging
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid
            )

            # Wait for a short moment to let the process start or fail quickly
            initial_wait = 0.2
            time.sleep(initial_wait)

            if process.poll() is None:
                # Process started and is running
                current_app.logger.info(f"VNC application '{application.name}' (PID: {process.pid}) started successfully.")
                return process.pid
            else:
                # Process terminated quickly, capture error output
                try:
                    stdout, stderr = process.communicate(timeout=5)
                    stdout_text = stdout.decode('utf-8', errors='ignore') if stdout else ''
                    stderr_text = stderr.decode('utf-8', errors='ignore') if stderr else ''
                    
                    error_msg = f"Application exited with code {process.returncode}"
                    if stderr_text:
                        error_msg += f"\nStderr: {stderr_text[:500]}"
                    if stdout_text:
                        error_msg += f"\nStdout: {stdout_text[:500]}"
                    
                    current_app.logger.error(f"VNC application '{application.name}' failed: {error_msg}")
                    
                except subprocess.TimeoutExpired:
                    error_msg = f"Application exited with code {process.returncode} (output timeout)"
                    current_app.logger.error(f"VNC application '{application.name}' failed: {error_msg}")
                
                return None
                    
        except FileNotFoundError as e:
            current_app.logger.error(f"Command not found for VNC application '{application.name}': {e}")
            raise
        except PermissionError as e:
            current_app.logger.error(f"Permission error for VNC application '{application.name}': {e}")
            raise
        except OSError as e:
            if e.errno == 8:  # Exec format error
                current_app.logger.error(f"Exec format error for '{application.name}': {e}")
                current_app.logger.error(f"This usually means:")
                current_app.logger.error(f"1. The file is not executable")
                current_app.logger.error(f"2. The file is a script without proper shebang")
                current_app.logger.error(f"3. The file is corrupted or wrong architecture")
                current_app.logger.error(f"4. The file needs a specific interpreter")
                
                # Try to provide helpful information
                try:
                    file_info = subprocess.run(['file', base_command], 
                                            capture_output=True, text=True, timeout=5)
                    if file_info.returncode == 0:
                        current_app.logger.error(f"File type: {file_info.stdout.strip()}")
                except:
                    pass
                
                raise OSError(f"Cannot execute '{base_command}': {e}. Check if the file is executable and has proper format.")
            else:
                current_app.logger.error(f"OS error starting VNC application '{application.name}': {e}")
                raise
        except Exception as e:
            current_app.logger.error(f"Unexpected error starting VNC application '{application.name}': {e}")
            current_app.logger.error(traceback.format_exc())
            raise
    
    @staticmethod
    def _test_display(display_number):
        """Test if X11 display is working"""
        try:
            result = subprocess.run(['xdpyinfo', '-display', f':{display_number}'], 
                                  capture_output=True, timeout=2)
            return result.returncode == 0
        except:
            return False
    
    @staticmethod
    def _cleanup_session_processes(session):
        """Clean up all VNC session processes with better error handling"""
        processes = [
            ('Application', session.app_pid),
            ('x11vnc', session.x11vnc_pid),
            ('Xvfb', session.xvfb_pid)
        ]
        
        for process_name, pid in processes:
            if pid and pid != 99999:  # Skip placeholder PID
                ProcessManager.terminate_process(pid, process_name)
            elif pid == 99999 and process_name == 'x11vnc':
                # Intentar terminar x11vnc usando pkill como fallback
                try:
                    subprocess.run(['pkill', '-f', f'x11vnc.*:{session.display_number}'], 
                                capture_output=True, timeout=5)
                    current_app.logger.info(f"Terminated x11vnc using pkill for display :{session.display_number}")
                except Exception as e:
                    current_app.logger.warning(f"Could not terminate x11vnc with pkill: {e}")

    @staticmethod
    def _check_x11vnc_version():
        """Check x11vnc version and capabilities"""
        try:
            result = subprocess.run(['x11vnc', '-version'], capture_output=True, text=True, timeout=5)
            version_info = result.stderr  # x11vnc outputs version to stderr
            
            current_app.logger.info(f"x11vnc version info: {version_info[:200]}...")
            
            # Verificar si soporta -pidfile
            if '-pidfile' in version_info or 'pidfile' in version_info:
                return True
            else:
                current_app.logger.warning("x11vnc does not support -pidfile option")
                return False
                
        except Exception as e:
            current_app.logger.warning(f"Could not check x11vnc version: {e}")
            return False

class AdaptiveGUISessionManager:
    """Adaptive manager that chooses WSLg or VNC based on environment"""
    
    def __init__(self):
        self.env_info = None
        self.use_wslg = None
        self._initialized = False
    
    def _ensure_initialized(self):
        """Lazy initialization"""
        if not self._initialized:
            self.env_info = GUIEnvironmentDetector.detect_environment()
            self.use_wslg = self.env_info['has_wslg']
            self._initialized = True
            
            if current_app:
                current_app.logger.info(f"GUI Manager initialized - Display method: {self.env_info['display_method']}")
    
    def create_session(self, application_id, user_id, session_name=None, **kwargs):
        """Create session using appropriate method"""
        self._ensure_initialized()
        
        try:
            application = GUIApplication.query.get(application_id)
            if not application or not application.enabled:
                return False, "Application not found or disabled"
            
            session_name = session_name or f"{application.display_name} - {datetime.now().strftime('%H:%M:%S')}"
            
            if self.use_wslg:
                return WSLgGUIManager.create_session(application, user_id, session_name, **kwargs)
            else:
                return VNCGUIManager.create_session(application, user_id, session_name, **kwargs)
                
        except Exception as e:
            if current_app:
                current_app.logger.error(f"Error in adaptive session creation: {e}")
            return False, f"Error creating session: {str(e)}"
    
    def close_session(self, session_id, user_id=None):
        """Close session using appropriate method"""
        self._ensure_initialized()
        
        try:
            query = GUISession.query.filter_by(session_id=session_id)
            if user_id:
                query = query.filter_by(user_id=user_id)
            
            session = query.first()
            if not session:
                return False, "Session not found"
            
            if not session.active:
                return True, "Session already closed"
            
            if self.use_wslg:
                return WSLgGUIManager.close_session(session)
            else:
                return VNCGUIManager.close_session(session)
                
        except Exception as e:
            if current_app:
                current_app.logger.error(f"Error closing session: {e}")
            return False, f"Error closing session: {str(e)}"
    
    def get_session_status(self, session_id):
        """Get session status using appropriate method"""
        self._ensure_initialized()
        
        try:
            session = GUISession.query.filter_by(session_id=session_id).first()
            if not session:
                return {'exists': False}
            
            if self.use_wslg:
                return WSLgGUIManager.get_session_status(session)
            else:
                return VNCGUIManager.get_session_status(session)
                
        except Exception as e:
            if current_app:
                current_app.logger.error(f"Error getting session status: {e}")
            return {'exists': False, 'error': str(e)}
    
    def cleanup_inactive_sessions(self):
        """Clean up inactive sessions"""
        self._ensure_initialized()
        
        try:
            active_sessions = GUISession.query.filter_by(active=True).all()
            cleaned_count = 0
            
            for session in active_sessions:
                if self.use_wslg:
                    if session.app_pid and not ProcessManager.check_process(session.app_pid)['running']:
                        session.active = False
                        session.end_time = datetime.utcnow()
                        cleaned_count += 1
                else:
                    # Check VNC processes
                    processes_alive = [
                        ProcessManager.check_process(session.xvfb_pid)['running'] if session.xvfb_pid else False,
                        ProcessManager.check_process(session.x11vnc_pid)['running'] if session.x11vnc_pid else False
                    ]
                    
                    if not any(processes_alive):
                        VNCGUIManager._cleanup_session_processes(session)
                        session.active = False
                        session.end_time = datetime.utcnow()
                        cleaned_count += 1
            
            if cleaned_count > 0:
                db.session.commit()
                if current_app:
                    current_app.logger.info(f"Cleaned up {cleaned_count} inactive sessions")
            
            return cleaned_count
            
        except Exception as e:
            if current_app:
                current_app.logger.error(f"Error cleaning up sessions: {e}")
            return 0
    
    def get_environment_info(self):
        """Get environment information"""
        if not hasattr(self, 'env_info') or self.env_info is None:
            self.env_info = GUIEnvironmentDetector.detect_environment()
        return self.env_info

# Global instance with lazy initialization
GUISessionManager = AdaptiveGUISessionManager()