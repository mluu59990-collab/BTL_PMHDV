"""Kiểm thử API qua Gateway + MySQL tạm, không ghi dữ liệu vào DB ứng dụng.
Chạy bằng Python của BE: python checks/run_features.py --env /path/BE/.env
"""
import argparse
import asyncio
import os
from pathlib import Path
import re
import sys
import uuid

import httpx
from dotenv import dotenv_values
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'BE'), str(ROOT/'Gateway')]


def sql_statements(path):
    delimiter=';'
    buffer=''
    for line in path.read_text().splitlines():
        if line.strip().upper().startswith('DELIMITER '):
            delimiter=line.strip().split()[1]
            continue
        if line.lstrip().startswith('--') or not line.strip(): continue
        buffer += line+'\n'
        if buffer.rstrip().endswith(delimiter):
            statement=buffer.rstrip()[:-len(delimiter)].strip()
            buffer=''
            if statement and not statement.upper().startswith('USE '): yield statement
    if buffer.strip(): raise ValueError(f'SQL chưa kết thúc: {path}')


async def main(env):
    values=dotenv_values(env)
    db_name='cms_feature_test_'+uuid.uuid4().hex
    url=make_url(values['DATABASE_URL'])
    admin=create_async_engine(url,connect_args={'init_command':"SET time_zone = '+00:00'"})
    async with admin.begin() as conn:
        await conn.execute(text(f'CREATE DATABASE `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'))
    test_url=url.set(database=db_name).render_as_string(hide_password=False)
    os.environ.update(DATABASE_URL=test_url,DEBUG='false',JWT_SECRET_KEY='feature-test-jwt-'*4,
                      GATEWAY_SHARED_SECRET='feature-test-gateway-'*4)
    db=create_async_engine(test_url,connect_args={'init_command':"SET time_zone = '+00:00'"})
    backend_engine=None
    try:
        async with db.begin() as conn:
            source=(ROOT/'sql/my_db_logistic.sql').read_text()
            for statement in re.findall(r'CREATE TABLE IF NOT EXISTS.*?;',source,re.S):
                await conn.exec_driver_sql(statement)
            seed=re.search(r'INSERT INTO users .*?;',source,re.S).group()
            await conn.exec_driver_sql(seed)
            for path in sorted((ROOT/'sql').glob('[0-9][0-9]_*.sql')):
                for statement in sql_statements(path): await conn.exec_driver_sql(statement)
        from app.main import app as backend
        from app.infrastructure.db.session import engine as backend_engine
        from gateway_app.app import create_app
        from gateway_app.config import Settings

        class Stream(httpx.AsyncByteStream):
            def __init__(self,body): self.body=body
            async def __aiter__(self): yield self.body
        class BackendTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(self,request):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=backend)) as client:
                    response=await client.send(request)
                    return httpx.Response(response.status_code,headers=response.headers,stream=Stream(response.content))
        gateway=create_app(Settings(_env_file=None),BackendTransport())
        count=0
        async with gateway.router.lifespan_context(gateway):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=gateway),base_url='http://gateway') as client:
                async def check(method,path,status,**kwargs):
                    nonlocal count
                    response=await client.request(method,path,**kwargs)
                    assert response.status_code==status, f'{method} {path}: {response.status_code}, expected {status}: {response.text[:200]}'
                    count+=1
                    return response
                await check('GET','/health',200)
                await check('GET','/users',401)
                body=dict(username='new_customer',password='Strong@123456',full_name='Khách hàng mới',email='new@example.com')
                response=await check('POST','/auth/register',201,json=body)
                assert response.json()['role']=='CUSTOMER' and 'password' not in response.text
                customer_id=response.json()['id']
                await check('POST','/auth/register',409,json=body)
                await check('POST','/auth/register',409,json={**body,'username':'another_customer'})
                await check('POST','/auth/register',422,json={**body,'username':'badrole','role':'ADMIN'})
                await check('POST','/auth/register',422,json={**body,'password':'123'})
                await check('POST','/auth/register',422,json={**body,'full_name':'   '})
                await check('POST','/auth/login',401,json={'username':'admin','password':'wrong'})
                response=await check('POST','/auth/login',200,json={'username':body['username'],'password':body['password']})
                customer_tokens=response.json()
                customer_headers={'Authorization':'Bearer '+customer_tokens['access_token']}
                await check('GET','/users',403,headers=customer_headers)
                response=await check('POST','/auth/login',200,json={'username':'admin','password':'Admin@123456'})
                admin_tokens=response.json()
                admin_headers={'Authorization':'Bearer '+admin_tokens['access_token']}
                await check('GET','/users',200,headers=admin_headers)
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=backend),base_url='http://backend') as direct:
                    assert (await direct.get('/users',headers=admin_headers)).status_code==403
                # Rotation, rejeu, logout et séparation access/refresh.
                response=await check('POST','/auth/refresh',200,json={'refresh_token':customer_tokens['refresh_token']})
                rotated=response.json()
                assert rotated['refresh_token'] != customer_tokens['refresh_token']
                await check('POST','/auth/refresh',401,json={'refresh_token':customer_tokens['refresh_token']})
                await check('POST','/auth/refresh',401,json={'refresh_token':customer_tokens['access_token']})
                await check('GET','/users',401,headers={'Authorization':'Bearer '+rotated['refresh_token']})
                await check('POST','/auth/refresh',401,json={'refresh_token':'invalid'})
                await check('POST','/auth/logout',204,json={'refresh_token':rotated['refresh_token']})
                await check('POST','/auth/logout',204,json={'refresh_token':rotated['refresh_token']})
                await check('POST','/auth/refresh',401,json={'refresh_token':rotated['refresh_token']})
                # Deux refresh concurrents: un seul gagne, transaction atomique.
                responses=await asyncio.gather(*[client.post('/auth/refresh',json={'refresh_token':admin_tokens['refresh_token']}) for _ in range(2)])
                assert sorted(r.status_code for r in responses)==[200,401]
                count+=2
                admin_tokens=next(r.json() for r in responses if r.status_code==200)
                admin_headers={'Authorization':'Bearer '+admin_tokens['access_token']}
                async with db.begin() as conn:
                    await conn.execute(text("UPDATE users SET status='LOCKED' WHERE id=:id"),{'id':customer_id})
                await check('GET','/auth/me',403,headers=customer_headers)
                await check('POST','/auth/login',403,json={'username':body['username'],'password':body['password']})
                async with db.begin() as conn:
                    await conn.execute(text("UPDATE users SET status='ACTIVE' WHERE id=:id"),{'id':customer_id})
                # FEATURE_CHECKS: Các kiểm thử chức năng tiếp theo được bổ sung tại đây.
        print(f'PASS: {count} HTTP checks qua Gateway + MySQL thật; chặn gọi trực tiếp BE.')
    finally:
        if backend_engine: await backend_engine.dispose()
        await db.dispose()
        async with admin.begin() as conn:
            assert re.fullmatch(r'cms_feature_test_[0-9a-f]{32}',db_name)
            await conn.execute(text(f'DROP DATABASE `{db_name}`'))
        await admin.dispose()

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--env',required=True,type=Path)
    args=parser.parse_args()
    asyncio.run(main(args.env))
