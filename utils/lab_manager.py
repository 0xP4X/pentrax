import json
import subprocess
import uuid
import time
from datetime import datetime, timedelta
from models import db, Lab, LearningPath, CTFChallenge, SandboxEnvironment, UserSandboxSession, LabProgress, LabHint, UserHintUsage, LabRating, User, CTFSubmission
from utils import create_notification, log_siem_event

# Optional docker import
try:
    import docker
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False
    docker = None

class LabManager:
    """Advanced lab management system for cybersecurity training"""
    
    def __init__(self):
        self.docker_client = None
        if DOCKER_AVAILABLE:
            try:
                self.docker_client = docker.from_env()
            except:
                pass  # Docker not available
    
    def create_learning_path(self, name, description, difficulty, category, **kwargs):
        """Create a structured learning path"""
        path = LearningPath(
            name=name,
            description=description,
            difficulty=difficulty,
            category=category,
            **kwargs
        )
        db.session.add(path)
        db.session.commit()
        return path
    
    def add_lab_to_path(self, lab_id, path_id, order):
        """Add a lab to a learning path"""
        lab = Lab.query.get(lab_id)
        if lab:
            lab.learning_path_id = path_id
            lab.path_order = order
            db.session.commit()
            return True
        return False
    
    def create_ctf_challenge(self, title, description, category, difficulty, flag, **kwargs):
        """Create a CTF challenge"""
        challenge = CTFChallenge(
            title=title,
            description=description,
            category=category,
            difficulty=difficulty,
            flag=flag,
            **kwargs
        )
        db.session.add(challenge)
        db.session.commit()
        return challenge
    
    def submit_ctf_flag(self, user_id, challenge_id, submitted_flag):
        """Submit a CTF flag"""
        challenge = CTFChallenge.query.get(challenge_id)
        if not challenge:
            return {'success': False, 'message': 'Challenge not found'}
        
        # Check if already solved
        existing_submission = CTFSubmission.query.filter_by(
            user_id=user_id, 
            challenge_id=challenge_id, 
            is_correct=True
        ).first()
        
        if existing_submission:
            return {'success': False, 'message': 'Already solved this challenge'}
        
        is_correct = submitted_flag.strip() == challenge.flag.strip()
        
        submission = CTFSubmission(
            user_id=user_id,
            challenge_id=challenge_id,
            submitted_flag=submitted_flag,
            is_correct=is_correct,
            points_earned=challenge.points if is_correct else 0
        )
        db.session.add(submission)
        
        if is_correct:
            # Update challenge stats
            challenge.solved_by += 1
            
            # Check for first blood
            if not challenge.first_blood:
                challenge.first_blood = user_id
                challenge.first_blood_time = datetime.utcnow()
            
            # Award points to user
            user = User.query.get(user_id)
            if user:
                user.reputation += challenge.points
            
            # Create notification
            create_notification(
                user_id, 
                f"CTF Challenge Solved: {challenge.title}", 
                f"You earned {challenge.points} points!"
            )
            
            # Log SIEM event
            log_siem_event(
                event_type='ctf_solve',
                message=f'User solved CTF challenge: {challenge.title}',
                severity='info',
                user_id=user_id
            )
        
        db.session.commit()
        
        return {
            'success': True,
            'correct': is_correct,
            'message': 'Flag correct!' if is_correct else 'Incorrect flag',
            'points_earned': challenge.points if is_correct else 0
        }
    
    def create_sandbox_environment(self, name, description, environment_type, **kwargs):
        """Create a sandbox environment"""
        sandbox = SandboxEnvironment(
            name=name,
            description=description,
            environment_type=environment_type,
            **kwargs
        )
        db.session.add(sandbox)
        db.session.commit()
        return sandbox
    
    def start_sandbox_session(self, user_id, sandbox_id):
        """Start a sandbox session for a user"""
        sandbox = SandboxEnvironment.query.get(sandbox_id)
        if not sandbox:
            return {'success': False, 'message': 'Sandbox not found'}
        
        # Check if user already has an active session
        active_session = UserSandboxSession.query.filter_by(
            user_id=user_id,
            status='running'
        ).first()
        
        if active_session:
            return {'success': False, 'message': 'You already have an active sandbox session'}
        
        session_id = str(uuid.uuid4())
        
        if sandbox.environment_type == 'docker' and DOCKER_AVAILABLE and self.docker_client:
            try:
                # Start Docker container
                container = self.docker_client.containers.run(
                    sandbox.image_name,
                    detach=True,
                    name=f"pentrax_sandbox_{session_id}",
                    ports={'22/tcp': None, '80/tcp': None, '443/tcp': None}
                )
                
                # Get container info
                container_info = container.attrs
                access_url = f"http://localhost:{container_info['NetworkSettings']['Ports']['80/tcp'][0]['HostPort']}"
                
                session = UserSandboxSession(
                    user_id=user_id,
                    sandbox_id=sandbox_id,
                    session_id=session_id,
                    container_id=container.id,
                    status='running',
                    access_url=access_url
                )
                
            except Exception as e:
                return {'success': False, 'message': f'Failed to start sandbox: {str(e)}'}
        else:
            # For non-Docker environments, create a placeholder session
            session = UserSandboxSession(
                user_id=user_id,
                sandbox_id=sandbox_id,
                session_id=session_id,
                status='running',
                access_url=sandbox.sandbox_url
            )
        
        db.session.add(session)
        db.session.commit()
        
        return {
            'success': True,
            'session_id': session_id,
            'access_url': session.access_url
        }
    
    def stop_sandbox_session(self, session_id):
        """Stop a sandbox session"""
        session = UserSandboxSession.query.filter_by(session_id=session_id).first()
        if not session:
            return {'success': False, 'message': 'Session not found'}
        
        if session.container_id and DOCKER_AVAILABLE and self.docker_client:
            try:
                container = self.docker_client.containers.get(session.container_id)
                container.stop()
                container.remove()
            except:
                pass  # Container might already be stopped
        
        session.status = 'stopped'
        session.stopped_at = datetime.utcnow()
        db.session.commit()
        
        return {'success': True, 'message': 'Session stopped'}
    
    def get_lab_progress(self, user_id, lab_id):
        """Get detailed progress for a lab"""
        progress = LabProgress.query.filter_by(user_id=user_id, lab_id=lab_id).first()
        if not progress:
            # Create new progress record
            lab = Lab.query.get(lab_id)
            if lab:
                progress = LabProgress(
                    user_id=user_id,
                    lab_id=lab_id,
                    total_steps=len(lab.terminal_commands) if lab.terminal_commands else 1
                )
                db.session.add(progress)
                db.session.commit()
        
        return progress
    
    def update_lab_progress(self, user_id, lab_id, step_completed=False, hint_used=False):
        """Update lab progress"""
        progress = self.get_lab_progress(user_id, lab_id)
        lab = Lab.query.get(lab_id)
        
        if step_completed:
            progress.current_step += 1
            progress.completed_steps += 1
        
        if hint_used:
            progress.hints_used += 1
        
        progress.attempts += 1
        progress.last_activity = datetime.utcnow()
        
        # Calculate progress percentage
        if lab and lab.terminal_commands:
            progress.progress_percentage = (progress.completed_steps / len(lab.terminal_commands)) * 100
        else:
            progress.progress_percentage = 100 if step_completed else 0
        
        # Check if lab is completed
        if progress.progress_percentage >= 100:
            progress.completed_at = datetime.utcnow()
            
            # Award points
            user = User.query.get(user_id)
            if user and lab:
                user.reputation += lab.points
            
            # Create completion notification
            create_notification(
                user_id,
                f"Lab Completed: {lab.title}",
                f"You earned {lab.points} points!"
            )
        
        db.session.commit()
        return progress
    
    def get_lab_hints(self, lab_id, user_id=None):
        """Get hints for a lab"""
        hints = LabHint.query.filter_by(lab_id=lab_id).order_by(LabHint.hint_order).all()
        
        if user_id:
            # Check which hints user has used
            used_hints = UserHintUsage.query.filter_by(user_id=user_id).all()
            used_hint_ids = {uh.hint_id for uh in used_hints}
            
            for hint in hints:
                hint.is_used = hint.id in used_hint_ids
        
        return hints
    
    def use_hint(self, user_id, hint_id):
        """Use a hint"""
        hint = LabHint.query.get(hint_id)
        if not hint:
            return {'success': False, 'message': 'Hint not found'}
        
        # Check if already used
        existing_usage = UserHintUsage.query.filter_by(
            user_id=user_id, 
            hint_id=hint_id
        ).first()
        
        if existing_usage:
            return {'success': False, 'message': 'Hint already used'}
        
        # Check if user has enough points
        user = User.query.get(user_id)
        if not user or user.reputation < hint.cost:
            return {'success': False, 'message': 'Not enough points to use this hint'}
        
        # Use the hint
        usage = UserHintUsage(
            user_id=user_id,
            hint_id=hint_id,
            points_spent=hint.cost
        )
        db.session.add(usage)
        
        # Deduct points if hint costs points
        if hint.cost > 0:
            user.reputation -= hint.cost
        
        db.session.commit()
        
        return {
            'success': True,
            'hint_text': hint.hint_text,
            'points_spent': hint.cost
        }
    
    def rate_lab(self, user_id, lab_id, rating, difficulty_rating=None, feedback=None):
        """Rate a lab"""
        # Check if already rated
        existing_rating = LabRating.query.filter_by(user_id=user_id, lab_id=lab_id).first()
        
        if existing_rating:
            # Update existing rating
            existing_rating.rating = rating
            existing_rating.difficulty_rating = difficulty_rating
            existing_rating.feedback = feedback
            existing_rating.created_at = datetime.utcnow()
        else:
            # Create new rating
            rating_obj = LabRating(
                user_id=user_id,
                lab_id=lab_id,
                rating=rating,
                difficulty_rating=difficulty_rating,
                feedback=feedback
            )
            db.session.add(rating_obj)
        
        # Update lab's average rating
        lab = Lab.query.get(lab_id)
        if lab:
            ratings = LabRating.query.filter_by(lab_id=lab_id).all()
            if ratings:
                lab.difficulty_rating = sum(r.rating for r in ratings) / len(ratings)
        
        db.session.commit()
        return {'success': True, 'message': 'Rating submitted'}
    
    def get_lab_statistics(self, lab_id):
        """Get comprehensive statistics for a lab"""
        lab = Lab.query.get(lab_id)
        if not lab:
            return None
        
        # Get completion statistics
        total_attempts = LabProgress.query.filter_by(lab_id=lab_id).count()
        completed_attempts = LabProgress.query.filter_by(
            lab_id=lab_id, 
            completed_at=None
        ).count()
        
        completion_rate = (completed_attempts / total_attempts * 100) if total_attempts > 0 else 0
        
        # Get average completion time
        completed_progress = LabProgress.query.filter_by(
            lab_id=lab_id
        ).filter(LabProgress.completed_at != None).all()
        
        if completed_progress:
            avg_time = sum(p.time_spent for p in completed_progress) / len(completed_progress)
        else:
            avg_time = 0
        
        # Get rating statistics
        ratings = LabRating.query.filter_by(lab_id=lab_id).all()
        avg_rating = sum(r.rating for r in ratings) / len(ratings) if ratings else 0
        
        return {
            'total_attempts': total_attempts,
            'completed_attempts': completed_attempts,
            'completion_rate': completion_rate,
            'average_time': avg_time,
            'average_rating': avg_rating,
            'total_ratings': len(ratings)
        }
    
    def get_learning_path_progress(self, user_id, path_id):
        """Get progress through a learning path"""
        path = LearningPath.query.get(path_id)
        if not path:
            return None
        
        labs = Lab.query.filter_by(learning_path_id=path_id).order_by(Lab.path_order).all()
        completed_labs = 0
        total_points = 0
        
        for lab in labs:
            progress = LabProgress.query.filter_by(
                user_id=user_id, 
                lab_id=lab.id
            ).filter(LabProgress.completed_at != None).first()
            
            if progress:
                completed_labs += 1
                total_points += lab.points
        
        return {
            'path': path,
            'total_labs': len(labs),
            'completed_labs': completed_labs,
            'progress_percentage': (completed_labs / len(labs) * 100) if labs else 0,
            'total_points': total_points,
            'labs': labs
        }
    
    def get_ctf_leaderboard(self):
        """Get CTF leaderboard"""
        # Get all users with their CTF points
        users = User.query.all()
        leaderboard = []
        
        for user in users:
            submissions = CTFSubmission.query.filter_by(
                user_id=user.id, 
                is_correct=True
            ).all()
            
            total_points = sum(s.points_earned for s in submissions)
            solved_challenges = len(submissions)
            
            if solved_challenges > 0:
                leaderboard.append({
                    'user': user,
                    'points': total_points,
                    'solved': solved_challenges
                })
        
        # Sort by points (descending)
        leaderboard.sort(key=lambda x: x['points'], reverse=True)
        return leaderboard[:50]  # Top 50
    
    def cleanup_expired_sessions(self):
        """Clean up expired sandbox sessions"""
        expired_sessions = UserSandboxSession.query.filter(
            UserSandboxSession.started_at < datetime.utcnow() - timedelta(hours=2),
            UserSandboxSession.status == 'running'
        ).all()
        
        for session in expired_sessions:
            self.stop_sandbox_session(session.session_id)
        
        return len(expired_sessions)

