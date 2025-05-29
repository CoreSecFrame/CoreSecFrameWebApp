#!/usr/bin/env python3
# app/modules/enhanced_runner.py
"""
Enhanced module runner for CoreSecFrame webapp
Handles both new and legacy module formats with improved compatibility
"""

import sys
import os
import importlib
import importlib.util
import argparse
import traceback
import json
from pathlib import Path

def setup_module_paths():
    """Setup Python paths for module imports"""
    # Get the project root directory
    current_file = Path(__file__).resolve()
    # Assuming runner.py is in /app/modules/runner.py, traverse up three levels (runner.py -> modules -> app -> project_root)
    project_root = current_file.parent.parent.parent 
    modules_dir = project_root / 'modules'
    
    # Add paths to sys.path if not already present
    paths_to_add = [
        str(project_root),
        str(modules_dir),
        str(modules_dir / 'core')
    ]
    
    for path in paths_to_add:
        if path not in sys.path:
            sys.path.insert(0, path)
    
    return project_root, modules_dir

def find_module_class(module, module_name, verbose=False):
    """
    Find the appropriate class in the module to instantiate
    
    Args:
        module: The imported module
        module_name: Name of the module file
        verbose: Whether to print debug info
        
    Returns:
        tuple: (class_instance, class_name) or (None, None) if not found
    """
    # Define common naming conventions for module classes (e.g., ModName, ModNameModule, ModNameTool)
    possible_class_names = [
        module_name,
        module_name.capitalize(),
        f"{module_name}Module",
        f"{module_name.capitalize()}Module",
        f"{module_name}Tool",
        f"{module_name.capitalize()}Tool"
    ]
    
    if verbose:
        print(f"Looking for classes: {possible_class_names}")
        print(f"Available attributes: {[attr for attr in dir(module) if not attr.startswith('_')]}")
    
    # First, try the exact names we expect
    for class_name in possible_class_names:
        if hasattr(module, class_name):
            class_obj = getattr(module, class_name)
            if isinstance(class_obj, type):
                try:
                    instance = class_obj()
                    # Check if it has the required methods
                    required_methods = ['run_guided', 'run_direct']
                    if all(hasattr(instance, method) for method in required_methods):
                        if verbose:
                            print(f"Found compatible class: {class_name}")
                        return instance, class_name
                except Exception as e:
                    if verbose:
                        print(f"Could not instantiate {class_name}: {e}")
                    continue
    
    # Fallback: If no standard name matches, inspect all attributes in the module
    # to find a compatible class based on required methods and naming hints.
    for attr_name in dir(module):
        if attr_name.startswith('_'):
            continue
            
        attr = getattr(module, attr_name)
        if not isinstance(attr, type):
            continue
        
        try:
            instance = attr()
            
            # Check for ToolModule/GetModule methods
            required_methods = ['run_guided', 'run_direct']
            helper_methods = ['_get_name', '_get_category', '_get_description']
            
            has_required = all(hasattr(instance, method) for method in required_methods)
            has_helpers = any(hasattr(instance, method) for method in helper_methods)
            
            if has_required and (has_helpers or 'Module' in attr_name or 'Tool' in attr_name):
                if verbose:
                    print(f"Found compatible class by inspection: {attr_name}")
                return instance, attr_name
                
        except Exception as e:
            if verbose:
                print(f"Could not instantiate {attr_name}: {e}")
            continue
    
    return None, None

