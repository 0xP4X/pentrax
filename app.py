import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_login import LoginManager
from dotenv import load_dotenv
from flask_socketio import SocketIO, emit
import eventlet
# import pty  # Commented out for Windows compatibility
# import select  # Commented out for Windows compatibility
import subprocess

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
migrate = Migrate()

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure the database - use Supabase PostgreSQL
database_url = os.environ.get("DATABASE_URL", "postgresql://postgres.dmhjkqwtorscryuivxht:oIVPpgKI7TAQPavI@aws-0-eu-central-1.pooler.supabase.com:5432/postgres")
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# File upload configuration
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max file size
app.config["UPLOAD_FOLDER"] = "uploads"

# Initialize extensions
db.init_app(app)
migrate.init_app(app, db)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

socketio = SocketIO(app, async_mode='eventlet')

@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))

# Ensure upload directory exists
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# Import routes
from routes import *

# Terminal functionality commented out for Windows compatibility
# @socketio.on('start_terminal', namespace='/terminals')
# def start_terminal(message):
#     # Spawn a shell
#     (child_pid, fd) = pty.fork()
#     if child_pid == 0:
#         # Child process: replace with shell
#         os.execvp('bash', ['bash'])
#     else:
#         # Parent: read/write to fd
#         eventlet.spawn_n(read_and_forward_pty, fd)
#         # Save fd in session for this socket
#         socketio.server.environ[socketio.server.eio_sid]['pty_fd'] = fd

# @socketio.on('input', namespace='/terminals')
# def terminal_input(data):
#     fd = socketio.server.environ[socketio.server.eio_sid].get('pty_fd')
#     if fd:
#         os.write(fd, data['input'].encode())

# def read_and_forward_pty(fd):
#     while True:
#         eventlet.sleep(0.01)
#         if select.select([fd], [], [], 0)[0]:
#             output = os.read(fd, 1024).decode(errors='ignore')
#             socketio.emit('output', {'output': output}, namespace='/terminals')

if __name__ == '__main__':
    with app.app_context():
        # Import models to ensure tables are created
        from models import User
        db.create_all()
        
        # Create admin user if it doesn't exist
        from werkzeug.security import generate_password_hash
        
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            admin_user = User(
                username='admin',
                email='admin@pentrax.com',
                password_hash=generate_password_hash('password123'),
                is_admin=True,
                bio='System Administrator',
                skills='System Administration, Security'
            )
            db.session.add(admin_user)
            db.session.commit()
            logging.info("Admin user created with username: admin, password: password123")
    
    socketio.run(app, debug=True, host='0.0.0.0', port=5000) 