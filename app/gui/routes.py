# app/gui/routes.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.gui.models import GUIApplication, GUISession, GUICategory, GUISessionLog
from app.gui.manager import GUISessionManager
from datetime import datetime
import traceback

gui_bp = Blueprint('gui', __name__, url_prefix='/gui')

@gui_bp.route('/')
@login_required
def index():
    """Main GUI applications page"""
    # Get applications grouped by category
    categories = GUICategory.query.order_by(GUICategory.sort_order, GUICategory.name).all()
    applications = GUIApplication.query.filter_by(enabled=True).order_by(GUIApplication.name).all()
    
    # Get user's active sessions
    active_sessions = GUISession.query.filter_by(
        user_id=current_user.id, 
        active=True
    ).order_by(GUISession.start_time.desc()).all()
    
    # Group applications by category
    apps_by_category = {}
    for app in applications:
        category = app.category or 'Uncategorized'
        if category not in apps_by_category:
            apps_by_category[category] = []
        apps_by_category[category].append(app)
    
    return render_template(
        'gui/index.html',
        title='GUI Applications',
        categories=categories,
        applications=applications,
        apps_by_category=apps_by_category,
        active_sessions=active_sessions
    )

@gui_bp.route('/applications')
@login_required
def applications():
    """List all GUI applications"""
    category_filter = request.args.get('category')
    search_query = request.args.get('q', '')
    
    # Base query
    query = GUIApplication.query.filter_by(enabled=True)
    
    # Apply filters
    if category_filter:
        query = query.filter_by(category=category_filter)
    
    if search_query:
        query = query.filter(
            db.or_(
                GUIApplication.name.ilike(f'%{search_query}%'),
                GUIApplication.display_name.ilike(f'%{search_query}%'),
                GUIApplication.description.ilike(f'%{search_query}%')
            )
        )
    
    applications = query.order_by(GUIApplication.name).all()
    categories = GUICategory.query.order_by(GUICategory.sort_order, GUICategory.name).all()
    
    return render_template(
        'gui/applications.html',
        title='GUI Applications',
        applications=applications,
        categories=categories,
        current_category=category_filter,
        search_query=search_query
    )

@gui_bp.route('/application/<int:app_id>')
@login_required
def application_detail(app_id):
    """Show application details"""
    application = GUIApplication.query.get_or_404(app_id)
    
    # Get user's sessions for this application
    user_sessions = GUISession.query.filter_by(
        application_id=app_id,
        user_id=current_user.id
    ).order_by(GUISession.start_time.desc()).limit(10).all()
    
    return render_template(
        'gui/application_detail.html',
        title=f'Application: {application.display_name}',
        application=application,
        user_sessions=user_sessions
    )

@gui_bp.route('/sessions')
@login_required
def sessions():
    """List user's GUI sessions"""
    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Get user's sessions
    sessions_query = GUISession.query.filter_by(user_id=current_user.id).order_by(
        GUISession.active.desc(),
        GUISession.start_time.desc()
    )
    
    sessions_pagination = sessions_query.paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Get session statistics
    total_sessions = GUISession.query.filter_by(user_id=current_user.id).count()
    active_sessions = GUISession.query.filter_by(user_id=current_user.id, active=True).count()
    
    return render_template(
        'gui/sessions.html',
        title='GUI Sessions',
        sessions_pagination=sessions_pagination,
        total_sessions=total_sessions,
        active_sessions=active_sessions
    )

@gui_bp.route('/session/<session_id>')
@login_required
def session_detail(session_id):
    """Show session details"""
    session = GUISession.query.filter_by(
        session_id=session_id,
        user_id=current_user.id
    ).first_or_404()
    
    # Get session status
    status = GUISessionManager.get_session_status(session_id)
    
    # Get session logs
    logs = GUISessionLog.query.filter_by(session_id=session_id).order_by(
        GUISessionLog.timestamp.desc()
    ).limit(50).all()
    
    return render_template(
        'gui/session_detail.html',
        title=f'Session: {session.name}',
        session=session,
        status=status,
        logs=logs
    )

