# app/modules/routes.py
from flask import Blueprint, render_template, redirect, url_for

modules_bp = Blueprint('modules', __name__, url_prefix='/modules')

@modules_bp.route('/')
def index():
    return render_template('modules/index.html', title='Modules', modules=[], categories=[])

@modules_bp.route('/shop')
def shop():
    return render_template('modules/shop.html', title='Module Shop', modules=[], categories=[])