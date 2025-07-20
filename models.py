from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from db import db
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    bio = db.Column(db.Text)
    skills = db.Column(db.String(500))
    github_username = db.Column(db.String(80))
    avatar_url = db.Column(db.String(200))
    is_admin = db.Column(db.Boolean, default=False)
    is_premium = db.Column(db.Boolean, default=False)
    is_banned = db.Column(db.Boolean, default=False)
    is_muted = db.Column(db.Boolean, default=False)
    onboarding_complete = db.Column(db.Boolean, default=False)
    reputation = db.Column(db.Integer, default=0)
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    posts = db.relationship('Post', backref='author', lazy=True)
    comments = db.relationship('Comment', backref='author', lazy=True)
    followers = db.relationship('Follow', foreign_keys='Follow.followed_id', backref='followed', lazy='dynamic')
    following = db.relationship('Follow', foreign_keys='Follow.follower_id', backref='follower', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def has_active_premium(self):
        """Check if user has an active premium subscription"""
        # Check if platform is in free mode
        if is_platform_free_mode():
            return True
        
        if self.is_admin:
            return True
        
        # Check for active subscription
        active_subscription = PremiumSubscription.query.filter_by(
            user_id=self.id,
            is_active=True
        ).filter(
            PremiumSubscription.end_date > datetime.utcnow()
        ).first()
        
        return active_subscription is not None
    
    def get_active_subscription(self):
        """Get the user's active premium subscription"""
        if self.is_admin:
            return None  # Admin doesn't need subscription
        
        return PremiumSubscription.query.filter_by(
            user_id=self.id,
            is_active=True
        ).filter(
            PremiumSubscription.end_date > datetime.utcnow()
        ).first()
    
    def get_active_ban(self):
        """Get the user's active ban if any"""
        return UserBan.query.filter_by(
            user_id=self.id,
            is_active=True
        ).filter(
            (UserBan.expires_at > datetime.utcnow()) | (UserBan.expires_at.is_(None))
        ).first()
    
    def is_temporarily_banned(self):
        """Check if user is temporarily banned"""
        active_ban = self.get_active_ban()
        if active_ban and active_ban.ban_type == 'temporary' and active_ban.expires_at:
            return active_ban.expires_at > datetime.utcnow()
        return False
    
    def is_permanently_banned(self):
        """Check if user is permanently banned"""
        active_ban = self.get_active_ban()
        if active_ban and active_ban.ban_type == 'permanent':
            return True
        return False
    
    def is_muted_user(self):
        """Check if user is muted"""
        active_ban = self.get_active_ban()
        if active_ban and active_ban.ban_type == 'mute':
            return True
        return False
    
    def get_ban_expiry_date(self):
        """Get the expiry date of the current ban"""
        active_ban = self.get_active_ban()
        if active_ban and active_ban.expires_at:
            return active_ban.expires_at
        return None
    
    def get_ban_reason(self):
        """Get the reason for the current ban"""
        active_ban = self.get_active_ban()
        if active_ban:
            return active_ban.reason
        return None
    
    def get_ban_duration_remaining(self):
        """Get the remaining duration of the ban in seconds"""
        active_ban = self.get_active_ban()
        if active_ban and active_ban.expires_at:
            remaining = active_ban.expires_at - datetime.utcnow()
            return max(0, int(remaining.total_seconds()))
        return None
    
    def can_post(self):
        """Check if user can create posts"""
        if self.is_admin:
            return True
        if self.is_permanently_banned() or self.is_temporarily_banned():
            return False
        return True
    
    def can_comment(self):
        """Check if user can comment"""
        if self.is_admin:
            return True
        if self.is_permanently_banned() or self.is_temporarily_banned() or self.is_muted_user():
            return False
        return True
    
    def can_access_labs(self):
        """Check if user can access labs"""
        if self.is_admin:
            return True
        if self.is_permanently_banned() or self.is_temporarily_banned():
            return False
        return True

class Follow(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    follower_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    followed_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False)  # tools, bugs, ideas, jobs
    tags = db.Column(db.String(200))
    file_path = db.Column(db.String(200))
    file_name = db.Column(db.String(100))
    price = db.Column(db.Float, default=0.0)
    is_premium = db.Column(db.Boolean, default=False)
    is_featured = db.Column(db.Boolean, default=False)
    views = db.Column(db.Integer, default=0)
    likes = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Foreign keys
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Relationships
    comments = db.relationship('Comment', backref='post', lazy=True, cascade='all, delete-orphan')

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Foreign keys
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

class Lab(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    difficulty = db.Column(db.String(20), nullable=False)  # easy, medium, hard, expert
    category = db.Column(db.String(50), nullable=False)  # web, network, crypto, forensics, reverse_engineering, etc.
    subcategory = db.Column(db.String(50))  # sql_injection, xss, buffer_overflow, etc.
    points = db.Column(db.Integer, default=10)
    hints = db.Column(db.Text)
    solution = db.Column(db.Text)
    flag = db.Column(db.String(100))  # CTF-style flag
    instructions = db.Column(db.Text)  # Detailed step-by-step instructions
    tools_needed = db.Column(db.String(500))  # Required tools/software
    learning_objectives = db.Column(db.Text)  # What students will learn
    prerequisites = db.Column(db.Text)  # Required knowledge/skills
    estimated_time = db.Column(db.Integer, default=30)  # minutes
    is_premium = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Advanced lab features
    lab_type = db.Column(db.String(20), default='standard')  # standard, terminal, sandbox, quiz, ctf, real_hacking
    lab_format = db.Column(db.String(20), default='individual')  # individual, team, competition
    
    # Sandbox and environment
    sandbox_url = db.Column(db.String(500))  # URL or connection info for sandbox
    sandbox_instructions = db.Column(db.Text)  # How to use the sandbox
    environment_type = db.Column(db.String(50))  # docker, vm, cloud, local
    environment_config = db.Column(db.Text)  # JSON config for environment setup
    
    # Real-time hacking features
    required_command = db.Column(db.Text)  # Command user must run
    command_success_criteria = db.Column(db.Text)  # Output or flag to check for success
    allow_multiple_flags = db.Column(db.Boolean, default=False)  # Multiple flags for different difficulty levels
    flag_hints = db.Column(db.Text)  # JSON array of hints for each flag
    
    # Terminal-based labs
    terminal_enabled = db.Column(db.Boolean, default=False)
    terminal_instructions = db.Column(db.Text)
    terminal_shell = db.Column(db.String(20), default='bash')  # bash, powershell, cmd, etc.
    terminal_timeout = db.Column(db.Integer, default=300)  # Timeout in seconds
    allow_command_hints = db.Column(db.Boolean, default=True)
    strict_order = db.Column(db.Boolean, default=True)
    allow_retry = db.Column(db.Boolean, default=True)
    
    # CTF and competition features
    ctf_category = db.Column(db.String(50))  # web, crypto, forensics, pwn, reverse, misc
    ctf_points = db.Column(db.Integer, default=0)  # Dynamic points based on solves
    ctf_solves = db.Column(db.Integer, default=0)  # Number of successful solves
    ctf_first_blood = db.Column(db.Integer, db.ForeignKey('user.id'))  # First to solve
    ctf_first_blood_time = db.Column(db.DateTime)
    
    # Learning path integration
    learning_path_id = db.Column(db.Integer, db.ForeignKey('learning_path.id'))
    path_order = db.Column(db.Integer, default=0)  # Order in learning path
    
    # Progress tracking
    completion_rate = db.Column(db.Float, default=0.0)  # Percentage of users who complete
    average_time = db.Column(db.Float, default=0.0)  # Average completion time in minutes
    difficulty_rating = db.Column(db.Float, default=0.0)  # User-rated difficulty (1-5)
    
    # Relationships
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    learning_path = db.relationship('LearningPath', backref='labs')
    first_blood_user = db.relationship('User', foreign_keys=[ctf_first_blood])

class LearningPath(db.Model):
    """Model for structured learning paths like TryHackMe paths"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    difficulty = db.Column(db.String(20), nullable=False)  # beginner, intermediate, advanced, expert
    category = db.Column(db.String(50), nullable=False)  # web_security, network_security, etc.
    estimated_duration = db.Column(db.Integer, default=0)  # hours
    total_points = db.Column(db.Integer, default=0)
    is_premium = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Learning path features
    prerequisites = db.Column(db.Text)  # Required knowledge
    learning_objectives = db.Column(db.Text)  # What students will learn
    target_audience = db.Column(db.String(200))  # Who this path is for
    certification = db.Column(db.String(100))  # Certification offered (if any)
    
    # Progress tracking
    enrolled_users = db.Column(db.Integer, default=0)
    completed_users = db.Column(db.Integer, default=0)
    average_rating = db.Column(db.Float, default=0.0)

class CTFChallenge(db.Model):
    """Model for CTF-style challenges"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False)  # web, crypto, forensics, pwn, reverse, misc
    difficulty = db.Column(db.String(20), nullable=False)  # easy, medium, hard, expert
    points = db.Column(db.Integer, default=100)
    flag = db.Column(db.String(200), nullable=False)
    hints = db.Column(db.Text)  # JSON array of hints
    files = db.Column(db.Text)  # JSON array of downloadable files
    solved_by = db.Column(db.Integer, default=0)  # Number of solves
    first_blood = db.Column(db.Integer, db.ForeignKey('user.id'))
    first_blood_time = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Challenge features
    challenge_type = db.Column(db.String(50))  # static, dynamic, jeopardy, attack_defense
    time_limit = db.Column(db.Integer)  # Time limit in minutes (if any)
    max_attempts = db.Column(db.Integer, default=0)  # 0 = unlimited
    
    # Relationships
    first_blood_user = db.relationship('User', foreign_keys=[first_blood])

class CTFSubmission(db.Model):
    """Model for CTF flag submissions"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    challenge_id = db.Column(db.Integer, db.ForeignKey('ctf_challenge.id'), nullable=False)
    submitted_flag = db.Column(db.String(200), nullable=False)
    is_correct = db.Column(db.Boolean, default=False)
    points_earned = db.Column(db.Integer, default=0)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='ctf_submissions')
    challenge = db.relationship('CTFChallenge', backref='submissions')

class SandboxEnvironment(db.Model):
    """Model for sandbox environments"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    environment_type = db.Column(db.String(50), nullable=False)  # docker, vm, cloud
    image_name = db.Column(db.String(200))  # Docker image or VM template
    configuration = db.Column(db.Text)  # JSON configuration
    resources = db.Column(db.Text)  # CPU, RAM, storage requirements
    is_active = db.Column(db.Boolean, default=True)
    max_concurrent_users = db.Column(db.Integer, default=10)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class UserSandboxSession(db.Model):
    """Model for user sandbox sessions"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    sandbox_id = db.Column(db.Integer, db.ForeignKey('sandbox_environment.id'), nullable=False)
    session_id = db.Column(db.String(100), unique=True, nullable=False)
    container_id = db.Column(db.String(100))  # Docker container ID or VM ID
    status = db.Column(db.String(20), default='starting')  # starting, running, stopped, error
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    stopped_at = db.Column(db.DateTime)
    access_url = db.Column(db.String(500))  # URL to access the sandbox
    
    # Relationships
    user = db.relationship('User', backref='sandbox_sessions')
    sandbox = db.relationship('SandboxEnvironment', backref='user_sessions')

class LabProgress(db.Model):
    """Model for tracking detailed lab progress"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    lab_id = db.Column(db.Integer, db.ForeignKey('lab.id'), nullable=False)
    progress_percentage = db.Column(db.Float, default=0.0)
    current_step = db.Column(db.Integer, default=1)
    total_steps = db.Column(db.Integer, default=1)
    time_spent = db.Column(db.Integer, default=0)  # seconds
    hints_used = db.Column(db.Integer, default=0)
    attempts = db.Column(db.Integer, default=0)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_activity = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    
    # Relationships
    user = db.relationship('User', backref='lab_progress')
    lab = db.relationship('Lab', backref='user_progress')

class LabHint(db.Model):
    """Model for lab hints with progressive reveal"""
    id = db.Column(db.Integer, primary_key=True)
    lab_id = db.Column(db.Integer, db.ForeignKey('lab.id'), nullable=False)
    hint_text = db.Column(db.Text, nullable=False)
    hint_order = db.Column(db.Integer, default=1)  # Order of hint reveal
    cost = db.Column(db.Integer, default=0)  # Points cost to reveal hint
    is_free = db.Column(db.Boolean, default=True)  # Whether hint is free
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    lab = db.relationship('Lab', backref='lab_hints')

class UserHintUsage(db.Model):
    """Model for tracking hint usage by users"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    hint_id = db.Column(db.Integer, db.ForeignKey('lab_hint.id'), nullable=False)
    used_at = db.Column(db.DateTime, default=datetime.utcnow)
    points_spent = db.Column(db.Integer, default=0)
    
    # Relationships
    user = db.relationship('User', backref='hint_usage')
    hint = db.relationship('LabHint', backref='usage')

class LabRating(db.Model):
    """Model for user ratings and feedback on labs"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    lab_id = db.Column(db.Integer, db.ForeignKey('lab.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1-5 stars
    difficulty_rating = db.Column(db.Integer)  # 1-5 difficulty
    feedback = db.Column(db.Text)  # User feedback
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='lab_ratings')
    lab = db.relationship('Lab', backref='lab_ratings')
    
    # Ensure one rating per user per lab
    __table_args__ = (db.UniqueConstraint('user_id', 'lab_id', name='unique_user_lab_rating'),)

class LabCompletion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    lab_id = db.Column(db.Integer, db.ForeignKey('lab.id'), nullable=False)
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='lab_completions')
    lab = db.relationship('Lab', backref='lab_completions')

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='notifications')

class AdminSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text)
    description = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = db.Column(db.Integer, db.ForeignKey('user.id'))

class UserAction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action_type = db.Column(db.String(50), nullable=False)  # login, post_create, file_download, etc.
    target_type = db.Column(db.String(50))  # post, user, file, etc.
    target_id = db.Column(db.Integer)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='actions')

class UserBan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    banned_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    ban_type = db.Column(db.String(20), default='temporary')  # temporary, permanent, mute
    expires_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    user = db.relationship('User', foreign_keys=[user_id], backref='bans')
    banned_by_user = db.relationship('User', foreign_keys=[banned_by])

class PostLike(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='post_likes')
    post = db.relationship('Post', backref='post_likes')
    
    # Ensure a user can only like a post once
    __table_args__ = (db.UniqueConstraint('user_id', 'post_id', name='unique_user_post_like'),)

class CommentLike(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    comment_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='comment_likes')
    comment = db.relationship('Comment', backref='comment_likes')
    
    # Ensure a user can only like a comment once
    __table_args__ = (db.UniqueConstraint('user_id', 'comment_id', name='unique_user_comment_like'),)

# Store Models
class Purchase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default='USD')
    status = db.Column(db.String(20), default='pending')  # pending, completed, failed, refunded
    payment_method = db.Column(db.String(50))  # paystack, paypal, etc.
    transaction_id = db.Column(db.String(100), unique=True)
    purchase_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='purchases')
    post = db.relationship('Post', backref='purchases')

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(50), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default='USD')
    status = db.Column(db.String(20), default='pending')  # pending, processing, completed, cancelled
    payment_status = db.Column(db.String(20), default='pending')  # pending, paid, failed
    shipping_address = db.Column(db.Text)  # For physical items if needed
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='orders')
    items = db.relationship('OrderItem', backref='order', cascade='all, delete-orphan')

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    unit_price = db.Column(db.Float, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    
    # Relationships
    post = db.relationship('Post')

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.String(100), unique=True, nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default='USD')
    payment_method = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, success, failed, refunded
    gateway_response = db.Column(db.Text)  # JSON response from payment gateway
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    order = db.relationship('Order', backref='transactions')

