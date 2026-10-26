"""Chạy từ gốc repo: BE/.venv/bin/python BE/tests/check_fulfillment.py.
Tạo DB MySQL tạm, chạy API thật qua Gateway, không ghi vào DB ứng dụng.
Thêm --postman để chạy collection với hai server HTTP tạm.
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


async def run_postman():
    """Run local collection against real HTTP processes backed by the disposable DB."""
    import shutil
    import socket
    import subprocess
    import tempfile
    import time
    if not shutil.which('postman'):
        raise RuntimeError('Postman CLI chưa được cài')

    def free_port():
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            return sock.getsockname()[1]

    backend_port = free_port()
    gateway_port = free_port()
    while gateway_port == backend_port:
        gateway_port = free_port()
    env = {**os.environ, 'BACKEND_URL': f'http://127.0.0.1:{backend_port}'}
    processes = []
    with tempfile.TemporaryDirectory(prefix='orders-http-check-') as folder:
        logs = []
        cli = None
        try:
            for directory, module, port in [('BE','app.main:app',backend_port),('Gateway','gateway_app.main:app',gateway_port)]:
                log = open(Path(folder)/f'{directory}.log', 'w+')
                logs.append(log)
                processes.append(subprocess.Popen([sys.executable,'-m','uvicorn',module,'--host','127.0.0.1',
                    '--port',str(port),'--log-level','warning'], cwd=ROOT/directory, env=env, stdout=log, stderr=log))
            async with httpx.AsyncClient(timeout=1) as client:
                deadline = time.monotonic() + 20
                while True:
                    if any(process.poll() is not None for process in processes):
                        raise RuntimeError('HTTP test server không khởi động được')
                    try:
                        response = await client.get(f'http://127.0.0.1:{gateway_port}/health')
                        if response.status_code == 200:
                            break
                    except httpx.RequestError:
                        pass
                    if time.monotonic() > deadline:
                        raise RuntimeError('Timeout chờ HTTP test server')
                    await asyncio.sleep(0.1)
            cli = await asyncio.create_subprocess_exec('postman','collection','run',
                str(ROOT/'Gateway/postman/Logistics-Fulfillment.postman_collection.json'),
                '--env-var',f'base_url=http://127.0.0.1:{gateway_port}',
                '--env-var','admin_username=admin','--env-var','admin_password=Strong@123456',
                '--no-report-events', cwd=ROOT, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
            output, _ = await asyncio.wait_for(cli.communicate(), timeout=90)
            print(output.decode(errors='replace'))
            if cli.returncode:
                raise AssertionError(f'Postman CLI failed: {cli.returncode}')
        finally:
            if cli and cli.returncode is None:
                cli.kill()
                await cli.wait()
            for process in processes:
                process.terminate()
            for process in processes:
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            for log in logs:
                log.close()


async def main():
    url = make_url(dotenv_values(ROOT/'BE/.env')['DATABASE_URL'])
    name = 'cms_fulfillment_test_' + uuid.uuid4().hex
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
                for file in ('cms_logistics_procedures.sql', 'cms_logistics_customers.sql', 'cms_logistics_orders.sql', 'cms_logistics_fulfillment.sql'):
                    for stmt in statements(ROOT/'sql'/file):
                        await conn.exec_driver_sql(stmt)
            assert len((await conn.exec_driver_sql('SHOW TABLES')).all()) == 10
            from app.infrastructure.security.password import Argon2PasswordHasher
            hashed = await Argon2PasswordHasher().hash('Strong@123456')
            ids = {}
            for username, role in [('admin','ADMIN'),('sale_a','SALE'),('sale_b','SALE'),
                                   ('customer_a','CUSTOMER'),('customer_b','CUSTOMER'),('warehouse','WAREHOUSE'),('accountant','ACCOUNTANT')]:
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
                customer_body = dict(name='Khách A',phone='0912345678',address='Hà Nội')
                r=await check('POST','/customers',201,'admin',json={**customer_body,'user_id':ids['customer_a'],'sale_id':ids['sale_a']})
                ca=r.json()['id']
                r=await check('POST','/customers',201,'admin',json={**customer_body,'name':'Khách B','user_id':ids['customer_b'],'sale_id':ids['sale_b']})
                cb=r.json()['id']
                wh=dict(warehouse_code='cn_01',name='Kho Trung Quốc',address='Quảng Châu',country_code='CN')
                r=await check('POST','/warehouses',201,'admin',json=wh)
                cn=r.json()['id'];assert r.json()['warehouse_code']=='CN_01'
                r=await check('POST','/warehouses',201,'admin',json={**wh,'warehouse_code':'vn_01','name':'Kho VN','country_code':'VN'})
                vn=r.json()['id']
                await check('POST','/warehouses',409,'admin',json=wh)
                for who in ('warehouse','sale_a','customer_a','accountant'):
                    await check('POST','/warehouses',403,who,json={**wh,'warehouse_code':'DENIED'})
                    await check('PATCH',f'/warehouses/{cn}',403,who,json={'name':'Denied'})
                    await check('DELETE',f'/warehouses/{cn}',403,who)
                for field,value in [('country_code','US'),('warehouse_code','bad code'),('name',' '),('address','')]:
                    await check('POST','/warehouses',422,'admin',json={**wh,field:value})
                for patch in ({},{'name':None},{'is_active':None},{'country_code':'VN'}):
                    await check('PATCH',f'/warehouses/{cn}',422,'admin',json=patch)
                await check('PATCH',f'/warehouses/{cn}',200,'admin',json={'name':'Kho CN mới'})
                for who in ('admin','warehouse'):
                    r=await check('GET','/warehouses',200,who);assert len(r.json()['items'])==2
                    await check('GET',f'/warehouses/{cn}',200,who)
                for who in ('sale_a','customer_a','sale_b','customer_b'):
                    r=await check('GET','/warehouses',200,who);assert r.json()['items']==[]
                    await check('GET',f'/warehouses/{cn}',404,who)
                await check('GET','/warehouses',403,'accountant')
                order_body=dict(customer_id=ca,recipient_name='Người nhận',recipient_phone='0912345678',recipient_address='Hà Nội',
                    items=[{'name':'Áo','quantity':10},{'name':'Giày','quantity':4}])
                r=await check('POST','/orders',201,'admin',json=order_body)
                oid=r.json()['id'];shirt,shoe=[i['id'] for i in r.json()['items']]
                metrics=dict(weight_kg='2.500',length_cm='30.00',width_cm='20.00',height_cm='10.00')
                pkg=dict(order_id=oid,**metrics,items=[{'order_item_id':shirt,'quantity':6},{'order_item_id':shoe,'quantity':2}],note='Đóng kiện đầu')
                await check('POST','/packages',409,'warehouse',json=pkg)
                await check('PATCH',f'/orders/{oid}/status',200,'admin',json={'status':'CONFIRMED'})
                r=await check('POST','/orders',201,'admin',json={**order_body,'customer_id':cb})
                ob=r.json()['id'];other_item=r.json()['items'][0]['id']
                await check('PATCH',f'/orders/{ob}/status',200,'admin',json={'status':'CONFIRMED'})
                r=await check('POST','/packages',201,'warehouse',json={**pkg,'tracking_code':'test_pkg_a'})
                p1=r.json()['id'];assert r.json()['tracking_code']=='TEST_PKG_A' and r.json()['weight_kg']=='2.500'
                r=await check('POST','/packages',201,'admin',json={**pkg,'items':[{'order_item_id':shirt,'quantity':4},{'order_item_id':shoe,'quantity':2}]})
                p2=r.json()['id']
                r=await check('GET',f'/orders/{oid}',200,'warehouse')
                assert [(i['packed_quantity'],i['remaining_quantity']) for i in r.json()['items']]==[(10,0),(4,0)]
                await check('PATCH',f'/orders/{oid}',403,'warehouse',json={'note':'Denied'})
                await check('POST','/packages',409,'admin',json=pkg)
                await check('POST','/packages',409,'admin',json={**pkg,'tracking_code':'TEST_PKG_A'})
                await check('POST','/packages',422,'admin',json={**pkg,'items':[{'order_item_id':other_item,'quantity':1}]})
                for key,value in [('weight_kg','0'),('weight_kg','NaN'),('weight_kg','1.0001'),('length_cm','-1'),
                                  ('height_cm','100000000'),('unknown',1)]:
                    await check('POST','/packages',422,'admin',json={**pkg,key:value})
                for items in ([],[{'order_item_id':shirt,'quantity':0}],[{'order_item_id':shirt,'quantity':True}],
                              [{'order_item_id':shirt,'quantity':1.5}],[{'order_item_id':shirt,'quantity':'2'}],
                              [{'order_item_id':shirt,'quantity':1},{'order_item_id':shirt,'quantity':1}]):
                    await check('POST','/packages',422,'admin',json={**pkg,'items':items})
                for patch in ({},{'weight_kg':None},{'items':None},{'order_id':ob}, {'items':[]}):
                    await check('PATCH',f'/packages/{p1}',422,'admin',json=patch)
                await check('PATCH',f'/packages/{p1}',409,'warehouse',json={'items':[{'order_item_id':shirt,'quantity':7}]})
                r=await check('GET',f'/packages/{p1}',200,'admin');assert r.json()['items'][0]['quantity']==6
                r=await check('PATCH',f'/packages/{p1}',200,'warehouse',json={'weight_kg':'3.125','items':pkg['items']})
                assert r.json()['weight_kg']=='3.125'
                for who in ('admin','warehouse','sale_a','customer_a'):
                    await check('GET',f'/packages/{p1}',200,who)
                    r=await check('GET',f'/packages/{p1}/history',200,who)
                    assert len(r.json()['items'])==1 and r.json()['items'][0]['status']=='CREATED'
                    r=await check('GET',f'/packages?order_id={oid}',200,who);assert len(r.json()['items'])==2
                for who in ('sale_b','customer_b'):
                    await check('GET',f'/packages/{p1}',404,who)
                    await check('GET',f'/packages/{p1}/history',404,who)
                    r=await check('GET',f'/packages?order_id={oid}',200,who);assert r.json()['items']==[]
                for who in ('sale_a','customer_a','accountant'):
                    await check('POST','/packages',403,who,json=pkg)
                    await check('PATCH',f'/packages/{p1}',403,who,json={'weight_kg':'1'})
                    await check('PATCH',f'/packages/{p1}/status',403,who,json={'status':'CANCELLED'})
                await check('GET','/packages',403,'accountant')
                await check('GET',f'/packages/{p1}/history',403,'accountant')
                await check('GET','/packages',401)
                await check('GET','/warehouses',401)
                # Cancellation releases reserved quantities but retains contents/history.
                await check('PATCH',f'/packages/{p2}/status',200,'warehouse',json={'status':'CANCELLED','note':'Đóng lại kiện'})
                await check('PATCH',f'/packages/{p2}/status',200,'warehouse',json={'status':'CANCELLED'})
                r=await check('GET',f'/packages/{p2}/history',200,'admin');assert len(r.json()['items'])==2
                await check('PATCH',f'/packages/{p2}/status',409,'warehouse',json={'status':'CREATED'})
                await check('PATCH',f'/packages/{p2}',409,'warehouse',json={'weight_kg':'1'})
                r=await check('GET',f'/orders/{oid}',200,'warehouse');assert r.json()['items'][0]['remaining_quantity']==4
                remainder=[{'order_item_id':shirt,'quantity':4},{'order_item_id':shoe,'quantity':2}]
                r=await check('POST','/packages',201,'warehouse',json={**pkg,'items':remainder})
                p3=r.json()['id']
                await check('PATCH',f'/orders/{oid}/status',409,'admin',json={'status':'SHIPPING'})
                for status_body in [{'status':'IN_WAREHOUSE'}, {'status':'IN_TRANSIT','warehouse_id':cn}, {'status':'BAD'}]:
                    await check('PATCH',f'/packages/{p1}/status',422,'warehouse',json=status_body)
                await check('PATCH',f'/packages/{p1}/status',409,'warehouse',json={'status':'DELIVERED'})
                await check('DELETE',f'/warehouses/{vn}',204,'admin')
                await check('PATCH',f'/packages/{p3}/status',422,'warehouse',json={'status':'IN_WAREHOUSE','warehouse_id':vn})
                r=await check('GET',f'/packages/{p3}/history',200,'admin');assert len(r.json()['items'])==1
                await check('PATCH',f'/warehouses/{vn}',200,'admin',json={'is_active':True})
                await check('PATCH',f'/packages/{p1}/status',200,'warehouse',json={'status':'IN_WAREHOUSE','warehouse_id':cn,'note':'Nhập CN'})
                await check('PATCH',f'/packages/{p1}/status',200,'warehouse',json={'status':'IN_WAREHOUSE','warehouse_id':cn})
                await check('DELETE',f'/warehouses/{cn}',409,'admin')
                await check('PATCH',f'/warehouses/{cn}',409,'admin',json={'is_active':False})
                await check('PATCH',f'/packages/{p1}',409,'warehouse',json={'weight_kg':'1'})
                await check('PATCH',f'/packages/{p1}/status',409,'warehouse',json={'status':'IN_WAREHOUSE','warehouse_id':vn})
                r=await check('GET',f'/packages?warehouse_id={cn}&status=IN_WAREHOUSE',200,'warehouse');assert [p['id'] for p in r.json()['items']]==[p1]
                for who in ('sale_a','customer_a'):
                    await check('GET',f'/warehouses/{cn}',200,who)
                    r=await check('GET','/warehouses',200,who);assert [w['id'] for w in r.json()['items']]==[cn]
                await check('GET',f'/warehouses/{cn}',404,'customer_b')
                await check('PATCH',f'/packages/{p1}/status',200,'warehouse',json={'status':'IN_TRANSIT','note':'Xuất kho CN'})
                r=await check('GET',f'/packages/{p1}',200,'admin');assert r.json()['warehouse_id'] is None
                r=await check('GET',f'/orders/{oid}',200,'warehouse');assert r.json()['status']=='SHIPPING'
                await check('DELETE',f'/warehouses/{cn}',204,'admin')
                await check('PATCH',f'/packages/{p3}/status',422,'warehouse',json={'status':'IN_WAREHOUSE','warehouse_id':cn})
                await check('PATCH',f'/warehouses/{cn}',200,'admin',json={'is_active':True})
                await check('PATCH',f'/packages/{p1}/status',200,'warehouse',json={'status':'IN_WAREHOUSE','warehouse_id':vn})
                await check('PATCH',f'/packages/{p3}/status',200,'warehouse',json={'status':'IN_WAREHOUSE','warehouse_id':cn})
                await check('PATCH',f'/packages/{p1}/status',200,'warehouse',json={'status':'IN_TRANSIT'})
                await check('PATCH',f'/packages/{p1}/status',200,'warehouse',json={'status':'DELIVERED'})
                r=await check('GET',f'/orders/{oid}',200,'customer_a');assert r.json()['status']=='SHIPPING'
                await check('PATCH',f'/orders/{oid}/status',409,'admin',json={'status':'DELIVERED'})
                await check('PATCH',f'/packages/{p3}/status',200,'warehouse',json={'status':'IN_TRANSIT'})
                await check('PATCH',f'/packages/{p3}/status',409,'warehouse',json={'status':'CANCELLED'})
                await check('PATCH',f'/packages/{p3}/status',200,'warehouse',json={'status':'DELIVERED'})
                r=await check('GET',f'/orders/{oid}',200,'customer_a');assert r.json()['status']=='DELIVERED'
                r=await check('GET',f'/packages/{p1}/history',200,'customer_a')
                events=r.json()['items'];assert [e['status'] for e in events]==['CREATED','IN_WAREHOUSE','IN_TRANSIT','IN_WAREHOUSE','IN_TRANSIT','DELIVERED']
                assert events[2]['warehouse_id']==cn and events[3]['warehouse_id']==vn
                await check('PATCH',f'/packages/{p1}/status',200,'warehouse',json={'status':'DELIVERED'})
                await check('PATCH',f'/packages/{p1}/status',409,'warehouse',json={'status':'IN_TRANSIT'})
                r=await check('GET',f'/packages/{p1}/history?limit=2&offset=1',200,'customer_a');assert len(r.json()['items'])==2
                r=await check('GET','/warehouses',200,'customer_a');assert {w['id'] for w in r.json()['items']}=={cn,vn}
                # Reassignment updates scope on both packages and visited warehouses.
                await check('PATCH',f'/customers/{ca}',200,'admin',json={'sale_id':ids['sale_b']})
                await check('GET',f'/packages/{p1}',404,'sale_a')
                await check('GET',f'/packages/{p1}',200,'sale_b')
                await check('GET',f'/warehouses/{cn}',404,'sale_a')
                await check('GET',f'/warehouses/{cn}',200,'sale_b')
                # Partial shipment: delivered packages do not finish an order with unpacked items.
                r=await check('POST','/orders',201,'admin',json={**order_body,'items':[{'name':'Hàng chia đợt','quantity':2}]})
                partial=r.json()['id'];partial_item=r.json()['items'][0]['id']
                await check('PATCH',f'/orders/{partial}/status',200,'admin',json={'status':'CONFIRMED'})
                for index in range(2):
                    r=await check('POST','/packages',201,'warehouse',json={**metrics,'order_id':partial,'items':[{'order_item_id':partial_item,'quantity':1}]})
                    pid=r.json()['id']
                    for status_body in [{'status':'IN_WAREHOUSE','warehouse_id':cn},{'status':'IN_TRANSIT'},{'status':'DELIVERED'}]:
                        await check('PATCH',f'/packages/{pid}/status',200,'warehouse',json=status_body)
                    r=await check('GET',f'/orders/{partial}',200,'admin');assert r.json()['status']==('SHIPPING' if index==0 else 'DELIVERED')
                # Two operators try to reserve the same last item: only one succeeds.
                r=await check('POST','/orders',201,'admin',json={**order_body,'items':[{'name':'Hàng cuối','quantity':1}]})
                race=r.json()['id'];race_item=r.json()['items'][0]['id']
                await check('PATCH',f'/orders/{race}/status',200,'admin',json={'status':'CONFIRMED'})
                race_body={**metrics,'order_id':race,'items':[{'order_item_id':race_item,'quantity':1}]}
                responses=await asyncio.gather(*[client.post('/packages',headers=tokens[who],json=race_body) for who in ('admin','warehouse')])
                assert sorted(r.status_code for r in responses)==[201,409],[(r.status_code,r.text) for r in responses]
                count+=2
                r=await check('GET',f'/packages?order_id={race}',200,'admin');assert len(r.json()['items'])==1
                race_pkg=r.json()['items'][0]['id']
                # Closing an empty warehouse races with receiving a package: cannot leave stock in an inactive warehouse.
                r=await check('POST','/warehouses',201,'admin',json={**wh,'warehouse_code':'RACE_CLOSING'})
                close_warehouse=r.json()['id']
                arrival,closing=await asyncio.gather(
                    client.patch(f'/packages/{race_pkg}/status',headers=tokens['warehouse'],json={'status':'IN_WAREHOUSE','warehouse_id':close_warehouse}),
                    client.delete(f'/warehouses/{close_warehouse}',headers=tokens['admin']))
                assert (arrival.status_code,closing.status_code) in ((200,409),(422,204)),(arrival.text,closing.text)
                count+=2
                r=await check('GET',f'/warehouses/{close_warehouse}',200,'admin')
                assert r.json()['is_active']==(arrival.status_code==200)
                # Order cancellation and first packing share the same parent lock.
                r=await check('POST','/orders',201,'admin',json={**order_body,'items':[{'name':'Race cancel','quantity':1}]})
                race_order=r.json()['id'];race_order_item=r.json()['items'][0]['id']
                await check('PATCH',f'/orders/{race_order}/status',200,'admin',json={'status':'CONFIRMED'})
                packing,cancel=await asyncio.gather(
                    client.post('/packages',headers=tokens['warehouse'],json={**metrics,'order_id':race_order,'items':[{'order_item_id':race_order_item,'quantity':1}]}),
                    client.patch(f'/orders/{race_order}/status',headers=tokens['admin'],json={'status':'CANCELLED'}))
                assert (packing.status_code,cancel.status_code) in ((201,409),(409,200)),(packing.text,cancel.text)
                count+=2
                # HTTP-triggered late SQL failure rolls back all package/detail/history inserts.
                r=await check('POST','/orders',201,'admin',json={**order_body,'items':[{'name':'Rollback','quantity':3}]})
                rollback_order=r.json()['id'];rollback_item=r.json()['items'][0]['id']
                await check('PATCH',f'/orders/{rollback_order}/status',200,'admin',json={'status':'CONFIRMED'})
                rollback_body={**metrics,'order_id':rollback_order,'items':[{'order_item_id':rollback_item,'quantity':1}]}
                await check('POST','/packages',422,'warehouse',json={**rollback_body,'items':rollback_body['items']+[{'order_item_id':other_item,'quantity':1}]})
                r=await check('GET',f'/packages?order_id={rollback_order}',200,'admin');assert r.json()['items']==[]
                r=await check('POST','/packages',201,'warehouse',json=rollback_body);rollback_pkg=r.json()['id']
                await check('PATCH',f'/packages/{rollback_pkg}',422,'warehouse',json={'items':rollback_body['items']+[{'order_item_id':other_item,'quantity':1}]})
                r=await check('GET',f'/packages/{rollback_pkg}',200,'admin');assert len(r.json()['items'])==1 and r.json()['items'][0]['order_item_id']==rollback_item
                # Invalid/missing paths and pagination.
                for path in ['/warehouses/0','/warehouses?limit=0','/packages?status=BAD','/packages?order_id=0',f'/packages/{p1}/history?limit=0']:
                    await check('GET',path,422,'admin')
                for path in ['/warehouses/999999','/packages/999999','/packages/999999/history']:
                    await check('GET',path,404,'admin')
                await check('PATCH','/packages/999999/status',404,'warehouse',json={'status':'CANCELLED'})
                await check('POST','/packages',404,'warehouse',json={**pkg,'order_id':999999})
                # SQL layer must reject writes even if HTTP dependencies are bypassed.
                from sqlalchemy.exc import DBAPIError
                async with db.connect() as conn:
                    for statement,params in [("CALL sp_update_warehouse(:actor,:id,'{\"name\":\"Denied\"}')",{'actor':ids['warehouse'],'id':cn}),
                        ("CALL sp_create_package(:actor,:order,'DENIED','{}','[]',NULL)",{'actor':ids['sale_a'],'order':oid})]:
                        try:
                            await conn.execute(text(statement),params)
                            raise AssertionError('SQL authorization bypass')
                        except DBAPIError as exc:
                            assert exc.orig.args[0]==1644 and exc.orig.args[1]=='FORBIDDEN'
                            await conn.rollback()
                async with db.begin() as conn:
                    await conn.execute(text("UPDATE nguoi_dung SET vai_tro='CUSTOMER' WHERE ma=:id"),{'id':ids['warehouse']})
                await check('POST','/packages',403,'warehouse',json=rollback_body)
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=backend),base_url='http://backend') as direct:
                    assert (await direct.get('/packages',headers=tokens['admin'])).status_code==403
                print(f'PASS: {count} HTTP checks; MySQL packing capacity, concurrency, atomic history, warehouse scope and order sync; 10 tables.')
        if '--postman' in sys.argv:
            await run_postman()
    finally:
        if backend_engine is not None:
            await backend_engine.dispose()
        await db.dispose()
        if created:
            assert name.startswith('cms_fulfillment_test_') and len(name) == len('cms_fulfillment_test_') + 32
            async with admin.begin() as conn:
                await conn.exec_driver_sql(f'DROP DATABASE `{name}`')
        await admin.dispose()


if __name__ == '__main__':
    asyncio.run(main())
