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
        {"name": "Forum Legend", "description": "Create 100 posts.", "icon": "fas fa-crown", "type": "post", "criteria": "posts>=100"},
        
        # Comment achievements
        {"name": "First Comment", "description": "Leave your first comment.", "icon": "fas fa-comment", "type": "comment", "criteria": "comments>=1"},
        {"name": "Active Commenter", "description": "Leave 25 comments.", "icon": "fas fa-comments", "type": "comment", "criteria": "comments>=25"},
        {"name": "Discussion Master", "description": "Leave 100 comments.", "icon": "fas fa-comment-dots", "type": "comment", "criteria": "comments>=100"},
        
        # Reaction achievements
        {"name": "First Reaction", "description": "Give or receive your first reaction.", "icon": "fas fa-smile", "type": "reaction", "criteria": "total_reactions>=1"},
        {"name": "Reaction King", "description": "Give or receive 100 reactions.", "icon": "fas fa-crown", "type": "reaction", "criteria": "total_reactions>=100"},
        {"name": "Reaction Master", "description": "Give or receive 500 reactions.", "icon": "fas fa-fire", "type": "reaction", "criteria": "total_reactions>=500"},
        
        # Lab achievements
        {"name": "Lab Explorer", "description": "Complete your first lab.", "icon": "fas fa-flask", "type": "lab", "criteria": "labs_completed>=1"},
        {"name": "Lab Enthusiast", "description": "Complete 5 labs.", "icon": "fas fa-vial", "type": "lab", "criteria": "labs_completed>=5"},
        {"name": "Lab Master", "description": "Complete 10 labs.", "icon": "fas fa-trophy", "type": "lab", "criteria": "labs_completed>=10"},
        {"name": "Lab Legend", "description": "Complete 25 labs.", "icon": "fas fa-medal", "type": "lab", "criteria": "labs_completed>=25"},
        {"name": "Lab Champion", "description": "Complete 50 labs.", "icon": "fas fa-gem", "type": "lab", "criteria": "labs_completed>=50"},
        
        # Streak achievements
        {"name": "3-Day Streak", "description": "Be active 3 days in a row.", "icon": "fas fa-fire", "type": "streak", "criteria": "current_streak>=3"},
        {"name": "7-Day Streak", "description": "Be active 7 days in a row.", "icon": "fas fa-bolt", "type": "streak", "criteria": "current_streak>=7"},
        {"name": "14-Day Streak", "description": "Be active 14 days in a row.", "icon": "fas fa-meteor", "type": "streak", "criteria": "current_streak>=14"},
        {"name": "30-Day Streak", "description": "Be active 30 days in a row.", "icon": "fas fa-infinity", "type": "streak", "criteria": "current_streak>=30"},
        {"name": "60-Day Streak", "description": "Be active 60 days in a row.", "icon": "fas fa-dragon", "type": "streak", "criteria": "current_streak>=60"},
        {"name": "100-Day Streak", "description": "Be active 100 days in a row.", "icon": "fas fa-crown", "type": "streak", "criteria": "current_streak>=100"},
        
        # Reputation achievements
        {"name": "Rising Star", "description": "Reach 100 reputation points.", "icon": "fas fa-star", "type": "reputation", "criteria": "reputation>=100"},
        {"name": "Respected Member", "description": "Reach 500 reputation points.", "icon": "fas fa-star-half-alt", "type": "reputation", "criteria": "reputation>=500"},
        {"name": "Community Leader", "description": "Reach 1000 reputation points.", "icon": "fas fa-star-of-life", "type": "reputation", "criteria": "reputation>=1000"},
        {"name": "Legendary Status", "description": "Reach 5000 reputation points.", "icon": "fas fa-crown", "type": "reputation", "criteria": "reputation>=5000"},
        
        # Social achievements
        {"name": "First Follower", "description": "Gain your first follower.", "icon": "fas fa-user-plus", "type": "social", "criteria": "followers>=1"},
        {"name": "Popular", "description": "Gain 10 followers.", "icon": "fas fa-users", "type": "social", "criteria": "followers>=10"},
        {"name": "Influencer", "description": "Gain 50 followers.", "icon": "fas fa-user-friends", "type": "social", "criteria": "followers>=50"},
        {"name": "Community Icon", "description": "Gain 100 followers.", "icon": "fas fa-user-graduate", "type": "social", "criteria": "followers>=100"},
        
        # Time-based achievements
        {"name": "Newcomer", "description": "Join the community.", "icon": "fas fa-user", "type": "time", "criteria": "days_since_joined>=1"},
        {"name": "Regular", "description": "Be a member for 30 days.", "icon": "fas fa-calendar-check", "type": "time", "criteria": "days_since_joined>=30"},
        {"name": "Veteran", "description": "Be a member for 100 days.", "icon": "fas fa-calendar-alt", "type": "time", "criteria": "days_since_joined>=100"},
        {"name": "Elder", "description": "Be a member for 365 days.", "icon": "fas fa-calendar-day", "type": "time", "criteria": "days_since_joined>=365"},
        
        # Special achievements
        {"name": "First Blood", "description": "Complete your first lab", "icon": "fas fa-tint", "type": "special", "criteria": "labs_completed>=1"},
        {"name": "Social Butterfly", "description": "Make 10 posts and gain 10 followers", "icon": "fas fa-butterfly", "type": "special", "criteria": "posts>=10 and followers>=10"},
        {"name": "Well Rounded", "description": "Have at least 5 posts, 5 labs, and 5 days streak", "icon": "fas fa-circle", "type": "special", "criteria": "posts>=5 and labs_completed>=5 and current_streak>=5"},
        {"name": "Community Pillar", "description": "Reach 1000 reputation and 50 followers", "icon": "fas fa-pillar", "type": "special", "criteria": "reputation>=1000 and followers>=50"},
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