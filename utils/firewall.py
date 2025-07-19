from flask import request, abort
from utils.siem import log_siem_event
from datetime import datetime, timedelta
from collections import defaultdict
from models import db, BlockedIP

# In-memory blocklist and rate limit store (replace with DB/Redis for production)
BLOCKED_IPS = set()
RATE_LIMITS = defaultdict(list)  # {ip: [timestamps]}
RATE_LIMIT = 100  # requests
RATE_PERIOD = timedelta(minutes=5)

# Add an IP to the blocklist
def add_blocked_ip(ip, reason=None, blocked_by=None):
    BLOCKED_IPS.add(ip)
    if not BlockedIP.query.filter_by(ip_address=ip).first():
        db.session.add(BlockedIP(ip_address=ip, reason=reason, blocked_by=blocked_by))
        db.session.commit()
    log_siem_event(
        event_type='ip_blocked',
        message=f'IP {ip} blocked. Reason: {reason or "manual"}',
        severity='warning',
        source='firewall',
        ip_address=ip,
        raw_data={'reason': reason, 'blocked_by': blocked_by}
    )

def is_blocked_ip(ip):
    if ip in BLOCKED_IPS:
        return True
    if BlockedIP.query.filter_by(ip_address=ip).first():
        BLOCKED_IPS.add(ip)
        return True
    return False

def unblock_ip(ip, reason=None):
    BLOCKED_IPS.discard(ip)
    blocked = BlockedIP.query.filter_by(ip_address=ip).first()
    if blocked:
        db.session.delete(blocked)
        db.session.commit()
    log_siem_event(
        event_type='ip_unblocked',
        message=f'IP {ip} unblocked. Reason: {reason or "manual"}',
        severity='info',
        source='firewall',
        ip_address=ip,
        raw_data={'reason': reason}
    )

def get_blocked_ips():
    return [b.ip_address for b in BlockedIP.query.all()]

# Middleware function
def firewall_middleware(app):
    @app.before_request
    def check_firewall():
        ip = request.remote_addr
        # Blocked IP
        if is_blocked_ip(ip):
            log_siem_event(
                event_type='blocked_request',
                message=f'Blocked request from {ip}',
                severity='critical',
                source='firewall',
                ip_address=ip
            )
            abort(403)
        # Rate limiting
        now = datetime.utcnow()
        timestamps = RATE_LIMITS[ip]
        # Remove old timestamps
        RATE_LIMITS[ip] = [t for t in timestamps if now - t < RATE_PERIOD]
        if len(RATE_LIMITS[ip]) >= RATE_LIMIT:
            add_blocked_ip(ip, reason='rate_limit')
            abort(429)
        RATE_LIMITS[ip].append(now)
        # Suspicious pattern example (extend as needed)
        if '/admin' in request.path and request.method == 'POST' and not request.user_agent.string.lower().startswith('mozilla'):
            log_siem_event(
                event_type='suspicious_request',
                message=f'Suspicious admin POST from {ip}',
                severity='warning',
                source='firewall',
                ip_address=ip,
                raw_data={'path': request.path, 'user_agent': request.user_agent.string}
            )
    return app 