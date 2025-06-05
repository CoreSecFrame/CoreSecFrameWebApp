import os
import subprocess
from app import create_app, socketio

app = create_app()

if app:  # Ensure app object was created successfully
    # Import log_system_event if it's not already imported at the top of run.py
    # Assuming it might not be, let's add a local import for safety.
    from app.core.logging import log_system_event
    with app.app_context():
        log_system_event('application_ready', 'CoreSecFrame application initialized successfully')

def is_wsl_environment():
    """Detects if the app is running in a WSL environment"""
    try:
        with open("/proc/sys/kernel/osrelease", "r") as f:
            osrelease = f.read().lower()
            return "microsoft" in osrelease or "wsl" in osrelease
    except Exception:
        return False

if __name__ == '__main__':
    # The logic for starting noVNC service has been removed.
    # is_wsl_environment() function remains if needed elsewhere,
    # or can be removed if this was its only use.
    socketio.run(app, debug=False, host='0.0.0.0', allow_unsafe_werkzeug=True)