# Predefined lab categories and difficulties
LAB_CATEGORIES = {
    'web': ['sql_injection', 'xss', 'csrf', 'file_upload', 'authentication', 'authorization'],
    'network': ['port_scanning', 'network_enumeration', 'sniffing', 'man_in_middle', 'arp_spoofing'],
    'crypto': ['caesar_cipher', 'substitution', 'transposition', 'rsa', 'hash_cracking'],
    'forensics': ['memory_analysis', 'disk_analysis', 'network_forensics', 'steganography'],
    'reverse_engineering': ['malware_analysis', 'binary_analysis', 'decompilation', 'debugging'],
    'exploitation': ['buffer_overflow', 'rop_chains', 'shellcode', 'privilege_escalation'],
    'wireless': ['wifi_cracking', 'bluetooth_attacks', 'rf_analysis', 'signal_jamming'],
    'mobile': ['android_analysis', 'ios_analysis', 'app_reverse', 'mobile_forensics']
}

LAB_DIFFICULTIES = {
    'easy': {'points': 10, 'time': 15, 'hints': 3},
    'medium': {'points': 25, 'time': 30, 'hints': 2},
    'hard': {'points': 50, 'time': 60, 'hints': 1},
    'expert': {'points': 100, 'time': 120, 'hints': 0}
}

CTF_CATEGORIES = ['web', 'crypto', 'forensics', 'pwn', 'reverse', 'misc', 'stego', 'mobile'] 