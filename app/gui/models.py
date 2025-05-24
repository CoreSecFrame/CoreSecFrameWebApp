# app/gui/models.py
from app import db
from datetime import datetime
import uuid
import json

class GUIApplication(db.Model):
    __tablename__ = 'gui_application'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    display_name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text)
    command = db.Column(db.String(256), nullable=False)
    icon = db.Column(db.String(64), default='app')
    category = db.Column(db.String(64), default='Applications')
    enabled = db.Column(db.Boolean, default=True)
    installed = db.Column(db.Boolean, default=False)
    launch_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def check_installed(self):
        """Check if application is installed on system"""
        import shutil
        self.installed = shutil.which(self.command.split()[0]) is not None
        return self.installed
    
    def increment_launch_count(self):
        """Increment launch counter"""
        self.launch_count += 1
        db.session.commit()
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'display_name': self.display_name,
            'description': self.description,
            'command': self.command,
            'icon': self.icon,
            'category': self.category,
            'enabled': self.enabled,
            'installed': self.installed,
            'launch_count': self.launch_count
        }

class GUISession(db.Model):
    __tablename__ = 'gui_session'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    session_id = db.Column(db.String(36), unique=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Application info
    application_name = db.Column(db.String(64), nullable=False)
    application_command = db.Column(db.String(256), nullable=False)
    
    # Session settings
    screen_width = db.Column(db.Integer, default=1024)
    screen_height = db.Column(db.Integer, default=768)
    
    # Session state
    active = db.Column(db.Boolean, default=True)
    display_number = db.Column(db.Integer)
    vnc_port = db.Column(db.Integer)
    pid = db.Column(db.Integer)
    
    # Timestamps
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    last_activity = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Statistics
    total_input_events = db.Column(db.Integer, default=0)
    
    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity = datetime.utcnow()
        db.session.commit()
    
    def get_duration(self):
        """Get session duration as formatted string"""
        if self.active:
            end_time = datetime.utcnow()
        else:
            end_time = self.last_activity
        
        delta = end_time - self.start_time
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60
        seconds = delta.seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'session_id': self.session_id,
            'user_id': self.user_id,
            'application_name': self.application_name,
            'application_command': self.application_command,
            'screen_width': self.screen_width,
            'screen_height': self.screen_height,
            'active': self.active,
            'display_number': self.display_number,
            'vnc_port': self.vnc_port,
            'pid': self.pid,
            'start_time': self.start_time.isoformat(),
            'last_activity': self.last_activity.isoformat(),
            'total_input_events': self.total_input_events,
            'duration': self.get_duration()
        }

class GUISessionEvent(db.Model):
    __tablename__ = 'gui_session_event'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(36), db.ForeignKey('gui_session.session_id'))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    event_type = db.Column(db.String(32), nullable=False)  # user_input, system_event, etc.
    input_type = db.Column(db.String(32))  # mouse, keyboard, etc.
    
    # Input coordinates (for mouse events)
    coordinates_x = db.Column(db.Integer)
    coordinates_y = db.Column(db.Integer)
    
    # Key information (for keyboard events)
    key_code = db.Column(db.String(32))
    
    # Additional event data
    event_data = db.Column(db.Text)  # JSON data
    
    # Client info
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(256))

class WebRTCSignalingMessage(db.Model):
    __tablename__ = 'webrtc_signaling_message'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(36), db.ForeignKey('gui_session.session_id'))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    message_type = db.Column(db.String(32), nullable=False)  # offer, answer, ice-candidate
    sender = db.Column(db.String(16), nullable=False)  # client, server
    message_data = db.Column(db.Text, nullable=False)  # JSON data