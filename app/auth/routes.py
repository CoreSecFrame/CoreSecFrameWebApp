# app/auth/routes.py
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user, login_required
from app import db
from app.auth.models import User
from app.auth.forms import LoginForm, RegistrationForm
from datetime import datetime

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('core.index'))
    form = LoginForm()
    if form.validate_on_submit():
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
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        
        # Make the first registered user an admin
        if User.query.count() == 0:
            user.role = 'admin'
            
        db.session.add(user)
        db.session.commit()
        flash('Congratulations, you are now a registered user!', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/register.html', title='Register', form=form)

@auth_bp.route('/profile')
@login_required
def profile():
    return render_template('auth/profile.html', title='User Profile')