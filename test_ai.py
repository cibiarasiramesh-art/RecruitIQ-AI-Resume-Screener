from services.ai_resume_analyzer import analyze_resume

resume = """
Python
Flask
SQLite
REST API
Git
"""

job = """
Backend Developer

Required Skills:
Python
Flask
REST API
SQL
Docker
Git
"""

result = analyze_resume(resume, job)

print(result)