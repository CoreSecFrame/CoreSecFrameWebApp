# app/gui/models.py
from app import db
from datetime import datetime
from flask_login import current_user
import uuid
import json

class GUIApplication(db.Model):
    """Model for GUI applications that can be launched"""
    __tablename__ = 'gui_application'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False, index=True)
    display_name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(64), index=True)
    
    # Application execution details
    command = db.Column(db.String(256), nullable=False)  # Command to execute
    working_directory = db.Column(db.String(256))  # Optional working directory
    environment_vars = db.Column(db.Text)  # JSON string of environment variables
    
    # Application requirements
    required_packages = db.Column(db.Text)  # JSON array of required system packages
    
    # Metadata
    icon_path = db.Column(db.String(256))  # Path to application icon
    version = db.Column(db.String(32))
    installed = db.Column(db.Boolean, default=False)
    enabled = db.Column(db.Boolean, default=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_used = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    sessions = db.relationship('GUISession', backref='application', lazy='dynamic', 
                              cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<GUISession {self.name} ({self.session_id})>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'display_name': self.display_name,
            'description': self.description,
            'category': self.category,
            'command': self.command,
            'working_directory': self.working_directory,
            'environment_vars': json.loads(self.environment_vars) if self.environment_vars else {},
            'required_packages': json.loads(self.required_packages) if self.required_packages else [],
            'icon_path': self.icon_path,
            'version': self.version,
            'installed': self.installed,
            'enabled': self.enabled,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'last_used': self.last_used.isoformat() if self.last_used else None,
            'active_sessions': self.sessions.filter_by(active=True).count()
        }
    
    def get_environment_dict(self):
        """Get environment variables as dictionary"""
        if self.environment_vars:
            try:
                return json.loads(self.environment_vars)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_environment_dict(self, env_dict):
        """Set environment variables from dictionary"""
        self.environment_vars = json.dumps(env_dict) if env_dict else None
    
    def get_required_packages_list(self):
        """Get required packages as list"""
        if self.required_packages:
            try:
                return json.loads(self.required_packages)
            except json.JSONDecodeError:
                return []
        return []
    
    def set_required_packages_list(self, packages_list):
        """Set required packages from list"""
        self.required_packages = json.dumps(packages_list) if packages_list else None

class GUISession(db.Model):
    """Model for active GUI sessions"""
    __tablename__ = 'gui_session'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(36), unique=True, nullable=False, index=True, 
                          default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(128), nullable=False)
    
    # Foreign keys
    application_id = db.Column(db.Integer, db.ForeignKey('gui_application.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Session state
    active = db.Column(db.Boolean, default=True, index=True)
    
    # X11 and VNC configuration
    display_number = db.Column(db.Integer)  # X11 display number (e.g., 99 for :99)
    vnc_port = db.Column(db.Integer)  # VNC port (e.g., 5999)
    vnc_password = db.Column(db.String(16))  # Optional VNC password
    
    # Process information
    xvfb_pid = db.Column(db.Integer)  # Xvfb process PID
    app_pid = db.Column(db.Integer)   # Application process PID
    x11vnc_pid = db.Column(db.Integer)  # x11vnc process PID
    
    # Session configuration
    screen_resolution = db.Column(db.String(16), default='1024x768')  # Screen resolution
    color_depth = db.Column(db.Integer, default=24)  # Color depth
    
    # Statistics
    cpu_usage = db.Column(db.Float, default=0.0)
    memory_usage = db.Column(db.Float, default=0.0)
    
    # Timestamps
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    last_activity = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime, nullable=True)
    
    # Note: User relationship is defined in User model with backref

    
    def __repr__(self):
        return f'<GUISession {self.name} ({self.session_id})>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'name': self.name,
            'application_id': self.application_id,
            'application_name': self.application.name if self.application else None,
            'application_display_name': self.application.display_name if self.application else None,
            'user_id': self.user_id,
            'username': self.user.username if self.user else None,
            'active': self.active,
            'display_number': self.display_number,
            'vnc_port': self.vnc_port,
            'screen_resolution': self.screen_resolution,
            'color_depth': self.color_depth,
            'cpu_usage': self.cpu_usage,
            'memory_usage': self.memory_usage,
            'start_time': self.start_time.isoformat(),
            'last_activity': self.last_activity.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration': self.get_duration(),
            'vnc_url': self.get_vnc_url(),
            'novnc_url': self.get_novnc_url()
        }
    
    def get_duration(self):
        """Get session duration as formatted string"""
        if self.active:
            end_time = datetime.utcnow()
        else:
            end_time = self.end_time or self.last_activity
        
        duration = end_time - self.start_time
        hours = duration.seconds // 3600
        minutes = (duration.seconds % 3600) // 60
        seconds = duration.seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    def get_display_string(self):
        """Get X11 display string (e.g., ':99')"""
        return f":{self.display_number}" if self.display_number else None
    

    def get_vnc_url(self):
        """Get direct VNC connection URL with proper IP detection"""
        if self.vnc_port:
            from app.gui.network_utils import VNCConnectionHelper
            return VNCConnectionHelper.get_vnc_url(self.vnc_port)
        return None
    
    def get_novnc_url(self, base_url=None):
        """Get noVNC web client URL with proper IP detection"""
        if self.vnc_port:
            from app.gui.network_utils import VNCConnectionHelper
            return VNCConnectionHelper.get_novnc_url(self.vnc_port, base_url)
        return None

    def get_connection_info(self):
        """Get complete VNC connection information"""
        if self.vnc_port:
            from app.gui.network_utils import VNCConnectionHelper
            return VNCConnectionHelper.get_connection_info(self.vnc_port, self.display_number)
        return None

    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity = datetime.utcnow()
        db.session.commit()
    
    def update_stats(self, cpu_usage=None, memory_usage=None):
        """Update session statistics"""
        if cpu_usage is not None:
            self.cpu_usage = cpu_usage
        if memory_usage is not None:
            self.memory_usage = memory_usage
        self.update_activity()

