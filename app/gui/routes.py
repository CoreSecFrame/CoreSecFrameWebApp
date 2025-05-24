# app/gui/routes.py
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from flask_socketio import emit, join_room, leave_room
from app import db, socketio
from app.gui.models import GUISession, GUIApplication, GUISessionEvent, WebRTCSignalingMessage
from app.gui.manager import GUISessionManager
from app.gui.webrtc_handler import webrtc_handler
from datetime import datetime
import json
import traceback

gui_bp = Blueprint('gui', __name__, url_prefix='/gui')

@gui_bp.route('/')
@login_required
def index():
    """List all GUI sessions for the current user"""
    try:
        # Get active sessions
        active_sessions = GUISession.query.filter_by(
            user_id=current_user.id,
            active=True
        ).order_by(GUISession.last_activity.desc()).all()
        
        # Get inactive sessions
        inactive_sessions = GUISession.query.filter_by(
            user_id=current_user.id,
            active=False
        ).order_by(GUISession.last_activity.desc()).limit(10).all()
        
        # Get available applications
        available_apps = GUIApplication.query.filter_by(
            enabled=True,
            installed=True
        ).order_by(GUIApplication.name).all()
        
        return render_template(
            'gui/index.html',
            title='GUI Sessions',
            active_sessions=active_sessions,
            inactive_sessions=inactive_sessions,
            available_apps=available_apps
        )
        
    except Exception as e:
        current_app.logger.error(f"Error in GUI index: {e}")
        flash('Error loading GUI sessions', 'danger')
        return redirect(url_for('core.dashboard'))

@gui_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_session():
    """Create a new GUI session"""
    if request.method == 'POST':
        try:
            # Get form data
            session_name = request.form.get('session_name', 'GUI Session')
            app_id = request.form.get('application_id', type=int)
            screen_width = request.form.get('screen_width', 1024, type=int)
            screen_height = request.form.get('screen_height', 768, type=int)
            
            # Get application
            app = GUIApplication.query.get_or_404(app_id)
            
            if not app.enabled or not app.installed:
                flash('Application is not available', 'danger')
                return redirect(url_for('gui.new_session'))
            
            # Create GUI session in database
            gui_session = GUISession(
                name=session_name,
                user_id=current_user.id,
                application_name=app.name,
                application_command=app.command,
                screen_width=screen_width,
                screen_height=screen_height
            )
            
            db.session.add(gui_session)
            db.session.commit()
            
            # Start the actual session
            session_info, error = GUISessionManager.create_session(
                gui_session.session_id,
                app.command,
                screen_width,
                screen_height
            )
            
            if session_info:
                # Update database with session details
                gui_session.display_number = session_info['display_number']
                gui_session.vnc_port = session_info['vnc_port']
                gui_session.pid = session_info['app_process'].pid if session_info.get('app_process') else None
                
                db.session.commit()
                
                # Update application usage stats
                app.increment_launch_count()
                
                # Start WebRTC bridge
                webrtc_handler.start_vnc_to_webrtc_bridge(gui_session.session_id)
                
                flash(f'GUI session "{session_name}" created successfully', 'success')
                return redirect(url_for('gui.view_session', session_id=gui_session.session_id))
            else:
                # Clean up database entry if session creation failed
                db.session.delete(gui_session)
                db.session.commit()
                
                flash(f'Failed to create GUI session: {error}', 'danger')
                return redirect(url_for('gui.new_session'))
                
        except Exception as e:
            current_app.logger.error(f"Error creating GUI session: {e}")
            current_app.logger.error(traceback.format_exc())
            flash('Error creating GUI session', 'danger')
            return redirect(url_for('gui.new_session'))
    
    # GET request - show form
    try:
        # Get available applications
        applications = GUIApplication.query.filter_by(
            enabled=True,
            installed=True
        ).order_by(GUIApplication.category, GUIApplication.name).all()
        
        # Group by category
        apps_by_category = {}
        for app in applications:
            category = app.category
            if category not in apps_by_category:
                apps_by_category[category] = []
            apps_by_category[category].append(app)
        
        return render_template(
            'gui/new.html',
            title='New GUI Session',
            apps_by_category=apps_by_category,
            current_time=datetime.utcnow().strftime('%Y%m%d-%H%M%S')
        )
        
    except Exception as e:
        current_app.logger.error(f"Error loading new GUI session form: {e}")
        flash('Error loading applications', 'danger')
        return redirect(url_for('gui.index'))

