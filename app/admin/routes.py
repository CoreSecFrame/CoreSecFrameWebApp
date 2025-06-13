# app/admin/routes.py - Enhanced Version
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from app import db
from app.auth.models import User
from app.auth.forms import RegistrationForm
from app.admin.forms import UserForm, LogSearchForm
from app.terminal.models import TerminalSession
from app.modules.models import Module
from app.core.models import SystemLog, LogSearchQuery
from app.core.logging import log_user_action, log_security_event
import os
import psutil
from datetime import datetime, timedelta
from sqlalchemy import desc, func
from app.utils import admin_required, json_success, json_error # Import helpers

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/')
@login_required
@admin_required
def index():
    # Admin check is now handled by @admin_required decorator
    log_user_action(
        current_user.id, 
        'admin_panel_access', 
        'Accessed admin dashboard',
        ip_address=request.remote_addr
    )
    
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
    
    # Get real log statistics
    log_stats = get_log_statistics()
    recent_logs = SystemLog.get_recent_logs(limit=10)
    
    return render_template(
        'admin/index.html', 
        title='Admin Panel', 
        users=users,
        system_info=system_info,
        active_sessions=active_sessions,
        installed_modules=installed_modules,
        log_stats=log_stats,
        recent_logs=recent_logs
    )

@admin_bp.route('/logs')
@login_required
@admin_required
def system_logs():
    # Admin check is now handled by @admin_required decorator
    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    # Build base query using the helper
    base_query = _build_log_query(request.args)
    
    # Order by timestamp (newest first)
    ordered_query = base_query.order_by(desc(SystemLog.timestamp))
    
    # Paginate
    logs_pagination = ordered_query.paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Get filter options for dropdowns
    filter_options = get_log_filter_options()
    
    # Get summary statistics for current filters
    summary_stats = get_filtered_log_stats(request.args) # Pass request.args
    
    log_user_action(
        current_user.id,
        'view_system_logs',
        f'Viewed system logs page {page} with filters: {request.args.to_dict()}', # Log all filters
        ip_address=request.remote_addr
    )
    
    return render_template(
        'admin/logs.html',
        title='System Logs',
        logs_pagination=logs_pagination,
        filter_options=filter_options,
        summary_stats=summary_stats,
        current_filters=request.args.to_dict() # Pass all filters to template
    )

@admin_bp.route('/logs/export')
@login_required
@admin_required
def export_logs():
    """Export system logs as CSV or JSON"""
    # Admin check is now handled by @admin_required decorator
    # Get export parameters
    format_type = request.args.get('format', 'csv')
    # limit will be applied after building the base query
    limit = request.args.get('limit', 1000, type=int)

    # Build base query using the helper
    base_query = _build_log_query(request.args)
    
    # Apply ordering and limit
    ordered_query = base_query.order_by(desc(SystemLog.timestamp))
    logs = ordered_query.limit(limit).all()
    
    log_user_action(
        current_user.id,
        'export_system_logs',
        f'Exported {len(logs)} system logs in {format_type} format',
        ip_address=request.remote_addr
    )
    
    if format_type == 'json':
        from flask import Response
        import json
        
        logs_data = [log.to_dict() for log in logs]
        
        response = Response(
            json.dumps(logs_data, indent=2, default=str),
            mimetype='application/json',
            headers={
                'Content-Disposition': f'attachment; filename=system_logs_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.json'
            }
        )
        
        return response
    
    else:  # CSV format
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'Timestamp', 'Level', 'Module', 'Function', 'Line', 
            'Message', 'User ID', 'Session ID', 'IP Address', 
            'Security Event', 'Exception'
        ])
        
        # Write data
        for log in logs:
            writer.writerow([
                log.get_formatted_timestamp(),
                log.level,
                log.module or '',
                log.function or '',
                log.line_number or '',
                log.message,
                log.user_id or '',
                log.session_id or '',
                log.ip_address or '',
                'Yes' if log.is_security_event else 'No',
                log.exception_text or ''
            ])
        
        output.seek(0)
        
        from flask import Response
        response = Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename=system_logs_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.csv'
            }
        )
        
        return response

@admin_bp.route('/logs/cleanup', methods=['POST'])
@login_required
@admin_required
def cleanup_logs():
    """Clean up old system logs"""
    # Admin check is now handled by @admin_required decorator
    days_to_keep = request.form.get('days_to_keep', 30, type=int)
    
    try:
        deleted_count = SystemLog.cleanup_old_logs(days_to_keep)
        
        log_user_action(
            current_user.id,
            'cleanup_system_logs',
            f'Cleaned up {deleted_count} old log entries (kept logs from last {days_to_keep} days)',
            ip_address=request.remote_addr
        )
        
        flash(f'Successfully cleaned up {deleted_count} old log entries.', 'success')
        
    except Exception as e:
        current_app.logger.error(f"Error cleaning up logs: {e}")
        flash(f'Error cleaning up logs: {str(e)}', 'danger')
    
    return redirect(url_for('admin.system_logs'))

