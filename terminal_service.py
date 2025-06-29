import subprocess
import re
import json
from datetime import datetime
from models import LabTerminalCommand, LabTerminalAttempt, LabTerminalSession, db

class TerminalService:
    """Service for handling terminal-based lab operations"""
    
    def __init__(self):
        self.supported_shells = ['bash', 'powershell', 'cmd']
    
    def create_terminal_session(self, user_id, lab_id):
        """Create a new terminal session for a user"""
        # Get all commands for this lab
        commands = LabTerminalCommand.query.filter_by(lab_id=lab_id).order_by(LabTerminalCommand.order).all()
        
        if not commands:
            return None
        
        # Create session
        session = LabTerminalSession(
            user_id=user_id,
            lab_id=lab_id,
            session_id=f"session_{user_id}_{lab_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            current_step=1,
            total_steps=len(commands),
            max_points=sum(cmd.points for cmd in commands)
        )
        
        db.session.add(session)
        db.session.commit()
        
        return session
    
    def get_current_command(self, session_id):
        """Get the current expected command for a session"""
        session = LabTerminalSession.query.filter_by(session_id=session_id).first()
        if not session:
            return None
        
        command = LabTerminalCommand.query.filter_by(
            lab_id=session.lab_id,
            order=session.current_step
        ).first()
        
        return command
    
    def validate_command(self, session_id, user_command, user_output=None):
        """Validate a user's command against the expected command"""
        session = LabTerminalSession.query.filter_by(session_id=session_id).first()
        if not session:
            return {'success': False, 'message': 'Session not found'}
        
        expected_command = self.get_current_command(session_id)
        if not expected_command:
            return {'success': False, 'message': 'No expected command found'}
        
        # Check if command matches (case-insensitive, trim whitespace)
        command_match = user_command.strip().lower() == expected_command.command.strip().lower()
        
        # Check output if required
        output_match = True
        if expected_command.expected_output and user_output:
            output_match = self._check_output_match(user_output, expected_command.expected_output)
        
        is_correct = command_match and output_match
        
        # Record attempt
        attempt = LabTerminalAttempt(
            user_id=session.user_id,
            lab_id=session.lab_id,
            command_id=expected_command.id,
            user_command=user_command,
            user_output=user_output,
            is_correct=is_correct,
            points_earned=expected_command.points if is_correct else 0
        )
        
        db.session.add(attempt)
        
        # Update session if correct
        if is_correct:
            session.completed_steps += 1
            session.total_points += expected_command.points
            session.current_step += 1
            
            # Check if lab is completed
            if session.current_step > session.total_steps:
                session.is_completed = True
                session.completed_at = datetime.utcnow()
        
        db.session.commit()
        
        return {
            'success': True,
            'is_correct': is_correct,
            'points_earned': attempt.points_earned,
            'next_step': session.current_step if is_correct else session.current_step,
            'total_steps': session.total_steps,
            'completed_steps': session.completed_steps,
            'is_completed': session.is_completed,
            'hint': expected_command.hint if not is_correct else None,
            'expected_command': expected_command.command if not is_correct else None,
            'expected_output': expected_command.expected_output if not is_correct else None
        }
    
    def _check_output_match(self, user_output, expected_output):
        """Check if user output matches expected output"""
        if not expected_output:
            return True
        
        # Simple string matching for now
        # Could be enhanced with regex patterns
        return expected_output.strip().lower() in user_output.strip().lower()
    
    def get_session_progress(self, session_id):
        """Get the current progress of a terminal session"""
        session = LabTerminalSession.query.filter_by(session_id=session_id).first()
        if not session:
            return None
        
        return {
            'current_step': session.current_step,
            'total_steps': session.total_steps,
            'completed_steps': session.completed_steps,
            'total_points': session.total_points,
            'max_points': session.max_points,
            'is_completed': session.is_completed,
            'progress_percentage': (session.completed_steps / session.total_steps) * 100 if session.total_steps > 0 else 0
        }
    
    def reset_session(self, session_id):
        """Reset a terminal session to start over"""
        session = LabTerminalSession.query.filter_by(session_id=session_id).first()
        if not session:
            return False
        
        session.current_step = 1
        session.completed_steps = 0
        session.total_points = 0
        session.is_completed = False
        session.completed_at = None
        
        db.session.commit()
        return True
    
    def get_lab_commands(self, lab_id):
        """Get all commands for a lab (admin function)"""
        commands = LabTerminalCommand.query.filter_by(lab_id=lab_id).order_by(LabTerminalCommand.order).all()
        return commands
    
    def add_lab_command(self, lab_id, command, expected_output=None, order=None, points=1, hint=None, description=None, is_optional=False):
        """Add a new command to a lab (admin function)"""
        if order is None:
            # Auto-assign order
            max_order = db.session.query(db.func.max(LabTerminalCommand.order)).filter_by(lab_id=lab_id).scalar()
            order = (max_order or 0) + 1
        
        command_obj = LabTerminalCommand(
            lab_id=lab_id,
            command=command,
            expected_output=expected_output,
            order=order,
            points=points,
            hint=hint,
            description=description,
            is_optional=is_optional
        )
        
        db.session.add(command_obj)
        db.session.commit()
        
        return command_obj
    
    def update_lab_command(self, command_id, **kwargs):
        """Update a lab command (admin function)"""
        command = LabTerminalCommand.query.get(command_id)
        if not command:
            return None
        
        for key, value in kwargs.items():
            if hasattr(command, key):
                setattr(command, key, value)
        
        db.session.commit()
        return command
    
    def delete_lab_command(self, command_id):
        """Delete a lab command (admin function)"""
        command = LabTerminalCommand.query.get(command_id)
        if not command:
            return False
        
        db.session.delete(command)
        db.session.commit()
        
        return True
    
    def reorder_commands(self, lab_id, command_orders):
        """Reorder commands for a lab (admin function)"""
        # command_orders should be a dict: {command_id: new_order}
        for command_id, new_order in command_orders.items():
            command = LabTerminalCommand.query.get(command_id)
            if command and command.lab_id == lab_id:
                command.order = new_order
        
        db.session.commit()
        return True 