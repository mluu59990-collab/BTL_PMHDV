"""Tạo collection Buổi 1 chạy tuần tự, tự lấy token và ID từ response."""
import json
from pathlib import Path

items=[]
def add(name,method,path,status,body=None,auth=False,save=None,base='{{base_url}}',token='{{access_token}}'):
    request={'method':method,'url':base+path,'header':[], 'auth':{'type':'noauth'}}
    if auth: request['auth']={'type':'bearer','bearer':[{'key':'token','value':token,'type':'string'}]}
    if body is not None:
        request['header']=[{'key':'Content-Type','value':'application/json'}]
        request['body']={'mode':'raw','raw':json.dumps(body,ensure_ascii=False,indent=2),'options':{'raw':{'language':'json'}}}
    script=[f'pm.test("HTTP {status}", () => pm.response.to.have.status({status}));']
    if save:
        script.append(f'if (pm.response.code === {status}) {{ const d = pm.response.json();')
        for variable,field in save.items(): script.append(f'pm.collectionVariables.set("{variable}", d.{field});')
        script.append('}')
    items.append({'name':name,'request':request,'event':[{'listen':'test','script':{'type':'text/javascript','exec':script}}]})

def login(username,password,name):
    add(name,'POST','/auth/login',200,{'username':username,'password':password},save={'access_token':'access_token','refresh_token':'refresh_token'})

add('01 Gateway hoạt động','GET','/gateway/health',200)
add('02 Backend và DB hoạt động','GET','/health',200)
add('03 Từ chối thiếu token','GET','/users',401)
add('04 Từ chối gọi thẳng BE','GET','/users',403,base='{{backend_url}}')
add('05 Đăng ký khách mới','POST','/auth/register',201,{'username':'khach_{{$guid}}','password':'Strong@123456','full_name':'Khách kiểm thử'},save={'user_id':'id'})
add('06 Chặn tự chọn ADMIN khi đăng ký','POST','/auth/register',422,{'username':'khach_{{$guid}}','password':'Strong@123456','full_name':'Khách','role':'ADMIN'})
add('07 Sai mật khẩu','POST','/auth/login',401,{'username':'admin','password':'wrong-password'})
login('admin','{{admin_password}}','08 Đăng nhập ADMIN')
add('09 Thông tin hiện tại','GET','/auth/me',200,auth=True)
add('10 Quyền hiện tại','GET','/auth/permissions',200,auth=True)
add('11 Danh sách người dùng','GET','/users?limit=10&offset=0',200,auth=True)
add('12 ADMIN phân quyền khách vừa tạo','PATCH','/users/{{user_id}}/access',200,{'role':'SALE'},auth=True)
add('13 Cập nhật tỷ giá NDT','POST','/exchange-rates',201,{'currency_code':'NDT','rate':'3920.1234'},auth=True)
add('14 Cập nhật tỷ giá USD','POST','/exchange-rates',201,{'currency_code':'USD','rate':'26500'},auth=True)
add('15 Tỷ giá hiện hành','GET','/exchange-rates/current',200,auth=True)
add('16 Lịch sử tỷ giá CNY','GET','/exchange-rates/history?currency_code=CNY',200,auth=True)
add('17 Chặn tỷ giá âm','POST','/exchange-rates',422,{'currency_code':'USD','rate':'-1'},auth=True)
fees={'fee_type':'INTERNATIONAL_SHIPPING','unit':'VND_PER_KG','effective_date':'2026-01-01','tiers':[{'tier_min':'0','tier_max':'10','value':'30000'},{'tier_min':'10','tier_max':None,'value':'25000'}]}
add('18 Tạo bảng phí vận chuyển','POST','/fee-configs',201,fees,auth=True,save={'fee_id':'id'})
add('19 Chi tiết bảng phí','GET','/fee-configs/{{fee_id}}',200,auth=True)
add('20 Bảng phí hiện hành','GET','/fee-configs/current?fee_type=INTERNATIONAL_SHIPPING',200,auth=True)
add('21 Chặn bậc phí chồng lấn','POST','/fee-configs',422,{**fees,'tiers':[{'tier_min':'0','tier_max':'10','value':'1'},{'tier_min':'9','value':'1'}]},auth=True)
add('22 Sửa mô tả bảng phí','PATCH','/fee-configs/{{fee_id}}',200,{'description':'Bảng phí test Postman'},auth=True)
add('23 Xóa mềm bảng phí vừa tạo','DELETE','/fee-configs/{{fee_id}}',204,auth=True)
add('24 Lịch sử bảng phí','GET','/fee-configs?active_only=false',200,auth=True)
add('25 Refresh token','POST','/auth/refresh',200,{'refresh_token':'{{refresh_token}}'},save={'access_token':'access_token','refresh_token':'refresh_token'})
add('26 Đăng xuất','POST','/auth/logout',204,{'refresh_token':'{{refresh_token}}'})
add('27 Không dùng lại refresh đã đăng xuất','POST','/auth/refresh',401,{'refresh_token':'{{refresh_token}}'})
for username,label in [('sale01','Sale'),('kho01','Kho'),('ketoan01','Kế toán'),('khach01','Khách hàng')]:
    login(username,'{{staff_password}}',f'Đăng nhập {label}')
    add(f'{label} được đọc tỷ giá','GET','/exchange-rates/current',200,auth=True)
    add(f'{label} không được cập nhật tỷ giá','POST','/exchange-rates',403,{'currency_code':'CNY','rate':'1'},auth=True)
    add(f'{label} không được xem users','GET','/users',403,auth=True)
    add(f'Đăng xuất {label}','POST','/auth/logout',204,{'refresh_token':'{{refresh_token}}'})
collection={'info':{'name':'Logistics Gateway — Buổi 1','schema':'https://schema.getpostman.com/json/collection/v2.1.0/collection.json','description':'Chạy 1 iteration trên DB dev. Tạo tài khoản/tỷ giá/bảng phí mẫu, sửa quyền tài khoản mới; bảng phí mẫu được xóa mềm.'},'variable':[{'key':k,'value':v,'type':'string'} for k,v in [('base_url','http://127.0.0.1:8000'),('backend_url','http://127.0.0.1:8001'),('admin_password','Admin@123456'),('staff_password','Test@123456'),('access_token',''),('refresh_token',''),('user_id',''),('fee_id','')]],'item':items}
path=Path(__file__).resolve().parents[1]/'postman/Logistics-Gateway.postman_collection.json'
path.write_text(json.dumps(collection,ensure_ascii=False,indent=2)+'\n')
print(f'Đã tạo {len(items)} request Postman với assertion HTTP.')
