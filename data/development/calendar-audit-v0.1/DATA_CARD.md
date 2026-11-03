# Calendar audit v0.1

Ngày 03/11/2026. Protocol `settlement_calendar_audit_v0.1` đối soát
ngày trong snapshot KBS 2021–2024 với lịch thanh toán ứng viên từ
chín thông báo VSD/VSDC. Không chạy lợi suất, giao dịch, LLM hoặc
ghi nhãn thật ở mốc này.

## Nguồn và curation

Raw HTML được tải từ domain VSDC bằng HTTPS kiểm chứng chỉ mặc định,
lưu URL/thời điểm/status/hash; capture chính thức có chín request,
không retry/redirect/cookie hoặc xác thực. Có một probe HTTP thành
công trước đó được giữ riêng và một lần lỗi DNS trong sandbox.
Các lần đọc/search web phục vụ tìm nguồn không được tính vào chín
request capture. Không có API key hoặc import Vnstock.

Các khoảng nghỉ được trợ lý nhập theo thông báo, gắn source ID,
hash toàn raw và body, anchor kiểm tra, revision và quan hệ thay thế.
Đây là curation phát triển, chưa có người đánh giá độc lập xác nhận.
Hash/anchor chỉ kiểm bytes và sự hiện diện chuỗi; chưa tự xác nhận
toàn bộ ngữ nghĩa hoặc tính đầy đủ của thông báo.

Giữ lịch 2021 ban đầu/sửa đổi, 2022, 2023 ban đầu/sửa đổi và 2024
ban đầu/thông báo tháng 4. Thông báo thời điểm T+2 năm 2022 chỉ làm
tài liệu tham khảo; lịch 2025 chỉ dùng phần 01–03/01 làm đuôi.
Giữ nguyên lỗi chú thích năm 2020 trong raw bản sửa đổi 2021.
Xem [tài liệu và URL nguồn](../../../docs/research/37-settlement-calendar-audit.md).

## Kết quả phát triển

Lịch ứng viên là thứ Hai–thứ Sáu trừ khoảng nghỉ có nguồn, không phải
toàn bộ lịch giao dịch HOSE đã xác minh. Có 998 ngày: 250/249/249/250
theo năm 2021/2022/2023/2024. FPT, HPG, VCB mỗi mã khớp toàn bộ tập
998 ngày, không có ngày thừa/thiếu. Giữ năm ngày đổi trạng thái giữa
bản gốc và sửa đổi; không chỉ so tổng số ngày.

VNINDEX giữ lỗi OHLC của snapshot gốc, nằm trong danh sách chưa đối
soát, không được vá hoặc bỏ khỏi báo cáo. Mã cổ phiếu lỗi dữ liệu
không được âm thầm loại để báo tổng thể khớp. Sinh 998 cặp ngày T+2,
có đuôi qua đầu năm 2025; giờ khả dụng tiền/cổ phiếu vẫn null.

35 test mới, nhóm liên quan 114 test và toàn repository 801 test đạt;
Ruff đạt, còn hai cảnh báo phụ thuộc cũ. Run thật/CLI replay khớp,
114 hash bảo vệ cũ giữ nguyên, review DB thật vẫn vắng mặt. Frontend
không thay đổi nên không chạy lại build/QA giao diện.

## Tái lập và giới hạn

`manifest.json` pin source archive, snapshot giá, config, code và
study. Raw/run/CSV chỉ ở local ngoài Git. Clone mới muốn replay ID
trong manifest cần khôi phục đúng dependency; chưa xác nhận chủ dự
án đã đưa các thư mục mới lên Drive. Có thể capture nguồn mới bằng
script PowerShell 7.2+, nhưng web đổi raw cần review/profile phiên
bản mới, không sửa seal artifact cũ để ép khớp.

```powershell
.\run.ps1 test tests/test_calendar_audit.py tests/test_market_snapshot.py tests/test_timed_execution.py
.\run.ps1 calendar-audit --replay outputs/calendar-audits/20261103T025840Z-fa7a29cb
```

Lịch dựng hồi cứu; chưa đủ nguồn HOSE/phiên bất thường, giờ khả dụng
ở tài khoản, lịch sử corporate actions, adjustment/universe hoặc
lineage cutoff. Không áp quy tắc thanh toán cổ phiếu sang công cụ
nợ. `venue_calendar_verified`, `broker_availability_verified`,
`historical_availability_validated`, `independent_gold`,
`eligible_for_execution`, `research_result` đều false. Chưa nối vào
engine; không nâng cohort PiT strict hoặc công bố kết quả đầu tư.
