# run.py
from app import create_app, socketio, db
from app.auth.models import User
from app.modules.models import Module, ModuleCategory
from app.terminal.models import TerminalSession, TerminalLog
import click
from app.gui.models import GUIApplication, GUISession, GUISessionEvent, WebRTCSignalingMessage


# Create the Flask application
app = create_app()
with app.app_context():
    db.create_all()

# Only register these if app was successfully created
if app:
    @app.shell_context_processor
    def make_shell_context():
        return {
            'db': db, 
            'User': User, 
            'Module': Module, 
            'ModuleCategory': ModuleCategory,
            'TerminalSession': TerminalSession,
            'TerminalLog': TerminalLog
        }

    @app.cli.command("init-db")
    def init_db():
        """Initialize the database with tables and sample data."""
        click.echo("Dropping all tables...")
        db.drop_all()
        
        click.echo("Creating all tables...")
        db.create_all()
        
        # Create admin user
        click.echo("Creating admin user...")
        admin = User(username='admin', email='admin@example.com', role='admin')
        admin.set_password('admin')
        db.session.add(admin)
        
        # Create a regular user
        click.echo("Creating regular user...")
        user = User(username='user', email='user@example.com', role='user')
        user.set_password('password')
        db.session.add(user)
        
        # Create module categories
        click.echo("Creating module categories...")
        categories = [
            ModuleCategory(name='Reconnaissance'),
            ModuleCategory(name='Vulnerability Analysis'),
            ModuleCategory(name='Exploitation'),
            ModuleCategory(name='Post Exploitation'),
            ModuleCategory(name='Reporting'),
            ModuleCategory(name='Utils')
        ]
        db.session.add_all(categories)
        
        # Create GUI application categories and basic applications
        click.echo("Creating GUI applications...")
        from app.gui.models import GUIApplication
        
        gui_apps = [
            GUIApplication(
                name='firefox',
                display_name='Firefox Browser',
                description='Mozilla Firefox web browser',
                command='firefox',
                icon='globe',
                category='Internet'
            ),
            GUIApplication(
                name='terminal',
                display_name='Terminal',
                description='System terminal',
                command='gnome-terminal',
                icon='terminal',
                category='System'
            ),
            GUIApplication(
                name='filemanager',
                display_name='File Manager',
                description='System file manager',
                command='nautilus',
                icon='folder',
                category='System'
            )
        ]
        
        for app in gui_apps:
            app.check_installed()
            db.session.add(app)
        
        # Commit the changes
        click.echo("Committing changes...")
        db.session.commit()
        
        click.echo("Database initialization complete!")

# Run the application if executed directly
if __name__ == '__main__':
    if app:
        socketio.run(app, debug=True, host='0.0.0.0')
    else:
        print("Error: Failed to create Flask application")