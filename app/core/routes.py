# app/core/routes.py - Optimized version
from flask import Blueprint, render_template, redirect, url_for, current_app
from flask_login import login_required, current_user
import platform
import psutil
from app.modules.models import Module, ModuleCategory
from app import db

core_bp = Blueprint('core', __name__)

@core_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('core.dashboard'))
    return render_template('index.html', title='Welcome')

@core_bp.route('/dashboard')
@login_required
def dashboard():
    try:
        system_info = _get_system_info()
        modules_info = _get_modules_info()
        sessions_info = _get_sessions_info()
        gui_info = _get_gui_info()
        
        return render_template(
            'core/dashboard.html', 
            title='Dashboard',
            system_info=system_info,
            modules_info=modules_info,
            sessions_info=sessions_info,
            gui_info=gui_info
        )
    except Exception as e:
        current_app.logger.error(f"Dashboard error: {e}")
        # Return a minimal dashboard on error
        return render_template(
            'core/dashboard.html',
            title='Dashboard',
            system_info={'cpu_percent': 0, 'memory_percent': 0, 'disk_percent': 0},
            modules_info={'total': 0, 'installed': 0, 'available': 0, 'categories': []},
            sessions_info={'total': 0, 'active': 0, 'inactive': 0, 'recent': []},
            gui_info={'total': 0, 'active': 0, 'inactive': 0, 'available_apps': 0, 'webrtc_sessions': 0, 'recent': []}
        )

@core_bp.route('/system-info')
@login_required
def system_info():
    """Display detailed system information"""
    try:
        # Get basic system info
        system_info = _get_system_info()
        
        # Get detailed network, disk, CPU, memory info
        network_info = _get_network_info()
        disk_info = _get_disk_info()
        cpu_info = _get_cpu_info()
        memory_info = _get_memory_info()
        swap_info = _get_swap_info()
        python_info = _get_python_info()
        os_info = _get_os_info()
        
        return render_template(
            'core/system_info.html',
            title='System Information',
            system_info=system_info,
            network_info=network_info,
            disk_info=disk_info,
            cpu_info=cpu_info,
            memory_info=memory_info,
            swap_info=swap_info,
            python_info=python_info,
            os_info=os_info
        )
    except Exception as e:
        current_app.logger.error(f"System info error: {e}")
        return render_template('errors/500.html'), 500

# Private helper functions with consistent error handling

def _get_system_info():
    """Get basic system information with error handling"""
    try:
        return {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': psutil.disk_usage('/').percent,
            'hostname': platform.node(),
            'platform': platform.system(),
            'python_version': platform.python_version()
        }
    except Exception as e:
        current_app.logger.warning(f"Error getting system info: {e}")
        return {
            'cpu_percent': 0,
            'memory_percent': 0,
            'disk_percent': 0,
            'hostname': 'Unknown',
            'platform': 'Unknown',
            'python_version': 'Unknown'
        }

def _get_modules_info():
    """Get modules information with error handling"""
    try:
        total_modules = Module.query.count()
        installed_modules = Module.query.filter_by(installed=True).count()
        
        categories = []
        for category in ModuleCategory.query.all():
            count = Module.query.filter_by(category=category.name).count()
            if count > 0:
                categories.append({'name': category.name, 'count': count})
        
        return {
            'total': total_modules,
            'installed': installed_modules,
            'available': total_modules - installed_modules,
            'categories': categories
        }
    except Exception as e:
        current_app.logger.warning(f"Error getting modules info: {e}")
        return {
            'total': 0,
            'installed': 0,
            'available': 0,
            'categories': []
        }

def _get_sessions_info():
    """Get sessions information with error handling"""
    try:
        from app.terminal.models import TerminalSession
        
        total_sessions = TerminalSession.query.filter_by(user_id=current_user.id).count()
        active_sessions = TerminalSession.query.filter_by(user_id=current_user.id, active=True).count()
        
        recent_sessions = TerminalSession.query.filter_by(user_id=current_user.id).order_by(
            TerminalSession.last_activity.desc()
        ).limit(5).all()
        
        return {
            'total': total_sessions,
            'active': active_sessions,
            'inactive': total_sessions - active_sessions,
            'recent': recent_sessions
        }
    except Exception as e:
        current_app.logger.warning(f"Error getting sessions info: {e}")
        return {
            'total': 0,
            'active': 0,
            'inactive': 0,
            'recent': []
        }

