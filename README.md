# CMS Nguonhang1688 — Backend Buổi 1–3 (MySQL)

FastAPI + SQLAlchemy async + **MySQL 8.0.16 trở lên / InnoDB**, theo Clean Architecture.
Phạm vi phát triển tiếp theo MasterPlan.xlsx: Buổi 3 — CRM.

## Chạy trên máy

MySQL cục bộ: `127.0.0.1:3306`. Tạo database rỗng bằng MySQL Workbench:

```sql
CREATE DATABASE cms_nguonhang1688 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env  # chỉ khi chưa có .env
```

Đặt `DATABASE_URL=mysql+asyncmy://USER:PASSWORD@127.0.0.1:3306/cms_nguonhang1688` trong `.env`.
Ký tự đặc biệt trong mật khẩu cần URL encode. Tạo `JWT_SECRET_KEY` bằng
`python -c 'import secrets; print(secrets.token_urlsafe(48))'`.

```bash
DEBUG=false python scripts/init_db.py --dev-users
DEBUG=false uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Swagger: <http://127.0.0.1:8000/docs>. `DEBUG=false` ghi rõ để tránh biến `DEBUG=release`
của môi trường máy ghi đè cấu hình boolean trong `.env`.

Nếu muốn dùng MySQL Docker mới: `docker compose up -d` và dùng port **3307**.
Container MySQL hiện có trên máy dùng port 3306; không cần tạo thêm container.
SQL được chạy theo thứ tự `01` đến `06`. `03_seed_dev_users.sql` chỉ dành cho dev;
không truyền `--dev-users` khi khởi tạo môi trường thật. Không xóa volume để nâng cấp.

**Database đã có Buổi 1–2 trên MySQL:** áp dụng `sql/06_crm_schema.sql` qua Workbench
hoặc `scripts/init_db.py`. `CREATE TABLE IF NOT EXISTS` không tự sửa cấu trúc bảng có sẵn.
Các file SQL hiện dành cho MySQL; chuyển dữ liệu từ PostgreSQL cũ cần quy trình riêng.
MySQL DDL tự commit, nên các lệnh tạo bảng không rollback nguyên file khi gặp lỗi.

## Tài khoản dev

| Username | Mật khẩu | Vai trò |
|---|---|---|
| admin | Admin@123456 | ADMIN |
| sale01 | Test@123456 | SALE |
| kho01 | Test@123456 | WAREHOUSE |
| ketoan01 | Test@123456 | ACCOUNTANT |
| muahang01 | Test@123456 | PURCHASER |
| khach01 | Test@123456 | CUSTOMER |

## API Buổi 1–2

Prefix `/api/v1`, trừ `/health`.

| Nhóm | Endpoint | Quyền |
|---|---|---|
| Auth | `POST /auth/register`, `/login`, `/refresh`, `/logout` | Công khai; đăng ký luôn tạo CUSTOMER |
| Cá nhân | `GET/PATCH /users/me`, `POST /users/me/change-password` | Đã đăng nhập |
| Users | `GET/POST /users`, `PATCH /users/{id}` | ADMIN |
| Tỷ giá | `GET /exchange-rates/current`, `/current/{CNY\|USD}`, `/history` | Đã đăng nhập |
| Tỷ giá | `POST /exchange-rates` | ADMIN |
| Phí | `GET /fee-configs`, `/current`, `/{id}` | Đã đăng nhập |
| Phí | `POST /fee-configs`, `PATCH/DELETE /fee-configs/{id}` | ADMIN |
| Danh mục | `/catalog/countries`, `/units`, `/package-types`, `/categories` | Đọc: đăng nhập; ghi: ADMIN |
| Sản phẩm | `/products` | Đọc: đăng nhập; ghi: ADMIN, PURCHASER |
| Quyền thương hiệu | `/brand-rights` | Đọc: ADMIN, SALE, PURCHASER; ghi: ADMIN |
| Health | `GET /health` | Công khai, kiểm tra DB |

Mỗi tài nguyên danh mục/sản phẩm/thương hiệu có `GET/POST` danh sách,
`GET/PATCH/DELETE /{id}`. DELETE là xóa mềm (`is_active=false`).
Danh sách trả `{items,total,offset,limit}`, với `search`, `offset`, `limit` (1–100),
`active_only`. Sản phẩm hỗ trợ lọc các ID danh mục; quyền thương hiệu lọc sản phẩm/ngành hàng.
Mã/SKU được trim và viết hoa; mã nước gồm hai chữ cái. Các URL chỉ cho HTTP(S);
link mua hàng giới hạn 1688/Taobao/Tmall. Quyền thương hiệu gắn đúng một sản phẩm
hoặc ngành hàng; ngày kết thúc không trước ngày bắt đầu.

Refresh token xoay vòng và chỉ sử dụng một lần. Logout có tính idempotent: token
hỏng/hết hạn cũng trả 204. Đổi mật khẩu/khóa tài khoản thu hồi refresh token;
access token đã phát vẫn có hạn dùng riêng, trạng thái tài khoản được kiểm tra mỗi request.
Tiền trả dạng chuỗi Decimal. Tỷ giá giữ lịch sử; biểu phí hiện hành lấy phiên bản mới nhất
cho từng loại/đơn vị/bậc có hiệu lực đến ngày chọn. Số phí seed chỉ là dữ liệu mẫu.
Thời gian trong MySQL lưu UTC `DATETIME(6)`; API trả ISO-8601 có múi giờ UTC.

## Buổi 3 — CRM

Bảy nhóm dưới đây đều có `GET/POST` và `GET/PATCH/DELETE /{id}`:

| Endpoint | Nội dung |
|---|---|
| `/api/v1/crm/customers` | Khách hàng, liên hệ, liên kết tài khoản CUSTOMER, Sale phụ trách, hạn mức tín dụng |
| `/api/v1/crm/trackings` | Mã vận đơn, khách hàng, ngày gửi, ghi chú |
| `/api/v1/crm/care-tasks` | Công việc CSKH, ngày hẹn, bước xử lý |
| `/api/v1/crm/sales-plans` | Kế hoạch tháng/quý theo Sale, mục tiêu, doanh số ghi nhận thủ công |
| `/api/v1/crm/service-reviews` | Đánh giá 1–5 điểm theo khách hàng và khoảng thời gian |
| `/api/v1/crm/vip-packages` | Điều kiện, quyền lợi dạng mô tả, thời hạn tối đa |
| `/api/v1/crm/vip-memberships` | Đăng ký gói cho khách hàng, ngày bắt đầu/kết thúc |

### Quy tắc nghiệp vụ

- ADMIN có toàn quyền. SALE chỉ truy cập khách hàng được phân công và dữ liệu liên quan,
  cùng kế hoạch của chính mình. Khách do Sale tạo tự gán cho Sale đó.
- Chỉ ADMIN được đổi Sale phụ trách, tài khoản khách liên kết, hạn mức tín dụng và ghi gói/đăng ký VIP.
  SALE được đọc gói VIP và đăng ký của khách mình phụ trách.
- CUSTOMER và các vai trò khác không truy cập CRM nội bộ ở giai đoạn này.
- Danh sách hỗ trợ phân trang/tìm kiếm/xóa mềm như catalog. Lọc `sale_id`; các nhóm
  liên quan khách hỗ trợ `customer_id`. Vận đơn hỗ trợ thêm `date_from/date_to` (bao gồm hai ngày biên).
  Ngày đảo ngược hoặc bộ lọc không áp dụng cho tài nguyên trả 422.
- Sale phải là tài khoản SALE đang hoạt động. Khách hàng/gói VIP liên kết phải tồn tại và hoạt động.
- CSKH bắt đầu ở `NEW`; luồng `NEW → CONTACTED → FOLLOW_UP → COMPLETED`.
  `CONTACTED` cũng được chuyển thẳng `COMPLETED`; trạng thái chưa hoàn tất được chuyển `CANCELLED`.
  Hai trạng thái kết thúc không được quay lại bước trước.
- Kế hoạch bắt đầu ngày đầu tháng/quý, không trùng Sale/loại kỳ/ngày bắt đầu.
- VIP không cho hai đăng ký đang hoạt động trùng ngày hiệu lực cho một khách.
  Hai ngày biên đều được tính; gói 30 ngày từ 01/10 kết thúc muộn nhất 30/10.
  Transaction dùng READ COMMITTED và khóa khách hàng trước khi kiểm tra trùng. `is_active` là cờ quản trị;
  khi xác định quyền lợi đang có hiệu lực cần xét cả khoảng ngày.

**Ranh giới với các buổi sau:** vận đơn hiện nhập tại CRM, chưa liên kết đơn OMS/kho;
đánh giá theo kỳ, chưa theo đơn. Doanh số thực hiện được ghi nhận thủ công, chưa tổng hợp từ đơn hàng.
Hạn mức tín dụng đã có; công nợ hiện tại cần dữ liệu đơn/giao dịch ở phần OMS,
chưa được triển khai và không trả số dư giả. Điều kiện VIP lưu để nhân viên xét duyệt thủ công.

## Kiểm thử MySQL thật

```bash
python scripts/run_checks.py
```

Script đọc `.env`, tạo database ngẫu nhiên `cms_test_<uuid>`, áp dụng SQL/seed **hai lần**,
chạy pytest (có 69 smoke check Buổi 1), rồi xóa đúng database tạm đó.
Tài khoản MySQL phải có quyền CREATE/DROP DATABASE. Có thể tự đặt `TEST_DATABASE_URL`
và chạy `python -m pytest tests -q`; thiếu biến này sẽ **skip**, không phải pass.

## Postman — khoảng 10 tình huống mỗi API

Collection: [postman/CMS.postman_collection.json](postman/CMS.postman_collection.json).
Bao gồm request đúng, thiếu trường, sai kiểu/ngày/ID, trùng dữ liệu, token sai, sai quyền,
xóa mềm và các bước nghiệp vụ. Mỗi cặp method/path có ít nhất 10 lượt; bốn loại catalog
được kiểm riêng. Health và một số API đọc đơn giản có lượt lặp lại/đổi tài khoản.

```bash
npm install --prefix /private/tmp/btl-postman newman
python scripts/build_postman.py
python scripts/run_postman.py --serve
```

Runner tạo database `cms_postman_<uuid>` mới, khởi động API ở `127.0.0.1:8001`, chạy collection
**1 iteration** bằng Newman và giữ API mở với `--serve`. Database test được giữ để xem lại
trong Workbench. Database ứng dụng không nhận dữ liệu test. Có thể đổi port bằng `--port`.
Nếu Newman ở chỗ khác, dùng `--newman /duong/dan/newman`.

Trong **Postman trên máy**: Import collection → chọn collection → Run → Iterations **1**.
Biến `base_url` mặc định `http://127.0.0.1:8001`. Các request đã tách sẵn thành từng tình huống;
không cần đặt 10 iterations. Request tự đăng nhập và lấy ID từ phản hồi thật.
API phải đang chạy khi dùng Postman.