@admin_bp.route('/logs/api')
@login_required
@admin_required
def logs_api():
    """API endpoint for real-time log data"""
    # Admin check is now handled by @admin_required decorator
    # For API endpoints, the decorator's redirect might not be ideal.
    # However, for this task, we'll use the standard decorator.
    # A future enhancement could be an API-specific admin_required decorator.
    # Get parameters
    limit = request.args.get('limit', 20, type=int)
    level = request.args.get('level', '')
    since_id = request.args.get('since_id', 0, type=int)
    
    # Build query
    query = SystemLog.query.order_by(desc(SystemLog.timestamp))
    
    if since_id:
        query = query.filter(SystemLog.id > since_id)
    
    if level:
        query = query.filter(SystemLog.level == level)
    
    logs = query.limit(limit).all()
    
    data = {
        'logs': [log.to_dict() for log in logs],
        'count': len(logs),
        'latest_id': logs[0].id if logs else since_id
    }
    return json_success(data=data)

@admin_bp.route('/logs/stats')
@login_required
@admin_required
def logs_stats():
    """Get comprehensive log statistics"""
    # Admin check is now handled by @admin_required decorator
    hours = request.args.get('hours', 24, type=int)
    
    # Get various statistics
    try:
        stats_data = {
            'total_logs': SystemLog.query.count(),
            'recent_logs': SystemLog.query.filter(
                SystemLog.timestamp >= datetime.utcnow() - timedelta(hours=hours)
            ).count(),
            'error_count_24h': SystemLog.get_error_count_last_24h(),
            'security_events_24h': SystemLog.get_security_events_count_last_24h(),
            'level_stats': SystemLog.get_log_level_stats(hours),
            'module_stats': SystemLog.get_module_stats(hours),
            'time_range_hours': hours,
            'generated_at': datetime.utcnow().isoformat()
        }
        return json_success(data=stats_data)
    except Exception as e:
        current_app.logger.error(f"Error fetching log statistics: {e}")
        return json_error(message="Failed to fetch log statistics.", details=str(e), status_code=500)

@admin_bp.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    # Admin check is now handled by @admin_required decorator
    user = User.query.get_or_404(user_id)
    form = UserForm(obj=user)
    
    if form.validate_on_submit():
        old_data = {
            'username': user.username,
            'email': user.email,
            'role': user.role
        }
        
        # Update user with form data
        user.username = form.username.data
        user.email = form.email.data
        user.role = form.role.data
        
        # Update password if provided
        if form.password.data:
            user.set_password(form.password.data)
        
        db.session.commit()
        
        # Log the user modification
        log_user_action(
            current_user.id,
            'modify_user',
            f'Modified user {user.username} (ID: {user_id}). Changes: {old_data} -> {{"username": user.username, "email": user.email, "role": user.role}}',
            ip_address=request.remote_addr
        )
        
        flash(f'User {user.username} has been updated successfully.', 'success')
        return redirect(url_for('admin.index'))
    
    return render_template('admin/edit_user.html', title='Edit User', form=form, user=user)

@admin_bp.route('/create_user', methods=['GET', 'POST'])
@login_required
@admin_required
def create_user():
    # Admin check is now handled by @admin_required decorator
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
        
        # Log the user creation
        log_user_action(
            current_user.id,
            'create_user',
            f'Created new user {user.username} (ID: {user.id}) with role {user.role}',
            ip_address=request.remote_addr
        )
        
        flash(f'User {user.username} has been created successfully.', 'success')
        return redirect(url_for('admin.index'))
    
    return render_template('admin/edit_user.html', title='Create User', form=form, user=None)

@admin_bp.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    # Admin check is now handled by @admin_required decorator
    # Prevent self-deletion
    if user_id == current_user.id:
        flash('You cannot delete your own account.', 'danger')
        return redirect(url_for('admin.index'))
    
    user = User.query.get_or_404(user_id)
    
    # Delete all user's sessions
    from app.terminal.models import TerminalSession, TerminalLog
    sessions = TerminalSession.query.filter_by(user_id=user.id).all()
    deleted_sessions = 0
    deleted_logs = 0
    
    for session in sessions:
        # Delete session logs
        session_logs = TerminalLog.query.filter_by(session_id=session.session_id).delete()
        deleted_logs += session_logs
        db.session.delete(session)
        deleted_sessions += 1
    
    # Store username for logging and flash message
    username = user.username
    
    # Delete user
    db.session.delete(user)
    db.session.commit()
    
    # Log the user deletion
    log_user_action(
        current_user.id,
        'delete_user',
        f'Deleted user {username} (ID: {user_id}) and {deleted_sessions} sessions with {deleted_logs} log entries',
        ip_address=request.remote_addr
    )
    
    flash(f'User {username} has been deleted.', 'success')
    return redirect(url_for('admin.index'))

