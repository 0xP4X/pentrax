from models import db, SIEMEvent
from flask_login import current_user
from datetime import datetime
from flask import request
import requests

def enrich_ip_info(ip):
    try:
        resp = requests.get(f'http://ip-api.com/json/{ip}?fields=status,message,country,regionName,city,zip,lat,lon,isp,org,as,query', timeout=2)
        data = resp.json()
        if data.get('status') == 'success':
            return {
                'country': data.get('country'),
                'region': data.get('regionName'),
                'city': data.get('city'),
                'zip': data.get('zip'),
                'lat': data.get('lat'),
                'lon': data.get('lon'),
                'isp': data.get('isp'),
                'org': data.get('org'),
                'as': data.get('as'),
                'ip': data.get('query'),
            }
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
    event = SIEMEvent(
        event_type=event_type,
        user_id=user.id if user else None,
        username=user.username if user else None,
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