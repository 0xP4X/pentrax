import os
import uuid
from datetime import datetime, timedelta
from flask import render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory, abort, make_response, g
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import or_, desc
from app import app, db
from models import User, Post, Comment, Lab, LabCompletion, Notification, Follow, AdminSettings, UserAction, UserBan, PostLike, CommentLike, Purchase, Order, OrderItem, Transaction, UserWallet, WalletTransaction, LabQuizQuestion, LabQuizAttempt, ActivationKey, PremiumSubscription, PaymentPlan, is_platform_free_mode, set_platform_free_mode, LabTerminalCommand, LabTerminalSession, Contact, SIEMEvent, BlockedIP
from ai_assistant import get_ai_response
from utils import allowed_file, create_notification, send_email
from payment_service import PaymentService
import json
import requests
import hashlib
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, validators
from utils.achievements import update_user_streak, check_and_unlock_achievements, get_user_achievements_with_progress, get_leaderboard_data, get_user_stats
from functools import wraps
from utils.firewall import add_blocked_ip, get_blocked_ips, unblock_ip
from utils.siem import get_deep_ip_info, log_siem_event
import re
from collections import defaultdict
from utils.lab_manager import LabManager, LAB_CATEGORIES, LAB_DIFFICULTIES, CTF_CATEGORIES

@app.context_processor
def inject_user():
    return dict(current_user=current_user)

@app.route('/')
def index():
    # Get recent posts from all categories
    recent_posts = Post.query.order_by(desc(Post.created_at)).limit(10).all()
    featured_posts = Post.query.filter_by(is_featured=True).limit(5).all()
    return render_template('index.html', recent_posts=recent_posts, featured_posts=featured_posts)

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        ip = request.remote_addr
        if user and user.check_password(password):
            # Only block permanently banned users from logging in
            if user.is_permanently_banned():
                log_siem_event(
                    event_type='login_banned',
                    message=f'Banned user {user.username} attempted login',
                    severity='warning',
                    user=user,
                    ip_address=ip,
                    source='auth'
                )
                flash('Your account has been permanently banned. Please contact support if you believe this is an error.', 'error')
                return render_template('login.html')
            # Allow temporarily banned and muted users to log in
            # They will be redirected to ban notification by the before_request middleware
            login_user(user)
            update_user_streak(user.id)
            check_and_unlock_achievements(user)
            log_siem_event(
                event_type='login_success',
                message=f'User {user.username} logged in',
                severity='info',
                user=user,
                ip_address=ip,
                source='auth'
            )
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            log_siem_event(
                event_type='login_failed',
                message=f'Failed login attempt for {username}',
                severity='warning',
                ip_address=ip,
                source='auth'
            )
            flash('Invalid username or password', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        ip = request.remote_addr
        # Check if user already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return render_template('register.html')
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return render_template('register.html')
        # Create new user
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password)
        )
        db.session.add(user)
        db.session.commit()
        # Log in the user automatically after registration
        login_user(user)
        log_siem_event(
            event_type='register_success',
            message=f'User {user.username} registered',
            severity='info',
            user=user,
            ip_address=ip,
            source='auth'
        )
        # Redirect to onboarding for new users
        return redirect(url_for('onboarding'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    log_siem_event(
        event_type='logout',
        message=f'User {current_user.username} logged out',
        severity='info',
        user=current_user,
        ip_address=request.remote_addr,
        source='auth'
    )
    logout_user()
    return redirect(url_for('index'))

@app.before_request
def enforce_onboarding():
    if current_user.is_authenticated and not getattr(current_user, 'onboarding_complete', False):
        allowed = [
            'onboarding', 'complete_onboarding', 'logout', 'static', 'uploads'
        ]
        if request.endpoint and not any(request.endpoint.startswith(a) for a in allowed):
            return redirect(url_for('onboarding'))

@app.route('/onboarding')
@login_required
def onboarding():
    if getattr(current_user, 'onboarding_complete', False):
        return redirect(url_for('index'))  # or your dashboard/profile
    return render_template('onboarding.html')

@app.route('/complete-onboarding', methods=['POST'])
@login_required
def complete_onboarding():
    data = request.get_json()
    # Save onboarding data to user
    current_user.bio = data.get('bio', '')
    current_user.skills = ','.join(data.get('skills', []))
    current_user.onboarding_complete = True
    db.session.commit()
    return jsonify({
        'success': True,
        'redirect_url': url_for('user_profile', username=current_user.username),
        'username': current_user.username
    })

class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current Password', [validators.DataRequired()])
    new_password = PasswordField('New Password', [
        validators.DataRequired(),
        validators.EqualTo('confirm_new_password', message='Passwords must match')
    ])
    confirm_new_password = PasswordField('Confirm New Password')
    submit = SubmitField('Change Password')

@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        user = current_user
        if check_password_hash(user.password_hash, form.current_password.data):
            user.password_hash = generate_password_hash(form.new_password.data)
            db.session.commit()
            log_siem_event(
                event_type='password_change',
                message=f'User {user.username} changed password',
                severity='info',
                user=user,
                ip_address=request.remote_addr,
                source='profile'
            )
            flash('Your password has been changed successfully!', 'success')
            return redirect(url_for('profile'))
        else:
            flash('Incorrect current password.', 'error')
    return render_template('change_password.html', form=form)

# Profile routes
@app.route('/profile')
@login_required
def profile():
    user_posts = Post.query.filter_by(user_id=current_user.id).order_by(desc(Post.created_at)).all()
    return render_template('profile.html', user_posts=user_posts)

@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    user = current_user
    if request.method == 'POST':
        current_user.bio = request.form.get('bio', '')
        current_user.skills = request.form.get('skills', '')
        current_user.github_username = request.form.get('github_username', '')
        
        # Handle avatar upload with validation
        if 'avatar' in request.files:
            avatar = request.files['avatar']
            if avatar and avatar.filename:
                # Check file type
                allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
                file_ext = avatar.filename.rsplit('.', 1)[1].lower() if '.' in avatar.filename else ''
                
                if file_ext not in allowed_extensions:
                    flash('Invalid file type. Please upload PNG, JPG, JPEG, GIF, or WebP images only.', 'error')
                    return render_template('profile.html', edit_mode=True)
                
                # Check file size (max 5MB)
                if len(avatar.read()) > 5 * 1024 * 1024:
                    flash('File too large. Please upload an image smaller than 5MB.', 'error')
                    return render_template('profile.html', edit_mode=True)
                
                # Reset file pointer
                avatar.seek(0)
                
                from werkzeug.utils import secure_filename
                import os
                from datetime import datetime
                
                # Generate unique filename with timestamp
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = secure_filename(f"{current_user.username}_avatar_{timestamp}.{file_ext}")
                avatar_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                
                # Save the file
                avatar.save(avatar_path)
                
                # Update avatar URL
                current_user.avatar_url = f'/uploads/{filename}'
                
                flash('Profile picture updated successfully!', 'success')
        
        db.session.commit()
        log_siem_event(
            event_type='profile_update',
            message=f'User {user.username} updated profile',
            severity='info',
            user=user,
            ip_address=request.remote_addr,
            source='profile'
        )
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))
    return render_template('profile.html', edit_mode=True)

@app.route('/user/<username>')
def user_profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    user_posts = Post.query.filter_by(user_id=user.id).order_by(desc(Post.created_at)).all()
    # Followers: users who follow this user
    followers = [f.follower for f in user.followers]
    # Following: users this user follows
    following = [f.followed for f in user.following]
    # Streak and achievements
    streak = user.streak
    achievements = [ua.achievement for ua in user.user_achievements]
    return render_template(
        'user_profile.html',
        user=user,
        user_posts=user_posts,
        followers=followers,
        following=following,
        streak=streak,
        achievements=achievements
    )

# Forum routes
@app.route('/forum/<category>')
def forum(category):
    valid_categories = ['tools', 'bugs', 'ideas', 'jobs']
    if category not in valid_categories:
        flash('Invalid category', 'error')
        return redirect(url_for('index'))
    
    search_query = request.args.get('search', '')
    posts_query = Post.query.filter_by(category=category)
    
    if search_query:
        posts_query = posts_query.filter(
            or_(
                Post.title.contains(search_query),
                Post.content.contains(search_query),
                Post.tags.contains(search_query)
            )
        )
    
    posts = posts_query.order_by(desc(Post.created_at)).all()
    return render_template('forum.html', posts=posts, category=category, search_query=search_query)

@app.route('/post/<int:post_id>')
def post_detail(post_id):
    post = Post.query.get_or_404(post_id)
    post.views += 1
    db.session.commit()
    
    comments = Comment.query.filter_by(post_id=post_id).order_by(Comment.created_at).all()
    return render_template('post_detail.html', post=post, comments=comments)

@app.route('/create_post', methods=['GET', 'POST'])
@login_required
def create_post():
    """Legacy route - redirects to appropriate creation page based on context"""
    post_type = request.args.get('type', 'forum')
    if post_type == 'store':
        return redirect(url_for('create_store_item'))
    else:
        return redirect(url_for('create_forum_post', category=request.args.get('category', 'tools')))

@app.route('/create/forum', methods=['GET', 'POST'])
@login_required
def create_forum_post():
    """Create a forum post (community discussion, not for sale)"""
    # Check if user is banned
    if current_user.is_permanently_banned() or current_user.is_temporarily_banned():
        flash('You cannot create posts while your account is suspended.', 'error')
        return redirect(url_for('ban_notification'))
    
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        category = request.form['category']
        tags = request.form.get('tags', '')
        
        # Handle file upload (optional for forum posts)
        file_path = None
        file_name = None
        if 'file' in request.files:
            file = request.files['file']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                file_name = filename
        
        post = Post(
            title=title,
            content=content,
            category=category,
            tags=tags,
            price=0.0,  # Forum posts are always free
            is_premium=False,  # Forum posts are never premium
            file_path=file_path,
            file_name=file_name,
            user_id=current_user.id
        )
        
        db.session.add(post)
        db.session.commit()
        update_user_streak(current_user.id)
        check_and_unlock_achievements(current_user)
        log_siem_event(
            event_type='post_create',
            message=f'User {current_user.username} created a post',
            severity='info',
            user=current_user,
            ip_address=request.remote_addr,
            source='post'
        )
        
        flash('Forum post created successfully!', 'success')
        return redirect(url_for('post_detail', post_id=post.id))
    
    return render_template('create_forum_post.html')

@app.route('/create/store', methods=['GET', 'POST'])
@login_required
def create_store_item():
    """Create a store item (premium content for sale)"""
    # Check if user is banned
    if current_user.is_permanently_banned() or current_user.is_temporarily_banned():
        flash('You cannot create content while your account is suspended.', 'error')
        return redirect(url_for('ban_notification'))
    
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        category = request.form['category']
        tags = request.form.get('tags', '')
        price = float(request.form.get('price', 0.0))
        
        # Validate price for store items
        if price <= 0:
            flash('Store items must have a price greater than 0.', 'error')
            return render_template('create_store_item.html')
        
        # Handle file upload (required for store items)
        file_path = None
        file_name = None
        if 'file' in request.files:
            file = request.files['file']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                file_name = filename
        
        if not file_name:
            flash('Store items must include a downloadable file.', 'error')
            return render_template('create_store_item.html')
        
        post = Post(
            title=title,
            content=content,
            category=category,
            tags=tags,
            price=price,
            is_premium=True,  # Store items are always premium
            file_path=file_path,
            file_name=file_name,
            user_id=current_user.id
        )
        
        db.session.add(post)
        db.session.commit()
        update_user_streak(current_user.id)
        check_and_unlock_achievements(current_user)
        
        flash('Store item created successfully! You can track sales in your Creator Dashboard.', 'success')
        return redirect(url_for('post_detail', post_id=post.id))
    
    return render_template('create_store_item.html')

@app.route('/add_comment/<int:post_id>', methods=['POST'])
@login_required
def add_comment(post_id):
    # Check if user is banned or muted
    if current_user.is_permanently_banned() or current_user.is_temporarily_banned() or current_user.is_muted_user():
        flash('You cannot comment while your account is suspended or muted.', 'error')
        return redirect(url_for('ban_notification'))
    
    content = request.form['content']
    post = Post.query.get_or_404(post_id)
    
    comment = Comment(
        content=content,
        user_id=current_user.id,
        post_id=post_id
    )
    
    db.session.add(comment)
    db.session.commit()
    
    # Create notification for post author
    if post.user_id != current_user.id:
        create_notification(
            post.user_id,
            'New Comment',
            f'{current_user.username} commented on your post "{post.title}"'
        )
    
    flash('Comment added successfully!', 'success')
    log_siem_event(
        event_type='comment_create',
        message=f'User {current_user.username} added a comment',
        severity='info',
        user=current_user,
        ip_address=request.remote_addr,
        source='comment'
    )
    return redirect(url_for('post_detail', post_id=post_id))

# File download route
@app.route('/download/<filename>')
@login_required
def download_file(filename):
    log_siem_event(
        event_type='download',
        message=f'User {current_user.username} downloaded file {filename}',
        severity='info',
        user=current_user,
        ip_address=request.remote_addr,
        source='download'
    )
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# AI Assistant routes
@app.route('/ai_chat', methods=['POST'])
@login_required
def ai_chat():
    try:
        user_message = request.json.get('message', '')
        if not user_message:
            return jsonify({'error': 'No message provided'}), 400
        
        response = get_ai_response(user_message)
        return jsonify({'response': response})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Cyber Labs routes
@app.route('/labs')
def cyber_labs():
    # Filter labs based on user access
    if current_user.is_authenticated:
        if current_user.is_permanently_banned() or current_user.is_temporarily_banned():
            flash('You cannot access labs while your account is suspended.', 'error')
            return redirect(url_for('ban_notification'))
        
        if current_user.has_active_premium() or is_platform_free_mode():
            labs = Lab.query.filter_by(is_active=True).all()
        else:
            labs = Lab.query.filter_by(is_active=True, is_premium=False).all()
    else:
        labs = Lab.query.filter_by(is_active=True, is_premium=False).all()
    
    # Get user's completed labs
    completed_labs = []
    if current_user.is_authenticated:
        completed_labs = [comp.lab_id for comp in LabCompletion.query.filter_by(user_id=current_user.id).all()]
    
    return render_template('cyber_labs.html', labs=labs, completed_labs=completed_labs)

