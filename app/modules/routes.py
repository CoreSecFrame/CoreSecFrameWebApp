# app/modules/routes.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.modules.models import Module, ModuleCategory
from app.modules.utils import scan_local_modules, fetch_remote_modules, download_module, install_module, uninstall_module
import os
import traceback

modules_bp = Blueprint('modules', __name__, url_prefix='/modules')

@modules_bp.route('/')
@login_required
def index():
    # Protected module names and paths that should be filtered out
    protected_modules = ['base', 'colors']
    protected_paths = ['core']
    
    # Get all modules, filtering out protected ones
    modules = Module.query.filter(~Module.name.in_(protected_modules)).all()
    
    # Further filter out core modules by checking their paths
    modules = [m for m in modules if not any(p in m.local_path for p in protected_paths)]
    
    categories = ModuleCategory.query.all()
    
    # Count installed modules
    installed_modules = sum(1 for m in modules if m.installed)
    total_modules = len(modules)
    
    return render_template(
        'modules/index.html', 
        title='Modules',
        modules=modules, 
        categories=categories,
        installed_modules=installed_modules,
        total_modules=total_modules
    )

@modules_bp.route('/category/<name>')
@login_required
def category(name):
    # Protected module names and paths that should be filtered out
    protected_modules = ['base', 'colors']
    protected_paths = ['core']
    
    # Get category
    category = ModuleCategory.query.filter_by(name=name).first_or_404()
    
    # Get modules in category, filtering out protected ones
    modules = Module.query.filter(
        Module.category == name,
        ~Module.name.in_(protected_modules)
    ).all()
    
    # Further filter out core modules by checking their paths
    modules = [m for m in modules if not any(p in m.local_path for p in protected_paths)]
    
    categories = ModuleCategory.query.all()
    
    # Count installed modules
    installed_modules = Module.query.filter_by(installed=True).count()
    total_modules = Module.query.count()
    
    return render_template(
        'modules/index.html', 
        title=f'Category: {name}',
        modules=modules, 
        categories=categories,
        installed_modules=installed_modules,
        total_modules=total_modules,
        current_category=category
    )

@modules_bp.route('/view/<int:id>')
@login_required
def view(id):
    module = Module.query.get_or_404(id)
    
    # Check if this is a protected module
    if module.name in ['base', 'colors'] or 'core' in module.local_path:
        flash('This system module cannot be modified or viewed directly.', 'danger')
        return redirect(url_for('modules.index'))
        
    return render_template('modules/view.html', title=f'Module: {module.name}', module=module)

