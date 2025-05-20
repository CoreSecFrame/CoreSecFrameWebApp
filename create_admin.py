# create_admin.py
from app import db
from app.auth.models import User
from datetime import datetime

# Check if admin user already exists
admin = User.query.filter_by(username='admin').first()

if not admin:
    print("Creating admin user...")
    admin = User(
        username='admin',
        email='admin@example.com',
        role='admin',
        created_at=datetime.utcnow()
    )
    admin.set_password('admin')  # Set a default password
    db.session.add(admin)
    db.session.commit()
    print("Admin user created successfully.")
else:
    print("Admin user already exists.")