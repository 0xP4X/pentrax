#!/usr/bin/env python3
"""
Startup script for PentraX Flask application
"""
import os
import sys
from app import app

if __name__ == "__main__":
    # Set environment variables if not already set
    if not os.environ.get("DATABASE_URL"):
        os.environ["DATABASE_URL"] = "postgresql://postgres.dmhjkqwtorscryuivxht:oIVPpgKI7TAQPavI@aws-0-eu-central-1.pooler.supabase.com:5432/postgres"
    
    if not os.environ.get("SESSION_SECRET"):
        os.environ["SESSION_SECRET"] = "dev-secret-key-change-this-in-production"
    
    if not os.environ.get("FLASK_ENV"):
        os.environ["FLASK_ENV"] = "development"
    
    print("🚀 Starting PentraX Flask Application...")
    print(f"📊 Database: {os.environ.get('DATABASE_URL', 'Not set')}")
    print(f"🌍 Environment: {os.environ.get('FLASK_ENV', 'development')}")
    print("🔗 Server will be available at: http://localhost:5000")
    
    app.run(debug=True, host='0.0.0.0', port=5000) 