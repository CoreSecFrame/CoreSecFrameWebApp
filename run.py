# run.py
from app import create_app, socketio, db
from app.auth.models import User

app = create_app()

@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User}

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0')