# app/modules/utils.py
import os
import sys
import importlib
import importlib.util
import requests
import shutil
import subprocess
import traceback
import types
from pathlib import Path
from datetime import datetime
from flask import current_app
from app import db
from app.modules.models import Module, ModuleCategory
import shlex

def scan_local_modules():
    """
    Scan the modules directory for local modules
    
    Returns:
        tuple: (added_count, updated_count)
    """
    # Use root modules directory
    modules_dir = current_app.config['MODULES_DIR']
    module_path = Path(modules_dir)
    
    if not module_path.exists():
        os.makedirs(modules_dir, exist_ok=True)
        return 0, 0
    
    added_count = 0
    updated_count = 0
    
    # Check modules in the base directory
    for file_path in module_path.glob('*.py'):
        if file_path.name == '__init__.py':
            continue
        
        try:
            # Import the module to get details
            module_name = file_path.stem
            spec = importlib.util.spec_from_file_location(module_name, str(file_path))
            if not spec:
                continue
                
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module  # Add to sys.modules to avoid import errors
            
            try:
                spec.loader.exec_module(module)
            except Exception as e:
                current_app.logger.error(f"Error executing module {file_path}: {str(e)}")
                continue
            
            # Find the class inheriting from ToolModule or with special methods
            module_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if not isinstance(attr, type):
                    continue
                    
                # Check if this is a ToolModule class or has the required methods
                try:
                    instance = attr()
                    if hasattr(instance, '_get_name') and hasattr(instance, '_get_category'):
                        module_class = instance
                        break
                except Exception as e:
                    current_app.logger.error(f"Error instantiating class {attr_name}: {str(e)}")
                    continue
            
            if not module_class:
                continue
            
            # Get module info
            name = module_class._get_name()
            category_name = getattr(module_class, '_get_category', lambda: 'Uncategorized')()
            description = getattr(module_class, '_get_description', lambda: '')()
            command = getattr(module_class, '_get_command', lambda: '')()
            
            # Check if category exists
            category = ModuleCategory.query.filter_by(name=category_name).first()
            if not category:
                category = ModuleCategory(name=category_name)
                db.session.add(category)
                db.session.commit()
            
            # Check if module exists in database
            existing_module = Module.query.filter_by(name=name).first()
            
            # Update or create module
            if existing_module:
                existing_module.description = description
                existing_module.category = category_name
                existing_module.command = command
                existing_module.local_path = str(file_path)
                existing_module.updated_at = datetime.utcnow()
                db.session.add(existing_module)
                updated_count += 1
                current_app.logger.info(f"Updated module: {name}")
            else:
                new_module = Module(
                    name=name,
                    description=description,
                    category=category_name,
                    command=command,
                    local_path=str(file_path),
                    installed=check_module_installed(module_class)
                )
                db.session.add(new_module)
                added_count += 1
                current_app.logger.info(f"Added module: {name}")
            
            try:
                db.session.commit()
            except sqlalchemy.exc.IntegrityError as e:
                current_app.logger.error(f"Database integrity error for module {name}: {e}")
                db.session.rollback()
            
        except Exception as e:
            current_app.logger.error(f"Error scanning module {file_path}: {str(e)}")
            current_app.logger.error(traceback.format_exc())
            db.session.rollback()
    
    # Check modules in subdirectories (categories)
    for dir_path in module_path.glob('*/'):
        if not dir_path.is_dir() or dir_path.name == '__pycache__':
            continue
            
        # Check if category exists
        category_name = dir_path.name
        category = ModuleCategory.query.filter_by(name=category_name).first()
        if not category:
            category = ModuleCategory(name=category_name)
            db.session.add(category)
            try:
                db.session.commit()
            except Exception as e:
                current_app.logger.error(f"Error adding category {category_name}: {str(e)}")
                db.session.rollback()
        
        # Create __init__.py in category directory if it doesn't exist
        init_file = dir_path / "__init__.py"
        if not init_file.exists():
            with open(init_file, 'w') as f:
                f.write('# Category module initialization\n')
        
        # Check modules in this category
        for file_path in dir_path.glob('*.py'):
            if file_path.name == '__init__.py':
                continue
                
            try:
                # Import the module to get details
                module_name = file_path.stem
                import_path = f"modules.{category_name}.{module_name}"
                spec = importlib.util.spec_from_file_location(import_path, str(file_path))
                if not spec:
                    continue
                    
                module = importlib.util.module_from_spec(spec)
                sys.modules[import_path] = module  # Add to sys.modules to avoid import errors
                
                try:
                    spec.loader.exec_module(module)
                except Exception as e:
                    current_app.logger.error(f"Error executing module {file_path}: {str(e)}")
                    continue
                
                # Find the class inheriting from ToolModule or with special methods
                module_class = None
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if not isinstance(attr, type):
                        continue
                        
                    # Check if this is a ToolModule class or has the required methods
                    try:
                        instance = attr()
                        if hasattr(instance, '_get_name') and hasattr(instance, '_get_category'):
                            module_class = instance
                            break
                    except Exception as e:
                        current_app.logger.error(f"Error instantiating class {attr_name}: {str(e)}")
                        continue
                
                if not module_class:
                    continue
                
                # Get module info
                name = module_class._get_name()
                description = getattr(module_class, '_get_description', lambda: '')()
                command = getattr(module_class, '_get_command', lambda: '')()
                
                # Check if module exists in database
                existing_module = Module.query.filter_by(name=name).first()
                
                # Update or create module
                if existing_module:
                    existing_module.description = description
                    existing_module.category = category_name
                    existing_module.command = command
                    existing_module.local_path = str(file_path)
                    existing_module.updated_at = datetime.utcnow()
                    db.session.add(existing_module)
                    updated_count += 1
                    current_app.logger.info(f"Updated module: {name}")
                else:
                    new_module = Module(
                        name=name,
                        description=description,
                        category=category_name,
                        command=command,
                        local_path=str(file_path),
                        installed=check_module_installed(module_class)
                    )
                    db.session.add(new_module)
                    added_count += 1
                    current_app.logger.info(f"Added module: {name}")
                
                try:
                    db.session.commit()
                except sqlalchemy.exc.IntegrityError as e:
                    current_app.logger.error(f"Database integrity error for module {name}: {e}")
                    db.session.rollback()
                
            except Exception as e:
                current_app.logger.error(f"Error scanning module {file_path}: {str(e)}")
                current_app.logger.error(traceback.format_exc())
                db.session.rollback()
    
    return added_count, updated_count