@modules_bp.route('/shop')
@login_required
def shop():
    try:
        # Get remote modules
        remote_modules = fetch_remote_modules()
        
        # Get all existing modules
        existing_modules = {module.name: module for module in Module.query.all()}
        
        # Mark downloaded modules
        for remote_module in remote_modules:
            remote_module['downloaded'] = remote_module['name'] in existing_modules
        
        # Get unique categories
        categories = sorted(list(set(module['category'] for module in remote_modules)))
        
        return render_template(
            'modules/shop.html', 
            title='Module Shop',
            modules=remote_modules,
            categories=categories
        )
    except Exception as e:
        current_app.logger.error(f"Error fetching remote modules: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        flash(f'Error fetching remote modules: {str(e)}', 'danger')
        return redirect(url_for('modules.index'))


@modules_bp.route('/scan')
@login_required
def scan():
    try:
        # First run enhanced cleanup to remove duplicates and orphaned entries
        from app.modules.utils import clean_module_database, scan_local_modules
        
        current_app.logger.info("Starting module scan with enhanced cleanup...")
        
        # Clean up database first
        removed = clean_module_database()
        cleanup_message = ""
        if removed > 0:
            cleanup_message = f"Database cleanup: {removed} duplicate/orphaned modules removed. "
            current_app.logger.info(f"Cleanup removed {removed} modules")
        
        # Then scan for modules with the new deduplication logic
        added, updated = scan_local_modules()
        
        scan_message = f"Scan completed: {added} modules added, {updated} modules updated"
        full_message = cleanup_message + scan_message
        
        current_app.logger.info(f"Module scan completed: cleanup removed {removed}, added {added}, updated {updated}")
        flash(full_message, 'success')
        
    except Exception as e:
        current_app.logger.error(f"Error during module scan: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        flash(f'Error during module scan: {str(e)}', 'danger')
    
    return redirect(url_for('modules.index'))

@modules_bp.route('/sync')
@login_required
def sync():
    try:
        # Fetch remote modules
        remote_modules = fetch_remote_modules()
        
        # Get existing modules
        existing_modules = {module.name: module for module in Module.query.all()}
        
        added = 0
        updated = 0
        
        # Process remote modules
        for remote_module in remote_modules:
            name = remote_module['name']
            
            if name in existing_modules:
                # Module exists, update metadata
                module = existing_modules[name]
                module.description = remote_module['description']
                module.category = remote_module['category']
                module.remote_url = remote_module['url']
                db.session.add(module)
                updated += 1
            else:
                # New module, create record
                module = Module(
                    name=name,
                    description=remote_module['description'],
                    category=remote_module['category'],
                    remote_url=remote_module['url'],
                    installed=False
                )
                db.session.add(module)
                added += 1
            
            # Ensure category exists
            category = ModuleCategory.query.filter_by(name=remote_module['category']).first()
            if not category:
                category = ModuleCategory(name=remote_module['category'])
                db.session.add(category)
        
        # Commit changes
        db.session.commit()
        
        flash(f'Sync completed: {added} modules added, {updated} modules updated', 'success')
        
    except Exception as e:
        current_app.logger.error(f"Error syncing modules: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        flash(f'Error syncing modules: {str(e)}', 'danger')
    
    return redirect(url_for('modules.shop'))

@modules_bp.route('/cleanup')
@login_required
def cleanup():
    """Manual database cleanup route"""
    try:
        from app.modules.utils import clean_module_database
        
        current_app.logger.info("Starting manual module database cleanup...")
        removed = clean_module_database()
        
        if removed > 0:
            flash(f'Database cleanup completed: {removed} duplicate/orphaned modules removed', 'success')
            current_app.logger.info(f"Manual cleanup removed {removed} modules")
        else:
            flash('Database cleanup completed: no duplicates or orphaned entries found', 'info')
            current_app.logger.info("Manual cleanup found no issues")
            
    except Exception as e:
        current_app.logger.error(f"Error during manual cleanup: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        flash(f'Error during database cleanup: {str(e)}', 'danger')
    
    return redirect(url_for('modules.index'))

@modules_bp.route('/download', methods=['POST'])
@login_required
def download():
    try:
        module_name = request.form.get('module_name')
        module_url = request.form.get('module_url')
        module_category = request.form.get('module_category')
        module_description = request.form.get('module_description')
        
        if not all([module_name, module_url, module_category]):
            flash('Invalid module data', 'danger')
            return redirect(url_for('modules.shop'))
        
        # Download the module
        success, local_path, message = download_module(module_url, module_name, module_category)
        
        if success:
            # Create or update module record
            module = Module.query.filter_by(name=module_name).first()
            
            if module:
                # Update existing module
                module.description = module_description
                module.category = module_category
                module.remote_url = module_url
                module.local_path = local_path
            else:
                # Create new module
                module = Module(
                    name=module_name,
                    description=module_description,
                    category=module_category,
                    command=module_name.lower(),
                    remote_url=module_url,
                    local_path=local_path,
                    installed=False
                )
            
            db.session.add(module)
            
            # Ensure category exists
            category = ModuleCategory.query.filter_by(name=module_category).first()
            if not category:
                category = ModuleCategory(name=module_category)
                db.session.add(category)
                
            db.session.commit()
            
            flash(f'Module {module_name} downloaded successfully', 'success')
        else:
            flash(f'Failed to download module: {message}', 'danger')
        
        return redirect(url_for('modules.shop'))
        
    except Exception as e:
        current_app.logger.error(f"Error downloading module: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        flash(f'Error downloading module: {str(e)}', 'danger')
        return redirect(url_for('modules.shop'))

@modules_bp.route('/install/<int:id>', methods=['POST'])
@login_required
def install(id):
    try:
        module = Module.query.get_or_404(id)
        
        # Protect system modules
        if module.name in ['base', 'colors'] or 'core' in module.local_path:
            flash('System modules cannot be modified.', 'danger')
            return redirect(url_for('modules.index'))
        
        # Always use sudo for module installation - ignore the checkbox
        use_sudo = True
        sudo_password = request.form.get('sudo_password', '')
        
        # Validate that sudo password is provided (it's now required)
        if not sudo_password:
            flash('Sudo password is required for module installation.', 'danger')
            return redirect(url_for('modules.view', id=id))
        
        # Install the module
        success, message = install_module(module, use_sudo, sudo_password)
        
        if success:
            flash(f'Module {module.name} installed successfully', 'success')
        else:
            flash(f'Failed to install module: {message}', 'danger')
        
        return redirect(url_for('modules.view', id=id))
        
    except Exception as e:
        current_app.logger.error(f"Error installing module: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        flash(f'Error installing module: {str(e)}', 'danger')
        return redirect(url_for('modules.view', id=id))

@modules_bp.route('/uninstall/<int:id>', methods=['POST'])
@login_required
def uninstall(id):
    try:
        module = Module.query.get_or_404(id)
        
        # Protect system modules
        if module.name in ['base', 'colors'] or 'core' in module.local_path:
            flash('System modules cannot be modified.', 'danger')
            return redirect(url_for('modules.view', id=id))
        
        # Get sudo password from form
        sudo_password = request.form.get('sudo_password', '')
        
        # Validate that sudo password is provided
        if not sudo_password:
            flash('Sudo password is required for module uninstallation.', 'danger')
            return redirect(url_for('modules.view', id=id))
        
        # Uninstall the module with sudo password
        success, message = uninstall_module(module, sudo_password)
        
        if success:
            flash(f'Module {module.name} uninstalled successfully', 'success')
        else:
            # Check for sudo authentication failures
            if any(phrase in message.lower() for phrase in [
                "incorrect password",
                "sorry, try again", 
                "sudo authentication failed",
                "authentication failure"
            ]):
                flash('Sudo password authentication failed. Please try again with the correct password.', 'danger')
            else:
                flash(f'Failed to uninstall module: {message}', 'danger')
        
        return redirect(url_for('modules.view', id=id))
        
    except Exception as e:
        current_app.logger.error(f"Error uninstalling module: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        flash(f'Error uninstalling module: {str(e)}', 'danger')
        return redirect(url_for('modules.view', id=id))

@modules_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete(id):
    try:
        module = Module.query.get_or_404(id)
        module_name = module.name
        
        # Get the file path for logging
        file_path = module.local_path
        current_app.logger.info(f"Attempting to delete module: {module_name} at {file_path}")
        
        # Delete the module
        from app.modules.utils import delete_module
        success, message = delete_module(module)
        
        if success:
            flash(f'Module {module_name} deleted successfully', 'success')
        else:
            flash(f'Failed to delete module: {message}', 'danger')
        
        return redirect(url_for('modules.index'))
        
    except Exception as e:
        current_app.logger.error(f"Error deleting module: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        flash(f'Error deleting module: {str(e)}', 'danger')
        return redirect(url_for('modules.index'))

@modules_bp.route('/search')
@login_required
def search():
    """Search modules by name, description or category"""
    query = request.args.get('q', '')
    
    if not query:
        return redirect(url_for('modules.index'))
    
    # Protected module names and paths that should be filtered out
    protected_modules = ['base', 'colors']
    protected_paths = ['core']
    
    # Search modules, filtering out protected ones
    modules = Module.query.filter(
        db.or_(
            Module.name.ilike(f'%{query}%'),
            Module.description.ilike(f'%{query}%'),
            Module.category.ilike(f'%{query}%')
        ),
        ~Module.name.in_(protected_modules)
    ).all()
    
    # Further filter out core modules by checking their paths
    modules = [m for m in modules if not any(p in m.local_path for p in protected_paths)]
    
    # Get categories for sidebar
    categories = ModuleCategory.query.all()
    
    # Get count information
    total_modules = Module.query.count()
    installed_modules = Module.query.filter_by(installed=True).count()
    
    return render_template(
        'modules/index.html', 
        title=f'Search Results: {query}',
        modules=modules, 
        categories=categories,
        installed_modules=installed_modules,
        total_modules=total_modules,
        search_query=query
    )


@modules_bp.route('/api/list')
@login_required
def api_list():
    """API endpoint to list available modules"""
    modules = Module.query.all()
    
    # Format modules for API response
    module_list = []
    for module in modules:
        module_list.append({
            'id': module.id,
            'name': module.name,
            'description': module.description,
            'category': module.category,
            'installed': module.installed,
            'command': module.command,
            'local_path': module.local_path,
            'remote_url': module.remote_url
        })
    
    return jsonify({
        'success': True,
        'count': len(module_list),
        'modules': module_list
    })

@modules_bp.route('/api/info/<name>')
@login_required
def api_info(name):
    """API endpoint to get detailed module information"""
    module = Module.query.filter_by(name=name).first()
    
    if not module:
        return jsonify({
            'success': False,
            'message': f'Module "{name}" not found'
        }), 404
    
    # Try to get module help information
    help_info = {}
    try:
        # Import the module
        module_path = Path(module.local_path)
        if "modules" in str(module_path):
            if module_path.parent.name == "modules":
                import_path = f"modules.{module.name}"
            else:
                category = module_path.parent.name
                import_path = f"modules.{category}.{module.name}"
        else:
            import_path = module.name
        
        # Add modules directory to Python path
        modules_dir = current_app.config['MODULES_DIR']
        project_dir = str(Path(modules_dir).parent)
        
        if project_dir not in sys.path:
            sys.path.insert(0, project_dir)
        
        if modules_dir not in sys.path:
            sys.path.insert(0, modules_dir)
        
        # Try to import the module
        try:
            imported_module = importlib.import_module(import_path)
        except ImportError:
            spec = importlib.util.spec_from_file_location(import_path, str(module_path))
            if spec:
                imported_module = importlib.util.module_from_spec(spec)
                sys.modules[import_path] = imported_module
                spec.loader.exec_module(imported_module)
            else:
                raise ImportError(f"Could not create spec for module: {module_path}")
        
        # Find the module class
        module_class = None
        for attr_name in dir(imported_module):
            if attr_name.startswith('__'):
                continue
            
            attr = getattr(imported_module, attr_name)
            if not isinstance(attr, type):
                continue
            
            try:
                instance = attr()
                if hasattr(instance, 'get_help'):
                    help_info = instance.get_help()
                    break
                if hasattr(instance, 'run_guided') and hasattr(instance, 'run_direct'):
                    module_class = instance
            except Exception as e:
                continue
        
        # If we found a module class but no help_info, try to get some basic info
        if module_class and not help_info:
            help_info = {
                'title': module.name,
                'usage': f"Use {module.name} via CoreSecFrame",
                'desc': module.description,
                'modes': {
                    'Guided': 'Interactive guided mode',
                    'Direct': 'Direct command execution mode'
                }
            }
    except Exception as e:
        current_app.logger.error(f"Error getting module help info: {e}")
        current_app.logger.error(traceback.format_exc())
    
    # Return module info
    return jsonify({
        'success': True,
        'module': {
            'id': module.id,
            'name': module.name,
            'description': module.description,
            'category': module.category,
            'installed': module.installed,
            'command': module.command,
            'local_path': module.local_path,
            'remote_url': module.remote_url,
            'help': help_info
        }
    })

@modules_bp.route('/run/<name>')
@login_required
def run(name):
    """Launch a module in the terminal"""
    module = Module.query.filter_by(name=name).first_or_404()
    
    mode = request.args.get('mode', 'guided')
    
    # Redirect to the terminal creation page with module parameters
    return redirect(url_for('terminal.new', module=name, mode=mode))