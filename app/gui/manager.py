# app/gui/manager.py - Versión con inicialización lazy
import os
import signal
import subprocess
import psutil
import time
import shutil
from datetime import datetime
from flask import current_app
from app import db
from app.gui.models import GUISession, GUIApplication, GUISessionLog
import traceback

class GUIEnvironmentDetector:
    """Detector del entorno de ejecución para GUI"""
    
    @staticmethod
    def detect_environment():
        """Detecta si estamos en WSL, WSLg, o Linux nativo"""
        env_info = {
            'is_wsl': False,
            'has_wslg': False,
            'is_linux_native': False,
            'display_method': 'unknown',
            'wayland_display': None,
            'x11_display': None
        }
        
        try:
            # Detectar WSL
            if os.path.exists('/proc/version'):
                with open('/proc/version', 'r') as f:
                    proc_version = f.read().lower()
                    if 'microsoft' in proc_version or 'wsl' in proc_version:
                        env_info['is_wsl'] = True
                        # Solo usar logger si hay contexto de app
                        if current_app:
                            current_app.logger.info("Detected WSL environment")
            
            # Detectar WSLg
            wayland_display = os.environ.get('WAYLAND_DISPLAY')
            if wayland_display:
                env_info['has_wslg'] = True
                env_info['wayland_display'] = wayland_display
                env_info['display_method'] = 'wslg'
                if current_app:
                    current_app.logger.info(f"Detected WSLg with Wayland display: {wayland_display}")
            
            # Detectar X11 display
            x11_display = os.environ.get('DISPLAY')
            if x11_display and not env_info['has_wslg']:
                env_info['x11_display'] = x11_display
                if env_info['is_wsl']:
                    env_info['display_method'] = 'wsl_x11'
                else:
                    env_info['display_method'] = 'native_x11'
                if current_app:
                    current_app.logger.info(f"Detected X11 display: {x11_display}")
            
            # Si no es WSL, es Linux nativo
            if not env_info['is_wsl']:
                env_info['is_linux_native'] = True
                env_info['display_method'] = 'native_x11' if x11_display else 'headless'
                if current_app:
                    current_app.logger.info("Detected native Linux environment")
            
            return env_info
            
        except Exception as e:
            # Solo usar logger si hay contexto de app, sino imprimir
            if current_app:
                current_app.logger.error(f"Error detecting environment: {e}")
            else:
                print(f"Error detecting GUI environment: {e}")
            return env_info

