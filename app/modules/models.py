# app/modules/models.py
from app import db
from datetime import datetime

class Module(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), index=True, unique=True)
    description = db.Column(db.Text)
    category = db.Column(db.String(64), index=True)
    command = db.Column(db.String(128))
    remote_url = db.Column(db.String(256), nullable=True)
    local_path = db.Column(db.String(256))
    installed = db.Column(db.Boolean, default=False)
    installed_date = db.Column(db.DateTime, nullable=True)
    last_used = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ModuleCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), index=True, unique=True)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)