def clean_module_database():
    """
    Clean up the module database by removing duplicates
    
    Returns:
        int: Number of modules removed
    """
    try:
        # Get all modules
        modules = Module.query.all()
        
        # Group by name
        module_dict = {}
        for module in modules:
            if module.name in module_dict:
                module_dict[module.name].append(module)
            else:
                module_dict[module.name] = [module]
        
        # Find duplicates
        duplicates = {name: modules for name, modules in module_dict.items() if len(modules) > 1}
        
        removed_count = 0
        for name, module_list in duplicates.items():
            # Keep the most recently updated one
            module_list.sort(key=lambda m: m.updated_at if m.updated_at else datetime.min, reverse=True)
            keep_module = module_list[0]
            
            # Remove the rest
            for module in module_list[1:]:
                current_app.logger.info(f"Removing duplicate module: {module.name} (id={module.id})")
                db.session.delete(module)
                removed_count += 1
        
        db.session.commit()
        return removed_count
        
    except Exception as e:
        current_app.logger.error(f"Error cleaning module database: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        db.session.rollback()
        return 0

def check_module_installed(module_class):
    """
    Check if a module is installed
    
    Args:
        module_class: Instance of module class
        
    Returns:
        bool: True if installed, False otherwise
    """
    try:
        # First try the module's own check_installation method if it exists
        if hasattr(module_class, 'check_installation'):
            return module_class.check_installation()
        
        # Then try to get the command and check if it exists in PATH
        if hasattr(module_class, '_get_command'):
            command = module_class._get_command()
            if command:
                return shutil.which(command) is not None
        
        # For modules that don't have a command (e.g. Python-only modules)
        return True
    except Exception as e:
        current_app.logger.error(f"Error checking if module is installed: {str(e)}")
        return False

def fetch_remote_modules():
    """
    Fetch available modules from remote repository
    
    Returns:
        list: List of module dictionaries
    """
    try:
        # Default repository URL
        repo_url = current_app.config.get('MODULES_REPOSITORY_URL', 
                                         "https://github.com/CoreSecFrame/CoreSecFrame-Modules")
        api_url = repo_url.replace("github.com", "api.github.com/repos")
        if api_url.endswith("/"):
            api_url = api_url[:-1]
        api_url += "/contents"
        
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "CoreSecFrameWeb"
        }
        
        # Fetch repository contents recursively
        def fetch_repo_contents(api_url, path=""):
            contents = []
            current_url = f"{api_url}/{path}".rstrip('/')
            
            response = requests.get(current_url, headers=headers)
            response.raise_for_status()
            
            for item in response.json():
                if item["type"] == "dir":
                    # Recursively fetch contents of subdirectory
                    contents.extend(fetch_repo_contents(api_url, item["path"]))
                elif item["type"] == "file" and item["name"].endswith(".py"):
                    # Add file details to contents
                    contents.append({
                        "path": item["path"],
                        "name": item["name"],
                        "url": item["html_url"].replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
                    })
                    
            return contents
        
        # Fetch all repository contents
        module_files = fetch_repo_contents(api_url)
        
        # Process module files
        modules = []
        for item in module_files:
            try:
                # Get file content
                file_response = requests.get(item["url"], headers=headers)
                file_response.raise_for_status()
                content = file_response.text
                
                # Parse module info
                name = item["name"].replace(".py", "")
                description, category = parse_module_info(content)
                
                # If category not explicitly defined, use directory name
                if category == "Uncategorized" and "/" in item["path"]:
                    category = item["path"].split("/")[0]
                
                modules.append({
                    "name": name,
                    "description": description,
                    "category": category,
                    "url": item["url"],
                    "filename": item["name"],
                    "path": item["path"]
                })
            except Exception as e:
                current_app.logger.error(f"Error processing module {item['name']}: {str(e)}")
        
        return modules
    except Exception as e:
        current_app.logger.error(f"Error fetching remote modules: {str(e)}")
        return []

