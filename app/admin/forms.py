# app/admin/forms.py - Enhanced Version
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, SubmitField, BooleanField, IntegerField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, Optional, ValidationError, NumberRange
from app.auth.models import User

class UserForm(FlaskForm):
    username = StringField('Username', validators=[
        DataRequired(), 
        Length(min=3, max=64, message='Username must be between 3 and 64 characters')
    ])
    email = StringField('Email', validators=[
        DataRequired(), 
        Email(message='Please enter a valid email address')
    ])
    password = PasswordField('Password', validators=[
        Optional(),  # Password is optional when editing
        Length(min=8, message='Password must be at least 8 characters long')
    ])
    role = SelectField('Role', choices=[
        ('user', 'User'),
        ('admin', 'Administrator')
    ])
    submit = SubmitField('Submit')
    
    def __init__(self, *args, **kwargs):
        super(UserForm, self).__init__(*args, **kwargs)
        # Store original user if we're editing
        if 'obj' in kwargs:
            self.original_user = kwargs['obj']
        else:
            self.original_user = None
    
    def validate_username(self, username):
        # Skip validation if username hasn't changed
        if self.original_user and self.original_user.username == username.data:
            return
            
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('This username is already taken. Please choose a different one.')
            
    def validate_email(self, email):
        # Skip validation if email hasn't changed
        if self.original_user and self.original_user.email == email.data:
            return
            
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('This email is already registered. Please use a different one.')
            
    def validate_password(self, password):
        # Make password required for new users
        if not self.original_user and not password.data:
            raise ValidationError('Password is required when creating a new user.')

class LogSearchForm(FlaskForm):
    """Form for searching and filtering system logs"""
    
    # Search and filter fields
    search_query = StringField('Search Message', validators=[Optional(), Length(max=255)])
    
    level = SelectField('Log Level', choices=[
        ('', 'All Levels'),
        ('DEBUG', 'Debug'),
        ('INFO', 'Info'),
        ('WARNING', 'Warning'),
        ('ERROR', 'Error'),
        ('CRITICAL', 'Critical')
    ], default='')
    
    module = StringField('Module Name', validators=[Optional(), Length(max=100)])
    
    security_only = BooleanField('Security Events Only')
    
    # Time range
    hours_back = SelectField('Time Range', choices=[
        ('1', 'Last Hour'),
        ('6', 'Last 6 Hours'),
        ('24', 'Last 24 Hours'),
        ('168', 'Last Week'),
        ('720', 'Last 30 Days'),
        ('', 'All Time')
    ], default='24')
    
    # Pagination
    per_page = SelectField('Results Per Page', choices=[
        ('25', '25'),
        ('50', '50'),
        ('100', '100'),
        ('200', '200')
    ], default='50')
    
    # Actions
    search = SubmitField('Search Logs')
    export_csv = SubmitField('Export CSV')
    export_json = SubmitField('Export JSON')
    clear_filters = SubmitField('Clear Filters')

class LogCleanupForm(FlaskForm):
    """Form for cleaning up old system logs"""
    
    days_to_keep = IntegerField(
        'Days to Keep', 
        validators=[
            DataRequired(), 
            NumberRange(min=1, max=365, message='Must be between 1 and 365 days')
        ],
        default=30,
        description='Number of days of logs to retain (security events kept for 90 days)'
    )
    
    confirm_cleanup = BooleanField(
        'I understand this will permanently delete old log entries',
        validators=[DataRequired(message='You must confirm the cleanup operation')]
    )
    
    cleanup = SubmitField('Clean Up Logs')

class SystemMaintenanceForm(FlaskForm):
    """Form for system maintenance operations"""
    
    operation = SelectField('Maintenance Operation', choices=[
        ('', 'Select Operation'),
        ('cleanup_logs', 'Clean Up Old Logs'),
        ('vacuum_database', 'Optimize Database'),
        ('clear_cache', 'Clear Application Cache'),
        ('restart_services', 'Restart Background Services')
    ])
    
    # Parameters for different operations
    cleanup_days = IntegerField('Days to Keep (for log cleanup)', default=30)
    confirm_operation = BooleanField('I confirm this maintenance operation')
    
    execute = SubmitField('Execute Maintenance')
    
    def validate_confirm_operation(self, confirm_operation):
        if not confirm_operation.data:
            raise ValidationError('You must confirm the maintenance operation.')

