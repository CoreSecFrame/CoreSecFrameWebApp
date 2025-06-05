from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.gui.models import GUIApplication, GUISession, GUICategory, GUISessionLog
from app.gui.manager import GUISessionManager, GUIEnvironmentDetector
from datetime import datetime
import traceback
import shutil # For _test_command_availability and _scan_system_applications
import os # For _scan_system_applications
import subprocess

# Module-level constant for default applications to scan
DEFAULT_SCAN_APPLICATIONS = [
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
        'command': 'gvim', # gvim is the GUI version
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
        'command': 'gnome-calculator', # Example, might vary (e.g., kcalc)
        'category': 'utilities',
        'icon_path': '/usr/share/pixmaps/calc.png' # Example path
    },
    {
        'name': 'file-manager',
        'display_name': 'File Manager',
        'description': 'GNOME file manager', # Example, could be Dolphin, Thunar etc.
        'command': 'nautilus', 
        'category': 'utilities',
        'icon_path': '/usr/share/pixmaps/nautilus.png' # Example path
    },
    
    # Development
    {
        'name': 'code',
        'display_name': 'Visual Studio Code',
        'description': 'Code editor by Microsoft',
        'command': 'code',
        'category': 'development',
        'icon_path': '/usr/share/pixmaps/code.png' # Example path
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

gui_bp = Blueprint('gui', __name__, url_prefix='/gui')

@gui_bp.route('/')
@login_required
def index():
    """Main GUI applications page with WSLg awareness"""
    # Detect environment
    env_info = GUIEnvironmentDetector.detect_environment()
    
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
        active_sessions=active_sessions,
        # Environment info for templates
        gui_environment=env_info['display_method'],
        gui_uses_wslg=env_info['has_wslg'],
        gui_has_wayland=bool(env_info['wayland_display']),
        gui_has_x11=bool(env_info['x11_display']),
        gui_is_wsl=env_info['is_wsl']
    )


@gui_bp.route('/applications')
@login_required
def applications():
    """List all GUI applications with environment awareness"""
    category_filter = request.args.get('category')
    search_query = request.args.get('q', '')
    env_info = GUIEnvironmentDetector.detect_environment()
    
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
        search_query=search_query,
        # Environment info
        gui_environment=env_info['display_method'],
        gui_uses_wslg=env_info['has_wslg']
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
    """List user's GUI sessions with environment awareness"""
    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = 20
    env_info = GUIEnvironmentDetector.detect_environment()
    
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
        active_sessions=active_sessions,
        # Environment info
        gui_environment=env_info['display_method'],
        gui_uses_wslg=env_info['has_wslg']
    )

