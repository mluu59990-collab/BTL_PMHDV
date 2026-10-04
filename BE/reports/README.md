# Kết quả kiểm thử ngày 27/09/2026

## Lượt cuối

- **889/889 request PASS**, 0 FAIL; **647 ca lỗi đầu vào/quyền truy cập**.
- **86 API**, mỗi API ít nhất **10 lượt**; kiểm riêng bốn loại catalog.
- **42 pytest PASS**, gồm bộ smoke check 69 kiểm tra Buổi 1 và ca hai đăng ký VIP đồng thời.
- MySQL thật **8.0.46** trên máy; database test: `cms_postman_577eaca804ee`.
- Collection chạy bằng **Newman (Postman collection runner)**, 1 iteration; Postman desktop đã được mở với file collection.
- API test còn chạy tại <http://127.0.0.1:8001/docs> khi tiến trình runner còn hoạt động.

[**Mở báo cáo HTML**](20260927-232608/report.html) ·
[CSV mở bằng Excel](20260927-232608/results.csv) ·
[Độ phủ từng API](20260927-232608/coverage.md) ·
[Nhật ký lỗi và cách sửa](BUGS.md).

HTML cho phép tìm theo endpoint hoặc tên ca, mở từng dòng để xem dữ liệu gửi,
HTTP kỳ vọng, HTTP thực tế và response. Token/mật khẩu được che trong báo cáo.

## Lịch sử

1. Lượt Newman đầu: 885/886 PASS; một kỳ vọng của test sai (`401` thay vì `422`).
2. Hai test bổ sung tái hiện lỗi thật: chấp nhận tên toàn dấu cách và bỏ qua bước đầu CSKH.
3. Đã sửa và thêm regression; 42 pytest cùng 889 request collection ở lượt cuối đều pass.

Mỗi request trong collection có tên theo tình huống. Lỗi nhập liệu đúng kỳ vọng được tính PASS.
Các API đọc đơn giản/health có lượt lặp lại hoặc đổi tài khoản; không giả định mọi endpoint đều có
10 loại lỗi khác nhau. Đây là kiểm thử chức năng tuần tự, chưa phải kiểm thử tải đồng thời.