Kết quả từng lượt ở `reports/<thời điểm>/`:

- `report.html`: tìm theo API/tên ca, lọc FAIL, mở từng request xem input và response.
- `results.csv`: mở bằng Excel; `results.json`: dữ liệu đầy đủ đã che token/mật khẩu.
- `database.txt`: tên database đã test.
- Bản xuất Newman gốc và log chỉ lưu cục bộ, được gitignore vì có thể chứa token.

Ca nhập sai trả đúng lỗi mong đợi là **PASS**. `FAIL` cần đối chiếu để phân biệt lỗi API
và lỗi test. Lịch sử lỗi tìm được: [reports/BUGS.md](reports/BUGS.md).
Đây là kiểm thử chức năng tuần tự, chưa phải kiểm thử tải 200 request đồng thời của SRS.

Tham khảo runner: [tài liệu Newman của Postman](https://learning.postman.com/docs/collections/using-newman-cli/installing-running-newman).

## Cấu trúc

```text
app/domain/                 Entity, enum, cổng repository; không phụ thuộc framework
app/application/services/   Nghiệp vụ, quyền sở hữu dữ liệu, ranh giới transaction
app/infrastructure/         MySQL ORM/repository, UTC datetime, Argon2, JWT
app/presentation/           Schema, router, dependency injection
sql/                        DDL và seed MySQL, nguồn schema triển khai
scripts/                    Khởi tạo DB, test tích hợp, tạo/chạy collection, báo cáo
postman/                    Collection có thể import
reports/                    Kết quả chạy thực tế
```
