# app/auth/routes.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, current_user, login_required
from app import db
from app.auth.models import User
from app.auth.forms import LoginForm, RegistrationForm
from datetime import datetime
import traceback

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

def _handle_auth_exception(e, operation_name):
    """Helper function to log and flash authentication errors."""
    current_app.logger.error(f"{operation_name} error: {str(e)}")
    current_app.logger.error(traceback.format_exc())
    flash(f'An error occurred during {operation_name.lower()}. Please try again.', 'danger')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('core.index'))
    form = LoginForm()
    if form.validate_on_submit():
        try:
            user = User.query.filter_by(username=form.username.data).first()
            if user is None or not user.check_password(form.password.data):
                flash('Invalid username or password', 'danger')
                return redirect(url_for('auth.login'))
            login_user(user, remember=form.remember_me.data)
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            next_page = request.args.get('next')
            if not next_page or not next_page.startswith('/'):
                next_page = url_for('core.index')
            return redirect(next_page)
        except Exception as e:
            _handle_auth_exception(e, "Login")
    return render_template('auth/login.html', title='Sign In', form=form)

@auth_bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('core.index'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('core.index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        try:
            user = User(username=form.username.data, email=form.email.data)
            user.set_password(form.password.data)
            
            # Make the first registered user an admin
            if User.query.count() == 0:
                user.role = 'admin'
                current_app.logger.info("Setting as admin (first user)")
            
            db.session.add(user)
            db.session.commit()
            flash('Congratulations, you are now a registered user!', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback() # Keep rollback here as it's specific to DB operations
            _handle_auth_exception(e, "Registration")
    return render_template('auth/register.html', title='Register', form=form)

@auth_bp.route('/profile')
@login_required
def profile():
    return render_template('auth/profile.html', title='User Profile')