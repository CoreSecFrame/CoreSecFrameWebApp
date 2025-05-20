# init_db.py
from app import create_app, db
from app.auth.models import User
from app.modules.models import Module, ModuleCategory
from app.terminal.models import TerminalSession, TerminalLog
from datetime import datetime

app = create_app()

with app.app_context():
    # Drop all tables and recreate
    print("Dropping all tables...")
    db.drop_all()
    
    print("Creating all tables...")
    db.create_all()
    
    # Create admin user
    print("Creating admin user...")
    admin = User(username='admin', email='admin@example.com', role='admin')
    admin.set_password('admin')
    db.session.add(admin)
    
    # Create a regular user
    print("Creating regular user...")
    user = User(username='user', email='user@example.com', role='user')
    user.set_password('password')
    db.session.add(user)
    
    # Create module categories
    print("Creating module categories...")
    categories = [
        ModuleCategory(name='Reconnaissance'),
        ModuleCategory(name='Vulnerability Analysis'),
        ModuleCategory(name='Exploitation'),
        ModuleCategory(name='Post Exploitation'),
        ModuleCategory(name='Reporting'),
        ModuleCategory(name='Utils')
    ]
    db.session.add_all(categories)
    
    # Create a sample module
    print("Creating sample module...")
    example_module = Module(
        name='Example',
        description='Example module for demonstration',
        category='Utils',
        command='echo',
        local_path='/app/modules/example.py',
        installed=True
    )
    db.session.add(example_module)
    
    # Commit the changes
    print("Committing changes...")
    db.session.commit()
    
    print("Database initialization complete!")