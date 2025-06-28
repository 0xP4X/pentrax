import os
from flask import render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import or_, desc
from app import app, db
from models import User, Post, Comment, Lab, LabCompletion, Notification, Follow, AdminSettings, UserAction, UserBan
from ai_assistant import get_ai_response
from utils import allowed_file, create_notification

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
    labs = Lab.query.all()
    user_completions = []
    if current_user.is_authenticated:
        user_completions = [comp.lab_id for comp in LabCompletion.query.filter_by(user_id=current_user.id).all()]
    
    return render_template('cyber_labs.html', labs=labs, user_completions=user_completions)

@app.route('/lab/<int:lab_id>')
@login_required
def lab_detail(lab_id):
    lab = Lab.query.get_or_404(lab_id)
    return render_template('lab_detail.html', lab=lab)

# Store routes
@app.route('/store')
def store():
    premium_posts = Post.query.filter_by(is_premium=True).order_by(desc(Post.created_at)).all()
    return render_template('store.html', premium_posts=premium_posts)

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
                         recent_posts=recent_posts, recent_actions=recent_actions)

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
        # Update API keys and settings
        settings_to_update = [
            ('openai_api_key', 'OpenAI API Key for AI Assistant'),
            ('paystack_public_key', 'Paystack Public Key for Payments'),
            ('paystack_secret_key', 'Paystack Secret Key for Payments'),
            ('commission_rate', 'Platform Commission Rate (%)'),
            ('platform_name', 'Platform Name'),
            ('max_file_size', 'Maximum File Upload Size (MB)')
        ]
        
        for key, description in settings_to_update:
            value = request.form.get(key)
            if value:
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
    return render_template('admin_settings.html', settings=settings)

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

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500
