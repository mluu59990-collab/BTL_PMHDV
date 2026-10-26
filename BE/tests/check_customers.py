"""Chạy từ gốc repo: BE/.venv/bin/python BE/tests/check_customers.py.
Tạo DB MySQL tạm, chạy API thật qua Gateway, không ghi vào DB ứng dụng.
"""
import asyncio
import os
from pathlib import Path
import sys
import uuid

import httpx
from dotenv import dotenv_values
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'BE'), str(ROOT/'Gateway')]


def statements(path):
    delimiter, buffer = ';', ''
    for line in path.read_text().splitlines():
        if line.strip().upper().startswith('DELIMITER '):
            delimiter = line.strip().split()[1]
            continue
        if not line.strip() or line.lstrip().startswith('--'):
            continue
        buffer += line + '\n'
        if buffer.rstrip().endswith(delimiter):
            statement = buffer.rstrip()[:-len(delimiter)].strip()
            buffer = ''
            if not statement.upper().startswith('USE '):
                yield statement
    if buffer.strip():
        raise ValueError(f'SQL chưa kết thúc: {path}')


async def main():
    url = make_url(dotenv_values(ROOT/'BE/.env')['DATABASE_URL'])
    name = 'cms_customer_test_' + uuid.uuid4().hex
    admin = create_async_engine(url)
    db = create_async_engine(url.set(database=name))
    backend_engine = None
    created = False
    count = 0
    try:
        async with admin.begin() as conn:
            await conn.exec_driver_sql(f'CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
            created = True
        os.environ.update(DATABASE_URL=url.set(database=name).render_as_string(hide_password=False),
                          DEBUG='false', JWT_SECRET_KEY='customer-test-jwt-'*4,
                          GATEWAY_SHARED_SECRET='customer-test-gateway-'*4)
        async with db.begin() as conn:
            await conn.exec_driver_sql('SET sql_notes=0')
            for stmt in statements(ROOT/'sql/cms_logistics_schema.sql'):
                await conn.exec_driver_sql(stmt)
            for _ in range(2):
                for file in ('cms_logistics_procedures.sql', 'cms_logistics_customers.sql'):
                    for stmt in statements(ROOT/'sql'/file):
                        await conn.exec_driver_sql(stmt)
            assert len((await conn.exec_driver_sql('SHOW TABLES')).all()) == 10
            from app.infrastructure.security.password import Argon2PasswordHasher
            hashed = await Argon2PasswordHasher().hash('Strong@123456')
            ids = {}
            for username, role in [('admin','ADMIN'),('sale_a','SALE'),('sale_b','SALE'),
                                   ('customer_a','CUSTOMER'),('customer_b','CUSTOMER'),('warehouse','WAREHOUSE')]:
                result = await conn.execute(text('INSERT INTO nguoi_dung(ten_dang_nhap,ho_ten,mat_khau_bam,vai_tro) VALUES(:name,:name,:hash,:role)'),
                                            dict(name=username, hash=hashed, role=role))
                ids[username] = result.lastrowid
        from app.main import app as backend
        from app.infrastructure.db.session import engine as backend_engine
        from gateway_app.app import create_app
        from gateway_app.config import Settings

        class Stream(httpx.AsyncByteStream):
            def __init__(self, body): self.body = body
            async def __aiter__(self): yield self.body

        class BackendTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=backend)) as client:
                    response = await client.send(request)
                    return httpx.Response(response.status_code, headers=response.headers,
                                          stream=Stream(response.content))

        gateway = create_app(Settings(_env_file=None), BackendTransport())
        async with gateway.router.lifespan_context(gateway):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=gateway), base_url='http://gateway') as client:
                async def check(method, path, expected, who=None, **kwargs):
                    nonlocal count
                    if who:
                        kwargs['headers'] = tokens[who]
                    response = await client.request(method, path, **kwargs)
                    assert response.status_code == expected, (method, path, response.status_code, response.text)
                    count += 1
                    return response

                tokens = {}
                for username in ids:
                    r = await check('POST','/auth/login',200,json={'username':username,'password':'Strong@123456'})
                    tokens[username] = {'Authorization':'Bearer '+r.json()['access_token']}
                await check('GET','/health',200)
                await check('GET','/customers',401)
                body = dict(name='Khách A', phone='0912345678', address='Hà Nội', email='a@example.com')
                r = await check('POST','/customers',201,'admin',json={**body,'user_id':ids['customer_a'],'sale_id':ids['sale_a']})
                first = r.json()['id']
                assert r.json()['user_id'] == ids['customer_a'] and r.json()['is_active'] is True
                r = await check('POST','/customers',201,'sale_b',json={**body,'name':'Khách B'})
                second = r.json()['id']
                assert r.json()['sale_id'] == ids['sale_b']
                await check('PATCH',f'/customers/{second}',200,'admin',json={'user_id':ids['customer_b']})
                for who in ('admin','sale_a','customer_a'):
                    await check('GET',f'/customers/{first}',200,who)
                for who in ('sale_b','customer_b'):
                    await check('GET',f'/customers/{first}',404,who)
                for who, expected_ids in [('admin',{first,second}),('sale_a',{first}),('sale_b',{second}),('customer_a',{first}),('customer_b',{second})]:
                    r = await check('GET','/customers?active_only=false',200,who)
                    assert {i['id'] for i in r.json()['items']} == expected_ids
                for method,path,kwargs in [('POST','/customers',{'json':body}),('PATCH',f'/customers/{first}',{'json':{'name':'Forbidden'}}),('DELETE',f'/customers/{first}',{})]:
                    await check(method,path,403,'customer_a',**kwargs)
                for method,path,kwargs in [('GET','/customers',{}),('GET',f'/customers/{first}',{}),('POST','/customers',{'json':body}),('PATCH',f'/customers/{first}',{'json':{'name':'Forbidden'}}),('DELETE',f'/customers/{first}',{})]:
                    await check(method,path,403,'warehouse',**kwargs)
                await check('PATCH',f'/customers/{first}',404,'sale_b',json={'name':'Forbidden'})
                await check('DELETE',f'/customers/{first}',404,'sale_b')
                await check('PATCH',f'/customers/{first}',200,'sale_a',json={'name':'Khách sửa','phone':'+84912345678'})
                for key,value in [('sale_id',ids['sale_b']),('sale_id',None),('user_id',None),('is_active',False)]:
                    await check('PATCH',f'/customers/{first}',403,'sale_a',json={key:value})
                for key,value in [('sale_id',ids['sale_a']),('user_id',None)]:
                    await check('POST','/customers',403,'sale_a',json={**body,key:value})
                for patch in [{},{'name':None},{'phone':None},{'address':None},{'is_active':None},
                              {'name':'  '},{'address':'  '},{'phone':'abc'},{'email':'bad'},
                              {'unknown':'x'},{'sale_id':0},{'user_id':-1}]:
                    await check('PATCH',f'/customers/{first}',422,'admin',json=patch)
                for key,value in [('sale_id',ids['customer_b']),('sale_id',99999),('user_id',ids['sale_b']),('user_id',99999)]:
                    await check('POST','/customers',422,'admin',json={**body,key:value})
                    await check('PATCH',f'/customers/{first}',422,'admin',json={key:value})
                await check('POST','/customers',409,'admin',json={**body,'user_id':ids['customer_a']})
                await check('PATCH',f'/customers/{second}',409,'admin',json={'user_id':ids['customer_a']})
                await check('PATCH',f'/customers/{first}',200,'admin',json={'email':None,'sale_id':ids['sale_b']})
                await check('GET',f'/customers/{first}',404,'sale_a')
                await check('PATCH',f'/customers/{first}',404,'sale_a',json={'name':'Forbidden'})
                await check('GET',f'/customers/{first}',200,'sale_b')
                await check('DELETE',f'/customers/{first}',204,'sale_b')
                await check('DELETE',f'/customers/{first}',204,'sale_b')
                await check('GET',f'/customers/{first}',404,'customer_a')
                r = await check('GET','/customers?active_only=false',200,'customer_a')
                assert r.json()['items'] == []
                r = await check('GET','/customers',200,'admin')
                assert {i['id'] for i in r.json()['items']} == {second}
                r = await check('GET','/customers?active_only=false',200,'admin')
                assert len(r.json()['items']) == 2
                await check('PATCH',f'/customers/{first}',200,'admin',json={'is_active':True})
                await check('GET',f'/customers/{first}',200,'customer_a')
                await check('PATCH',f'/customers/{first}',200,'admin',json={'user_id':None,'sale_id':None})
                await check('GET',f'/customers/{first}',404,'customer_a')
                await check('GET',f'/customers/{first}',404,'sale_b')
                await check('GET','/customers/999999',404,'admin')
                await check('PATCH','/customers/999999',404,'admin',json={'name':'Missing'})
                await check('DELETE','/customers/999999',404,'admin')
                for path in ['/customers/0','/customers?limit=0','/customers?offset=-1']:
                    await check('GET',path,422,'admin')
                r = await check('GET','/customers?search=Khách&limit=1&offset=1',200,'admin')
                assert len(r.json()['items']) == 1
                r = await check('GET','/customers?search=not-found',200,'admin')
                assert r.json()['items'] == []
                # A JWT issued before a role change must not retain write access.
                async with db.begin() as conn:
                    await conn.execute(text("UPDATE nguoi_dung SET vai_tro='CUSTOMER' WHERE ma=:id"),{'id':ids['sale_b']})
                await check('POST','/customers',403,'sale_b',json=body)
                await check('GET','/customers',200,'sale_b')
                r = await check('GET','/auth/permissions',200,'customer_a')
                assert 'customers:read:own' in r.json()['permissions']
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=backend),base_url='http://backend') as direct:
                    assert (await direct.get('/customers',headers=tokens['admin'])).status_code == 403
                # Verify SQL itself rejects unauthorized writes, not only HTTP dependencies.
                from sqlalchemy.exc import DBAPIError
                async with db.connect() as conn:
                    try:
                        await conn.execute(text('CALL sp_deactivate_customer(:actor,:id)'),{'actor':ids['customer_a'],'id':first})
                        raise AssertionError('CUSTOMER write was allowed by SQL')
                    except DBAPIError as exc:
                        assert exc.orig.args[0] == 1644 and exc.orig.args[1] == 'FORBIDDEN'
                        await conn.rollback()
                print(f'PASS: {count} HTTP checks; Gateway → BE → MySQL, scope/validation/soft-delete, SQL defense; 10 tables.')
    finally:
        if backend_engine is not None:
            await backend_engine.dispose()
        await db.dispose()
        if created:
            assert name.startswith('cms_customer_test_') and len(name) == len('cms_customer_test_') + 32
            async with admin.begin() as conn:
                await conn.exec_driver_sql(f'DROP DATABASE `{name}`')
        await admin.dispose()


if __name__ == '__main__':
    asyncio.run(main())
