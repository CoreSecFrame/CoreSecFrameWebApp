# app/core/routes.py - Updated with GUI support
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
    system_info = get_system_info()
    modules_info = get_modules_info()
    sessions_info = get_sessions_info()
    gui_info = get_gui_info()  # New GUI information
    
    return render_template(
        'core/dashboard.html', 
        title='Dashboard',
        system_info=system_info,
        modules_info=modules_info,
        sessions_info=sessions_info,
        gui_info=gui_info
    )

# Utility functions for the dashboard
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
    try:
        total_modules = Module.query.count()
        installed_modules = Module.query.filter_by(installed=True).count()
        
        # Get module categories
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
        # If the Module table doesn't exist, return default values
        current_app.logger.error(f"Error getting modules info: {str(e)}")
        return {
            'total': 0,
            'installed': 0,
            'available': 0,
            'categories': []
        }

def get_sessions_info():
    # Get sessions information from the terminal sessions
    from app.terminal.models import TerminalSession
    
    total_sessions = TerminalSession.query.filter_by(user_id=current_user.id).count()
    active_sessions = TerminalSession.query.filter_by(user_id=current_user.id, active=True).count()
    inactive_sessions = total_sessions - active_sessions
    
    # Get recent sessions
    recent_sessions = TerminalSession.query.filter_by(user_id=current_user.id).order_by(
        TerminalSession.last_activity.desc()
    ).limit(5).all()
    
    return {
        'total': total_sessions,
        'active': active_sessions,
        'inactive': inactive_sessions,
        'recent': recent_sessions
    }

def get_gui_info():
    """Get GUI sessions information with proper error handling"""
    try:
        # Try to import GUI models - they might not exist
        from app.gui.models import GUISession, GUIApplication
        
        # Check if tables exist by trying a simple query
        try:
            # Test if GUI tables exist
            db.session.execute(db.text("SELECT 1 FROM gui_session LIMIT 1")).fetchone()
            db.session.execute(db.text("SELECT 1 FROM gui_application LIMIT 1")).fetchone()
        except Exception:
            # Tables don't exist, return default values
            current_app.logger.info("GUI tables do not exist yet")
            return {
                'total': 0,
                'active': 0,
                'inactive': 0,
                'available_apps': 0,
                'webrtc_sessions': 0,
                'recent': []
            }
        
        # Get GUI session statistics
        total_gui_sessions = GUISession.query.filter_by(user_id=current_user.id).count()
        active_gui_sessions = GUISession.query.filter_by(user_id=current_user.id, active=True).count()
        
        # Get available applications
        available_apps = GUIApplication.query.filter_by(enabled=True, installed=True).count()
        
        # Get recent GUI sessions
        recent_gui_sessions = GUISession.query.filter_by(user_id=current_user.id).order_by(
            GUISession.last_activity.desc()
        ).limit(5).all()
        
        # Count WebRTC sessions (active GUI sessions with WebRTC enabled)
        webrtc_sessions = GUISession.query.filter_by(
            user_id=current_user.id, 
            active=True
        ).count()  # Assuming all active GUI sessions use WebRTC
        
        return {
            'total': total_gui_sessions,
            'active': active_gui_sessions,
            'inactive': total_gui_sessions - active_gui_sessions,
            'available_apps': available_apps,
            'webrtc_sessions': webrtc_sessions,
            'recent': recent_gui_sessions
        }
        
    except ImportError:
        # GUI module not installed/available
        current_app.logger.info("GUI module not available")
        return {
            'total': 0,
            'active': 0,
            'inactive': 0,
            'available_apps': 0,
            'webrtc_sessions': 0,
            'recent': []
        }
    except Exception as e:
        current_app.logger.error(f"Error getting GUI info: {str(e)}")
        return {
            'total': 0,
            'active': 0,
            'inactive': 0,
            'available_apps': 0,
            'webrtc_sessions': 0,
            'recent': []
        }
        
    except ImportError:
        # GUI module not installed/available
        current_app.logger.info("GUI module not available")
        return {
            'total': 0,
            'active': 0,
            'inactive': 0,
            'available_apps': 0,
            'webrtc_sessions': 0,
            'recent': []
        }
    except Exception as e:
        current_app.logger.error(f"Error getting GUI info: {str(e)}")
        return {
            'total': 0,
            'active': 0,
            'inactive': 0,
            'available_apps': 0,
            'webrtc_sessions': 0,
            'recent': []
        }

@core_bp.route('/system-info')
@login_required
def system_info():
    """Display detailed system information"""
    system_info = get_system_info()
    
    # Add more detailed system info
    import psutil
    import platform
    import socket
    
    # Get network information
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
    
    # Get disk information
    disk_info = []
    for partition in psutil.disk_partitions():
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
    
    # Get CPU information
    cpu_info = {
        'physical_cores': psutil.cpu_count(logical=False),
        'logical_cores': psutil.cpu_count(logical=True),
        'current_frequency': psutil.cpu_freq().current if psutil.cpu_freq() else 'N/A',
        'min_frequency': psutil.cpu_freq().min if psutil.cpu_freq() else 'N/A',
        'max_frequency': psutil.cpu_freq().max if psutil.cpu_freq() else 'N/A',
        'cpu_percent': psutil.cpu_percent(interval=1, percpu=True),
        'architecture': platform.machine(),
        'processor': platform.processor()
    }
    
    # Get memory information
    memory = psutil.virtual_memory()
    memory_info = {
        'total': memory.total,
        'available': memory.available,
        'used': memory.used,
        'percent': memory.percent
    }
    
    # Get swap information
    swap = psutil.swap_memory()
    swap_info = {
        'total': swap.total,
        'used': swap.used,
        'free': swap.free,
        'percent': swap.percent
    }
    
    # Get Python information
    python_info = {
        'version': platform.python_version(),
        'implementation': platform.python_implementation(),
        'compiler': platform.python_compiler()
    }
    
    # Get OS information
    os_info = {
        'system': platform.system(),
        'release': platform.release(),
        'version': platform.version(),
        'architecture': platform.architecture()[0]
    }
    
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