@gui_bp.route('/session/<session_id>')
@login_required
def view_session(session_id):
    """View a GUI session with WebRTC viewer"""
    try:
        # Get session from database
        gui_session = GUISession.query.filter_by(
            session_id=session_id,
            user_id=current_user.id
        ).first_or_404()
        
        # Get session info from manager
        session_info = GUISessionManager.get_session_info(session_id)
        
        # Update last activity
        gui_session.update_activity()
        
        return render_template(
            'gui/viewer.html',
            title=f'GUI Session: {gui_session.name}',
            gui_session=gui_session,
            session_info=session_info,
            webrtc_config=webrtc_handler.create_peer_connection_config()
        )
        
    except Exception as e:
        current_app.logger.error(f"Error viewing GUI session: {e}")
        flash('Error loading GUI session', 'danger')
        return redirect(url_for('gui.index'))

@gui_bp.route('/session/<session_id>/close', methods=['POST'])
@login_required
def close_session(session_id):
    """Close a GUI session"""
    try:
        # Get session
        gui_session = GUISession.query.filter_by(
            session_id=session_id,
            user_id=current_user.id
        ).first_or_404()
        
        # Stop WebRTC bridge
        webrtc_handler.stop_vnc_to_webrtc_bridge(session_id)
        
        # Close session via manager
        success = GUISessionManager.close_session(session_id)
        
        if success:
            # Update database
            gui_session.active = False
            gui_session.last_activity = datetime.utcnow()
            db.session.commit()
            
            flash(f'GUI session "{gui_session.name}" closed successfully', 'success')
        else:
            flash('Error closing GUI session', 'danger')
        
        return redirect(url_for('gui.index'))
        
    except Exception as e:
        current_app.logger.error(f"Error closing GUI session: {e}")
        flash('Error closing GUI session', 'danger')
        return redirect(url_for('gui.index'))

@gui_bp.route('/session/<session_id>/delete', methods=['POST'])
@login_required
def delete_session(session_id):
    """Delete a GUI session and its logs"""
    try:
        # Get session
        gui_session = GUISession.query.filter_by(
            session_id=session_id,
            user_id=current_user.id
        ).first_or_404()
        
        # Close if still active
        if gui_session.active:
            webrtc_handler.stop_vnc_to_webrtc_bridge(session_id)
            GUISessionManager.close_session(session_id)
        
        # Delete events and signaling messages
        GUISessionEvent.query.filter_by(session_id=session_id).delete()
        WebRTCSignalingMessage.query.filter_by(session_id=session_id).delete()
        
        # Delete session
        session_name = gui_session.name
        db.session.delete(gui_session)
        db.session.commit()
        
        flash(f'GUI session "{session_name}" deleted successfully', 'success')
        return redirect(url_for('gui.index'))
        
    except Exception as e:
        current_app.logger.error(f"Error deleting GUI session: {e}")
        flash('Error deleting GUI session', 'danger')
        return redirect(url_for('gui.index'))

# WebRTC API endpoints