class UserWallet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    balance = db.Column(db.Float, default=0.0)
    currency = db.Column(db.String(3), default='USD')
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='wallet')

class WalletTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    wallet_id = db.Column(db.Integer, db.ForeignKey('user_wallet.id'), nullable=False)
    transaction_type = db.Column(db.String(20), nullable=False)  # deposit, withdrawal, purchase, refund
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text)
    reference = db.Column(db.String(100))  # External reference
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    wallet = db.relationship('UserWallet', backref='transactions')

class LabQuizQuestion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lab_id = db.Column(db.Integer, db.ForeignKey('lab.id'), nullable=False)
    question = db.Column(db.Text, nullable=False)
    options = db.Column(db.Text, nullable=False)  # JSON-encoded list of options
    correct_answer = db.Column(db.String(200), nullable=False)
    explanation = db.Column(db.Text)
    order = db.Column(db.Integer, default=0)
    marks = db.Column(db.Integer, default=1)  # Marks for this question
    
    lab = db.relationship('Lab', backref='quiz_questions')

class LabQuizAttempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    lab_id = db.Column(db.Integer, db.ForeignKey('lab.id'), nullable=False)
    answers = db.Column(db.Text)  # JSON-encoded dict: {question_id: selected_option}
    score = db.Column(db.Integer, default=0)
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='quiz_attempts')
    lab = db.relationship('Lab', backref='lab_quiz_attempts')

