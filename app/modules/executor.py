# app/modules/executor.py
import os
import traceback # Keep: Used in execute_module
from flask import current_app # Keep: Used in execute_module
from pathlib import Path # Keep: Used in execute_module
# sys - Removed: Only used in _build_module_command
# importlib - Removed: Only used in _build_module_command
# importlib.util - Removed: Only used in _build_module_command

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
    
# _build_module_command removed
# Imports exclusively used by it (sys, importlib, importlib.util, uuid, stat) also removed.