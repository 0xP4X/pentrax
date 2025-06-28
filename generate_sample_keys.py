#!/usr/bin/env python3
"""
Script to generate sample activation keys for testing the premium system
"""
from app import app, db
from models import User, ActivationKey
from datetime import datetime, timedelta
import secrets
import string

def generate_sample_keys():
    with app.app_context():
        # Get admin user
        admin_user = User.query.filter_by(username='admin').first()
        
        if not admin_user:
            print("Admin user not found!")
            return
        
        # Sample activation keys
        sample_keys = [
            {
                'plan_type': 'monthly',
                'duration_days': 30,
                'price': 9.99,
                'quantity': 5
            },
            {
                'plan_type': 'yearly',
                'duration_days': 365,
                'price': 99.99,
                'quantity': 3
            },
            {
                'plan_type': 'lifetime',
                'duration_days': 9999,
                'price': 299.99,
                'quantity': 2
            }
        ]
        
        generated_keys = []
        
        for key_data in sample_keys:
            for _ in range(key_data['quantity']):
                # Generate unique key
                while True:
                    key = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(16))
                    if not ActivationKey.query.filter_by(key=key).first():
                        break
                
                # Set expiration (30 days from now for unused keys)
                expires_at = datetime.utcnow() + timedelta(days=30)
                
                activation_key = ActivationKey(
                    key=key,
                    plan_type=key_data['plan_type'],
                    duration_days=key_data['duration_days'],
                    price=key_data['price'],
                    created_by=admin_user.id,
                    expires_at=expires_at
                )
                db.session.add(activation_key)
                generated_keys.append({
                    'key': key,
                    'plan': key_data['plan_type'],
                    'price': key_data['price']
                })
        
        db.session.commit()
        
        print("✅ Sample activation keys generated successfully!")
        print("\nGenerated Keys:")
        print("-" * 50)
        for key_info in generated_keys:
            print(f"Key: {key_info['key']}")
            print(f"Plan: {key_info['plan'].title()}")
            print(f"Price: ${key_info['price']}")
            print("-" * 50)
        
        print(f"\nTotal keys generated: {len(generated_keys)}")
        print("You can now test the premium activation system!")

if __name__ == '__main__':
    generate_sample_keys() 