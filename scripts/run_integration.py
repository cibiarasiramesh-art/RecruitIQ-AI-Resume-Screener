from app import app, init_db
from io import BytesIO
import time

init_db()
client = app.test_client()

# Register a test user with a timestamped email to avoid duplicates
ts = int(time.time())
test_email = f"inttest+{ts}@example.com"
resp = client.post('/api/register', json={'name': 'IntTest', 'email': test_email, 'password': 'secret123'})
print('register', resp.status_code, resp.get_json())

# Upload a sample resume and analyze
fd = {'resume': (BytesIO(b'Python Flask REST API Git SQL'), 'resume.txt')}
resp = client.post('/api/analyze', data=fd, content_type='multipart/form-data')
print('analyze', resp.status_code)
body = resp.get_json()
print('keys', sorted(body.keys()))
print('scores', body.get('scores'))
print('matched', body.get('skills_matched'))
print('missing', body.get('skills_missing'))
print('history_id', body.get('history_id'))

# Fetch report
report_resp = client.get(f"/api/report/{body.get('history_id')}")
print('report', report_resp.status_code, report_resp.content_type)
print('report bytes', len(report_resp.data))
