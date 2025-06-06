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
    Scan the modules directory for local modules with deduplication
    
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
    
    # Define protected modules that should not be listed
    protected_modules = [
        'base',         # The base module class
        'colors',       # Core utility for terminal colors
        '__init__',     # Package initialization files
        '__pycache__',  # Python cache directories
    ]
    
    # Track processed files to avoid duplicates
    processed_files = set()
    
    def process_module_file(file_path, category_name=None):
        """Process a single module file and return module info"""
        nonlocal added_count, updated_count
        
        # Skip if already processed
        file_key = str(file_path.resolve())
        if file_key in processed_files:
            current_app.logger.info(f"Skipping already processed file: {file_path}")
            return
        processed_files.add(file_key)
        
        # Skip protected modules
        if file_path.stem in protected_modules:
            current_app.logger.info(f"Skipping protected module: {file_path.stem}")
            return
            
        if file_path.name == '__init__.py':
            return
        
        try:
            # Import the module to get details
            module_file_name = file_path.stem
            
            # Determine import path
            if category_name:
                import_path = f"modules.{category_name}.{module_file_name}"
            else:
                import_path = f"modules.{module_file_name}"
            
            spec = importlib.util.spec_from_file_location(import_path, str(file_path))
            if not spec:
                current_app.logger.warning(f"Could not create spec for {file_path}")
                return
                
            module = importlib.util.module_from_spec(spec)
            sys.modules[import_path] = module  # Add to sys.modules to avoid import errors
            
            try:
                spec.loader.exec_module(module)
            except Exception as e:
                current_app.logger.error(f"Error executing module {file_path}: {str(e)}")
                return
            
            # Find the class inheriting from ToolModule or with special methods
            module_class = None
            class_candidates = []
            
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if not isinstance(attr, type):
                    continue
                    
                # Check if this is a ToolModule class or has the required methods
                try:
                    instance = attr()
                    if hasattr(instance, '_get_name') and hasattr(instance, '_get_category'):
                        class_candidates.append((attr_name, instance))
                except Exception as e:
                    current_app.logger.debug(f"Error instantiating class {attr_name}: {str(e)}")
                    continue
            
            if not class_candidates:
                current_app.logger.warning(f"No valid module class found in {file_path}")
                return
            
            # Choose the best class candidate
            # Priority: 1) Class name matches file name, 2) First valid class
            module_class = None
            for class_name, instance in class_candidates:
                if class_name.lower() == module_file_name.lower():
                    module_class = instance
                    break
                elif class_name.lower().replace('module', '') == module_file_name.lower().replace('_module', ''):
                    module_class = instance
                    break
            
            # If no priority match, use the first candidate
            if not module_class and class_candidates:
                module_class = class_candidates[0][1]
            
            if not module_class:
                return
            
            # Get module info from the class
            class_name = module_class._get_name()
            class_category = getattr(module_class, '_get_category', lambda: 'Uncategorized')()
            description = getattr(module_class, '_get_description', lambda: '')()
            command = getattr(module_class, '_get_command', lambda: '')()
            
            # Use category from directory structure if class doesn't specify or specifies 'Uncategorized'
            if category_name and (class_category == 'Uncategorized' or not class_category):
                final_category = category_name
            else:
                final_category = class_category
            
            # UNIFIED NAMING STRATEGY: Use file name as the primary identifier
            # This prevents duplicates from different class names in the same file
            unified_module_name = module_file_name
            
            current_app.logger.info(f"Processing module: file={module_file_name}, class_name={class_name}, unified_name={unified_module_name}")
            
            # Check if category exists
            category = ModuleCategory.query.filter_by(name=final_category).first()
            if not category:
                category = ModuleCategory(name=final_category)
                db.session.add(category)
                try:
                    db.session.commit()
                except Exception as e:
                    current_app.logger.error(f"Error adding category {final_category}: {str(e)}")
                    db.session.rollback()
            
            # Check if module exists in database BY FILE PATH (most reliable identifier)
            existing_module = Module.query.filter_by(local_path=str(file_path)).first()
            
            # If not found by path, check by unified name (but prefer path-based lookup)
            if not existing_module:
                existing_module = Module.query.filter_by(name=unified_module_name).first()
            
            # Update or create module
            if existing_module:
                # Update existing module
                existing_module.name = unified_module_name  # Ensure consistent naming
                existing_module.description = description
                existing_module.category = final_category
                existing_module.command = command
                existing_module.local_path = str(file_path)  # Ensure path is current
                existing_module.updated_at = datetime.utcnow()
                db.session.add(existing_module)
                updated_count += 1
                current_app.logger.info(f"Updated module: {unified_module_name}")
            else:
                # Create new module
                new_module = Module(
                    name=unified_module_name,
                    description=description,
                    category=final_category,
                    command=command,
                    local_path=str(file_path),
                    installed=check_module_installed(module_class)
                )
                db.session.add(new_module)
                added_count += 1
                current_app.logger.info(f"Added module: {unified_module_name}")
            
            try:
                db.session.commit()
            except Exception as e:
                current_app.logger.error(f"Database error for module {unified_module_name}: {e}")
                db.session.rollback()
            
        except Exception as e:
            current_app.logger.error(f"Error scanning module {file_path}: {str(e)}")
            current_app.logger.error(traceback.format_exc())
            db.session.rollback()
    
    # Check modules in the base directory
    for file_path in module_path.glob('*.py'):
        process_module_file(file_path)
    
    # Check modules in subdirectories (categories)
    for dir_path in module_path.glob('*/'):
        if not dir_path.is_dir() or dir_path.name == '__pycache__':
            continue
            
        # Skip the core directory entirely - it contains system modules
        if dir_path.name == 'core':
            current_app.logger.info(f"Skipping core system modules directory")
            continue
        
        category_name = dir_path.name
        
        # Create __init__.py in category directory if it doesn't exist
        init_file = dir_path / "__init__.py"
        if not init_file.exists():
            with open(init_file, 'w') as f:
                f.write('# Category module initialization\n')
        
        # Check modules in this category
        for file_path in dir_path.glob('*.py'):
            process_module_file(file_path, category_name)
    
    return added_count, updated_count

