import json
import time

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient

from gateway_app.app import create_app
from gateway_app.config import Settings

SECRET = 'test-jwt-secret-' * 4
KEY = 'test-internal-key-' * 4


def token(**changes):
    data = dict(sub='1', role='ADMIN', type='access', jti='test', iat=int(time.time()), exp=int(time.time()) + 300)
    data.update(changes)
    return jwt.encode(data, SECRET, algorithm='HS256')


class Body(httpx.AsyncByteStream):
    async def __aiter__(self):
        yield b'{"ok":true}'


def upstream_response(status=200, headers=None):
    return httpx.Response(status, stream=Body(), headers=headers or {'content-type': 'application/json'})


def client_for(handler, **kwargs):
    settings = Settings(_env_file=None, jwt_secret_key=SECRET, gateway_shared_secret=KEY, **kwargs)
    return TestClient(create_app(settings, httpx.MockTransport(handler)))


@pytest.mark.parametrize('path,method', [('/users','GET'),('/new-api','POST'),('/auth/login','GET'),('/health','POST'),('/auth/login/','POST')])
def test_default_deny(path, method):
    with client_for(lambda req: pytest.fail('Không được gọi upstream')) as client:
        assert client.request(method, path).status_code == 401


@pytest.mark.parametrize('bad', ['garbage', token(exp=1), token(type='refresh'), token(sub='abc'), token(role='ROOT'), jwt.encode(dict(sub='1',exp=9999999999), 'wrong'*10, algorithm='HS256')])
def test_invalid_tokens(bad):
    with client_for(lambda req: pytest.fail('Không được gọi upstream')) as client:
        assert client.get('/users', headers={'Authorization': 'Bearer ' + bad}).status_code == 401


def test_forwarding_and_spoofed_headers():
    captured = []
    def handler(req):
        captured.append(req)
        return upstream_response(201, [('content-type','application/json'), ('set-cookie','a=1'), ('set-cookie','b=2'), ('connection','x-remove'), ('x-remove','secret')])
    with client_for(handler) as client:
        response = client.post('/orders?tag=a&tag=b', content=b'{"name":"test"}', headers={
            'Authorization': 'Bearer ' + token(), 'Content-Type':'application/json',
            'X-Gateway-Key':'fake', 'X-User-Role':'ADMIN', 'X-Forwarded-For':'fake'})
    req = captured[0]
    assert req.url.host == '127.0.0.1' and req.url.port == 8001
    assert str(req.url).endswith('/orders?tag=a&tag=b')
    assert req.content == b'{"name":"test"}' and req.method == 'POST'
    assert req.headers['x-gateway-key'] == KEY
    assert 'x-user-role' not in req.headers and 'x-forwarded-for' not in req.headers
    assert response.status_code == 201 and response.json() == {'ok':True}
    assert response.headers.get_list('set-cookie') == ['a=1','b=2']
    assert 'x-remove' not in response.headers


@pytest.mark.parametrize('path,method', [('/auth/login','POST'),('/auth/register','POST'),('/auth/refresh','POST'),('/auth/logout','POST'),('/health','GET')])
def test_public(path, method):
    with client_for(lambda req: upstream_response()) as client:
        assert client.request(method, path).status_code == 200


def test_own_health():
    with client_for(lambda req: pytest.fail('Không cần BE')) as client:
        assert client.get('/gateway/health').json()['service'] == 'gateway'


@pytest.mark.parametrize('error,status', [(httpx.ConnectError('down'),502),(httpx.ReadTimeout('slow'),504)])
def test_backend_failure(error,status):
    def handler(req):
        raise error
    with client_for(handler) as client:
        assert client.get('/health').status_code == status


def test_body_limit():
    with client_for(lambda req: pytest.fail('Không được gọi upstream'), max_body_bytes=4) as client:
        assert client.post('/auth/login', content=b'12345').status_code == 413


def test_backend_redirect_not_followed():
    calls=[]
    def handler(req):
        calls.append(req)
        return upstream_response(307, {'location':'http://example.com'})
    with client_for(handler) as client:
        assert client.get('/health', follow_redirects=False).status_code == 307
    assert len(calls) == 1


def test_missing_claims():
    t = jwt.encode({'sub':'1','exp':int(time.time())+60}, SECRET, algorithm='HS256')
    with client_for(lambda req: pytest.fail('Không được gọi upstream')) as client:
        assert client.get('/users', headers={'Authorization':'Bearer '+t}).status_code == 401


def test_duplicate_auth():
    with client_for(lambda req: pytest.fail('Không được gọi upstream')) as client:
        assert client.get('/users', headers=[('authorization','Bearer '+token()), ('authorization','Bearer '+token())]).status_code == 401
