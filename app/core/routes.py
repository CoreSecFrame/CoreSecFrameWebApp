# app/core/routes.py
from flask import Blueprint, render_template
from flask_login import login_required, current_user

core_bp = Blueprint('core', __name__)

@core_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('core.dashboard'))
    return render_template('index.html', title='Welcome')

@core_bp.route('/dashboard')
@login_required
def dashboard():
    system_info = get_system_info()
    modules_info = get_modules_info()
    sessions_info = get_sessions_info()
    return render_template(
        'core/dashboard.html', 
        title='Dashboard',
        system_info=system_info,
        modules_info=modules_info,
        sessions_info=sessions_info
    )

# Utility functions to gather info for the dashboard
def get_system_info():
    # Get system information (CPU, memory, disk usage)
    import psutil
    return {
        'cpu_percent': psutil.cpu_percent(),
        'memory_percent': psutil.virtual_memory().percent,
        'disk_percent': psutil.disk_usage('/').percent,
        'hostname': platform.node(),
        'platform': platform.system(),
        'python_version': platform.python_version()
    }

def get_modules_info():
    # Get modules information from the framework
    # This will need to be adapted to use your current module system
    return {
        'total': 0,
        'installed': 0,
        'available': 0,
        'categories': []
    }

def get_sessions_info():
    # Get sessions information
    # This will need to be adapted to use your current session system
    return {
        'total': 0,
        'active': 0,
        'inactive': 0,
        'recent': []
    }