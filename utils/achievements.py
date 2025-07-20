import datetime
from models import db, UserStreak, Achievement, UserAchievement, User, Post, LabCompletion, PostLike, Comment, CommentLike
from utils import create_notification

def update_user_streak(user_id):
    today = datetime.date.today()
    streak = UserStreak.query.filter_by(user_id=user_id).first()
    if not streak:
        streak = UserStreak(user_id=user_id, current_streak=1, longest_streak=1, last_active_date=today)
        db.session.add(streak)
        db.session.commit()
        return streak
    if streak.last_active_date == today:
        return streak  # Already updated today
    elif streak.last_active_date == today - datetime.timedelta(days=1):
        streak.current_streak += 1
        if streak.current_streak > streak.longest_streak:
            streak.longest_streak = streak.current_streak
    else:
        streak.current_streak = 1
    streak.last_active_date = today
    db.session.commit()
    return streak

def get_user_stats(user):
    """Get comprehensive user statistics for achievement checking"""
    # Optimize received likes queries
    post_ids = db.session.query(Post.id).filter_by(user_id=user.id)
    comment_ids = db.session.query(Comment.id).filter_by(user_id=user.id)
    stats = {
        'posts': Post.query.filter_by(user_id=user.id).count(),
        'comments': Comment.query.filter_by(user_id=user.id).count(),
        'post_likes_given': PostLike.query.filter_by(user_id=user.id).count(),
        'post_likes_received': PostLike.query.filter(PostLike.post_id.in_(post_ids)).count(),
        'comment_likes_given': CommentLike.query.filter_by(user_id=user.id).count(),
        'comment_likes_received': CommentLike.query.filter(CommentLike.comment_id.in_(comment_ids)).count(),
        'labs_completed': LabCompletion.query.filter_by(user_id=user.id).count(),
        'reputation': user.reputation,
        'days_since_joined': (datetime.date.today() - user.created_at.date()).days,
        'followers': user.followers.count(),
        'following': user.following.count(),
    }
    
    # Get streak info
    streak = UserStreak.query.filter_by(user_id=user.id).first()
    if streak:
        stats['current_streak'] = streak.current_streak
        stats['longest_streak'] = streak.longest_streak
        stats['total_reactions'] = stats['post_likes_given'] + stats['comment_likes_given']
    else:
        stats['current_streak'] = 0
        stats['longest_streak'] = 0
        stats['total_reactions'] = stats['post_likes_given'] + stats['comment_likes_given']
    
    return stats

def check_and_unlock_achievements(user):
    unlocked = []
    stats = get_user_stats(user)
    
    # Get all achievements
    achievements = Achievement.query.all()
    for ach in achievements:
        if UserAchievement.query.filter_by(user_id=user.id, achievement_id=ach.id).first():
            continue  # Already unlocked
        
        # Check if achievement criteria is met
        if is_achievement_unlocked(ach, stats):
            unlock_achievement(user, ach)
            unlocked.append(ach)
    
    return unlocked

def is_achievement_unlocked(achievement, stats):
    """Check if achievement criteria is met using the stats"""
    try:
        # Replace variables in criteria with actual values
        criteria = achievement.criteria
        for key, value in stats.items():
            criteria = criteria.replace(key, str(value))
        
        # Evaluate the criteria
        return eval(criteria)
    except:
        return False

def unlock_achievement(user, achievement):
    ua = UserAchievement(user_id=user.id, achievement_id=achievement.id)
    db.session.add(ua)
    db.session.commit()
    # Notify user
    create_notification(user.id, f"Achievement Unlocked: {achievement.name}", f"{achievement.description}")

