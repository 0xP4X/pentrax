#!/usr/bin/env python3
"""
Database migration script for PentraX Flask app
"""
import os
import sys
from flask_migrate import upgrade, init, migrate
from app import app, db

def init_migrations():
    """Initialize migrations if not already done"""
    try:
        with app.app_context():
            init()
            print("✅ Migrations initialized successfully")
    except Exception as e:
        print(f"⚠️  Migrations may already be initialized: {e}")

def create_migration():
    """Create a new migration"""
    try:
        with app.app_context():
            migrate()
            print("✅ Migration created successfully")
    except Exception as e:
        print(f"❌ Error creating migration: {e}")

def run_migrations():
    """Run all pending migrations"""
    try:
        with app.app_context():
            upgrade()
            print("✅ All migrations applied successfully")
    except Exception as e:
        print(f"❌ Error running migrations: {e}")

def create_tables():
    """Create all tables directly"""
    try:
        with app.app_context():
            db.create_all()
            print("✅ All tables created successfully")
    except Exception as e:
        print(f"❌ Error creating tables: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python migrate_db.py [init|migrate|upgrade|create_tables]")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "init":
        init_migrations()
    elif command == "migrate":
        create_migration()
    elif command == "upgrade":
        run_migrations()
    elif command == "create_tables":
        create_tables()
    else:
        print("Invalid command. Use: init, migrate, upgrade, or create_tables") 