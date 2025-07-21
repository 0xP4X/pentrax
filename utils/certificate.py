from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, Frame
from datetime import datetime
import os
import uuid

def generate_certificate(user_name, path_name, completion_date=None, cert_id=None, output_dir='static/certificates'):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    if not completion_date:
        completion_date = datetime.utcnow().strftime('%B %d, %Y')
    if not cert_id:
        cert_id = str(uuid.uuid4())[:8]
    file_name = f"certificate_{user_name.replace(' ', '_')}_{cert_id}.pdf"
    file_path = os.path.join(output_dir, file_name)

    c = canvas.Canvas(file_path, pagesize=A4)
    width, height = A4

    # Background
    c.setFillColorRGB(0.97, 0.98, 1)
    c.rect(0, 0, width, height, fill=1)

    # Border
    c.setStrokeColor(colors.HexColor('#1a237e'))
    c.setLineWidth(8)
    c.rect(30, 30, width-60, height-60, stroke=1, fill=0)

    # Title
    c.setFont('Helvetica-Bold', 32)
    c.setFillColor(colors.HexColor('#1a237e'))
    c.drawCentredString(width/2, height-120, 'Certificate of Completion')

    # Platform branding
    c.setFont('Helvetica-Bold', 20)
    c.setFillColor(colors.HexColor('#3949ab'))
    c.drawCentredString(width/2, height-160, 'PentraX Cybersecurity Platform')

    # Decorative line
    c.setStrokeColor(colors.HexColor('#3949ab'))
    c.setLineWidth(2)
    c.line(width*0.2, height-175, width*0.8, height-175)

    # Recipient
    c.setFont('Helvetica', 18)
    c.setFillColor(colors.black)
    c.drawCentredString(width/2, height-220, f"This certifies that")
    c.setFont('Helvetica-Bold', 24)
    c.setFillColor(colors.HexColor('#1a237e'))
    c.drawCentredString(width/2, height-260, user_name)

    # Path name
    c.setFont('Helvetica', 18)
    c.setFillColor(colors.black)
    c.drawCentredString(width/2, height-300, f"has successfully completed the learning path:")
    c.setFont('Helvetica-Bold', 20)
    c.setFillColor(colors.HexColor('#3949ab'))
    c.drawCentredString(width/2, height-340, f'“{path_name}”')

    # Date and cert ID
    c.setFont('Helvetica', 14)
    c.setFillColor(colors.black)
    c.drawString(60, 80, f'Date: {completion_date}')
    c.drawRightString(width-60, 80, f'Certificate ID: {cert_id}')

    # Signature
    c.setFont('Helvetica-Oblique', 16)
    c.setFillColor(colors.HexColor('#1a237e'))
    c.drawString(60, 130, '_________________________')
    c.setFont('Helvetica', 12)
    c.drawString(60, 115, 'PentraX Team')

    # Badge/Icon (optional)
    c.setFont('Helvetica-Bold', 40)
    c.setFillColor(colors.HexColor('#ffd600'))
    c.drawCentredString(width-120, 120, '★')

    c.save()
    return file_path 