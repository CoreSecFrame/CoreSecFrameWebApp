# app/terminal/routes.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.terminal.models import TerminalSession, TerminalLog, TerminalLogSummary
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
    
    # Get all terminal sessions for the current user with enhanced info
    sessions = TerminalSession.query.filter_by(user_id=current_user.id).order_by(TerminalSession.last_activity.desc()).all()
    
    # Update session statistics for display
    for session in sessions:
        try:
            session.update_stats()
        except Exception as e:
            current_app.logger.warning(f"Could not update stats for session {session.session_id}: {e}")
    
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
            run_via_oniux = request.form.get('run_via_oniux') == 'true'
            
            # Create new terminal session
            session = TerminalSession(
                name=session_name,
                user_id=current_user.id,
                module_name=module_name,
                session_type=session_type,
                use_oniux=run_via_oniux
            )
            db.session.add(session)
            db.session.commit()
            
            # Initialize summary
            TerminalLogSummary.update_for_session(session.session_id)
            
            # If this is a module session, prepare to execute the module
            if module_name and session_type in ['guided', 'direct']:
                flash(f'Terminal session "{session_name}" created. Launching module {module_name}...', 'success')
                return redirect(url_for('terminal.view', session_id=session.session_id, 
                                        execute_module=module_name, mode=session_type))
            else:
                flash(f'Terminal session "{session_name}" created successfully.', 'success')
                return redirect(url_for('terminal.view', session_id=session.session_id))
            
        except Exception as e:
            current_app.logger.error(f"Error creating terminal session: {str(e)}")
            flash(f'An unexpected error occurred: {str(e)}', 'danger')
            return redirect(url_for('terminal.index'))
    
    # GET request handling
    module_name = request.args.get('module', None)
    mode = request.args.get('mode', 'guided')
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
    
    # Prepare module execution data for JavaScript
    module_to_execute = None
    if execute_module and session.active:
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
    
    # Close the terminal session (this will preserve all logs)
    TerminalManager.close_session(session_id)
    
    # Update session status in database
    session.active = False
    session.last_activity = datetime.utcnow()
    
    # Update final statistics
    session.update_stats()
    TerminalLogSummary.update_for_session(session_id)
    
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
    
    # Save name for flash message
    session_name = session.name
    
    # Delete all related data
    try:
        # Delete summary
        TerminalLogSummary.query.filter_by(session_id=session.session_id).delete()
        
        # Delete logs (this is where all the session history is stored)
        deleted_logs = TerminalLog.query.filter_by(session_id=session.session_id).delete()
        
        # Delete session
        db.session.delete(session)
        db.session.commit()
        
        current_app.logger.info(f"Deleted session {session_name} with {deleted_logs} log entries")
        flash(f'Terminal session "{session_name}" and all its logs have been deleted', 'success')
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting session: {e}")
        flash(f'Error deleting session: {str(e)}', 'danger')
    
    return redirect(url_for('terminal.index'))

@terminal_bp.route('/<session_id>/logs')
@login_required
def view_logs(session_id):
    """View detailed logs for a session (for debugging and analysis)"""
    session = TerminalSession.query.filter_by(session_id=session_id, user_id=current_user.id).first_or_404()
    
    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    event_type = request.args.get('event_type', '')
    
    # Build query
    query = TerminalLog.query.filter_by(session_id=session.session_id)
    
    if event_type:
        query = query.filter_by(event_type=event_type)
    
    # Get paginated logs
    logs_pagination = query.order_by(TerminalLog.timestamp.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Get summary statistics
    summary = TerminalLogSummary.query.filter_by(session_id=session_id).first()
    if not summary:
        summary = TerminalLogSummary.update_for_session(session_id)
    
    # Get event type counts for filtering
    event_counts = db.session.query(
        TerminalLog.event_type,
        db.func.count(TerminalLog.id).label('count')
    ).filter_by(session_id=session_id).group_by(TerminalLog.event_type).all()
    
    return render_template(
        'terminal/logs.html',
        title=f'Logs: {session.name}',
        session=session,
        logs_pagination=logs_pagination,
        summary=summary,
        event_counts=event_counts,
        current_event_type=event_type
    )

@terminal_bp.route('/<session_id>/logs/api')
@login_required
def logs_api(session_id):
    """API endpoint for retrieving session logs"""
    session = TerminalSession.query.filter_by(session_id=session_id, user_id=current_user.id).first_or_404()
    
    # Get query parameters
    event_type = request.args.get('event_type')
    limit = request.args.get('limit', 100, type=int)
    offset = request.args.get('offset', 0, type=int)
    
    # Build query
    query = TerminalLog.query.filter_by(session_id=session.session_id)
    
    if event_type:
        query = query.filter_by(event_type=event_type)
    
    # Get logs
    logs = query.order_by(TerminalLog.timestamp.desc()).offset(offset).limit(limit).all()
    
    # Convert to JSON
    logs_data = [log.to_dict() for log in logs]
    
    return jsonify({
        'session_id': session_id,
        'session_name': session.name,
        'active': session.active,
        'total_logs': query.count(),
        'returned_logs': len(logs_data),
        'logs': logs_data
    })

@terminal_bp.route('/<session_id>/export')
@login_required
def export_session(session_id):
    """Export complete session history"""
    session = TerminalSession.query.filter_by(session_id=session_id, user_id=current_user.id).first_or_404()
    
    # Get complete session buffer
    buffer, commands = TerminalManager.get_session_logs(session_id)
    
    # Create export data
    export_data = {
        'session_info': session.to_dict(),
        'exported_at': datetime.utcnow().isoformat(),
        'complete_buffer': buffer,
        'command_history': commands,
        'export_format': 'terminal_session_v1'
    }
    
    from flask import Response
    import json
    
    # Return as downloadable JSON file
    response = Response(
        json.dumps(export_data, indent=2),
        mimetype='application/json',
        headers={
            'Content-Disposition': f'attachment; filename=terminal_session_{session_id}_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.json'
        }
    )
    
    return response

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
    
    # Update session activity
    session.last_activity = datetime.utcnow()
    db.session.commit()
    
    return jsonify({
        'success': success,
        'message': message
    })

@terminal_bp.route('/<session_id>/stats')
@login_required
def session_stats(session_id):
    """Get detailed session statistics"""
    session = TerminalSession.query.filter_by(session_id=session_id, user_id=current_user.id).first_or_404()
    
    # Update statistics
    session.update_stats()
    summary = TerminalLogSummary.update_for_session(session_id)
    
    # Get additional statistics
    event_stats = db.session.query(
        TerminalLog.event_type,
        db.func.count(TerminalLog.id).label('count'),
        db.func.sum(TerminalLog.output_size).label('total_size')
    ).filter_by(session_id=session_id).group_by(TerminalLog.event_type).all()
    
    # Get timeline data (commands over time)
    timeline_data = db.session.query(
        db.func.date(TerminalLog.timestamp).label('date'),
        db.func.count(TerminalLog.id).label('commands')
    ).filter_by(
        session_id=session_id,
        event_type='command_input'
    ).group_by(db.func.date(TerminalLog.timestamp)).all()
    
    stats_data = {
        'session': session.to_dict(),
        'summary': summary.to_dict() if summary else None,
        'event_statistics': [
            {
                'event_type': stat.event_type,
                'count': stat.count,
                'total_size': stat.total_size or 0
            }
            for stat in event_stats
        ],
        'timeline': [
            {
                'date': stat.date.isoformat(),
                'commands': stat.commands
            }
            for stat in timeline_data
        ]
    }
    
    return jsonify(stats_data)