class GUICategory(db.Model):
    """Model for GUI application categories"""
    __tablename__ = 'gui_category'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False, index=True)
    display_name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text)
    icon_class = db.Column(db.String(64))  # CSS icon class
    sort_order = db.Column(db.Integer, default=0)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<GUICategory {self.name}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'display_name': self.display_name,
            'description': self.description,
            'icon_class': self.icon_class,
            'sort_order': self.sort_order,
            'created_at': self.created_at.isoformat(),
            'application_count': GUIApplication.query.filter_by(category=self.name).count()
        }

class GUISessionLog(db.Model):
    """Model for GUI session activity logs"""
    __tablename__ = 'gui_session_log'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(36), db.ForeignKey('gui_session.session_id'), 
                          nullable=False, index=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Log entry details
    event_type = db.Column(db.String(32), nullable=False, index=True)
    # Types: 'session_start', 'session_end', 'process_start', 'process_end', 
    #        'resolution_change', 'activity_update', 'error'
    
    message = db.Column(db.String(512))
    details = db.Column(db.Text)  # JSON string for additional details
    
    # Relationship
    session = db.relationship('GUISession', backref='logs')
    
    def __repr__(self):
        return f'<GUISessionLog {self.event_type} for {self.session_id}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'timestamp': self.timestamp.isoformat(),
            'event_type': self.event_type,
            'message': self.message,
            'details': json.loads(self.details) if self.details else None
        }
    
    def set_details_dict(self, details_dict):
        """Set details from dictionary"""
        self.details = json.dumps(details_dict) if details_dict else None
    
    def get_details_dict(self):
        """Get details as dictionary"""
        if self.details:
            try:
                return json.loads(self.details)
            except json.JSONDecodeError:
                return {}
        return {}