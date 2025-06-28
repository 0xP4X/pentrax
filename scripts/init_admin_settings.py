#!/usr/bin/env python3
"""
Script to initialize default admin settings
"""
from app import app, db
from models import AdminSettings, User

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

if __name__ == "__main__":
    init_admin_settings() 