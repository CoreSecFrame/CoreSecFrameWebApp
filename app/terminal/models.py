# app/terminal/models.py
from app import db
from datetime import datetime
from flask_login import current_user
import uuid

class TerminalSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), index=True)
    session_id = db.Column(db.String(36), index=True, unique=True, default=lambda: str(uuid.uuid4()))
    module_name = db.Column(db.String(64), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    last_activity = db.Column(db.DateTime, default=datetime.utcnow)
    active = db.Column(db.Boolean, default=True)
    session_type = db.Column(db.String(20), default='terminal')  # 'terminal', 'guided', 'direct'
    
    def __repr__(self):
        return f'<TerminalSession {self.name}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'session_id': self.session_id,
            'module_name': self.module_name,
            'user_id': self.user_id,
            'start_time': self.start_time.isoformat(),
            'last_activity': self.last_activity.isoformat(),
            'active': self.active,
            'session_type': self.session_type,
            'duration': self.get_duration()
        }
    
    def get_duration(self):
        delta = datetime.utcnow() - self.start_time
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60
        seconds = delta.seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

class TerminalLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(36), db.ForeignKey('terminal_session.session_id'))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    command = db.Column(db.Text, nullable=True)
    output = db.Column(db.Text, nullable=True)
    event_type = db.Column(db.String(20), default='command')  # 'command', 'output', 'system'
    
    def __repr__(self):
        return f'<TerminalLog {self.id}>'