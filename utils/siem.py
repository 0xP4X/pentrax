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

# Patch log_siem_event to enrich IP info
old_log_siem_event = log_siem_event

def log_siem_event(event_type, message, severity='info', source=None, user=None, ip_address=None, raw_data=None):
    if ip_address and (not raw_data or 'ip_info' not in (raw_data or {})):
        ip_info = enrich_ip_info(ip_address)
        if raw_data is None:
            raw_data = {}
        raw_data['ip_info'] = ip_info
    return old_log_siem_event(event_type, message, severity, source, user, ip_address, raw_data) 