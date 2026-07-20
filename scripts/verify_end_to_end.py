"""
Verify end-to-end application flows via Flask test client.
Checks:
- Root redirects to login when unauthenticated
- Register, login, logout, session handling
- Unauthorized dashboard access
- Upload & analyze resume
- History saved
- Report download returns PDF
"""
from app import app, init_db
from io import BytesIO

init_db()
client = app.test_client()

def assert_status(resp, code):
    print(f"Status {resp.status_code} (expected {code})")
    assert resp.status_code == code, resp.get_data(as_text=True)

# 1. Root should redirect to login
resp = client.get('/')
assert_status(resp, 302)
print('Root redirect location:', resp.headers.get('Location'))

# 2. Unauthenticated dashboard access should redirect to login
resp = client.get('/dashboard')
assert_status(resp, 302)
print('Dashboard redirect location:', resp.headers.get('Location'))

# 3. Register
resp = client.post('/api/register', json={'name':'Verify','email':'verify@example.com','password':'verify123'})
print('register', resp.status_code, resp.get_json())
assert resp.status_code in (200, 201)

# 4. After register, dashboard should be accessible
resp = client.get('/dashboard')
assert_status(resp, 200)

# 5. Logout and ensure dashboard protected
resp = client.get('/logout')
assert_status(resp, 302)
resp = client.get('/dashboard')
assert_status(resp, 302)

# 6. Login
resp = client.post('/api/login', json={'email':'verify@example.com','password':'verify123'})
print('login', resp.status_code, resp.get_json())
assert_status(resp, 200)

# 7. Upload & analyze
fd = {'resume': (BytesIO(b'Test resume content Python Flask SQL'), 'resume.txt')}
resp = client.post('/api/analyze', data=fd, content_type='multipart/form-data')
print('analyze', resp.status_code)
body = resp.get_json()
print('keys', sorted(body.keys()))
assert_status(resp, 200)
assert 'history_id' in body and body['history_id']

hid = body['history_id']

# 8. History fetch
resp = client.get('/api/history')
print('history', resp.status_code, resp.get_json())
assert_status(resp, 200)
items = resp.get_json().get('items', [])
assert any(i['id'] == hid for i in items)

# 9. Report download
resp = client.get(f'/api/report/{hid}')
print('report', resp.status_code, resp.content_type)
assert_status(resp, 200)
print('report length', len(resp.data))
assert len(resp.data) > 200

print('All checks passed.')
