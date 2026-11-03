# 36 — Thanh toán theo thời điểm và hai lịch tường minh

Ngày 03/11/2026. Protocol `synthetic_timed_execution_v0.1` bổ sung thời
điểm khả dụng của cổ phiếu và tiền bán vào động cơ giả lập. Lệnh vẫn thực
thi tại open của phiên được cung cấp kế tiếp. Chưa có backtest giá thật,
lịch HOSE/VSDC được xác minh hoặc kết quả đầu tư của các agent.

## Vấn đề và cách biểu diễn

Mốc 33 giải phóng tài sản tại open sau một số phiên nguyên. Cách đó
không biểu diễn được tài sản về giữa ngày. Phiên bản mới nằm ở các
module `timed_contracts`, `timed_engine`, `timed_runner`, không sửa mã,
cấu hình hoặc artifact `synthetic_execution_v0.1`.

Thông báo ngày 19/08/2022 của VSD mô tả thời điểm hoàn tất thanh toán
T+2 được chuyển sớm hơn và yêu cầu phân bổ cho khách hàng trước 13h.
Thông báo nêu giao dịch ngày 25/08 nhận tài sản ngày 29/08/2022 theo
thay đổi mới. Vì vậy, mô hình cần lấy giờ khả dụng theo **ngày thanh
toán**, tránh áp thời gian cũ chỉ vì giao dịch phát sinh trước 29/08.
Đây là cơ sở thiết kế; không xác nhận toàn bộ quy tắc cho 2021–2024.
[Nguồn VSDC](https://vsdc.vn/vi/ad/152750).

Input tách hai lịch:

- `market.sessions` chứa các phiên có bar/open/close/decision. Kế thừa
  hợp đồng giả lập mốc 33, panel đầy đủ, không tự điền phiên thiếu.
- `settlement_days` chứa danh sách ngày thanh toán và hai thời điểm
  `shares_at`, `cash_at` có timezone. Có thể có ngày không có bar giao
  dịch. Mỗi ngày là dữ liệu do người tạo kịch bản cung cấp, chưa là
  lịch làm việc của sở, VSDC hoặc ngân hàng.

Độ trễ cổ phiếu và tiền bán được đếm trên lịch thanh toán. Lấy ngày
giao dịch ở chỉ số i, ngày thanh toán là i + lag, rồi lấy giờ trên
ngày đích. Không cộng ngày dương lịch, tự sinh ngày thường, bỏ ngày
nghỉ hoặc suy lịch từ tập giá. Các ngày phải duy nhất, tăng dần;
mọi phiên giao dịch phải có trong lịch thanh toán. Input thiếu phần
đuôi để xác định thanh toán cho bất kỳ phiên nào đều bị chặn trước
khi tạo run, kể cả chiến lược được chọn sẽ không giao dịch phiên đó.

## Thực thi và kế toán

Engine giải phóng tài sản có `available_at <= checkpoint` trước
open, close và decision. Ranh giới đúng bằng được chấp nhận, vẫn
phân biệt một microsecond sau open. T+0 có giờ về đúng open được
dùng cho lệnh tiếp theo; T+0 về 13h không được dùng lúc 09h.

| Tình huống giả lập | Lúc mở cửa | Khi ghi nhận close/decision |
|---|---|---|
| Cổ phiếu về 13h ngày T+2 | Chưa bán được | Tăng số cổ phiếu khả dụng sau khi đến hạn |
| Tiền bán về 13h ngày T+2 | Chưa cấp vốn cho lệnh mua | Chuyển khoản phải thu sang tiền khả dụng |
| Tiền về 15h30, close 15h, decision 16h | Chưa dùng | Close giữ khoản phải thu; decision đã có tiền |
| Tài sản về sau decision cuối | Chưa dùng | Giữ trong ending lots/receivables, không tạo phiên tiếp |

Lệnh chưa khớp không tự thử lại vào buổi chiều hoặc ngày kế tiếp.
Muốn thử lại cần target mới; engine chưa có giá/lệnh thực thi buổi
chiều. Không sử dụng close làm giá mua/bán ngay khi tài sản về.
Giữ phí hai chiều, slippage bất lợi, lô, giới hạn volume/cash/stock,
FIFO, thứ tự bán trước mua và không thanh lý cuối kỳ của mốc 33.

`settlement_events` lưu giờ đến hạn và `observed_at` là checkpoint
đã xử lý. Khi tài sản về vào ngày không có bar, ledger giữ ngày/giờ
đến hạn thực của kịch bản, ghi riêng checkpoint kế tiếp; không bịa
thêm bar hoặc giao dịch. Các timestamp là giả định input, không là
log xác nhận thanh toán thật. `ending_lots`, `ending_receivables`,
`ending_available_cash` có `state_at` là decision cuối; equity curve
là ảnh chụp tại close, không bị cập nhật ngược khi tài sản về muộn.

Tổng tài sản luôn gồm tiền khả dụng + khoản phải thu + giá trị mọi
cổ phiếu, kể cả chưa về. Giải phóng tài sản không tự sinh lợi nhuận.
Dùng Decimal context 50 chữ số; chưa có tick/rounding tiền/phí thật,
corporate actions, cổ tức, margin hoặc ứng trước tiền bán.

## Chạy và replay

```powershell
.\run.ps1 backtest-timed --demo
.\run.ps1 backtest-timed --demo --baseline Q0
.\run.ps1 backtest-timed --demo --baseline Q1 --rebalance-every 2
.\run.ps1 backtest-timed --replay outputs/backtest-timed-synthetic/20261103T022902Z-9c1ddc0f
```

Input tự tạo dùng `--scenario`, tùy chọn `--config`. Demo có ngày
thanh toán riêng với lịch phiên thưa, chỉ là fixture phát triển.
JSON đầu vào chặn khóa trùng, NaN/Infinity, field lạ hoặc số không
đúng schema. Chỉ nhận `explicit_synthetic_settlement_days`, không
cho khai báo đầu vào là lịch HOSE đã được xác minh.

Mỗi run giữ nguyên bytes input/config, scenario sau lịch baseline,
kết quả, nguồn code và hash. Ngoài năm CSV mốc 33 còn có
`settlement_schedule.csv`, `settlement_events.csv`; trade/cash ledger
thêm thời điểm thanh toán. CSV vẫn có header khi không có event/trade.
Replay offline kiểm file set/hash, tái tạo lịch baseline, kế toán và
toàn bộ JSON/CSV; chặn override và đường dẫn ngoài thư mục run của
protocol. Bản chép code chỉ lưu để truy nguyên, không tự thực thi.
Checksum không chứng minh nguồn hoặc người đánh giá độc lập.

## Kiểm chứng và giới hạn

42 test mới kiểm đối chứng integer-lag/timestamp, ranh giới open,
T+2 tiền về trưa, thay đổi giờ theo ngày thanh toán, hai lịch khác
nhau, ngày không có bar, close/decision, khoản chưa về, FIFO/phí,
lô/volume/slippage, timezone, precision, future-price perturbation,
input sai, CLI, CSV và sửa kết quả có reseal. Nhóm backtest có 86
test đạt. Ba lịch manual/Q0/Q1 phát triển mới và ba run v0.1 cũ đều
replay khớp. 104 hash bảo vệ cũ giữ nguyên; không tạo review DB thật,
không gọi LLM hoặc tải thêm dữ liệu giá.
Toàn bộ 766 test và Ruff đạt, còn hai cảnh báo phụ thuộc đã có từ
trước. Frontend không thay đổi nên không chạy lại build/QA giao diện.

Study: `outputs/timed-execution-development/20261103T022901Z-a6f9af92/`.
Xem [data card](../../data/development/timed-execution-v0.1/DATA_CARD.md)
và [validation](../../data/development/timed-execution-v0.1/validation.json).
Code/config/metadata nhỏ nằm trong Git; raw run và CSV ở ngoài Git.

Tiếp theo cần lập lịch HOSE và thanh toán 2021–2024 từ thông báo gốc,
bao gồm sửa đổi, phiên bất thường và phần đuôi thanh toán; phân biệt
giờ hoàn tất ở VSDC với giờ tài sản khả dụng ở tài khoản khách hàng.
Sau đó xác minh điều chỉnh giá/corporate actions và lịch sử universe
trước khi nối dữ liệu thật vào engine. Bản mới vẫn đặt
`eligible_for_execution=false`, `venue_calendar_verified=false` và
`research_result=false`; không nâng snapshot giá hoặc cohort PiT strict.
