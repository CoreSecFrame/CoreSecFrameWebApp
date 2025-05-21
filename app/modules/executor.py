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
                
            # Determine the module import path
            if "modules" in str(module_path):
                if module_path.parent.name == "modules":
                    # Top-level module
                    import_path = f"modules.{module_name}"
                else:
                    # Category module
                    category = module_path.parent.name
                    import_path = f"modules.{category}.{module_name}"
            else:
                # Fall back to simple import
                import_path = module_name
            
            current_app.logger.info(f"Importing module '{import_path}' from {module_path}")
            
            # Add modules directory to Python path
            modules_dir = current_app.config['MODULES_DIR']
            project_dir = str(Path(modules_dir).parent)
            
            if project_dir not in sys.path:
                sys.path.insert(0, project_dir)
            
            if modules_dir not in sys.path:
                sys.path.insert(0, modules_dir)
            
            # Try to import the module
            try:
                # Try direct import first
                module = importlib.import_module(import_path)
            except ImportError:
                # If that fails, use spec_from_file_location
                spec = importlib.util.spec_from_file_location(import_path, str(module_path))
                if not spec:
                    return False, f"Could not create spec for module: {module_path}"
                
                module = importlib.util.module_from_spec(spec)
                sys.modules[import_path] = module
                spec.loader.exec_module(module)
            
            # Find the module class
            module_class = None
            class_name = None
            
            # First look for a class with a similar name to the module
            module_names = [
                module_name,
                module_name.capitalize(),
                module_name.title(),
                f"{module_name}Module",
                f"{module_name.capitalize()}Module"
            ]
            
            for name in module_names:
                if hasattr(module, name):
                    attr = getattr(module, name)
                    if isinstance(attr, type):
                        try:
                            instance = attr()
                            if hasattr(instance, 'run_guided') and hasattr(instance, 'run_direct'):
                                module_class = instance
                                class_name = name
                                break
                        except Exception as e:
                            current_app.logger.error(f"Error instantiating class {name}: {e}")
            
            # If not found, try all classes in the module
            if not module_class:
                for attr_name in dir(module):
                    if attr_name.startswith('__'):
                        continue
                    
                    attr = getattr(module, attr_name)
                    if not isinstance(attr, type):
                        continue
                    
                    try:
                        instance = attr()
                        if hasattr(instance, 'run_guided') and hasattr(instance, 'run_direct'):
                            module_class = instance
                            class_name = attr_name
                            break
                    except Exception as e:
                        current_app.logger.error(f"Error instantiating class {attr_name}: {e}")
            
            if not module_class:
                return False, f"Could not find a suitable class in module {module_name}"
            
            current_app.logger.info(f"Found module class: {class_name}")
            
            # Create a specialized command for running the module
            # This command will be sent to the terminal session
            command = ModuleExecutor._build_module_command(
                module_path=module_path,
                import_path=import_path,
                class_name=class_name,
                mode=mode
            )
            
            if not command:
                return False, "Failed to build module execution command"
            
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

# Make sure we have the proper paths in sys.path
if project_root not in sys.path:
    sys.path.insert(0, project_root)
    
if modules_dir not in sys.path:
    sys.path.insert(0, modules_dir)

# Add parent directory of module to path
if module_parent not in sys.path:
    sys.path.insert(0, module_parent)

# Print paths for debugging
print("Python path includes:")
for path in sys.path:
    print(f"  - {{path}}")

try:
    # Try importing the module
    try:
        print(f"\\nAttempting to import {{import_path}}.{{class_name}}...")
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
    except ImportError as e:
        print(f"Import Error: {{e}}")
        print("\\nTrying alternate import method...")
        
        # Try direct file path import
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
                print(f"Module loaded but class '{{class_name}}' not found")
                print("Available classes:")
                for attr in dir(module):
                    if not attr.startswith('__') and isinstance(getattr(module, attr), type):
                        print(f"  - {{attr}}")
        else:
            print(f"Could not create module spec for {{module_path}}")
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
        
        # Command to run the script and then remove it
        command = f"python3 {script_filename} && rm {script_filename}"
        
        return command