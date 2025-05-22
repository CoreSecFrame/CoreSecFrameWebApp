# app/sessions/routes.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.terminal.models import TerminalSession, TerminalLog
from datetime import datetime
import subprocess
import traceback

sessions_bp = Blueprint('sessions', __name__, url_prefix='/sessions')

@sessions_bp.route('/')
@login_required
def index():
    # Get all sessions for the current user
    active_sessions = TerminalSession.query.filter_by(
        user_id=current_user.id, 
        active=True
    ).order_by(TerminalSession.last_activity.desc()).all()
    
    inactive_sessions = TerminalSession.query.filter_by(
        user_id=current_user.id, 
        active=False
    ).order_by(TerminalSession.last_activity.desc()).all()
    
    return render_template(
        'sessions/index.html',
        title='Sessions',
        active_sessions=active_sessions,
        inactive_sessions=inactive_sessions
    )

@sessions_bp.route('/<session_id>')
@login_required
def view(session_id):
    # Get session
    session = TerminalSession.query.filter_by(
        session_id=session_id,
        user_id=current_user.id
    ).first_or_404()
    
    # Get session logs
    logs = TerminalLog.query.filter_by(
        session_id=session.session_id
    ).order_by(TerminalLog.timestamp).all()
    
    return render_template(
        'sessions/view.html',
        title=f'Session: {session.name}',
        session=session,
        logs=logs
    )

@sessions_bp.route('/<session_id>/logs')
@login_required
def get_logs(session_id):
    # Get session
    session = TerminalSession.query.filter_by(
        session_id=session_id,
        user_id=current_user.id
    ).first_or_404()
    
    # Get session logs
    logs = TerminalLog.query.filter_by(
        session_id=session.session_id
    ).order_by(TerminalLog.timestamp).all()
    
    # Format logs for JSON response
    logs_data = [{
        'id': log.id,
        'timestamp': log.timestamp.isoformat(),
        'event_type': log.event_type,
        'command': log.command,
        'output': log.output
    } for log in logs]
    
    return jsonify({
        'session': {
            'id': session.id,
            'name': session.name,
            'session_id': session.session_id,
            'active': session.active,
            'session_type': session.session_type,
            'start_time': session.start_time.isoformat(),
            'last_activity': session.last_activity.isoformat(),
            'duration': session.get_duration()
        },
        'logs': logs_data
    })

@sessions_bp.route('/<session_id>/close', methods=['POST'])
@login_required
def close(session_id):
    try:
        # Get session
        session = TerminalSession.query.filter_by(
            session_id=session_id,
            user_id=current_user.id
        ).first_or_404()
        
        # Kill the tmux session if active
        if session.active:
            try:
                subprocess.run(['tmux', 'kill-session', '-t', session.session_id], check=True)
            except:
                pass  # Ignore errors if session already dead
        
        # Update session status
        session.active = False
        session.last_activity = datetime.utcnow()
        db.session.commit()
        
        # Log the session close
        log = TerminalLog(
            session_id=session.session_id,
            event_type='system',
            command=None,
            output=f"Session closed: {session.name}"
        )
        db.session.add(log)
        db.session.commit()
        
        flash(f'Session "{session.name}" has been closed', 'success')
    except Exception as e:
        current_app.logger.error(f"Error closing session: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        flash(f'Error closing session: {str(e)}', 'danger')
    
    return redirect(url_for('sessions.index'))

@sessions_bp.route('/<session_id>/delete', methods=['POST'])
@login_required
def delete(session_id):
    try:
        # Get session
        session = TerminalSession.query.filter_by(
            session_id=session_id,
            user_id=current_user.id
        ).first_or_404()
        
        # First make sure the session is closed
        if session.active:
            try:
                subprocess.run(['tmux', 'kill-session', '-t', session.session_id], check=True)
            except:
                pass  # Ignore errors if session already dead
        
        # Store session name for flash message
        session_name = session.name
        
        # Delete logs
        TerminalLog.query.filter_by(session_id=session.session_id).delete()
        
        # Delete session
        db.session.delete(session)
        db.session.commit()
        
        flash(f'Session "{session_name}" has been deleted', 'success')
    except Exception as e:
        current_app.logger.error(f"Error deleting session: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        flash(f'Error deleting session: {str(e)}', 'danger')
        db.session.rollback()  # Rollback in case of error
    
    return redirect(url_for('sessions.index'))