@app.route('/lab/<int:lab_id>')
@login_required
def lab_detail(lab_id):
    # Check if user is banned
    if current_user.is_permanently_banned() or current_user.is_temporarily_banned():
        flash('You cannot access labs while your account is suspended.', 'error')
        return redirect(url_for('ban_notification'))
    
    lab = Lab.query.get_or_404(lab_id)
    
    # Check access permissions
    if lab.is_premium and not current_user.has_active_premium():
        flash('This lab requires premium access. Upgrade your account to continue.', 'warning')
        return redirect(url_for('cyber_labs'))
    
    # Redirect terminal labs to terminal interface
    if lab.lab_type == 'terminal':
        return render_template('terminal_lab.html', lab=lab)
    
    # Check if user has completed this lab
    completion = LabCompletion.query.filter_by(user_id=current_user.id, lab_id=lab_id).first()
    
    # Get user's progress on this lab
    user_hints_used = session.get(f'lab_{lab_id}_hints_used', 0)
    
    # Fetch quiz questions (ordered)
    quiz_questions = LabQuizQuestion.query.filter_by(lab_id=lab_id).order_by(LabQuizQuestion.order).all()
    
    # Fetch user's quiz attempt if any
    quiz_attempt = LabQuizAttempt.query.filter_by(user_id=current_user.id, lab_id=lab_id).first()
    user_answers = {}
    if quiz_attempt and quiz_attempt.answers:
        try:
            user_answers = json.loads(quiz_attempt.answers)
        except Exception:
            user_answers = {}
    
    # Fetch user's command attempt from session (optional, for feedback)
    last_command = session.get(f'lab_{lab_id}_last_command', '')
    last_output = session.get(f'lab_{lab_id}_last_output', '')
    
    return render_template('lab_detail.html', lab=lab, completion=completion, hints_used=user_hints_used, quiz_questions=quiz_questions, quiz_attempt=quiz_attempt, user_answers=user_answers, last_command=last_command, last_output=last_output)

@app.route('/lab/<int:lab_id>/submit_flag', methods=['POST'])
@login_required
def submit_flag(lab_id):
    lab = Lab.query.get_or_404(lab_id)
    submitted_flag = request.form.get('flag', '').strip()
    
    # Check if already completed
    existing_completion = LabCompletion.query.filter_by(user_id=current_user.id, lab_id=lab_id).first()
    if existing_completion:
        flash('You have already completed this lab!', 'info')
        return redirect(url_for('lab_detail', lab_id=lab_id))
    
    # Validate flag
    if submitted_flag == lab.flag:
        # Mark as completed
        completion = LabCompletion(user_id=current_user.id, lab_id=lab_id)
        db.session.add(completion)
        
        # Award points to user
        current_user.reputation += lab.points
        
        # Log the achievement
        action = UserAction(
            user_id=current_user.id,
            action_type='lab_completed',
            target_type='lab',
            target_id=lab_id,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        db.session.add(action)
        db.session.commit()
        update_user_streak(current_user.id)
        check_and_unlock_achievements(current_user)
        flash('Congratulations! You completed the lab and earned points!', 'success')
        log_siem_event(
            event_type='lab_complete',
            message=f'User {current_user.username} completed lab {lab_id}',
            severity='info',
            user=current_user,
            ip_address=request.remote_addr,
            source='lab'
        )
        return redirect(url_for('lab_detail', lab_id=lab_id))
    else:
        flash('Incorrect flag. Try again!', 'error')
        return redirect(url_for('lab_detail', lab_id=lab_id))

@app.route('/lab/<int:lab_id>/get_hint', methods=['POST'])
@login_required
def get_hint(lab_id):
    lab = Lab.query.get_or_404(lab_id)
    
    # Track hints used in session
    session_key = f'lab_{lab_id}_hints_used'
    hints_used = session.get(session_key, 0)
    
    if hints_used == 0 and lab.hints:
        session[session_key] = 1
        return jsonify({'success': True, 'hint': lab.hints})
    else:
        return jsonify({'success': False, 'message': 'No more hints available for this lab.'})

@app.route('/lab/<int:lab_id>/reset', methods=['POST'])
@login_required
def reset_lab(lab_id):
    # Reset user's progress on the lab
    session_key = f'lab_{lab_id}_hints_used'
    session.pop(session_key, None)
    
    flash('Lab progress has been reset.', 'info')
    return redirect(url_for('lab_detail', lab_id=lab_id))

@app.route('/lab/<int:lab_id>/submit_quiz', methods=['POST'])
@login_required
def submit_quiz(lab_id):
    lab = Lab.query.get_or_404(lab_id)
    quiz_questions = LabQuizQuestion.query.filter_by(lab_id=lab_id).order_by(LabQuizQuestion.order).all()
    answers = {}
    score = 0
    for q in quiz_questions:
        user_answer = request.form.get(f'q_{q.id}', '').strip()
        answers[str(q.id)] = user_answer
        if user_answer == q.correct_answer:
            score += 1
    # Save attempt
    attempt = LabQuizAttempt.query.filter_by(user_id=current_user.id, lab_id=lab_id).first()
    if not attempt:
        attempt = LabQuizAttempt(user_id=current_user.id, lab_id=lab_id)
        db.session.add(attempt)
    attempt.answers = json.dumps(answers)
    attempt.score = score
    db.session.commit()
    flash(f'Quiz submitted! You scored {score} out of {len(quiz_questions)}.', 'success')
    log_siem_event(
        event_type='quiz_submit',
        message=f'User {current_user.username} submitted quiz for lab {lab_id}',
        severity='info',
        user=current_user,
        ip_address=request.remote_addr,
        source='lab'
    )
    return redirect(url_for('lab_detail', lab_id=lab_id))

@app.route('/lab/<int:lab_id>/submit_command', methods=['POST'])
@login_required
def submit_command(lab_id):
    lab = Lab.query.get_or_404(lab_id)
    user_command = request.form.get('user_command', '').strip()
    user_output = request.form.get('user_output', '').strip()
    # Check if already completed
    if LabCompletion.query.filter_by(user_id=current_user.id, lab_id=lab_id).first():
        flash('You have already completed this lab!', 'info')
        return redirect(url_for('lab_detail', lab_id=lab_id))
    # Check required command
    command_ok = True
    if lab.required_command:
        command_ok = (user_command.strip() == lab.required_command.strip())
    # Check output/flag
    output_ok = True
    if lab.command_success_criteria:
        output_ok = (lab.command_success_criteria.strip() in user_output)
    if command_ok and output_ok:
        completion = LabCompletion(user_id=current_user.id, lab_id=lab_id)
        db.session.add(completion)
        # Award points
        current_user.reputation += lab.points
        db.session.commit()
        update_user_streak(current_user.id)
        check_and_unlock_achievements(current_user)
        flash(f'Success! You completed the hacking lab and earned {lab.points} reputation points!', 'success')
        return redirect(url_for('lab_detail', lab_id=lab_id))
    else:
        flash('Incorrect command or output. Please try again.', 'error')
    return redirect(url_for('lab_detail', lab_id=lab_id))

# Store routes
@app.route('/store')
@login_required
def store():
    # Check if user has active premium subscription
    if not current_user.has_active_premium():
        flash('Premium subscription required to access the store. Please activate your premium account.', 'error')
        return redirect(url_for('activate_premium'))
    
    premium_posts = Post.query.filter_by(is_premium=True).order_by(desc(Post.created_at)).all()
    # Pass a default category for the category_bar macro
    return render_template('store.html', premium_posts=premium_posts, is_free_mode=is_platform_free_mode(), category='tools')

@app.route('/purchase/<int:post_id>', methods=['POST'])
@login_required
def purchase_post(post_id):
    # Check if user has active premium subscription
    if not current_user.has_active_premium():
        flash('Premium subscription required to make purchases.', 'error')
        return redirect(url_for('activate_premium'))
    
    post = Post.query.get_or_404(post_id)
    
    if not post.is_premium:
        flash('This item is not available for purchase.', 'error')
        return redirect(url_for('post_detail', post_id=post_id))
    
    # Check if user already purchased this post
    payment_service = PaymentService()
    if payment_service.has_user_purchased(current_user.id, post_id):
        flash('You have already purchased this item.', 'info')
        return redirect(url_for('post_detail', post_id=post_id))
    
    # Check if user is trying to purchase their own post
    if post.user_id == current_user.id:
        flash('You cannot purchase your own content.', 'error')
        return redirect(url_for('post_detail', post_id=post_id))
    
    try:
        # Create order
        items = [{'post_id': post_id, 'price': post.price, 'quantity': 1}]
        order = payment_service.create_order(current_user, items)
        
        # Initialize payment
        callback_url = url_for('payment_callback', _external=True)
        payment_result = payment_service.initialize_payment(order, callback_url)
        
        if payment_result['success']:
            return redirect(payment_result['authorization_url'])
        else:
            flash(f'Payment initialization failed: {payment_result["message"]}', 'error')
            return redirect(url_for('post_detail', post_id=post_id))
            
    except Exception as e:
        flash(f'Purchase failed: {str(e)}', 'error')
        return redirect(url_for('post_detail', post_id=post_id))

@app.route('/payment/callback')
def payment_callback():
    reference = request.args.get('reference')
    if not reference:
        flash('Invalid payment reference.', 'error')
        return redirect(url_for('store'))
    
    payment_service = PaymentService()
    result = payment_service.verify_payment(reference)
    
    if result['success']:
        flash('Payment successful! You can now access your purchased content.', 'success')
        return redirect(url_for('my_purchases'))
    else:
        flash(f'Payment verification failed: {result["message"]}', 'error')
        return redirect(url_for('store'))

@app.route('/my-purchases')
@login_required
def my_purchases():
    payment_service = PaymentService()
    purchases = payment_service.get_user_purchases(current_user.id)
    return render_template('my_purchases.html', purchases=purchases)

@app.route('/creator-dashboard')
@login_required
def creator_dashboard():
    payment_service = PaymentService()
    
    # Get creator's posts
    creator_posts = Post.query.filter_by(user_id=current_user.id, is_premium=True).all()
    
    # Get earnings
    total_earnings = payment_service.get_creator_earnings(current_user.id)
    
    # Get wallet
    wallet = payment_service.get_user_wallet(current_user.id)
    
    # Get recent sales
    recent_sales = Purchase.query.join(Post).filter(
        Post.user_id == current_user.id,
        Purchase.status == 'completed'
    ).order_by(Purchase.purchase_date.desc()).limit(10).all()
    
    return render_template('creator_dashboard.html', 
                         creator_posts=creator_posts,
                         total_earnings=total_earnings,
                         wallet=wallet,
                         recent_sales=recent_sales)

@app.route('/download-purchased/<int:post_id>')
@login_required
def download_purchased(post_id):
    post = Post.query.get_or_404(post_id)
    
    # Check if user has purchased this post or if platform is in free mode
    payment_service = PaymentService()
    if not payment_service.has_user_purchased(current_user.id, post_id) and not is_platform_free_mode():
        flash('You need to purchase this content first.', 'error')
        return redirect(url_for('post_detail', post_id=post_id))
    
    if not post.file_path or not os.path.exists(post.file_path):
        flash('File not found.', 'error')
        return redirect(url_for('post_detail', post_id=post_id))
    
    # Log download action
    action = UserAction(
        user_id=current_user.id,
        action_type='file_download',
        target_type='post',
        target_id=post_id,
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent')
    )
    db.session.add(action)
    db.session.commit()
    
    return send_from_directory(app.config['UPLOAD_FOLDER'], post.file_name, as_attachment=True)

@app.route('/wallet/withdraw', methods=['POST'])
@login_required
def withdraw_funds():
    amount = float(request.form.get('amount', 0))
    
    if amount <= 0:
        flash('Invalid withdrawal amount.', 'error')
        return redirect(url_for('creator_dashboard'))
    
    payment_service = PaymentService()
    wallet = payment_service.get_user_wallet(current_user.id)
    
    if wallet.balance < amount:
        flash('Insufficient balance for withdrawal.', 'error')
        return redirect(url_for('creator_dashboard'))
    
    # Create withdrawal transaction
    withdrawal = WalletTransaction(
        wallet_id=wallet.id,
        transaction_type='withdrawal',
        amount=-amount,
        description=f'Withdrawal request for ${amount:.2f}',
        reference=f'WTH-{datetime.utcnow().strftime("%Y%m%d")}-{uuid.uuid4().hex[:8].upper()}'
    )
    
    wallet.balance -= amount
    
    db.session.add(withdrawal)
    db.session.commit()
    
    flash(f'Withdrawal request submitted for ${amount:.2f}. You will receive payment within 3-5 business days.', 'success')
    return redirect(url_for('creator_dashboard'))

# Admin routes
@app.route('/admin')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))
    
    # Basic stats
    total_users = User.query.count()
    total_posts = Post.query.count()
    premium_users = User.query.filter_by(is_premium=True).count()
    banned_users = User.query.filter_by(is_banned=True).count()
    total_downloads = UserAction.query.filter_by(action_type='file_download').count()
    total_views = sum(post.views for post in Post.query.all())
    
    # Contact statistics
    pending_contacts = Contact.query.filter_by(status='pending').count()
    total_contacts = Contact.query.count()
    
    # Recent activity
    recent_users = User.query.order_by(desc(User.created_at)).limit(10).all()
    recent_posts = Post.query.order_by(desc(Post.created_at)).limit(10).all()
    recent_actions = UserAction.query.order_by(desc(UserAction.timestamp)).limit(20).all()
    
    # Revenue calculation (mock for now)
    revenue = sum(post.price for post in Post.query.filter(Post.price > 0).all()) * 0.15  # 15% commission
    
    return render_template('admin_dashboard.html', 
                         total_users=total_users, total_posts=total_posts,
                         premium_users=premium_users, banned_users=banned_users,
                         total_downloads=total_downloads, total_views=total_views,
                         revenue=revenue, recent_users=recent_users,
                         recent_posts=recent_posts, posts=recent_posts,
                         recent_actions=recent_actions, users=recent_users,
                         pending_contacts=pending_contacts, total_contacts=total_contacts)

@app.route('/admin/toggle_feature/<int:post_id>')
@login_required
def toggle_featured(post_id):
    if not current_user.is_admin:
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    post = Post.query.get_or_404(post_id)
    post.is_featured = not post.is_featured
    db.session.commit()
    
    flash(f'Post {"featured" if post.is_featured else "unfeatured"} successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/toggle_user_status/<int:user_id>')
@login_required
def toggle_user_status(user_id):
    if not current_user.is_admin:
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    user = User.query.get_or_404(user_id)
    if user.username == 'admin':
        flash('Cannot modify admin user.', 'error')
        return redirect(url_for('admin_dashboard'))
    
    user.is_premium = not user.is_premium
    db.session.commit()
    
    flash(f'User {user.username} premium status updated!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/users')
@login_required
def admin_users():
    if not current_user.is_admin:
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    users = User.query.order_by(desc(User.created_at)).all()
    return render_template('admin_users.html', users=users)

