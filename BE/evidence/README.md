# Minh chứng Buổi 2 và Buổi 3

Mở `buoi-2-3.html` bằng Chrome. Trang đọc dữ liệu từ kết quả đã lưu ngày 27/09/2026,
không kết nối API và không chạy thêm test. Đây là trang tổng hợp minh chứng backend.

## Bốn ảnh nên chụp

1. **Tổng quan**: chức năng, số API và số lượt PASS riêng Buổi 2–3.
2. **Buổi 2**: chọn “Tạo sản phẩm”; chụp bảng chức năng cùng request/response HTTP 201.
3. **Buổi 3**: chọn “Tạo khách hàng & gán Sale” hoặc “Tạo đăng ký VIP”; chụp dữ liệu thực tế.
4. **Ca kiểm thử & lỗi**: chọn lỗi bỏ qua NEW, trùng SKU hoặc Sale tự nâng hạn mức; chụp HTTP 422/409/403 đúng kỳ vọng.

## Tổng hợp để đưa vào báo cáo

| Buổi | Nội dung đã làm | API | Lượt kiểm thử đã PASS |
|---|---|---:|---:|
| 2 | CRUD sản phẩm; mã nước, đơn vị tính, loại kiện, ngành hàng; quyền thương hiệu; tìm kiếm, phân trang, xóa mềm, phân quyền | 30 | 307/307 |
| 3 | CRUD khách hàng, gán Sale, tra cứu vận đơn theo khách/Sale/ngày; quy trình CSKH; kế hoạch tháng/quý; đánh giá; gói và đăng ký VIP; hạn mức tín dụng | 35 | 367/367 |
| **Tổng Buổi 2–3** | Mỗi API ít nhất 10 lượt | **65** | **674/674** |

Toàn bộ Buổi 1–3: 86 API, 889/889 lượt PASS; gồm 647 ca nhập sai/sai quyền.
Collection đã chạy bằng Newman, kết quả chi tiết tại `reports/20260927-232608/`.

Phần còn thiếu của CRM: công nợ, liên kết đơn OMS/kho, đánh giá theo đơn và tổng hợp doanh số tự động.
Doanh số hiện nhập thủ công; điều kiện VIP lưu mô tả để nhân viên xét duyệt.
Giao diện nghiệp vụ CMS chưa được xây dựng; hiện có Postman, MySQL Workbench và trang minh chứng này.

## MySQL Workbench

Kết nối `127.0.0.1:3306`, mở schema **cms_postman_577eaca804ee** để xem dữ liệu test.
Database ứng dụng là `cms_nguonhang1688` và không nhận dữ liệu của collection test.
Có thể mở `xem-database-da-test.sql`, chạy từng câu SELECT để chụp bảng dữ liệu.
Các thao tác này chỉ đọc database, không gọi API hay sửa dữ liệu.
Các bản ghi test có thể đã được xóa mềm (`is_active=0`); truy vấn minh chứng giữ cả các bản ghi đó.
