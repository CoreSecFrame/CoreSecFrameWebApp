# app/modules/executor.py
import os
import sys
import importlib
import importlib.util
import traceback
from flask import current_app
from pathlib import Path

class ModuleExecutor:
    """Bridge between web app and module execution"""
    
    @staticmethod
    def execute_module(module_name, mode='guided', session_id=None):
        """
        Execute a module in guided or direct mode
        
        Args:
            module_name: Name of the module
            mode: 'guided' or 'direct'
            session_id: Terminal session ID
                
        Returns:
            tuple: (success, message)
        """
        try:
            # Find the module in database
            from app.modules.models import Module
            module_record = Module.query.filter_by(name=module_name).first()
            
            if not module_record:
                return False, f"Module '{module_name}' not found in database"
                    
            if not module_record.installed:
                return False, f"Module '{module_name}' is not installed"
                    
            # Get module path
            module_path = Path(module_record.local_path)
            if not module_path.exists():
                return False, f"Module file not found: {module_path}"
            
            # Find the module class (choose a name that's likely to work)
            class_name = None
            possible_names = [
                module_name,
                module_name.capitalize(),
                f"{module_name}Module",
                f"{module_name.capitalize()}Module"
            ]
            
            # We'll use the first possible name (most probable)
            # The runner script will try alternatives if needed
            class_name = possible_names[0]
            
            # Build module info
            module_info = {
                'path': str(module_path),
                'name': module_name,
                'class': class_name,
                'mode': mode
            }
            
            # Convert to JSON - make sure to escape properly for shell
            import json
            import shlex
            module_info_json = json.dumps(module_info)
            
            # Get runner script path
            from flask import current_app
            runner_script = os.path.join(current_app.config['BASE_DIR'], 'app', 'modules', 'runner.py')
            
            # A simpler approach: write the JSON to a temporary file
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as temp_file:
                json.dump(module_info, temp_file)
                temp_file_path = temp_file.name
            
            # Build command to run the module using the JSON file
            command = f"clear && python3 {runner_script} {temp_file_path} && rm {temp_file_path}"
            
            # If we have a session ID, send the command to that terminal
            if session_id:
                from app.terminal.manager import TerminalManager
                TerminalManager.send_command(session_id, command, None)
                return True, f"Module {module_name} launched in {mode} mode"
            
            return True, command
                
        except Exception as e:
            current_app.logger.error(f"Error executing module {module_name}: {e}")
            current_app.logger.error(traceback.format_exc())
            return False, f"Error executing module: {str(e)}"
    
    @staticmethod
    def _build_module_command(module_path, import_path, class_name, mode):
        """
        Build a Python command to execute the module
        
        Args:
            module_path: Path to module file
            import_path: Python import path
            class_name: Name of the module class
            mode: 'guided' or 'direct'
            
        Returns:
            str: Command to execute
        """
        # Get the absolute path to the root project directory and modules directory
        from flask import current_app
        project_root = current_app.config['BASE_DIR']
        modules_dir = current_app.config['MODULES_DIR']
        
        # This script will be executed to run the module
        script_content = f'''#!/usr/bin/env python3
import sys
import os

# Add project root and modules directory to Python path
project_root = "{project_root}"
modules_dir = "{modules_dir}"
module_parent = "{os.path.dirname(module_path)}"
import_path = "{import_path}"
class_name = "{class_name}"
mode = "{mode}"

# Quietly add paths to sys.path
if project_root not in sys.path:
    sys.path.insert(0, project_root)
    
if modules_dir not in sys.path:
    sys.path.insert(0, modules_dir)

if module_parent not in sys.path:
    sys.path.insert(0, module_parent)

try:
    # Try importing the module
    try:
        module_parts = import_path.split('.')
        
        # For handling "modules.Category.Module" style imports
        if len(module_parts) > 2:
            exec(f"from {{module_parts[0]}}.{{module_parts[1]}} import {{module_parts[2]}}")
            instance = eval(f"{{module_parts[2]}}()")
        else:
            # Simple import case
            exec(f"from {{import_path}} import {{class_name}}")
            instance = eval(f"{{class_name}}()")
        
        print('\\n--- Starting {{class_name}} in ' + mode + ' mode ---\\n')
        
        # Call the appropriate method
        if mode == "guided":
            instance.run_guided()
        else:
            instance.run_direct()
            
        print('\\n--- Module execution completed ---')
    except ImportError:
        # Try direct file path import (silently)
        import importlib.util
        spec = importlib.util.spec_from_file_location(import_path, "{module_path}")
        if spec:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Find the class
            if hasattr(module, class_name):
                instance = getattr(module, class_name)()
                
                print('\\n--- Starting ' + class_name + ' in ' + mode + ' mode ---\\n')
                
                # Call the appropriate method
                if mode == "guided":
                    instance.run_guided()
                else:
                    instance.run_direct()
                    
                print('\\n--- Module execution completed ---')
            else:
                print(f"Error: Could not find class '{{class_name}}' in the module")
        else:
            print(f"Error: Could not load module file")
except Exception as e:
    print(f"Error executing module: {{e}}")
    import traceback
    traceback.print_exc()
'''
    
        # Create a temporary directory if it doesn't exist
        tmp_dir = '/tmp/coresecframe'
        if not os.path.exists(tmp_dir):
            os.makedirs(tmp_dir)
        
        # Create a unique filename for this execution
        import uuid
        script_filename = f"{tmp_dir}/module_exec_{uuid.uuid4().hex}.py"
        
        # Write the script content to the file
        with open(script_filename, 'w') as f:
            f.write(script_content)
        
        # Make the script executable
        import stat
        os.chmod(script_filename, os.stat(script_filename).st_mode | stat.S_IEXEC)
        
        # Command to run the script and silently remove it afterward
        # The 2>/dev/null suppresses error output from the rm command
        command = f"clear && python3 {script_filename} && rm {script_filename} 2>/dev/null"
        
        return command