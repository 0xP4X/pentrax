import os
from app import db
from models import Notification

ALLOWED_EXTENSIONS = {'txt', 'py', 'sh', 'rb', 'pl', 'php', 'js', 'html', 'css', 'json', 'xml', 'md', 'zip', 'tar', 'gz'}

def allowed_file(filename):
    """Check if uploaded file has allowed extension"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def create_notification(user_id, title, message):
    """Create a notification for a user"""
    notification = Notification(
        user_id=user_id,
        title=title,
        message=message
    )
    db.session.add(notification)
    db.session.commit()

def get_file_icon(filename):
    """Get appropriate icon class for file type"""
    if not filename:
        return 'fas fa-file'
    
    extension = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    
    icon_map = {
        'py': 'fab fa-python',
        'js': 'fab fa-js-square',
        'html': 'fab fa-html5',
        'css': 'fab fa-css3-alt',
        'php': 'fab fa-php',
        'rb': 'fas fa-gem',
        'sh': 'fas fa-terminal',
        'md': 'fab fa-markdown',
        'json': 'fas fa-code',
        'xml': 'fas fa-code',
        'zip': 'fas fa-file-archive',
        'tar': 'fas fa-file-archive',
        'gz': 'fas fa-file-archive',
    }
    
    return icon_map.get(extension, 'fas fa-file-code')

def format_file_size(size_bytes):
    """Format file size in human readable format"""
    if size_bytes == 0:
        return "0B"
    
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f}{size_names[i]}"
