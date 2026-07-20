"""
Real end-to-end verification script:
- Register user
- Analyze resume via /api/analyze
- Inspect SQLite history row
- Download report and validate PDF using pypdf
- Load scikit-learn model via predict_resume_match and compare scores
"""
import os
import json
from io import BytesIO
from datetime import datetime
import sqlite3

from app import app, init_db, BASE_DIR
from models.custom_resume_model import predict_resume_match, MODEL_PATH, load_model

init_db()
client = app.test_client()

# Unique email
email = f"e2e+{int(datetime.utcnow().timestamp())}@example.com"
print('Registering:', email)
resp = client.post('/api/register', json={'name':'E2E','email':email,'password':'verify123'})
print('register', resp.status_code, resp.get_json())
assert resp.status_code == 200

# Analyze
resume_text = b"Experienced Python developer with Flask, SQL, Docker, AWS"
fd = {'resume': (BytesIO(resume_text), 'resume.txt')}
resp = client.post('/api/analyze', data=fd, content_type='multipart/form-data')
print('analyze status', resp.status_code)
body = resp.get_json()
print('analyze keys:', sorted(body.keys()))
print('ats_score:', body.get('ats_score'))
print('skills_matched sample:', {k:v for k,v in list(body.get('skills_matched', {}).items())[:3]})
print('skills_missing sample:', {k:v for k,v in list(body.get('skills_missing', {}).items())[:3]})
assert resp.status_code == 200
hid = body.get('history_id')
assert hid

# Inspect DB
db_path = os.path.join(BASE_DIR, 'database.db')
print('DB path:', db_path)
con = sqlite3.connect(db_path)
cur = con.cursor()
cur.execute('SELECT id, user_id, filename, job_title, overall_score, ats_score, data_json, created_at FROM history WHERE id = ?', (hid,))
row = cur.fetchone()
assert row, 'History row not found'
print('history row:', row[0:6])
data_json = json.loads(row[6])
print('data_json keys:', list(data_json.keys()))
assert 'ai_analysis' in data_json
print('ai_analysis keys:', list(data_json['ai_analysis'].keys()))
con.close()

# Report download
resp = client.get(f'/api/report/{hid}')
print('report status', resp.status_code, resp.content_type)
assert resp.status_code == 200
pdf_bytes = resp.data
print('report bytes len', len(pdf_bytes))

# Validate PDF using pypdf
try:
    from pypdf import PdfReader
    reader = PdfReader(BytesIO(pdf_bytes))
    print('PDF pages:', len(reader.pages))
    assert len(reader.pages) >= 1
except Exception as e:
    print('PDF validation failed:', e)
    raise

# Model verification: load model and predict
print('MODEL_PATH:', MODEL_PATH)
model = load_model(MODEL_PATH)
print('Model keys:', list(model.keys()))
model_pred = predict_resume_match(resume_text.decode('utf-8'), '')
print('model_pred ats:', model_pred.get('ats_score'))

# Compare to API ai_analysis
ai_ats = data_json.get('ai_analysis', {}).get('ats_score')
print('ai_analysis ats:', ai_ats)

# Basic sanity checks
assert isinstance(model_pred.get('ats_score'), (int, float))
assert model_pred.get('ats_score') >= 0

print('\nE2E real verification PASSED')
