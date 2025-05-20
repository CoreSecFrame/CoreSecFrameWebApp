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
    # Get all modules
    modules = Module.query.all()
    categories = ModuleCategory.query.all()
    
    # Count installed modules
    installed_modules = Module.query.filter_by(installed=True).count()
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
    # Get modules in category
    category = ModuleCategory.query.filter_by(name=name).first_or_404()
    modules = Module.query.filter_by(category=name).all()
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
        # First clean up the database
        from app.modules.utils import clean_module_database, scan_local_modules
        removed = clean_module_database()
        if removed > 0:
            flash(f'Cleaned up database: {removed} duplicate modules removed', 'info')
        
        # Then scan for modules
        added, updated = scan_local_modules()
        flash(f'Scan completed: {added} modules added, {updated} modules updated', 'success')
    except Exception as e:
        current_app.logger.error(f"Error scanning modules: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        flash(f'Error scanning modules: {str(e)}', 'danger')
    
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
        
        # Install the module
        from app.modules.utils import install_module
        success, message = install_module(module)
        
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
        
        # Uninstall the module
        from app.modules.utils import uninstall_module
        success, message = uninstall_module(module)
        
        if success:
            flash(f'Module {module.name} uninstalled successfully', 'success')
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
    query = request.args.get('q', '')
    
    if not query:
        return redirect(url_for('modules.index'))
    
    # Search modules
    modules = Module.query

