# app/modules/routes.py - Simple fix for the original error
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.modules.models import Module, ModuleCategory, ModuleShopCache
from app.modules.utils import scan_local_modules, fetch_remote_modules, download_module, install_module, uninstall_module, delete_module, clean_module_database
import os
import traceback
import json
from datetime import datetime, timedelta

modules_bp = Blueprint('modules', __name__, url_prefix='/modules')

@modules_bp.route('/')
@login_required
def index():
    # Protected module names and paths that should be filtered out
    protected_modules = ['base', 'colors']
    protected_paths = ['core']
    
    # Get all modules, filtering out protected ones
    modules = Module.query.filter(~Module.name.in_(protected_modules)).all()
    
    # FIXED: Further filter out core modules by checking their paths safely
    filtered_modules = []
    for m in modules:
        try:
            # Check if local_path exists and is not None before checking if it contains protected paths
            if m.local_path is not None and not any(p in m.local_path for p in protected_paths):
                filtered_modules.append(m)
            elif m.local_path is None:
                # Log the module with null path but don't crash
                current_app.logger.warning(f"Module {m.name} has null local_path")
        except Exception as e:
            current_app.logger.error(f"Error checking module {m.name}: {e}")
            continue
    
    modules = filtered_modules
    
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
    category_obj = ModuleCategory.query.filter_by(name=name).first_or_404()
    
    # Get modules in category, filtering out protected ones
    modules = Module.query.filter(
        Module.category == name,
        ~Module.name.in_(protected_modules)
    ).all()
    
    # FIXED: Further filter out core modules by checking their paths safely
    filtered_modules = []
    for m in modules:
        try:
            # Check if local_path exists and is not None before checking if it contains protected paths
            if m.local_path is not None and not any(p in m.local_path for p in protected_paths):
                filtered_modules.append(m)
            elif m.local_path is None:
                # Log the module with null path but don't crash
                current_app.logger.warning(f"Module {m.name} has null local_path")
        except Exception as e:
            current_app.logger.error(f"Error checking module {m.name}: {e}")
            continue
    
    modules = filtered_modules
    
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
        current_category=category_obj
    )

@modules_bp.route('/view/<int:id>')
@login_required
def view(id):
    module = Module.query.get_or_404(id)
    
    # Check if this is a protected module
    if module.name in ['base', 'colors'] or (module.local_path and 'core' in module.local_path):
        flash('This system module cannot be modified or viewed directly.', 'danger')
        return redirect(url_for('modules.index'))
        
    return render_template('modules/view.html', title=f'Module: {module.name}', module=module)

