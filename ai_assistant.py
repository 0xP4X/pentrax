import os
import json
from openai import OpenAI

# the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
# do not change this unless explicitly requested by the user
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "default-key")
client = OpenAI(api_key=OPENAI_API_KEY)

def get_ai_response(user_message):
    """
    Get AI assistant response for cybersecurity-related queries
    """
    try:
        system_prompt = """You are a cybersecurity expert AI assistant for PentraX, a platform for cybersecurity professionals. 
        You help users with:
        - Debugging security tools and scripts
        - Explaining cybersecurity concepts and vulnerabilities
        - Guiding through penetration testing techniques
        - Reviewing code for security issues
        - Suggesting improvements for security tools
        - Explaining CVEs and attack vectors
        
        Always provide helpful, accurate, and ethical cybersecurity guidance. 
        Focus on defensive security and responsible disclosure practices.
        Keep responses concise but informative."""
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            max_tokens=500,
            temperature=0.7
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        return f"I'm currently unavailable. Please try again later. Error: {str(e)}"

def analyze_code_security(code_content):
    """
    Analyze code for potential security vulnerabilities
    """
    try:
        prompt = f"""Analyze the following code for security vulnerabilities and provide recommendations:

{code_content}

Please identify:
1. Potential security vulnerabilities
2. Best practice violations
3. Recommended fixes
4. Overall security assessment

Respond in JSON format with: {{"vulnerabilities": [], "recommendations": [], "severity": "low/medium/high"}}"""

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a security code reviewer. Analyze code for vulnerabilities."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            max_tokens=800
        )
        
        return json.loads(response.choices[0].message.content)
        
    except Exception as e:
        return {
            "vulnerabilities": ["Unable to analyze code at this time"],
            "recommendations": ["Please try again later"],
            "severity": "unknown",
            "error": str(e)
        }
