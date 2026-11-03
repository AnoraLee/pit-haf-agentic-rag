# Synthetic timed execution v0.1

Ngày 03/11/2026. Bộ chẩn đoán phần mềm cho
`synthetic_timed_execution_v0.1`, không chứa giá thị trường, nhãn người
đánh giá hoặc kết quả chiến lược tài chính. Tất cả giá/target/lịch trong
demo và test là dữ liệu tự tạo; không có LLM dự báo ở mốc này.

## Mục đích và phạm vi

Tách lịch phiên khỏi lịch thanh toán, xác định ngày theo số ngày được
cung cấp rồi lấy giờ khả dụng trên ngày thanh toán. Engine kiểm ranh
giới open/close/decision, không cho dùng tiền/cổ phiếu trước lúc về.
Phần chưa về vẫn tính trong NAV; close snapshot không bị cập nhật ngược
bởi sự kiện sau close. Không tự thêm ngày nghỉ, bar hoặc lệnh thử lại.

Nguồn gốc input là fixture do trợ lý xây dựng để phát triển phần mềm.
Thông báo VSDC liên kết trong tài liệu mốc 36 chỉ được dùng làm cơ sở
thiết kế thời điểm, không chuyển fixture thành lịch thị trường được
xác minh. Không lưu raw tài liệu web trong bộ này.

42 test mới và nhóm 86 test backtest đã đạt. Ba run manual/Q0/Q1 mới
replay khớp; ba run `synthetic_execution_v0.1` cũ cũng replay khớp.
104 hash bảo vệ cũ không đổi. Không tạo database duyệt thật, gọi LLM,
tải giá hoặc sửa output cũ. Kết quả kiểm thử toàn repository nằm trong
`validation.json`, không là semantic accuracy hoặc hiệu quả đầu tư.

## Tái lập và lưu trữ

```powershell
.\run.ps1 test tests/test_timed_execution.py tests/test_backtest_execution.py
.\run.ps1 backtest-timed --demo
.\run.ps1 backtest-timed --demo --baseline Q0
.\run.ps1 backtest-timed --demo --baseline Q1 --rebalance-every 2
```

`manifest.json` pin config, study và ba run local. Các run giữ input,
nguồn, JSON/CSV và seal trong `outputs/backtest-timed-synthetic/`;
không đưa raw/CSV lên Git. Clone mới có thể chạy demo không cần corpus,
Ollama hoặc Internet; muốn replay ID cũ phải khôi phục nguyên thư mục.

Lệnh replay dùng `--replay <run folder>`, kiểm toàn vẹn rồi tái tính
bằng code hiện tại. Code snapshot không được thực thi tự động; nếu
hành vi phiên bản sau khác, cần commit gốc để đối chiếu. Hash không
thay xác nhận nguồn hoặc đánh giá độc lập.

## Giới hạn

Lịch/giờ là giả định input. `eligible_for_execution=false`,
`venue_calendar_verified=false`, `historical_availability_validated=false`,
`independent_gold=false`, `research_result=false`. Thực thi vẫn chỉ ở
open kế tiếp, chưa có giá/lệnh chiều, corporate actions, ứng trước,
tick/fee rounding hoặc lịch sử universe. Q0/Q1 vẫn là lịch trên kịch
bản giả lập; không công bố lợi suất demo như kết quả đề tài. Cohort PiT
strict và số nhãn thật không tăng.
