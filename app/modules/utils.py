# app/modules/utils.py
import os
import sys
import importlib
import importlib.util
import requests
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from flask import current_app
from app import db
from app.modules.models import Module, ModuleCategory

def scan_local_modules():
    """
    Scan the modules directory for local modules
    
    Returns:
        tuple: (added_count, updated_count)
    """
    modules_dir = current_app.config['MODULES_DIR']
    module_path = Path(modules_dir)
    
    if not module_path.exists():
        return 0, 0
    
    added_count = 0
    updated_count = 0
    
    # Check modules in the base directory
    for file_path in module_path.glob('*.py'):
        if file_path.name == '__init__.py':
            continue
        
        try:
            # Check if module exists in database
            module_name = file_path.stem
            existing_module = Module.query.filter_by(name=module_name).first()
            
            # Import the module to get details
            spec = importlib.util.spec_from_file_location(module_name, str(file_path))
            if not spec:
                continue
                
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module  # Add to sys.modules to avoid import errors
            spec.loader.exec_module(module)
            
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
                except:
                    continue
            
            if not module_class:
                continue
            
            # Get module info
            name = module_class._get_name()
            category_name = module_class._get_category()
            description = getattr(module_class, '_get_description', lambda: '')()
            command = getattr(module_class, '_get_command', lambda: '')()
            
            # Check if category exists
            category = ModuleCategory.query.filter_by(name=category_name).first()
            if not category:
                category = ModuleCategory(name=category_name)
                db.session.add(category)
            
            # Update or create module
            if existing_module:
                existing_module.description = description
                existing_module.category = category_name
                existing_module.command = command
                existing_module.local_path = str(file_path)
                existing_module.updated_at = datetime.utcnow()
                updated_count += 1
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
            
            db.session.commit()
            
        except Exception as e:
            current_app.logger.error(f"Error scanning module {file_path}: {str(e)}")
    
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
            db.session.commit()
        
        # Check modules in this category
        for file_path in dir_path.glob('*.py'):
            if file_path.name == '__init__.py':
                continue
                
            try:
                # Check if module exists in database
                module_name = file_path.stem
                existing_module = Module.query.filter_by(name=module_name).first()
                
                # Import the module to get details
                import_path = f"modules.{category_name}.{module_name}"
                spec = importlib.util.spec_from_file_location(import_path, str(file_path))
                if not spec:
                    continue
                    
                module = importlib.util.module_from_spec(spec)
                sys.modules[import_path] = module  # Add to sys.modules to avoid import errors
                spec.loader.exec_module(module)
                
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
                    except:
                        continue
                
                if not module_class:
                    continue
                
                # Get module info
                name = module_class._get_name()
                description = getattr(module_class, '_get_description', lambda: '')()
                command = getattr(module_class, '_get_command', lambda: '')()
                
                # Update or create module
                if existing_module:
                    existing_module.description = description
                    existing_module.category = category_name
                    existing_module.command = command
                    existing_module.local_path = str(file_path)
                    existing_module.updated_at = datetime.utcnow()
                    updated_count += 1
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
                
                db.session.commit()
                
            except Exception as e:
                current_app.logger.error(f"Error scanning module {file_path}: {str(e)}")
    
    return added_count, updated_count

def check_module_installed(module_class):
    """
    Check if a module is installed
    
    Args:
        module_class: Instance of module class
        
    Returns:
        bool: True if installed, False otherwise
    """
    try:
        if hasattr(module_class, 'check_installation'):
            return module_class.check_installation()
        
        # Fallback: check if command exists
        if hasattr(module_class, 'command'):
            return shutil.which(module_class.command) is not None
            
        return False
    except:
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
                
    except Exception:
        pass
        
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
        # Check if modules directory exists
        modules_dir = current_app.config['MODULES_DIR']
        module_path = Path(modules_dir)
        
        if not module_path.exists():
            module_path.mkdir(parents=True, exist_ok=True)
        
        # Create base __init__.py if it doesn't exist
        base_init = module_path / "__init__.py"
        if not base_init.exists():
            base_init.touch()
        
        # Set up category directory if needed
        if category != "Uncategorized":
            category_dir = module_path / category
            module_file_path = category_dir / f"{name}.py"
            
            # Create category directory and its __init__.py
            category_dir.mkdir(exist_ok=True)
            category_init = category_dir / "__init__.py"
            if not category_init.exists():
                category_init.touch()
        else:
            module_file_path = module_path / f"{name}.py"

        if module_file_path.exists():
            return True, str(module_file_path), "Module already exists"

        # Download module
        response = requests.get(url)
        response.raise_for_status()
        
        # Save module
        with open(module_file_path, 'wb') as f:
            f.write(response.content)
        
        return True, str(module_file_path), "Module downloaded successfully"
        
    except Exception as e:
        return False, None, str(e)

