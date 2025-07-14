import datetime
from models import db, UserStreak, Achievement, UserAchievement, User, Post, LabCompletion, PostLike
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

def check_and_unlock_achievements(user):
    unlocked = []
    # Count user actions
    post_count = Post.query.filter_by(user_id=user.id).count()
    reaction_count = PostLike.query.filter_by(user_id=user.id).count()  # You can add CommentLike, MessageReaction, etc.
    lab_count = LabCompletion.query.filter_by(user_id=user.id).count()
    streak = UserStreak.query.filter_by(user_id=user.id).first()
    streak_count = streak.current_streak if streak else 0
    # Get all achievements
    achievements = Achievement.query.all()
    for ach in achievements:
        if UserAchievement.query.filter_by(user_id=user.id, achievement_id=ach.id).first():
            continue  # Already unlocked
        # Parse criteria
        if ach.type == 'post' and eval(ach.criteria.replace('posts', str(post_count))):
            unlock_achievement(user, ach)
            unlocked.append(ach)
        elif ach.type == 'reaction' and eval(ach.criteria.replace('reactions', str(reaction_count))):
            unlock_achievement(user, ach)
            unlocked.append(ach)
        elif ach.type == 'lab' and eval(ach.criteria.replace('labs_completed', str(lab_count))):
            unlock_achievement(user, ach)
            unlocked.append(ach)
        elif ach.type == 'streak' and eval(ach.criteria.replace('streak', str(streak_count))):
            unlock_achievement(user, ach)
            unlocked.append(ach)
    return unlocked

def unlock_achievement(user, achievement):
    ua = UserAchievement(user_id=user.id, achievement_id=achievement.id)
    db.session.add(ua)
    db.session.commit()
    # Notify user
    create_notification(user.id, f"Achievement Unlocked: {achievement.name}", f"{achievement.description}") 