@gui_bp.route('/api/environment')
@login_required
def api_environment():
    """API endpoint to get GUI environment information"""
    try:
        env_info = GUIEnvironmentDetector.detect_environment()
        
        return jsonify({
            'success': True,
            'environment': {
                'display_method': env_info['display_method'],
                'is_wsl': env_info['is_wsl'],
                'has_wslg': env_info['has_wslg'],
                'is_linux_native': env_info['is_linux_native'],
                'wayland_display': env_info['wayland_display'],
                'x11_display': env_info['x11_display'],
                'connection_type': 'native' if env_info['has_wslg'] else 'vnc',
                'features': {
                    'native_integration': env_info['has_wslg'],
                    'vnc_required': not env_info['has_wslg'],
                    'clipboard_sharing': env_info['has_wslg'],
                    'audio_support': env_info['has_wslg'],
                    'file_integration': env_info['has_wslg'],
                    'window_management': env_info['has_wslg'],
                    'drag_and_drop': env_info['has_wslg']
                },
                'recommendations': {
                    'optimal_for_wslg': env_info['has_wslg'],
                    'message': 'Using WSLg for optimal GUI experience!' if env_info['has_wslg'] else 'Traditional VNC mode - consider upgrading to WSLg for better performance'
                }
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting environment info: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
        
    except Exception as e:
        current_app.logger.error(f"Error getting environment info: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@gui_bp.route('/session/<session_id>')
@login_required
def session_detail(session_id):
    """Show session details with WSLg-aware information"""
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
    
    # Detect environment
    env_info = GUIEnvironmentDetector.detect_environment()
    
    return render_template(
        'gui/session_detail.html',
        title=f'Session: {session.name}',
        session=session,
        status=status,
        logs=logs,
        # Environment info
        gui_environment=env_info['display_method'],
        gui_uses_wslg=env_info['has_wslg'],
        gui_has_wayland=bool(env_info['wayland_display']),
        gui_has_x11=bool(env_info['x11_display']),
        gui_is_wsl=env_info['is_wsl']
    )

@gui_bp.route('/launch/<int:app_id>', methods=['GET', 'POST'])
@login_required
def launch_application(app_id):
    """Launch a GUI application with WSLg-aware handling"""
    application = GUIApplication.query.get_or_404(app_id)
    
    if not application.enabled:
        flash('This application is currently disabled.', 'warning')
        return redirect(url_for('gui.application_detail', app_id=app_id))
    
    # Detect environment for UI customization
    env_info = GUIEnvironmentDetector.detect_environment()
    
    if request.method == 'POST':
        try:
            # Get form data
            session_name = request.form.get('session_name', '').strip()
            resolution = request.form.get('resolution', '1024x768')
            color_depth = request.form.get('color_depth', 24, type=int)
            
            # Validate inputs
            if not session_name:
                session_name = f"{application.display_name} - {datetime.now().strftime('%H:%M:%S')}"
            
            # For WSLg, resolution is not as relevant but keep for compatibility
            if env_info['has_wslg']:
                resolution = "native"  # WSLg handles this automatically
            elif not resolution or 'x' not in resolution:
                resolution = '1024x768'
            
            # Validate color depth
            if color_depth not in [16, 24, 32]:
                color_depth = 24
            
            current_app.logger.info(f"User {current_user.username} launching {application.name} in {env_info['display_method']} mode")
            
            # Create session using adaptive manager
            success, result = GUISessionManager.create_session(
                application_id=app_id,
                user_id=current_user.id,
                session_name=session_name,
                resolution=resolution,
                color_depth=color_depth
            )
            
            if success:
                session = result
                
                if env_info['has_wslg']:
                    # WSLg success messages - more specific and helpful
                    flash(f'🚀 {application.display_name} launched successfully with WSLg!', 'success')
                    flash('🎯 Your application is now running natively in Windows.', 'info')
                    flash('💡 Check your Windows taskbar or use Alt+Tab to find the application.', 'info')
                    flash('✨ Full clipboard, audio, and file integration is active!', 'info')
                else:
                    # VNC success messages
                    flash(f'🚀 {application.display_name} launched successfully!', 'success')
                    flash(f'🔗 VNC server ready on display :{session.display_number}, port {session.vnc_port}', 'info')
                    flash('📱 Use a VNC client to connect, or try the web interface.', 'info')
                
                return redirect(url_for('gui.session_detail', session_id=session.session_id))
            else:
                error_msg = result
                
                if env_info['has_wslg']:
                    flash(f'❌ Failed to launch WSLg application: {error_msg}', 'danger')
                    flash('💡 Try checking if the application is installed and accessible.', 'warning')
                else:
                    flash(f'❌ Failed to launch VNC session: {error_msg}', 'danger')
                    flash('💡 Check system requirements: Xvfb, x11vnc must be installed.', 'warning')
                    
                current_app.logger.error(f"Failed to launch {application.name}: {error_msg}")
                
        except Exception as e:
            current_app.logger.error(f"Error launching application: {e}")
            current_app.logger.error(traceback.format_exc())
            
            if env_info['has_wslg']:
                flash(f'❌ WSLg launch error: {str(e)}', 'danger')
            else:
                flash(f'❌ VNC launch error: {str(e)}', 'danger')
    
    # GET request - show launch form with environment-specific information
    # Get user's recent sessions for this app
    user_sessions = GUISession.query.filter_by(
        application_id=app_id,
        user_id=current_user.id
    ).order_by(GUISession.start_time.desc()).limit(5).all()
    
    return render_template(
        'gui/launch_application.html',
        title=f'Launch: {application.display_name}',
        application=application,
        user_sessions=user_sessions,
        # Environment info
        gui_environment=env_info['display_method'],
        gui_uses_wslg=env_info['has_wslg'],
        gui_has_wayland=bool(env_info['wayland_display']),
        gui_has_x11=bool(env_info['x11_display']),
        gui_is_wsl=env_info['is_wsl'],
        # Additional context - current time for form
        current_time=datetime.now().strftime('%H:%M:%S')
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
    """Connect to a GUI session with WSLg awareness"""
    session = GUISession.query.filter_by(
        session_id=session_id,
        user_id=current_user.id
    ).first_or_404()
    
    env_info = GUIEnvironmentDetector.detect_environment()
    
    if not session.active:
        flash('Cannot connect to inactive session.', 'warning')
        return redirect(url_for('gui.session_detail', session_id=session_id))
    
    # For WSLg, redirect to session details with specific message
    if env_info['has_wslg']:
        flash('🎯 WSLg applications run natively in Windows - check your taskbar!', 'info')
        flash('💡 No VNC connection needed. The application should be visible as a regular Windows app.', 'info')
        return redirect(url_for('gui.session_detail', session_id=session_id))
    
    # For traditional VNC, check session status
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
        status=status,
        gui_environment=env_info['display_method'],
        gui_uses_wslg=env_info['has_wslg'],
        gui_has_wayland=bool(env_info['wayland_display']),
        gui_has_x11=bool(env_info['x11_display']),
        gui_is_wsl=env_info['is_wsl']
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
    """API endpoint to launch an application with WSLg awareness"""
    try:
        application = GUIApplication.query.get(app_id)
        if not application:
            return jsonify({'success': False, 'error': 'Application not found'}), 404
        
        if not application.enabled:
            return jsonify({'success': False, 'error': 'Application is disabled'}), 400
        
        # Detect environment
        env_info = GUIEnvironmentDetector.detect_environment()
        
        # Get JSON data
        data = request.get_json() or {}
        session_name = data.get('session_name', '').strip()
        resolution = data.get('resolution', '1024x768')
        color_depth = data.get('color_depth', 24)
        
        # Set default session name
        if not session_name:
            session_name = f"{application.display_name} - {datetime.now().strftime('%H:%M:%S')}"
        
        # Adjust for WSLg
        if env_info['has_wslg']:
            resolution = "native"
        
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
            session_data = session.to_dict()
            
            # Add environment-specific information
            session_data['environment'] = env_info['display_method']
            session_data['connection_type'] = 'native' if env_info['has_wslg'] else 'vnc'
            
            # Customize instructions based on environment
            if env_info['has_wslg']:
                instructions = {
                    'primary': '🚀 Application launched natively in Windows!',
                    'secondary': '🎯 Look for the application in your Windows taskbar or desktop.',
                    'tips': [
                        '✨ The application runs as a native Windows application',
                        '📋 Full clipboard, audio, and file integration available',
                        '🖱️ No VNC client needed - interact directly with the app',
                        '🪟 Window management works just like regular Windows apps',
                        '🔍 Use Alt+Tab to switch between applications',
                        '📁 Drag files from Windows Explorer directly into the app'
                    ],
                    'next_steps': [
                        'Check your Windows taskbar for the application icon',
                        'Use Alt+Tab to cycle through open applications',
                        'Right-click the taskbar icon for context menu options'
                    ]
                }
            else:
                instructions = {
                    'primary': f'🖥️ VNC session created on display :{session.display_number}',
                    'secondary': f'🔗 Connect using VNC client to localhost:{session.vnc_port}',
                    'tips': [
                        '🔌 Use any VNC client (TigerVNC, RealVNC, etc.)',
                        f'📡 Connect to localhost:{session.vnc_port}',
                        '🌐 Use the web interface for browser-based access',
                        '⏰ Session will remain active until manually closed',
                        '🎨 Adjust color depth for better performance',
                        '📏 Change resolution if display appears too small/large'
                    ],
                    'next_steps': [
                        'Download and install a VNC client if needed',
                        f'Connect to localhost:{session.vnc_port}',
                        'Use the session details page for connection help'
                    ]
                }
            
            session_data['instructions'] = instructions
            
            return jsonify({
                'success': True,
                'session': session_data,
                'message': f'Application launched successfully using {env_info["display_method"]}',
                'environment': env_info
            })
        else:
            error_msg = result
            return jsonify({
                'success': False,
                'error': error_msg,
                'environment': env_info,
                'troubleshooting': {
                    'wslg': env_info['has_wslg'],
                    'suggestions': [
                        'Check if the application is installed and accessible',
                        'Verify system requirements are met',
                        'Try launching with different settings'
                    ] if env_info['has_wslg'] else [
                        'Ensure Xvfb and x11vnc are installed',
                        'Check for port conflicts',
                        'Verify X11 display availability',
                        'Try different resolution settings'
                    ]
                }
            }), 500
            
    except Exception as e:
        current_app.logger.error(f"API error launching application: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'troubleshooting': {
                'general': 'An unexpected error occurred',
                'suggestions': [
                    'Check server logs for more details',
                    'Try refreshing the page and launching again',
                    'Contact administrator if problem persists'
                ]
            }
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
            # Manejo de datos del formulario y JSON
            if request.is_json:
                data = request.get_json()
                if not data:
                    return jsonify({'success': False, 'error': 'No JSON data received'}), 400
            else:
                # Manejar datos del formulario
                data = {}
                
                # Campos básicos
                data['name'] = request.form.get('name', '').strip()
                data['display_name'] = request.form.get('display_name', '').strip()
                data['description'] = request.form.get('description', '').strip()
                data['category'] = request.form.get('category', '').strip()
                data['command'] = request.form.get('command', '').strip()
                data['working_directory'] = request.form.get('working_directory', '').strip()
                data['version'] = request.form.get('version', '').strip()
                data['icon_path'] = request.form.get('icon_path', '').strip()
                
                # Procesar variables de entorno
                env_keys = request.form.getlist('env_keys[]')
                env_values = request.form.getlist('env_values[]')
                env_dict = {}
                
                for i, key in enumerate(env_keys):
                    if key.strip() and i < len(env_values) and env_values[i].strip():
                        env_dict[key.strip()] = env_values[i].strip()
                
                if env_dict:
                    data['environment_vars'] = env_dict
            
            # Validar campos requeridos
            required_fields = ['name', 'display_name', 'command']
            missing_fields = []
            
            for field in required_fields:
                if not data.get(field, '').strip():
                    missing_fields.append(field.replace('_', ' ').title())
            
            if missing_fields:
                error_msg = f"Required fields missing: {', '.join(missing_fields)}"
                if request.is_json:
                    return jsonify({'success': False, 'error': error_msg}), 400
                flash(error_msg, 'danger')
                return redirect(url_for('gui.add_application'))
            
            # Validar nombre único
            existing_app = GUIApplication.query.filter_by(name=data['name'].strip()).first()
            if existing_app:
                error_msg = f"Application with name '{data['name']}' already exists"
                if request.is_json:
                    return jsonify({'success': False, 'error': error_msg}), 400
                flash(error_msg, 'danger')
                return redirect(url_for('gui.add_application'))
            
            # Validar comando
            command_parts = data['command'].strip().split()
            if not command_parts:
                error_msg = "Invalid command format"
                if request.is_json:
                    return jsonify({'success': False, 'error': error_msg}), 400
                flash(error_msg, 'danger')
                return redirect(url_for('gui.add_application'))
            
            # Verificar si el comando está disponible
            command_available = _test_command_availability(data['command'].strip())
            
            # Crear nueva aplicación
            app = GUIApplication(
                name=data['name'].strip(),
                display_name=data['display_name'].strip(),
                description=data.get('description', '').strip() or None,
                category=data.get('category', '').strip() or None,
                command=data['command'].strip(),
                working_directory=data.get('working_directory', '').strip() or None,
                version=data.get('version', '').strip() or None,
                icon_path=data.get('icon_path', '').strip() or None,
                installed=command_available,
                enabled=True
            )
            
            # Establecer variables de entorno si se proporcionan
            if 'environment_vars' in data and data['environment_vars']:
                app.set_environment_dict(data['environment_vars'])
            
            # Guardar en base de datos
            db.session.add(app)
            db.session.commit()
            
            current_app.logger.info(f"User {current_user.username} added GUI application: {app.name}")
            
            success_msg = f'Application "{app.display_name}" added successfully!'
            if not command_available:
                success_msg += f' (Command "{command_parts[0]}" not found - marked as not installed)'
            
            if request.is_json:
                response_data = {
                    'success': True,
                    'message': success_msg,
                    'application': app.to_dict(),
                    'command_available': command_available
                }
                return jsonify(response_data), 200
            
            flash(success_msg, 'success')
            return redirect(url_for('gui.application_detail', app_id=app.id))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error adding GUI application: {e}")
            current_app.logger.error(traceback.format_exc())
            
            error_msg = f'Error adding application: {str(e)}'
            if request.is_json:
                return jsonify({'success': False, 'error': error_msg}), 500
            flash(error_msg, 'danger')
            return redirect(url_for('gui.add_application'))
    
    # GET request - mostrar formulario
    try:
        categories = GUICategory.query.order_by(GUICategory.sort_order, GUICategory.name).all()
        return render_template(
            'gui/add_application.html',
            title='Add GUI Application',
            categories=categories
        )
    except Exception as e:
        current_app.logger.error(f"Error loading add application form: {e}")
        flash('Error loading form', 'danger')
        return redirect(url_for('gui.index'))

@gui_bp.route('/api/test-command', methods=['POST'])
@login_required
def api_test_command():
    """Test if a command is available on the system"""
    try:
        # Validar request JSON
        data, error_response, status_code = validate_json_request(['command'])
        if error_response:
            return error_response, status_code
        
        command = data.get('command', '').strip()
        
        if not command:
            return jsonify({
                'success': False, 
                'available': False, 
                'error': 'Command cannot be empty'
            }), 400
        
        # Extraer el comando base (primera palabra)
        command_parts = command.split()
        base_command = command_parts[0] if command_parts else command
        
        # Log para debugging
        current_app.logger.debug(f"Testing command: '{command}' (base: '{base_command}')")
        
        # Verificar disponibilidad
        available = _test_command_availability(command)
        
        response_data = {
            'success': True,
            'available': available,
            'command': command,
            'base_command': base_command
        }
        
        if available:
            # Intentar obtener información adicional del comando
            try:
                which_result = shutil.which(base_command)
                if which_result:
                    response_data['path'] = which_result
                    current_app.logger.debug(f"Command found at: {which_result}")
            except Exception as e:
                current_app.logger.warning(f"Error getting command path: {e}")
        else:
            current_app.logger.debug(f"Command '{base_command}' not found in PATH")
        
        return jsonify(response_data), 200
        
    except Exception as e:
        current_app.logger.error(f"Error testing command: {e}")
        current_app.logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'available': False, 
            'error': f'Server error: {str(e)}'
        }), 500

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
    """Test if a command is available and executable on the system"""
    try:
        if not command or not command.strip():
            return False

        command_parts = command.strip().split()
        if not command_parts:
            return False
        
        base_command = command_parts[0]
        current_app.logger.debug(f"Testing command availability for: '{base_command}' (full command: '{command}')")

        command_path = None
        
        # Try to find command using 'command -v'
        try:
            current_app.logger.debug(f"Attempting to find '{base_command}' using 'command -v'")
            command_v_result = subprocess.run(['command', '-v', base_command], 
                                              capture_output=True, text=True, check=False, timeout=5)
            if command_v_result.returncode == 0 and command_v_result.stdout.strip():
                command_path = command_v_result.stdout.strip()
                current_app.logger.info(f"Command '{base_command}' found using 'command -v': {command_path}")
            else:
                current_app.logger.debug(f"'command -v {base_command}' failed or returned empty. RC: {command_v_result.returncode}, Stdout: '{command_v_result.stdout.strip()}'")
        except FileNotFoundError:
            current_app.logger.warning("Utility 'command' not found. Falling back to shutil.which for command lookup.")
            command_path = None # Ensure fallback to shutil.which occurs
        except subprocess.TimeoutExpired:
            current_app.logger.warning(f"'command -v {base_command}' timed out.")
        except Exception as e: # General exception for other subprocess errors
            current_app.logger.warning(f"Error running 'command -v {base_command}': {e}")

        # If 'command -v' fails (or 'command' utility not found), try shutil.which
        if not command_path:
            current_app.logger.debug(f"Attempting to find '{base_command}' using 'shutil.which'")
            command_path_shutil = shutil.which(base_command)
            if command_path_shutil:
                command_path = command_path_shutil
                current_app.logger.info(f"Command '{base_command}' found using 'shutil.which': {command_path}")
            else:
                current_app.logger.debug(f"'shutil.which({base_command})' did not find the command.")

        if command_path:
            current_app.logger.debug(f"Command '{base_command}' resolved to path: {command_path}")
            
            # Additional checks for the found command
            try:
                # Check if it's actually executable
                if not os.access(command_path, os.X_OK):
                    current_app.logger.warning(f"Command path '{command_path}' for '{base_command}' found but not executable.")
                    return False
                
                current_app.logger.debug(f"Command path '{command_path}' is executable. Checking file type.")
                # Get file information
                try:
                    # Run 'file' command without check=True, handle errors manually
                    file_info_process = subprocess.run(['file', command_path], 
                                                       capture_output=True, text=True, timeout=5, check=False)
                    
                    if file_info_process.returncode != 0:
                        current_app.logger.warning(f"'file {command_path}' failed with RC {file_info_process.returncode}: {file_info_process.stderr.strip()}")
                        # If 'file' command fails, we might still consider it available if it's executable
                        # but log a warning. This behavior is similar to previous logic.
                        return True

                    file_type = file_info_process.stdout.strip().lower()
                    current_app.logger.debug(f"File type for '{command_path}': {file_type}")
                        
                    if 'cannot execute binary file' in file_type:
                        current_app.logger.warning(f"Binary file architecture mismatch for '{command_path}': {file_type}")
                        return False
                        
                    if 'script' in file_type or command_path.endswith(('.sh', '.py', '.pl', '.rb')):
                        current_app.logger.debug(f"Detected script: '{command_path}'")
                        if command_path.endswith('.sh'):
                            try:
                                with open(command_path, 'r', encoding='utf-8', errors='ignore') as f:
                                    first_line = f.readline().strip()
                                    if not first_line.startswith('#!'):
                                        current_app.logger.debug(f"Shell script '{command_path}' without shebang. Assuming bash can handle.")
                            except Exception as e_script:
                                current_app.logger.warning(f"Could not read script '{command_path}' to check shebang: {e_script}")
                        return True
                        
                    if 'java' in file_type or command_path.endswith('.jar'):
                        current_app.logger.debug(f"Detected Java application: '{command_path}'")
                        if shutil.which('java'):
                            return True
                        else:
                            current_app.logger.warning(f"Java application '{command_path}' found, but 'java' runtime is not available in PATH.")
                            return False
                        
                    return True # Default to available if file type is recognized and not problematic
                        
                except subprocess.TimeoutExpired:
                    current_app.logger.warning(f"'file {command_path}' timed out. Assuming available as it's executable.")
                    return True # If file command times out, assume it's available
                except FileNotFoundError:
                    current_app.logger.warning(f"Utility 'file' not found. Skipping file type check for {command_path}.")
                    return True # Proceed as if file check was inconclusive but command is executable
                except Exception as e_file:
                    current_app.logger.error(f"Error running 'file {command_path}': {e_file}", exc_info=True)
                    # If 'file' command has other issues, but path was found and executable, cautiously return True
                    return True
                
            except Exception as e_access:
                current_app.logger.error(f"Error during access or file checks for '{command_path}': {e_access}", exc_info=True)
                return False # If any other unexpected error occurs during these checks
        else:
            # This block is reached if both 'command -v' and 'shutil.which' failed
            current_app.logger.warning(f"Command '{base_command}' not found using 'command -v' or 'shutil.which'.")

        # If not found with 'command -v' or 'shutil.which', try absolute path (existing logic)
        if os.path.isabs(base_command):
            current_app.logger.debug(f"Checking absolute path: {base_command}")
            if os.path.exists(base_command):
                if os.access(base_command, os.X_OK):
                    current_app.logger.debug(f"Absolute path executable: {base_command}")
                    return True
                else:
                    current_app.logger.debug(f"Absolute path exists but not executable: {base_command}")
                    return False
            else:
                current_app.logger.debug(f"Absolute path does not exist: {base_command}")
                return False
        
        # Special handling for common applications that might need special treatment
        if base_command in ['burpsuitepro', 'burp', 'burpsuite']:
            current_app.logger.debug(f"Checking special application: {base_command}")
            return _check_burpsuite_availability()
        
        current_app.logger.debug(f"Command '{base_command}' not found in PATH")
        return False
            
    except Exception as e:
        current_app.logger.error(f"Error testing command availability for '{command}': {e}")
        return False

def _check_burpsuite_availability():
    """Special check for Burp Suite Pro availability"""
    try:
        # Common Burp Suite Pro locations
        burp_locations = [
            '/opt/BurpSuitePro/BurpSuitePro',
            '/usr/local/bin/burpsuitepro',
            os.path.expanduser('~/BurpSuitePro/BurpSuitePro'),
            '/opt/burpsuite_pro/BurpSuitePro'
        ]
        
        jar_locations = [
            '/opt/burpsuite_pro/burpsuite_pro.jar',
            os.path.expanduser('~/burpsuite_pro.jar'),
            '/usr/local/share/burpsuite_pro/burpsuite_pro.jar'
        ]
        
        # Check executable locations
        for location in burp_locations:
            if os.path.exists(location) and os.access(location, os.X_OK):
                current_app.logger.debug(f"Found Burp Suite Pro executable at: {location}")
                return True
        
        # Check JAR locations (if java is available)
        if shutil.which('java'):
            for jar_location in jar_locations:
                if os.path.exists(jar_location):
                    current_app.logger.debug(f"Found Burp Suite Pro JAR at: {jar_location}")
                    return True
        
        # Check in home directory with wildcard
        import glob
        home_pattern = os.path.expanduser('~/*/BurpSuitePro')
        matches = glob.glob(home_pattern)
        for match in matches:
            if os.path.exists(match) and os.access(match, os.X_OK):
                current_app.logger.debug(f"Found Burp Suite Pro in home directory: {match}")
                return True
        
        current_app.logger.debug("Burp Suite Pro not found in common locations")
        return False
        
    except Exception as e:
        current_app.logger.error(f"Error checking Burp Suite availability: {e}")
        return False

def _scan_system_applications():
    """Scan system for common GUI applications using the module-level constant."""
    try:
        # shutil and os are already imported at the module level
        
        # Use the module-level constant
        common_apps_to_scan = DEFAULT_SCAN_APPLICATIONS
        
        available_apps = []
        
        for app_info in common_apps_to_scan: # Iterate over a copy or directly if not modifying
            # Create a copy to avoid modifying the original constant list items
            app = app_info.copy() 
            
            if _test_command_availability(app['command']):
                # Check if icon exists
                if app.get('icon_path') and not os.path.exists(app['icon_path']):
                    app['icon_path'] = None  # Set to None if path is invalid
                
                available_apps.append(app)
        
        current_app.logger.info(f"Scanned system: found {len(available_apps)} available GUI applications from default list.")
        return available_apps
        
    except Exception as e:
        current_app.logger.error(f"Error scanning system applications: {e}")
        return []

# Manejadores de error mejorados
@gui_bp.errorhandler(400)
def bad_request(error):
    if request.is_json or request.path.startswith('/gui/api/'):
        return jsonify({
            'success': False,
            'error': 'Bad request',
            'message': str(error.description) if hasattr(error, 'description') else 'Invalid request'
        }), 400
    return render_template('gui/error.html', 
                         title='Bad Request',
                         error_code=400,
                         error_message='Invalid request.'), 400

@gui_bp.errorhandler(404)
def gui_not_found(error):
    if request.is_json or request.path.startswith('/gui/api/'):
        return jsonify({
            'success': False,
            'error': 'Not found',
            'message': 'The requested resource was not found'
        }), 404
    return render_template('gui/error.html', 
                         title='Page Not Found',
                         error_code=404,
                         error_message='The requested GUI resource was not found.'), 404

@gui_bp.errorhandler(500)
def gui_server_error(error):
    db.session.rollback()
    current_app.logger.error(f"GUI module server error: {error}")
    
    if request.is_json or request.path.startswith('/gui/api/'):
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': 'An unexpected error occurred on the server'
        }), 500
    return render_template('gui/error.html',
                         title='Server Error', 
                         error_code=500,
                         error_message='An internal server error occurred.'), 500

@gui_bp.errorhandler(405)
def method_not_allowed(error):
    if request.is_json or request.path.startswith('/gui/api/'):
        return jsonify({
            'success': False,
            'error': 'Method not allowed',
            'message': f'Method {request.method} not allowed for this endpoint'
        }), 405
    return render_template('gui/error.html',
                         title='Method Not Allowed', 
                         error_code=405,
                         error_message='This method is not allowed for this resource.'), 405

# Middleware para debugging de requests JSON
@gui_bp.before_request
def log_request_info():
    """Log request details for debugging"""
    if current_app.debug and request.path.startswith('/gui/api/'):
        current_app.logger.debug(f"GUI API Request: {request.method} {request.path}")
        current_app.logger.debug(f"Content-Type: {request.content_type}")
        current_app.logger.debug(f"Is JSON: {request.is_json}")
        if request.is_json:
            try:
                data = request.get_json()
                current_app.logger.debug(f"JSON Data: {data}")
            except Exception as e:
                current_app.logger.error(f"Error parsing JSON: {e}")

# Función auxiliar para validar datos JSON
def validate_json_request(required_fields=None):
    """Validate JSON request and return data"""
    if not request.is_json:
        return None, jsonify({
            'success': False,
            'error': 'Content-Type must be application/json'
        }), 400
    
    try:
        data = request.get_json()
        if data is None:
            return None, jsonify({
                'success': False,
                'error': 'No JSON data received'
            }), 400
    except Exception as e:
        return None, jsonify({
            'success': False,
            'error': f'Invalid JSON: {str(e)}'
        }), 400
    
    if required_fields:
        missing_fields = [field for field in required_fields if not data.get(field)]
        if missing_fields:
            return None, jsonify({
                'success': False,
                'error': f'Missing required fields: {", ".join(missing_fields)}'
            }), 400
    
    return data, None, None