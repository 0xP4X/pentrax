import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional, List
import os
from flask import current_app
from models import AdminSettings

class EmailService:
    """Email service for sending emails via SMTP"""
    
    def __init__(self):
        self.settings = self._load_smtp_settings()
    
    def _load_smtp_settings(self) -> dict:
        """Load SMTP settings from database"""
        from app import db
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
    
    def is_configured(self) -> bool:
        """Check if SMTP is properly configured"""
        required_fields = ['smtp_server', 'smtp_port', 'smtp_username', 'smtp_password']
        return all(self.settings.get(field) for field in required_fields)
    
    def send_email(self, to_email: str, subject: str, body: str, 
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
        if not self.is_configured():
            current_app.logger.error("SMTP not configured")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = f"{self.settings.get('smtp_from_name', 'PentraX Admin')} <{self.settings.get('smtp_from_email', self.settings.get('smtp_username'))}>"
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
            server = self._connect_smtp()
            if not server:
                return False
            
            # Send email
            server.send_message(msg)
            server.quit()
            
            current_app.logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            current_app.logger.error(f"Failed to send email: {str(e)}")
            return False
    
    def _connect_smtp(self) -> Optional[smtplib.SMTP]:
        """Connect to SMTP server with proper authentication"""
        try:
            server = smtplib.SMTP(self.settings['smtp_server'], int(self.settings['smtp_port']))
            
            # Start TLS if required
            if self.settings.get('smtp_use_tls', 'false').lower() == 'true':
                server.starttls(context=ssl.create_default_context())
            
            # Login
            server.login(self.settings['smtp_username'], self.settings['smtp_password'])
            
            return server
            
        except Exception as e:
            current_app.logger.error(f"SMTP connection failed: {str(e)}")
            return None
    
    def test_connection(self) -> dict:
        """Test SMTP connection and return status"""
        if not self.is_configured():
            return {
                'success': False,
                'message': 'SMTP not configured. Please configure all required settings.'
            }
        
        try:
            server = self._connect_smtp()
            if server:
                server.quit()
                return {
                    'success': True,
                    'message': 'SMTP connection successful!'
                }
            else:
                return {
                    'success': False,
                    'message': 'Failed to connect to SMTP server.'
                }
        except Exception as e:
            return {
                'success': False,
                'message': f'SMTP connection failed: {str(e)}'
            }
    
    def send_contact_reply(self, contact_email: str, contact_name: str, 
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
        
        return self.send_email(contact_email, subject, body, html_body)
    
    def send_notification_email(self, to_email: str, subject: str, 
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
        
        return self.send_email(to_email, subject, body, html_body)

# Global email service instance
email_service = EmailService() 