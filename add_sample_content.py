#!/usr/bin/env python3
"""
Script to add sample premium content for testing the store functionality
"""
from app import app, db
from models import Post, User

def add_sample_content():
    with app.app_context():
        # Get admin user
        admin_user = User.query.filter_by(username='admin').first()
        
        if not admin_user:
            print("Admin user not found!")
            return
        
        # Sample premium posts
        sample_posts = [
            {
                'title': 'Advanced Network Scanner Pro',
                'content': 'A comprehensive network scanning tool with advanced features for penetration testing. Includes port scanning, service detection, vulnerability assessment, and detailed reporting capabilities.',
                'category': 'tools',
                'price': 29.99,
                'tags': 'network, scanner, pentest, security'
            },
            {
                'title': 'Web Application Firewall Bypass Techniques',
                'content': 'Advanced techniques for bypassing WAF protection. Includes detailed analysis of common WAF bypass methods, custom payload generation, and real-world case studies.',
                'category': 'bugs',
                'price': 49.99,
                'tags': 'waf, bypass, web, security'
            },
            {
                'title': 'Zero-Day Exploit Development Guide',
                'content': 'Complete guide to developing zero-day exploits. Covers vulnerability research, exploit development, shellcode creation, and advanced exploitation techniques.',
                'category': 'ideas',
                'price': 79.99,
                'tags': 'exploit, zero-day, research, development'
            },
            {
                'title': 'Malware Analysis Toolkit',
                'content': 'Professional toolkit for malware analysis including static and dynamic analysis tools, sandbox environments, and reverse engineering utilities.',
                'category': 'tools',
                'price': 39.99,
                'tags': 'malware, analysis, reverse-engineering, toolkit'
            }
        ]
        
        # Add posts
        for post_data in sample_posts:
            # Check if post already exists
            existing_post = Post.query.filter_by(title=post_data['title']).first()
            if not existing_post:
                post = Post(
                    title=post_data['title'],
                    content=post_data['content'],
                    category=post_data['category'],
                    price=post_data['price'],
                    tags=post_data['tags'],
                    is_premium=True,
                    user_id=admin_user.id
                )
                db.session.add(post)
                print(f"Added: {post_data['title']}")
            else:
                print(f"Already exists: {post_data['title']}")
        
        db.session.commit()
        print("\n✅ Sample premium content added successfully!")
        print("You can now test the store functionality with these items.")

if __name__ == "__main__":
    add_sample_content() 