from models import db, SIEMEvent
from flask_login import current_user
from datetime import datetime
from flask import request
import requests

# Replace with your AbuseIPDB API key if available
ABUSEIPDB_API_KEY = None  # Set to your key for abuse reports

# Deep IP info function for on-demand scans

def get_deep_ip_info(ip):
    result = {}
    # ip-api.com (geo)
    try:
        resp = requests.get(f'http://ip-api.com/json/{ip}?fields=status,message,country,regionName,city,zip,lat,lon,isp,org,as,query', timeout=2)
        data = resp.json()
        if data.get('status') == 'success':
            result['geo'] = data
    except Exception as e:
        result['geo_error'] = str(e)
    # ipinfo.io (ASN, org, privacy)
    try:
        resp = requests.get(f'https://ipinfo.io/{ip}/json', timeout=2)
        if resp.status_code == 200:
            result['ipinfo'] = resp.json()
    except Exception as e:
        result['ipinfo_error'] = str(e)
    # AbuseIPDB (abuse/blacklist)
    if ABUSEIPDB_API_KEY:
        try:
            resp = requests.get(
                'https://api.abuseipdb.com/api/v2/check',
                params={'ipAddress': ip, 'maxAgeInDays': 90},
                headers={'Key': ABUSEIPDB_API_KEY, 'Accept': 'application/json'},
                timeout=3
            )
            if resp.status_code == 200:
                result['abuseipdb'] = resp.json().get('data', {})
        except Exception as e:
            result['abuseipdb_error'] = str(e)
    return result

def enrich_ip_info(ip):
    # Use only fast geo for event logging, deep scan for on-demand
    try:
        resp = requests.get(f'http://ip-api.com/json/{ip}?fields=status,message,country,regionName,city,zip,lat,lon,isp,org,as,query', timeout=2)
        data = resp.json()
        if data.get('status') == 'success':
            return data
    except Exception as e:
        return {'error': str(e)}
    return None

def log_siem_event(event_type, message, severity='info', source=None, user=None, ip_address=None, raw_data=None):
    if ip_address and (not raw_data or 'ip_info' not in (raw_data or {})):
        ip_info = enrich_ip_info(ip_address)
        if raw_data is None:
            raw_data = {}
        raw_data['ip_info'] = ip_info
    if user is None:
        user = getattr(current_user, '_get_current_object', lambda: None)()
    user_id = user.id if user and hasattr(user, 'is_authenticated') and user.is_authenticated else None
    username = user.username if user and hasattr(user, 'is_authenticated') and user.is_authenticated else None
    event = SIEMEvent(
        event_type=event_type,
        user_id=user_id,
        username=username,
        ip_address=ip_address or (request.remote_addr if request else None),
        source=source,
        severity=severity,
        message=message,
        raw_data=raw_data,
        timestamp=datetime.utcnow()
    )
    db.session.add(event)
    db.session.commit()
    return event 