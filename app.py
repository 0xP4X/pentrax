import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_login import LoginManager
from dotenv import load_dotenv
from flask_socketio import SocketIO, emit, join_room, leave_room
import eventlet
# import pty  # Commented out for Windows compatibility
# import select  # Commented out for Windows compatibility
import subprocess
from datetime import datetime

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
database_url = os.environ.get("DATABASE_URL", "postgresql://postgres.lmpticqxipcdkpcmfpvi:HH8m1MvSUtxBjTKV@aws-0-eu-north-1.pooler.supabase.com:5432/postgres")
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

# Real-time messaging events
@socketio.on('join_conversation')
def handle_join_conversation(data):
    room = f"conversation_{data['conversation_id']}"
    join_room(room)
    emit('user_joined', {'user_id': data['user_id']}, room=room)

@socketio.on('leave_conversation')
def handle_leave_conversation(data):
    room = f"conversation_{data['conversation_id']}"
    leave_room(room)
    emit('user_left', {'user_id': data['user_id']}, room=room)

@socketio.on('send_message')
def handle_send_message(data):
    # data: {conversation_id, sender_id, content, attachment_url (optional), attachment_type (optional)}
    from models import Message, Conversation, ConversationParticipant, User
    from flask_login import current_user
    from datetime import datetime
    from app import db
    from utils import create_notification
    
    message = Message(
        conversation_id=data['conversation_id'],
        sender_id=data['sender_id'],
        content=data['content'],
        attachment_url=data.get('attachment_url'),
        attachment_type=data.get('attachment_type'),
        created_at=datetime.utcnow()
    )
    db.session.add(message)
    
    # Update conversation timestamp
    conversation = Conversation.query.get(data['conversation_id'])
    conversation.updated_at = datetime.utcnow()
    
    # Get other participants for notifications
    other_participants = ConversationParticipant.query.filter(
        ConversationParticipant.conversation_id == data['conversation_id'],
        ConversationParticipant.user_id != data['sender_id']
    ).all()
    
    db.session.commit()
    
    # Create notifications for other participants
    sender = User.query.get(data['sender_id'])
    for participant in other_participants:
        create_notification(
            participant.user_id,
            f'New message from {sender.username}',
            f'{sender.username}: {data["content"][:50]}{"..." if len(data["content"]) > 50 else ""}'
        )
    
    # Broadcast to room
    room = f"conversation_{data['conversation_id']}"
    emit('receive_message', {
        'id': message.id,
        'conversation_id': message.conversation_id,
        'sender_id': message.sender_id,
        'content': message.content,
        'attachment_url': message.attachment_url,
        'attachment_type': message.attachment_type,
        'created_at': message.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        'is_read': message.is_read
    }, room=room)

@socketio.on('typing')
def handle_typing(data):
    # data: {conversation_id, user_id}
    room = f"conversation_{data['conversation_id']}"
    emit('typing', {'user_id': data['user_id']}, room=room, include_self=False)

@socketio.on('read_message')
def handle_read_message(data):
    # data: {conversation_id, user_id, message_id}
    from models import Message, MessageReadReceipt
    from app import db
    message = Message.query.get(data['message_id'])
    if message and not message.is_read:
        message.is_read = True
        receipt = MessageReadReceipt(message_id=message.id, user_id=data['user_id'])
        db.session.add(receipt)
        db.session.commit()
        room = f"conversation_{data['conversation_id']}"
        emit('message_read', {'message_id': message.id, 'user_id': data['user_id']}, room=room)

@socketio.on('edit_message')
def handle_edit_message(data):
    # data: {message_id, conversation_id, content}
    from models import Message
    from app import db
    message = Message.query.get(data['message_id'])
    if message and message.sender_id == data.get('sender_id'):
        message.content = data['content']
        db.session.commit()
        room = f"conversation_{data['conversation_id']}"
        emit('message_edited', {
            'message_id': message.id,
            'content': message.content
        }, room=room)

@socketio.on('delete_message')
def handle_delete_message(data):
    # data: {message_id, conversation_id}
    from models import Message
    from app import db
    message = Message.query.get(data['message_id'])
    if message and message.sender_id == data.get('sender_id'):
        message_id = message.id
        db.session.delete(message)
        db.session.commit()
        room = f"conversation_{data['conversation_id']}"
        emit('message_deleted', {'message_id': message_id}, room=room)

@socketio.on('add_reaction')
def handle_add_reaction(data):
    # data: {message_id, conversation_id, emoji, user_id}
    from models import Message, MessageReaction
    from app import db
    message = Message.query.get(data['message_id'])
    if message:
        # Check if reaction already exists
        existing_reaction = MessageReaction.query.filter_by(
            message_id=data['message_id'],
            user_id=data['user_id'],
            emoji=data['emoji']
        ).first()
        
        if existing_reaction:
            # Remove reaction (toggle)
            db.session.delete(existing_reaction)
        else:
            # Add reaction
            reaction = MessageReaction(
                message_id=data['message_id'],
                user_id=data['user_id'],
                emoji=data['emoji']
            )
            db.session.add(reaction)
        
        db.session.commit()
        
        # Get reaction count
        reaction_count = MessageReaction.query.filter_by(
            message_id=data['message_id'],
            emoji=data['emoji']
        ).count()
        
        room = f"conversation_{data['conversation_id']}"
        emit('reaction_added', {
            'message_id': data['message_id'],
            'emoji': data['emoji'],
            'count': reaction_count
        }, room=room)

@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))

# Ensure upload directory exists
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# Import routes
from routes import *

@app.context_processor
def inject_now():
    return {'current_year': datetime.now().year}

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
    # This block is for local development only.
    with app.app_context():
        from models import User
        db.create_all()
        from werkzeug.security import generate_password_hash
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            admin_user = User(
                username='admin',
                email='admpentrax@gmail.com',
                password_hash=generate_password_hash('password123'),
                is_admin=True,
                bio='System Administrator',
                skills='System Administration, Security'
            )
            db.session.add(admin_user)
            db.session.commit()
            logging.info("Admin user created with username: admin, password: password123")
    # For development only:
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)

# For production, use Gunicorn with eventlet:
# gunicorn --worker-class eventlet -w 1 app:app 