class ActivationKey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(64), unique=True, nullable=False)
    plan_type = db.Column(db.String(20), nullable=False)  # monthly, yearly, lifetime
    duration_days = db.Column(db.Integer, nullable=False)  # 30, 365, 9999 for lifetime
    price = db.Column(db.Float, nullable=False)
    is_used = db.Column(db.Boolean, default=False)
    used_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    used_at = db.Column(db.DateTime)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # admin who created it
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)  # when the key itself expires if unused
    
    # Relationships
    user = db.relationship('User', foreign_keys=[used_by], backref='activation_keys')
    creator = db.relationship('User', foreign_keys=[created_by])

class PremiumSubscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    activation_key_id = db.Column(db.Integer, db.ForeignKey('activation_key.id'), nullable=False)
    plan_type = db.Column(db.String(20), nullable=False)  # monthly, yearly, lifetime
    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    end_date = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    payment_status = db.Column(db.String(20), default='completed')  # pending, completed, failed, refunded
    amount_paid = db.Column(db.Float, nullable=False)
    
    # Relationships
    user = db.relationship('User', backref='subscriptions')
    activation_key = db.relationship('ActivationKey', backref='subscriptions')

class PaymentPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)  # monthly, yearly, lifetime
    display_name = db.Column(db.String(100), nullable=False)  # Monthly Plan, Yearly Plan, etc.
    price = db.Column(db.Float, nullable=False)
    duration_days = db.Column(db.Integer, nullable=False)  # 30, 365, 9999 for lifetime
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    features = db.Column(db.JSON)  # List of features included
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<PaymentPlan {self.name}: ${self.price}>'

