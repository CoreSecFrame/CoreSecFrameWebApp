# app/terminal/utils.py
import subprocess
import os
import signal
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
            
        # Create a new session
        if session.session_type == 'terminal':
            # Basic shell session
            subprocess.run([
                'tmux', 'new-session',
                '-d',  # Start detached
                '-s', session.session_id,  # Session name
                '-n', 'main',  # Window name
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
                module_cmd  # Command to run
            ], check=True)
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
        print(f"Error creating terminal process: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False

def build_module_command(module_name, mode):
    """Build the command to run a module in guided or direct mode"""
    try:
        # This will need to be adapted based on your specific module structure
        framework_root = current_app.config['BASE_DIR']
        
        # Try to locate the module file
        module_dir = Path(framework_root) / 'modules'
        module_path = None
        
        # Check in base modules directory
        base_module = module_dir / f"{module_name}.py"
        if base_module.exists():
            module_path = f"modules.{module_name}"
        else:
            # Check in subdirectories
            for subdir in module_dir.iterdir():
                if subdir.is_dir():
                    submodule = subdir / f"{module_name}.py"
                    if submodule.exists():
                        module_path = f"modules.{subdir.name}.{module_name}"
                        break
        
        if not module_path:
            return None
            
        # Build the command
        cmd = (f"cd {framework_root} && "
              f"python3 -u -c \""
              f"import sys; "
              f"sys.path.append('{framework_root}'); "
              f"from {module_path} import * "
              f"tool = {module_name.capitalize()}(); "
              f"tool.{'run_guided' if mode == 'guided' else 'run_direct'}()\"; "
              f"echo 'Module execution completed'; "
              f"exec bash -l")
              
        return cmd
        
    except Exception as e:
        print(f"Error building module command: {e}")
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