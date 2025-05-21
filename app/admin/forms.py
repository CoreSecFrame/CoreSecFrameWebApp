# app/admin/forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, SubmitField
from wtforms.validators import DataRequired, Email, Length, Optional, ValidationError
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