def parse_module_info(content):
    """
    Parse module metadata from content
    
    Args:
        content: Module file content
        
    Returns:
        tuple: (description, category)
    """
    import re
    
    description = "No description"
    category = "Uncategorized"
    
    try:
        # Look for category in _get_category()
        if "_get_category" in content:
            cat_match = re.search(r'def\s+_get_category.*?return\s+[\'"](.+?)[\'"]', content, re.DOTALL)
            if cat_match:
                category = cat_match.group(1)
        
        # Look for description in _get_description() or docstring
        if "_get_description" in content:
            desc_match = re.search(r'def\s+_get_description.*?return\s+[\'"](.+?)[\'"]', content, re.DOTALL)
            if desc_match:
                description = desc_match.group(1)
        elif '"""' in content:
            doc_start = content.find('"""') + 3
            doc_end = content.find('"""', doc_start)
            if doc_end > doc_start:
                description = content[doc_start:doc_end].strip().split('\n')[0]
                
    except Exception as e:
        current_app.logger.error(f"Error parsing module info: {str(e)}")
        
    return description, category

def download_module(url, name, category):
    """
    Download a module from URL
    
    Args:
        url: Module URL
        name: Module name
        category: Module category
        
    Returns:
        tuple: (success, local_path, message)
    """
    try:
        # Use root modules directory
        modules_dir = current_app.config['MODULES_DIR']
        module_path = Path(modules_dir)
        
        current_app.logger.info(f"Downloading module to: {modules_dir}")
        
        if not module_path.exists():
            module_path.mkdir(parents=True, exist_ok=True)
            current_app.logger.info(f"Created modules directory: {modules_dir}")
        
        # Create base __init__.py if it doesn't exist
        base_init = module_path / "__init__.py"
        if not base_init.exists():
            with open(base_init, 'w') as f:
                f.write('# This file makes the modules directory a Python package\n')
            current_app.logger.info(f"Created base __init__.py at: {base_init}")
        
        # Set up category directory if needed
        if category != "Uncategorized":
            category_dir = module_path / category
            module_file_path = category_dir / f"{name}.py"
            
            # Create category directory and its __init__.py
            category_dir.mkdir(exist_ok=True)
            current_app.logger.info(f"Created/checked category directory: {category_dir}")
            
            category_init = category_dir / "__init__.py"
            if not category_init.exists():
                with open(category_init, 'w') as f:
                    f.write(f'# {category} modules initialization\n')
                current_app.logger.info(f"Created category __init__.py at: {category_init}")
        else:
            module_file_path = module_path / f"{name}.py"

        current_app.logger.info(f"Module will be saved to: {module_file_path}")
        
        if module_file_path.exists():
            current_app.logger.info(f"Module already exists at: {module_file_path}")
            return True, str(module_file_path), "Module already exists"

        # Download module
        current_app.logger.info(f"Downloading from URL: {url}")
        response = requests.get(url)
        response.raise_for_status()
        
        # Save module
        with open(module_file_path, 'wb') as f:
            f.write(response.content)
        
        current_app.logger.info(f"Successfully saved module to: {module_file_path}")
        return True, str(module_file_path), "Module downloaded successfully"
        
    except Exception as e:
        current_app.logger.error(f"Error downloading module: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return False, None, str(e)
        
def install_module(module, use_sudo=True, sudo_password=None):
    """
    Install a module
    
    Args:
        module: Module object
        use_sudo: Whether to use sudo for commands
        sudo_password: Sudo password if needed
        
    Returns:
        tuple: (success, message)
    """
    try:
        # Load module
        file_path = Path(module.local_path)
        module_name = file_path.stem
        
        if not file_path.exists():
            return False, "Module file not found"
        
        current_app.logger.info(f"Installing module: {module_name} from {file_path}")
        
        # Add modules directory to Python path
        modules_dir = current_app.config['MODULES_DIR']
        project_dir = str(Path(modules_dir).parent)
        
        # Make sure needed directories are in sys.path
        if project_dir not in sys.path:
            sys.path.insert(0, project_dir)
        
        if modules_dir not in sys.path:
            sys.path.insert(0, modules_dir)
        
        current_app.logger.info(f"Python path: {sys.path}")
        
        # Determine the import path
        if 'modules' in str(file_path.parent.name):
            # Module is in the modules directory
            import_path = f"modules.{module_name}"
        else:
            # Module is in a subdirectory
            category = file_path.parent.name
            import_path = f"modules.{category}.{module_name}"
        
        current_app.logger.info(f"Import path: {import_path}")
        
        # Import the module
        try:
            # Try direct import first
            try:
                mod = importlib.import_module(import_path)
                current_app.logger.info(f"Imported module using importlib.import_module")
            except ImportError:
                # If that fails, use spec_from_file_location
                spec = importlib.util.spec_from_file_location(import_path, str(file_path))
                if not spec:
                    return False, f"Failed to create module spec for {file_path}"
                
                mod = importlib.util.module_from_spec(spec)
                sys.modules[import_path] = mod
                spec.loader.exec_module(mod)
                current_app.logger.info(f"Imported module using spec_from_file_location")
                
        except ImportError as e:
            # Check if it's the core module that's missing
            if "No module named 'core'" in str(e):
                current_app.logger.error(f"Core module not found: {e}")
                return False, f"Module depends on 'core' module. Make sure it exists in {modules_dir}/core"
            else:
                current_app.logger.error(f"Import error: {e}")
                return False, f"Error importing module: {str(e)}"
        except Exception as e:
            current_app.logger.error(f"Error executing module: {e}")
            return False, f"Error loading module: {str(e)}"
        
        # Find the module class
        module_class = None
        class_name = None
        
        # First, try to find a class with the same name as the module
        capitalized_name = module_name.capitalize()
        if hasattr(mod, capitalized_name):
            class_attr = getattr(mod, capitalized_name)
            if isinstance(class_attr, type):
                try:
                    instance = class_attr()
                    if hasattr(instance, '_get_name') and hasattr(instance, '_get_category'):
                        module_class = instance
                        class_name = capitalized_name
                        current_app.logger.info(f"Found module class with capitalized name: {class_name}")
                except Exception as e:
                    current_app.logger.error(f"Error instantiating class {capitalized_name}: {e}")
        
        # If not found, try other classes
        if module_class is None:
            for attr_name in dir(mod):
                if attr_name.startswith('__'):
                    continue
                
                attr = getattr(mod, attr_name)
                if not isinstance(attr, type):
                    continue
                
                try:
                    instance = attr()
                    if hasattr(instance, '_get_name') and hasattr(instance, '_get_category'):
                        module_class = instance
                        class_name = attr_name
                        current_app.logger.info(f"Found module class: {class_name}")
                        break
                except Exception as e:
                    current_app.logger.error(f"Error instantiating class {attr_name}: {e}")
        
        # If still no module class found, try to find any class and make it work
        if module_class is None:
            for attr_name in dir(mod):
                if attr_name.startswith('__'):
                    continue
                
                attr = getattr(mod, attr_name)
                if not isinstance(attr, type):
                    continue
                
                try:
                    instance = attr()
                    class_name = attr_name
                    # Add missing methods if needed
                    if not hasattr(instance, '_get_name'):
                        setattr(instance.__class__, '_get_name', lambda self: module_name)
                    if not hasattr(instance, '_get_category'):
                        setattr(instance.__class__, '_get_category', lambda self: "Uncategorized")
                    if not hasattr(instance, '_get_description'):
                        setattr(instance.__class__, '_get_description', lambda self: "No description provided")
                    if not hasattr(instance, '_get_command'):
                        setattr(instance.__class__, '_get_command', lambda self: "")
                    if not hasattr(instance, '_get_install_command'):
                        setattr(instance.__class__, '_get_install_command', lambda self, pkg_manager: [])
                    
                    module_class = instance
                    current_app.logger.info(f"Using class with added methods: {class_name}")
                    break
                except Exception as e:
                    current_app.logger.error(f"Error using class {attr_name}: {e}")
        
        if not module_class:
            return False, "No suitable module class found in the module file"
        
        # Get package manager
        pkg_manager = None
        if hasattr(module_class, 'get_package_manager'):
            try:
                pkg_managers = module_class.get_package_manager()
                if pkg_managers and len(pkg_managers) > 0:
                    pkg_manager = pkg_managers[0]
            except Exception as e:
                current_app.logger.error(f"Error getting package manager: {e}")
        
        if not pkg_manager:
            # Detect the system's package manager
            if shutil.which('apt-get'):
                pkg_manager = 'apt'
            elif shutil.which('yum'):
                pkg_manager = 'yum'
            elif shutil.which('dnf'):
                pkg_manager = 'dnf'
            elif shutil.which('pacman'):
                pkg_manager = 'pacman'
            else:
                pkg_manager = 'apt'  # Default to apt
        
        current_app.logger.info(f"Using package manager: {pkg_manager}")
        
        # Get installation command
        if not hasattr(module_class, '_get_install_command'):
            # If the module doesn't have an install command, consider it already installed
            module.installed = True
            module.installed_date = datetime.utcnow()
            db.session.commit()
            return True, f"Module {module_name} installed successfully (no installation needed)"
        
        # Get installation commands
        try:
            commands = module_class._get_install_command(pkg_manager)
            
            # If commands is None, handle it gracefully
            if commands is None:
                commands = []
        except Exception as e:
            current_app.logger.error(f"Error getting install commands: {e}")
            return False, f"Error getting installation commands: {str(e)}"
        
        if not commands:
            # If there are no commands, just mark as installed
            module.installed = True
            module.installed_date = datetime.utcnow()
            db.session.commit()
            return True, f"Module {module_name} installed successfully (no commands needed)"
        
        # Convert single command to list
        if isinstance(commands, str):
            commands = [commands]
        
        current_app.logger.info(f"Installation commands: {commands}")
        
        # Execute installation commands
        all_output = []
        for cmd in commands:
            # Modify command to use sudo if needed
            original_cmd = cmd
            if use_sudo and not cmd.startswith('sudo ') and sudo_password:
                # Use echo to pipe password to sudo without showing in logs
                cmd = f"echo {shlex.quote(sudo_password)} | sudo -S {cmd}"
            elif use_sudo and not cmd.startswith('sudo '):
                # Add sudo but without password
                cmd = f"sudo {cmd}"
            
            current_app.logger.info(f"Executing command: {original_cmd}")
            result = subprocess.run(
                cmd, 
                shell=True, 
                check=False,  # Don't raise exception on error
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True
            )
            
            all_output.append(f"Command: {original_cmd}")
            all_output.append(f"Exit code: {result.returncode}")
            all_output.append(f"Output: {result.stdout}")
            
            if result.returncode != 0:
                all_output.append(f"Error: {result.stderr}")
                # Check for sudo password errors
                if "incorrect password" in result.stderr.lower() or "sorry, try again" in result.stderr.lower():
                    return False, "Incorrect sudo password. Please try again."
                current_app.logger.error(f"Command failed: {original_cmd}\n{result.stderr}")
                return False, "\n".join(all_output)
        
        # Update module status
        module.installed = True
        module.installed_date = datetime.utcnow()
        db.session.commit()
        
        all_output.append(f"Module {module_name} installed successfully")
        current_app.logger.info(f"Module {module_name} installed successfully")
        
        return True, "\n".join(all_output)
        
    except Exception as e:
        current_app.logger.error(f"Error installing module: {e}")
        current_app.logger.error(traceback.format_exc())
        return False, f"Error installing module: {str(e)}"

def uninstall_module(module):
    """
    Uninstall a module
    
    Args:
        module: Module object
        
    Returns:
        tuple: (success, message)
    """
    try:
        # Load module
        file_path = Path(module.local_path)
        module_name = file_path.stem
        
        if not file_path.exists():
            # If file doesn't exist, just mark as uninstalled in database
            module.installed = False
            db.session.commit()
            return True, "Module file not found, marked as uninstalled"
        
        # Get the proper import path
        if str(file_path.parent).endswith('modules'):
            # Module is in the base modules directory
            import_path = f"modules.{module_name}"
        else:
            # Module is in a category subdirectory
            category = file_path.parent.name
            import_path = f"modules.{category}.{module_name}"
        
        # Add modules directory to Python path
        modules_dir = current_app.config['MODULES_DIR']
        modules_parent = str(Path(modules_dir).parent)
        if modules_parent not in sys.path:
            sys.path.insert(0, modules_parent)
        
        # Import module
        current_app.logger.info(f"Importing module from {file_path} with path {import_path}")
        
        spec = importlib.util.spec_from_file_location(import_path, str(file_path))
        if not spec:
            # If we can't import, just mark as uninstalled
            module.installed = False
            db.session.commit()
            return True, "Failed to create module spec, marked as uninstalled"
            
        mod = importlib.util.module_from_spec(spec)
        sys.modules[import_path] = mod  # Add to sys.modules to avoid import errors
        
        try:
            spec.loader.exec_module(mod)
        except Exception as e:
            current_app.logger.error(f"Error executing module: {str(e)}")
            # If we can't execute the module, just mark as uninstalled
            module.installed = False
            db.session.commit()
            return True, f"Error loading module: {str(e)}, marked as uninstalled"
        
        # Find the module class
        module_class = None
        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)
            if not isinstance(attr, type):
                continue
                
            # Check if this is a ToolModule class or has the required methods
            try:
                instance = attr()
                if hasattr(instance, '_get_name') and hasattr(instance, '_get_category'):
                    module_class = instance
                    break
            except Exception as e:
                current_app.logger.error(f"Error instantiating class {attr_name}: {str(e)}")
                continue
       
        if not module_class:
            # If we can't find the class, just mark as uninstalled
            module.installed = False
            db.session.commit()
            return True, "Module class not found, marked as uninstalled"
        
        current_app.logger.info(f"Found module class: {module_class.__class__.__name__}")
       
        # Get package manager
        pkg_manager = None
        if hasattr(module_class, 'get_package_manager'):
            pkg_managers = module_class.get_package_manager()
            if pkg_managers and len(pkg_managers) > 0:
                pkg_manager = pkg_managers[0]
       
        if not pkg_manager:
            # Detect the system's package manager
            if shutil.which('apt-get'):
                pkg_manager = 'apt'
            elif shutil.which('yum'):
                pkg_manager = 'yum'
            elif shutil.which('dnf'):
                pkg_manager = 'dnf'
            elif shutil.which('pacman'):
                pkg_manager = 'pacman'
            else:
                pkg_manager = 'apt'  # Default to apt
        
        current_app.logger.info(f"Using package manager: {pkg_manager}")
       
        # Get uninstallation command
        if not hasattr(module_class, '_get_uninstall_command'):
            # If the module doesn't have an uninstall command, just mark as uninstalled
            module.installed = False
            db.session.commit()
            return True, "Module doesn't have uninstallation method, marked as uninstalled"
           
        commands = module_class._get_uninstall_command(pkg_manager)
       
        if not commands:
            # If there are no commands for this package manager, just mark as uninstalled
            module.installed = False
            db.session.commit()
            return True, f"No uninstallation command for {pkg_manager}, marked as uninstalled"
       
        # Convert single command to list
        if isinstance(commands, str):
            commands = [commands]
        
        current_app.logger.info(f"Uninstallation commands: {commands}")
       
        # Execute uninstallation commands
        all_output = []
        for cmd in commands:
            current_app.logger.info(f"Executing command: {cmd}")
            result = subprocess.run(
                cmd, 
                shell=True, 
                check=False,  # Don't raise exception on error
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True
            )
            
            all_output.append(f"Command: {cmd}")
            all_output.append(f"Exit code: {result.returncode}")
            all_output.append(f"Output: {result.stdout}")
            
            if result.returncode != 0:
                all_output.append(f"Error: {result.stderr}")
                current_app.logger.warning(f"Command failed: {cmd}\n{result.stderr}")
                # Continue with other commands even if one fails
        
        # Update module status
        module.installed = False
        db.session.commit()
        
        all_output.append("Module uninstalled successfully")
        current_app.logger.info(f"Module {module_name} uninstalled successfully")
       
        return True, "\n".join(all_output)
       
    except Exception as e:
        current_app.logger.error(f"Error uninstalling module: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return False, str(e)

def delete_module(module):
    """
    Delete a module file and its database entry
    
    Args:
        module: Module object
        
    Returns:
        tuple: (success, message)
    """
    try:
        # First make sure it's uninstalled
        if module.installed:
            success, message = uninstall_module(module)
            if not success:
                return False, f"Failed to uninstall module before deletion: {message}"
        
        # Delete the file
        file_path = Path(module.local_path)
        module_name = module.name
        category = module.category
        
        current_app.logger.info(f"Deleting module file: {file_path}")
        
        if file_path.exists():
            try:
                os.remove(file_path)
                current_app.logger.info(f"Deleted module file: {file_path}")
            except Exception as e:
                current_app.logger.error(f"Error deleting module file {file_path}: {str(e)}")
                return False, f"Failed to delete module file: {str(e)}"
            
            # Check if directory is empty (except for __init__.py) and remove if needed
            dir_path = file_path.parent
            if not str(dir_path).endswith('modules'):  # Don't delete the main modules directory
                files = list(dir_path.glob('*'))
                if len(files) <= 1 and all(f.name == '__init__.py' for f in files):
                    # Directory only has __init__.py or is empty, we can remove __init__.py and the directory
                    init_file = dir_path / '__init__.py'
                    if init_file.exists():
                        try:
                            os.remove(init_file)
                            current_app.logger.info(f"Deleted init file: {init_file}")
                        except Exception as e:
                            current_app.logger.error(f"Error deleting init file {init_file}: {str(e)}")
                    
                    try:
                        os.rmdir(dir_path)
                        current_app.logger.info(f"Deleted empty directory: {dir_path}")
                    except OSError as e:
                        # Directory not empty, just leave it
                        current_app.logger.warning(f"Could not remove directory {dir_path}: {str(e)}")
        else:
            current_app.logger.warning(f"Module file not found: {file_path}")
        
        # Remove from database
        db.session.delete(module)
        db.session.commit()
        
        current_app.logger.info(f"Module {module_name} deleted successfully")
        return True, f"Module {module_name} deleted successfully"
        
    except Exception as e:
        current_app.logger.error(f"Error deleting module: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        db.session.rollback()
        return False, str(e)

def import_module_from_path(file_path, add_to_path=True):
    """
    Import a module from a file path
    
    Args:
        file_path: Path to the module file
        add_to_path: Whether to add the module's parent directories to sys.path
        
    Returns:
        tuple: (module, error_message)
    """
    try:
        file_path = Path(file_path)
        module_name = file_path.stem
        
        if add_to_path:
            # Add parent directories to sys.path
            parent_dir = file_path.parent
            project_root = parent_dir.parent
            
            if str(parent_dir) not in sys.path:
                sys.path.insert(0, str(parent_dir))
            
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))
            
            # If this is a module in a subdirectory, make sure the subdirectory is in the path
            if parent_dir.name != 'modules':
                modules_dir = parent_dir.parent
                if str(modules_dir) not in sys.path:
                    sys.path.insert(0, str(modules_dir))
        
        # Check if it's part of a package
        import_path = module_name
        if 'modules' in str(file_path):
            if file_path.parent.name == 'modules':
                import_path = f"modules.{module_name}"
            else:
                category = file_path.parent.name
                import_path = f"modules.{category}.{module_name}"
        
        current_app.logger.info(f"Python path: {sys.path}")
        current_app.logger.info(f"Importing module from {file_path} with path {import_path}")
        
        # Try to import the module
        try:
            # First try direct import
            spec = importlib.util.find_spec(import_path)
            if spec:
                module = importlib.import_module(import_path)
                return module, None
            
            # If that fails, try spec_from_file_location
            spec = importlib.util.spec_from_file_location(import_path, str(file_path))
            if not spec:
                return None, f"Failed to create module spec for {file_path}"
            
            module = importlib.util.module_from_spec(spec)
            sys.modules[import_path] = module
            spec.loader.exec_module(module)
            return module, None
            
        except ImportError as e:
            # Try to handle missing core module
            if "No module named 'core'" in str(e):
                # Try to modify the module content to remove core imports
                with open(file_path, 'r') as f:
                    content = f.read()
                
                # Check if we can patch the imports
                if "from core." in content:
                    current_app.logger.info(f"Module uses 'from core.' imports. Attempting to patch...")
                    
                    # Create a temporary module with modified imports
                    temp_content = content.replace("from core.", "# from core.")
                    
                    # Create a temporary module
                    temp_module = types.ModuleType(import_path)
                    exec(temp_content, temp_module.__dict__)
                    
                    return temp_module, None
                
                # If we can't patch it, create a basic module without the core dependency
                return None, f"Module depends on 'core' module. Try installing the core module first."
            
            return None, f"ImportError: {str(e)}"
            
        except Exception as e:
            return None, f"Error importing module: {str(e)}"
    
    except Exception as e:
        current_app.logger.error(f"Error in import_module_from_path: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return None, str(e)