@gui_bp.route('/launch/<int:app_id>', methods=['GET', 'POST'])
@login_required
def launch_application(app_id):
    """Launch a GUI application"""
    application = GUIApplication.query.get_or_404(app_id)
    
    if not application.enabled:
        flash('This application is currently disabled.', 'warning')
        return redirect(url_for('gui.application_detail', app_id=app_id))
    
    if request.method == 'POST':
        try:
            # Get form data
            session_name = request.form.get('session_name', '').strip()
            resolution = request.form.get('resolution', '1024x768')
            color_depth = request.form.get('color_depth', 24, type=int)
            
            # Validate inputs
            if not session_name:
                session_name = f"{application.display_name} - {datetime.now().strftime('%H:%M:%S')}"
            
            # Validate resolution
            if not resolution or 'x' not in resolution:
                resolution = '1024x768'
            
            # Validate color depth
            if color_depth not in [16, 24, 32]:
                color_depth = 24
            
            current_app.logger.info(f"User {current_user.username} launching {application.name}")
            
            # Create session
            success, result = GUISessionManager.create_session(
                application_id=app_id,
                user_id=current_user.id,
                session_name=session_name,
                resolution=resolution,
                color_depth=color_depth
            )
            
            if success:
                session = result
                flash(f'Application "{application.display_name}" launched successfully!', 'success')
                return redirect(url_for('gui.session_detail', session_id=session.session_id))
            else:
                error_msg = result
                flash(f'Failed to launch application: {error_msg}', 'danger')
                current_app.logger.error(f"Failed to launch {application.name}: {error_msg}")
                
        except Exception as e:
            current_app.logger.error(f"Error launching application: {e}")
            current_app.logger.error(traceback.format_exc())
            flash(f'An unexpected error occurred: {str(e)}', 'danger')
    
    # GET request - show launch form
    return render_template(
        'gui/launch_application.html',
        title=f'Launch: {application.display_name}',
        application=application
    )

@gui_bp.route('/session/<session_id>/close', methods=['POST'])
@login_required
def close_session(session_id):
    """Close a GUI session"""
    try:
        success, message = GUISessionManager.close_session(session_id, current_user.id)
        
        if success:
            flash(message, 'success')
        else:
            flash(f'Error closing session: {message}', 'danger')
            
    except Exception as e:
        current_app.logger.error(f"Error closing session {session_id}: {e}")
        flash(f'An unexpected error occurred: {str(e)}', 'danger')
    
    return redirect(url_for('gui.sessions'))

@gui_bp.route('/<session_id>/delete', methods=['POST'])
@login_required
def delete_session(session_id):
    """Delete a GUI session and all its data"""
    try:
        session = GUISession.query.filter_by(session_id=session_id, user_id=current_user.id).first_or_404()
        
        # First make sure it's closed
        if session.active:
            GUISessionManager.close_session(session_id, current_user.id)
        
        # Save name for flash message
        session_name = session.name
        
        # Delete all related data
        try:
            # Delete session logs
            deleted_logs = GUISessionLog.query.filter_by(session_id=session.session_id).delete()
            
            # Delete session
            db.session.delete(session)
            db.session.commit()
            
            current_app.logger.info(f"User {current_user.username} deleted GUI session {session_name} with {deleted_logs} log entries")
            flash(f'GUI session "{session_name}" and all its data have been deleted', 'success')
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error deleting GUI session: {e}")
            flash(f'Error deleting session: {str(e)}', 'danger')
        
        return redirect(url_for('gui.sessions'))
        
    except Exception as e:
        current_app.logger.error(f"Error deleting GUI session {session_id}: {e}")
        flash(f'An unexpected error occurred: {str(e)}', 'danger')
        return redirect(url_for('gui.sessions'))