def is_platform_free_mode():
    """Check if the platform is in free mode (all features available to everyone)"""
    try:
        free_mode_setting = AdminSettings.query.filter_by(key='platform_free_mode').first()
        if free_mode_setting:
            return free_mode_setting.value.lower() == 'true'
        return False
    except:
        return False

def set_platform_free_mode(enabled):
    """Set the platform free mode setting"""
    try:
        free_mode_setting = AdminSettings.query.filter_by(key='platform_free_mode').first()
        if free_mode_setting:
            free_mode_setting.value = str(enabled).lower()
        else:
            free_mode_setting = AdminSettings(
                key='platform_free_mode',
                value=str(enabled).lower(),
                description='When enabled, all premium features become free for all users'
            )
            db.session.add(free_mode_setting)
        
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        return False

class LabTerminalCommand(db.Model):
    """Model for terminal commands that users must execute in order"""
    id = db.Column(db.Integer, primary_key=True)
    lab_id = db.Column(db.Integer, db.ForeignKey('lab.id'), nullable=False)
    command = db.Column(db.Text, nullable=False)  # The command user must enter
    expected_output = db.Column(db.Text)  # Expected output or success criteria
    order = db.Column(db.Integer, nullable=False)  # Order of execution
    points = db.Column(db.Integer, default=1)  # Points for this command
    hint = db.Column(db.Text)  # Hint for this command
    description = db.Column(db.Text)  # What this command does
    is_optional = db.Column(db.Boolean, default=False)  # Optional command
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    lab = db.relationship('Lab', backref='terminal_commands')

