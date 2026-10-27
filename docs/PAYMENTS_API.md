# Thu/hoàn phí vận chuyển

Các API ghi nhận tiền nhân viên đã thu/hoàn vào bảng thanh_toan hiện có, không thực hiện
chuyển tiền thật hoặc gọi ngân hàng/cổng thanh toán. Vẫn giữ 10 bảng. Giao dịch không sửa/xóa;
sai sót xử lý bằng giao dịch hoàn phù hợp và đối soát, không sửa lịch sử.

Base URL: http://127.0.0.1:8000. Mọi request cần Authorization → Bearer Token.
POST dùng Body → raw → JSON. Các ID bên dưới phải thay bằng ID thật.

## Quyền

- ADMIN/ACCOUNTANT đọc tất cả và ghi nhận thu/hoàn. ACCOUNTANT được đọc đơn để đối soát,
  không được tạo/sửa/chuyển trạng thái đơn, quản lý khách hoặc kho.
- SALE chỉ đọc giao dịch/số dư đơn của khách hiện được phân công.
- CUSTOMER chỉ đọc giao dịch/số dư đơn thuộc hồ sơ liên kết với tài khoản mình.
- WAREHOUSE không được truy cập sổ thu/hoàn và payment-summary.
- Truy cập đơn/giao dịch ngoài phạm vi hoặc không tồn tại trả 404. Gọi chức năng không
  được phép trả 403. Quyền lấy từ DB hiện tại, không tin vai trò cũ trong JWT.

## 5 API

| Method | URL đầy đủ | Chức năng |
|---|---|---|
| POST | http://127.0.0.1:8000/payments | Ghi phiếu thu |
| POST | http://127.0.0.1:8000/payments/refunds | Ghi phiếu hoàn |
| GET | http://127.0.0.1:8000/payments?order_id=1&limit=20&offset=0 | Lịch sử giao dịch |
| GET | http://127.0.0.1:8000/payments/1 | Chi tiết giao dịch |
| GET | http://127.0.0.1:8000/orders/1/payment-summary | Tổng hợp tiền của đơn |

## Thu tiền

```json
{
  "order_id": 1,
  "amount": "100000.50",
  "method": "BANK_TRANSFER",
  "reference_code": "TT_DH1_001"
}
```

order_id là ID đơn, không phải ID khách. Chỉ thu khi đơn CONFIRMED/SHIPPING/DELIVERED.
amount >0, tối đa 16 chữ số nguyên và 2 số thập phân, response trả chuỗi chính xác.
method: CASH hoặc BANK_TRANSFER. Hệ thống không tự xác minh chuyển khoản; nhân viên phải đối soát
trước khi ghi. Không gửi transaction_type/created_by từ client: BE quyết định loại và người tạo.
Số tiền thu không vượt shipping_fee - (tổng thu - tổng hoàn), kể cả request đồng thời.
Phí bằng 0 thì đã thanh toán đủ, không cần giao dịch giá trị 0.

reference_code bắt buộc: 3–80 ký tự chữ/số/_.:/-, được trim và viết hoa, duy nhất toàn hệ thống.
Mỗi giao dịch thực tế dùng một mã riêng. Gửi lại request do timeout phải giữ nguyên mã và nội dung:

- Lần đầu: 201, replayed=false.
- Cùng mã, cùng order_id/amount/method/loại giao dịch: 200, replayed=true, cùng ID cũ,
  không tạo hàng mới và không đổi người tạo ban đầu.
- Cùng mã nhưng khác dữ liệu hoặc loại thu/hoàn: 409.
- Hai nhân viên gửi đồng thời cùng mã/cùng đơn: một 201, một 200; không thu hai lần.
- Retry khác mã sẽ được coi là giao dịch mới, không phải retry.

Response: id, order_id, amount, transaction_type (PAYMENT/REFUND), method,
reference_code, created_by, created_at (UTC); POST thêm replayed.
Replay giao dịch cũ vẫn trả 200 sau khi đơn bị hủy, vì không ghi nhận khoản thu mới.

## Hoàn tiền

`POST /payments/refunds`

```json
{
  "order_id": 1,
  "amount": "20000.00",
  "method": "CASH",
  "reference_code": "HT_DH1_001"
}
```

Cùng validation/idempotency như thu tiền, nhưng transaction_type do server đặt REFUND.
Hoàn tối đa số đang giữ = tổng thu - tổng hoàn. Cho phép hoàn sau giao hàng hoặc với đơn hủy
cũ còn giữ tiền; không hoàn được khi chưa thu. Không có liên kết tới một phiếu thu riêng vì
schema hiện tại chỉ lưu giao dịch theo đơn. Đây là hoàn theo số dư toàn đơn, không gọi ngân hàng.

Hoàn tiền không tự hủy đơn hoặc miễn phí cho đơn đang hoạt động. Ví dụ phí 100000, đã thu đủ,
hoàn 20000 thì net_paid=80000 và amount_due=20000. Muốn hủy đơn, hoàn đủ rồi ADMIN/SALE gọi
API hủy đơn nếu trạng thái/kiện cho phép. Hủy vẫn bị chặn khi còn kiện chưa CANCELLED hoặc số dư khác 0.
Lịch sử phiếu thu/hoàn giữ nguyên sau khi hủy.