@gui_bp.route('/api/session/<session_id>/delete', methods=['POST'])
@login_required
def api_delete_session(session_id):
    """API endpoint to delete a session"""
    try:
        session = GUISession.query.filter_by(session_id=session_id, user_id=current_user.id).first()
        
        if not session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404
        
        # First close if active
        if session.active:
            success, message = GUISessionManager.close_session(session_id, current_user.id)
            if not success:
                return jsonify({'success': False, 'error': f'Failed to close session: {message}'}), 500
        
        session_name = session.name
        
        # Delete related data
        deleted_logs = GUISessionLog.query.filter_by(session_id=session.session_id).delete()
        
        # Delete session
        db.session.delete(session)
        db.session.commit()
        
        current_app.logger.info(f"User {current_user.username} deleted GUI session {session_name} via API")
        
        return jsonify({
            'success': True,
            'message': f'Session "{session_name}" deleted successfully',
            'deleted_logs': deleted_logs
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"API error deleting GUI session {session_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@gui_bp.route('/session/<session_id>/connect')
@login_required
def connect_session(session_id):
    """Connect to a GUI session via noVNC"""
    session = GUISession.query.filter_by(
        session_id=session_id,
        user_id=current_user.id
    ).first_or_404()
    
    if not session.active:
        flash('Cannot connect to inactive session.', 'warning')
        return redirect(url_for('gui.session_detail', session_id=session_id))
    
    # Check session status
    status = GUISessionManager.get_session_status(session_id)
    if not status.get('exists') or not status.get('active'):
        flash('Session is not available for connection.', 'warning')
        return redirect(url_for('gui.session_detail', session_id=session_id))
    
    # Update last activity
    session.update_activity()
    
    return render_template(
        'gui/connect_session.html',
        title=f'Connect: {session.name}',
        session=session,
        status=status
    )

# API Routes

@gui_bp.route('/api/sessions')
@login_required
def api_sessions():
    """API endpoint to list user's sessions"""
    sessions = GUISession.query.filter_by(user_id=current_user.id).order_by(
        GUISession.active.desc(),
        GUISession.start_time.desc()
    ).all()
    
    return jsonify({
        'success': True,
        'sessions': [session.to_dict() for session in sessions]
    })

@gui_bp.route('/api/session/<session_id>/status')
@login_required
def api_session_status(session_id):
    """API endpoint to get session status"""
    # Verify user owns the session
    session = GUISession.query.filter_by(
        session_id=session_id,
        user_id=current_user.id
    ).first()
    
    if not session:
        return jsonify({'success': False, 'error': 'Session not found'}), 404
    
    status = GUISessionManager.get_session_status(session_id)
    return jsonify({
        'success': True,
        'status': status
    })

@gui_bp.route('/api/session/<session_id>/close', methods=['POST'])
@login_required
def api_close_session(session_id):
    """API endpoint to close a session"""
    try:
        success, message = GUISessionManager.close_session(session_id, current_user.id)
        
        return jsonify({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        current_app.logger.error(f"API error closing session {session_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@gui_bp.route('/api/applications')
@login_required
def api_applications():
    """API endpoint to list applications"""
    applications = GUIApplication.query.filter_by(enabled=True).order_by(
        GUIApplication.name
    ).all()
    
    return jsonify({
        'success': True,
        'applications': [app.to_dict() for app in applications]
    })

@gui_bp.route('/api/application/<int:app_id>/launch', methods=['POST'])
@login_required
def api_launch_application(app_id):
    """API endpoint to launch an application"""
    try:
        application = GUIApplication.query.get(app_id)
        if not application:
            return jsonify({'success': False, 'error': 'Application not found'}), 404
        
        if not application.enabled:
            return jsonify({'success': False, 'error': 'Application is disabled'}), 400
        
        # Get JSON data
        data = request.get_json() or {}
        session_name = data.get('session_name', '').strip()
        resolution = data.get('resolution', '1024x768')
        color_depth = data.get('color_depth', 24)
        
        # Set default session name
        if not session_name:
            session_name = f"{application.display_name} - {datetime.now().strftime('%H:%M:%S')}"
        
        # Create session
        success, result = GUISessionManager.create_session(
            application_id=app_id,
            user_id=current_user.id,
            session_name=session_name,
            resolution=resolution,
            color_depth=color_depth
        )
        
        if success:
            session = result
            return jsonify({
                'success': True,
                'session': session.to_dict(),
                'message': 'Application launched successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': result
            }), 500
            
    except Exception as e:
        current_app.logger.error(f"API error launching application: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@gui_bp.route('/api/cleanup', methods=['POST'])
@login_required
def api_cleanup_sessions():
    """API endpoint to cleanup inactive sessions (admin only)"""
    if not current_user.is_admin():
        return jsonify({'success': False, 'error': 'Admin access required'}), 403
    
    try:
        cleaned_count = GUISessionManager.cleanup_inactive_sessions()
        
        return jsonify({
            'success': True,
            'message': f'Cleaned up {cleaned_count} inactive sessions',
            'cleaned_count': cleaned_count
        })
        
    except Exception as e:
        current_app.logger.error(f"API error during cleanup: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Background cleanup task endpoint (for scheduled jobs)
@gui_bp.route('/api/maintenance/cleanup', methods=['POST'])
def api_maintenance_cleanup():
    """Maintenance endpoint for cleaning up sessions (no auth required, for cron jobs)"""
    # Optional: Add IP whitelist or token-based auth for security
    client_ip = request.remote_addr
    
    # Only allow from localhost for security
    if client_ip not in ['127.0.0.1', '::1']:
        return jsonify({'success': False, 'error': 'Access denied'}), 403
    
    try:
        cleaned_count = GUISessionManager.cleanup_inactive_sessions()
        
        current_app.logger.info(f"Maintenance cleanup completed: {cleaned_count} sessions cleaned")
        
        return jsonify({
            'success': True,
            'message': f'Maintenance cleanup completed',
            'cleaned_count': cleaned_count,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        current_app.logger.error(f"Maintenance cleanup error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Error handlers specific to GUI module
@gui_bp.errorhandler(404)
def gui_not_found(error):
    return render_template('gui/error.html', 
                         title='Page Not Found',
                         error_code=404,
                         error_message='The requested GUI resource was not found.'), 404

@gui_bp.errorhandler(500)
def gui_server_error(error):
    db.session.rollback()
    return render_template('gui/error.html',
                         title='Server Error', 
                         error_code=500,
                         error_message='An internal server error occurred.'), 500

# Nuevas rutas para agregar aplicaciones

@gui_bp.route('/add-application', methods=['GET', 'POST'])
@login_required
def add_application():
    """Add a new GUI application"""
    if request.method == 'POST':
        try:
            # Handle JSON requests (from API)
            if request.is_json:
                data = request.get_json()
            else:
                # Handle form data
                data = request.form.to_dict()
                
                # Process environment variables
                env_keys = request.form.getlist('env_keys[]')
                env_values = request.form.getlist('env_values[]')
                env_dict = {}
                
                for i, key in enumerate(env_keys):
                    if key.strip() and i < len(env_values):
                        env_dict[key.strip()] = env_values[i].strip()
                
                if env_dict:
                    data['environment_vars'] = env_dict
            
            # Validate required fields
            required_fields = ['name', 'display_name', 'command']
            for field in required_fields:
                if not data.get(field, '').strip():
                    if request.is_json:
                        return jsonify({'success': False, 'error': f'{field} is required'}), 400
                    flash(f'{field.replace("_", " ").title()} is required.', 'danger')
                    return redirect(url_for('gui.add_application'))
            
            # Check if application name already exists
            existing_app = GUIApplication.query.filter_by(name=data['name'].strip()).first()
            if existing_app:
                error_msg = f"Application with name '{data['name']}' already exists"
                if request.is_json:
                    return jsonify({'success': False, 'error': error_msg}), 400
                flash(error_msg, 'danger')
                return redirect(url_for('gui.add_application'))
            
            # Test if command is available
            command_available = _test_command_availability(data['command'].strip())
            
            # Create new application
            app = GUIApplication(
                name=data['name'].strip(),
                display_name=data['display_name'].strip(),
                description=data.get('description', '').strip(),
                category=data.get('category', '').strip() or None,
                command=data['command'].strip(),
                working_directory=data.get('working_directory', '').strip() or None,
                version=data.get('version', '').strip() or None,
                icon_path=data.get('icon_path', '').strip() or None,
                installed=command_available,
                enabled=True
            )
            
            # Set environment variables if provided
            if 'environment_vars' in data and data['environment_vars']:
                app.set_environment_dict(data['environment_vars'])
            
            db.session.add(app)
            db.session.commit()
            
            current_app.logger.info(f"User {current_user.username} added GUI application: {app.name}")
            
            if request.is_json:
                return jsonify({
                    'success': True,
                    'message': 'Application added successfully',
                    'application': app.to_dict()
                })
            
            flash(f'Application "{app.display_name}" added successfully!', 'success')
            return redirect(url_for('gui.application_detail', app_id=app.id))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error adding GUI application: {e}")
            current_app.logger.error(traceback.format_exc())
            
            error_msg = f'Error adding application: {str(e)}'
            if request.is_json:
                return jsonify({'success': False, 'error': error_msg}), 500
            flash(error_msg, 'danger')
    
    # GET request - show form
    categories = GUICategory.query.order_by(GUICategory.sort_order, GUICategory.name).all()
    return render_template(
        'gui/add_application.html',
        title='Add GUI Application',
        categories=categories
    )

@gui_bp.route('/api/test-command', methods=['POST'])
@login_required
def api_test_command():
    """Test if a command is available on the system"""
    try:
        data = request.get_json()
        command = data.get('command', '').strip()
        
        if not command:
            return jsonify({'available': False, 'error': 'No command provided'})
        
        available = _test_command_availability(command)
        
        return jsonify({
            'available': available,
            'command': command
        })
        
    except Exception as e:
        current_app.logger.error(f"Error testing command: {e}")
        return jsonify({'available': False, 'error': str(e)})

@gui_bp.route('/api/scan-applications', methods=['POST'])
@login_required
def api_scan_applications():
    """Scan system for available GUI applications"""
    try:
        current_app.logger.info(f"User {current_user.username} initiated application scan")
        
        # Get existing application names
        existing_apps = set(app.name for app in GUIApplication.query.all())
        
        # Scan for common GUI applications
        scanned_apps = _scan_system_applications()
        
        # Filter out already existing applications
        new_apps = [app for app in scanned_apps if app['name'] not in existing_apps]
        
        return jsonify({
            'success': True,
            'applications': new_apps,
            'total_found': len(scanned_apps),
            'new_applications': len(new_apps)
        })
        
    except Exception as e:
        current_app.logger.error(f"Error scanning applications: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'applications': []
        })

@gui_bp.route('/api/add-scanned-applications', methods=['POST'])
@login_required
def api_add_scanned_applications():
    """Add multiple scanned applications at once"""
    try:
        data = request.get_json()
        applications_data = data.get('applications', [])
        
        if not applications_data:
            return jsonify({'success': False, 'error': 'No applications provided'})
        
        added_apps = []
        errors = []
        
        for app_data in applications_data:
            try:
                # Check if application already exists
                if GUIApplication.query.filter_by(name=app_data['name']).first():
                    errors.append(f"Application '{app_data['name']}' already exists")
                    continue
                
                # Create application
                app = GUIApplication(
                    name=app_data['name'],
                    display_name=app_data['display_name'],
                    description=app_data.get('description', ''),
                    category=app_data.get('category'),
                    command=app_data['command'],
                    icon_path=app_data.get('icon_path'),
                    installed=True,  # Assumed available since it was scanned
                    enabled=True
                )
                
                db.session.add(app)
                added_apps.append(app_data['display_name'])
                
            except Exception as e:
                errors.append(f"Error adding '{app_data.get('name', 'unknown')}': {str(e)}")
        
        db.session.commit()
        
        current_app.logger.info(f"User {current_user.username} added {len(added_apps)} GUI applications via scan")
        
        return jsonify({
            'success': True,
            'added_count': len(added_apps),
            'added_applications': added_apps,
            'errors': errors
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error adding scanned applications: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@gui_bp.route('/api/system-info')
@login_required
def api_system_info():
    """Get system information for GUI applications"""
    try:
        import platform
        import os
        
        # Get basic system info
        system_info = {
            'os': f"{platform.system()} {platform.release()}",
            'desktop': os.environ.get('DESKTOP_SESSION', 'Unknown'),
            'gui_apps_count': GUIApplication.query.count()
        }
        
        # Try to detect desktop environment
        if 'XDG_CURRENT_DESKTOP' in os.environ:
            system_info['desktop'] = os.environ['XDG_CURRENT_DESKTOP']
        elif 'GNOME_DESKTOP_SESSION_ID' in os.environ:
            system_info['desktop'] = 'GNOME'
        elif 'KDE_SESSION_VERSION' in os.environ:
            system_info['desktop'] = 'KDE'
        
        return jsonify(system_info)
        
    except Exception as e:
        current_app.logger.error(f"Error getting system info: {e}")
        return jsonify({
            'os': 'Unknown',
            'desktop': 'Unknown',
            'gui_apps_count': 0
        })

# Helper functions

def _test_command_availability(command):
    """Test if a command is available on the system"""
    try:
        import shutil
        
        # Extract the base command (first word)
        base_command = command.split()[0]
        
        # Check if command exists
        return shutil.which(base_command) is not None
        
    except Exception as e:
        current_app.logger.error(f"Error testing command availability: {e}")
        return False

def _scan_system_applications():
    """Scan system for common GUI applications"""
    try:
        import shutil
        import os
        
        # Common GUI applications with their details
        common_apps = [
            # Web Browsers
            {
                'name': 'firefox',
                'display_name': 'Firefox',
                'description': 'Mozilla Firefox web browser',
                'command': 'firefox',
                'category': 'browsers',
                'icon_path': '/usr/share/pixmaps/firefox.png'
            },
            {
                'name': 'chromium',
                'display_name': 'Chromium',
                'description': 'Open-source web browser',
                'command': 'chromium-browser',
                'category': 'browsers',
                'icon_path': '/usr/share/pixmaps/chromium.png'
            },
            {
                'name': 'google-chrome',
                'display_name': 'Google Chrome',
                'description': 'Google Chrome web browser',
                'command': 'google-chrome',
                'category': 'browsers',
                'icon_path': '/usr/share/pixmaps/google-chrome.png'
            },
            
            # Text Editors
            {
                'name': 'gedit',
                'display_name': 'Text Editor (gedit)',
                'description': 'GNOME text editor',
                'command': 'gedit',
                'category': 'editors',
                'icon_path': '/usr/share/pixmaps/gedit.png'
            },
            {
                'name': 'nano',
                'display_name': 'Nano Editor',
                'description': 'Simple text editor',
                'command': 'nano',
                'category': 'editors',
                'icon_path': '/usr/share/pixmaps/nano.png'
            },
            {
                'name': 'vim',
                'display_name': 'Vim Editor',
                'description': 'Vi improved text editor',
                'command': 'gvim',
                'category': 'editors',
                'icon_path': '/usr/share/pixmaps/vim.png'
            },
            
            # Terminals
            {
                'name': 'xterm',
                'display_name': 'XTerm',
                'description': 'Classic X terminal emulator',
                'command': 'xterm',
                'category': 'terminals',
                'icon_path': '/usr/share/pixmaps/xterm.png'
            },
            {
                'name': 'gnome-terminal',
                'display_name': 'GNOME Terminal',
                'description': 'GNOME terminal emulator',
                'command': 'gnome-terminal',
                'category': 'terminals',
                'icon_path': '/usr/share/pixmaps/gnome-terminal.png'
            },
            
            # Utilities
            {
                'name': 'calculator',
                'display_name': 'Calculator',
                'description': 'Desktop calculator',
                'command': 'gnome-calculator',
                'category': 'utilities',
                'icon_path': '/usr/share/pixmaps/calc.png'
            },
            {
                'name': 'file-manager',
                'display_name': 'File Manager',
                'description': 'GNOME file manager',
                'command': 'nautilus',
                'category': 'utilities',
                'icon_path': '/usr/share/pixmaps/nautilus.png'
            },
            
            # Development
            {
                'name': 'code',
                'display_name': 'Visual Studio Code',
                'description': 'Code editor by Microsoft',
                'command': 'code',
                'category': 'development',
                'icon_path': '/usr/share/pixmaps/code.png'
            },
            
            # Multimedia
            {
                'name': 'vlc',
                'display_name': 'VLC Media Player',
                'description': 'Multimedia player',
                'command': 'vlc',
                'category': 'multimedia',
                'icon_path': '/usr/share/pixmaps/vlc.png'
            }
        ]
        
        # Test each application and return only available ones
        available_apps = []
        
        for app in common_apps:
            if _test_command_availability(app['command']):
                # Check if icon exists
                if app['icon_path'] and not os.path.exists(app['icon_path']):
                    app['icon_path'] = None
                
                available_apps.append(app)
        
        current_app.logger.info(f"Scanned system: found {len(available_apps)} available GUI applications")
        return available_apps
        
    except Exception as e:
        current_app.logger.error(f"Error scanning system applications: {e}")
        return []