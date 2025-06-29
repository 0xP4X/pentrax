# PentraX - Cybersecurity Community Platform

A Flask-based web application for cybersecurity professionals, featuring forums, labs, and tools sharing.

## Features

- User authentication and authorization
- Forum posts and comments
- Cybersecurity labs and challenges
- File sharing and downloads
- Admin dashboard
- User profiles and reputation system

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Environment Variables

Create a `.env` file in the root directory with the following variables:

```env
DATABASE_URL=postgresql://postgres.dmhjkqwtorscryuivxht:oIVPpgKI7TAQPavI@aws-0-eu-central-1.pooler.supabase.com:5432/postgres
SESSION_SECRET=your-super-secret-session-key-change-this-in-production
FLASK_APP=app.py
FLASK_ENV=development
```

### 3. Database Setup

#### Option A: Using Flask-Migrate (Recommended)

```bash
# Initialize migrations
python migrate_db.py init

# Create initial migration
python migrate_db.py migrate

# Apply migrations
python migrate_db.py upgrade
```

#### Option B: Direct Table Creation

```bash
python migrate_db.py create_tables
```

### 4. Run the Application

```bash
python run.py
```

Or alternatively:

```bash
python app.py
```

The application will be available at `http://localhost:5000`

## Default Admin Account

- **Username**: admin
- **Password**: password123
- **Email**: admpentrax@gmail.com

⚠️ **Important**: Change the default admin password in production!

## Database Schema

The application includes the following main models:

- **User**: User accounts with authentication and profiles
- **Post**: Forum posts with categories and tags
- **Comment**: Comments on posts
- **Lab**: Cybersecurity labs and challenges
- **LabCompletion**: Track lab completions
- **Notification**: User notifications
- **AdminSettings**: Application settings
- **UserAction**: User activity logging
- **UserBan**: User moderation system

## Development

### Project Structure

```
pentrax2/
├── app.py              # Main Flask application
├── models.py           # Database models
├── routes.py           # Route handlers
├── utils.py            # Utility functions
├── ai_assistant.py     # AI assistant functionality
├── requirements.txt    # Python dependencies
├── run.py             # Application startup script
├── migrate_db.py      # Database migration script
├── static/            # Static files (CSS, JS)
├── templates/         # HTML templates
└── uploads/           # File uploads directory
```

### Database Migrations

To create a new migration after model changes:

```bash
python migrate_db.py migrate
```

To apply pending migrations:

```bash
python migrate_db.py upgrade
```

## Production Deployment

1. Set proper environment variables
2. Use a production WSGI server like Gunicorn
3. Configure a reverse proxy (Nginx)
4. Set up SSL certificates
5. Change default admin credentials
6. Configure proper logging

## License

This project is licensed under the MIT License. 