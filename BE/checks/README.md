# Kiểm thử logistics hiện tại

Từ thư mục BE, dùng Python đã cài requirements-dev.txt:

```bash
.venv/bin/python checks/run_features.py --env .env
```

Runner tạo database ngẫu nhiên `cms_feature_test_<uuid>`, tạo bảng/thủ tục, chạy HTTP qua gateway và backend với MySQL thật, rồi xóa đúng database tạm. Cần quyền CREATE/DROP DATABASE và CREATE ROUTINE. Không chỉnh dữ liệu database ứng dụng. Các test cũ tại `BE/tests` thuộc schema CRM/catalog trước đây.
