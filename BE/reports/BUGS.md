# Nhật ký lỗi khi phát triển và kiểm thử

Ngày chạy: 27/09/2026. Cơ sở dữ liệu: MySQL 8.0.46, container `mysql-local`.
Các lỗi dưới đây được tái hiện bằng request thật qua FastAPI TestClient trên MySQL.
Minh chứng trước sửa: [regression-before.txt](regression-before.txt).

| Mã | Thao tác | Trước sửa | Mong đợi / bản sửa |
|---|---|---|---|
| BUG-001 | `POST /auth/register` với username mới, mật khẩu hợp lệ, `full_name: "   "` | HTTP 201, tạo user có tên rỗng | HTTP 422; service kiểm tra tên sau trim trước khi lưu |
| BUG-002 | `POST /crm/care-tasks` với khách hợp lệ và `status: "COMPLETED"` | HTTP 201; bỏ qua toàn bộ bước CSKH | HTTP 422; tạo mới bắt buộc bắt đầu ở NEW |

Hai ca có regression test trong `tests/test_crm.py` và đã thêm vào collection Postman.

## Sai lệch của test, không phải lỗi API

Lượt Newman đầu: 886 request, 885 PASS, 1 FAIL. Ca đổi mật khẩu với mật khẩu cũ sai
đặt kỳ vọng 401, trong khi service quy định lỗi nghiệp vụ là 422. Đã sửa kỳ vọng thành 422.
[Chi tiết lượt đầu](20260927-220657/report.html).

## Điều chỉnh tương thích MySQL qua kiểm tra mã nguồn

- `DISTINCT ON` thay bằng `row_number()` để lấy tỷ giá/biểu phí mới nhất.
- `UPDATE ... RETURNING` thay bằng kiểm tra số dòng cập nhật để thu hồi token nguyên tử.
- Bỏ `NULLS FIRST`; MySQL xếp NULL trước khi sort tăng dần.
- SQL chuyển sang AUTO_INCREMENT, khóa ngoại cấp bảng, index trong CREATE TABLE,
  seed ON DUPLICATE KEY UPDATE và DATETIME(6) lưu UTC.
- Đổi driver asyncpg thành asyncmy; tests khởi tạo database MySQL riêng.

Các mục tương thích được tìm khi đọc code và kiểm chứng qua test; không tính là
những lỗi đã quan sát trên API trước khi sửa.

## Xác nhận sau sửa

- 42 pytest PASS (bao gồm BUG-001 và BUG-002).
- Lượt Newman cuối: **889/889 request PASS**, **647 ca nhập sai/sai quyền**.
- [Báo cáo cuối](20260927-232608/report.html) và [độ phủ 86 API](20260927-232608/coverage.md).
