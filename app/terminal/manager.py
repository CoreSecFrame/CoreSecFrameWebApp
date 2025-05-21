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
    """Manages terminal sessions"""
    
    @staticmethod
    def create_session(session_id, socketio, allow_create=True):
        """Create a new terminal session or return existing one
        
        Args:
            session_id: Session ID
            socketio: SocketIO instance
            allow_create: Whether to allow creation of new sessions (set to False for viewing inactive sessions)
        """
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
            env['BASH_COMPLETION_ENABLED'] = '1'  # Enable bash completion
            
            # Start bash with completion enabled
            process = subprocess.Popen(
                ['/bin/bash', '--login'],  # Login shell to load .bashrc
                stdin=slave,
                stdout=slave,
                stderr=slave,
                start_new_session=True,  # Start in a new process group
                env=env,                 # Modified environment
                close_fds=True           # Close other file descriptors
            )
            
            # Close slave FD in parent
            os.close(slave)
            
            # Store terminal info
            active_terminals[session_id] = {
                'fd': master,
                'process': process,
                'thread': None,
                'last_activity': datetime.utcnow(),
                'buffer': '',    # Store output buffer for persistence
                'history': [],   # Command history
                'command': '',   # Current command being built
                'cwd': os.getcwd()  # Current working directory
            }
            
            # Start reader thread
            thread = threading.Thread(
                target=TerminalManager._read_output,
                args=(session_id, master, socketio)
            )
            thread.daemon = True
            thread.start()
            
            active_terminals[session_id]['thread'] = thread
            
            # Log creation
            TerminalManager._log_event(session_id, 'system', None, 'Terminal session created')
            
            # Enable better command completion
            welcome_commands = [
                # Enable tab completion
                "bind 'set show-all-if-ambiguous on'",
                "bind 'set completion-ignore-case on'",
                # Set prompt to show current directory
                "export PS1='\\[\\033[01;32m\\]\\u@\\h\\[\\033[00m\\]:\\[\\033[01;34m\\]\\w\\[\\033[00m\\]\\$ '",
                # Welcome message
                "echo 'Welcome to CoreSecFrame Terminal - Type \"help\" for commands'",
                # Clear the history of these startup commands
                "history -c"
            ]
            
            # Execute startup commands
            for cmd in welcome_commands:
                time.sleep(0.1)  # Small delay between commands
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
        """Send input to terminal session"""
        if session_id not in active_terminals:
            return False
        
        fd = active_terminals[session_id]['fd']
        try:
            os.write(fd, data.encode())
            active_terminals[session_id]['last_activity'] = datetime.utcnow()
            
            # Track current command for tab completion
            if data == '\t':  # Tab key pressed
                TerminalManager._handle_tab_completion(session_id)
            elif data == '\n':  # Enter key pressed
                # Command completed, add to history if not empty
                command = active_terminals[session_id].get('command', '').strip()
                if command:
                    TerminalManager._log_event(session_id, 'command', command, None)
                    
                    # Add to history if not duplicate
                    history = active_terminals[session_id].get('history', [])
                    if not history or history[-1] != command:
                        history.append(command)
                        # Limit history size
                        if len(history) > 100:
                            history = history[-100:]
                        active_terminals[session_id]['history'] = history
                
                # Reset current command
                active_terminals[session_id]['command'] = ''
                
                # Update working directory
                TerminalManager._update_working_directory(session_id)
            elif data == '\b' or data == '\x7f':  # Backspace or Delete
                # Remove last character from command
                command = active_terminals[session_id].get('command', '')
                if command:
                    active_terminals[session_id]['command'] = command[:-1]
            else:
                # Add character to command (ignore control characters)
                if not data.startswith('\x1b'):  # Ignore escape sequences
                    command = active_terminals[session_id].get('command', '')
                    active_terminals[session_id]['command'] = command + data
            
            return True
        except Exception as e:
            current_app.logger.error(f"Error writing to terminal: {e}")
            return False
    
    @staticmethod
    def _handle_tab_completion(session_id):
        """Handle tab completion manually"""
        if session_id not in active_terminals:
            return False
        
        # Get current command
        current_command = active_terminals[session_id].get('command', '').strip()
        if not current_command:
            return False
        
        # Simply send tab to terminal - bash's built-in tab completion will handle it
        # This is handled internally by the shell
        
        return True
    
    @staticmethod
    def _update_working_directory(session_id):
        """Update the current working directory by asking the shell"""
        if session_id not in active_terminals:
            return
        
        # We'll send a command to get the current working directory
        # But we don't want to log this command
        # This command is sent silently and its output will be caught by the reader thread
        cmd = "pwd > /tmp/cwd_$$ && echo '_PWD:'$(cat /tmp/cwd_$$) && rm /tmp/cwd_$$"
        fd = active_terminals[session_id]['fd']
        try:
            # Send the command quietly
            os.write(fd, f"\n{cmd}\n".encode())
        except Exception as e:
            current_app.logger.error(f"Error updating working directory: {e}")
    
    @staticmethod
    def send_command(session_id, command, socketio):
        """Send a complete command to terminal session"""
        if session_id not in active_terminals:
            return False
        
        # Store command in history
        if command.strip():
            history = active_terminals[session_id].get('history', [])
            if not history or history[-1] != command:
                history.append(command)
                # Limit history size
                if len(history) > 100:
                    history = history[-100:]
                active_terminals[session_id]['history'] = history
            
            # Log command
            TerminalManager._log_event(session_id, 'command', command, None)
        
        # Reset current command
        active_terminals[session_id]['command'] = ''
        
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
            
            # Set new size
            import fcntl
            import termios
            import struct
            
            term_size = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(fd, termios.TIOCSWINSZ, term_size)
            
            current_app.logger.info(f"Resized terminal {session_id} to {rows}x{cols}")
            return True
        except Exception as e:
            current_app.logger.error(f"Error resizing terminal: {e}")
            return False
    
    @staticmethod
    def close_session(session_id):
        """Close terminal session"""
        if session_id not in active_terminals:
            return False
        
        try:
            # Get a copy of the terminal info
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
            
            # Try to log closure if possible
            try:
                from flask import current_app
                with current_app.app_context():
                    TerminalManager._log_event(session_id, 'system', None, 'Terminal session closed')
            except:
                logger.info(f"Session {session_id} closed (couldn't log to database)")
            
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
                    # Send SIGTERM
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    
                    # Wait briefly for process to terminate
                    time.sleep(0.5)
                    
                    # If still running, force kill
                    if process.poll() is None:
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                except Exception as e:
                    logger.error(f"Error terminating process: {e}")
            
            # Remove from active terminals (use pop to avoid race conditions)
            active_terminals.pop(session_id, None)
            logger.info(f"Closed terminal session {session_id}")
            return True
        except Exception as e:
            logger.error(f"Error closing terminal session: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    @staticmethod
    def _read_output(session_id, fd, socketio):
        """Read output from terminal and send to client"""
        import logging
        # Create a standalone logger that doesn't rely on Flask's app context
        logger = logging.getLogger('terminal_manager')
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        
        max_read_bytes = 1024 * 4  # 4KB buffer
        
        # PWD tracking pattern
        pwd_pattern = b"_PWD:"
        
        while True:
            try:
                # Check if terminal session still exists
                if session_id not in active_terminals:
                    break
                
                # Select to wait for data with timeout
                ready_to_read, _, _ = select.select([fd], [], [], 0.1)
                
                if not ready_to_read:
                    # Check if process is still alive
                    process = active_terminals[session_id]['process']
                    if process.poll() is not None:
                        # Process ended, wait a moment then clean up
                        time.sleep(1)
                        if session_id in active_terminals and process.poll() is not None:
                            logger.info(f"Process for session {session_id} has ended")
                            try:
                                # Try to get app context if available
                                from flask import current_app
                                with current_app.app_context():
                                    TerminalManager._log_event(session_id, 'system', None, 'Process terminated')
                            except:
                                # If not available, just proceed without logging to database
                                pass
                            TerminalManager.close_session(session_id)
                            break
                    continue
                
                # Read data from terminal
                try:
                    output = os.read(fd, max_read_bytes)
                    if not output:
                        time.sleep(0.1)
                        continue
                    
                    # Check for PWD tracking output
                    pwd_idx = output.find(pwd_pattern)
                    if pwd_idx >= 0:
                        # Extract the PWD
                        pwd_end = output.find(b"\n", pwd_idx)
                        if pwd_end > pwd_idx:
                            pwd = output[pwd_idx + len(pwd_pattern):pwd_end].decode('utf-8', errors='replace').strip()
                            # Update the CWD in session info
                            if session_id in active_terminals:
                                active_terminals[session_id]['cwd'] = pwd
                            
                            # Remove the PWD output from the terminal output
                            output = output[:pwd_idx] + output[pwd_end+1:]
                            if not output:  # Skip if nothing left
                                continue
                    
                    # Convert to string and store in buffer
                    output_str = output.decode('utf-8', errors='replace')
                    if session_id in active_terminals:
                        # Append to buffer
                        buffer = active_terminals[session_id].get('buffer', '')
                        buffer += output_str
                        
                        # Limit buffer size (keep last 50KB)
                        if len(buffer) > 50000:
                            buffer = buffer[-50000:]
                        
                        active_terminals[session_id]['buffer'] = buffer
                        
                        # Log output selectively - don't log every keystroke or cursor movement
                        # Only log actual command output that matters
                        if len(output_str) > 5 and not all(c in ' \r\n\t\x1b[' for c in output_str):
                            try:
                                # Try to get app context if available
                                from flask import current_app
                                with current_app.app_context():
                                    TerminalManager._log_event(session_id, 'output', None, output_str)
                            except:
                                # If not available, just proceed without logging to database
                                pass
                    
                    # Send to client
                    socketio.emit('terminal_output', output_str, room=session_id)
                    
                except OSError as e:
                    if e.errno == 5:  # Input/output error
                        break
                    time.sleep(0.1)
            
            except Exception as e:
                logger.error(f"Error in terminal reader: {e}")
                import traceback
                logger.error(traceback.format_exc())
                time.sleep(0.5)
        
        logger.info(f"Reader thread exiting for session {session_id}")
    
    @staticmethod
    def get_buffer(session_id):
        """Get terminal output buffer"""
        if session_id not in active_terminals:
            return None
        return active_terminals[session_id].get('buffer', '')
    
    @staticmethod
    def get_history(session_id):
        """Get command history"""
        if session_id not in active_terminals:
            return []
        return active_terminals[session_id].get('history', [])
    
    @staticmethod
    def get_session_logs(session_id):
        """Get logs for an inactive session"""
        from app.terminal.models import TerminalLog
        from sqlalchemy import desc
        
        # Get logs for the session ordered by timestamp
        logs = TerminalLog.query.filter_by(
            session_id=session_id
        ).order_by(TerminalLog.timestamp).all()
        
        # Concatenate logs into a buffer
        buffer = '\r\n=== Session History ===\r\n\r\n'
        
        if not logs:
            buffer += "No logs found for this session.\r\n"
        else:
            # Process logs
            for log in logs:
                if log.event_type == 'command':
                    # Add command with prompt
                    buffer += f'$ {log.command}\r\n'
                elif log.event_type == 'output' and log.output:
                    # Add output, ensuring it has proper line endings
                    output = log.output.replace('\n', '\r\n') if log.output else ''
                    buffer += f'{output}'
                elif log.event_type == 'system' and log.output:
                    # Add system messages
                    buffer += f'\r\n--- {log.output} ---\r\n'
        
        # Extract command history
        commands = [log.command for log in logs if log.event_type == 'command' and log.command]
        
        current_app.logger.info(f"Retrieved {len(logs)} logs for session {session_id}")
        
        return buffer, commands
    
    @staticmethod
    def _log_event(session_id, event_type, command, output):
        """Log terminal event to database"""
        try:
            # Create a standalone logger for errors
            import logging
            logger = logging.getLogger('terminal_manager')
            if not logger.handlers:
                handler = logging.StreamHandler()
                formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
                handler.setFormatter(formatter)
                logger.addHandler(handler)
                logger.setLevel(logging.INFO)
            
            # Create log entry
            log = TerminalLog(
                session_id=session_id,
                event_type=event_type,
                command=command,
                output=output
            )
            
            # Add to database
            db.session.add(log)
            db.session.commit()
            
            return True
        except Exception as e:
            try:
                db.session.rollback()
            except:
                pass
            
            logger.error(f"Error logging terminal event: {e}")
            return False
    
    @staticmethod
    def execute_command(session_id, command, background=False):
        """Execute a command in the terminal (useful for API control)"""
        if session_id not in active_terminals:
            return False, "Session not found"
        
        try:
            # Prepare command
            if background and not command.endswith('&'):
                command = command.rstrip() + ' &'
            
            # Log and send command
            TerminalManager._log_event(session_id, 'system', None, f"Executing command: {command}")
            
            # Send each character with a small delay to mimic typing
            for char in command:
                TerminalManager.send_input(session_id, char)
                time.sleep(0.01)  # Small delay
            
            # Send enter
            TerminalManager.send_input(session_id, '\n')
            
            return True, "Command executed"
        except Exception as e:
            current_app.logger.error(f"Error executing command: {e}")
            return False, str(e)