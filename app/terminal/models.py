# app/terminal/models.py
from app import db
from datetime import datetime
from flask_login import current_user
import uuid
import json

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
    use_oniux = db.Column(db.Boolean, default=False, nullable=False)
    
    # Enhanced fields for better tracking
    total_commands = db.Column(db.Integer, default=0)
    total_output_size = db.Column(db.Integer, default=0)
    last_command = db.Column(db.String(256), nullable=True)
    
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
            'use_oniux': self.use_oniux,
            'duration': self.get_duration(),
            'total_commands': self.total_commands,
            'total_output_size': self.total_output_size,
            'last_command': self.last_command
        }
    
    def get_duration(self):
        if self.active:
            end_time = datetime.utcnow()
        else:
            # For inactive sessions, find the last log timestamp
            last_log = TerminalLog.query.filter_by(session_id=self.session_id).order_by(TerminalLog.timestamp.desc()).first()
            end_time = last_log.timestamp if last_log else self.last_activity
        
        delta = end_time - self.start_time
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60
        seconds = delta.seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    def update_stats(self):
        """Update session statistics from logs"""
        try:
            # Count commands
            command_count = TerminalLog.query.filter_by(
                session_id=self.session_id,
                event_type='command_input'
            ).count()
            
            # Calculate total output size
            output_logs = TerminalLog.query.filter_by(
                session_id=self.session_id,
                event_type='terminal_output'
            ).all()
            
            total_size = sum(len(log.output or '') for log in output_logs)
            
            # Get last command
            last_cmd_log = TerminalLog.query.filter_by(
                session_id=self.session_id,
                event_type='command_input'
            ).order_by(TerminalLog.timestamp.desc()).first()
            
            # Update fields
            self.total_commands = command_count
            self.total_output_size = total_size
            self.last_command = last_cmd_log.command if last_cmd_log else None
            
            db.session.commit()
            
        except Exception as e:
            print(f"Error updating session stats: {e}")
            db.session.rollback()

class TerminalLog(db.Model):
    __tablename__ = 'terminal_log'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(36), db.ForeignKey('terminal_session.session_id'), index=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Event classification
    event_type = db.Column(db.String(30), default='terminal_output', index=True)
    # Types: 'session_start', 'session_end', 'command_input', 'terminal_output', 
    #        'session_buffer', 'tab_completion', 'process_exit', 'terminal_resize', 'api_command'
    
    # Content fields
    command = db.Column(db.Text, nullable=True)  # For command_input events
    output = db.Column(db.Text, nullable=True)   # For terminal_output and session_buffer events
    
    # Enhanced metadata
    message = db.Column(db.String(256), nullable=True)  # Human-readable message
    extra_data = db.Column(db.Text, nullable=True)      # JSON metadata (renamed from metadata)
    output_size = db.Column(db.Integer, default=0)      # Size of output for indexing
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Auto-calculate output size
        if self.output:
            self.output_size = len(self.output)
    
    def __repr__(self):
        return f'<TerminalLog {self.id} {self.event_type}>'
    
    def to_dict(self):
        """Convert log entry to dictionary"""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'timestamp': self.timestamp.isoformat(),
            'event_type': self.event_type,
            'command': self.command,
            'output': self.output,
            'message': self.message,
            'output_size': self.output_size,
            'metadata': json.loads(self.extra_data) if self.extra_data else None
        }
    
    def get_formatted_timestamp(self):
        """Get formatted timestamp for display"""
        return self.timestamp.strftime('%Y-%m-%d %H:%M:%S')
    
    def get_display_output(self, max_length=500):
        """Get truncated output for display purposes"""
        if not self.output:
            return None
        
        if len(self.output) <= max_length:
            return self.output
        
        return self.output[:max_length] + f"... (truncated, {len(self.output)} total chars)"
    
    def is_command(self):
        """Check if this log entry represents a command"""
        return self.event_type == 'command_input' and self.command is not None
    
    def is_output(self):
        """Check if this log entry represents terminal output"""
        return self.event_type in ['terminal_output', 'session_buffer'] and self.output is not None
    
    def is_system_event(self):
        """Check if this log entry represents a system event"""
        return self.event_type in ['session_start', 'session_end', 'process_exit', 'terminal_resize']

class TerminalLogSummary(db.Model):
    """Summary table for session statistics and quick access"""
    __tablename__ = 'terminal_log_summary'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(36), db.ForeignKey('terminal_session.session_id'), unique=True, index=True)
    
    # Summary statistics
    total_commands = db.Column(db.Integer, default=0)
    total_output_entries = db.Column(db.Integer, default=0)
    total_output_size = db.Column(db.Integer, default=0)
    session_duration_seconds = db.Column(db.Integer, default=0)
    
    # Quick access data
    first_command = db.Column(db.String(256), nullable=True)
    last_command = db.Column(db.String(256), nullable=True)
    most_recent_output = db.Column(db.Text, nullable=True)  # Last 1000 chars of output
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<TerminalLogSummary {self.session_id}>'
    
    @classmethod
    def update_for_session(cls, session_id):
        """Update or create summary for a session"""
        try:
            # Get or create summary
            summary = cls.query.filter_by(session_id=session_id).first()
            if not summary:
                summary = cls(session_id=session_id)
                db.session.add(summary)
            
            # Calculate statistics
            command_logs = TerminalLog.query.filter_by(
                session_id=session_id,
                event_type='command_input'
            ).order_by(TerminalLog.timestamp).all()
            
            output_logs = TerminalLog.query.filter_by(
                session_id=session_id,
                event_type='terminal_output'
            ).all()
            
            # Update statistics
            summary.total_commands = len(command_logs)
            summary.total_output_entries = len(output_logs)
            summary.total_output_size = sum(len(log.output or '') for log in output_logs)
            
            # Update quick access data
            if command_logs:
                summary.first_command = command_logs[0].command
                summary.last_command = command_logs[-1].command
            
            # Get most recent output (last 1000 chars)
            if output_logs:
                recent_output = output_logs[-1].output or ''
                summary.most_recent_output = recent_output[-1000:] if len(recent_output) > 1000 else recent_output
            
            # Calculate session duration
            session = TerminalSession.query.filter_by(session_id=session_id).first()
            if session:
                if session.active:
                    duration = datetime.utcnow() - session.start_time
                else:
                    last_log = TerminalLog.query.filter_by(session_id=session_id).order_by(TerminalLog.timestamp.desc()).first()
                    end_time = last_log.timestamp if last_log else session.last_activity
                    duration = end_time - session.start_time
                
                summary.session_duration_seconds = int(duration.total_seconds())
            
            db.session.commit()
            return summary
            
        except Exception as e:
            print(f"Error updating terminal log summary: {e}")
            db.session.rollback()
            return None