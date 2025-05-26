from app import create_app, socketio
from app.gui.models import GUIApplication, GUISession, GUICategory, GUISessionLog

app = create_app()

if __name__ == '__main__':
    socketio.run(app, debug=False, host='0.0.0.0')
