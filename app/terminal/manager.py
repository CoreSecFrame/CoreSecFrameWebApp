# app/terminal/manager.py
import os
import pty
import select
import signal
import subprocess
import threading
import time
import glob
import shlex
from datetime import datetime
from flask import current_app
from app import db
from app.terminal.models import TerminalLog

# Store active terminal sessions
active_terminals = {}

class TerminalManager:
    """Manages terminal sessions with comprehensive logging"""
    
    @staticmethod
    def create_session(app, session_id, socketio, allow_create=True):
        """Create a new terminal session or return existing one"""
        # If session exists, return it
        if session_id in active_terminals:
            # Check if process is still running
            process = active_terminals[session_id]['process']
            if process.poll() is None:
                return active_terminals[session_id]
            else:
                # Process ended, clean up
                TerminalManager.close_session(session_id)
        
        # If not allowed to create new sessions, return None
        if not allow_create:
            return None
        
        try:
            # Create PTY
            master, slave = pty.openpty()
            
            # Set terminal size
            try:
                import fcntl
                import termios
                import struct
                # Set default terminal size (80x24)
                term_size = struct.pack("HHHH", 24, 80, 0, 0)
                fcntl.ioctl(slave, termios.TIOCSWINSZ, term_size)
            except Exception as e:
                current_app.logger.warning(f"Failed to set terminal size: {e}")
            
            # Prepare environment
            env = os.environ.copy()
            env['TERM'] = 'xterm-256color'
            env['BASH_COMPLETION_ENABLED'] = '1'
            
            # Start bash with completion enabled
            process = subprocess.Popen(
                ['/bin/bash', '--login'],
                stdin=slave,
                stdout=slave,
                stderr=slave,
                start_new_session=True,
                env=env,
                close_fds=True
            )
            
            # Close slave FD in parent
            os.close(slave)
            
            # Store terminal info with enhanced logging capabilities
            active_terminals[session_id] = {
                'fd': master,
                'process': process,
                'thread': None,
                'last_activity': datetime.utcnow(),
                'full_buffer': '',       # Complete session output
                'input_buffer': '',      # Current input being typed
                'command_history': [],   # All commands executed
                'session_log': [],       # Structured log entries
                'cwd': os.getcwd()
            }
            active_terminals[session_id]['app'] = app
            
            # Start reader thread
            thread = threading.Thread(
                target=TerminalManager._read_output,
                args=(app, session_id, master, socketio)
            )
            thread.daemon = True
            thread.start()
            
            active_terminals[session_id]['thread'] = thread
            
            # Log session creation
            TerminalManager._log_comprehensive_event(app, session_id, 'session_start', 
                                                   message='Terminal session started')
            
            # Send welcome message and setup
            welcome_commands = [
                "export PS1='\\[\\033[01;32m\\]\\u@\\h\\[\\033[00m\\]:\\[\\033[01;34m\\]\\w\\[\\033[00m\\]\\$ '",
                "clear"
            ]
            
            # Execute startup commands
            for cmd in welcome_commands:
                time.sleep(0.1)
                TerminalManager.send_input(session_id, cmd + '\n')
            
            current_app.logger.info(f"Created terminal session {session_id}")
            return active_terminals[session_id]
            
        except Exception as e:
            current_app.logger.error(f"Error creating terminal session: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    @staticmethod
    def send_input(session_id, data):
        """Send input to terminal session with comprehensive logging"""
        if session_id not in active_terminals:
            return False
        
        fd = active_terminals[session_id]['fd']
        try:
            os.write(fd, data.encode())
            active_terminals[session_id]['last_activity'] = datetime.utcnow()
            
            # Track input for command reconstruction
            terminal_info = active_terminals[session_id]
            
            # Handle different input types
            if data == '\n' or data == '\r':
                # Command completed
                current_input = terminal_info.get('input_buffer', '').strip()
                if current_input:
                    app = terminal_info.get('app')
                    if app:
                        # Log the complete command
                        TerminalManager._log_comprehensive_event(
                            app, session_id, 'command_input', 
                            command=current_input,
                            message=f"Command executed: {current_input}"
                        )
                    else:
                        # Consider logging a warning if app is not found
                        pass
                    
                    # Add to command history
                    terminal_info['command_history'].append({
                        'command': current_input,
                        'timestamp': datetime.utcnow(),
                        'cwd': terminal_info.get('cwd', os.getcwd())
                    })
                
                # Reset input buffer
                terminal_info['input_buffer'] = ''
                
            elif data == '\b' or data == '\x7f':
                # Backspace - remove last character
                if terminal_info.get('input_buffer'):
                    terminal_info['input_buffer'] = terminal_info['input_buffer'][:-1]
                    
            elif data.startswith('\x1b'):
                # Escape sequence (arrow keys, etc.) - don't add to input buffer
                pass
                
            elif data == '\t':
                app = terminal_info.get('app')
                if app:
                    # Tab completion - log attempt
                    TerminalManager._log_comprehensive_event(
                        app, session_id, 'tab_completion',
                        message=f"Tab completion on: {terminal_info.get('input_buffer', '')}"
                    )
                else:
                    # Consider logging a warning if app is not found
                    pass
                
            else:
                # Regular character input
                if 'input_buffer' not in terminal_info:
                    terminal_info['input_buffer'] = ''
                terminal_info['input_buffer'] += data
            
            return True
            
        except Exception as e:
            current_app.logger.error(f"Error writing to terminal: {e}")
            return False
    
    @staticmethod
    def _read_output(app, session_id, fd, socketio):
        """Read output from terminal and perform comprehensive logging"""
        import logging
        logger = logging.getLogger('terminal_manager')
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        
        max_read_bytes = 1024 * 4
        output_accumulator = ""  # Accumulate output for better logging
        last_log_time = time.time()
        
        while True:
            try:
                # Check if terminal session still exists
                if session_id not in active_terminals:
                    break
                
                try:
                    # Check if fd is still a valid open file descriptor
                    os.fstat(fd)
                except OSError:
                    # fd is no longer valid (e.g., closed)
                    with app.app_context():
                        logger.warning(f"FD for session {session_id} is no longer valid. Exiting reader thread.")
                    break 
                
                # Select to wait for data with timeout
                ready_to_read, _, _ = select.select([fd], [], [], 0.1)
                
                if not ready_to_read:
                    # Flush accumulated output if enough time has passed
                    current_time = time.time()
                    if output_accumulator and (current_time - last_log_time > 0.5):
                        TerminalManager._log_comprehensive_event(
                            app, session_id, 'terminal_output',
                            output=output_accumulator,
                            message="Terminal output"
                        )
                        output_accumulator = ""
                        last_log_time = current_time
                    
                    # Check if process is still alive
                    process = active_terminals[session_id]['process']
                    if process.poll() is not None:
                        time.sleep(1)
                        if session_id in active_terminals and process.poll() is not None:
                            logger.info(f"Process for session {session_id} has ended")
                            TerminalManager._log_comprehensive_event(
                                app, session_id, 'process_exit',
                                message=f"Process terminated with code {process.poll()}"
                            )
                            TerminalManager.close_session(session_id) # close_session will fetch its own app instance
                            break
                    continue
                
                # Read data from terminal
                try:
                    output = os.read(fd, max_read_bytes)
                    if not output:
                        time.sleep(0.1)
                        continue
                    
                    # Convert to string
                    output_str = output.decode('utf-8', errors='replace')
                    
                    # Add to session buffer
                    if session_id in active_terminals:
                        terminal_info = active_terminals[session_id]
                        
                        # Add to full buffer (preserve everything)
                        if 'full_buffer' not in terminal_info:
                            terminal_info['full_buffer'] = ''
                        terminal_info['full_buffer'] += output_str
                        
                        # Limit buffer size (keep last 100KB)
                        if len(terminal_info['full_buffer']) > 100000:
                            terminal_info['full_buffer'] = terminal_info['full_buffer'][-100000:]
                        
                        # Accumulate output for batched logging
                        output_accumulator += output_str
                        
                        # If we have a significant amount of output, log it immediately
                        if len(output_accumulator) > 1000:
                            TerminalManager._log_comprehensive_event(
                                app, session_id, 'terminal_output',
                                output=output_accumulator,
                                message="Terminal output (large batch)"
                            )
                            output_accumulator = ""
                            last_log_time = time.time()
                    
                    # Send to client
                    socketio.emit('terminal_output', output_str, room=session_id)
                    
                except OSError as e:
                    if e.errno == 5:  # Input/output error
                        break
                    time.sleep(0.1)
            
            except Exception as e:
                with app.app_context():
                    logger.error(f"Error in terminal reader: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                time.sleep(0.5)
        
        # Final flush of any remaining output
        if output_accumulator:
            TerminalManager._log_comprehensive_event(
                app, session_id, 'terminal_output',
                output=output_accumulator,
                message="Terminal output (final)"
            )
        
        with app.app_context():
            logger.info(f"Reader thread exiting for session {session_id}")
    
    @staticmethod
    def close_session(session_id):
        """Close terminal session and preserve all logs"""
        if session_id not in active_terminals:
            return False
        
        try:
            terminal_info = active_terminals.get(session_id, {})
            
            # Create a standalone logger
            import logging
            logger = logging.getLogger('terminal_manager')
            if not logger.handlers:
                handler = logging.StreamHandler()
                formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
                handler.setFormatter(formatter)
                logger.addHandler(handler)
                logger.setLevel(logging.INFO)
            
            # Log session closure with final state
            app_instance = terminal_info.get('app') # Get app instance
            if app_instance: # Check if app_instance exists
                try:
                    with app_instance.app_context(): # Use the explicit app_instance
                        # Save final session state
                        final_buffer = terminal_info.get('full_buffer', '')
                        command_history = terminal_info.get('command_history', [])
                        
                        TerminalManager._log_comprehensive_event(
                            app_instance, session_id, 'session_end',
                            message='Terminal session closed',
                            metadata={
                                'final_buffer_size': len(final_buffer),
                                'total_commands': len(command_history),
                                'session_duration': str(datetime.utcnow() - terminal_info.get('last_activity', datetime.utcnow()))
                            }
                        )
                        
                        # Save complete buffer as final log entry
                        if final_buffer:
                            TerminalManager._log_comprehensive_event(
                                app_instance, session_id, 'session_buffer',
                                output=final_buffer,
                                message='Complete session buffer'
                            )
                except Exception as e:
                    logger.info(f"Session {session_id} closed (couldn't save final state: {e})")
            else:
                logger.warning(f"App instance not found for session {session_id} during close_session logging.")

            # Close file descriptor
            fd = terminal_info.get('fd')
            if fd:
                try:
                    os.close(fd)
                except OSError:
                    pass
            
            # Terminate process
            process = terminal_info.get('process')
            if process and process.poll() is None:
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    time.sleep(0.5)
                    if process.poll() is None:
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                except Exception as e:
                    logger.error(f"Error terminating process: {e}")
            
            # Remove from active terminals
            active_terminals.pop(session_id, None)
            logger.info(f"Closed terminal session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error closing terminal session: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    @staticmethod
    def get_session_logs(session_id):
        """Get comprehensive logs for a session (active or inactive)"""
        from app.terminal.models import TerminalLog
        from sqlalchemy import desc
        
        # Check if session is active first
        if session_id in active_terminals:
            # For active sessions, return current buffer
            terminal_info = active_terminals[session_id]
            buffer = terminal_info.get('full_buffer', '')
            history = [cmd['command'] for cmd in terminal_info.get('command_history', [])]
            
            if not buffer:
                buffer = '\r\n=== Active Session ===\r\n'
                buffer += 'Session is active but no output yet.\r\n'
                buffer += 'Type commands to see output here.\r\n'
            
            return buffer, history
        
        # For inactive sessions, reconstruct from database logs
        logs = TerminalLog.query.filter_by(
            session_id=session_id
        ).order_by(TerminalLog.timestamp).all()
        
        if not logs:
            buffer = '\r\n=== Session History ===\r\n\r\n'
            buffer += 'No logs found for this session.\r\n'
            return buffer, []
        
        # Look for complete session buffer first
        session_buffer_log = None
        for log in reversed(logs):  # Check most recent first
            if log.event_type == 'session_buffer' and log.output:
                session_buffer_log = log
                break
        
        if session_buffer_log:
            # Use the complete session buffer if available
            buffer = session_buffer_log.output
            
            # Also extract command history
            commands = []
            for log in logs:
                if log.event_type == 'command_input' and log.command:
                    commands.append(log.command)
            
            current_app.logger.info(f"Retrieved complete session buffer for {session_id}")
            return buffer, commands
        
        # Fallback: reconstruct from individual log entries
        buffer = '\r\n=== Session History ===\r\n\r\n'
        commands = []
        
        for log in logs:
            if log.event_type == 'session_start':
                buffer += f'--- {log.message} at {log.timestamp.strftime("%Y-%m-%d %H:%M:%S")} ---\r\n\r\n'
                
            elif log.event_type == 'command_input' and log.command:
                # Show command with prompt
                buffer += f'$ {log.command}\r\n'
                commands.append(log.command)
                
            elif log.event_type == 'terminal_output' and log.output:
                # Add terminal output
                output = log.output.replace('\n', '\r\n') if log.output else ''
                buffer += output
                
            elif log.event_type == 'session_end':
                buffer += f'\r\n--- {log.message} at {log.timestamp.strftime("%Y-%m-%d %H:%M:%S")} ---\r\n'
        
        current_app.logger.info(f"Reconstructed session history for {session_id}: {len(logs)} log entries")
        return buffer, commands
    
    @staticmethod
    def _log_comprehensive_event(app, session_id, event_type, command=None, output=None, message=None, metadata=None):
        """Enhanced logging with comprehensive event tracking"""
        # Ensure current_app, db, TerminalLog, logging, datetime, json are available through imports
        with app.app_context(): # Use the passed app instance
            try:
                # Existing logger setup:
                import logging # Keep import here as it was in the original provided snippet
                logger = logging.getLogger('terminal_manager')
                if not logger.handlers: # This check might be part of original code
                    handler = logging.StreamHandler()
                    formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
                    handler.setFormatter(formatter)
                    logger.addHandler(handler)
                    logger.setLevel(logging.INFO)

                log_entry = TerminalLog(
                    session_id=session_id,
                    event_type=event_type,
                    command=command,
                    output=output,
                    timestamp=datetime.utcnow() 
                )
            
                if metadata:
                    import json # Keep import local if only used here
                    if hasattr(log_entry, 'extra_data'):
                        log_entry.extra_data = json.dumps(metadata)
            
                db.session.add(log_entry)
                db.session.commit()
            
                if session_id in active_terminals:
                    # This part of the original code should be preserved as is:
                    session_log = active_terminals[session_id].get('session_log', [])
                    session_log.append({
                        'timestamp': datetime.utcnow(),
                        'event_type': event_type,
                        'command': command,
                        'output': output,
                        'message': message,
                        'metadata': metadata
                    })
                    active_terminals[session_id]['session_log'] = session_log

                return True
            
            except Exception as e:
                # It's good practice to get a logger instance here if not already available
                # However, the logger setup is inside the try block. For robustness,
                # especially if logger setup itself could fail or if we are here due to app context issues,
                # a more resilient logger might be needed or ensure logger is initialized outside/before this.
                # For now, assuming logger might be available from the try block or a higher scope if it didn't fail early.
                logger = logging.getLogger('terminal_manager') # Attempt to get logger again or rely on outer scope
                try:
                    db.session.rollback()
                except Exception as dbe:
                    # Use a logger that is guaranteed to work (e.g., print or root logger direct)
                    # or ensure this logger.error doesn't also try to use DatabaseHandler if it's failing
                    print(f"Database rollback failed: {dbe}") # Or use specific logger
                    logger.error(f"Database rollback failed for session {session_id}: {dbe}")

                logger.error(f"Error logging comprehensive event for session {session_id}, event {event_type}: {e}")
                return False
    
    @staticmethod
    def send_command(session_id, command, socketio):
        """Send a complete command to terminal session"""
        if session_id not in active_terminals:
            return False
        
        # Store command in history
        if command.strip():
            terminal_info = active_terminals[session_id]
            terminal_info.setdefault('command_history', []).append({
                'command': command,
                'timestamp': datetime.utcnow(),
                'cwd': terminal_info.get('cwd', os.getcwd())
            })
            
            # Log command
            app_instance = terminal_info.get('app')
            if app_instance:
                TerminalManager._log_comprehensive_event(
                    app_instance, session_id, 'command_input', 
                    command=command,
                    message=f"API command executed: {command}"
                )
            else:
                # Consider logging a warning if app is not found
                pass
        
        # Reset input buffer
        active_terminals[session_id]['input_buffer'] = ''
        
        # Send command and newline
        result = TerminalManager.send_input(session_id, command + '\n')
        active_terminals[session_id]['last_activity'] = datetime.utcnow()
        return result
    
    @staticmethod
    def resize_terminal(session_id, rows, cols):
        """Resize terminal"""
        if session_id not in active_terminals:
            return False
        
        try:
            fd = active_terminals[session_id]['fd']
            
            import fcntl
            import termios
            import struct
            
            term_size = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(fd, termios.TIOCSWINSZ, term_size)
            
            # Log resize event
            app_instance = active_terminals[session_id].get('app')
            if app_instance:
                TerminalManager._log_comprehensive_event(
                    app_instance, session_id, 'terminal_resize',
                    message=f"Terminal resized to {rows}x{cols}"
                )
            else:
                # Consider logging a warning if app is not found
                pass
            
            current_app.logger.info(f"Resized terminal {session_id} to {rows}x{cols}")
            return True
            
        except Exception as e:
            current_app.logger.error(f"Error resizing terminal: {e}")
            return False
    
    @staticmethod
    def get_buffer(session_id):
        """Get terminal output buffer"""
        if session_id not in active_terminals:
            return None
        return active_terminals[session_id].get('full_buffer', '')
    
    @staticmethod
    def get_history(session_id):
        """Get command history"""
        if session_id not in active_terminals:
            return []
        history = active_terminals[session_id].get('command_history', [])
        return [cmd['command'] for cmd in history]
    
    @staticmethod
    def execute_command(session_id, command, background=False):
        """Execute a command in the terminal"""
        if session_id not in active_terminals:
            return False, "Session not found"
        
        try:
            if background and not command.endswith('&'):
                command = command.rstrip() + ' &'
            
            app_instance = active_terminals[session_id].get('app')
            if app_instance:
                TerminalManager._log_comprehensive_event(
                    app_instance, session_id, 'api_command',
                    command=command,
                    message=f"API command execution: {command}"
                )
            else:
                # Consider logging a warning if app is not found
                pass
            
            # Send each character with a small delay
            for char in command:
                TerminalManager.send_input(session_id, char)
                time.sleep(0.01)
            
            # Send enter
            TerminalManager.send_input(session_id, '\n')
            
            return True, "Command executed"
            
        except Exception as e:
            current_app.logger.error(f"Error executing command: {e}")
            return False, str(e)