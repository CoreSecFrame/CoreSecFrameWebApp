from flask import Blueprint

bp = Blueprint('file_manager', __name__, template_folder='templates')

from app.file_manager import routes