class LogAlertForm(FlaskForm):
    """Form for configuring log-based alerts"""
    
    name = StringField(
        'Alert Name', 
        validators=[DataRequired(), Length(min=3, max=100)]
    )
    
    description = TextAreaField(
        'Description',
        validators=[Optional(), Length(max=500)]
    )
    
    # Alert conditions
    log_level = SelectField('Trigger on Log Level', choices=[
        ('ERROR', 'Error'),
        ('CRITICAL', 'Critical'),
        ('WARNING', 'Warning')
    ])
    
    keyword_filter = StringField(
        'Keyword Filter (optional)',
        validators=[Optional(), Length(max=255)],
        description='Alert will trigger if log message contains this keyword'
    )
    
    module_filter = StringField(
        'Module Filter (optional)',
        validators=[Optional(), Length(max=100)],
        description='Alert will trigger only for logs from this module'
    )
    
    security_events_only = BooleanField('Security Events Only')
    
    # Thresholds
    threshold_count = IntegerField(
        'Threshold Count',
        validators=[DataRequired(), NumberRange(min=1)],
        default=5,
        description='Number of matching log entries to trigger alert'
    )
    
    time_window_minutes = IntegerField(
        'Time Window (minutes)',
        validators=[DataRequired(), NumberRange(min=1, max=1440)],
        default=15,
        description='Time window for counting log entries'
    )
    
    # Notification settings
    email_notifications = BooleanField('Send Email Notifications')
    email_recipients = TextAreaField(
        'Email Recipients',
        description='One email address per line'
    )
    
    active = BooleanField('Alert Active', default=True)
    
    save_alert = SubmitField('Save Alert')
    
    def validate_email_recipients(self, email_recipients):
        if self.email_notifications.data and not email_recipients.data:
            raise ValidationError('Email recipients are required when email notifications are enabled.')
        
        if email_recipients.data:
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            
            for line in email_recipients.data.strip().split('\n'):
                email = line.strip()
                if email and not re.match(email_pattern, email):
                    raise ValidationError(f'Invalid email address: {email}')

class SystemConfigForm(FlaskForm):
    """Form for system configuration settings"""
    
    # Logging settings
    log_level = SelectField('System Log Level', choices=[
        ('DEBUG', 'Debug (Most Verbose)'),
        ('INFO', 'Info'),
        ('WARNING', 'Warning'),
        ('ERROR', 'Error Only'),
        ('CRITICAL', 'Critical Only')
    ], default='INFO')
    
    enable_database_logging = BooleanField(
        'Enable Database Logging',
        default=True,
        description='Store logs in database (requires more storage)'
    )
    
    log_retention_days = IntegerField(
        'Log Retention (Days)',
        validators=[NumberRange(min=1, max=365)],
        default=30,
        description='How long to keep logs before automatic cleanup'
    )
    
    # Security settings
    max_login_attempts = IntegerField(
        'Max Login Attempts',
        validators=[NumberRange(min=1, max=100)],
        default=5,
        description='Maximum failed login attempts before lockout'
    )
    
    session_timeout_minutes = IntegerField(
        'Session Timeout (Minutes)',
        validators=[NumberRange(min=5, max=1440)],
        default=60,
        description='User session timeout in minutes'
    )
    
    enable_security_logging = BooleanField(
        'Enhanced Security Logging',
        default=True,
        description='Log detailed security events'
    )
    
    # Performance settings
    terminal_buffer_size_kb = IntegerField(
        'Terminal Buffer Size (KB)',
        validators=[NumberRange(min=10, max=1000)],
        default=100,
        description='Maximum terminal output buffer size'
    )
    
    max_concurrent_sessions = IntegerField(
        'Max Concurrent Terminal Sessions',
        validators=[NumberRange(min=1, max=100)],
        default=10,
        description='Maximum number of concurrent terminal sessions per user'
    )
    
    # Module settings
    auto_install_dependencies = BooleanField(
        'Auto-install Module Dependencies',
        default=True,
        description='Automatically install system dependencies for modules'
    )
    
    enable_module_updates = BooleanField(
        'Enable Module Updates',
        default=True,
        description='Allow automatic module updates from repository'
    )
    
    save_config = SubmitField('Save Configuration')

class BulkUserActionForm(FlaskForm):
    """Form for bulk user management actions"""
    
    action = SelectField('Bulk Action', choices=[
        ('', 'Select Action'),
        ('activate', 'Activate Selected Users'),
        ('deactivate', 'Deactivate Selected Users'),
        ('change_role', 'Change Role'),
        ('send_notification', 'Send Notification'),
        ('export_data', 'Export User Data')
    ])
    
    # For role changes
    new_role = SelectField('New Role', choices=[
        ('user', 'User'),
        ('admin', 'Administrator')
    ])
    
    # For notifications
    notification_subject = StringField('Notification Subject')
    notification_message = TextAreaField('Notification Message')
    
    # Confirmation
    confirm_action = BooleanField('I confirm this bulk action')
    
    execute_bulk_action = SubmitField('Execute Action')
    
    def validate_confirm_action(self, confirm_action):
        if not confirm_action.data:
            raise ValidationError('You must confirm the bulk action.')