def _get_gui_info():
    """Get GUI sessions information with comprehensive error handling"""
    try:
        # Try to import GUI models
        from app.gui.models import GUISession, GUIApplication
        
        # Test if tables exist with a simple query
        try:
            db.session.execute(db.text("SELECT 1 FROM gui_session LIMIT 1")).fetchone()
            db.session.execute(db.text("SELECT 1 FROM gui_application LIMIT 1")).fetchone()
        except Exception:
            current_app.logger.info("GUI tables do not exist yet")
            return _get_default_gui_info()
        
        # Get GUI session statistics
        total_gui_sessions = GUISession.query.filter_by(user_id=current_user.id).count()
        active_gui_sessions = GUISession.query.filter_by(user_id=current_user.id, active=True).count()
        available_apps = GUIApplication.query.filter_by(enabled=True, installed=True).count()
        
        recent_gui_sessions = GUISession.query.filter_by(user_id=current_user.id).order_by(
            GUISession.last_activity.desc()
        ).limit(5).all()
        
        return {
            'total': total_gui_sessions,
            'active': active_gui_sessions,
            'inactive': total_gui_sessions - active_gui_sessions,
            'available_apps': available_apps,
            'webrtc_sessions': active_gui_sessions,
            'recent': recent_gui_sessions
        }
        
    except ImportError:
        current_app.logger.info("GUI module not available")
        return _get_default_gui_info()
    except Exception as e:
        current_app.logger.warning(f"Error getting GUI info: {e}")
        return _get_default_gui_info()

def _get_default_gui_info():
    """Return default GUI info when GUI module is not available"""
    return {
        'total': 0,
        'active': 0,
        'inactive': 0,
        'available_apps': 0,
        'webrtc_sessions': 0,
        'recent': []
    }

def _get_network_info():
    """Get network information with error handling"""
    try:
        import socket
        
        network_info = {
            'hostname': socket.gethostname(),
            'ip_address': socket.gethostbyname(socket.gethostname()),
            'interfaces': {}
        }
        
        # Get network interfaces
        for interface, addresses in psutil.net_if_addrs().items():
            network_info['interfaces'][interface] = []
            for addr in addresses:
                if addr.family == socket.AF_INET:  # IPv4
                    network_info['interfaces'][interface].append({
                        'address': addr.address,
                        'netmask': addr.netmask
                    })
        
        return network_info
    except Exception as e:
        current_app.logger.warning(f"Error getting network info: {e}")
        return {'hostname': 'Unknown', 'ip_address': 'Unknown', 'interfaces': {}}

def _get_disk_info():
    """Get disk information with error handling"""
    try:
        disk_info = []
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                disk_info.append({
                    'device': partition.device,
                    'mountpoint': partition.mountpoint,
                    'fstype': partition.fstype,
                    'total_size': usage.total,
                    'used_size': usage.used,
                    'free_size': usage.free,
                    'percent': usage.percent
                })
            except PermissionError:
                # Skip partitions we can't access
                continue
        return disk_info
    except Exception as e:
        current_app.logger.warning(f"Error getting disk info: {e}")
        return []

def _get_cpu_info():
    """Get CPU information with error handling"""
    try:
        cpu_freq = psutil.cpu_freq()
        return {
            'physical_cores': psutil.cpu_count(logical=False),
            'logical_cores': psutil.cpu_count(logical=True),
            'current_frequency': cpu_freq.current if cpu_freq else 'N/A',
            'min_frequency': cpu_freq.min if cpu_freq else 'N/A',
            'max_frequency': cpu_freq.max if cpu_freq else 'N/A',
            'cpu_percent': psutil.cpu_percent(interval=1, percpu=True),
            'architecture': platform.machine(),
            'processor': platform.processor()
        }
    except Exception as e:
        current_app.logger.warning(f"Error getting CPU info: {e}")
        return {
            'physical_cores': 0,
            'logical_cores': 0,
            'current_frequency': 'N/A',
            'min_frequency': 'N/A',
            'max_frequency': 'N/A',
            'cpu_percent': [0],
            'architecture': 'Unknown',
            'processor': 'Unknown'
        }

def _get_memory_info():
    """Get memory information with error handling"""
    try:
        memory = psutil.virtual_memory()
        return {
            'total': memory.total,
            'available': memory.available,
            'used': memory.used,
            'percent': memory.percent
        }
    except Exception as e:
        current_app.logger.warning(f"Error getting memory info: {e}")
        return {'total': 0, 'available': 0, 'used': 0, 'percent': 0}

def _get_swap_info():
    """Get swap information with error handling"""
    try:
        swap = psutil.swap_memory()
        return {
            'total': swap.total,
            'used': swap.used,
            'free': swap.free,
            'percent': swap.percent
        }
    except Exception as e:
        current_app.logger.warning(f"Error getting swap info: {e}")
        return {'total': 0, 'used': 0, 'free': 0, 'percent': 0}

def _get_python_info():
    """Get Python information"""
    return {
        'version': platform.python_version(),
        'implementation': platform.python_implementation(),
        'compiler': platform.python_compiler()
    }

def _get_os_info():
    """Get OS information"""
    return {
        'system': platform.system(),
        'release': platform.release(),
        'version': platform.version(),
        'architecture': platform.architecture()[0]
    }