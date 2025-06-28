#!/usr/bin/env python3
"""
Script to add sample labs for demo/testing
"""
from app import app, db
from models import Lab, LabQuizQuestion
import json

def add_sample_labs():
    with app.app_context():
        sample_labs = [
            {
                'title': 'SQL Injection Basics',
                'description': 'Learn to identify and exploit basic SQL injection vulnerabilities.',
                'difficulty': 'easy',
                'category': 'web',
                'points': 50,
                'hints': 'Try using a single quote in the input field.',
                'solution': 'Use UNION SELECT to extract data.',
                'flag': 'PENTRAX{sql_injection_master}',
                'instructions': 'Find the admin password by exploiting the login form.',
                'tools_needed': 'Burp Suite, browser',
                'learning_objectives': 'Understand SQLi basics and bypass authentication.',
                'is_premium': False,
                'is_active': True,
                'estimated_time': 15,
                'quiz': [
                    {
                        'question': 'What is the most common character to test for SQL injection?',
                        'options': [';', "'", '"', '--'],
                        'correct_answer': "'",
                        'explanation': "A single quote (') is often used to test for SQL injection vulnerabilities."
                    },
                    {
                        'question': 'Which SQL command can be used to extract data from another table?',
                        'options': ['SELECT', 'INSERT', 'UPDATE', 'DELETE'],
                        'correct_answer': 'SELECT',
                        'explanation': 'SELECT is used to retrieve data from a database.'
                    }
                ]
            },
            {
                'title': 'XSS Challenge',
                'description': 'Exploit cross-site scripting vulnerabilities in web applications.',
                'difficulty': 'medium',
                'category': 'web',
                'points': 100,
                'hints': 'Try injecting a <script> tag.',
                'solution': 'Inject <script>alert(1)</script> in the comment box.',
                'flag': 'PENTRAX{xss_found}',
                'instructions': 'Trigger a JavaScript alert by injecting code into the comment box.',
                'tools_needed': 'Browser, developer tools',
                'learning_objectives': 'Understand and exploit XSS vulnerabilities.',
                'is_premium': False,
                'is_active': True,
                'estimated_time': 30,
                'quiz': [
                    {
                        'question': 'What does XSS stand for?',
                        'options': ['Cross-Site Scripting', 'Extra Secure Sockets', 'XML Site Scripting', 'Cross Server Scripting'],
                        'correct_answer': 'Cross-Site Scripting',
                        'explanation': 'XSS stands for Cross-Site Scripting.'
                    }
                ]
            },
            {
                'title': 'Gobuster Enumeration',
                'description': 'Use Gobuster to discover hidden directories and files.',
                'difficulty': 'easy',
                'category': 'network',
                'points': 75,
                'hints': 'Use a common wordlist.',
                'solution': 'Find /hidden/flag.txt',
                'flag': 'PENTRAX{gobuster_success}',
                'instructions': 'Enumerate the target to find the hidden flag file.',
                'tools_needed': 'Gobuster, wordlists',
                'learning_objectives': 'Practice directory brute-forcing.',
                'is_premium': False,
                'is_active': True,
                'estimated_time': 20,
                'quiz': [
                    {
                        'question': 'Which tool is used for directory brute-forcing?',
                        'options': ['Gobuster', 'Nmap', 'Nikto', 'Hydra'],
                        'correct_answer': 'Gobuster',
                        'explanation': 'Gobuster is a tool for brute-forcing directories and files.'
                    }
                ]
            },
            {
                'title': 'Linux Privilege Escalation (Sandbox)',
                'description': 'Practice privilege escalation in a real Linux sandbox environment.',
                'difficulty': 'hard',
                'category': 'system',
                'points': 200,
                'hints': 'Check for SUID binaries and misconfigured sudo.',
                'solution': 'Exploit a vulnerable SUID binary to get root.',
                'flag': 'PENTRAX{root_shell}',
                'instructions': 'Connect to the sandbox and escalate your privileges to root. The flag is in /root/flag.txt.',
                'tools_needed': 'Linux terminal, enumeration scripts',
                'learning_objectives': 'Understand Linux privilege escalation techniques.',
                'is_premium': True,
                'is_active': True,
                'estimated_time': 60,
                'sandbox_url': 'ssh://demo-user@demo-sandbox.pentrax.local:2222',
                'sandbox_instructions': 'Use SSH to connect: ssh demo-user@demo-sandbox.pentrax.local -p 2222. Your goal is to get a root shell and read /root/flag.txt.'
            }
        ]
        for lab_data in sample_labs:
            quiz = lab_data.pop('quiz', None)
            lab = Lab.query.filter_by(title=lab_data['title']).first()
            if not lab:
                lab = Lab(**lab_data)
                db.session.add(lab)
                db.session.flush()  # Get lab.id
                print(f"Added: {lab_data['title']}")
            else:
                print(f"Already exists: {lab_data['title']}")
            # Add quiz questions if present
            if quiz:
                for i, q in enumerate(quiz):
                    if not LabQuizQuestion.query.filter_by(lab_id=lab.id, question=q['question']).first():
                        qq = LabQuizQuestion(
                            lab_id=lab.id,
                            question=q['question'],
                            options=json.dumps(q['options']),
                            correct_answer=q['correct_answer'],
                            explanation=q.get('explanation', ''),
                            order=i
                        )
                        db.session.add(qq)
        db.session.commit()
        print("\n✅ Sample labs and quiz questions added successfully!")

if __name__ == "__main__":
    add_sample_labs() 