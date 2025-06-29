import os
import uuid
from datetime import datetime, timedelta
from flask import render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory, abort
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import or_, desc
from app import app, db
from models import User, Post, Comment, Lab, LabCompletion, Notification, Follow, AdminSettings, UserAction, UserBan, PostLike, CommentLike, Purchase, Order, OrderItem, Transaction, UserWallet, WalletTransaction, LabQuizQuestion, LabQuizAttempt, ActivationKey, PremiumSubscription, PaymentPlan, is_platform_free_mode, set_platform_free_mode, LabTerminalCommand, LabTerminalSession, Contact
from ai_assistant import get_ai_response
from utils import allowed_file, create_notification, send_email
from payment_service import PaymentService
import json
import requests
import hashlib

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
        
        if user and check_password_hash(user.password_hash, password):
            # Only block permanently banned users from logging in
            if user.is_permanently_banned():
                flash('Your account has been permanently banned. Please contact support if you believe this is an error.', 'error')
                return render_template('login.html')
            
            # Admin device lock: generate fingerprint
            if user.is_admin:
                user_agent = request.headers.get('User-Agent', '')
                ip = request.remote_addr or ''
                fingerprint = hashlib.sha256((user_agent + ip).encode()).hexdigest()
                user.admin_device_fingerprint = fingerprint
                db.session.commit()
                session['admin_device_fingerprint'] = fingerprint
            
            # Allow temporarily banned and muted users to log in
            # They will be redirected to ban notification by the before_request middleware
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
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
        
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# Profile routes
@app.route('/profile')
@login_required
def profile():
    user_posts = Post.query.filter_by(user_id=current_user.id).order_by(desc(Post.created_at)).all()
    return render_template('profile.html', user_posts=user_posts)

@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        current_user.bio = request.form.get('bio', '')
        current_user.skills = request.form.get('skills', '')
        current_user.github_username = request.form.get('github_username', '')
        
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))
    
    return render_template('profile.html', edit_mode=True)

@app.route('/user/<username>')
def user_profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    user_posts = Post.query.filter_by(user_id=user.id).order_by(desc(Post.created_at)).all()
    return render_template('user_profile.html', user=user, user_posts=user_posts)

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
    # Check if user is banned
    if current_user.is_permanently_banned() or current_user.is_temporarily_banned():
        flash('You cannot create posts while your account is suspended.', 'error')
        return redirect(url_for('ban_notification'))
    
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        category = request.form['category']
        tags = request.form.get('tags', '')
        price = float(request.form.get('price', 0.0))
        
        # Handle file upload
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
            price=price,
            is_premium=price > 0,
            file_path=file_path,
            file_name=file_name,
            user_id=current_user.id
        )
        
        db.session.add(post)
        db.session.commit()
        
        flash('Post created successfully!', 'success')
        return redirect(url_for('post_detail', post_id=post.id))
    
    return render_template('create_post.html')

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
    return redirect(url_for('post_detail', post_id=post_id))

# File download route
@app.route('/download/<filename>')
@login_required
def download_file(filename):
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
        
        flash(f'Congratulations! You completed the lab and earned {lab.points} reputation points!', 'success')
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
        flash(f'Success! You completed the hacking lab and earned {lab.points} reputation points!', 'success')
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
    return render_template('store.html', premium_posts=premium_posts, is_free_mode=is_platform_free_mode())

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
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500

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
    
    # Check if user owns this post
    if post.user_id != current_user.id:
        flash('You can only delete your own posts.', 'error')
        return redirect(url_for('post_detail', post_id=post_id))
    
    # Check if premium post has been purchased
    if post.is_premium:
        existing_purchases = Purchase.query.filter_by(post_id=post.id, status='completed').count()
        if existing_purchases > 0:
            flash('Cannot delete premium content that has been purchased. Contact admin if needed.', 'error')
            return redirect(url_for('post_detail', post_id=post_id))
    
    # Delete associated file if it exists
    if post.file_path and os.path.exists(post.file_path):
        os.remove(post.file_path)
    
    # Delete the post
    db.session.delete(post)
    db.session.commit()
    
    flash('Post deleted successfully!', 'success')
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
    
    return redirect(url_for('admin_contact_detail', contact_id=contact_id))

@app.before_request
def enforce_admin_device_lock():
    if current_user.is_authenticated and current_user.is_admin:
        if request.path.startswith('/admin'):
            user_agent = request.headers.get('User-Agent', '')
            ip = request.remote_addr or ''
            fingerprint = hashlib.sha256((user_agent + ip).encode()).hexdigest()
            # Strict: session and db fingerprint must match
            if (
                not current_user.admin_device_fingerprint or
                current_user.admin_device_fingerprint != fingerprint or
                session.get('admin_device_fingerprint') != fingerprint
            ):
                logout_user()
                session.pop('admin_device_fingerprint', None)
                flash('Admin access denied: device mismatch or session invalidated. Please log in from your authorized device.', 'error')
                return redirect(url_for('login'))
