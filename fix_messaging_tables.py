#!/usr/bin/env python3
"""
Fix messaging system tables by dropping and recreating them properly.
"""

import os
import sys
from datetime import datetime

# Add the current directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Conversation, ConversationParticipant, Message, MessageReadReceipt

def drop_messaging_tables():
    """Drop the messaging system tables"""
    with app.app_context():
        try:
            print("Dropping existing messaging tables...")
            
            # Drop tables in reverse order of dependencies
            MessageReadReceipt.__table__.drop(db.engine, checkfirst=True)
            Message.__table__.drop(db.engine, checkfirst=True)
            ConversationParticipant.__table__.drop(db.engine, checkfirst=True)
            Conversation.__table__.drop(db.engine, checkfirst=True)
            
            print("✅ Messaging tables dropped successfully!")
            return True
            
        except Exception as e:
            print(f"❌ Error dropping tables: {e}")
            return False

def create_messaging_tables():
    """Create the messaging system tables"""
    with app.app_context():
        try:
            print("Creating messaging system tables...")
            
            # Create the tables
            db.create_all()
            
            print("✅ Messaging system tables created successfully!")
            print("\nCreated tables:")
            print("- conversation")
            print("- conversation_participant") 
            print("- message")
            print("- message_read_receipt")
            
        except Exception as e:
            print(f"❌ Error creating tables: {e}")
            return False
    
    return True

def verify_tables():
    """Verify that the tables were created correctly"""
    with app.app_context():
        try:
            # Check if tables exist by trying to query them
            conversation_count = Conversation.query.count()
            participant_count = ConversationParticipant.query.count()
            message_count = Message.query.count()
            receipt_count = MessageReadReceipt.query.count()
            
            print(f"\n✅ Table verification successful!")
            print(f"Conversation table: {conversation_count} records")
            print(f"ConversationParticipant table: {participant_count} records")
            print(f"Message table: {message_count} records")
            print(f"MessageReadReceipt table: {receipt_count} records")
            
            return True
            
        except Exception as e:
            print(f"❌ Error verifying tables: {e}")
            return False

if __name__ == "__main__":
    print("🔧 PentraX Messaging System Table Fix")
    print("=" * 40)
    
    # Drop existing tables
    if drop_messaging_tables():
        # Create tables
        if create_messaging_tables():
            # Verify tables
            verify_tables()
            print("\n🎉 Messaging system tables fixed successfully!")
            print("\nThe messaging system is now ready to use.")
        else:
            print("\n💥 Failed to create tables!")
            sys.exit(1)
    else:
        print("\n💥 Failed to drop tables!")
        sys.exit(1) 