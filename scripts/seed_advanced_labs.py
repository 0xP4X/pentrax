#!/usr/bin/env python3
"""
Script to seed advanced cybersecurity labs with sample content
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import Lab, LearningPath, CTFChallenge, SandboxEnvironment, LabHint, User
from utils.lab_manager import LabManager
from datetime import datetime, timedelta
import json

def seed_learning_paths():
    """Create sample learning paths"""
    lab_manager = LabManager()
    
    paths = [
        {
            'name': 'Web Security Fundamentals',
            'description': 'Learn the basics of web security including SQL injection, XSS, and authentication bypass techniques.',
            'difficulty': 'beginner',
            'category': 'web_security',
            'estimated_duration': 20,
            'prerequisites': 'Basic knowledge of HTML, CSS, and JavaScript',
            'learning_objectives': 'Understand common web vulnerabilities and how to exploit them',
            'target_audience': 'Beginners interested in web security'
        },
        {
            'name': 'Network Penetration Testing',
            'description': 'Master network reconnaissance, enumeration, and exploitation techniques.',
            'difficulty': 'intermediate',
            'category': 'network_security',
            'estimated_duration': 30,
            'prerequisites': 'Basic networking knowledge, familiarity with Linux',
            'learning_objectives': 'Learn network scanning, enumeration, and exploitation',
            'target_audience': 'Security professionals and ethical hackers'
        },
        {
            'name': 'Reverse Engineering',
            'description': 'Learn to analyze and reverse engineer software and malware.',
            'difficulty': 'advanced',
            'category': 'reverse_engineering',
            'estimated_duration': 40,
            'prerequisites': 'Programming knowledge, assembly language basics',
            'learning_objectives': 'Master static and dynamic analysis techniques',
            'target_audience': 'Advanced security researchers and malware analysts'
        },
        {
            'name': 'Digital Forensics',
            'description': 'Learn digital forensics techniques for evidence collection and analysis.',
            'difficulty': 'intermediate',
            'category': 'digital_forensics',
            'estimated_duration': 25,
            'prerequisites': 'Basic computer knowledge',
            'learning_objectives': 'Understand forensic tools and evidence handling',
            'target_audience': 'Law enforcement, security professionals'
        }
    ]
    
    created_paths = []
    for path_data in paths:
        path = lab_manager.create_learning_path(**path_data)
        created_paths.append(path)
        print(f"✅ Created learning path: {path.name}")
    
    return created_paths

def seed_advanced_labs():
    """Create sample advanced labs"""
    labs = [
        # Web Security Labs
        {
            'title': 'SQL Injection Basics',
            'description': 'Learn SQL injection techniques by exploiting a vulnerable web application.',
            'difficulty': 'easy',
            'category': 'web',
            'subcategory': 'sql_injection',
            'points': 25,
            'lab_type': 'terminal',
            'terminal_enabled': True,
            'estimated_time': 30,
            'learning_objectives': 'Understand SQL injection vulnerabilities and exploitation',
            'tools_needed': 'Burp Suite, SQLMap, Web browser',
            'instructions': '''
1. Start the vulnerable web application
2. Identify the SQL injection point
3. Use SQLMap to extract database information
4. Find the flag in the database
            ''',
            'flag': 'flag{sql_injection_master}',
            'is_premium': False
        },
        {
            'title': 'XSS Cross-Site Scripting',
            'description': 'Practice Cross-Site Scripting attacks on a vulnerable application.',
            'difficulty': 'medium',
            'category': 'web',
            'subcategory': 'xss',
            'points': 35,
            'lab_type': 'terminal',
            'terminal_enabled': True,
            'estimated_time': 45,
            'learning_objectives': 'Master XSS attack techniques and payloads',
            'tools_needed': 'Burp Suite, Web browser, JavaScript knowledge',
            'instructions': '''
1. Identify XSS vulnerabilities in the application
2. Craft malicious JavaScript payloads
3. Steal user cookies and session data
4. Execute the final payload to get the flag
            ''',
            'flag': 'flag{xss_expert}',
            'is_premium': True
        },
        {
            'title': 'Buffer Overflow Exploitation',
            'description': 'Learn buffer overflow exploitation on a vulnerable binary.',
            'difficulty': 'hard',
            'category': 'exploitation',
            'subcategory': 'buffer_overflow',
            'points': 75,
            'lab_type': 'terminal',
            'terminal_enabled': True,
            'estimated_time': 90,
            'learning_objectives': 'Understand memory corruption and exploitation',
            'tools_needed': 'GDB, Python, pwntools',
            'instructions': '''
1. Analyze the vulnerable binary
2. Identify the buffer overflow vulnerability
3. Create a payload to control execution flow
4. Exploit the vulnerability to get shell access
            ''',
            'flag': 'flag{buffer_overflow_master}',
            'is_premium': True
        },
        {
            'title': 'Network Enumeration',
            'description': 'Practice network reconnaissance and enumeration techniques.',
            'difficulty': 'easy',
            'category': 'network',
            'subcategory': 'network_enumeration',
            'points': 20,
            'lab_type': 'terminal',
            'terminal_enabled': True,
            'estimated_time': 25,
            'learning_objectives': 'Learn network scanning and enumeration',
            'tools_needed': 'Nmap, Netcat, Wireshark',
            'instructions': '''
1. Scan the target network
2. Identify open ports and services
3. Enumerate running services
4. Find hidden information and the flag
            ''',
            'flag': 'flag{network_enumeration_complete}',
            'is_premium': False
        },
        {
            'title': 'Cryptography Challenge',
            'description': 'Solve cryptographic challenges using various techniques.',
            'difficulty': 'medium',
            'category': 'crypto',
            'subcategory': 'hash_cracking',
            'points': 40,
            'lab_type': 'quiz',
            'estimated_time': 60,
            'learning_objectives': 'Understand cryptographic concepts and attacks',
            'tools_needed': 'Hashcat, Python, Cryptography libraries',
            'instructions': '''
1. Analyze the encrypted data
2. Identify the encryption algorithm
3. Use appropriate tools to crack the encryption
4. Decrypt the flag
            ''',
            'flag': 'flag{crypto_master}',
            'is_premium': False
        }
    ]
    
    # Get admin user for lab creation
    admin_user = User.query.filter_by(username='admin').first()
    if not admin_user:
        print("❌ Admin user not found!")
        return []
    
    created_labs = []
    for lab_data in labs:
        lab = Lab(
            user_id=admin_user.id,
            **lab_data
        )
        db.session.add(lab)
        created_labs.append(lab)
        print(f"✅ Created lab: {lab.title}")
    
    db.session.commit()
    return created_labs

def seed_ctf_challenges():
    """Create sample CTF challenges"""
    challenges = [
        {
            'title': 'Web Flag Finder',
            'description': 'Find the hidden flag in this web application by exploring all possible paths.',
            'category': 'web',
            'difficulty': 'easy',
            'points': 100,
            'flag': 'flag{web_exploration_complete}',
            'hints': json.dumps(['Check the source code', 'Look for hidden directories', 'Try different HTTP methods']),
            'challenge_type': 'jeopardy'
        },
        {
            'title': 'Crypto Puzzle',
            'description': 'Decrypt this message using the provided key and algorithm.',
            'category': 'crypto',
            'difficulty': 'medium',
            'points': 200,
            'flag': 'flag{crypto_solved}',
            'hints': json.dumps(['The key is in the filename', 'Use base64 decoding', 'Try XOR encryption']),
            'challenge_type': 'jeopardy'
        },
        {
            'title': 'Memory Forensics',
            'description': 'Analyze this memory dump to find the hidden flag.',
            'category': 'forensics',
            'difficulty': 'hard',
            'points': 300,
            'flag': 'flag{memory_analysis_complete}',
            'hints': json.dumps(['Look for strings in memory', 'Check running processes', 'Search for file artifacts']),
            'challenge_type': 'jeopardy'
        },
        {
            'title': 'Binary Exploitation',
            'description': 'Exploit this vulnerable binary to get shell access and find the flag.',
            'category': 'pwn',
            'difficulty': 'hard',
            'points': 400,
            'flag': 'flag{binary_exploitation_master}',
            'hints': json.dumps(['Check for buffer overflow', 'Use GDB to analyze', 'Create a ROP chain']),
            'challenge_type': 'jeopardy'
        },
        {
            'title': 'Steganography',
            'description': 'Find the hidden message in this image file.',
            'category': 'stego',
            'difficulty': 'easy',
            'points': 150,
            'flag': 'flag{stego_master}',
            'hints': json.dumps(['Check the image metadata', 'Look for hidden data', 'Try different stego tools']),
            'challenge_type': 'jeopardy'
        }
    ]
    
    lab_manager = LabManager()
    created_challenges = []
    
    for challenge_data in challenges:
        challenge = lab_manager.create_ctf_challenge(**challenge_data)
        created_challenges.append(challenge)
        print(f"✅ Created CTF challenge: {challenge.title}")
    
    return created_challenges

def seed_sandbox_environments():
    """Create sample sandbox environments"""
    sandboxes = [
        {
            'name': 'Kali Linux Sandbox',
            'description': 'Full Kali Linux environment with penetration testing tools pre-installed.',
            'environment_type': 'docker',
            'image_name': 'kalilinux/kali-rolling',
            'configuration': json.dumps({
                'ports': {'22/tcp': 2222, '80/tcp': 8080, '443/tcp': 8443},
                'volumes': ['/tmp/pentrax:/workspace'],
                'environment': {'DISPLAY': ':0'}
            }),
            'resources': json.dumps({
                'cpu': '2 cores',
                'memory': '4GB',
                'storage': '20GB'
            }),
            'max_concurrent_users': 5
        },
        {
            'name': 'Windows 10 Sandbox',
            'description': 'Windows 10 environment for Windows-specific security testing.',
            'environment_type': 'vm',
            'image_name': 'windows-10-security',
            'configuration': json.dumps({
                'ram': '4GB',
                'cpu': '2 cores',
                'network': 'bridged'
            }),
            'resources': json.dumps({
                'cpu': '2 cores',
                'memory': '4GB',
                'storage': '50GB'
            }),
            'max_concurrent_users': 3
        },
        {
            'name': 'Web Application Sandbox',
            'description': 'Vulnerable web applications for practice and testing.',
            'environment_type': 'docker',
            'image_name': 'vulnerables/web-dvwa',
            'configuration': json.dumps({
                'ports': {'80/tcp': 8081},
                'environment': {'MYSQL_ROOT_PASSWORD': 'pentrax123'}
            }),
            'resources': json.dumps({
                'cpu': '1 core',
                'memory': '2GB',
                'storage': '10GB'
            }),
            'max_concurrent_users': 10
        }
    ]
    
    lab_manager = LabManager()
    created_sandboxes = []
    
    for sandbox_data in sandboxes:
        sandbox = lab_manager.create_sandbox_environment(**sandbox_data)
        created_sandboxes.append(sandbox)
        print(f"✅ Created sandbox: {sandbox.name}")
    
    return created_sandboxes

def seed_lab_hints():
    """Create sample hints for labs"""
    hints_data = [
        # SQL Injection hints
        {
            'lab_title': 'SQL Injection Basics',
            'hints': [
                {'text': 'Try adding a single quote to see if the application is vulnerable', 'order': 1, 'cost': 0},
                {'text': 'Use UNION SELECT to extract data from the database', 'order': 2, 'cost': 5},
                {'text': 'The flag is stored in a table called "flags"', 'order': 3, 'cost': 10}
            ]
        },
        # XSS hints
        {
            'lab_title': 'XSS Cross-Site Scripting',
            'hints': [
                {'text': 'Look for input fields that reflect user input', 'order': 1, 'cost': 0},
                {'text': 'Try basic XSS payloads like <script>alert(1)</script>', 'order': 2, 'cost': 5},
                {'text': 'Use JavaScript to steal cookies and send them to your server', 'order': 3, 'cost': 15}
            ]
        },
        # Buffer Overflow hints
        {
            'lab_title': 'Buffer Overflow Exploitation',
            'hints': [
                {'text': 'Use GDB to analyze the binary and find the vulnerable function', 'order': 1, 'cost': 0},
                {'text': 'Create a pattern to find the exact offset', 'order': 2, 'cost': 10},
                {'text': 'Use ROP gadgets to bypass ASLR and DEP', 'order': 3, 'cost': 25}
            ]
        }
    ]
    
    for hint_data in hints_data:
        lab = Lab.query.filter_by(title=hint_data['lab_title']).first()
        if lab:
            for hint_info in hint_data['hints']:
                hint = LabHint(
                    lab_id=lab.id,
                    hint_text=hint_info['text'],
                    hint_order=hint_info['order'],
                    cost=hint_info['cost'],
                    is_free=hint_info['cost'] == 0
                )
                db.session.add(hint)
                print(f"✅ Added hint for {lab.title}: {hint_info['text'][:50]}...")
    
    db.session.commit()

def main():
    """Main seeding function"""
    with app.app_context():
        print("🚀 Starting advanced lab system seeding...")
        
        # Create learning paths
        print("\n📚 Creating learning paths...")
        paths = seed_learning_paths()
        
        # Create advanced labs
        print("\n🔬 Creating advanced labs...")
        labs = seed_advanced_labs()
        
        # Create CTF challenges
        print("\n🏁 Creating CTF challenges...")
        challenges = seed_ctf_challenges()
        
        # Create sandbox environments
        print("\n📦 Creating sandbox environments...")
        sandboxes = seed_sandbox_environments()
        
        # Create lab hints
        print("\n💡 Creating lab hints...")
        seed_lab_hints()
        
        print(f"\n✅ Seeding completed successfully!")
        print(f"📊 Summary:")
        print(f"   - Learning Paths: {len(paths)}")
        print(f"   - Advanced Labs: {len(labs)}")
        print(f"   - CTF Challenges: {len(challenges)}")
        print(f"   - Sandbox Environments: {len(sandboxes)}")
        print(f"\n🎯 Your advanced cybersecurity training platform is ready!")

if __name__ == "__main__":
    main() 