def run_module(module_path, module_name, class_name, mode='guided', verbose=False):
    """
    Run a security module in guided or direct mode with enhanced compatibility
    
    Args:
        module_path: Path to the module file
        module_name: Name of the module
        class_name: Name of the class to instantiate (can be None for auto-detection)
        mode: 'guided' or 'direct'
        verbose: Whether to print debug information
    """
    project_root, modules_dir = setup_module_paths()
    
    if verbose:
        print("Python path includes:")
        for path in sys.path[:5]:  # Show first 5 paths
            print(f"  - {path}")
        print(f"\nModule path: {module_path}")
        print(f"Module name: {module_name}")
        print(f"Mode: {mode}")
    
    try:
        # Import the module
        module = None
        
        # Method 1: Attempt direct import using importlib.import_module.
        # This method works well for modules correctly structured within the 'modules' package 
        # (e.g., modules/category/module_name.py or modules/module_name.py).
        try:
            if 'modules' in str(module_path):
                # Build import path
                path_obj = Path(module_path)
                if path_obj.parent.name == 'modules':
                    import_path = f"modules.{module_name}"
                else:
                    category = path_obj.parent.name
                    import_path = f"modules.{category}.{module_name}"
                
                if verbose:
                    print(f"Trying import path: {import_path}")
                
                module = importlib.import_module(import_path)
                if verbose:
                    print("✓ Successfully imported using importlib")
                    
        except ImportError as e:
            if verbose:
                print(f"Import method 1 failed: {e}")
        # End of Method 1
        
        # Method 2: Fallback to spec-based import.
        # This is more flexible and can handle modules located via absolute paths or
        # those not fitting the standard package structure.
        if module is None:
            try:
                if verbose:
                    print("Trying spec-based import...")
                
                spec = importlib.util.spec_from_file_location(module_name, module_path)
                if not spec:
                    raise ImportError(f"Could not create spec for module: {module_path}")
                    
                module = importlib.util.module_from_spec(spec)
                
                # Add to sys.modules before executing.
                # Crucial step: This makes the module available in sys.modules *before* exec_module.
                # This is important if the module being loaded performs any internal relative imports
                # (e.g., from . import utils) as it needs to be recognized as part of a package.
                import_name = f"modules.{module_name}" # Standardized import name
                sys.modules[import_name] = module
                
                spec.loader.exec_module(module) # Actually execute the module code
                
                if verbose:
                    print("✓ Successfully imported using spec")
                    
            except Exception as e:
                if verbose:
                    print(f"Import method 2 failed: {e}")
                # Spec-based import is more flexible but can be more complex if not set up correctly.
                raise ImportError(f"Failed to import module: {e}")
        # End of Method 2
        
        # Find the appropriate class
        instance, found_class_name = find_module_class(module, module_name, verbose)
        
        if not instance:
            raise ValueError(f"Could not find a suitable class in module {module_name}")
        
        if verbose:
            print(f"Using class: {found_class_name}")
        
        # Run the module
        print(f"\n--- Starting {found_class_name} in {mode} mode ---\n")
        
        try:
            if mode == 'guided':
                if hasattr(instance, 'run_guided'):
                    instance.run_guided()
                else:
                    print("Guided mode not available for this module")
                    if hasattr(instance, 'run_direct'):
                        print("Falling back to direct mode...")
                        instance.run_direct()
            else:
                if hasattr(instance, 'run_direct'):
                    instance.run_direct()
                else:
                    print("Direct mode not available for this module")
                    if hasattr(instance, 'run_guided'):
                        print("Falling back to guided mode...")
                        instance.run_guided()
                        
        except KeyboardInterrupt:
            print(f"\n{Colors.WARNING}[!] Module execution interrupted by user{Colors.ENDC}")
        except Exception as e:
            print(f"\n{Colors.FAIL}[!] Error during module execution: {e}{Colors.ENDC}")
            if verbose:
                traceback.print_exc()
            
        print(f"\n--- Module execution completed ---")
        
    except Exception as e:
        print(f"Error executing module: {e}")
        if verbose:
            traceback.print_exc()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Enhanced module runner for CoreSecFrame')
    parser.add_argument('module_info_file', help='Path to JSON file with module information')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')
    
    args = parser.parse_args()
    
    try:
        # Read the module info from the JSON file
        with open(args.module_info_file, 'r') as f:
            module_info = json.load(f)
        
        # Extract class name (can be None for auto-detection)
        class_name = module_info.get('class')
        
        run_module(
            module_info['path'],
            module_info['name'],
            class_name,
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
    except Exception as e:
        print(f"Unexpected error: {e}")
        if args.verbose:
            traceback.print_exc()
        sys.exit(1)