@app.route('/admin/ban_user/<int:user_id>', methods=['POST'])
@login_required
def ban_user(user_id):
    if not current_user.is_admin:
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    user = User.query.get_or_404(user_id)
    if user.username == 'admin':
        flash('Cannot ban admin user.', 'error')
        return redirect(url_for('admin_users'))
    
    reason = request.form.get('reason', 'Violation of community guidelines')
    ban_type = request.form.get('ban_type', 'temporary')
    
    user.is_banned = True
    if ban_type == 'mute':
        user.is_muted = True
        user.is_banned = False
    
    ban_record = UserBan(
        user_id=user_id,
        banned_by=current_user.id,
        reason=reason,
        ban_type=ban_type
    )
    
    db.session.add(ban_record)
    db.session.commit()
    
    flash(f'User {user.username} has been {ban_type}!', 'success')
    log_siem_event(
        event_type='admin_ban',
        message=f'Admin {current_user.username} banned user {user_id}',
        severity='warning',
        user=current_user,
        ip_address=request.remote_addr,
        source='admin'
    )
    return redirect(url_for('admin_users'))

@app.route('/admin/unban_user/<int:user_id>', methods=['POST'])
@login_required
def unban_user(user_id):
    if not current_user.is_admin:
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    user = User.query.get_or_404(user_id)
    user.is_banned = False
    user.is_muted = False
    
    # Deactivate ban records
    UserBan.query.filter_by(user_id=user_id, is_active=True).update({'is_active': False})
    
    db.session.commit()
    flash(f'User {user.username} has been unbanned!', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/settings', methods=['GET', 'POST'])
@login_required
def admin_settings():
    if not current_user.is_admin:
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        # Handle platform free mode toggle
        platform_free_mode = request.form.get('platform_free_mode') == 'on'
        if set_platform_free_mode(platform_free_mode):
            mode_text = 'enabled' if platform_free_mode else 'disabled'
            flash(f'Platform free mode {mode_text} successfully!', 'success')
        else:
            flash('Failed to update platform free mode setting.', 'error')
        
        # Handle SMTP security radio button
        smtp_security = request.form.get('smtp_security', 'tls')
        smtp_use_tls = 'true' if smtp_security == 'tls' else 'false'
        smtp_use_ssl = 'true' if smtp_security == 'ssl' else 'false'

        # Update API keys and settings
        settings_to_update = [
            ('openai_api_key', 'OpenAI API Key for AI Assistant'),
            ('paystack_public_key', 'Paystack Public Key for Payments'),
            ('paystack_secret_key', 'Paystack Secret Key for Payments'),
            ('commission_rate', 'Platform Commission Rate (%)'),
            ('platform_name', 'Platform Name'),
            ('max_file_size', 'Maximum File Upload Size (MB)'),
            # SMTP Settings
            ('smtp_server', 'SMTP Server Address'),
            ('smtp_port', 'SMTP Port Number'),
            ('smtp_username', 'SMTP Username/Email'),
            ('smtp_password', 'SMTP Password/App Password'),
            ('smtp_from_email', 'SMTP From Email Address'),
            ('smtp_from_name', 'SMTP From Name'),
            ('smtp_use_tls', 'SMTP Use TLS'),
            ('smtp_use_ssl', 'SMTP Use SSL')
        ]
        
        for key, description in settings_to_update:
            if key == 'smtp_use_tls':
                value = smtp_use_tls
            elif key == 'smtp_use_ssl':
                value = smtp_use_ssl
            else:
                value = request.form.get(key)
            if value is not None:
                setting = AdminSettings.query.filter_by(key=key).first()
                if setting:
                    setting.value = value
                    setting.updated_by = current_user.id
                    setting.updated_at = datetime.utcnow()
                else:
                    setting = AdminSettings(
                        key=key,
                        value=value,
                        description=description,
                        updated_by=current_user.id
                    )
                    db.session.add(setting)
        
        db.session.commit()
        flash('Settings updated successfully!', 'success')
        return redirect(url_for('admin_settings'))
    
    # Get current settings
    settings = {s.key: s.value for s in AdminSettings.query.all()}
    return render_template('admin_settings.html', settings=settings, is_free_mode=is_platform_free_mode())

@app.route('/admin/test-smtp', methods=['POST'])
@login_required
def test_smtp_connection():
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Access denied.'})
    
    try:
        # Get SMTP settings from form
        smtp_settings = {
            'smtp_server': request.form.get('smtp_server'),
            'smtp_port': request.form.get('smtp_port'),
            'smtp_username': request.form.get('smtp_username'),
            'smtp_password': request.form.get('smtp_password'),
            'smtp_use_tls': request.form.get('smtp_use_tls') == 'true',
            'smtp_use_ssl': request.form.get('smtp_use_ssl') == 'true'
        }
        
        # Validate required fields
        required_fields = ['smtp_server', 'smtp_port', 'smtp_username', 'smtp_password']
        for field in required_fields:
            if not smtp_settings[field]:
                return jsonify({
                    'success': False, 
                    'message': f'Missing required field: {field}'
                })
        
        # Test connection
        import smtplib
        import ssl
        
        try:
            # Create SMTP connection
            if smtp_settings['smtp_use_ssl']:
                server = smtplib.SMTP_SSL(smtp_settings['smtp_server'], int(smtp_settings['smtp_port']))
            else:
                server = smtplib.SMTP(smtp_settings['smtp_server'], int(smtp_settings['smtp_port']))
            
            # Start TLS if required
            if smtp_settings['smtp_use_tls']:
                server.starttls(context=ssl.create_default_context())
            
            # Login
            server.login(smtp_settings['smtp_username'], smtp_settings['smtp_password'])
            
            # Close connection
            server.quit()
            
            return jsonify({
                'success': True,
                'message': 'SMTP connection test successful! Your email configuration is working correctly.'
            })
            
        except smtplib.SMTPAuthenticationError:
            return jsonify({
                'success': False,
                'message': 'Authentication failed. Please check your username and password/app password.'
            })
        except smtplib.SMTPConnectError:
            return jsonify({
                'success': False,
                'message': 'Connection failed. Please check your SMTP server and port settings.'
            })
        except smtplib.SMTPException as e:
            return jsonify({
                'success': False,
                'message': f'SMTP error: {str(e)}'
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Connection test failed: {str(e)}'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Test failed: {str(e)}'
        })

@app.route('/admin/analytics')
@login_required
def admin_analytics():
    if not current_user.is_admin:
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    # User analytics
    total_users = User.query.count()
    new_users_today = User.query.filter(User.created_at >= datetime.utcnow().date()).count()
    premium_users = User.query.filter_by(is_premium=True).count()
    banned_users = User.query.filter_by(is_banned=True).count()
    
    # Content analytics
    total_posts = Post.query.count()
    premium_posts = Post.query.filter_by(is_premium=True).count()
    featured_posts = Post.query.filter_by(is_featured=True).count()
    total_views = sum(post.views for post in Post.query.all())
    
    # Category breakdown
    tools_count = Post.query.filter_by(category='tools').count()
    bugs_count = Post.query.filter_by(category='bugs').count()
    ideas_count = Post.query.filter_by(category='ideas').count()
    jobs_count = Post.query.filter_by(category='jobs').count()
    
    # Revenue analytics
    total_revenue = sum(post.price for post in Post.query.filter(Post.price > 0).all())
    platform_revenue = total_revenue * 0.15  # 15% commission
    
    # Download statistics
    total_downloads = UserAction.query.filter_by(action_type='file_download').count()
    
    # Popular posts
    popular_posts = Post.query.order_by(desc(Post.views)).limit(10).all()
    
    return render_template('admin_analytics.html',
                         total_users=total_users, new_users_today=new_users_today,
                         premium_users=premium_users, banned_users=banned_users,
                         total_posts=total_posts, premium_posts=premium_posts,
                         featured_posts=featured_posts, total_views=total_views,
                         tools_count=tools_count, bugs_count=bugs_count,
                         ideas_count=ideas_count, jobs_count=jobs_count,
                         total_revenue=total_revenue, platform_revenue=platform_revenue,
                         total_downloads=total_downloads, popular_posts=popular_posts)

@app.route('/admin/activity')
@login_required
def admin_activity():
    if not current_user.is_admin:
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    page = request.args.get('page', 1, type=int)
    actions = UserAction.query.order_by(desc(UserAction.timestamp)).paginate(
        page=page, per_page=50, error_out=False)
    
    return render_template('admin_activity.html', actions=actions)

# Follow/Unfollow routes
@app.route('/follow/<username>')
@login_required
def follow_user(username):
    user = User.query.filter_by(username=username).first_or_404()
    if user == current_user:
        flash('You cannot follow yourself!', 'error')
        return redirect(url_for('user_profile', username=username))
    
    if Follow.query.filter_by(follower_id=current_user.id, followed_id=user.id).first():
        flash('You are already following this user!', 'info')
        return redirect(url_for('user_profile', username=username))
    
    follow = Follow(follower_id=current_user.id, followed_id=user.id)
    db.session.add(follow)
    db.session.commit()
    
    create_notification(user.id, 'New Follower', f'{current_user.username} started following you!')
    flash(f'You are now following {username}!', 'success')
    return redirect(url_for('user_profile', username=username))

@app.route('/unfollow/<username>')
@login_required
def unfollow_user(username):
    user = User.query.filter_by(username=username).first_or_404()
    follow = Follow.query.filter_by(follower_id=current_user.id, followed_id=user.id).first()
    
    if follow:
        db.session.delete(follow)
        db.session.commit()
        flash(f'You unfollowed {username}.', 'success')
    else:
        flash('You are not following this user.', 'info')
    
    return redirect(url_for('user_profile', username=username))

# Like/Unlike routes
@app.route('/like_post/<int:post_id>', methods=['POST'])
@login_required
def like_post(post_id):
    # Check if user is banned or muted
    if current_user.is_permanently_banned() or current_user.is_temporarily_banned() or current_user.is_muted_user():
        return jsonify({'success': False, 'message': 'You cannot like posts while your account is suspended or muted.'})
    
    post = Post.query.get_or_404(post_id)
    
    # Check if user already liked this post
    existing_like = PostLike.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    
    if existing_like:
        # Unlike the post
        db.session.delete(existing_like)
        post.likes -= 1
        db.session.commit()
        return jsonify({'success': True, 'liked': False, 'count': post.likes})
    else:
        # Like the post
        like = PostLike(user_id=current_user.id, post_id=post_id)
        db.session.add(like)
        post.likes += 1
        db.session.commit()
        
        # Create notification for post author
        if post.user_id != current_user.id:
            create_notification(
                post.user_id,
                'Post Liked',
                f'{current_user.username} liked your post "{post.title}"'
            )
        
        return jsonify({'success': True, 'liked': True, 'count': post.likes})

@app.route('/like_comment/<int:comment_id>', methods=['POST'])
@login_required
def like_comment(comment_id):
    # Check if user is banned or muted
    if current_user.is_permanently_banned() or current_user.is_temporarily_banned() or current_user.is_muted_user():
        return jsonify({'success': False, 'message': 'You cannot like comments while your account is suspended or muted.'})
    
    comment = Comment.query.get_or_404(comment_id)
    
    # Check if user already liked this comment
    existing_like = CommentLike.query.filter_by(user_id=current_user.id, comment_id=comment_id).first()
    
    if existing_like:
        # Unlike the comment
        db.session.delete(existing_like)
        db.session.commit()
        return jsonify({'success': True, 'liked': False})
    else:
        # Like the comment
        like = CommentLike(user_id=current_user.id, comment_id=comment_id)
        db.session.add(like)
        db.session.commit()
        
        # Create notification for comment author
        if comment.user_id != current_user.id:
            create_notification(
                comment.user_id,
                'Comment Liked',
                f'{current_user.username} liked your comment'
            )
        
        return jsonify({'success': True, 'liked': True})

# Admin: List Labs
@app.route('/admin/labs')
@login_required
def admin_labs():
    if not current_user.is_admin:
        abort(403)
    labs = Lab.query.order_by(Lab.id.desc()).all()
    return render_template('admin_labs.html', labs=labs)

# Admin: Create Lab
@app.route('/admin/labs/new', methods=['GET', 'POST'])
@login_required
def admin_create_lab():
    if not current_user.is_admin:
        abort(403)
    if request.method == 'POST':
        data = request.form
        lab = Lab(
            title=data['title'],
            description=data['description'],
            difficulty=data['difficulty'],
            category=data['category'],
            lab_type=data.get('lab_type', 'standard'),
            points=int(data['points']),
            hints=data.get('hints', ''),
            solution=data.get('solution', ''),
            flag=data['flag'],
            instructions=data.get('instructions', ''),
            tools_needed=data.get('tools_needed', ''),
            learning_objectives=data.get('learning_objectives', ''),
            is_premium=('is_premium' in data),
            is_active=('is_active' in data),
            estimated_time=int(data.get('estimated_time', 0)),
            sandbox_url=data.get('sandbox_url', ''),
            sandbox_instructions=data.get('sandbox_instructions', ''),
            required_command=data.get('required_command', ''),
            command_success_criteria=data.get('command_success_criteria', ''),
            # Terminal lab fields
            terminal_enabled=(data.get('lab_type') == 'terminal'),
            terminal_instructions=data.get('terminal_instructions', ''),
            terminal_shell=data.get('terminal_shell', 'bash'),
            terminal_timeout=int(data.get('terminal_timeout', 300)),
            allow_command_hints=('allow_command_hints' in data),
            strict_order=('strict_order' in data),
            allow_retry=('allow_retry' in data)
        )
        db.session.add(lab)
        db.session.commit()
        update_user_streak(current_user.id)
        check_and_unlock_achievements(current_user)
        flash('Lab created!', 'success')
        return redirect(url_for('admin_labs'))
    return render_template('admin_lab_form.html', lab=None)

# Admin: Edit Lab
@app.route('/admin/labs/edit/<int:lab_id>', methods=['GET', 'POST'])
@login_required
def admin_edit_lab(lab_id):
    if not current_user.is_admin:
        abort(403)
    lab = Lab.query.get_or_404(lab_id)
    if request.method == 'POST':
        data = request.form
        lab.title = data['title']
        lab.description = data['description']
        lab.difficulty = data['difficulty']
        lab.category = data['category']
        lab.lab_type = data.get('lab_type', 'standard')
        lab.points = int(data['points'])
        lab.hints = data.get('hints', '')
        lab.solution = data.get('solution', '')
        lab.flag = data['flag']
        lab.instructions = data.get('instructions', '')
        lab.tools_needed = data.get('tools_needed', '')
        lab.learning_objectives = data.get('learning_objectives', '')
        lab.is_premium = ('is_premium' in data)
        lab.is_active = ('is_active' in data)
        lab.estimated_time = int(data.get('estimated_time', 0))
        lab.sandbox_url = data.get('sandbox_url', '')
        lab.sandbox_instructions = data.get('sandbox_instructions', '')
        lab.required_command = data.get('required_command', '')
        lab.command_success_criteria = data.get('command_success_criteria', '')
        # Terminal lab fields
        lab.terminal_enabled = (data.get('lab_type') == 'terminal')
        lab.terminal_instructions = data.get('terminal_instructions', '')
        lab.terminal_shell = data.get('terminal_shell', 'bash')
        lab.terminal_timeout = int(data.get('terminal_timeout', 300))
        lab.allow_command_hints = ('allow_command_hints' in data)
        lab.strict_order = ('strict_order' in data)
        lab.allow_retry = ('allow_retry' in data)
        db.session.commit()
        update_user_streak(current_user.id)
        check_and_unlock_achievements(current_user)
        flash('Lab updated!', 'success')
        return redirect(url_for('admin_labs'))
    # Attach options_list for quiz questions
    if lab.quiz_questions:
        for q in lab.quiz_questions:
            try:
                q.options_list = json.loads(q.options)
            except Exception:
                q.options_list = []
    return render_template('admin_lab_form.html', lab=lab)

# Admin: Delete Lab
@app.route('/admin/labs/delete/<int:lab_id>', methods=['POST'])
@login_required
def admin_delete_lab(lab_id):
    if not current_user.is_admin:
        abort(403)
    lab = Lab.query.get_or_404(lab_id)
    db.session.delete(lab)
    db.session.commit()
    flash('Lab deleted.', 'info')
    return redirect(url_for('admin_labs'))

@app.route('/admin/labs/<int:lab_id>/add_quiz_question', methods=['POST'])
@login_required
def admin_add_quiz_question(lab_id):
    if not current_user.is_admin:
        abort(403)
    lab = Lab.query.get_or_404(lab_id)
    question = request.form['question']
    options = [opt.strip() for opt in request.form['options'].split(',') if opt.strip()]
    correct_answer = request.form['correct_answer']
    explanation = request.form.get('explanation', '')
    marks = int(request.form.get('marks', 1))
    order = len(lab.quiz_questions)
    qq = LabQuizQuestion(
        lab_id=lab.id,
        question=question,
        options=json.dumps(options),
        correct_answer=correct_answer,
        explanation=explanation,
        marks=marks,
        order=order
    )
    db.session.add(qq)
    db.session.commit()
    flash('Quiz question added!', 'success')
    return redirect(url_for('admin_edit_lab', lab_id=lab.id))

@app.route('/admin/labs/<int:lab_id>/delete_quiz_question/<int:question_id>', methods=['POST'])
@login_required
def admin_delete_quiz_question(lab_id, question_id):
    if not current_user.is_admin:
        abort(403)
    qq = LabQuizQuestion.query.get_or_404(question_id)
    db.session.delete(qq)
    db.session.commit()
    flash('Quiz question deleted.', 'info')
    return redirect(url_for('admin_edit_lab', lab_id=lab_id))

# Terminal Command Management Routes
@app.route('/admin/labs/<int:lab_id>/add_terminal_command', methods=['POST'])
@login_required
def admin_add_terminal_command(lab_id):
    if not current_user.is_admin:
        abort(403)
    
    lab = Lab.query.get_or_404(lab_id)
    
    try:
        order = int(request.form.get('order', 1))
        command = request.form.get('command', '').strip()
        expected_output = request.form.get('expected_output', '').strip()
        points = int(request.form.get('points', 1))
        hint = request.form.get('hint', '').strip()
        description = request.form.get('description', '').strip()
        is_optional = 'is_optional' in request.form
        
        if not command:
            flash('Command is required.', 'error')
            return redirect(url_for('admin_edit_lab', lab_id=lab_id))
        
        # Create terminal command
        terminal_command = LabTerminalCommand(
            lab_id=lab_id,
            command=command,
            expected_output=expected_output if expected_output else None,
            order=order,
            points=points,
            hint=hint if hint else None,
            description=description if description else None,
            is_optional=is_optional
        )
        
        db.session.add(terminal_command)
        db.session.commit()
        
        flash('Terminal command added successfully!', 'success')
        
    except ValueError as e:
        flash(f'Invalid input: {str(e)}', 'error')
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding command: {str(e)}', 'error')
    
    return redirect(url_for('admin_edit_lab', lab_id=lab_id))

@app.route('/admin/labs/<int:lab_id>/edit_terminal_command/<int:command_id>', methods=['POST'])
@login_required
def admin_edit_terminal_command(lab_id, command_id):
    if not current_user.is_admin:
        abort(403)
    
    command = LabTerminalCommand.query.get_or_404(command_id)
    
    try:
        command.order = int(request.form.get('order', command.order))
        command.command = request.form.get('command', '').strip()
        command.expected_output = request.form.get('expected_output', '').strip()
        command.points = int(request.form.get('points', command.points))
        command.hint = request.form.get('hint', '').strip()
        command.description = request.form.get('description', '').strip()
        command.is_optional = 'is_optional' in request.form
        
        if not command.command:
            flash('Command is required.', 'error')
            return redirect(url_for('admin_edit_lab', lab_id=lab_id))
        
        db.session.commit()
        flash('Terminal command updated successfully!', 'success')
        
    except ValueError as e:
        flash(f'Invalid input: {str(e)}', 'error')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating command: {str(e)}', 'error')
    
    return redirect(url_for('admin_edit_lab', lab_id=lab_id))

@app.route('/admin/labs/<int:lab_id>/delete_terminal_command/<int:command_id>', methods=['POST'])
@login_required
def admin_delete_terminal_command(lab_id, command_id):
    if not current_user.is_admin:
        abort(403)
    
    command = LabTerminalCommand.query.get_or_404(command_id)
    
    try:
        db.session.delete(command)
        db.session.commit()
        flash('Terminal command deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting command: {str(e)}', 'error')
    
    return redirect(url_for('admin_edit_lab', lab_id=lab_id))

@app.route('/admin/labs/<int:lab_id>/reorder_terminal_commands', methods=['POST'])
@login_required
def admin_reorder_terminal_commands(lab_id, command_id):
    if not current_user.is_admin:
        abort(403)
    
    try:
        command_orders = request.get_json()
        if not command_orders:
            return jsonify({'success': False, 'message': 'No data provided'})
        
        for command_id, new_order in command_orders.items():
            command = LabTerminalCommand.query.get(command_id)
            if command and command.lab_id == lab_id:
                command.order = new_order
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Commands reordered successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error reordering commands: {str(e)}'})

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    ip = request.remote_addr
    path = request.path
    now = datetime.utcnow()
    # Log all 404s
    log_siem_event(
        event_type='not_found',
        message=f'404 on {path}',
        severity='info',
        ip_address=ip,
        source='security'
    )
    # Track repeated 404s for brute force
    REPEATED_404S[ip] = [t for t in REPEATED_404S[ip] if (now - t).total_seconds() < ADMIN_404_WINDOW]
    REPEATED_404S[ip].append(now)
    # If path is sensitive or repeated 404s, escalate
    if path in SENSITIVE_PATHS or any(s in path for s in SENSITIVE_PATHS):
        log_siem_event(
            event_type='sensitive_404',
            message=f'404 on sensitive path {path}',
            severity='warning',
            ip_address=ip,
            source='security'
        )
        if len(REPEATED_404S[ip]) >= ADMIN_404_THRESHOLD:
            log_siem_event(
                event_type='dir_bruteforce_detected',
                message=f'Repeated 404s from {ip} (possible dir brute force)',
                severity='critical',
                ip_address=ip,
                source='security'
            )
            add_blocked_ip(ip, reason='Directory brute force detected', blocked_by='SIEM')
            REPEATED_404S[ip] = []
    return make_response(render_template('404.html'), 404)

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500

# Admin Content Deletion Routes
@app.route('/admin/delete/post/<int:post_id>', methods=['POST'])
@login_required
def admin_delete_post(post_id):
    """Admin can delete any post (premium or not, purchased or not)"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))
    
    post = Post.query.get_or_404(post_id)
    
    try:
        # Delete associated purchases
        Purchase.query.filter_by(post_id=post_id).delete()
        
        # Delete associated comments
        Comment.query.filter_by(post_id=post_id).delete()
        
        # Delete associated likes
        PostLike.query.filter_by(post_id=post_id).delete()
        
        # Delete associated user actions
        UserAction.query.filter_by(target_type='post', target_id=post_id).delete()
        
        # Delete the post file if it exists
        if post.file_path and os.path.exists(post.file_path):
            os.remove(post.file_path)
        
        # Delete the post
        db.session.delete(post)
        db.session.commit()
        
        flash(f'Post "{post.title}" has been permanently deleted along with all associated data.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting post: {str(e)}', 'error')
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete/comment/<int:comment_id>', methods=['POST'])
@login_required
def admin_delete_comment(comment_id):
    """Admin can delete any comment"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))
    
    comment = Comment.query.get_or_404(comment_id)
    
    try:
        # Delete associated likes
        CommentLike.query.filter_by(comment_id=comment_id).delete()
        
        # Delete associated user actions
        UserAction.query.filter_by(target_type='comment', target_id=comment_id).delete()
        
        # Delete the comment
        db.session.delete(comment)
        db.session.commit()
        
        flash(f'Comment has been permanently deleted.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting comment: {str(e)}', 'error')
    
    return redirect(request.referrer or url_for('admin_dashboard'))

@app.route('/admin/delete/lab/<int:lab_id>', methods=['POST'])
@login_required
def admin_delete_lab_comprehensive(lab_id):
    """Admin can delete any lab with all associated data"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))
    
    lab = Lab.query.get_or_404(lab_id)
    
    try:
        # Delete lab completions
        LabCompletion.query.filter_by(lab_id=lab_id).delete()
        
        # Delete quiz attempts
        LabQuizAttempt.query.filter_by(lab_id=lab_id).delete()
        
        # Delete quiz questions
        LabQuizQuestion.query.filter_by(lab_id=lab_id).delete()
        
        # Delete terminal commands
        LabTerminalCommand.query.filter_by(lab_id=lab_id).delete()
        
        # Delete terminal attempts
        LabTerminalAttempt.query.filter_by(lab_id=lab_id).delete()
        
        # Delete terminal sessions
        LabTerminalSession.query.filter_by(lab_id=lab_id).delete()
        
        # Delete associated user actions
        UserAction.query.filter_by(target_type='lab', target_id=lab_id).delete()
        
        # Delete the lab
        db.session.delete(lab)
        db.session.commit()
        
        flash(f'Lab "{lab.title}" has been permanently deleted along with all associated data.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting lab: {str(e)}', 'error')
    
    return redirect(url_for('admin_labs'))

@app.route('/admin/delete/user/<int:user_id>', methods=['POST'])
@login_required
def admin_delete_user(user_id):
    """Admin can delete any user (except other admins) with all their content"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))
    
    user = User.query.get_or_404(user_id)
    
    # Prevent deletion of admin users
    if user.is_admin:
        flash('Cannot delete admin users.', 'error')
        return redirect(url_for('admin_users'))
    
    # Prevent self-deletion
    if user.id == current_user.id:
        flash('Cannot delete your own account.', 'error')
        return redirect(url_for('admin_users'))
    
    try:
        # Delete user's posts and associated data
        user_posts = Post.query.filter_by(user_id=user_id).all()
        for post in user_posts:
            # Delete post purchases
            Purchase.query.filter_by(post_id=post.id).delete()
            # Delete post comments
            Comment.query.filter_by(post_id=post.id).delete()
            # Delete post likes
            PostLike.query.filter_by(post_id=post.id).delete()
            # Delete post file
            if post.file_path and os.path.exists(post.file_path):
                os.remove(post.file_path)
        
        # Delete user's comments and associated likes
        user_comments = Comment.query.filter_by(user_id=user_id).all()
        for comment in user_comments:
            CommentLike.query.filter_by(comment_id=comment.id).delete()
        
        # Delete user's lab completions
        LabCompletion.query.filter_by(user_id=user_id).delete()
        
        # Delete user's quiz attempts
        LabQuizAttempt.query.filter_by(user_id=user_id).delete()
        
        # Delete user's terminal attempts and sessions
        LabTerminalAttempt.query.filter_by(user_id=user_id).delete()
        LabTerminalSession.query.filter_by(user_id=user_id).delete()
        
        # Delete user's purchases
        Purchase.query.filter_by(user_id=user_id).delete()
        
        # Delete user's wallet and transactions
        wallet = UserWallet.query.filter_by(user_id=user_id).first()
        if wallet:
            WalletTransaction.query.filter_by(wallet_id=wallet.id).delete()
            db.session.delete(wallet)
        
        # Delete user's orders and items
        user_orders = Order.query.filter_by(user_id=user_id).all()
        for order in user_orders:
            OrderItem.query.filter_by(order_id=order.id).delete()
        
        # Delete user's subscriptions
        PremiumSubscription.query.filter_by(user_id=user_id).delete()
        
        # Delete user's activation keys
        ActivationKey.query.filter_by(used_by=user_id).delete()
        
        # Delete user's bans
        UserBan.query.filter_by(user_id=user_id).delete()
        
        # Delete user's follows
        Follow.query.filter_by(follower_id=user_id).delete()
        Follow.query.filter_by(followed_id=user_id).delete()
        
        # Delete user's likes
        PostLike.query.filter_by(user_id=user_id).delete()
        CommentLike.query.filter_by(user_id=user_id).delete()
        
        # Delete user's notifications
        Notification.query.filter_by(user_id=user_id).delete()
        
        # Delete user's actions
        UserAction.query.filter_by(user_id=user_id).delete()
        
        # Delete user's contact messages
        Contact.query.filter_by(user_id=user_id).delete()
        
        # Delete user's conversations and messages
        user_conversations = db.session.query(Conversation).join(ConversationParticipant).filter(
            ConversationParticipant.user_id == user_id
        ).all()
        
        for conv in user_conversations:
            # Delete messages in conversation
            Message.query.filter_by(conversation_id=conv.id).delete()
            # Delete read receipts
            MessageReadReceipt.query.filter_by(conversation_id=conv.id).delete()
            # Delete participants
            ConversationParticipant.query.filter_by(conversation_id=conv.id).delete()
        
        # Delete user's conversation participations
        ConversationParticipant.query.filter_by(user_id=user_id).delete()
        
        # Delete user's posts, comments, orders
        Post.query.filter_by(user_id=user_id).delete()
        Comment.query.filter_by(user_id=user_id).delete()
        Order.query.filter_by(user_id=user_id).delete()
        
        # Finally delete the user
        db.session.delete(user)
        db.session.commit()
        
        flash(f'User "{user.username}" has been permanently deleted along with all their content and data.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting user: {str(e)}', 'error')
    
    return redirect(url_for('admin_users'))

@app.route('/admin/delete/purchase/<int:purchase_id>', methods=['POST'])
@login_required
def admin_delete_purchase(purchase_id):
    """Admin can delete any purchase record"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))
    
    purchase = Purchase.query.get_or_404(purchase_id)
    
    try:
        db.session.delete(purchase)
        db.session.commit()
        
        flash(f'Purchase record has been permanently deleted.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting purchase: {str(e)}', 'error')
    
    return redirect(request.referrer or url_for('admin_dashboard'))

@app.route('/admin/delete/order/<int:order_id>', methods=['POST'])
@login_required
def admin_delete_order(order_id):
    """Admin can delete any order with all its items"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))
    
    order = Order.query.get_or_404(order_id)
    
    try:
        # Delete order items
        OrderItem.query.filter_by(order_id=order_id).delete()
        
        # Delete the order
        db.session.delete(order)
        db.session.commit()
        
        flash(f'Order #{order.order_number} has been permanently deleted.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting order: {str(e)}', 'error')
    
    return redirect(request.referrer or url_for('admin_dashboard'))

@app.route('/admin/delete/contact/<int:contact_id>', methods=['POST'])
@login_required
def admin_delete_contact(contact_id):
    """Admin can delete any contact message"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))
    
    contact = Contact.query.get_or_404(contact_id)
    
    try:
        db.session.delete(contact)
        db.session.commit()
        
        flash(f'Contact message has been permanently deleted.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting contact: {str(e)}', 'error')
    
    return redirect(url_for('admin_contacts'))

@app.route('/admin/delete/conversation/<int:conversation_id>', methods=['POST'])
@login_required
def admin_delete_conversation(conversation_id):
    """Admin can delete any conversation with all its messages"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))
    
    conversation = Conversation.query.get_or_404(conversation_id)
    
    try:
        # Delete messages in conversation
        Message.query.filter_by(conversation_id=conversation_id).delete()
        
        # Delete read receipts
        MessageReadReceipt.query.filter_by(conversation_id=conversation_id).delete()
        
        # Delete participants
        ConversationParticipant.query.filter_by(conversation_id=conversation_id).delete()
        
        # Delete the conversation
        db.session.delete(conversation)
        db.session.commit()
        
        flash(f'Conversation has been permanently deleted along with all messages.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting conversation: {str(e)}', 'error')
    
    return redirect(request.referrer or url_for('admin_dashboard'))

@app.route('/admin/delete/activation-key/<int:key_id>', methods=['POST'])
@login_required
def admin_delete_activation_key(key_id):
    """Admin can delete any activation key"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))
    
    activation_key = ActivationKey.query.filter_by(id=key_id).first_or_404()
    
    try:
        # Delete associated subscription if key was used
        if activation_key.is_used:
            PremiumSubscription.query.filter_by(activation_key_id=key_id).delete()
        
        db.session.delete(activation_key)
        db.session.commit()
        
        flash(f'Activation key has been permanently deleted.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting activation key: {str(e)}', 'error')
    
    return redirect(url_for('admin_activation_keys'))

@app.route('/admin/delete/payment-plan/<int:plan_id>', methods=['POST'])
@login_required
def admin_delete_payment_plan(plan_id):
    """Admin can delete any payment plan"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))
    
    plan = PaymentPlan.query.get_or_404(plan_id)
    
    try:
        db.session.delete(plan)
        db.session.commit()
        
        flash(f'Payment plan "{plan.display_name}" has been permanently deleted.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting payment plan: {str(e)}', 'error')
    
    return redirect(url_for('admin_payment_plans'))

@app.route('/edit_post/<int:post_id>', methods=['GET', 'POST'])
@login_required
def edit_post(post_id):
    post = Post.query.get_or_404(post_id)
    
    # Check if user owns this post
    if post.user_id != current_user.id:
        flash('You can only edit your own posts.', 'error')
        return redirect(url_for('post_detail', post_id=post_id))
    
    if request.method == 'POST':
        post.title = request.form['title']
        post.content = request.form['content']
        post.category = request.form['category']
        post.tags = request.form.get('tags', '')
        
        # Handle price changes for premium content
        new_price = float(request.form.get('price', 0.0))
        if post.is_premium and new_price != post.price:
            # Check if anyone has purchased this post
            existing_purchases = Purchase.query.filter_by(post_id=post.id, status='completed').count()
            if existing_purchases > 0:
                flash('Cannot change price for posts that have been purchased. Contact admin if needed.', 'error')
                return redirect(url_for('edit_post', post_id=post_id))
            post.price = new_price
        
        # Handle file upload (only if no existing file or user wants to replace)
        if 'file' in request.files and request.files['file'].filename:
            file = request.files['file']
            if file and allowed_file(file.filename):
                # Remove old file if it exists
                if post.file_path and os.path.exists(post.file_path):
                    os.remove(post.file_path)
                
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                post.file_path = file_path
                post.file_name = filename
        
        # Handle premium status toggle
        is_premium = 'is_premium' in request.form
        if is_premium != post.is_premium:
            if is_premium and post.price <= 0:
                flash('Premium content must have a price greater than 0.', 'error')
                return redirect(url_for('edit_post', post_id=post_id))
            post.is_premium = is_premium
        
        db.session.commit()
        flash('Post updated successfully!', 'success')
        return redirect(url_for('post_detail', post_id=post.id))
    
    return render_template('edit_post.html', post=post)

@app.route('/delete_post/<int:post_id>', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    
    # Check if user owns this post (unless admin)
    if post.user_id != current_user.id and not current_user.is_admin:
        flash('You can only delete your own posts.', 'error')
        return redirect(url_for('post_detail', post_id=post_id))
    
    # Check if premium post has been purchased (unless admin)
    if post.is_premium and not current_user.is_admin:
        existing_purchases = Purchase.query.filter_by(post_id=post.id, status='completed').count()
        if existing_purchases > 0:
            flash('Cannot delete premium content that has been purchased. Contact admin if needed.', 'error')
            return redirect(url_for('post_detail', post_id=post_id))
    
    try:
        # Delete associated order items first
        OrderItem.query.filter_by(post_id=post_id).delete()
        # Delete associated purchases
        Purchase.query.filter_by(post_id=post_id).delete()
        # Delete associated comments
        Comment.query.filter_by(post_id=post_id).delete()
        # Delete associated likes
        PostLike.query.filter_by(post_id=post_id).delete()
        # Delete associated user actions
        UserAction.query.filter_by(target_type='post', target_id=post_id).delete()
        # Delete associated file if it exists
        if post.file_path and os.path.exists(post.file_path):
            os.remove(post.file_path)
        # Delete the post
        db.session.delete(post)
        db.session.commit()
        flash('Post deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting post: {str(e)}', 'error')
    return redirect(url_for('profile'))

# Activation Key routes
@app.route('/activate', methods=['GET', 'POST'])
@login_required
def activate_premium():
    if request.method == 'POST':
        activation_key = request.form.get('activation_key', '').strip()
        
        if not activation_key:
            flash('Please enter an activation key.', 'error')
            return redirect(url_for('activate_premium'))
        
        # Find the activation key
        key = ActivationKey.query.filter_by(key=activation_key).first()
        
        if not key:
            flash('Invalid activation key.', 'error')
            return redirect(url_for('activate_premium'))
        
        if key.is_used:
            flash('This activation key has already been used.', 'error')
            return redirect(url_for('activate_premium'))
        
        if key.expires_at and key.expires_at < datetime.utcnow():
            flash('This activation key has expired.', 'error')
            return redirect(url_for('activate_premium'))
        
        # Calculate subscription end date
        end_date = datetime.utcnow() + timedelta(days=key.duration_days)
        
        # Create subscription
        subscription = PremiumSubscription(
            user_id=current_user.id,
            activation_key_id=key.id,
            plan_type=key.plan_type,
            end_date=end_date,
            amount_paid=key.price
        )
        
        # Mark key as used
        key.is_used = True
        key.used_by = current_user.id
        key.used_at = datetime.utcnow()
        
        # Update user premium status
        current_user.is_premium = True
        
        db.session.add(subscription)
        db.session.commit()
        
        flash(f'Premium activated successfully! Your subscription expires on {end_date.strftime("%B %d, %Y")}.', 'success')
        return redirect(url_for('store'))
    
    # Always fetch active payment plans for display
    payment_plans = PaymentPlan.query.filter_by(is_active=True).order_by(PaymentPlan.duration_days).all()
    return render_template('activate_premium.html', payment_plans=payment_plans, is_free_mode=is_platform_free_mode())

@app.route('/contact', methods=['GET', 'POST'])
@login_required
def contact():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        subject = request.form.get('subject', '').strip()
        message = request.form.get('message', '').strip()
        
        # Validation
        if not all([name, email, subject, message]):
            flash('Please fill in all fields.', 'error')
            return redirect(url_for('contact'))
        
        if len(message) < 10:
            flash('Message must be at least 10 characters long.', 'error')
            return redirect(url_for('contact'))
        
        # Create contact message
        contact_msg = Contact(
            user_id=current_user.id,
            name=name,
            email=email,
            subject=subject,
            message=message
        )
        
        db.session.add(contact_msg)
        db.session.commit()
        
        flash('Your message has been sent successfully! We will get back to you within 24 hours.', 'success')
        log_siem_event(
            event_type='contact',
            message=f'User {current_user.username} submitted contact form',
            severity='info',
            user=current_user,
            ip_address=request.remote_addr,
            source='contact'
        )
        return redirect(url_for('contact'))
    
    return render_template('contact.html')

@app.route('/admin/activation-keys', methods=['GET', 'POST'])
@login_required
def admin_activation_keys():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        try:
            plan_type = request.form.get('plan_type')
            quantity = int(request.form.get('quantity', 1))
            price = float(request.form.get('price', 0))
            
            if not plan_type:
                flash('Please select a plan type.', 'error')
                return redirect(url_for('admin_activation_keys'))
            
            if quantity <= 0 or quantity > 100:
                flash('Quantity must be between 1 and 100.', 'error')
                return redirect(url_for('admin_activation_keys'))
            
            if price < 0:
                flash('Price cannot be negative.', 'error')
                return redirect(url_for('admin_activation_keys'))
            
            # Set duration based on plan type
            duration_map = {
                'monthly': 30,
                'yearly': 365,
                'lifetime': 9999
            }
            duration_days = duration_map.get(plan_type, 30)
            
            # Generate keys
            import secrets
            import string
            
            generated_count = 0
            for _ in range(quantity):
                # Generate unique key
                attempts = 0
                while attempts < 100:  # Prevent infinite loop
                    key = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(16))
                    if not ActivationKey.query.filter_by(key=key).first():
                        break
                    attempts += 1
                
                if attempts >= 100:
                    flash('Failed to generate unique key after 100 attempts.', 'error')
                    return redirect(url_for('admin_activation_keys'))
                
                # Set expiration (30 days from now for unused keys)
                expires_at = datetime.utcnow() + timedelta(days=30)
                
                activation_key = ActivationKey(
                    key=key,
                    plan_type=plan_type,
                    duration_days=duration_days,
                    price=price,
                    created_by=current_user.id,
                    expires_at=expires_at
                )
                db.session.add(activation_key)
                generated_count += 1
            
            db.session.commit()
            flash(f'{generated_count} activation key(s) generated successfully!', 'success')
            
        except ValueError as e:
            flash(f'Invalid input: {str(e)}', 'error')
        except Exception as e:
            db.session.rollback()
            flash(f'Error generating keys: {str(e)}', 'error')
        
        return redirect(url_for('admin_activation_keys'))
    
    # Get all activation keys
    activation_keys = ActivationKey.query.order_by(ActivationKey.created_at.desc()).all()
    
    return render_template('admin_activation_keys.html', 
                         activation_keys=activation_keys,
                         now=datetime.utcnow())

@app.route('/admin/activation-keys/delete/<int:key_id>', methods=['POST'])
@login_required
def delete_activation_key(key_id):
    if not current_user.is_admin:
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    key = ActivationKey.query.get_or_404(key_id)
    
    if key.is_used:
        flash('Cannot delete used activation keys.', 'error')
    else:
        db.session.delete(key)
        db.session.commit()
        flash('Activation key deleted successfully!', 'success')
    
    return redirect(url_for('admin_activation_keys'))

# Payment Plan Management Routes
@app.route('/admin/payment-plans', methods=['GET', 'POST'])
@login_required
def admin_payment_plans():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        # If adding a new plan
        if request.form.get('action') == 'add':
            try:
                name = request.form.get('name', '').strip().lower()
                display_name = request.form.get('display_name', '').strip()
                price = float(request.form.get('price', 0))
                duration_days = int(request.form.get('duration_days', 0))
                description = request.form.get('description', '').strip()
                features = request.form.get('features', '').strip()
                features_list = [f.strip() for f in features.split(',') if f.strip()]

                if not name or not display_name or price < 0 or duration_days <= 0:
                    flash('Please fill all required fields and ensure values are valid.', 'error')
                    return redirect(url_for('admin_payment_plans'))

                # Check for duplicate name
                if PaymentPlan.query.filter_by(name=name).first():
                    flash('A plan with this name already exists.', 'error')
                    return redirect(url_for('admin_payment_plans'))

                plan = PaymentPlan(
                    name=name,
                    display_name=display_name,
                    price=price,
                    duration_days=duration_days,
                    description=description,
                    features=features_list,
                    is_active=True
                )
                db.session.add(plan)
                db.session.commit()
                flash(f'Payment plan "{display_name}" added successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error adding plan: {str(e)}', 'error')
            return redirect(url_for('admin_payment_plans'))
        # Otherwise, update price as before
        try:
            plan_id = request.form.get('plan_id')
            new_price = float(request.form.get('price', 0))
            if new_price < 0:
                flash('Price cannot be negative.', 'error')
                return redirect(url_for('admin_payment_plans'))
            plan = PaymentPlan.query.get_or_404(plan_id)
            plan.price = new_price
            plan.updated_at = datetime.utcnow()
            db.session.commit()
            flash(f'Price updated for {plan.display_name} to ${new_price:.2f}', 'success')
        except ValueError as e:
            flash(f'Invalid price: {str(e)}', 'error')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating plan: {str(e)}', 'error')
        return redirect(url_for('admin_payment_plans'))
    
    # Get all payment plans
    payment_plans = PaymentPlan.query.filter_by(is_active=True).order_by(PaymentPlan.duration_days).all()
    
    return render_template('admin_payment_plans.html', payment_plans=payment_plans)

@app.route('/admin/payment-plans/toggle/<int:plan_id>', methods=['POST'])
@login_required
def toggle_payment_plan(plan_id):
    if not current_user.is_admin:
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    plan = PaymentPlan.query.get_or_404(plan_id)
    plan.is_active = not plan.is_active
    plan.updated_at = datetime.utcnow()
    
    db.session.commit()
    
    status = 'activated' if plan.is_active else 'deactivated'
    flash(f'{plan.display_name} {status} successfully!', 'success')
    
    return redirect(url_for('admin_payment_plans'))

# Payment Plan Selection and Purchase Routes
@app.route('/plans')
def view_plans():
    """Show available payment plans to users"""
    payment_plans = PaymentPlan.query.filter_by(is_active=True).order_by(PaymentPlan.duration_days).all()
    return render_template('payment_plans.html', payment_plans=payment_plans, is_free_mode=is_platform_free_mode())

@app.route('/purchase-plan/<int:plan_id>', methods=['POST'])
@login_required
def purchase_plan(plan_id):
    """Initiate payment for a specific plan"""
    plan = PaymentPlan.query.get_or_404(plan_id)
    
    if not plan.is_active:
        flash('This plan is not available for purchase.', 'error')
        return redirect(url_for('view_plans'))
    
    # Check if user already has an active subscription
    if current_user.has_active_premium():
        flash('You already have an active premium subscription.', 'info')
        return redirect(url_for('store'))
    
    # Check if platform is in free mode
    if is_platform_free_mode():
        # Automatically grant premium access without payment
        try:
            # Generate activation key for this user
            import secrets
            import string
            
            # Generate unique key
            while True:
                key = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(16))
                if not ActivationKey.query.filter_by(key=key).first():
                    break
            
            # Create activation key
            activation_key = ActivationKey(
                key=key,
                plan_type=plan.name,
                duration_days=plan.duration_days,
                price=0.0,  # Free in free mode
                created_by=1,  # Admin user ID
                expires_at=datetime.utcnow() + timedelta(days=30)
            )
            
            # Create subscription
            end_date = datetime.utcnow() + timedelta(days=plan.duration_days)
            subscription = PremiumSubscription(
                user_id=current_user.id,
                activation_key_id=activation_key.id,
                plan_type=plan.name,
                end_date=end_date,
                amount_paid=0.0  # Free in free mode
            )
            
            # Mark key as used
            activation_key.is_used = True
            activation_key.used_by = current_user.id
            activation_key.used_at = datetime.utcnow()
            
            # Update user premium status
            current_user.is_premium = True
            
            db.session.add(activation_key)
            db.session.add(subscription)
            db.session.commit()
            
            flash(f'Premium access granted! Your {plan.display_name} is now active. (Free Mode)', 'success')
            return redirect(url_for('store'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error granting premium access: {str(e)}', 'error')
            return redirect(url_for('view_plans'))
    
    # Normal payment flow for premium mode
    try:
        # Initialize payment with Paystack
        payment_service = PaymentService()
        
        # Create a unique reference for this payment
        import uuid
        reference = f"plan_{plan.id}_{current_user.id}_{uuid.uuid4().hex[:8]}"
        
        # Create payment initialization
        payment_data = {
            'amount': int(plan.price * 100),  # Convert to kobo (smallest currency unit)
            'email': current_user.email,
            'reference': reference,
            'callback_url': url_for('plan_payment_callback', _external=True),
            'metadata': {
                'plan_id': plan.id,
                'user_id': current_user.id,
                'plan_name': plan.name,
                'duration_days': plan.duration_days
            }
        }
        
        # Initialize payment
        paystack_url = f"https://api.paystack.co/transaction/initialize"
        headers = {
            'Authorization': f'Bearer {payment_service.paystack_secret_key}',
            'Content-Type': 'application/json'
        }
        data = payment_data.copy()
        response = requests.post(paystack_url, headers=headers, json=data)
        result = response.json()
        if result.get('status'):
            session['pending_plan_payment'] = {
                'reference': reference,
                'plan_id': plan.id,
                'amount': plan.price
            }
            return redirect(result['data']['authorization_url'])
        else:
            flash('Payment initialization failed. Please try again.', 'error')
            return redirect(url_for('view_plans'))
            
    except Exception as e:
        flash(f'Payment error: {str(e)}', 'error')
        return redirect(url_for('view_plans'))

@app.route('/plan-payment/callback')
def plan_payment_callback():
    """Handle Paystack payment callback for plan purchases"""
    try:
        payment_service = PaymentService()
        reference = request.args.get('reference')
        
        if not reference:
            flash('Invalid payment reference.', 'error')
            return redirect(url_for('view_plans'))
        
        # Verify payment
        verification = payment_service.verify_payment(reference)
        print('Paystack verification response:', verification)
        # Accept both 'success' and 'completed' as valid statuses, or verification['success']
        valid_status = False
        if verification.get('success'):
            valid_status = True
        elif verification.get('status'):
            data_status = verification.get('data', {}).get('status', '').lower()
            if data_status in ['success', 'completed']:
                valid_status = True
        if valid_status:
            # Get pending payment info from session
            pending_payment = session.get('pending_plan_payment')
            plan = None
            # Try to recover plan_id if session is missing or mismatched
            if not pending_payment or pending_payment['reference'] != reference:
                # Try to get plan_id from Paystack metadata
                metadata = verification['data'].get('metadata', {})
                plan_id = metadata.get('plan_id')
                if not plan_id:
                    # Try to extract from reference (format: plan_<plan_id>_<user_id>_<random>)
                    try:
                        parts = reference.split('_')
                        plan_id = int(parts[1])
                    except Exception:
                        flash('Payment verification failed: could not determine plan.', 'error')
                        return redirect(url_for('view_plans'))
                plan = PaymentPlan.query.get(plan_id)
                if not plan:
                    flash('Plan not found.', 'error')
                    return redirect(url_for('view_plans'))
            else:
                plan = PaymentPlan.query.get(pending_payment['plan_id'])
            # Generate activation key for this user
            import secrets
            import string
            while True:
                key = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(16))
                if not ActivationKey.query.filter_by(key=key).first():
                    break
            activation_key = ActivationKey(
                key=key,
                plan_type=plan.name,
                duration_days=plan.duration_days,
                price=plan.price,
                created_by=1,  # Admin user ID
                expires_at=datetime.utcnow() + timedelta(days=30)
            )
            activation_key.is_used = True
            activation_key.used_by = current_user.id
            activation_key.used_at = datetime.utcnow()
            db.session.add(activation_key)
            db.session.flush()  # Ensure activation_key.id is set
            end_date = datetime.utcnow() + timedelta(days=plan.duration_days)
            subscription = PremiumSubscription(
                user_id=current_user.id,
                activation_key_id=activation_key.id,
                plan_type=plan.name,
                end_date=end_date,
                amount_paid=plan.price
            )
            current_user.is_premium = True
            db.session.add(subscription)
            db.session.commit()
            # Clear session if present
            session.pop('pending_plan_payment', None)
            # Send activation key email to user
            subject = f"Your PentraX Premium Activation Key & Subscription Details"
            body = f"""Dear {current_user.username},\n\nThank you for your purchase of the {plan.display_name} on PentraX!\n\nYour activation key: {key}\nPlan: {plan.display_name}\nDuration: {plan.duration_days} days\nAmount Paid: ${plan.price:.2f}\n\nYour premium access is now active.\n\nIf you need to activate on another device, use the activation key above.\n\nBest regards,\nPentraX Team"""
            html_body = f"""
            <html>
            <body>
                <h2 style='color:#007bff;'>PentraX Premium Activated!</h2>
                <p>Dear <strong>{current_user.username}</strong>,</p>
                <p>Thank you for your purchase of the <strong>{plan.display_name}</strong> on PentraX!</p>
                <div style='background:#f8f9fa;padding:15px;border-left:4px solid #007bff;margin:20px 0;'>
                    <strong>Activation Key:</strong> <code style='font-size:1.2em'>{key}</code><br>
                    <strong>Plan:</strong> {plan.display_name}<br>
                    <strong>Duration:</strong> {plan.duration_days} days<br>
                    <strong>Amount Paid:</strong> ${plan.price:.2f}
                </div>
                <p>Your premium access is now <span style='color:green;font-weight:bold;'>active</span>.</p>
                <p>If you need to activate on another device, use the activation key above.</p>
                <p>Best regards,<br>PentraX Team</p>
            </body>
            </html>
            """
            send_email(current_user.email, subject, body, html_body)
            flash(f'Payment successful! Your {plan.display_name} is now active. Activation Key: {key}', 'success')
            return redirect(url_for('store'))
        else:
            flash(f'Payment verification failed. Response: {verification}', 'error')
            return redirect(url_for('view_plans'))
            
    except Exception as e:
        flash(f'Payment verification error: {str(e)}', 'error')
        return redirect(url_for('view_plans'))

# Terminal Lab Routes
@app.route('/lab/<int:lab_id>/terminal/session', methods=['POST'])
@login_required
def create_terminal_session(lab_id):
    lab = Lab.query.get_or_404(lab_id)
    
    # Check if user has access to this lab
    if lab.is_premium and not current_user.is_premium and not is_platform_free_mode():
        return jsonify({'success': False, 'message': 'Premium lab requires premium subscription'})
    
    # Check if lab is terminal-based
    if lab.lab_type != 'terminal':
        return jsonify({'success': False, 'message': 'This lab is not terminal-based'})
    
    try:
        from terminal_service import TerminalService
        terminal_service = TerminalService()
        
        # Create or get existing session
        existing_session = LabTerminalSession.query.filter_by(
            user_id=current_user.id,
            lab_id=lab_id,
            is_completed=False
        ).first()
        
        if existing_session:
            session = existing_session
        else:
            session = terminal_service.create_terminal_session(current_user.id, lab_id)
        
        if not session:
            return jsonify({'success': False, 'message': 'Failed to create session'})
        
        return jsonify({
            'success': True,
            'session': {
                'session_id': session.session_id,
                'current_step': session.current_step,
                'total_steps': session.total_steps,
                'completed_steps': session.completed_steps,
                'total_points': session.total_points,
                'max_points': session.max_points,
                'is_completed': session.is_completed
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/lab/<int:lab_id>/terminal/command', methods=['POST'])
@login_required
def execute_terminal_command(lab_id):
    lab = Lab.query.get_or_404(lab_id)
    
    if lab.lab_type != 'terminal':
        return jsonify({'success': False, 'message': 'This lab is not terminal-based'})
    
    data = request.get_json()
    session_id = data.get('session_id')
    command = data.get('command')
    
    if not session_id or not command:
        return jsonify({'success': False, 'message': 'Missing session_id or command'})
    
    try:
        from terminal_service import TerminalService
        terminal_service = TerminalService()
        
        # Validate command
        result = terminal_service.validate_command(session_id, command)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/lab/<int:lab_id>/terminal/current-command', methods=['POST'])
@login_required
def get_current_terminal_command(lab_id):
    lab = Lab.query.get_or_404(lab_id)
    
    if lab.lab_type != 'terminal':
        return jsonify({'success': False, 'message': 'This lab is not terminal-based'})
    
    data = request.get_json()
    session_id = data.get('session_id')
    
    if not session_id:
        return jsonify({'success': False, 'message': 'Missing session_id'})
    
    try:
        from terminal_service import TerminalService
        terminal_service = TerminalService()
        
        command = terminal_service.get_current_command(session_id)
        
        if command:
            return jsonify({
                'success': True,
                'command': {
                    'id': command.id,
                    'order': command.order,
                    'command': command.command,
                    'description': command.description,
                    'points': command.points,
                    'hint': command.hint,
                    'is_optional': command.is_optional
                }
            })
        else:
            return jsonify({'success': False, 'message': 'No current command found'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/lab/<int:lab_id>/terminal/hint', methods=['POST'])
@login_required
def get_terminal_hint(lab_id):
    lab = Lab.query.get_or_404(lab_id)
    
    if lab.lab_type != 'terminal':
        return jsonify({'success': False, 'message': 'This lab is not terminal-based'})
    
    if not lab.allow_command_hints:
        return jsonify({'success': False, 'message': 'Hints are not enabled for this lab'})
    
    data = request.get_json()
    session_id = data.get('session_id')
    
    if not session_id:
        return jsonify({'success': False, 'message': 'Missing session_id'})
    
    try:
        from terminal_service import TerminalService
        terminal_service = TerminalService()
        
        command = terminal_service.get_current_command(session_id)
        
        if command and command.hint:
            return jsonify({'success': True, 'hint': command.hint})
        else:
            return jsonify({'success': False, 'message': 'No hint available'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/lab/<int:lab_id>/terminal/reset', methods=['POST'])
@login_required
def reset_terminal_session(lab_id):
    lab = Lab.query.get_or_404(lab_id)
    
    if lab.lab_type != 'terminal':
        return jsonify({'success': False, 'message': 'This lab is not terminal-based'})
    
    data = request.get_json()
    session_id = data.get('session_id')
    
    if not session_id:
        return jsonify({'success': False, 'message': 'Missing session_id'})
    
    try:
        from terminal_service import TerminalService
        terminal_service = TerminalService()
        
        success = terminal_service.reset_session(session_id)
        
        return jsonify({'success': success, 'message': 'Session reset successfully' if success else 'Failed to reset session'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/lab/<int:lab_id>/terminal/progress', methods=['POST'])
@login_required
def get_terminal_progress(lab_id):
    lab = Lab.query.get_or_404(lab_id)
    
    if lab.lab_type != 'terminal':
        return jsonify({'success': False, 'message': 'This lab is not terminal-based'})
    
    data = request.get_json()
    session_id = data.get('session_id')
    
    if not session_id:
        return jsonify({'success': False, 'message': 'Missing session_id'})
    
    try:
        from terminal_service import TerminalService
        terminal_service = TerminalService()
        
        progress = terminal_service.get_session_progress(session_id)
        
        if progress:
            return jsonify({'success': True, 'progress': progress})
        else:
            return jsonify({'success': False, 'message': 'Session not found'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/ban-notification')
@login_required
def ban_notification():
    """Show ban notification page for banned users"""
    return render_template('ban_notification.html')

@app.before_request
def check_user_ban_status():
    """Check if user is banned and redirect to ban notification if necessary"""
    if current_user.is_authenticated:
        # Skip ban check for admin users
        if current_user.is_admin:
            return
        
        # Skip ban check for ban notification page itself
        if request.endpoint == 'ban_notification':
            return
        
        # Check if user is banned or muted
        if current_user.is_permanently_banned() or current_user.is_temporarily_banned() or current_user.is_muted_user():
            # Allow access to logout and ban notification
            if request.endpoint in ['logout', 'ban_notification']:
                return
            
            # Redirect to ban notification for all other routes
            return redirect(url_for('ban_notification'))

@app.route('/admin/contacts')
@login_required
def admin_contacts():
    if not current_user.is_admin:
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    # Get all contact submissions with user info
    contacts = Contact.query.order_by(desc(Contact.created_at)).all()
    return render_template('admin_contacts.html', contacts=contacts)

@app.route('/admin/contacts/<int:contact_id>')
@login_required
def admin_contact_detail(contact_id):
    if not current_user.is_admin:
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    contact = Contact.query.get_or_404(contact_id)
    return render_template('admin_contact_detail.html', contact=contact)

@app.route('/admin/contacts/<int:contact_id>/reply', methods=['POST'])
@login_required
def admin_contact_reply(contact_id):
    if not current_user.is_admin:
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    contact = Contact.query.get_or_404(contact_id)
    reply_message = request.form.get('reply_message', '').strip()
    
    if not reply_message:
        flash('Reply message cannot be empty.', 'error')
        return redirect(url_for('admin_contact_detail', contact_id=contact_id))
    
    try:
        from utils import send_contact_reply
        
        # Send email reply
        email_sent = send_contact_reply(
            contact_email=contact.email,
            contact_name=contact.name,
            original_subject=contact.subject,
            reply_message=reply_message,
            admin_name=current_user.username
        )
        
        if email_sent:
            # Update contact status
            contact.status = 'replied'
            contact.replied_at = datetime.utcnow()
            contact.replied_by = current_user.id
            contact.admin_notes = reply_message
            db.session.commit()
            
            flash('Reply sent successfully!', 'success')
        else:
            flash('Failed to send email reply. Please check your SMTP configuration.', 'error')
            
    except Exception as e:
        flash(f'Error sending reply: {str(e)}', 'error')
    
    return redirect(url_for('admin_contact_detail', contact_id=contact_id))

@app.route('/admin/contacts/<int:contact_id>/status', methods=['POST'])
@login_required
def admin_contact_status(contact_id):
    if not current_user.is_admin:
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    contact = Contact.query.get_or_404(contact_id)
    new_status = request.form.get('status', 'pending')
    
    if new_status in ['pending', 'read', 'replied', 'closed']:
        contact.status = new_status
        db.session.commit()
        flash(f'Contact status updated to {new_status}.', 'success')
    
    return redirect(url_for('admin_contact_detail', contact_id=contact.id))

@app.route('/admin/mass-mail', methods=['GET', 'POST'])
@login_required
def admin_mass_mail():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))

    from models import User
    from utils import send_email
    users = User.query.order_by(User.email).all()
    user_choices = [(u.email, f"{u.username} ({u.email})") for u in users]

    if request.method == 'POST':
        subject = request.form.get('subject', '').strip()
        message = request.form.get('message', '').strip()
        recipient = request.form.get('recipient', 'all')

        # Compose premium HTML email
        html_body = f'''
        <html>
        <body style="font-family: 'Segoe UI', Arial, sans-serif; background-color: #f4f6fb; margin: 0; padding: 0;">
          <table width="100%" bgcolor="#f4f6fb" cellpadding="0" cellspacing="0" style="padding: 0; margin: 0;">
            <tr>
              <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background: #fff; border-radius: 12px; box-shadow: 0 2px 16px rgba(0,0,0,0.07); margin: 40px 0;">
                  <tr>
                    <td style="background: #1a2235; border-radius: 12px 12px 0 0; padding: 32px 0; text-align: center;">
                      <h1 style="color: #fff; margin: 0; font-size: 2.2rem; letter-spacing: 2px;">PentraX Security</h1>
                      <p style="color: #b0b8d1; margin: 0; font-size: 1.1rem;">Your trusted cybersecurity platform</p>
                    </td>
                  </tr>
                  <tr>
                    <td style="padding: 36px 40px 24px 40px; color: #222;">
                      <h2 style="color: #007bff; margin-top: 0;">{subject}</h2>
                      <div style="font-size: 1.1rem; line-height: 1.7; color: #222; margin-bottom: 24px;">
                        {message.replace(chr(10), '<br>')}
                      </div>
                    </td>
                  </tr>
                  <tr>
                    <td style="padding: 0 40px 36px 40px;">
                      <div style="background: #f8f9fa; border-radius: 8px; padding: 18px 24px; color: #444; font-size: 1rem;">
                        <strong>Stay Secure:</strong> PentraX will never ask for your password or sensitive information by email.<br>
                        If you have any doubts, contact our support team directly from the platform.
                      </div>
                    </td>
                  </tr>
                  <tr>
                    <td style="background: #1a2235; border-radius: 0 0 12px 12px; padding: 18px 0; text-align: center; color: #b0b8d1; font-size: 0.95rem;">
                      &copy; {datetime.utcnow().year} PentraX Security. All rights reserved.
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
          </table>
        </body>
        </html>
        '''
        # ... existing code for sending email, using html_body as the HTML version ...

@app.route('/admin/mute_user/<int:user_id>', methods=['POST'])
@login_required
def mute_user(user_id):
    if not current_user.is_admin or current_user.id == user_id:
        abort(403)
    user = User.query.get_or_404(user_id)
    user.is_muted = True
    db.session.commit()
    flash(f'User {user.username} has been muted.', 'success')
    return redirect(request.referrer or url_for('user_profile', username=user.username))

@app.route('/admin/unmute_user/<int:user_id>', methods=['POST'])
@login_required
def unmute_user(user_id):
    if not current_user.is_admin:
        abort(403)
    user = User.query.get_or_404(user_id)
    user.is_muted = False
    db.session.commit()
    flash(f'User {user.username} has been unmuted.', 'success')
    return redirect(request.referrer or url_for('user_profile', username=user.username))

@app.route('/admin/delete/user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if not current_user.is_admin or current_user.id == user_id:
        abort(403)
    user = User.query.get_or_404(user_id)
    user.is_active = False
    db.session.commit()
    flash(f'User {user.username} has been deactivated.', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/reset_password/<int:user_id>', methods=['POST'])
@login_required
def reset_user_password(user_id):
    if not current_user.is_admin:
        abort(403)
    user = User.query.get_or_404(user_id)
    user.set_password('changeme123')
    db.session.commit()
    flash(f'Password for {user.username} has been reset to "changeme123".', 'info')
    return redirect(request.referrer or url_for('user_profile', username=user.username))

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/admin/siem')
@login_required
def admin_siem_dashboard():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))
    # Filters
    event_type = request.args.get('event_type')
    severity = request.args.get('severity')
    ip = request.args.get('ip')
    user = request.args.get('user')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    query = SIEMEvent.query
    if event_type:
        query = query.filter_by(event_type=event_type)
    if severity:
        query = query.filter_by(severity=severity)
    if ip:
        query = query.filter(SIEMEvent.ip_address == ip)
    if user:
        query = query.filter(SIEMEvent.username.ilike(f'%{user}%'))
    if date_from:
        query = query.filter(SIEMEvent.timestamp >= date_from)
    if date_to:
        query = query.filter(SIEMEvent.timestamp <= date_to)
    events = query.order_by(SIEMEvent.timestamp.desc()).limit(200).all()
    blocked_ips = get_blocked_ips()
    return render_template('admin_siem_dashboard.html', events=events, blocked_ips=blocked_ips, event_type=event_type, severity=severity, ip=ip, user=user, date_from=date_from, date_to=date_to)

@app.route('/admin/block_ip', methods=['POST'])
@login_required
def admin_block_ip():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))
    ip = request.form.get('ip')
    reason = request.form.get('reason') or 'manual block from SIEM dashboard'
    if not ip:
        flash('No IP address provided.', 'error')
        return redirect(url_for('admin_siem_dashboard'))
    add_blocked_ip(ip, reason=reason, blocked_by=current_user.username)
    flash(f'IP {ip} has been blocked.', 'success')
    return redirect(url_for('admin_siem_dashboard'))

@app.route('/admin/unblock_ip', methods=['POST'])
@login_required
def admin_unblock_ip():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))
    ip = request.form.get('ip')
    reason = request.form.get('reason') or 'manual unblock from SIEM dashboard'
    if not ip:
        flash('No IP address provided.', 'error')
        return redirect(url_for('admin_siem_dashboard'))
    unblock_ip(ip, reason=reason)
    flash(f'IP {ip} has been unblocked.', 'success')
    return redirect(url_for('admin_siem_dashboard'))

def get_blocked_ips():
    return BlockedIP.query.order_by(BlockedIP.blocked_at.desc()).all()

@app.route('/admin/deep_ip_scan')
@login_required
def admin_deep_ip_scan():
    if not current_user.is_admin:
        return {'error': 'Access denied'}, 403
    ip = request.args.get('ip')
    if not ip:
        return {'error': 'No IP provided'}, 400
    data = get_deep_ip_info(ip)
    return data

# Error handlers for unauthorized, forbidden, and rate limit
@app.errorhandler(401)
def unauthorized_error(error):
    log_siem_event(
        event_type='unauthorized_access',
        message=f'Unauthorized access attempt to {request.path}',
        severity='warning',
        ip_address=request.remote_addr,
        source='security'
    )
    return make_response(render_template('401.html'), 401)

@app.errorhandler(403)
def forbidden_error(error):
    log_siem_event(
        event_type='forbidden_access',
        message=f'Forbidden access attempt to {request.path}',
        severity='warning',
        ip_address=request.remote_addr,
        source='security'
    )
    return make_response(render_template('403.html'), 403)

@app.errorhandler(429)
def rate_limit_error(error):
    log_siem_event(
        event_type='rate_limit',
        message=f'Rate limit triggered for {request.remote_addr} on {request.path}',
        severity='warning',
        ip_address=request.remote_addr,
        source='security'
    )
    return make_response(render_template('429.html'), 429)

# Flag suspicious/attack patterns in before_request
@app.before_request
def flag_suspicious_requests():
    # Example: repeated failed logins, access to /admin by non-admins, suspicious user agents, etc.
    if request.path.startswith('/admin') and (not current_user.is_authenticated or not getattr(current_user, 'is_admin', False)):
        log_siem_event(
            event_type='suspicious_admin_access',
            message=f'Non-admin tried to access admin route: {request.path}',
            severity='warning',
            ip_address=request.remote_addr,
            source='security'
        )
    # Example: suspicious user agent
    if 'sqlmap' in (request.user_agent.string or '').lower():
        log_siem_event(
            event_type='attack_detected',
            message=f'SQLMap or automated tool detected: {request.user_agent.string}',
            severity='critical',
            ip_address=request.remote_addr,
            source='security'
        )

# In-memory store for repeated event aggregation (replace with Redis/DB for production)
FAILED_LOGIN_ATTEMPTS = defaultdict(list)  # {ip: [timestamps]}
ADMIN_ACCESS_ATTEMPTS = defaultdict(list)
MULTI_ACCOUNT_IPS = defaultdict(set)  # {ip: set(usernames)}
LAST_USER_IP = defaultdict(str)  # {username: last_ip}

# Helper: suspicious payload patterns
SUSPICIOUS_PATTERNS = [
    r"(\bselect\b|\binsert\b|\bupdate\b|\bdelete\b|\bdrop\b|\bunion\b|\b--|\b#|\b;|\b'\b|\b\"\b)",  # SQLi
    r"<script|onerror=|onload=|<img|<svg|javascript:",  # XSS
    r"(;|&&|\|\||`|\$\(|\bcat\b|\bwget\b|\bcurl\b|\bping\b|\bwhoami\b)",  # Command injection
]

# Helper: log and alert on repeated suspicious events
def alert_if_repeated(event_type, ip, threshold, window_sec=300):
    now = datetime.utcnow()
    store = FAILED_LOGIN_ATTEMPTS if event_type == 'login_failed' else ADMIN_ACCESS_ATTEMPTS
    store[ip] = [t for t in store[ip] if (now - t).total_seconds() < window_sec]
    store[ip].append(now)
    if len(store[ip]) >= threshold:
        log_siem_event(
            event_type=f'{event_type}_alert',
            message=f'{len(store[ip])} {event_type.replace("_", " ")}s from {ip} in {window_sec//60}min',
            severity='critical',
            ip_address=ip,
            source='security'
        )
        store[ip] = []  # reset after alert

@app.before_request
def advanced_intrusion_detection():
    ip = request.remote_addr
    path = request.path
    # 1. Detect repeated failed logins (brute force/credential stuffing)
    if path == '/login' and request.method == 'POST':
        username = request.form.get('username')
        user = User.query.filter_by(username=username).first()
        if not (user and user.check_password(request.form.get('password'))):
            alert_if_repeated('login_failed', ip, threshold=5)
    # 2. Detect repeated admin access attempts
    if path.startswith('/admin') and (not current_user.is_authenticated or not getattr(current_user, 'is_admin', False)):
        alert_if_repeated('admin_access', ip, threshold=3)
    # 3. Detect multiple accounts from same IP
    if current_user.is_authenticated:
        MULTI_ACCOUNT_IPS[ip].add(current_user.username)
        if len(MULTI_ACCOUNT_IPS[ip]) > 2:
            log_siem_event(
                event_type='multi_account_ip',
                message=f'Multiple accounts from IP {ip}: {list(MULTI_ACCOUNT_IPS[ip])}',
                severity='warning',
                ip_address=ip,
                source='security'
            )
    # 4. Detect geolocation/session hijacking
    if current_user.is_authenticated:
        last_ip = LAST_USER_IP.get(current_user.username)
        if last_ip and last_ip != ip:
            log_siem_event(
                event_type='session_hijack_possible',
                message=f'User {current_user.username} session from new IP {ip} (was {last_ip})',
                severity='warning',
                user=current_user,
                ip_address=ip,
                source='security'
            )
        LAST_USER_IP[current_user.username] = ip
    # 5. Detect suspicious payloads
    if request.method == 'POST':
        for k, v in request.form.items():
            for pat in SUSPICIOUS_PATTERNS:
                if re.search(pat, v, re.IGNORECASE):
                    log_siem_event(
                        event_type='suspicious_payload',
                        message=f'Suspicious input detected in {k} on {path}',
                        severity='critical',
                        ip_address=ip,
                        source='security',
                        raw_data={'field': k, 'value': v}
                    )
    # 6. Detect suspicious file uploads
    if request.files:
        for f in request.files.values():
            if f.filename.lower().endswith(('.php', '.exe', '.sh', '.bat', '.js', '.py', '.pl', '.rb')):
                log_siem_event(
                    event_type='suspicious_file_upload',
                    message=f'Suspicious file upload: {f.filename}',
                    severity='critical',
                    ip_address=ip,
                    source='security'
                )
    # 7. Detect access to other users' resources
    if '/user/' in path and current_user.is_authenticated:
        username = path.split('/user/')[-1].split('/')[0]
        if username != current_user.username and not current_user.is_admin:
            log_siem_event(
                event_type='unauthorized_user_resource',
                message=f'User {current_user.username} tried to access {username} profile/resource',
                severity='warning',
                user=current_user,
                ip_address=ip,
                source='security'
            )
    # 8. Detect requests from blocked/bad IPs
    if hasattr(g, 'blocked_ip') and g.blocked_ip:
        log_siem_event(
            event_type='blocked_ip_request',
            message=f'Request from blocked IP {ip}',
            severity='critical',
            ip_address=ip,
            source='firewall'
        )

# Add Nmap and port scan detection
NMAP_USER_AGENTS = [
    'nmap', 'masscan', 'zmap', 'netsparker', 'acunetix', 'sqlmap', 'nikto', 'wpscan', 'dirbuster', 'gobuster', 'fuzz', 'scanner'
]
PORT_SCAN_ATTEMPTS = defaultdict(list)  # {ip: [timestamps]}
UNCOMMON_PORTS = {2000, 5060, 8080, 8888, 3306, 5432, 6379, 11211, 27017, 5000, 9000, 10000}
PORT_SCAN_THRESHOLD = 5
PORT_SCAN_WINDOW = 120  # seconds

@app.before_request
def nmap_and_portscan_detection():
    ip = request.remote_addr
    ua = (request.user_agent.string or '').lower()
    # 1. Detect Nmap and common scanner user agents
    for scanner in NMAP_USER_AGENTS:
        if scanner in ua:
            log_siem_event(
                event_type='nmap_scan_detected',
                message=f'Nmap or scanner detected: {ua}',
                severity='critical',
                ip_address=ip,
                source='security'
            )
            add_blocked_ip(ip, reason='Nmap/scan detected', blocked_by='SIEM')
            break
    # 2. Detect port scan attempts (for uncommon ports)
    port = request.environ.get('REMOTE_PORT')
    try:
        port = int(port)
    except (TypeError, ValueError):
        port = None
    if port and port in UNCOMMON_PORTS:
        now = datetime.utcnow()
        PORT_SCAN_ATTEMPTS[ip] = [t for t in PORT_SCAN_ATTEMPTS[ip] if (now - t).total_seconds() < PORT_SCAN_WINDOW]
        PORT_SCAN_ATTEMPTS[ip].append(now)
        if len(PORT_SCAN_ATTEMPTS[ip]) >= PORT_SCAN_THRESHOLD:
            log_siem_event(
                event_type='port_scan_detected',
                message=f'Port scan detected from {ip} (ports: {UNCOMMON_PORTS})',
                severity='critical',
                ip_address=ip,
                source='security'
            )
            add_blocked_ip(ip, reason='Port scan detected', blocked_by='SIEM')
            PORT_SCAN_ATTEMPTS[ip] = []

# Directory brute force and admin protection
REPEATED_404S = defaultdict(list)  # {ip: [timestamps]}
SENSITIVE_PATHS = ['/admin', '/admin/', '/wp-admin', '/phpmyadmin', '/.env', '/config', '/setup', '/install', '/login', '/register']
ADMIN_404_THRESHOLD = 5
ADMIN_404_WINDOW = 180  # seconds

@app.errorhandler(404)
def not_found_error(error):
    ip = request.remote_addr
    path = request.path
    now = datetime.utcnow()
    # Log all 404s
    log_siem_event(
        event_type='not_found',
        message=f'404 on {path}',
        severity='info',
        ip_address=ip,
        source='security'
    )
    # Track repeated 404s for brute force
    REPEATED_404S[ip] = [t for t in REPEATED_404S[ip] if (now - t).total_seconds() < ADMIN_404_WINDOW]
    REPEATED_404S[ip].append(now)
    # If path is sensitive or repeated 404s, escalate
    if path in SENSITIVE_PATHS or any(s in path for s in SENSITIVE_PATHS):
        log_siem_event(
            event_type='sensitive_404',
            message=f'404 on sensitive path {path}',
            severity='warning',
            ip_address=ip,
            source='security'
        )
        if len(REPEATED_404S[ip]) >= ADMIN_404_THRESHOLD:
            log_siem_event(
                event_type='dir_bruteforce_detected',
                message=f'Repeated 404s from {ip} (possible dir brute force)',
                severity='critical',
                ip_address=ip,
                source='security'
            )
            add_blocked_ip(ip, reason='Directory brute force detected', blocked_by='SIEM')
            REPEATED_404S[ip] = []
    return make_response(render_template('404.html'), 404)

# Extra admin protection: log and block unauthorized admin access attempts
@app.before_request
def admin_protection():
    ip = request.remote_addr
    path = request.path
    if path.startswith('/admin'):
        if not current_user.is_authenticated or not getattr(current_user, 'is_admin', False):
            log_siem_event(
                event_type='unauthorized_admin_access',
                message=f'Unauthorized admin access attempt to {path}',
                severity='critical',
                ip_address=ip,
                source='admin'
            )
            add_blocked_ip(ip, reason='Unauthorized admin access', blocked_by='SIEM')

# Achievements and Streaks Routes
@app.route('/achievements')
@login_required
def achievements_dashboard():
    """Display user's achievements with progress tracking"""
    achievements_with_progress = get_user_achievements_with_progress(current_user)
    user_stats = get_user_stats(current_user)
    
    # Group achievements by type
    achievement_groups = {}
    for item in achievements_with_progress:
        ach_type = item['achievement'].type
        if ach_type not in achievement_groups:
            achievement_groups[ach_type] = []
        achievement_groups[ach_type].append(item)
    
    return render_template('achievements.html', 
                         achievements_with_progress=achievements_with_progress,
                         achievement_groups=achievement_groups,
                         user_stats=user_stats)

@app.route('/streaks')
@login_required
def streaks_dashboard():
    """Display user's streak information and progress"""
    user_stats = get_user_stats(current_user)
    streak = current_user.streak
    
    # Calculate streak milestones
    streak_milestones = [3, 7, 14, 30, 60, 100]
    current_streak = user_stats['current_streak']
    longest_streak = user_stats['longest_streak']
    
    # Get next milestone
    next_milestone = None
    for milestone in streak_milestones:
        if current_streak < milestone:
            next_milestone = milestone
            break
    
    return render_template('streaks.html',
                         user_stats=user_stats,
                         streak=streak,
                         streak_milestones=streak_milestones,
                         next_milestone=next_milestone)

@app.route('/leaderboard')
def leaderboard():
    """Display leaderboards for streaks, achievements, and reputation"""
    leaderboard_data = get_leaderboard_data()
    
    return render_template('leaderboard.html',
                         leaderboard_data=leaderboard_data)

@app.route('/api/achievement_progress')
@login_required
def api_achievement_progress():
    """API endpoint to get achievement progress for AJAX updates"""
    achievements_with_progress = get_user_achievements_with_progress(current_user)
    
    # Return only essential data for AJAX
    progress_data = []
    for item in achievements_with_progress:
        progress_data.append({
            'id': item['achievement'].id,
            'name': item['achievement'].name,
            'progress': item['progress'],
            'unlocked': item['unlocked']
        })
    
    return jsonify(progress_data)

# Advanced Lab System Routes
@app.route('/labs/advanced')
@login_required
def advanced_labs():
    """Advanced lab dashboard with categories and learning paths"""
    lab_manager = LabManager()
    
    # Get learning paths
    learning_paths = LearningPath.query.filter_by(is_active=True).all()
    
    # Get labs by category
    labs_by_category = {}
    for category in LAB_CATEGORIES.keys():
        labs = Lab.query.filter_by(category=category, is_active=True).all()
        labs_by_category[category] = labs
    
    # Get user's progress
    user_progress = {}
    for lab in Lab.query.filter_by(is_active=True).all():
        progress = lab_manager.get_lab_progress(current_user.id, lab.id)
        user_progress[lab.id] = progress
    
    return render_template('advanced_labs.html',
                         learning_paths=learning_paths,
                         labs_by_category=labs_by_category,
                         user_progress=user_progress,
                         categories=LAB_CATEGORIES,
                         difficulties=LAB_DIFFICULTIES)

@app.route('/labs/learning-path/<int:path_id>')
@login_required
def learning_path_detail(path_id):
    """Detailed view of a learning path"""
    lab_manager = LabManager()
    
    path = LearningPath.query.get_or_404(path_id)
    path_progress = lab_manager.get_learning_path_progress(current_user.id, path_id)
    
    return render_template('learning_path_detail.html',
                         path=path,
                         path_progress=path_progress)

@app.route('/ctf')
@login_required
def ctf_dashboard():
    """CTF challenges dashboard"""
    lab_manager = LabManager()
    
    # Get challenges by category
    challenges_by_category = {}
    for category in CTF_CATEGORIES:
        challenges = CTFChallenge.query.filter_by(
            category=category, 
            is_active=True
        ).order_by(CTFChallenge.difficulty).all()
        challenges_by_category[category] = challenges
    
    # Get leaderboard
    leaderboard = lab_manager.get_ctf_leaderboard()
    
    # Get user's solved challenges
    user_solved = CTFSubmission.query.filter_by(
        user_id=current_user.id, 
        is_correct=True
    ).all()
    solved_ids = {s.challenge_id for s in user_solved}
    
    return render_template('ctf_dashboard.html',
                         challenges_by_category=challenges_by_category,
                         leaderboard=leaderboard,
                         solved_ids=solved_ids,
                         categories=CTF_CATEGORIES)

@app.route('/ctf/challenge/<int:challenge_id>')
@login_required
def ctf_challenge_detail(challenge_id):
    """Individual CTF challenge view"""
    challenge = CTFChallenge.query.get_or_404(challenge_id)
    
    # Check if user has solved it
    solved = CTFSubmission.query.filter_by(
        user_id=current_user.id,
        challenge_id=challenge_id,
        is_correct=True
    ).first()
    
    # Get user's submission history
    submissions = CTFSubmission.query.filter_by(
        user_id=current_user.id,
        challenge_id=challenge_id
    ).order_by(CTFSubmission.submitted_at.desc()).all()
    
    return render_template('ctf_challenge_detail.html',
                         challenge=challenge,
                         solved=solved,
                         submissions=submissions)

@app.route('/ctf/submit', methods=['POST'])
@login_required
def submit_ctf_flag():
    """Submit a CTF flag"""
    challenge_id = request.form.get('challenge_id', type=int)
    flag = request.form.get('flag', '').strip()
    
    if not challenge_id or not flag:
        return jsonify({'success': False, 'message': 'Missing challenge ID or flag'})
    
    lab_manager = LabManager()
    result = lab_manager.submit_ctf_flag(current_user.id, challenge_id, flag)
    
    return jsonify(result)

@app.route('/sandbox')
@login_required
def sandbox_dashboard():
    """Sandbox environments dashboard"""
    sandboxes = SandboxEnvironment.query.filter_by(is_active=True).all()
    
    # Get user's active sessions
    active_sessions = UserSandboxSession.query.filter_by(
        user_id=current_user.id,
        status='running'
    ).all()
    
    return render_template('sandbox_dashboard.html',
                         sandboxes=sandboxes,
                         active_sessions=active_sessions)

@app.route('/sandbox/start/<int:sandbox_id>', methods=['POST'])
@login_required
def start_sandbox(sandbox_id):
    """Start a sandbox session"""
    lab_manager = LabManager()
    result = lab_manager.start_sandbox_session(current_user.id, sandbox_id)
    
    return jsonify(result)

@app.route('/sandbox/stop/<session_id>', methods=['POST'])
@login_required
def stop_sandbox(session_id):
    """Stop a sandbox session"""
    lab_manager = LabManager()
    result = lab_manager.stop_sandbox_session(session_id)
    
    return jsonify(result)

@app.route('/labs/<int:lab_id>/hints')
@login_required
def get_lab_hints(lab_id):
    """Get hints for a lab"""
    lab_manager = LabManager()
    hints = lab_manager.get_lab_hints(lab_id, current_user.id)
    
    return jsonify([{
        'id': hint.id,
        'text': hint.hint_text if hint.is_used else '***',
        'order': hint.hint_order,
        'cost': hint.cost,
        'is_free': hint.is_free,
        'is_used': getattr(hint, 'is_used', False)
    } for hint in hints])

@app.route('/labs/<int:lab_id>/use-hint/<int:hint_id>', methods=['POST'])
@login_required
def use_lab_hint(lab_id, hint_id):
    """Use a lab hint"""
    lab_manager = LabManager()
    result = lab_manager.use_hint(current_user.id, hint_id)
    
    return jsonify(result)

@app.route('/labs/<int:lab_id>/rate', methods=['POST'])
@login_required
def rate_lab(lab_id):
    """Rate a lab"""
    rating = request.form.get('rating', type=int)
    difficulty_rating = request.form.get('difficulty_rating', type=int)
    feedback = request.form.get('feedback', '')
    
    if not rating or rating < 1 or rating > 5:
        return jsonify({'success': False, 'message': 'Invalid rating'})
    
    lab_manager = LabManager()
    result = lab_manager.rate_lab(current_user.id, lab_id, rating, difficulty_rating, feedback)
    
    return jsonify(result)

@app.route('/labs/<int:lab_id>/progress')
@login_required
def get_lab_progress(lab_id):
    """Get detailed lab progress"""
    lab_manager = LabManager()
    progress = lab_manager.get_lab_progress(current_user.id, lab_id)
    
    return jsonify({
        'progress_percentage': progress.progress_percentage,
        'current_step': progress.current_step,
        'total_steps': progress.total_steps,
        'time_spent': progress.time_spent,
        'hints_used': progress.hints_used,
        'attempts': progress.attempts,
        'completed': progress.completed_at is not None
    })

@app.route('/labs/<int:lab_id>/update-progress', methods=['POST'])
@login_required
def update_lab_progress(lab_id):
    """Update lab progress"""
    step_completed = request.form.get('step_completed', 'false').lower() == 'true'
    hint_used = request.form.get('hint_used', 'false').lower() == 'true'
    
    lab_manager = LabManager()
    progress = lab_manager.update_lab_progress(
        current_user.id, 
        lab_id, 
        step_completed, 
        hint_used
    )
    
    return jsonify({
        'success': True,
        'progress_percentage': progress.progress_percentage,
        'completed': progress.completed_at is not None
    })

# Admin routes for advanced lab management
@app.route('/admin/learning-paths', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_learning_paths():
    """Admin management of learning paths"""
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        difficulty = request.form.get('difficulty')
        category = request.form.get('category')
        
        lab_manager = LabManager()
        path = lab_manager.create_learning_path(
            name=name,
            description=description,
            difficulty=difficulty,
            category=category
        )
        
        flash('Learning path created successfully!', 'success')
        return redirect(url_for('admin_learning_paths'))
    
    paths = LearningPath.query.all()
    return render_template('admin_learning_paths.html', paths=paths)

@app.route('/admin/ctf-challenges', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_ctf_challenges():
    """Admin management of CTF challenges"""
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        category = request.form.get('category')
        difficulty = request.form.get('difficulty')
        flag = request.form.get('flag')
        points = request.form.get('points', type=int)
        
        lab_manager = LabManager()
        challenge = lab_manager.create_ctf_challenge(
            title=title,
            description=description,
            category=category,
            difficulty=difficulty,
            flag=flag,
            points=points
        )
        
        flash('CTF challenge created successfully!', 'success')
        return redirect(url_for('admin_ctf_challenges'))
    
    challenges = CTFChallenge.query.all()
    return render_template('admin_ctf_challenges.html', 
                         challenges=challenges,
                         categories=CTF_CATEGORIES)

@app.route('/admin/sandbox-environments', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_sandbox_environments():
    """Admin management of sandbox environments"""
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        environment_type = request.form.get('environment_type')
        image_name = request.form.get('image_name')
        
        lab_manager = LabManager()
        sandbox = lab_manager.create_sandbox_environment(
            name=name,
            description=description,
            environment_type=environment_type,
            image_name=image_name
        )
        
        flash('Sandbox environment created successfully!', 'success')
        return redirect(url_for('admin_sandbox_environments'))
    
    sandboxes = SandboxEnvironment.query.all()
    return render_template('admin_sandbox_environments.html', sandboxes=sandboxes)
