# app/admin/routes.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from app import db
from app.auth.models import User
from app.auth.forms import RegistrationForm
from app.admin.forms import UserForm
from app.terminal.models import TerminalSession
from app.modules.models import Module
import os
import psutil
from datetime import datetime

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/')
@login_required
def index():
    if not current_user.is_admin():
        flash('You do not have permission to access the admin panel.', 'danger')
        return redirect(url_for('core.index'))
    
    # Get user data
    users = User.query.all()
    
    # Get system info for quick display
    system_info = {
        'cpu_percent': psutil.cpu_percent(),
        'memory_percent': psutil.virtual_memory().percent,
        'disk_percent': psutil.disk_usage('/').percent,
    }
    
    # Get application stats
    active_sessions = TerminalSession.query.filter_by(active=True).count()
    installed_modules = Module.query.filter_by(installed=True).count()
    
    # Get recent logs (simplified - in a real app, we'd have a proper logging system)
    recent_logs = get_recent_logs(10)
    
    return render_template(
        'admin/index.html', 
        title='Admin Panel', 
        users=users,
        system_info=system_info,
        active_sessions=active_sessions,
        installed_modules=installed_modules,
        recent_logs=recent_logs
    )

@admin_bp.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    if not current_user.is_admin():
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('core.index'))
    
    user = User.query.get_or_404(user_id)
    form = UserForm(obj=user)
    
    if form.validate_on_submit():
        # Update user with form data
        user.username = form.username.data
        user.email = form.email.data
        user.role = form.role.data
        
        # Update password if provided
        if form.password.data:
            user.set_password(form.password.data)
        
        db.session.commit()
        flash(f'User {user.username} has been updated successfully.', 'success')
        return redirect(url_for('admin.index'))
    
    return render_template('admin/edit_user.html', title='Edit User', form=form, user=user)

@admin_bp.route('/create_user', methods=['GET', 'POST'])
@login_required
def create_user():
    if not current_user.is_admin():
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('core.index'))
    
    form = UserForm()
    
    if form.validate_on_submit():
        # Create new user
        user = User(
            username=form.username.data,
            email=form.email.data,
            role=form.role.data,
            created_at=datetime.utcnow()
        )
        
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        
        flash(f'User {user.username} has been created successfully.', 'success')
        return redirect(url_for('admin.index'))
    
    return render_template('admin/edit_user.html', title='Create User', form=form, user=None)

@admin_bp.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if not current_user.is_admin():
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('core.index'))
    
    # Prevent self-deletion
    if user_id == current_user.id:
        flash('You cannot delete your own account.', 'danger')
        return redirect(url_for('admin.index'))
    
    user = User.query.get_or_404(user_id)
    
    # Delete all user's sessions
    from app.terminal.models import TerminalSession
    sessions = TerminalSession.query.filter_by(user_id=user.id).all()
    for session in sessions:
        # Delete session logs
        from app.terminal.models import TerminalLog
        TerminalLog.query.filter_by(session_id=session.session_id).delete()
        db.session.delete(session)
    
    # Store username for flash message
    username = user.username
    
    # Delete user
    db.session.delete(user)
    db.session.commit()
    
    flash(f'User {username} has been deleted.', 'success')
    return redirect(url_for('admin.index'))

@admin_bp.route('/system_logs')
@login_required
def system_logs():
    if not current_user.is_admin():
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('core.index'))
    
    # Get all logs (in a real app, we'd use a real logging system)
    logs = get_all_logs()
    
    return render_template('admin/logs.html', title='System Logs', logs=logs)

def get_recent_logs(limit=10):
    """Helper function to get recent logs (simplified implementation)"""
    logs_dir = current_app.config['LOGS_DIR']
    logs = []
    
    # In a real app, we'd use a proper logging system
    # This is just a placeholder implementation
    try:
        log_levels = {
            'ERROR': 'danger',
            'WARNING': 'warning',
            'INFO': 'info',
            'DEBUG': 'secondary'
        }
        
        # Generate some sample logs for display
        for i in range(min(limit, 10)):
            if i % 3 == 0:
                level = 'INFO'
            elif i % 3 == 1:
                level = 'WARNING'
            else:
                level = 'ERROR'
                
            logs.append({
                'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                'level': level,
                'level_class': log_levels.get(level, 'secondary'),
                'message': f'Sample log message #{i+1}'
            })
    except Exception as e:
        current_app.logger.error(f"Error reading logs: {e}")
    
    return logs

def get_all_logs():
    """Helper function to get all logs (simplified implementation)"""
    # In a real app, we'd have a proper logging system
    return get_recent_logs(30)  # Return 30 sample logs