class WSLgGUIManager:
    """Manager para WSLg - apps GUI nativas en Windows"""
    
    @staticmethod
    def create_session(application, user_id, session_name, **kwargs):
        """Crear sesión GUI directa en WSLg"""
        try:
            current_app.logger.info(f"Creating WSLg GUI session for {application.name}")
            
            # Crear registro de sesión
            session = GUISession(
                name=session_name,
                application_id=application.id,
                user_id=user_id,
                display_number=0,  # WSLg maneja esto automáticamente
                vnc_port=None,     # No necesitamos VNC
                screen_resolution="native",
                color_depth=32
            )
            
            db.session.add(session)
            db.session.commit()
            
            # Preparar entorno
            env = os.environ.copy()
            
            # Agregar variables específicas para WSLg
            env.update({
                'LIBGL_ALWAYS_INDIRECT': '1',
                'PULSE_SERVER': 'unix:/mnt/wslg/PulseServer',
                'WAYLAND_DISPLAY': env.get('WAYLAND_DISPLAY', 'wayland-0'),
                'XDG_RUNTIME_DIR': '/mnt/wslg/runtime-dir',
                'GTK_THEME': 'Default',
                'QT_X11_NO_MITSHM': '1'
            })
            
            # Añadir variables específicas de la aplicación
            app_env = application.get_environment_dict()
            env.update(app_env)
            
            # Preparar comando
            cmd = application.command.split()
            cwd = application.working_directory if application.working_directory else None
            
            current_app.logger.info(f"Starting WSLg application: {' '.join(cmd)}")
            
            # Iniciar aplicación directamente
            process = subprocess.Popen(
                cmd, 
                env=env, 
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid
            )
            
            # Esperar un momento y verificar que inició
            time.sleep(2)
            
            if process.poll() is None:
                session.app_pid = process.pid
                session.xvfb_pid = None
                session.x11vnc_pid = None
                db.session.commit()
                
                current_app.logger.info(f"WSLg application started successfully (PID: {process.pid})")
                
                WSLgGUIManager._log_session_event(
                    session, 'session_start', 
                    f'WSLg GUI session started for {application.name}',
                    {'display_method': 'wslg', 'pid': process.pid}
                )
                
                return True, session
            else:
                stdout, stderr = process.communicate()
                error_msg = f"Application failed to start."
                if stderr:
                    error_msg += f" Error: {stderr.decode()}"
                
                current_app.logger.error(error_msg)
                
                session.active = False
                session.end_time = datetime.utcnow()
                db.session.commit()
                
                return False, error_msg
                
        except Exception as e:
            current_app.logger.error(f"Error creating WSLg session: {e}")
            return False, f"Error creating WSLg session: {str(e)}"
    
    @staticmethod
    def close_session(session):
        """Cerrar sesión WSLg"""
        try:
            if session.app_pid:
                current_app.logger.info(f"Closing WSLg session {session.session_id}")
                
                try:
                    os.killpg(os.getpgid(session.app_pid), signal.SIGTERM)
                    time.sleep(2)
                    
                    if WSLgGUIManager._check_process(session.app_pid)['running']:
                        os.killpg(os.getpgid(session.app_pid), signal.SIGKILL)
                        
                except (ProcessLookupError, OSError):
                    pass
                
                session.active = False
                session.end_time = datetime.utcnow()
                db.session.commit()
                
                WSLgGUIManager._log_session_event(
                    session, 'session_end',
                    'WSLg GUI session closed successfully'
                )
                
                return True, "Session closed successfully"
            
        except Exception as e:
            current_app.logger.error(f"Error closing WSLg session: {e}")
            return False, f"Error closing session: {str(e)}"
    
    @staticmethod
    def get_session_status(session):
        """Obtener estado de sesión WSLg"""
        try:
            status = {
                'exists': True,
                'active': session.active,
                'session_data': session.to_dict(),
                'display_method': 'wslg',
                'processes': {}
            }
            
            if session.active and session.app_pid:
                process_status = WSLgGUIManager._check_process(session.app_pid)
                status['processes']['application'] = process_status
                
                if process_status['running']:
                    try:
                        process = psutil.Process(session.app_pid)
                        session.cpu_usage = process.cpu_percent()
                        session.memory_usage = process.memory_percent()
                        session.update_activity()
                        
                        status['session_data']['cpu_usage'] = session.cpu_usage
                        status['session_data']['memory_usage'] = session.memory_usage
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        session.active = False
                        session.end_time = datetime.utcnow()
                        db.session.commit()
                        status['active'] = False
            
            return status
            
        except Exception as e:
            current_app.logger.error(f"Error getting WSLg session status: {e}")
            return {'exists': False, 'error': str(e)}
    
    @staticmethod
    def _check_process(pid):
        """Verificar estado de proceso"""
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
            if current_app:
                current_app.logger.error(f"Error checking process {pid}: {e}")
            return {'running': False, 'pid': pid, 'error': str(e)}
    
    @staticmethod
    def _log_session_event(session, event_type, message, details=None):
        """Log de evento de sesión"""
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

