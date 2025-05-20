# app/admin/routes.py
from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.auth.models import User

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/')
@login_required
def index():
    if not current_user.is_admin():
        flash('You do not have permission to access the admin panel.', 'danger')
        return redirect(url_for('core.index'))
    
    users = User.query.all()
    return render_template('admin/index.html', title='Admin Panel', users=users)