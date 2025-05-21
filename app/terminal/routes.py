# app/terminal/routes.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.terminal.models import TerminalSession, TerminalLog
from app.terminal.manager import TerminalManager
from datetime import datetime
import os
import shutil
from app.modules.executor import ModuleExecutor


terminal_bp = Blueprint('terminal', __name__, url_prefix='/terminal')

@terminal_bp.route('/')
@login_required
def index():
    # Check if tmux is installed
    tmux_installed = shutil.which('tmux') is not None
    
    # Get all terminal sessions for the current user
    sessions = TerminalSession.query.filter_by(user_id=current_user.id).order_by(TerminalSession.last_activity.desc()).all()
    return render_template(
        'terminal/index.html', 
        title='Terminal Sessions', 
        sessions=sessions,
        tmux_installed=tmux_installed
    )

@terminal_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    if request.method == 'POST':
        try:
            session_name = request.form.get('session_name', f"Terminal-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}")
            session_type = request.form.get('session_type', 'terminal')
            module_name = request.form.get('module_name') if session_type != 'terminal' else None
            
            # Create new terminal session
            session = TerminalSession(
                name=session_name,
                user_id=current_user.id,
                module_name=module_name,
                session_type=session_type
            )
            db.session.add(session)
            db.session.commit()
            
            # If this is a module session, prepare to execute the module
            if module_name and session_type in ['guided', 'direct']:
                # First redirect to view the terminal
                flash(f'Terminal session "{session_name}" created. Launching module {module_name}...', 'success')
                return redirect(url_for('terminal.view', session_id=session.session_id, 
                                        execute_module=module_name, mode=session_type))
            else:
                # Regular terminal session
                flash(f'Terminal session "{session_name}" created successfully.', 'success')
                return redirect(url_for('terminal.view', session_id=session.session_id))
            
        except Exception as e:
            current_app.logger.error(f"Error creating terminal session: {str(e)}")
            flash(f'An unexpected error occurred: {str(e)}', 'danger')
            return redirect(url_for('terminal.index'))
    
    # GET request handling - same as before
    module_name = request.args.get('module', None)
    mode = request.args.get('mode', 'guided')  # Default to guided mode
    session_type = mode if module_name else 'terminal'
    
    # Get available modules for guided/direct mode
    from app.modules.models import Module
    modules = Module.query.filter_by(installed=True).all()
    
    # Generate current time string
    current_time = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
    
    # Generate session name
    if module_name:
        session_name = f"{module_name}-{mode}-{current_time}"
    else:
        session_name = f"Terminal-{current_time}"
    
    return render_template(
        'terminal/new.html', 
        title='New Terminal', 
        modules=modules, 
        current_time=current_time,
        selected_module=module_name,
        session_type=session_type,
        session_name=session_name
    )

@terminal_bp.route('/<session_id>')
@login_required
def view(session_id):
    session = TerminalSession.query.filter_by(session_id=session_id, user_id=current_user.id).first_or_404()
    
    # Update session last activity time
    session.last_activity = datetime.utcnow()
    db.session.commit()
    
    # Check if we need to execute a module
    execute_module = request.args.get('execute_module')
    mode = request.args.get('mode', 'guided')
    
    # We'll pass this to the template to trigger module execution after terminal initialization
    module_to_execute = None
    
    if execute_module and session.active:
        # Prepare module execution data to be used by JavaScript
        module_to_execute = {
            'name': execute_module,
            'mode': mode,
            'session_id': session_id
        }
    
    return render_template(
        'terminal/view.html', 
        title=f'Terminal: {session.name}',
        session=session,
        module_to_execute=module_to_execute
    )

@terminal_bp.route('/<session_id>/execute_module', methods=['POST'])
@login_required
def execute_module(session_id):
    session = TerminalSession.query.filter_by(session_id=session_id, user_id=current_user.id).first_or_404()
    
    if not session.active:
        return jsonify({
            'success': False,
            'message': 'Session is not active'
        }), 400
    
    # Get module information from request
    data = request.json
    module_name = data.get('module_name')
    mode = data.get('mode', 'guided')
    
    if not module_name:
        return jsonify({
            'success': False,
            'message': 'No module specified'
        }), 400
    
    # Execute the module
    success, message = ModuleExecutor.execute_module(module_name, mode, session_id)
    
    return jsonify({
        'success': success,
        'message': message
    })
    
@terminal_bp.route('/<session_id>/close', methods=['POST'])
@login_required
def close(session_id):
    session = TerminalSession.query.filter_by(session_id=session_id, user_id=current_user.id).first_or_404()
    
    # Close the terminal session
    TerminalManager.close_session(session_id)
    
    # Update session status in database
    session.active = False
    session.last_activity = datetime.utcnow()
    db.session.commit()
    
    flash(f'Terminal session "{session.name}" has been closed', 'success')
    return redirect(url_for('terminal.index'))

@terminal_bp.route('/<session_id>/delete', methods=['POST'])
@login_required
def delete(session_id):
    session = TerminalSession.query.filter_by(session_id=session_id, user_id=current_user.id).first_or_404()
    
    # First make sure it's closed
    if session.active:
        TerminalManager.close_session(session_id)
    
    # Delete logs
    TerminalLog.query.filter_by(session_id=session.session_id).delete()
    
    # Save name for flash message
    session_name = session.name
    
    # Delete session
    db.session.delete(session)
    db.session.commit()
    
    flash(f'Terminal session "{session_name}" has been deleted', 'success')
    return redirect(url_for('terminal.index'))

@terminal_bp.route('/<session_id>/logs')
@login_required
def view_logs(session_id):
    """View logs for a session (for debugging)"""
    session = TerminalSession.query.filter_by(session_id=session_id, user_id=current_user.id).first_or_404()
    
    # Get logs
    logs = TerminalLog.query.filter_by(
        session_id=session.session_id
    ).order_by(TerminalLog.timestamp).all()
    
    # Format for display
    formatted_logs = []
    for log in logs:
        formatted_logs.append({
            'id': log.id,
            'timestamp': log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'event_type': log.event_type,
            'command': log.command,
            'output': log.output[:100] + '...' if log.output and len(log.output) > 100 else log.output
        })
    
    return jsonify({
        'session_id': session_id,
        'session_name': session.name,
        'active': session.active,
        'log_count': len(logs),
        'logs': formatted_logs
    })

@terminal_bp.route('/<session_id>/execute', methods=['POST'])
@login_required
def execute_command(session_id):
    """API endpoint to execute a command in the terminal"""
    session = TerminalSession.query.filter_by(session_id=session_id, user_id=current_user.id).first_or_404()
    
    if not session.active:
        return jsonify({
            'success': False,
            'message': 'Session is not active'
        }), 400
    
    # Get command from request
    command = request.json.get('command', '')
    background = request.json.get('background', False)
    
    if not command:
        return jsonify({
            'success': False,
            'message': 'No command provided'
        }), 400
    
    # Execute command
    success, message = TerminalManager.execute_command(session_id, command, background)
    
    return jsonify({
        'success': success,
        'message': message
    })