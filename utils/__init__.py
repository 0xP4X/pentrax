# Utils package 

import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional, List
from app import db
from models import Notification, AdminSettings

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

# Email Service Functions
def get_smtp_settings():
    """Get SMTP settings from database"""
    settings = {}
    smtp_settings = AdminSettings.query.filter(
        AdminSettings.key.in_([
            'smtp_server', 'smtp_port', 'smtp_username', 
            'smtp_password', 'smtp_use_tls', 'smtp_use_ssl',
            'smtp_from_email', 'smtp_from_name'
        ])
    ).all()
    
    for setting in smtp_settings:
        settings[setting.key] = setting.value
    
    return settings

def is_smtp_configured():
    """Check if SMTP is properly configured"""
    settings = get_smtp_settings()
    required_fields = ['smtp_server', 'smtp_port', 'smtp_username', 'smtp_password']
    return all(settings.get(field) for field in required_fields)

def send_email(to_email: str, subject: str, body: str, 
               html_body: Optional[str] = None, 
               attachments: Optional[List[dict]] = None) -> bool:
    """
    Send an email via SMTP
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        body: Plain text body
        html_body: HTML body (optional)
        attachments: List of attachment dicts with 'filename' and 'content' keys
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    if not is_smtp_configured():
        return False
    
    settings = get_smtp_settings()
    
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['From'] = f"{settings.get('smtp_from_name', 'PentraX Admin')} <{settings.get('smtp_from_email', settings.get('smtp_username'))}>"
        msg['To'] = to_email
        msg['Subject'] = subject
        
        # Add plain text body
        text_part = MIMEText(body, 'plain', 'utf-8')
        msg.attach(text_part)
        
        # Add HTML body if provided
        if html_body:
            html_part = MIMEText(html_body, 'html', 'utf-8')
            msg.attach(html_part)
        
        # Add attachments if provided
        if attachments:
            for attachment in attachments:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment['content'])
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= {attachment["filename"]}'
                )
                msg.attach(part)
        
        # Connect to SMTP server
        server = _connect_smtp(settings)
        if not server:
            return False
        
        # Send email
        server.send_message(msg)
        server.quit()
        
        return True
        
    except Exception as e:
        print(f"Failed to send email: {str(e)}")
        return False

def _connect_smtp(settings: dict):
    """Connect to SMTP server with proper authentication"""
    try:
        server = smtplib.SMTP(settings['smtp_server'], int(settings['smtp_port']))
        
        # Start TLS if required
        if settings.get('smtp_use_tls', 'false').lower() == 'true':
            server.starttls(context=ssl.create_default_context())
        
        # Login
        server.login(settings['smtp_username'], settings['smtp_password'])
        
        return server
        
    except Exception as e:
        print(f"SMTP connection failed: {str(e)}")
        return None

def send_contact_reply(contact_email: str, contact_name: str, 
                      original_subject: str, reply_message: str, 
                      admin_name: str) -> bool:
    """
    Send a reply to a user's contact form submission
    
    Args:
        contact_email: User's email address
        contact_name: User's name
        original_subject: Original contact form subject
        reply_message: Admin's reply message
        admin_name: Admin's name
    
    Returns:
        bool: True if email sent successfully
    """
    subject = f"Re: {original_subject}"
    
    # Plain text body
    body = f"""Dear {contact_name},

Thank you for contacting PentraX support.

{reply_message}

Best regards,
{admin_name}
PentraX Support Team

---
This is a reply to your original message: "{original_subject}"
"""
    
    # HTML body
    html_body = f"""
    <html>
    <body>
        <p>Dear {contact_name},</p>
        
        <p>Thank you for contacting PentraX support.</p>
        
        <div style="background-color: #f8f9fa; padding: 15px; border-left: 4px solid #007bff; margin: 20px 0;">
            {reply_message.replace(chr(10), '<br>')}
        </div>
        
        <p>Best regards,<br>
        <strong>{admin_name}</strong><br>
        PentraX Support Team</p>
        
        <hr style="margin: 30px 0; border: none; border-top: 1px solid #ddd;">
        <p style="color: #666; font-size: 12px;">
            This is a reply to your original message: "{original_subject}"
        </p>
    </body>
    </html>
    """
    
    return send_email(contact_email, subject, body, html_body)

def send_notification_email(to_email: str, subject: str, 
                           message: str, notification_type: str = 'general') -> bool:
    """
    Send a notification email to users
    
    Args:
        to_email: Recipient email
        subject: Email subject
        message: Email message
        notification_type: Type of notification (general, security, etc.)
    
    Returns:
        bool: True if email sent successfully
    """
    # Plain text body
    body = f"""PentraX Notification

{message}

Best regards,
PentraX Team

---
You received this email because you have notifications enabled for {notification_type} updates.
"""
    
    # HTML body
    html_body = f"""
    <html>
    <body>
        <h2 style="color: #007bff;">PentraX Notification</h2>
        
        <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
            {message.replace(chr(10), '<br>')}
        </div>
        
        <p>Best regards,<br>
        <strong>PentraX Team</strong></p>
        
        <hr style="margin: 30px 0; border: none; border-top: 1px solid #ddd;">
        <p style="color: #666; font-size: 12px;">
            You received this email because you have notifications enabled for {notification_type} updates.
        </p>
    </body>
    </html>
    """
    
    return send_email(to_email, subject, body, html_body) 