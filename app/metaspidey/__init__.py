from flask import Blueprint

metaspidey_bp = Blueprint('metaspidey', __name__)

from app.metaspidey import routes