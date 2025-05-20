# app/terminal/routes.py (continued)
from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import login_required, current_user
from app import db, socketio
from app.terminal.models import TerminalSession, TerminalLog
from app.terminal.utils import create_terminal_process, get_process_details
import subprocess
import os
import json
from datetime import datetime

terminal_bp = Blueprint('terminal', __name__, url_prefix='/terminal')

@terminal_bp.route('/')
@login_required
def index():
   # Get all terminal sessions for the current user
   sessions = TerminalSession.query.filter_by(user_id=current_user.id).order_by(TerminalSession.last_activity.desc()).all()
   return render_template('terminal/index.html', title='Terminal Sessions', sessions=sessions)

@terminal_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
   if request.method == 'POST':
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
       
       # Create terminal process
       success = create_terminal_process(session)
       if not success:
           flash('Failed to create terminal process', 'danger')
           db.session.delete(session)
           db.session.commit()
           return redirect(url_for('terminal.index'))
       
       # Log the session creation
       log = TerminalLog(
           session_id=session.session_id,
           event_type='system',
           command=None,
           output=f"Session created: {session_name} ({session_type})"
       )
       db.session.add(log)
       db.session.commit()
       
       return redirect(url_for('terminal.view', session_id=session.session_id))
   
   # Get available modules for guided/direct mode
   modules = []  # You'll need to adapt this to get modules from your system
   return render_template('terminal/new.html', title='New Terminal', modules=modules)

@terminal_bp.route('/<session_id>')
@login_required
def view(session_id):
   session = TerminalSession.query.filter_by(session_id=session_id, user_id=current_user.id).first_or_404()
   
   # Check if terminal process is still running
   if session.active:
       proc_info = get_process_details(session)
       if not proc_info['running']:
           session.active = False
           db.session.commit()
   
   # Get terminal logs
   logs = TerminalLog.query.filter_by(session_id=session.session_id).order_by(TerminalLog.timestamp).all()
   
   return render_template(
       'terminal/view.html', 
       title=f'Terminal: {session.name}',
       session=session,
       logs=logs
   )

@terminal_bp.route('/<session_id>/close', methods=['POST'])
@login_required
def close(session_id):
   session = TerminalSession.query.filter_by(session_id=session_id, user_id=current_user.id).first_or_404()
   
   # Kill the tmux session
   try:
       if session.active:
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
   
   flash(f'Terminal session "{session.name}" has been closed', 'success')
   return redirect(url_for('terminal.index'))

@terminal_bp.route('/<session_id>/delete', methods=['POST'])
@login_required
def delete(session_id):
   session = TerminalSession.query.filter_by(session_id=session_id, user_id=current_user.id).first_or_404()
   
   # First make sure it's closed
   try:
       if session.active:
           subprocess.run(['tmux', 'kill-session', '-t', session.session_id], check=True)
   except:
       pass
   
   # Delete logs
   TerminalLog.query.filter_by(session_id=session.session_id).delete()
   
   # Delete session
   db.session.delete(session)
   db.session.commit()
   
   flash(f'Terminal session "{session.name}" has been deleted', 'success')
   return redirect(url_for('terminal.index'))

# API endpoint for getting terminal data
@terminal_bp.route('/<session_id>/data')
@login_required
def get_data(session_id):
   session = TerminalSession.query.filter_by(session_id=session_id, user_id=current_user.id).first_or_404()
   logs = TerminalLog.query.filter_by(session_id=session.session_id).order_by(TerminalLog.timestamp).all()
   
   return jsonify({
       'session': session.to_dict(),
       'logs': [{
           'id': log.id,
           'timestamp': log.timestamp.isoformat(),
           'command': log.command,
           'output': log.output,
           'event_type': log.event_type
       } for log in logs]
   })