class LabTerminalAttempt(db.Model):
    """Model for tracking user's terminal command attempts"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    lab_id = db.Column(db.Integer, db.ForeignKey('lab.id'), nullable=False)
    command_id = db.Column(db.Integer, db.ForeignKey('lab_terminal_command.id'), nullable=False)
    user_command = db.Column(db.Text, nullable=False)  # What user actually typed
    user_output = db.Column(db.Text)  # Output from user's command
    is_correct = db.Column(db.Boolean, default=False)  # Whether command was correct
    points_earned = db.Column(db.Integer, default=0)  # Points earned for this command
    attempted_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='terminal_attempts')
    lab = db.relationship('Lab', backref='lab_terminal_attempts')
    command = db.relationship('LabTerminalCommand', backref='attempts')

class LabTerminalSession(db.Model):
    """Model for tracking user's terminal session progress"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    lab_id = db.Column(db.Integer, db.ForeignKey('lab.id'), nullable=False)
    session_id = db.Column(db.String(100), unique=True, nullable=False)  # Unique session ID
    current_step = db.Column(db.Integer, default=1)  # Current command step
    total_steps = db.Column(db.Integer, default=0)  # Total commands in lab
    completed_steps = db.Column(db.Integer, default=0)  # Completed commands
    total_points = db.Column(db.Integer, default=0)  # Total points earned
    max_points = db.Column(db.Integer, default=0)  # Maximum possible points
    is_completed = db.Column(db.Boolean, default=False)  # Whether lab is completed
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    
    user = db.relationship('User', backref='terminal_sessions')
    lab = db.relationship('Lab', backref='lab_terminal_sessions')

class Contact(db.Model):
    """Model for contact form submissions"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, read, replied, closed
    admin_notes = db.Column(db.Text)  # Admin's internal notes
    replied_at = db.Column(db.DateTime)
    replied_by = db.Column(db.Integer, db.ForeignKey('user.id'))  # Admin who replied
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', foreign_keys=[user_id], backref='contact_messages')
    admin = db.relationship('User', foreign_keys=[replied_by])
    
    def __repr__(self):
        return f'<Contact {self.subject}>'

# Messaging System Models

class UserStreak(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    current_streak = db.Column(db.Integer, default=0)
    longest_streak = db.Column(db.Integer, default=0)
    last_active_date = db.Column(db.Date, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('streak', uselist=False))

class Achievement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(255), nullable=False)
    icon = db.Column(db.String(100), nullable=True)  # FontAwesome or custom icon name
    type = db.Column(db.String(50), nullable=False)  # post, reaction, lab, streak, etc.
    criteria = db.Column(db.String(255), nullable=False)  # JSON or string describing how to unlock
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class UserAchievement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    achievement_id = db.Column(db.Integer, db.ForeignKey('achievement.id'), nullable=False)
    unlocked_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='user_achievements')
    achievement = db.relationship('Achievement', backref='user_achievements')

class SIEMEvent(db.Model):
    __tablename__ = 'siem_events'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    event_type = db.Column(db.String(64), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    username = db.Column(db.String(64), nullable=True)
    ip_address = db.Column(db.String(64), nullable=True)
    source = db.Column(db.String(64), nullable=True)
    severity = db.Column(db.String(16), nullable=False, default='info')
    message = db.Column(db.Text, nullable=False)
    raw_data = db.Column(JSONB, nullable=True)

    def __repr__(self):
        return f'<SIEMEvent {self.event_type} {self.timestamp}>'

class BlockedIP(db.Model):
    __tablename__ = 'blocked_ips'
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(64), unique=True, nullable=False, index=True)
    blocked_at = db.Column(db.DateTime, default=datetime.utcnow)
    reason = db.Column(db.String(255), nullable=True)
    blocked_by = db.Column(db.String(64), nullable=True)

    def __repr__(self):
        return f'<BlockedIP {self.ip_address}>'