## Lịch sử và chi tiết

`GET /payments` hỗ trợ order_id, transaction_type (PAYMENT/REFUND), method,
search (mã tham chiếu), date_from/date_to (ISO 8601 có múi giờ), limit (1–100), offset (>=0).

Ví dụ: `/payments?order_id=1&transaction_type=PAYMENT&method=CASH&limit=20&offset=0`.
Ngày bắt đầu/kết thúc bao gồm cả hai mốc; date_from sau date_to hoặc thiếu múi giờ trả 422.
Thứ tự thời gian giảm dần, cùng thời gian thì ID giảm dần. Kết quả `{items: [...], limit, offset}`.
`GET /payments/1` trả một giao dịch. Không cung cấp PATCH/DELETE (trả 405).

## Tổng hợp theo đơn

`GET /orders/1/payment-summary`

```json
{
  "order_id": 1,
  "order_code": "DH...",
  "order_status": "CONFIRMED",
  "currency": "VND",
  "shipping_fee": "150000.50",
  "total_paid": "100000.00",
  "total_refunded": "20000.00",
  "net_paid": "80000.00",
  "amount_due": "70000.50",
  "refund_due": "0.00",
  "payment_status": "PARTIAL"
}
```

net_paid = total_paid - total_refunded.
Đơn hoạt động: amount_due=max(shipping_fee-net_paid,0), refund_due=max(net_paid-shipping_fee,0).
Đơn CANCELLED: amount_due=0, refund_due=max(net_paid,0); shipping_fee gốc vẫn được giữ để đối soát.
Các số tổng được tính từ ledger hiện tại, không lưu số dư giả ở bảng khác.

payment_status:

- UNPAID: chưa thu.
- PARTIAL: đã thu một phần.
- PAID: đã thu đủ (gồm đơn miễn phí).
- REFUNDED: hoàn hết, nhưng đơn đang hoạt động nên phí vẫn còn phải thu.
- CANCELLED: đơn đã hủy và không còn tiền phải hoàn.
- REFUND_DUE: dữ liệu đơn hủy cũ còn tiền phải trả khách.
- OVERPAID: dữ liệu cũ có số thu ròng vượt phí; cho phép hoàn phần thừa.
- INVALID: dữ liệu cũ có tổng hoàn vượt tổng thu; chặn giao dịch mới và cần quản trị viên đối soát.

## Luồng code

1. Gateway/gateway_app/app.py kiểm tra access token, thêm khóa nội bộ và chuyển request.
2. BE/app/main.py kiểm tra khóa, current_user trong BE/app/auth.py xác thực và đọc tài khoản từ DB;
   include_router(create_payment_router(current_user)) gắn router thanh toán.
3. BE/app/payments.py: PaymentCreate kiểm tra JSON, reader/writer kiểm tra vai trò,
   record_payment gọi procedure, commit/rollback và trả 201/200 theo replayed.
4. BE/app/infrastructure/db/session.py cấp session theo DATABASE_URL.
5. sql/cms_logistics_payments.sql có 6 procedure: sp_payment_actor,
   sp_lock_payment_order, sp_get_payment, sp_list_payments, sp_order_payment_summary, sp_record_payment.
6. Procedure khóa tài khoản → khách hàng → đơn trước khi tính số dư và thêm giao dịch;
   cùng thứ tự khóa với API đơn/kiện, tránh thu tiền đồng thời với hủy đơn hoặc thu/hoàn quá số dư.
   SQL kiểm tra lại quyền. Sổ giao dịch, số dư và dữ liệu phản hồi cùng một transaction.
7. payment_row đổi Decimal thành chuỗi, datetime thành UTC rồi trả qua Gateway về client.

sql/cms_logistics_orders.sql được cập nhật: ACCOUNTANT đọc đơn; ADMIN/SALE hủy đơn sau hoàn đủ;
điều kiện chặn kiện chưa hủy vẫn được giữ. API sửa thông tin đơn không cho chỉnh phí sau xác nhận/giao dịch.

## Cài đặt và test

DB đã có 10 bảng: chạy lại sql/cms_logistics_orders.sql rồi sql/cms_logistics_payments.sql.
Không cần chạy lại schema. Docker volume mới tự cài qua Compose.

```bash
BE/.venv/bin/python BE/tests/check_payments.py
BE/.venv/bin/python BE/tests/check_payments.py --postman
```

Runner tạo DB MySQL tạm, cài procedures hai lần, chạy test số dư/phân quyền/precision/concurrency,
và tự xóa DB tạm. Cần CREATE/DROP DATABASE và CREATE ROUTINE. --postman chạy 2 server tạm,
Postman CLI với --no-report-events rồi dọn server. Không tạo giao dịch trong DB ứng dụng.

Test thủ công: import Gateway/postman/Logistics-Payments.postman_collection.json;
điền admin_username/admin_password. Collection tạo khách/đơn/giao dịch thử thật trong DB
đang kết nối; không tự xóa dữ liệu. Có 22 request, 29 assertion.
