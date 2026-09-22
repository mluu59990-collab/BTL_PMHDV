# CMS Nguonhang1688 — Backend (Buổi 1–2)

Phạm vi Buổi 1 theo Master Plan:
- **1.1** Khởi tạo Clean Architecture + kết nối CSDL bất đồng bộ (FastAPI + SQLAlchemy 2.0 async + asyncpg + PostgreSQL)
- **1.2** Đăng ký / đăng nhập, JWT Access + Refresh token, phân quyền RBAC (REQ-1.1, 1.4)
- **1.3** API cập nhật/tra cứu tỷ giá NDT/USD + lịch sử (REQ-1.2, 1.3) và cấu hình thang bảng phí (REQ-9.1)

Yêu cầu: Python 3.11+, PostgreSQL 14+ (hoặc Docker).

## Chạy

### 1. Database (chọn 1 trong 2)

**Docker** (đơn giản nhất — tự chạy các file SQL khi khởi tạo volume mới):
```bash
docker compose up -d
```

**Postgres cài sẵn trên máy** (Homebrew, Postgres.app...):
```bash
createdb cms_nguonhang1688        # hoặc tạo DB bằng DBeaver/TablePlus
psql cms_nguonhang1688 -f sql/01_schema.sql
psql cms_nguonhang1688 -f sql/02_seed_data.sql
psql cms_nguonhang1688 -f sql/03_seed_dev_users.sql    # chỉ môi trường dev
psql cms_nguonhang1688 -f sql/04_catalog_schema.sql
psql cms_nguonhang1688 -f sql/05_catalog_seed.sql
```
Khi cấu hình backend bên dưới, sửa `DATABASE_URL` trong `.env` cho đúng user/mật khẩu của PostgreSQL trên máy.

