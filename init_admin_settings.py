#!/usr/bin/env python3
"""
Script to initialize default admin settings
"""
from app import app, db
from models import AdminSettings, User, Achievement
from datetime import datetime

def init_admin_settings():
    with app.app_context():
        # Get admin user
        admin_user = User.query.filter_by(username='admin').first()
        
        if not admin_user:
            print("Admin user not found!")
            return
        
        # Default settings
        default_settings = [
            {
                'key': 'paystack_public_key',
                'value': 'pk_test_your_public_key_here',
                'description': 'Paystack Public Key for Payments'
            },
            {
                'key': 'paystack_secret_key',
                'value': 'sk_test_your_secret_key_here',
                'description': 'Paystack Secret Key for Payments'
            },
            {
                'key': 'openai_api_key',
                'value': '',
                'description': 'OpenAI API Key for AI Assistant'
            },
            {
                'key': 'commission_rate',
                'value': '15',
                'description': 'Platform Commission Rate (%)'
            },
            {
                'key': 'platform_name',
                'value': 'PentraX',
                'description': 'Platform Name'
            },
            {
                'key': 'max_file_size',
                'value': '16',
                'description': 'Maximum File Upload Size (MB)'
            }
        ]
        
        # Add or update settings
        for setting_data in default_settings:
            existing_setting = AdminSettings.query.filter_by(key=setting_data['key']).first()
            
            if existing_setting:
                print(f"Setting already exists: {setting_data['key']}")
            else:
                setting = AdminSettings(
                    key=setting_data['key'],
                    value=setting_data['value'],
                    description=setting_data['description'],
                    updated_by=admin_user.id
                )
                db.session.add(setting)
                print(f"Added setting: {setting_data['key']}")
        
        db.session.commit()
        print("\n✅ Admin settings initialized successfully!")
        print("\n📝 Next steps:")
        print("1. Go to Admin Dashboard > Settings")
        print("2. Configure your Paystack API keys")
        print("3. Set up OpenAI API key for AI Assistant")
        print("4. Customize platform settings as needed")

def seed_achievements():
    default_achievements = [
        # Posting achievements
        {"name": "First Post", "description": "Create your first post.", "icon": "fas fa-feather-alt", "type": "post", "criteria": "posts>=1"},
        {"name": "Contributor", "description": "Create 10 posts.", "icon": "fas fa-pen-nib", "type": "post", "criteria": "posts>=10"},
        {"name": "Forum Star", "description": "Create 50 posts.", "icon": "fas fa-star", "type": "post", "criteria": "posts>=50"},
        # Reaction achievements
        {"name": "First Reaction", "description": "Give or receive your first reaction.", "icon": "fas fa-smile", "type": "reaction", "criteria": "reactions>=1"},
        {"name": "Reaction King", "description": "Give or receive 100 reactions.", "icon": "fas fa-crown", "type": "reaction", "criteria": "reactions>=100"},
        # Lab achievements
        {"name": "Lab Explorer", "description": "Complete your first lab.", "icon": "fas fa-flask", "type": "lab", "criteria": "labs_completed>=1"},
        {"name": "Lab Master", "description": "Complete 10 labs.", "icon": "fas fa-trophy", "type": "lab", "criteria": "labs_completed>=10"},
        # Streak achievements
        {"name": "3-Day Streak", "description": "Be active 3 days in a row.", "icon": "fas fa-fire", "type": "streak", "criteria": "streak>=3"},
        {"name": "7-Day Streak", "description": "Be active 7 days in a row.", "icon": "fas fa-bolt", "type": "streak", "criteria": "streak>=7"},
        {"name": "30-Day Streak", "description": "Be active 30 days in a row.", "icon": "fas fa-meteor", "type": "streak", "criteria": "streak>=30"},
    ]
    for ach in default_achievements:
        if not Achievement.query.filter_by(name=ach["name"]).first():
            db.session.add(Achievement(
                name=ach["name"],
                description=ach["description"],
                icon=ach["icon"],
                type=ach["type"],
                criteria=ach["criteria"],
                created_at=datetime.utcnow()
            ))
    db.session.commit()

if __name__ == "__main__":
    init_admin_settings()
    with app.app_context():
        seed_achievements() 