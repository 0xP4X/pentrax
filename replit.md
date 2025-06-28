# PentraX - Cybersecurity Collaboration Platform

## Overview

PentraX is a modern web-based cybersecurity collaboration platform built with Flask. It serves as a community hub for cybersecurity professionals to share tools, report vulnerabilities, publish research ideas, collaborate on projects, and monetize their content. The platform features an integrated AI assistant, forum-style discussions, user profiles, and planned cyber labs for hands-on learning.

## System Architecture

### Backend Architecture
- **Framework**: Flask (Python web framework)
- **Database**: SQLAlchemy ORM with SQLite (configurable to PostgreSQL via DATABASE_URL)
- **Authentication**: Flask-Login with session-based user management
- **File Handling**: Werkzeug secure filename handling with 16MB upload limit
- **AI Integration**: OpenAI GPT-4o API for cybersecurity-focused assistance

### Frontend Architecture
- **UI Framework**: Bootstrap 5.3.0 with dark theme support
- **Icons**: Font Awesome 6.4.0
- **JavaScript**: Vanilla JS with Bootstrap components
- **Theme System**: Local storage-based dark/light theme switching
- **Responsive Design**: Mobile-first approach with Bootstrap grid system

### Database Schema
The application uses a relational database with the following core entities:
- **Users**: Authentication, profiles, reputation system, admin/premium flags
- **Posts**: Forum content with categories (tools, bugs, ideas, jobs)
- **Comments**: Threaded discussions (model referenced but implementation incomplete)
- **Follow**: User relationship system
- **Labs/Notifications**: Planned features for cyber labs and user notifications

## Key Components

### User Management System
- Registration and login with password hashing
- Profile management with bio, skills, GitHub integration
- Role-based access (admin, premium users)
- Follow/unfollow functionality
- Reputation scoring system

### Forum System
- Four main categories: Tools, Bugs/CVEs, Ideas/Research, Jobs/Collaborations
- File upload support for sharing security tools and scripts
- Post categorization and tagging
- Premium content with pricing
- Featured posts system
- View counting and engagement metrics

### AI Assistant
- Always-available popup chat interface
- OpenAI GPT-4o integration with cybersecurity-focused prompts
- Conversation history stored in localStorage
- Specialized for debugging tools, explaining vulnerabilities, and security guidance
- Admin-configurable API key

### Content Management
- File upload restrictions to security-relevant formats
- Markdown support for post content
- Premium content monetization system (in development)
- Admin dashboard for platform oversight

## Data Flow

1. **User Registration/Login**: Credentials → Flask-Login → Session management
2. **Post Creation**: Form data → File processing → Database storage → Forum display
3. **AI Interaction**: User query → OpenAI API → Response processing → Chat interface
4. **File Uploads**: Security validation → Secure storage → Database reference
5. **Profile Updates**: Form submission → Database update → Profile display

## External Dependencies

### Core Dependencies
- **OpenAI API**: GPT-4o model for AI assistant functionality
- **Bootstrap CDN**: UI framework and components
- **Font Awesome CDN**: Icon library

### Python Packages
- Flask ecosystem (Flask, Flask-SQLAlchemy, Flask-Login)
- OpenAI Python client
- Werkzeug for security utilities
- SQLAlchemy for database operations

### Development Tools
- Environment variable management for API keys and database URLs
- SQLite for development (PostgreSQL ready for production)

## Deployment Strategy

### Current Setup
- Development server on host 0.0.0.0:5000
- Debug mode enabled for development
- SQLite database for rapid prototyping
- File uploads stored locally in 'uploads' directory

### Production Considerations
- Database migration to PostgreSQL via DATABASE_URL environment variable
- Static file serving optimization
- Environment-based configuration management
- Secure session key management
- File storage scaling (cloud storage integration)

### Environment Variables
- `OPENAI_API_KEY`: Required for AI assistant functionality
- `DATABASE_URL`: Database connection string (defaults to SQLite)
- `SESSION_SECRET`: Flask session security key

## User Preferences

Preferred communication style: Simple, everyday language.

## Changelog

Changelog:
- June 28, 2025. Initial setup