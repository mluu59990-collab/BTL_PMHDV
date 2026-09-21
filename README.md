# CMS Nguonhang1688 — Backend (Buổi 1)

Phạm vi Buổi 1 theo Master Plan:
- **1.1** Khởi tạo Clean Architecture + kết nối CSDL bất đồng bộ (FastAPI + SQLAlchemy 2.0 async + asyncpg + PostgreSQL)
- **1.2** Đăng ký / đăng nhập, JWT Access + Refresh token, phân quyền RBAC (REQ-1.1, 1.4)
- **1.3** API cập nhật/tra cứu tỷ giá NDT/USD + lịch sử (REQ-1.2, 1.3) và cấu hình thang bảng phí (REQ-9.1)

Yêu cầu: Python 3.11+, PostgreSQL 14+ (hoặc Docker).

## Chạy

### 1. Database (chọn 1 trong 2)

**Docker** (đơn giản nhất — tự chạy luôn 3 file SQL):
```bash
docker compose up -d
```

**Postgres cài sẵn trên máy** (Homebrew, Postgres.app...):
```bash
createdb cms_nguonhang1688        # hoặc tạo DB bằng DBeaver/TablePlus
psql cms_nguonhang1688 -f sql/01_schema.sql
psql cms_nguonhang1688 -f sql/02_seed_data.sql
psql cms_nguonhang1688 -f sql/03_seed_dev_users.sql    # chỉ môi trường dev
```
Rồi sửa `DATABASE_URL` trong `.env` cho đúng user/mật khẩu của máy mày.

### 2. Backend
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
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