### 2. Backend
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # chỉ khi chưa có .env
python -c 'import secrets; print(secrets.token_urlsafe(48))'
# Dán kết quả vào JWT_SECRET_KEY trong .env; kiểm tra DATABASE_URL trước khi chạy.
uvicorn app.main:app --reload
```
Mở **http://localhost:8000/docs** (Swagger). Bấm **Authorize**, đăng nhập `admin` / `Admin@123456` là thử được mọi API.

### 3. Kiểm tra nhanh
Với server đang chạy: `python scripts/smoke_test.py` (69 kiểm tra: auth, RBAC, tỷ giá, biểu phí).

## Tài khoản dev (`sql/03_seed_dev_users.sql`)
| Username | Mật khẩu | Vai trò |
|---|---|---|
| admin | Admin@123456 | ADMIN |
| sale01 | Test@123456 | SALE |
| kho01 | Test@123456 | WAREHOUSE |
| ketoan01 | Test@123456 | ACCOUNTANT |
| muahang01 | Test@123456 | PURCHASER |
| khach01 | Test@123456 | CUSTOMER |

⚠️ Không chạy `03_seed_dev_users.sql` ở production.

## API (prefix `/api/v1`)
| Nhóm | Endpoint | Ai gọi được |
|---|---|---|
| Xác thực | `POST /auth/register` (tạo CUSTOMER), `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout` | công khai |
| Cá nhân | `GET/PATCH /users/me`, `POST /users/me/change-password` | đã đăng nhập |
| Quản trị user | `GET /users`, `POST /users`, `PATCH /users/{id}` | ADMIN |
| Tỷ giá | `GET /exchange-rates/current`, `/current/{CNY\|USD}`, `/history` | đã đăng nhập |
| | `POST /exchange-rates` | ADMIN |
| Biểu phí | `GET /fee-configs`, `/fee-configs/current`, `/fee-configs/{id}` | đã đăng nhập |
| | `POST`, `PATCH /{id}`, `DELETE /{id}` (xóa mềm) | ADMIN |
| Hệ thống | `GET /health` | công khai |

ADMIN luôn qua mọi kiểm tra quyền. Muốn giới hạn endpoint cho vai trò khác:
```python
current: User = Depends(require_roles(RoleCode.SALE, RoleCode.WAREHOUSE))
```

## Cấu trúc (Clean Architecture — phụ thuộc chỉ đi từ ngoài vào trong)
```
app/
├── domain/          # Lõi: enums, entity, exception, interface repository. KHÔNG import FastAPI/SQLAlchemy
├── application/     # Nghiệp vụ: services (auth, user, exchange_rate, fee_config) + ports (hasher, JWT, UnitOfWork)
├── infrastructure/  # Chi tiết kỹ thuật: db (async engine, ORM), repositories, Argon2, PyJWT
├── presentation/    # FastAPI: routers, schemas, dependency injection (deps.py)
└── core/            # config (.env), clock
sql/                 # DDL + seed (nguồn sự thật của schema; models.py ánh xạ lại)
```
Thêm module mới (Buổi 2 trở đi): thêm bảng vào `sql/` → model trong `infrastructure/db/models.py` → interface trong `domain/repositories.py` → repo + service + router → `include_router` trong `api/v1/router.py`.

## Thiết kế cần biết
- **Vai trò**: 5 vai trò của Master Plan (Admin, Sale, Kho, Kế toán, Khách hàng) + `PURCHASER` (Nhân viên Đặt hàng, có trong SRS B.2.2). Không cần thì `DELETE FROM roles WHERE code='PURCHASER'`. Thêm vai trò mới: `INSERT` vào `roles` + thêm 1 dòng vào `RoleCode` trong `domain/enums.py`.
- **Token**: access 30 phút, refresh 7 ngày (chỉnh trong `.env`). Refresh token xoay vòng, mỗi token chỉ dùng 1 lần; đổi mật khẩu hoặc khóa tài khoản sẽ thu hồi hết. Quyền được đọc lại từ DB ở mỗi request nên đổi role/khóa tài khoản có hiệu lực ngay.
- **Tỷ giá**: chỉ INSERT, không UPDATE — tỷ giá hiện hành là dòng mới nhất của từng loại tiền, các dòng cũ là lịch sử để đối soát đơn cũ. `rate` = số VNĐ cho 1 đơn vị ngoại tệ.
- **Thang bảng phí**: `fee_type` là mã tự do (thêm loại phí mới không cần sửa code), `tier_min/tier_max` là bậc thang `[min, max)`, `effective_date` cho phép đặt trước biểu phí mới. `GET /fee-configs/current` trả bản có hiệu lực mới nhất ≤ hôm nay (giờ VN) cho từng bậc.
- ⚠️ **Số liệu phí trong `02_seed_data.sql` chỉ là số mẫu để test** — sửa theo biểu phí thật qua `PATCH /fee-configs/{id}`.
- Các trường tiền (`rate`, `value`, `balance`) trả về dạng chuỗi (`"3920.0000"`) để không mất độ chính xác; frontend tự parse.

## Buổi 2 — Danh mục sản phẩm (REQ-3.1 đến REQ-3.6)

Đã triển khai:
- **2.1 / REQ-3.2:** CRUD sản phẩm, SKU, tên, giá tham chiếu và tiền tệ (mặc định CNY), link 1688/Taobao/Tmall, URL hình ảnh, mô tả; lọc và phân trang.
- **2.2 / REQ-3.3–3.6:** CRUD mã nước, đơn vị tính, loại kiện hàng, ngành hàng. Sản phẩm liên kết riêng nước xuất xứ và nước vận chuyển.
- **2.3 / REQ-3.1:** CRUD quyền thương hiệu (bản quyền / uỷ quyền phân phối), chủ thể quyền, URL chứng từ và thời hạn; liên kết đúng một sản phẩm hoặc ngành hàng.

### Nâng cấp database đã chạy Buổi 1

Docker chỉ tự chạy SQL khi volume được tạo lần đầu. Với volume hiện có, chạy:
```bash
docker compose exec -T db psql -U cms -d cms_nguonhang1688 -v ON_ERROR_STOP=1 < sql/04_catalog_schema.sql
docker compose exec -T db psql -U cms -d cms_nguonhang1688 -v ON_ERROR_STOP=1 < sql/05_catalog_seed.sql
```
Nếu dùng PostgreSQL cài sẵn, chạy hai file này bằng `psql` như phần cài đặt. Các file có transaction và có thể chạy lại; không cần xóa dữ liệu Buổi 1.

### API Buổi 2

Tất cả đường dẫn dưới đây có prefix `/api/v1`. Mỗi nhóm có `GET` danh sách, `POST` tạo mới, `GET/PATCH/DELETE /{id}`. `DELETE` ngừng sử dụng bằng `is_active=false`; có thể kích hoạt lại bằng `PATCH`.

| Nhóm | Đường dẫn | Quyền đọc | Quyền ghi |
|---|---|---|---|
| Nước | `/catalog/countries` | Đã đăng nhập | ADMIN |
| Đơn vị tính | `/catalog/units` | Đã đăng nhập | ADMIN |
| Loại kiện | `/catalog/package-types` | Đã đăng nhập | ADMIN |
| Ngành hàng | `/catalog/categories` | Đã đăng nhập | ADMIN |
| Sản phẩm | `/products` | Đã đăng nhập | ADMIN, PURCHASER |
| Quyền thương hiệu | `/brand-rights` | ADMIN, SALE, PURCHASER | ADMIN |

Phân quyền ghi sản phẩm và đọc chứng từ thương hiệu là lựa chọn triển khai cho Buổi 2; SRS chưa quy định chi tiết từng thao tác.

Danh sách trả `{items, total, offset, limit}`. Query chung: `search`, `offset` (mặc định 0), `limit` (1–100, mặc định 20), `active_only` (mặc định true). Tìm kiếm theo mã/tên; quyền thương hiệu theo thương hiệu/chủ thể. Sản phẩm hỗ trợ lọc `category_id`, `origin_country_id`, `shipping_country_id`, `unit_id`, `package_type_id`; quyền thương hiệu hỗ trợ `product_id`, `category_id` (liên kết trực tiếp).

Ví dụ tạo sản phẩm bằng Swagger, thay các ID bằng kết quả API danh mục:
```json
{
  "sku": "SP-001",
  "name": "Áo thun",
  "reference_price": "25.5000",
  "currency_code": "CNY",
  "source_url": "https://detail.1688.com/offer/123.html",
  "image_url": "https://example.com/product.jpg",
  "origin_country_id": 1,
  "shipping_country_id": 1,
  "unit_id": 3,
  "package_type_id": 1,
  "category_id": 1
}
```

Mã danh mục/SKU được trim, viết hoa và chống trùng cả khi bản ghi cũ đã ngừng dùng. Mã nước gồm hai chữ cái. Giá dùng Decimal, trả chuỗi để giữ độ chính xác. Link/hình/chứng từ chỉ được lưu URL HTTP(S), backend không tải hoặc crawl nội dung. Các trường liên kết là tùy chọn; nếu gửi ID thì phải tồn tại và còn hoạt động. Ngừng một danh mục không xóa các liên kết cũ; khi thêm/đổi liên kết hoặc kích hoạt lại sản phẩm sẽ kiểm tra danh mục còn hoạt động.

Quyền thương hiệu dùng `right_type` là `COPYRIGHT` hoặc `DISTRIBUTION_AUTHORIZATION`. Khi chuyển từ sản phẩm sang ngành hàng, gửi đồng thời `product_id: null` và `category_id` mới. `valid_until` phải lớn hơn hoặc bằng `valid_from`. `is_active` là trạng thái quản trị, không tự thay đổi theo ngày hết hạn. Lịch sử phiên bản chứng từ/upload file chưa thuộc triển khai này.

### Kiểm thử tích hợp

```bash
pip install -r requirements-dev.txt
TEST_DATABASE_URL=postgresql://cms:cms@localhost:5432/postgres python -m pytest tests -q
```

User trong `TEST_DATABASE_URL` cần quyền `CREATEDB`. Bộ test tạo database ngẫu nhiên `cms_test_<uuid>`, áp dụng SQL/seed, chạy các ca Buổi 2 và 69 smoke check Buổi 1, rồi xóa database đó. Không dùng database ứng dụng làm nơi ghi dữ liệu kiểm thử. Nếu thiếu biến này, test được đánh dấu **skipped**, không phải đã kiểm thử thành công.