# Helper functions

def _build_log_query(filters):
    """Helper function to construct a SystemLog query based on filters."""
    query = SystemLog.query

    level_filter = filters.get('level', '')
    module_filter = filters.get('module', '')
    search_query = filters.get('search', '')
    # Correctly handle boolean conversion for 'security_only'
    security_only_str = filters.get('security_only', 'false') # Default to 'false' string
    security_only = security_only_str.lower() == 'true' if isinstance(security_only_str, str) else bool(security_only_str)

    hours_back_str = filters.get('hours', '') # Get as string first

    if level_filter:
        query = query.filter(SystemLog.level == level_filter)

    if module_filter:
        query = query.filter(SystemLog.module.ilike(f'%{module_filter}%'))

    if search_query:
        query = query.filter(SystemLog.message.ilike(f'%{search_query}%'))

    if security_only:
        query = query.filter(SystemLog.is_security_event == True)

    if hours_back_str: # Check if hours_back_str has a value
        try:
            hours_back = int(hours_back_str)
            if hours_back > 0: # Ensure positive hours
                since = datetime.utcnow() - timedelta(hours=hours_back)
                query = query.filter(SystemLog.timestamp >= since)
        except ValueError:
            # Handle case where hours_back is not a valid integer
            current_app.logger.warning(f"Invalid value for 'hours' filter: {hours_back_str}")
            # Optionally, you could flash a message or raise an error if strict validation is needed
            pass

    return query

def get_log_statistics():
    """Get comprehensive log statistics for dashboard"""
    try:
        now = datetime.utcnow()
        last_24h = now - timedelta(hours=24)
        last_week = now - timedelta(days=7)
        
        stats = {
            'total_logs': SystemLog.query.count(),
            'logs_24h': SystemLog.query.filter(SystemLog.timestamp >= last_24h).count(),
            'logs_week': SystemLog.query.filter(SystemLog.timestamp >= last_week).count(),
            'errors_24h': SystemLog.query.filter(
                SystemLog.timestamp >= last_24h,
                SystemLog.level.in_(['ERROR', 'CRITICAL'])
            ).count(),
            'security_events_24h': SystemLog.query.filter(
                SystemLog.timestamp >= last_24h,
                SystemLog.is_security_event == True
            ).count(),
            'level_distribution': SystemLog.get_log_level_stats(24),
            'top_modules': SystemLog.get_module_stats(24, limit=5)
        }
        
        return stats
        
    except Exception as e:
        current_app.logger.error(f"Error getting log statistics: {e}")
        return {
            'total_logs': 0,
            'logs_24h': 0,
            'logs_week': 0,
            'errors_24h': 0,
            'security_events_24h': 0,
            'level_distribution': {},
            'top_modules': []
        }

def get_log_filter_options():
    """Get available filter options for log search"""
    try:
        # Get unique levels
        levels = db.session.query(SystemLog.level.distinct()).all()
        levels = [level[0] for level in levels if level[0]]
        
        # Get top modules
        modules = db.session.query(
            SystemLog.module,
            func.count(SystemLog.id).label('count')
        ).group_by(SystemLog.module).order_by(
            func.count(SystemLog.id).desc()
        ).limit(20).all()
        
        modules = [{'name': mod.module, 'count': mod.count} for mod in modules if mod.module]
        
        return {
            'levels': sorted(levels),
            'modules': modules
        }
        
    except Exception as e:
        current_app.logger.error(f"Error getting filter options: {e}")
        return {'levels': [], 'modules': []}

def get_filtered_log_stats(filters):
    """Get statistics for current filter combination using provided filters."""
    try:
        # Use the helper to build the base query
        query = _build_log_query(filters)
        
        total_filtered = query.count()
        
        # Get level distribution for filtered results
        level_stats = query.with_entities(
            SystemLog.level,
            func.count(SystemLog.id).label('count')
        ).group_by(SystemLog.level).all()
        
        level_distribution = {stat.level: stat.count for stat in level_stats}
        
        return {
            'total_filtered': total_filtered,
            'level_distribution': level_distribution,
            'has_errors': any(level in ['ERROR', 'CRITICAL'] for level in level_distribution.keys()),
            'error_count': sum(count for level, count in level_distribution.items() if level in ['ERROR', 'CRITICAL'])
        }
        
    except Exception as e:
        current_app.logger.error(f"Error getting filtered stats: {e}")
        return {
            'total_filtered': 0,
            'level_distribution': {},
            'has_errors': False,
            'error_count': 0
        }