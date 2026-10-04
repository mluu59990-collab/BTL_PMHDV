"""Integration test: real Gateway/BE code and Argon2/JWT, fake stored-procedure results."""
import importlib.util
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import httpx
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
backend = Path(sys.argv[1])
sys.path.insert(0, str(backend))
os.environ['DEBUG'] = 'false'
os.environ['JWT_SECRET_KEY'] = 'integration-jwt-key-' * 4
os.environ['GATEWAY_SHARED_SECRET'] = 'integration-gateway-key-' * 4
from app.core import config
base = config.Settings(_env_file=backend / '.env')
settings = SimpleNamespace(**{**base.model_dump(), 'gateway_shared_secret': os.environ['GATEWAY_SHARED_SECRET']})
config.get_settings = lambda: settings
spec = importlib.util.spec_from_file_location('tested_backend', backend / 'app/main.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
from gateway_app.app import create_app
from gateway_app.config import Settings

user = dict(id=1, username='admin', full_name='Admin Test', role='ADMIN', status='ACTIVE', password_hash=module.DUMMY_HASH)

class Result:
    def __init__(self, rows): self.rows = rows
    def mappings(self): return self
    def first(self): return self.rows[0] if self.rows else None
    def all(self): return self.rows
    def one(self): return self.rows[0]

class Session:
    async def commit(self): pass
    async def rollback(self): pass
    async def execute(self, statement, params=None):
        sql = str(statement)
        assert sql.startswith('CALL '), 'Chỉ gọi stored procedure'
        if 'sp_get_user_for_login' in sql:
            return Result([dict(user)] if params['username'] == 'admin' else [])
        if 'sp_health' in sql: return Result([{'ok':1}])
        return Result([{k:v for k,v in user.items() if k != 'password_hash'}])

async def fake_session():
    yield Session()
module.app.dependency_overrides[module.get_session] = fake_session

# ASGITransport trả body đã buffer; adapter dùng stream cho proxy như HTTP thật.
class Stream(httpx.AsyncByteStream):
    def __init__(self, body): self.body = body
    async def __aiter__(self): yield self.body
class BackendTransport(httpx.AsyncBaseTransport):
    async def handle_async_request(self, request):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=module.app)) as client:
            response = await client.send(request)
            return httpx.Response(response.status_code, headers=response.headers, stream=Stream(response.content))

count=0
def check(response, status):
    global count
    assert response.status_code == status, (response.status_code, response.text)
    count += 1

with TestClient(module.app) as direct:
    check(direct.get('/health'), 403)
    check(direct.get('/users', headers={'x-gateway-key':'forged','x-user-role':'ADMIN'}), 403)

gateway = create_app(Settings(_env_file=None, jwt_secret_key=settings.jwt_secret_key, gateway_shared_secret=settings.gateway_shared_secret), BackendTransport())
with TestClient(gateway) as client:
    check(client.get('/health'),200)
    check(client.get('/users'),401)
    check(client.post('/auth/login',json={'username':'admin','password':'wrong'}),401)
    check(client.post('/auth/login',json={'username':'missing','password':'Test@123456'}),401)
    check(client.post('/auth/login',json={'username':'admin'}),422)
    response=client.post('/auth/login',json={'username':'admin','password':'Test@123456'})
    check(response,200)
    assert 'password_hash' not in response.text
    headers={'Authorization':'Bearer '+response.json()['access_token']}
    check(client.get('/auth/me',headers=headers),200)
    response=client.get('/users',headers=headers)
    check(response,200)
    assert 'password_hash' not in response.text
    user['role']='SALE'
    check(client.get('/users',headers=headers),403)
    user['status']='LOCKED'
    check(client.get('/auth/me',headers=headers),403)
    check(client.post('/auth/login',json={'username':'admin','password':'Test@123456'}),403)
print(f'{count} integration checks passed (DB mocked, real Argon2/JWT and Gateway → BE routing).')