def clean_module_database():
    """
    Clean up the module database by removing duplicates and orphaned entries
    
    Returns:
        int: Number of modules removed
    """
    try:
        current_app.logger.info("Starting enhanced module database cleanup...")
        
        # Get all modules
        modules = Module.query.all()
        removed_count = 0
        
        # Step 1: Remove modules with non-existent files (orphaned entries)
        orphaned_modules = []
        for module in modules:
            if module.local_path and not Path(module.local_path).exists():
                orphaned_modules.append(module)
        
        for module in orphaned_modules:
            current_app.logger.info(f"Removing orphaned module: {module.name} (file not found: {module.local_path})")
            db.session.delete(module)
            removed_count += 1
        
        # Step 2: Group remaining modules by file path to find duplicates
        path_groups = {}
        for module in Module.query.all():  # Re-query after orphan removal
            if module.local_path:
                abs_path = str(Path(module.local_path).resolve())
                if abs_path not in path_groups:
                    path_groups[abs_path] = []
                path_groups[abs_path].append(module)
        
        # Step 3: Resolve duplicates by file path
        for file_path, module_list in path_groups.items():
            if len(module_list) > 1:
                current_app.logger.info(f"Found {len(module_list)} duplicates for file: {file_path}")
                
                # Sort by preference: installed modules first, then by most recent update
                module_list.sort(key=lambda m: (
                    m.installed,  # Installed modules first
                    m.updated_at if m.updated_at else datetime.min,  # Most recent update
                    m.created_at if m.created_at else datetime.min   # Most recent creation
                ), reverse=True)
                
                # Keep the best module (first in sorted list)
                keep_module = module_list[0]
                
                # Get the file name for consistent naming
                file_name = Path(file_path).stem
                
                # Update the kept module to use file-based naming
                keep_module.name = file_name
                db.session.add(keep_module)
                
                current_app.logger.info(f"Keeping module: {keep_module.name} (id={keep_module.id}, installed={keep_module.installed})")
                
                # Remove the rest
                for module in module_list[1:]:
                    current_app.logger.info(f"Removing duplicate module: {module.name} (id={module.id})")
                    db.session.delete(module)
                    removed_count += 1
        
        # Step 4: Handle name-based duplicates (modules with same name but different paths)
        name_groups = {}
        for module in Module.query.all():  # Re-query after path-based cleanup
            if module.name not in name_groups:
                name_groups[module.name] = []
            name_groups[module.name].append(module)
        
        for module_name, module_list in name_groups.items():
            if len(module_list) > 1:
                current_app.logger.info(f"Found {len(module_list)} modules with same name: {module_name}")
                
                # Check if they're actually different files or just naming conflicts
                unique_paths = set(m.local_path for m in module_list if m.local_path)
                
                if len(unique_paths) > 1:
                    # Different files with same name - rename to avoid conflicts
                    for i, module in enumerate(module_list):
                        if i > 0:  # Keep first one as-is, rename others
                            file_path = Path(module.local_path) if module.local_path else None
                            if file_path:
                                category_suffix = f"_{file_path.parent.name}" if file_path.parent.name != 'modules' else ""
                                new_name = f"{module_name}{category_suffix}_{i}"
                                current_app.logger.info(f"Renaming module {module.name} to {new_name} to avoid conflict")
                                module.name = new_name
                                db.session.add(module)
                elif len(unique_paths) == 1:
                    # Same file, different entries - this shouldn't happen after path-based cleanup
                    # but let's handle it just in case
                    module_list.sort(key=lambda m: (
                        m.installed,
                        m.updated_at if m.updated_at else datetime.min
                    ), reverse=True)
                    
                    keep_module = module_list[0]
                    current_app.logger.info(f"Keeping name-duplicate module: {keep_module.name} (id={keep_module.id})")
                    
                    for module in module_list[1:]:
                        current_app.logger.info(f"Removing name-duplicate module: {module.name} (id={module.id})")
                        db.session.delete(module)
                        removed_count += 1
        
        # Step 5: Clean up empty categories
        all_categories = ModuleCategory.query.all()
        for category in all_categories:
            module_count = Module.query.filter_by(category=category.name).count()
            if module_count == 0:
                current_app.logger.info(f"Removing empty category: {category.name}")
                db.session.delete(category)
        
        # Commit all changes
        db.session.commit()
        
        current_app.logger.info(f"Database cleanup completed. Removed {removed_count} duplicate/orphaned modules.")
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
    Parse module metadata from content - handles Python type annotations
    
    Args:
        content: Module file content
        
    Returns:
        tuple: (description, category)
    """
    import re
    
    description = "No description"
    category = "Uncategorized"
    
    try:
        # Pattern for methods with type annotations: def _get_category(self) -> str:
        # Also handles methods without type annotations: def _get_category(self):
        
        # Category patterns - handle both with and without type annotations
        cat_patterns = [
            # With type annotation: def _get_category(self) -> str: return "OSINT"
            r'def\s+_get_category\s*\([^)]*\)\s*(?:->\s*\w+\s*)?:\s*return\s+["\']([^"\']+)["\']',
            # Multi-line with type annotation
            r'def\s+_get_category\s*\([^)]*\)\s*(?:->\s*\w+\s*)?:\s*\n\s*return\s+["\']([^"\']+)["\']',
            # With other code in between
            r'def\s+_get_category\s*\([^)]*\)\s*(?:->\s*\w+\s*)?:.*?return\s+["\']([^"\']+)["\']'
        ]
        
        for pattern in cat_patterns:
            cat_match = re.search(pattern, content, re.DOTALL)
            if cat_match:
                potential_category = cat_match.group(1).strip()
                # Validate it's a reasonable category name
                if (len(potential_category) < 50 and 
                    not any(bad in potential_category.lower() for bad in ['def', 'return', 'self', 'get_'])):
                    category = potential_category
                    break
        
        # Description patterns - handle both with and without type annotations  
        desc_patterns = [
            # With type annotation: def _get_description(self) -> str: return "description"
            r'def\s+_get_description\s*\([^)]*\)\s*(?:->\s*\w+\s*)?:\s*return\s+["\']([^"\']+)["\']',
            # Multi-line with type annotation
            r'def\s+_get_description\s*\([^)]*\)\s*(?:->\s*\w+\s*)?:\s*\n\s*return\s+["\']([^"\']+)["\']',
            # With other code in between
            r'def\s+_get_description\s*\([^)]*\)\s*(?:->\s*\w+\s*)?:.*?return\s+["\']([^"\']+)["\']'
        ]
        
        for pattern in desc_patterns:
            desc_match = re.search(pattern, content, re.DOTALL)
            if desc_match:
                potential_description = desc_match.group(1).strip()
                # Validate it's a reasonable description
                if (len(potential_description) < 300 and 
                    not any(bad in potential_description.lower() for bad in ['def', 'return', 'self'])):
                    description = potential_description
                    break
        
        # Fallback for description: try to find class docstring
        if description == "No description":
            class_doc_pattern = r'class\s+\w+.*?:\s*["\']([^"\']{15,100})["\']'
            doc_match = re.search(class_doc_pattern, content, re.DOTALL)
            if doc_match:
                doc_text = doc_match.group(1).strip()
                # Take first line if multiline
                first_line = doc_text.split('\n')[0].strip()
                if first_line and len(first_line) > 10:
                    description = first_line
                    
    except Exception as e:
        # Silent failure
        pass
    
    # Final cleanup
    if category and any(bad in category.lower() for bad in ['def ', 'return', 'self', 'get_command', 'get_name']):
        category = "Uncategorized"
    
    if description and any(bad in description.lower() for bad in ['def ', 'return', 'self']):
        description = "No description"
    
    # Limit lengths
    if len(category) > 50:
        category = "Uncategorized"
    if len(description) > 300:
        description = description[:300] + "..."
    
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
        # Import required modules
        import os
        import sys
        import importlib
        import importlib.util
        import subprocess
        import shlex
        import shutil
        import tempfile
        from pathlib import Path
        from datetime import datetime
        
        # Check if sudo password is provided
        if use_sudo and not sudo_password:
            return False, "Sudo password is required for module installation"
            
        # Check if expect is installed (needed for interactive sudo)
        has_expect = shutil.which('expect') is not None
            
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
        
        # Create a temporary directory for scripts
        temp_dir = tempfile.mkdtemp(prefix="module_install_")
        
        try:
            # Create a unified installation script that handles sudo once
            script_path = os.path.join(temp_dir, "install_script.sh")
            
            with open(script_path, "w") as f:
                f.write("#!/bin/bash\n")
                f.write("set -e\n\n")  # Exit on error
                
                if use_sudo:
                    # Add sudo authentication at the beginning
                    f.write(f"# Authenticate sudo once up front\n")
                    escaped_password = sudo_password.replace("'", "'\\''")  # Escape single quotes properly
                    f.write(f"echo '{escaped_password}' | sudo -S echo \"Starting installation...\"\n")
                    f.write(f"if [ $? -ne 0 ]; then\n")
                    f.write(f"    echo \"Sudo authentication failed. Exiting.\"\n")
                    f.write(f"    exit 1\n")
                    f.write(f"fi\n\n")
                
                # Add all commands
                f.write("# Installation commands\n")
                for i, cmd in enumerate(commands):
                    if use_sudo and not cmd.startswith("sudo "):
                        cmd = f"sudo {cmd}"
                    f.write(f"echo \"Running command {i+1}/{len(commands)}: {cmd}\"\n")
                    f.write(f"{cmd}\n")
                    f.write(f"if [ $? -ne 0 ]; then\n")
                    f.write(f"    echo \"Command failed: {cmd}\"\n")
                    f.write(f"    exit 1\n")
                    f.write(f"fi\n\n")
                
                f.write("echo \"Installation completed successfully\"\n")
            
            # Make script executable
            os.chmod(script_path, 0o755)
            
            # Execute the script
            current_app.logger.info(f"Executing installation script: {script_path}")
            
            result = subprocess.run(
                script_path,
                shell=True,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Process results
            all_output = []
            all_output.append(f"Script exit code: {result.returncode}")
            all_output.append(f"Output:\n{result.stdout}")
            
            if result.returncode != 0:
                all_output.append(f"Error:\n{result.stderr}")
                
                # Check for sudo authentication failures
                if any(phrase in result.stderr.lower() for phrase in [
                    "incorrect password",
                    "sorry, try again",
                    "sudo authentication failed",
                    "authentication failure"
                ]):
                    return False, "Sudo password authentication failed. Please try again with the correct password."
                
                return False, "\n".join(all_output)
            
            # Update module status
            module.installed = True
            module.installed_date = datetime.utcnow()
            db.session.commit()
            
            all_output.append(f"Module {module_name} installed successfully")
            current_app.logger.info(f"Module {module_name} installed successfully")
            
            return True, "\n".join(all_output)
        
        finally:
            # Clean up temporary directory
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                current_app.logger.warning(f"Failed to clean up temporary directory: {e}")
        
    except Exception as e:
        current_app.logger.error(f"Error installing module: {e}")
        current_app.logger.error(traceback.format_exc())
        return False, f"Error installing module: {str(e)}"

def uninstall_module(module, sudo_password=None):
    """
    Uninstall a module
    
    Args:
        module: Module object
        sudo_password: Sudo password for system-level operations
        
    Returns:
        tuple: (success, message)
    """
    try:
        # Import required modules
        import os
        import sys
        import importlib
        import importlib.util
        import subprocess
        import shlex
        import shutil
        import tempfile
        from pathlib import Path
        from datetime import datetime
        
        # Check if sudo password is provided
        if not sudo_password:
            return False, "Sudo password is required for module uninstallation"
        
        # Load module
        file_path = Path(module.local_path)
        module_name = file_path.stem
        
        current_app.logger.info(f"Uninstalling module: {module_name} from {file_path}")
        
        if not file_path.exists():
            # If file doesn't exist, just mark as uninstalled in database
            module.installed = False
            db.session.commit()
            return True, "Module file not found, marked as uninstalled"
        
        # Add modules directory to Python path
        modules_dir = current_app.config['MODULES_DIR']
        project_dir = str(Path(modules_dir).parent)
        
        # Make sure needed directories are in sys.path
        if project_dir not in sys.path:
            sys.path.insert(0, project_dir)
        
        if modules_dir not in sys.path:
            sys.path.insert(0, modules_dir)
        
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
                    # If we can't import, just mark as uninstalled
                    module.installed = False
                    db.session.commit()
                    return True, "Failed to create module spec, marked as uninstalled"
                    
                mod = importlib.util.module_from_spec(spec)
                sys.modules[import_path] = mod
                spec.loader.exec_module(mod)
                current_app.logger.info(f"Imported module using spec_from_file_location")
                
        except ImportError as e:
            # Check if it's the core module that's missing
            if "No module named 'core'" in str(e):
                current_app.logger.error(f"Core module not found during uninstall: {e}")
                # If we can't import due to missing core, just mark as uninstalled
                module.installed = False
                db.session.commit()
                return True, "Module depends on missing 'core' module, marked as uninstalled"
            else:
                current_app.logger.error(f"Import error during uninstall: {e}")
                # If we can't import, just mark as uninstalled
                module.installed = False
                db.session.commit()
                return True, f"Error importing module: {str(e)}, marked as uninstalled"
        except Exception as e:
            current_app.logger.error(f"Error executing module during uninstall: {e}")
            # If we can't execute the module, just mark as uninstalled
            module.installed = False
            db.session.commit()
            return True, f"Error loading module: {str(e)}, marked as uninstalled"
        
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
                    if not hasattr(instance, '_get_uninstall_command'):
                        setattr(instance.__class__, '_get_uninstall_command', lambda self, pkg_manager: [])
                    
                    module_class = instance
                    current_app.logger.info(f"Using class with added methods: {class_name}")
                    break
                except Exception as e:
                    current_app.logger.error(f"Error using class {attr_name}: {e}")
        
        if not module_class:
            # If we can't find the class, just mark as uninstalled
            module.installed = False
            db.session.commit()
            return True, "Module class not found, marked as uninstalled"
        
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
        
        # Get uninstallation command
        if not hasattr(module_class, '_get_uninstall_command'):
            # If the module doesn't have an uninstall command, just mark as uninstalled
            module.installed = False
            db.session.commit()
            return True, f"Module {module_name} uninstalled successfully (no uninstallation needed)"
        
        # Get uninstallation commands
        try:
            commands = module_class._get_uninstall_command(pkg_manager)
            
            # If commands is None, handle it gracefully
            if commands is None:
                commands = []
        except Exception as e:
            current_app.logger.error(f"Error getting uninstall commands: {e}")
            return False, f"Error getting uninstallation commands: {str(e)}"
        
        if not commands:
            # If there are no commands, just mark as uninstalled
            module.installed = False
            db.session.commit()
            return True, f"Module {module_name} uninstalled successfully (no commands needed)"
        
        # Convert single command to list
        if isinstance(commands, str):
            commands = [commands]
        
        current_app.logger.info(f"Uninstallation commands: {commands}")
        
        # Create a temporary directory for scripts
        temp_dir = tempfile.mkdtemp(prefix="module_uninstall_")
        
        try:
            # Create a unified uninstallation script that handles sudo once
            script_path = os.path.join(temp_dir, "uninstall_script.sh")
            
            with open(script_path, "w") as f:
                f.write("#!/bin/bash\n")
                f.write("set -e\n\n")  # Exit on error
                
                # Add sudo authentication at the beginning
                f.write(f"# Authenticate sudo once up front\n")
                escaped_password = sudo_password.replace("'", "'\\''")  # Escape single quotes properly
                f.write(f"echo '{escaped_password}' | sudo -S echo \"Starting uninstallation...\"\n")
                f.write(f"if [ $? -ne 0 ]; then\n")
                f.write(f"    echo \"Sudo authentication failed. Exiting.\"\n")
                f.write(f"    exit 1\n")
                f.write(f"fi\n\n")
                
                # Add all commands
                f.write("# Uninstallation commands\n")
                for i, cmd in enumerate(commands):
                    if not cmd.startswith("sudo "):
                        cmd = f"sudo {cmd}"
                    f.write(f"echo \"Running command {i+1}/{len(commands)}: {cmd}\"\n")
                    f.write(f"{cmd}\n")
                    f.write(f"if [ $? -ne 0 ]; then\n")
                    f.write(f"    echo \"Command failed: {cmd}\"\n")
                    f.write(f"    exit 1\n")
                    f.write(f"fi\n\n")
                
                f.write("echo \"Uninstallation completed successfully\"\n")
            
            # Make script executable
            os.chmod(script_path, 0o755)
            
            # Execute the script
            current_app.logger.info(f"Executing uninstallation script: {script_path}")
            
            result = subprocess.run(
                script_path,
                shell=True,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Process results
            all_output = []
            all_output.append(f"Script exit code: {result.returncode}")
            all_output.append(f"Output:\n{result.stdout}")
            
            if result.returncode != 0:
                all_output.append(f"Error:\n{result.stderr}")
                
                # Check for sudo authentication failures
                if any(phrase in result.stderr.lower() for phrase in [
                    "incorrect password",
                    "sorry, try again",
                    "sudo authentication failed",
                    "authentication failure"
                ]):
                    return False, "Sudo password authentication failed. Please try again with the correct password."
                
                return False, "\n".join(all_output)
            
            # Update module status
            module.installed = False
            db.session.commit()
            
            all_output.append(f"Module {module_name} uninstalled successfully")
            current_app.logger.info(f"Module {module_name} uninstalled successfully")
            
            return True, "\n".join(all_output)
        
        finally:
            # Clean up temporary directory
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                current_app.logger.warning(f"Failed to clean up temporary directory: {e}")
        
    except Exception as e:
        current_app.logger.error(f"Error uninstalling module: {e}")
        current_app.logger.error(traceback.format_exc())
        return False, f"Error uninstalling module: {str(e)}"

def delete_module(module):
    """
    Delete a module file and its database entry
    
    Args:
        module: Module object
        
    Returns:
        tuple: (success, message)
    """
    try:
        # Safety check - prevent deletion of system modules
        if module.name in ['base', 'colors'] or 'core' in str(module.local_path):
            return False, "Cannot delete system module."

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