@modules_bp.route('/shop')
@login_required
def shop():
    try:
        remote_modules = None
        cache_hit = False

        # Query for the latest cache entry
        cache_entry = ModuleShopCache.query.order_by(ModuleShopCache.last_updated.desc()).first()

        if cache_entry and cache_entry.last_updated > (datetime.utcnow() - timedelta(hours=12)):
            try:
                remote_modules = json.loads(cache_entry.data)
                cache_hit = True
                current_app.logger.info("Module shop data loaded from cache.")
            except json.JSONDecodeError as e:
                current_app.logger.error(f"Error decoding JSON from cache: {str(e)}")
                # Cache is invalid, proceed to fetch fresh data
        
        if not remote_modules:
            if cache_hit: # If decoding failed after a cache hit signal
                current_app.logger.info("Cache was hit, but data was invalid. Fetching fresh modules.")
            else:
                current_app.logger.info("No valid cache or cache is stale. Fetching fresh modules.")

            fresh_modules_data = fetch_remote_modules()
            if not isinstance(fresh_modules_data, list): # Ensure fetch_remote_modules returns a list
                current_app.logger.error(f"fetch_remote_modules did not return a list. Got: {type(fresh_modules_data)}")
                flash('Error fetching module list from source. Please try again later.', 'danger')
                return redirect(url_for('modules.index'))

            remote_modules = fresh_modules_data
            
            try:
                new_cache_entry = ModuleShopCache(
                    data=json.dumps(remote_modules),
                    last_updated=datetime.utcnow()
                )
                db.session.add(new_cache_entry)
                
                # Keep only the latest cache entry, remove older ones
                all_cache_entries = ModuleShopCache.query.order_by(ModuleShopCache.last_updated.desc()).all()
                if len(all_cache_entries) > 1:
                    for old_entry in all_cache_entries[1:]:
                        db.session.delete(old_entry)
                
                db.session.commit()
                current_app.logger.info("Module shop data fetched and new cache entry created.")
            except Exception as db_e:
                current_app.logger.error(f"Error saving module shop cache: {str(db_e)}")
                current_app.logger.error(traceback.format_exc())
                # Non-fatal, proceed with fresh data even if caching fails

        # Get all existing modules from the main Module table to check downloaded status
        existing_modules_db = {module.name: module for module in Module.query.all()}
        
        # Mark downloaded modules and prepare categories
        # This needs to be done whether modules are from cache or fresh
        if remote_modules:
            for remote_module in remote_modules:
                # Ensure 'name' key exists, providing a default or skipping if critical
                if 'name' not in remote_module:
                    current_app.logger.warning(f"Module data missing 'name' field: {remote_module}")
                    continue # Or assign a default name if appropriate

                # Check if module exists in database AND file actually exists
                module_name = remote_module['name']
                is_downloaded = False
                
                if module_name in existing_modules_db:
                    module_obj = existing_modules_db[module_name]
                    # Only mark as downloaded if the file actually exists
                    if module_obj.local_path and os.path.exists(module_obj.local_path):
                        is_downloaded = True
                    elif module_obj.local_path and not os.path.exists(module_obj.local_path):
                        # File is missing - reset the module state in background
                        current_app.logger.warning(f"Module {module_name} marked as downloaded but file missing: {module_obj.local_path}")
                
                remote_module['downloaded'] = is_downloaded
            
            # Get unique categories from the final list of modules
            categories = sorted(list(set(module['category'] for module in remote_modules if 'category' in module)))
        else:
            # Handle case where remote_modules is still None (e.g. fetch_remote_modules failed and didn't raise)
            flash('Could not retrieve module list. Please try again.', 'warning')
            remote_modules = [] # Ensure modules is an iterable for the template
            categories = []

        return render_template(
            'modules/shop.html', 
            title='Module Shop',
            modules=remote_modules,
            categories=categories
        )
    except Exception as e:
        current_app.logger.error(f"Error in module shop route: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        flash(f'An unexpected error occurred: {str(e)}', 'danger')
        return redirect(url_for('modules.index'))

@modules_bp.route('/shop/refresh')
@login_required
def refresh_shop():
    try:
        current_app.logger.info("Attempting to refresh module shop data...")
        fresh_modules_data = fetch_remote_modules()

        if not fresh_modules_data or not isinstance(fresh_modules_data, list):
            current_app.logger.error(f"fetch_remote_modules returned invalid data or failed. Type: {type(fresh_modules_data)}")
            flash('Error fetching fresh module list from source. Please try again later.', 'danger')
            return redirect(url_for('modules.shop'))

        current_app.logger.info(f"Successfully fetched {len(fresh_modules_data)} modules from remote.")

        # Create or update cache
        cache_entry = ModuleShopCache.query.order_by(ModuleShopCache.last_updated.desc()).first()
        if cache_entry:
            cache_entry.data = json.dumps(fresh_modules_data)
            cache_entry.last_updated = datetime.utcnow()
            current_app.logger.info(f"Updating existing cache entry (ID: {cache_entry.id}).")
        else:
            cache_entry = ModuleShopCache(
                data=json.dumps(fresh_modules_data),
                last_updated=datetime.utcnow()
            )
            db.session.add(cache_entry)
            current_app.logger.info("Creating new cache entry.")
        
        db.session.commit()
        current_app.logger.info("Module shop cache updated successfully.")

        # Clean up older cache entries, keeping only the newest one
        all_cache_entries = ModuleShopCache.query.order_by(ModuleShopCache.last_updated.desc()).all()
        if len(all_cache_entries) > 1:
            current_app.logger.info(f"Found {len(all_cache_entries)} cache entries. Cleaning up older ones.")
            for old_entry in all_cache_entries[1:]:
                current_app.logger.info(f"Deleting old cache entry ID: {old_entry.id}, Last Updated: {old_entry.last_updated}")
                db.session.delete(old_entry)
            db.session.commit()
            current_app.logger.info("Old cache entries cleaned up.")

        flash('Module list has been successfully refreshed from the source.', 'success')

    except Exception as e:
        current_app.logger.error(f"Error refreshing module shop: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        flash(f'An error occurred while refreshing the module list: {str(e)}', 'danger')
    
    return redirect(url_for('modules.shop'))

@modules_bp.route('/scan')
@login_required
def scan():
    try:
        # First run enhanced cleanup to remove duplicates and orphaned entries
        current_app.logger.info("Starting module scan with enhanced cleanup...")
        
        # Clean up database first
        removed = clean_module_database()
        cleanup_message = ""
        if removed > 0:
            cleanup_message = f"Database cleanup: {removed} duplicate/orphaned modules removed. "
            current_app.logger.info(f"Manual cleanup removed {removed} modules")
        else:
            flash('Database cleanup completed: no duplicates or orphaned entries found', 'info')
            current_app.logger.info("Manual cleanup found no issues")
        
        # Now scan for new modules
        scanned = scan_local_modules()
        scan_message = f"Scan completed: {scanned} new modules found."
        
        combined_message = cleanup_message + scan_message
        flash(combined_message, 'success')
        current_app.logger.info(f"Module scan completed: {scanned} new modules, {removed} cleaned up")
        
    except Exception as e:
        current_app.logger.error(f"Error during module scan: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        flash(f'Error during module scan: {str(e)}', 'danger')
    
    return redirect(url_for('modules.index'))

# Add alias for sync -> scan (in case templates use sync)
@modules_bp.route('/sync')
@login_required
def sync():
    """Synchronize with remote repository - download all available modules"""
    try:
        current_app.logger.info("Starting module synchronization...")
        
        # First, clean up orphaned database entries (modules marked as downloaded but files don't exist)
        cleaned_count = cleanup_orphaned_modules()
        
        # Get remote modules
        remote_modules = fetch_remote_modules()
        if not isinstance(remote_modules, list):
            flash('Error fetching module list from remote repository.', 'danger')
            return redirect(url_for('modules.shop'))
        
        # Get existing modules from database
        existing_modules = {module.name: module for module in Module.query.all()}
        
        downloaded_count = 0
        error_count = 0
        
        for remote_module in remote_modules:
            try:
                if 'name' not in remote_module or 'url' not in remote_module:
                    continue
                    
                module_name = remote_module['name']
                module_url = remote_module['url']
                module_category = remote_module.get('category', 'misc')
                module_description = remote_module.get('description', '')
                
                # Check if module exists in database and if file actually exists
                should_download = True
                if module_name in existing_modules:
                    module_obj = existing_modules[module_name]
                    if module_obj.local_path and os.path.exists(module_obj.local_path):
                        should_download = False  # Skip if file actually exists
                
                if should_download:
                    # Download the module
                    success, local_path, message = download_module(module_url, module_name, module_category)
                    
                    if success:
                        # Create or update module record
                        if module_name in existing_modules:
                            module = existing_modules[module_name]
                            module.local_path = local_path
                            module.description = module_description
                            module.category = module_category
                            module.remote_url = module_url
                        else:
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
                        
                        downloaded_count += 1
                        current_app.logger.info(f"Downloaded module: {module_name}")
                    else:
                        error_count += 1
                        current_app.logger.error(f"Failed to download {module_name}: {message}")
                        
            except Exception as e:
                error_count += 1
                current_app.logger.error(f"Error processing module {remote_module.get('name', 'unknown')}: {e}")
                continue
        
        # Commit all changes
        try:
            db.session.commit()
        except Exception as db_error:
            db.session.rollback()
            current_app.logger.error(f"Database error during sync: {db_error}")
            flash('Database error occurred during synchronization.', 'danger')
            return redirect(url_for('modules.shop'))
        
        # Show results
        if cleaned_count > 0:
            flash(f'Cleaned {cleaned_count} orphaned module records.', 'info')
        
        if downloaded_count > 0:
            flash(f'Successfully synchronized {downloaded_count} modules.', 'success')
        elif error_count == 0:
            flash('All modules are already up to date.', 'info')
        
        if error_count > 0:
            flash(f'{error_count} modules failed to download. Check logs for details.', 'warning')
        
        current_app.logger.info(f"Sync completed: {downloaded_count} downloaded, {error_count} errors, {cleaned_count} cleaned")
        
    except Exception as e:
        current_app.logger.error(f"Critical error during sync: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        flash(f'Critical error during synchronization: {str(e)}', 'danger')
    
    return redirect(url_for('modules.shop'))

def cleanup_orphaned_modules():
    """Clean up modules marked as downloaded but files don't exist"""
    try:
        orphaned_count = 0
        all_modules = Module.query.all()
        
        for module in all_modules:
            try:
                # If module has a local_path but file doesn't exist, clean it up
                if module.local_path and not os.path.exists(module.local_path):
                    current_app.logger.warning(f"Orphaned module found: {module.name} at {module.local_path}")
                    # Reset the module state so it can be downloaded again
                    module.local_path = None
                    module.installed = False
                    orphaned_count += 1
                elif module.local_path is None and module.name:
                    # Module with no local_path, keep it but log it
                    current_app.logger.info(f"Module {module.name} has no local_path")
                    
            except Exception as module_error:
                current_app.logger.error(f"Error checking module {getattr(module, 'name', 'unknown')}: {module_error}")
                continue
        
        if orphaned_count > 0:
            db.session.commit()
            current_app.logger.info(f"Cleaned up {orphaned_count} orphaned modules")
        
        return orphaned_count
        
    except Exception as e:
        current_app.logger.error(f"Error during orphaned cleanup: {e}")
        db.session.rollback()
        return 0

@modules_bp.route('/cleanup-orphaned', methods=['POST'])
@login_required  
def cleanup_orphaned():
    """Manual cleanup of orphaned modules"""
    try:
        cleaned_count = cleanup_orphaned_modules()
        
        if cleaned_count > 0:
            flash(f'Cleaned up {cleaned_count} orphaned module records. You can now download them again.', 'success')
        else:
            flash('No orphaned modules found.', 'info')
            
    except Exception as e:
        current_app.logger.error(f"Error in manual orphaned cleanup: {e}")
        flash('Error during cleanup.', 'danger')
    
    return redirect(url_for('modules.shop'))

@modules_bp.route('/cleanup')
@login_required
def cleanup():
    try:
        # Enhanced cleanup to remove duplicates and orphaned entries
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
        force_download = request.form.get('force_download', 'false').lower() == 'true'
        
        if not all([module_name, module_url, module_category]):
            flash('Invalid module data', 'danger')
            return redirect(url_for('modules.shop'))
        
        # Check if module already exists and if file actually exists
        existing_module = Module.query.filter_by(name=module_name).first()
        if existing_module and existing_module.local_path and os.path.exists(existing_module.local_path) and not force_download:
            flash(f'Module {module_name} is already downloaded.', 'info')
            return redirect(url_for('modules.shop'))
        
        # Download the module
        success, local_path, message = download_module(module_url, module_name, module_category)
        
        if success:
            # Create or update module record
            if existing_module:
                # Update existing module
                existing_module.description = module_description
                existing_module.category = module_category
                existing_module.remote_url = module_url
                existing_module.local_path = local_path
                existing_module.installed = False  # Reset installation status
                module = existing_module
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
        if module.name in ['base', 'colors'] or (module.local_path and 'core' in module.local_path):
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
            if "incorrect password" in message.lower():
                flash('Installation failed. Please try again with the correct password.', 'danger')
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
        if module.name in ['base', 'colors'] or (module.local_path and 'core' in module.local_path):
            flash('System modules cannot be modified.', 'danger')
            return redirect(url_for('modules.index'))
        
        # Get sudo password
        sudo_password = request.form.get('sudo_password', '')
        
        if not sudo_password:
            flash('Sudo password is required for module uninstallation.', 'danger')
            return redirect(url_for('modules.view', id=id))
        
        # Uninstall the module
        success, message = uninstall_module(module, sudo_password)
        
        if success:
            flash(f'Module {module.name} uninstalled successfully', 'success')
        else:
            if "incorrect password" in message.lower():
                flash('Uninstallation failed. Please try again with the correct password.', 'danger')
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
    
    # FIXED: Further filter out core modules by checking their paths safely
    filtered_modules = []
    for m in modules:
        try:
            # Check if local_path exists and is not None before checking if it contains protected paths
            if m.local_path is not None and not any(p in m.local_path for p in protected_paths):
                filtered_modules.append(m)
            elif m.local_path is None:
                # Log the module with null path but don't crash
                current_app.logger.warning(f"Module {m.name} has null local_path")
        except Exception as e:
            current_app.logger.error(f"Error checking module {m.name}: {e}")
            continue
    
    modules = filtered_modules
    
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
            'remote_url': getattr(module, 'remote_url', '')
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
            'remote_url': getattr(module, 'remote_url', '')
        }
    })
