# app/terminal/utils.py
import subprocess
import os
import signal
import shutil  # Add this import
from pathlib import Path
from flask import current_app
import psutil
from datetime import datetime

def create_terminal_process(session):
    """Create a tmux session for the terminal"""
    try:
        # Check if tmux is installed
        if not shutil.which('tmux'):
            return False
            
        # Check if session already exists
        check_session = subprocess.run(
            ['tmux', 'has-session', '-t', session.session_id],
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE
        )
        
        if check_session.returncode == 0:
            # Session already exists
            return True
        
        # Get user's home directory
        user_home = os.path.expanduser('~')
            
        # Create a new session
        if session.session_type == 'terminal':
            # Basic shell session
            subprocess.run([
                'tmux', 'new-session',
                '-d',  # Start detached
                '-s', session.session_id,  # Session name
                '-n', 'main',  # Window name
                '-c', user_home,  # Set working directory to user's home
                'bash'  # Command to run
            ], check=True)
        elif session.session_type in ['guided', 'direct']:
            # Run a module
            if not session.module_name:
                return False
                
            # Construct the module command based on guided or direct mode
            module_cmd = build_module_command(session.module_name, session.session_type)
            
            if not module_cmd:
                return False
                
            subprocess.run([
                'tmux', 'new-session',
                '-d',  # Start detached
                '-s', session.session_id,  # Session name
                '-n', session.module_name,  # Window name
                '-c', user_home,  # Set working directory to user's home
                module_cmd  # Command to run
            ], check=True)
            
            # Log the start of the module
            from app.terminal.models import TerminalLog
            log = TerminalLog(
                session_id=session.session_id,
                event_type='system',
                command=None,
                output=f"Starting module {session.module_name} in {session.session_type} mode"
            )
            db.session.add(log)
            db.session.commit()
        else:
            return False
            
        # Configure tmux session
        subprocess.run([
            'tmux', 'set-option', '-t', session.session_id,
            'status-right', f'#{session.session_id}'
        ], check=True)
        
        subprocess.run([
            'tmux', 'set-option', '-t', session.session_id,
            'mouse', 'on'
        ], check=True)
        
        return True
        
    except subprocess.CalledProcessError as e:
        current_app.logger.error(f"Error creating terminal process: {e}")
        return False
    except Exception as e:
        current_app.logger.error(f"Unexpected error: {e}")
        current_app.logger.error(traceback.format_exc())
        return False

def build_module_command(module_name, mode):
    """Build the command to run a module in guided or direct mode"""
    try:
        # Use the project root directory
        framework_root = current_app.config['BASE_DIR']
        
        # Use the proper modules directory at the project root
        module_dir = Path(current_app.config['MODULES_DIR'])
        
        # Get the module from the database to find its correct path
        from app.modules.models import Module
        module_obj = Module.query.filter_by(name=module_name).first()
        
        if not module_obj:
            current_app.logger.error(f"Module {module_name} not found in database")
            return None
            
        if not module_obj.installed:
            current_app.logger.error(f"Module {module_name} is not installed")
            return None
        
        module_path = None
        module_file = None
        
        if module_obj and module_obj.local_path:
            # Use the path stored in the database
            module_file = Path(module_obj.local_path)
            if module_file.exists():
                # Determine the proper import path
                if module_file.parent.name == 'modules':
                    # Module is in the base modules directory
                    module_path = f"modules.{module_name}"
                else:
                    # Module is in a category subdirectory
                    category = module_file.parent.name
                    module_path = f"modules.{category}.{module_name}"
        
        if not module_path:
            current_app.logger.error(f"Could not determine module path for {module_name}")
            return None
            
        # Parse the module file to find the actual class name
        class_name = module_name.capitalize()  # Default
        if module_file:
            try:
                with open(module_file, 'r') as f:
                    content = f.read()
                    
                # Look for class definitions with the module name or similar
                import re
                class_pattern = re.compile(r'class\s+(\w+)\s*[:\(]')
                matches = class_pattern.findall(content)
                
                if matches:
                    # Try to find a class that's similar to the module name
                    for match in matches:
                        if match.lower() == module_name.lower() or \
                           match.lower() == f"{module_name.lower()}module":
                            class_name = match
                            break
                    # If no match found, use first class
                    if not class_name and matches:
                        class_name = matches[0]
            except Exception as e:
                current_app.logger.error(f"Error parsing module file: {e}")
        
        # Build the command
        # Make sure to add the project root to the Python path
        cmd = (f"cd {framework_root} && "
              f"python3 -u -c \""
              f"import sys; "
              f"sys.path.append('{framework_root}'); "
              f"try:\n"
              f"    from {module_path} import {class_name} \n"
              f"    tool = {class_name}() \n"
              f"    print('Starting {class_name} in {mode} mode...\\n') \n"
              f"    tool.{'run_guided' if mode == 'guided' else 'run_direct'}() \n"
              f"except Exception as e:\n"
              f"    print(f'Error running module: {{e}}');\n"
              f"    import traceback; traceback.print_exc() \n"
              f"\"; "
              f"echo 'Module execution completed'; "
              f"exec bash -l")
        
        current_app.logger.info(f"Built module command: {cmd}")      
        return cmd
        
    except Exception as e:
        current_app.logger.error(f"Error building module command: {e}")
        current_app.logger.error(traceback.format_exc())
        return None

def get_process_details(session):
    """Get details about the tmux session process"""
    try:
        # Check if session exists
        result = subprocess.run(
            ['tmux', 'has-session', '-t', session.session_id],
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE
        )
        
        if result.returncode != 0:
            return {
                'running': False,
                'pid': None,
                'cpu_percent': 0,
                'memory_percent': 0
            }
            
        # Get tmux session PID
        result = subprocess.run(
            ['tmux', 'list-panes', '-t', session.session_id, '-F', '#{pane_pid}'],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0 or not result.stdout.strip():
            return {
                'running': False,
                'pid': None,
                'cpu_percent': 0,
                'memory_percent': 0
            }
            
        # Get the first pane PID
        pid = int(result.stdout.strip().split('\n')[0])
        
        # Get process info
        try:
            process = psutil.Process(pid)
            return {
                'running': True,
                'pid': pid,
                'cpu_percent': process.cpu_percent(),
                'memory_percent': process.memory_percent(),
                'create_time': datetime.fromtimestamp(process.create_time()).isoformat()
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return {
                'running': False,
                'pid': pid,
                'cpu_percent': 0,
                'memory_percent': 0
            }
            
    except Exception as e:
        print(f"Error getting process details: {e}")
        return {
            'running': False,
            'pid': None,
            'cpu_percent': 0,
            'memory_percent': 0,
            'error': str(e)
        }