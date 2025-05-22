# app/modules/runner.py
#!/usr/bin/env python3
import sys
import os
import importlib
import importlib.util
import argparse
import traceback
import json

def run_module(module_path, module_name, class_name, mode='guided', verbose=False):
    """
    Run a security module in guided or direct mode
    
    Args:
        module_path: Path to the module file
        module_name: Name of the module
        class_name: Name of the class to instantiate
        mode: 'guided' or 'direct'
        verbose: Whether to print debug information
    """
    # Get the module's parent directory
    module_parent = os.path.dirname(module_path)
    
    # Get the project root and modules directory
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
    modules_dir = os.path.join(project_root, 'modules')
    
    # Add paths to sys.path
    for path in [project_root, modules_dir, module_parent]:
        if path not in sys.path:
            sys.path.insert(0, path)
    
    if verbose:
        print("Python path includes:")
        for path in sys.path:
            print(f"  - {path}")
        print(f"\nModule path: {module_path}")
        print(f"Module name: {module_name}")
        print(f"Class name: {class_name}")
        print(f"Mode: {mode}")
    
    try:
        # Try to import the module
        try:
            # Determine import path
            if os.path.isabs(module_path):
                import_path = os.path.relpath(module_path, project_root)
                import_path = os.path.splitext(import_path)[0].replace('/', '.')
            else:
                import_path = module_name
                
            if verbose:
                print(f"Import path: {import_path}")
                
            # Try direct import
            module = importlib.import_module(import_path)
        except ImportError as e:
            if verbose:
                print(f"Import error: {e}")
                print("Trying file-based import...")
                
            # Try file-based import
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            if not spec:
                raise ImportError(f"Could not create spec for module: {module_path}")
                
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
        
        # Try to find the class
        if hasattr(module, class_name):
            instance = getattr(module, class_name)()
        else:
            # Try to find a suitable class
            for attr_name in dir(module):
                if attr_name.startswith('__'):
                    continue
                
                attr = getattr(module, attr_name)
                if not isinstance(attr, type):
                    continue
                
                try:
                    instance = attr()
                    if hasattr(instance, 'run_guided') and hasattr(instance, 'run_direct'):
                        class_name = attr_name
                        break
                except:
                    continue
            else:
                raise ValueError(f"Could not find a suitable class in module {module_name}")
        
        # Run the module
        print(f"\n--- Starting {class_name} in {mode} mode ---\n")
        
        if mode == 'guided':
            instance.run_guided()
        else:
            instance.run_direct()
            
        print(f"\n--- Module execution completed ---")
        
    except Exception as e:
        print(f"Error executing module: {e}")
        if verbose:
            traceback.print_exc()

# Update the main block in app/modules/runner.py
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run a security module')
    parser.add_argument('module_info_file', help='Path to JSON file with module information')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')
    
    args = parser.parse_args()
    
    try:
        # Read the module info from the JSON file
        with open(args.module_info_file, 'r') as f:
            module_info = json.load(f)
        
        run_module(
            module_info['path'],
            module_info['name'],
            module_info['class'],
            module_info['mode'],
            args.verbose
        )
    except json.JSONDecodeError:
        print("Error: Invalid JSON format in module_info file")
        sys.exit(1)
    except KeyError as e:
        print(f"Error: Missing required field in module_info: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print(f"Error: Module info file not found: {args.module_info_file}")
        sys.exit(1)