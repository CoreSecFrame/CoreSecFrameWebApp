# app/core/models.py
from app import db
from datetime import datetime
from sqlalchemy import Index

class SystemLog(db.Model):
    """Model for storing system logs in database"""
    __tablename__ = 'system_log'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Log metadata
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    level = db.Column(db.String(10), index=True)  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    
    # Log content
    message = db.Column(db.Text, nullable=False)
    
    # Source information
    module = db.Column(db.String(100), index=True)
    function = db.Column(db.String(100))
    line_number = db.Column(db.Integer)
    pathname = db.Column(db.String(255))
    
    # Process information
    thread_id = db.Column(db.BigInteger)
    process_id = db.Column(db.Integer)
    
    # Exception information
    exception_text = db.Column(db.Text, nullable=True)
    
    # Context information (optional)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)
    session_id = db.Column(db.String(36), nullable=True, index=True)
    ip_address = db.Column(db.String(45), nullable=True)  # IPv6 compatible
    
    # Security classification
    is_security_event = db.Column(db.Boolean, default=False, index=True)
    severity_score = db.Column(db.Integer, default=0)  # 0-10 scale
    
    # Additional metadata as JSON
    extra_data = db.Column(db.Text, nullable=True)
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_timestamp_level', 'timestamp', 'level'),
        Index('idx_security_timestamp', 'is_security_event', 'timestamp'),
        Index('idx_user_timestamp', 'user_id', 'timestamp'),
        Index('idx_module_level', 'module', 'level'),
    )
    
    def __repr__(self):
        return f'<SystemLog {self.id} {self.level} {self.module}>'
    
    def to_dict(self):
        """Convert log entry to dictionary"""
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'level': self.level,
            'message': self.message,
            'module': self.module,
            'function': self.function,
            'line_number': self.line_number,
            'pathname': self.pathname,
            'thread_id': self.thread_id,
            'process_id': self.process_id,
            'exception_text': self.exception_text,
            'user_id': self.user_id,
            'session_id': self.session_id,
            'ip_address': self.ip_address,
            'is_security_event': self.is_security_event,
            'severity_score': self.severity_score,
            'extra_data': self.extra_data
        }
    
    def get_level_class(self):
        """Get Bootstrap CSS class for log level"""
        level_classes = {
            'DEBUG': 'secondary',
            'INFO': 'info',
            'WARNING': 'warning',
            'ERROR': 'danger',
            'CRITICAL': 'danger'
        }
        return level_classes.get(self.level, 'secondary')
    
    def get_formatted_timestamp(self):
        """Get formatted timestamp for display"""
        return self.timestamp.strftime('%Y-%m-%d %H:%M:%S')
    
    def get_short_message(self, max_length=100):
        """Get truncated message for list views"""
        if len(self.message) <= max_length:
            return self.message
        return self.message[:max_length] + '...'
    
    def is_error(self):
        """Check if this is an error or critical log"""
        return self.level in ['ERROR', 'CRITICAL']
    
    def is_warning(self):
        """Check if this is a warning log"""
        return self.level == 'WARNING'
    
    @classmethod
    def get_recent_logs(cls, limit=50, level=None, is_security=None, user_id=None):
        """Get recent log entries with optional filtering"""
        query = cls.query.order_by(cls.timestamp.desc())
        
        if level:
            query = query.filter(cls.level == level)
        
        if is_security is not None:
            query = query.filter(cls.is_security_event == is_security)
        
        if user_id:
            query = query.filter(cls.user_id == user_id)
        
        return query.limit(limit).all()
    
    @classmethod
    def get_error_count_last_24h(cls):
        """Get count of errors in the last 24 hours"""
        from datetime import datetime, timedelta
        
        since = datetime.utcnow() - timedelta(hours=24)
        
        return cls.query.filter(
            cls.timestamp >= since,
            cls.level.in_(['ERROR', 'CRITICAL'])
        ).count()
    
    @classmethod
    def get_security_events_count_last_24h(cls):
        """Get count of security events in the last 24 hours"""
        from datetime import datetime, timedelta
        
        since = datetime.utcnow() - timedelta(hours=24)
        
        return cls.query.filter(
            cls.timestamp >= since,
            cls.is_security_event == True
        ).count()
    
    @classmethod
    def get_log_level_stats(cls, hours=24):
        """Get statistics by log level for the specified time period"""
        from datetime import datetime, timedelta
        from sqlalchemy import func
        
        since = datetime.utcnow() - timedelta(hours=hours)
        
        stats = db.session.query(
            cls.level,
            func.count(cls.id).label('count')
        ).filter(
            cls.timestamp >= since
        ).group_by(cls.level).all()
        
        return {stat.level: stat.count for stat in stats}
    
    @classmethod
    def get_module_stats(cls, hours=24, limit=10):
        """Get top modules by log count"""
        from datetime import datetime, timedelta
        from sqlalchemy import func
        
        since = datetime.utcnow() - timedelta(hours=hours)
        
        stats = db.session.query(
            cls.module,
            func.count(cls.id).label('count')
        ).filter(
            cls.timestamp >= since
        ).group_by(cls.module).order_by(
            func.count(cls.id).desc()
        ).limit(limit).all()
        
        return [{'module': stat.module, 'count': stat.count} for stat in stats]
    
    @classmethod
    def cleanup_old_logs(cls, days_to_keep=30):
        """Clean up old log entries"""
        from datetime import datetime, timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        # Keep security events longer (90 days)
        security_cutoff = datetime.utcnow() - timedelta(days=90)
        
        # Delete old non-security logs
        deleted_count = cls.query.filter(
            cls.timestamp < cutoff_date,
            cls.is_security_event == False
        ).delete()
        
        # Delete very old security logs
        deleted_security = cls.query.filter(
            cls.timestamp < security_cutoff,
            cls.is_security_event == True
        ).delete()
        
        db.session.commit()
        
        return deleted_count + deleted_security

class LogSearchQuery(db.Model):
    """Model to store and reuse common log search queries"""
    __tablename__ = 'log_search_query'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    
    # Query parameters
    level_filter = db.Column(db.String(20))
    module_filter = db.Column(db.String(100))
    message_search = db.Column(db.String(255))
    is_security_filter = db.Column(db.Boolean)
    date_range_hours = db.Column(db.Integer, default=24)
    
    # Metadata
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used = db.Column(db.DateTime)
    use_count = db.Column(db.Integer, default=0)
    
    def to_dict(self):
        """Convert to dictionary for API"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'level_filter': self.level_filter,
            'module_filter': self.module_filter,
            'message_search': self.message_search,
            'is_security_filter': self.is_security_filter,
            'date_range_hours': self.date_range_hours,
            'created_at': self.created_at.isoformat(),
            'last_used': self.last_used.isoformat() if self.last_used else None,
            'use_count': self.use_count
        }

class SystemMetric(db.Model):
    """Model for storing system performance metrics"""
    __tablename__ = 'system_metric'
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Metric identification
    metric_name = db.Column(db.String(50), index=True)
    metric_type = db.Column(db.String(20))  # counter, gauge, histogram
    
    # Values
    value = db.Column(db.Float)
    unit = db.Column(db.String(20))
    
    # Context
    tags = db.Column(db.Text)  # JSON string of key-value pairs
    
    def __repr__(self):
        return f'<SystemMetric {self.metric_name}={self.value}{self.unit}>'