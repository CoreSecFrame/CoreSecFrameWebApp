"""
BetterMITM - Advanced Bettercap GUI Interface
Enhanced web interface for network security testing with Bettercap
"""

from flask import Blueprint

bettermitm_bp = Blueprint(
    'bettermitm',
    __name__,
    template_folder='templates',
    static_folder='static',
    url_prefix='/bettermitm'
)

from . import routes