def get_achievement_progress(user, achievement):
    """Get progress towards an achievement (0-100)"""
    stats = get_user_stats(user)
    
    try:
        # Parse the criteria to understand what we're tracking
        criteria = achievement.criteria
        
        if 'posts' in criteria:
            current = stats['posts']
            # Extract target from criteria like "posts>=10"
            target = int(criteria.split('>=')[1].split()[0])
        elif 'labs_completed' in criteria:
            current = stats['labs_completed']
            target = int(criteria.split('>=')[1].split()[0])
        elif 'streak' in criteria:
            current = stats['current_streak']
            target = int(criteria.split('>=')[1].split()[0])
        elif 'reactions' in criteria:
            current = stats['total_reactions']
            target = int(criteria.split('>=')[1].split()[0])
        elif 'reputation' in criteria:
            current = stats['reputation']
            target = int(criteria.split('>=')[1].split()[0])
        elif 'followers' in criteria:
            current = stats['followers']
            target = int(criteria.split('>=')[1].split()[0])
        else:
            return 0
        
        progress = min(100, (current / target) * 100) if target > 0 else 0
        return round(progress, 1)
    except:
        return 0

def get_user_achievements_with_progress(user):
    """Get all achievements with progress for a user"""
    all_achievements = Achievement.query.all()
    user_achievements = {ua.achievement_id for ua in user.user_achievements}
    
    achievements_with_progress = []
    for achievement in all_achievements:
        progress = get_achievement_progress(user, achievement)
        is_unlocked = achievement.id in user_achievements
        
        achievements_with_progress.append({
            'achievement': achievement,
            'progress': progress,
            'unlocked': is_unlocked,
            'unlocked_at': None
        })
    
    # Add unlock dates for unlocked achievements
    for ua in user.user_achievements:
        for item in achievements_with_progress:
            if item['achievement'].id == ua.achievement_id:
                item['unlocked_at'] = ua.unlocked_at
                break
    
    return achievements_with_progress

def get_leaderboard_data():
    """Get leaderboard data for streaks and achievements"""
    # Top streaks
    top_streaks = db.session.query(User, UserStreak).join(UserStreak).order_by(
        UserStreak.longest_streak.desc(), UserStreak.current_streak.desc()
    ).limit(10).all()
    
    # Top achievement collectors
    top_achievements = db.session.query(
        User, db.func.count(UserAchievement.id).label('achievement_count')
    ).join(UserAchievement).group_by(User.id).order_by(
        db.func.count(UserAchievement.id).desc()
    ).limit(10).all()
    
    # Top reputation
    top_reputation = User.query.order_by(User.reputation.desc()).limit(10).all()
    
    return {
        'top_streaks': top_streaks,
        'top_achievements': top_achievements,
        'top_reputation': top_reputation
    }

def create_challenge_achievements():
    """Create time-based challenge achievements"""
    challenges = [
        # Weekly challenges
        {"name": "Week Warrior", "description": "Complete 5 labs in a week", "icon": "fas fa-calendar-week", "type": "challenge", "criteria": "weekly_labs>=5", "duration": "weekly"},
        {"name": "Social Butterfly", "description": "Make 10 posts in a week", "icon": "fas fa-comments", "type": "challenge", "criteria": "weekly_posts>=10", "duration": "weekly"},
        
        # Monthly challenges
        {"name": "Monthly Master", "description": "Maintain a 7-day streak in a month", "icon": "fas fa-calendar-alt", "type": "challenge", "criteria": "monthly_streak>=7", "duration": "monthly"},
        {"name": "Community Builder", "description": "Gain 50 reputation points in a month", "icon": "fas fa-users", "type": "challenge", "criteria": "monthly_reputation>=50", "duration": "monthly"},
        
        # Special challenges
        {"name": "First Blood", "description": "Complete your first lab", "icon": "fas fa-tint", "type": "special", "criteria": "labs_completed>=1", "duration": "permanent"},
        {"name": "Veteran", "description": "Be active for 100 days", "icon": "fas fa-medal", "type": "special", "criteria": "days_since_joined>=100", "duration": "permanent"},
    ]
    
    for challenge in challenges:
        if not Achievement.query.filter_by(name=challenge["name"]).first():
            db.session.add(Achievement(
                name=challenge["name"],
                description=challenge["description"],
                icon=challenge["icon"],
                type=challenge["type"],
                criteria=challenge["criteria"],
                created_at=datetime.utcnow()
            ))
    
    db.session.commit() 