class VNCGUIManager:
    """Manager para VNC tradicional"""
    
    @staticmethod
    def create_session(application, user_id, session_name, resolution=None, color_depth=None):
        """Crear sesión VNC tradicional simplificada"""
        try:
            current_app.logger.info(f"Creating VNC GUI session for {application.name}")
            
            resolution = resolution or "1024x768"
            color_depth = color_depth or 24
            
            # Encontrar puertos disponibles
            display_number = VNCGUIManager._find_available_display()
            if display_number is None:
                return False, "No available X11 displays"
            
            vnc_port = VNCGUIManager._find_available_vnc_port()
            if vnc_port is None:
                return False, "No available VNC ports"
            
            # Crear registro de sesión
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
                # 1. Iniciar Xvfb
                xvfb_pid = VNCGUIManager._start_xvfb(display_number, resolution, color_depth)
                if not xvfb_pid:
                    raise Exception("Failed to start Xvfb")
                
                session.xvfb_pid = xvfb_pid
                db.session.commit()
                
                # 2. Iniciar x11vnc
                x11vnc_pid = VNCGUIManager._start_x11vnc(display_number, vnc_port)
                if not x11vnc_pid:
                    raise Exception("Failed to start x11vnc")
                
                session.x11vnc_pid = x11vnc_pid
                db.session.commit()
                
                # 3. Iniciar aplicación
                app_pid = VNCGUIManager._start_application(application, display_number)
                if not app_pid:
                    raise Exception("Failed to start application")
                
                session.app_pid = app_pid
                db.session.commit()
                
                VNCGUIManager._log_session_event(
                    session, 'session_start',
                    f'VNC GUI session started for {application.name}',
                    {
                        'display': display_number,
                        'vnc_port': vnc_port,
                        'resolution': resolution,
                        'xvfb_pid': xvfb_pid,
                        'x11vnc_pid': x11vnc_pid,
                        'app_pid': app_pid
                    }
                )
                
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
        """Cerrar sesión VNC"""
        try:
            if not session.active:
                return True, "Session already closed"
            
            current_app.logger.info(f"Closing VNC session {session.session_id}")
            
            VNCGUIManager._cleanup_session_processes(session)
            
            session.active = False
            session.end_time = datetime.utcnow()
            db.session.commit()
            
            VNCGUIManager._log_session_event(session, 'session_end', 'VNC session closed successfully')
            
            return True, "Session closed successfully"
            
        except Exception as e:
            current_app.logger.error(f"Error closing VNC session: {e}")
            return False, f"Error closing session: {str(e)}"
    
    @staticmethod
    def get_session_status(session):
        """Obtener estado de sesión VNC"""
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
                    'xvfb': VNCGUIManager._check_process(session.xvfb_pid),
                    'x11vnc': VNCGUIManager._check_process(session.x11vnc_pid),
                    'application': VNCGUIManager._check_process(session.app_pid)
                }
                
                try:
                    if session.app_pid and VNCGUIManager._check_process(session.app_pid)['running']:
                        process = psutil.Process(session.app_pid)
                        session.cpu_usage = process.cpu_percent()
                        session.memory_usage = process.memory_percent()
                        session.update_activity()
                        
                        status['session_data']['cpu_usage'] = session.cpu_usage
                        status['session_data']['memory_usage'] = session.memory_usage
                except:
                    pass
            
            return status
            
        except Exception as e:
            current_app.logger.error(f"Error getting VNC session status: {e}")
            return {'exists': False, 'error': str(e)}
    
    # Métodos helper para VNC
    @staticmethod
    def _start_xvfb(display_number, resolution, color_depth):
        """Iniciar Xvfb simplificado"""
        try:
            cmd = [
                'Xvfb',
                f':{display_number}',
                '-screen', '0', f'{resolution}x{color_depth}',
                '-ac',
                '-nolisten', 'tcp',
                '-dpi', '96'
            ]
            
            current_app.logger.info(f"Starting Xvfb: {' '.join(cmd)}")
            
            process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(3)
            
            if process.poll() is None:
                if VNCGUIManager._test_display(display_number):
                    current_app.logger.info(f"Xvfb started successfully on :{display_number} (PID: {process.pid})")
                    return process.pid
                else:
                    process.terminate()
                    return None
            else:
                current_app.logger.error("Xvfb process died immediately")
                return None
                
        except Exception as e:
            current_app.logger.error(f"Error starting Xvfb: {e}")
            return None
    
    @staticmethod
    def _start_x11vnc(display_number, vnc_port):
        """Iniciar x11vnc simplificado para WSL"""
        try:
            time.sleep(2)
            
            cmd = [
                'x11vnc',
                '-display', f':{display_number}',
                '-rfbport', str(vnc_port),
                '-forever',
                '-shared',
                '-nopw',
                '-noshm',      # Crítico para WSL
                '-noxdamage',
                '-quiet',
                '-bg'
            ]
            
            current_app.logger.info(f"Starting x11vnc: {' '.join(cmd)}")
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            time.sleep(4)
            
            # x11vnc en modo -bg se hace daemon, buscar el PID real
            try:
                result = subprocess.run(['pgrep', '-f', f'x11vnc.*:{display_number}.*{vnc_port}'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0 and result.stdout.strip():
                    real_pid = int(result.stdout.strip().split('\n')[0])
                    current_app.logger.info(f"x11vnc started successfully (PID: {real_pid})")
                    return real_pid
            except:
                pass
            
            # Verificar por puerto
            if not VNCGUIManager._is_port_available(vnc_port):
                current_app.logger.info(f"x11vnc started on port {vnc_port}")
                return 99999  # PID ficticio pero funcional
            
            current_app.logger.error("x11vnc failed to start")
            return None
            
        except Exception as e:
            current_app.logger.error(f"Error starting x11vnc: {e}")
            return None
    
    @staticmethod
    def _start_application(application, display_number):
        """Iniciar aplicación GUI"""
        try:
            env = os.environ.copy()
            env['DISPLAY'] = f':{display_number}'
            
            env.update({
                'XLIB_SKIP_ARGB_VISUALS': '1',
                'QT_X11_NO_MITSHM': '1',
                'GTK_THEME': 'Default'
            })
            
            app_env = application.get_environment_dict()
            env.update(app_env)
            
            cmd = application.command.split()
            cwd = application.working_directory if application.working_directory else None
            
            current_app.logger.info(f"Starting application: {' '.join(cmd)}")
            
            process = subprocess.Popen(cmd, env=env, cwd=cwd,
                                     stdout=subprocess.DEVNULL, 
                                     stderr=subprocess.DEVNULL)
            
            time.sleep(2)
            
            if process.poll() is None:
                current_app.logger.info(f"Application started successfully (PID: {process.pid})")
                return process.pid
            else:
                current_app.logger.error("Application process died immediately")
                return None
                
        except Exception as e:
            current_app.logger.error(f"Error starting application: {e}")
            return None
    
    @staticmethod
    def _find_available_display():
        """Encontrar display X11 disponible"""
        used_displays = set()
        
        active_sessions = GUISession.query.filter_by(active=True).all()
        for session in active_sessions:
            if session.display_number:
                used_displays.add(session.display_number)
        
        for display_num in range(99, 150):
            if display_num not in used_displays:
                try:
                    result = subprocess.run(['xdpyinfo', '-display', f':{display_num}'], 
                                          capture_output=True, timeout=2)
                    if result.returncode != 0:
                        return display_num
                except:
                    return display_num
        
        return None
    
    @staticmethod
    def _find_available_vnc_port():
        """Encontrar puerto VNC disponible"""
        used_ports = set()
        
        active_sessions = GUISession.query.filter_by(active=True).all()
        for session in active_sessions:
            if session.vnc_port:
                used_ports.add(session.vnc_port)
        
        for port in range(5900, 6000):
            if port not in used_ports and VNCGUIManager._is_port_available(port):
                return port
        
        return None
    
    @staticmethod
    def _is_port_available(port):
        """Verificar si un puerto está disponible"""
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('localhost', port))
            sock.close()
            return result != 0
        except:
            return False
    
    @staticmethod
    def _test_display(display_number):
        """Probar que el display X11 funciona"""
        try:
            result = subprocess.run(['xdpyinfo', '-display', f':{display_number}'], 
                                  capture_output=True, timeout=5)
            return result.returncode == 0
        except:
            return False
    
    @staticmethod
    def _cleanup_session_processes(session):
        """Limpiar procesos VNC"""
        processes_to_kill = []
        
        if session.app_pid:
            processes_to_kill.append(('Application', session.app_pid))
        if session.x11vnc_pid:
            processes_to_kill.append(('x11vnc', session.x11vnc_pid))
        if session.xvfb_pid:
            processes_to_kill.append(('Xvfb', session.xvfb_pid))
        
        for process_name, pid in processes_to_kill:
            try:
                if pid and pid != 99999:
                    if VNCGUIManager._check_process(pid)['running']:
                        current_app.logger.info(f"Terminating {process_name} (PID: {pid})")
                        os.kill(pid, signal.SIGTERM)
                        time.sleep(1)
                        
                        if VNCGUIManager._check_process(pid)['running']:
                            os.kill(pid, signal.SIGKILL)
            except (ProcessLookupError, OSError):
                pass
            except Exception as e:
                current_app.logger.error(f"Error killing {process_name} {pid}: {e}")
    
    @staticmethod
    def _check_process(pid):
        """Verificar proceso"""
        return WSLgGUIManager._check_process(pid)
    
    @staticmethod
    def _log_session_event(session, event_type, message, details=None):
        """Log de evento de sesión"""
        return WSLgGUIManager._log_session_event(session, event_type, message, details)

class AdaptiveGUISessionManager:
    """Manager adaptativo que usa WSLg o VNC según el entorno"""
    
    def __init__(self):
        self.env_info = None
        self.use_wslg = None
        self._initialized = False
    
    def _ensure_initialized(self):
        """Inicialización perezosa - solo cuando Flask esté listo"""
        if not self._initialized:
            try:
                self.env_info = GUIEnvironmentDetector.detect_environment()
                self.use_wslg = self.env_info['has_wslg']
                
                if current_app:
                    current_app.logger.info(f"GUI Manager initialized - Display method: {self.env_info['display_method']}")
                    
                    if self.use_wslg:
                        current_app.logger.info("Using WSLg for native GUI integration")
                    else:
                        current_app.logger.info("Using traditional VNC approach")
                
                self._initialized = True
            except Exception as e:
                # Si no hay contexto de Flask, usar detección silenciosa
                self.env_info = GUIEnvironmentDetector.detect_environment()
                self.use_wslg = self.env_info['has_wslg']
                self._initialized = True
                print(f"GUI Manager initialized outside Flask context - Display method: {self.env_info['display_method']}")
    
    def create_session(self, application_id, user_id, session_name=None, 
                      resolution=None, color_depth=None):
        """Crear sesión GUI usando el método apropiado"""
        self._ensure_initialized()
        
        try:
            application = GUIApplication.query.get(application_id)
            if not application:
                return False, "Application not found"
            
            if not application.enabled:
                return False, "Application is disabled"
            
            if not session_name:
                session_name = f"{application.display_name} - {datetime.now().strftime('%H:%M:%S')}"
            
            if self.use_wslg:
                return WSLgGUIManager.create_session(
                    application, user_id, session_name,
                    resolution=resolution, color_depth=color_depth
                )
            else:
                return VNCGUIManager.create_session(
                    application, user_id, session_name, resolution, color_depth
                )
                
        except Exception as e:
            if current_app:
                current_app.logger.error(f"Error in adaptive session creation: {e}")
            return False, f"Error creating session: {str(e)}"
    
    def close_session(self, session_id, user_id=None):
        """Cerrar sesión usando el método apropiado"""
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
        """Obtener estado de sesión"""
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
        """Limpiar sesiones inactivas"""
        self._ensure_initialized()
        
        try:
            active_sessions = GUISession.query.filter_by(active=True).all()
            cleaned_count = 0
            
            for session in active_sessions:
                if self.use_wslg:
                    if session.app_pid:
                        if not WSLgGUIManager._check_process(session.app_pid)['running']:
                            if current_app:
                                current_app.logger.info(f"Cleaning up dead WSLg session {session.session_id}")
                            session.active = False
                            session.end_time = datetime.utcnow()
                            cleaned_count += 1
                else:
                    xvfb_alive = VNCGUIManager._check_process(session.xvfb_pid)['running'] if session.xvfb_pid else False
                    x11vnc_alive = VNCGUIManager._check_process(session.x11vnc_pid)['running'] if session.x11vnc_pid else False
                    
                    if not xvfb_alive or not x11vnc_alive:
                        if current_app:
                            current_app.logger.info(f"Cleaning up dead VNC session {session.session_id}")
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
        """Obtener información del entorno (sin inicializar si no es necesario)"""
        if not hasattr(self, 'env_info') or self.env_info is None:
            self.env_info = GUIEnvironmentDetector.detect_environment()
        return self.env_info

# Crear instancia global con inicialización lazy
GUISessionManager = AdaptiveGUISessionManager()