@gui_bp.route('/api/webrtc/<session_id>/offer', methods=['POST'])
@login_required
def webrtc_offer(session_id):
    """Handle WebRTC offer from client"""
    try:
        # Validate session ownership
        gui_session = GUISession.query.filter_by(
            session_id=session_id,
            user_id=current_user.id
        ).first()
        
        if not gui_session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404
        
        # Get offer data
        offer_data = request.json
        
        # Handle offer via WebRTC handler
        result = webrtc_handler.handle_signaling_message(
            session_id, 'offer', offer_data, 'client'
        )
        
        return jsonify(result)
        
    except Exception as e:
        current_app.logger.error(f"Error handling WebRTC offer: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@gui_bp.route('/api/webrtc/<session_id>/answer', methods=['POST'])
@login_required
def webrtc_answer(session_id):
    """Handle WebRTC answer from client"""
    try:
        # Validate session ownership
        gui_session = GUISession.query.filter_by(
            session_id=session_id,
            user_id=current_user.id
        ).first()
        
        if not gui_session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404
        
        # Get answer data
        answer_data = request.json
        
        # Handle answer via WebRTC handler
        result = webrtc_handler.handle_signaling_message(
            session_id, 'answer', answer_data, 'client'
        )
        
        return jsonify(result)
        
    except Exception as e:
        current_app.logger.error(f"Error handling WebRTC answer: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@gui_bp.route('/api/webrtc/<session_id>/ice-candidate', methods=['POST'])
@login_required
def webrtc_ice_candidate(session_id):
    """Handle ICE candidate from client"""
    try:
        # Validate session ownership
        gui_session = GUISession.query.filter_by(
            session_id=session_id,
            user_id=current_user.id
        ).first()
        
        if not gui_session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404
        
        # Get candidate data
        candidate_data = request.json
        
        # Handle ICE candidate via WebRTC handler
        result = webrtc_handler.handle_signaling_message(
            session_id, 'ice-candidate', candidate_data, 'client'
        )
        
        return jsonify(result)
        
    except Exception as e:
        current_app.logger.error(f"Error handling ICE candidate: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@gui_bp.route('/api/session/<session_id>/input', methods=['POST'])
@login_required
def send_input(session_id):
    """Send input event to GUI session"""
    try:
        # Validate session ownership
        gui_session = GUISession.query.filter_by(
            session_id=session_id,
            user_id=current_user.id
        ).first()
        
        if not gui_session or not gui_session.active:
            return jsonify({'success': False, 'error': 'Session not found or inactive'}), 404
        
        # Get input data
        input_data = request.json
        event_type = input_data.get('type')
        event_data = input_data.get('data', {})
        
        # Send input via manager
        success = GUISessionManager.send_input_event(session_id, event_type, event_data)
        
        if success:
            # Log input event
            gui_event = GUISessionEvent(
                session_id=session_id,
                event_type='user_input',
                input_type=event_type,
                coordinates_x=event_data.get('x'),
                coordinates_y=event_data.get('y'),
                key_code=event_data.get('key'),
                event_data=json.dumps(event_data),
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent', '')[:256]
            )
            
            db.session.add(gui_event)
            
            # Update session statistics
            gui_session.total_input_events += 1
            gui_session.update_activity()
            
            db.session.commit()
            
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Failed to send input'}), 500
        
    except Exception as e:
        current_app.logger.error(f"Error sending input: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@gui_bp.route('/api/session/<session_id>/stats')
@login_required
def session_stats(session_id):
    """Get session statistics"""
    try:
        # Validate session ownership
        gui_session = GUISession.query.filter_by(
            session_id=session_id,
            user_id=current_user.id
        ).first()
        
        if not gui_session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404
        
        # Get session info from manager
        session_info = GUISessionManager.get_session_info(session_id)
        
        # Get event statistics
        event_stats = db.session.query(
            GUISessionEvent.event_type,
            db.func.count(GUISessionEvent.id).label('count')
        ).filter_by(session_id=session_id).group_by(GUISessionEvent.event_type).all()
        
        stats = {
            'session': gui_session.to_dict(),
            'session_info': session_info,
            'event_statistics': [
                {'event_type': stat.event_type, 'count': stat.count}
                for stat in event_stats
            ],
            'is_active': session_id in GUISessionManager.active_gui_sessions if hasattr(GUISessionManager, 'active_gui_sessions') else False
        }
        
        return jsonify(stats)
        
    except Exception as e:
        current_app.logger.error(f"Error getting session stats: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Applications management

@gui_bp.route('/applications')
@login_required  
def applications():
    """List available GUI applications"""
    try:
        applications = GUIApplication.query.order_by(
            GUIApplication.category, GUIApplication.name
        ).all()
        
        # Group by category
        apps_by_category = {}
        for app in applications:
            category = app.category
            if category not in apps_by_category:
                apps_by_category[category] = []
            apps_by_category[category].append(app)
        
        # Get statistics
        total_apps = len(applications)
        installed_apps = len([app for app in applications if app.installed])
        enabled_apps = len([app for app in applications if app.enabled])
        
        return render_template(
            'gui/applications.html',
            title='GUI Applications',
            apps_by_category=apps_by_category,
            total_apps=total_apps,
            installed_apps=installed_apps,
            enabled_apps=enabled_apps
        )
        
    except Exception as e:
        current_app.logger.error(f"Error loading applications: {e}")
        flash('Error loading applications', 'danger')
        return redirect(url_for('gui.index'))

@gui_bp.route('/applications/scan')
@login_required
def scan_applications():
    """Scan system for available GUI applications"""
    try:
        # Define common GUI applications to scan for
        common_apps = [
            {
                'name': 'firefox',
                'display_name': 'Firefox Browser',
                'description': 'Mozilla Firefox web browser',
                'command': 'firefox',
                'icon': 'globe',
                'category': 'Internet'
            },
            {
                'name': 'chromium',
                'display_name': 'Chromium Browser',
                'description': 'Chromium web browser',
                'command': 'chromium-browser',
                'icon': 'browser-chrome',
                'category': 'Internet'
            },
            {
                'name': 'gedit',
                'display_name': 'Text Editor',
                'description': 'GNOME text editor',
                'command': 'gedit',
                'icon': 'file-text',
                'category': 'Editors'
            },
            {
                'name': 'nautilus',
                'display_name': 'File Manager',
                'description': 'GNOME file manager',
                'command': 'nautilus',
                'icon': 'folder',
                'category': 'System'
            },
            {
                'name': 'gimp',
                'display_name': 'GIMP',
                'description': 'GNU Image Manipulation Program',
                'command': 'gimp',
                'icon': 'image',
                'category': 'Graphics'
            },
            {
                'name': 'libreoffice',
                'display_name': 'LibreOffice',
                'description': 'LibreOffice office suite',
                'command': 'libreoffice',
                'icon': 'file-earmark-text',
                'category': 'Office'
            },
            {
                'name': 'wireshark',
                'display_name': 'Wireshark',
                'description': 'Network protocol analyzer',
                'command': 'wireshark',
                'icon': 'broadcast',
                'category': 'Security'
            },
            {
                'name': 'burpsuite',
                'display_name': 'Burp Suite',
                'description': 'Web security testing platform',
                'command': 'burpsuite',
                'icon': 'shield-check',
                'category': 'Security'
            }
        ]
        
        added_count = 0
        updated_count = 0
        
        for app_info in common_apps:
            # Check if app already exists
            existing_app = GUIApplication.query.filter_by(name=app_info['name']).first()
            
            if existing_app:
                # Update existing app
                existing_app.display_name = app_info['display_name']
                existing_app.description = app_info['description']
                existing_app.command = app_info['command']
                existing_app.icon = app_info['icon']
                existing_app.category = app_info['category']
                existing_app.check_installed()
                updated_count += 1
            else:
                # Create new app
                new_app = GUIApplication(
                    name=app_info['name'],
                    display_name=app_info['display_name'],
                    description=app_info['description'],
                    command=app_info['command'],
                    icon=app_info['icon'],
                    category=app_info['category']
                )
                new_app.check_installed()
                db.session.add(new_app)
                added_count += 1
        
        db.session.commit()
        
        flash(f'Application scan completed: {added_count} added, {updated_count} updated', 'success')
        return redirect(url_for('gui.applications'))
        
    except Exception as e:
        current_app.logger.error(f"Error scanning applications: {e}")
        flash('Error scanning applications', 'danger')
        return redirect(url_for('gui.applications'))

# Socket.IO handlers for GUI sessions

@socketio.on('gui_connect')
def handle_gui_connect(data):
    """Handle client connection to GUI session"""
    try:
        session_id = data.get('session_id')
        
        if not current_user.is_authenticated:
            emit('gui_error', {'error': 'Not authenticated'})
            return
        
        # Validate session ownership
        gui_session = GUISession.query.filter_by(
            session_id=session_id,
            user_id=current_user.id
        ).first()
        
        if not gui_session:
            emit('gui_error', {'error': 'Session not found'})
            return
        
        # Join session room
        join_room(session_id)
        
        # Update activity
        gui_session.update_activity()
        
        # Send connection confirmation
        emit('gui_connected', {
            'session_id': session_id,
            'screen_resolution': {
                'width': gui_session.screen_width,
                'height': gui_session.screen_height
            },
            'webrtc_config': webrtc_handler.create_peer_connection_config()
        })
        
        current_app.logger.info(f"Client connected to GUI session {session_id}")
        
    except Exception as e:
        current_app.logger.error(f"Error in GUI connect: {e}")
        emit('gui_error', {'error': 'Connection failed'})

@socketio.on('gui_input')
def handle_gui_input(data):
    """Handle input events from GUI client"""
    try:
        session_id = data.get('session_id')
        event_type = data.get('type')
        event_data = data.get('data', {})
        
        if not current_user.is_authenticated:
            return
        
        # Validate session
        gui_session = GUISession.query.filter_by(
            session_id=session_id,
            user_id=current_user.id
        ).first()
        
        if not gui_session or not gui_session.active:
            return
        
        # Send input event
        success = GUISessionManager.send_input_event(session_id, event_type, event_data)
        
        if success:
            # Log event
            gui_event = GUISessionEvent(
                session_id=session_id,
                event_type='user_input',
                input_type=event_type,
                coordinates_x=event_data.get('x'),
                coordinates_y=event_data.get('y'),
                key_code=event_data.get('key'),
                event_data=json.dumps(event_data),
                ip_address=request.remote_addr if request else None
            )
            
            db.session.add(gui_event)
            gui_session.total_input_events += 1
            gui_session.update_activity()
            db.session.commit()
        
    except Exception as e:
        current_app.logger.error(f"Error handling GUI input: {e}")

@socketio.on('gui_webrtc_offer')
def handle_webrtc_offer(data):
    """Handle WebRTC offer via Socket.IO"""
    try:
        session_id = data.get('session_id')
        offer_data = data.get('offer')
        
        if not current_user.is_authenticated:
            return
        
        # Handle offer
        result = webrtc_handler.handle_signaling_message(
            session_id, 'offer', offer_data, 'client'
        )
        
        # Emit result back to client
        emit('gui_webrtc_offer_result', result)
        
    except Exception as e:
        current_app.logger.error(f"Error handling WebRTC offer: {e}")
        emit('gui_webrtc_offer_result', {'success': False, 'error': str(e)})

@socketio.on('gui_webrtc_answer')
def handle_webrtc_answer(data):
    """Handle WebRTC answer via Socket.IO"""
    try:
        session_id = data.get('session_id')
        answer_data = data.get('answer')
        
        if not current_user.is_authenticated:
            return
        
        # Handle answer
        result = webrtc_handler.handle_signaling_message(
            session_id, 'answer', answer_data, 'client'
        )
        
        # Emit result back to client
        emit('gui_webrtc_answer_result', result)
        
    except Exception as e:
        current_app.logger.error(f"Error handling WebRTC answer: {e}")
        emit('gui_webrtc_answer_result', {'success': False, 'error': str(e)})

@socketio.on('gui_webrtc_ice_candidate')
def handle_webrtc_ice_candidate(data):
    """Handle WebRTC ICE candidate via Socket.IO"""
    try:
        session_id = data.get('session_id')
        candidate_data = data.get('candidate')
        
        if not current_user.is_authenticated:
            return
        
        # Handle ICE candidate
        result = webrtc_handler.handle_signaling_message(
            session_id, 'ice-candidate', candidate_data, 'client'
        )
        
        # Forward to other clients in the room
        emit('gui_webrtc_ice_candidate', candidate_data, room=session_id, include_self=False)
        
    except Exception as e:
        current_app.logger.error(f"Error handling WebRTC ICE candidate: {e}")

@socketio.on('gui_disconnect')
def handle_gui_disconnect(data):
    """Handle client disconnection from GUI session"""
    try:
        session_id = data.get('session_id')
        
        if session_id:
            leave_room(session_id)
            current_app.logger.info(f"Client disconnected from GUI session {session_id}")
        
    except Exception as e:
        current_app.logger.error(f"Error in GUI disconnect: {e}")