def install_module(module):
    """
    Install a module
    
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
            return False, "Module file not found"
        
        # Import module
        import_path = f"modules.{module.category}.{module_name}" if module.category != "Uncategorized" else f"modules.{module_name}"
        spec = importlib.util.spec_from_file_location(import_path, str(file_path))
        if not spec:
            return False, "Failed to create module spec"
            
        mod = importlib.util.module_from_spec(spec)
        sys.modules[import_path] = mod  # Add to sys.modules to avoid import errors
        spec.loader.exec_module(mod)
        
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
            except:
                continue
       
        if not module_class:
            return False, "Module class not found"
       
        # Get package manager
        pkg_manager = None
        if hasattr(module_class, 'get_package_manager'):
            pkg_managers = module_class.get_package_manager()
            if pkg_managers and len(pkg_managers) > 0:
                pkg_manager = pkg_managers[0]
       
        if not pkg_manager:
            # Default to apt
            pkg_manager = 'apt'
       
        # Get installation command
        if not hasattr(module_class, '_get_install_command'):
            return False, "Module does not support installation"
           
        commands = module_class._get_install_command(pkg_manager)
       
        if not commands:
            return False, f"No installation command for {pkg_manager}"
       
        # Convert single command to list
        if isinstance(commands, str):
            commands = [commands]
       
        # Execute installation commands
        for cmd in commands:
            result = subprocess.run(
                cmd, 
                shell=True, 
                check=True, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True
            )
           
            if result.returncode != 0:
                return False, f"Command failed: {cmd}\n{result.stderr}"
       
        return True, "Module installed successfully"
       
    except Exception as e:
        return False, str(e)

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
            return False, "Module file not found"
        
        # Import module
        import_path = f"modules.{module.category}.{module_name}" if module.category != "Uncategorized" else f"modules.{module_name}"
        spec = importlib.util.spec_from_file_location(import_path, str(file_path))
        if not spec:
            return False, "Failed to create module spec"
            
        mod = importlib.util.module_from_spec(spec)
        sys.modules[import_path] = mod  # Add to sys.modules to avoid import errors
        spec.loader.exec_module(mod)
        
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
            except:
                continue
       
        if not module_class:
            return False, "Module class not found"
       
        # Get package manager
        pkg_manager = None
        if hasattr(module_class, 'get_package_manager'):
            pkg_managers = module_class.get_package_manager()
            if pkg_managers and len(pkg_managers) > 0:
                pkg_manager = pkg_managers[0]
       
        if not pkg_manager:
            # Default to apt
            pkg_manager = 'apt'
       
        # Get uninstallation command
        if not hasattr(module_class, '_get_uninstall_command'):
            return False, "Module does not support uninstallation"
           
        commands = module_class._get_uninstall_command(pkg_manager)
       
        if not commands:
            return False, f"No uninstallation command for {pkg_manager}"
       
        # Convert single command to list
        if isinstance(commands, str):
            commands = [commands]
       
        # Execute uninstallation commands
        for cmd in commands:
            result = subprocess.run(
                cmd, 
                shell=True, 
                check=True, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True
            )
           
            if result.returncode != 0:
                return False, f"Command failed: {cmd}\n{result.stderr}"
       
        return True, "Module uninstalled successfully"
       
    except Exception as e:
        return False, str(e)