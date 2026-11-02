# 33 — Động cơ thực thi trên kịch bản giả lập

Ngày 02/11/2026. Bổ sung nền tảng định lượng M2 với protocol
`synthetic_execution_v0.1`. Đây là kiểm tra kỹ thuật bằng dữ liệu tự tạo,
chưa là backtest lịch sử, kết quả VN30 hoặc thực nghiệm đủ năm baseline.

## Phần đã triển khai

- Hợp đồng input chặt: lịch phiên tường minh, thời điểm có timezone,
  OHLCV đủ từng mã/phiên, target đầy đủ universe, long-only/cash và tổng
  trọng số không vượt 1. Thiếu bar thì dừng; không bù giá hoặc tự dời phiên.
- Tính số lượng từ NAV và giá đóng cửa tại phiên quyết định; chỉ xử lý
  lệnh ở **open phiên tiếp theo trong lịch được cung cấp**. Không tính
  số lượng từ open tương lai. Lệnh cuối mẫu không có phiên khớp được
  ghi expired; không bán ép toàn bộ danh mục ở cuối kỳ.
- Làm tròn xuống theo lô; phí mua/bán và slippage bất lợi theo bps.
  Không âm tiền mặt, không bán quá số cổ phiếu đã thanh toán. Cho khớp
  một phần khi thiếu tiền/khối lượng/cổ phiếu bán được. Giá sau slippage
  vượt high/low thì không khớp. Lệnh chỉ có hiệu lực một phiên, không tự
  thử lại phần còn thiếu.
- Theo dõi từng lô cổ phiếu, bán FIFO trong các lô đã thanh toán, và tiền
  bán chờ về. Cả hai độ trễ đều là tham số số phiên của kịch bản. Tiền
  bán chờ về vẫn nằm trong NAV nhưng chưa được dùng để mua; cổ phiếu chờ
  thanh toán vẫn được định giá nhưng chưa bán được.
- Sổ lệnh, giao dịch, tiền mặt, vị thế từng phiên và đường NAV. Tách
  đầy đủ/khớp một phần/không khớp/hết hiệu lực; giữ lý do, giá tính số
  lượng, tham chiếu open, phí và phần tiền chờ thanh toán.
- Lợi suất ròng đánh dấu theo giá đóng cửa, max drawdown, tổng phí,
  slippage và turnover hai chiều. Không tự tạo nhãn dự báo, Sharpe hoặc
  lợi suất năm từ vài phiên giả lập.

Trong một phiên, tiền đến hạn được giải phóng trước, sau đó lệnh bán
rồi lệnh mua, mỗi phía theo thứ tự mã chữ cái. Quy tắc phân bổ này có
thể ưu tiên mã đứng trước khi thiếu tiền; được ghi rõ để tái lập, chưa
phải tối ưu phân bổ danh mục. Số lượng target được tính từ close/NAV
phiên trước và không tự điều chỉnh theo giá khớp để đạt lại trọng số.

Số tiền/giá/trọng số nhập bằng chuỗi thập phân. Tính toán dùng Decimal
50 chữ số với context cố định; không phụ thuộc context của chương trình
gọi. Chưa áp dụng quy tắc làm tròn phí, tick giá hoặc thuế/phí thực tế.

## Phạm vi Q0/Q1 và giá thật

`manual` chạy lịch target đã cung cấp. Hai bộ tạo lịch có thêm:

| ID | Cơ chế giả lập | Chưa có |
|---|---|---|
| Q0 | Chia đều vốn theo universe cố định tại phiên quyết định đầu, giữ sau lượt mua kế tiếp | Xác minh universe lịch sử, thực thi thị trường thật |
| Q1 | Target đều mỗi N phiên được cung cấp, N phải khai báo tường minh | Lịch tái cân bằng đã khóa cho thực nghiệm cuối |

Trọng số chia đều làm tròn xuống tám chữ số; phần dư giữ ở tiền mặt.
Các policy này không đọc lợi suất để chọn ngày/mã và không gán dự đoán
UP/DOWN giả. Chưa có Q2 VNINDEX comparator, Q3 momentum/MA hoặc Q4
logistic regression. Chưa có policy thoát theo horizon năm phiên cho
dự đoán agent; không dùng target thủ công thay thế policy này.

Runner hiện **chỉ nhận** `kind=synthetic_execution_diagnostic`,
`adjustment_status=synthetic_no_corporate_actions`,
`calendar_basis=explicit_synthetic_sessions`, `currency=scenario_units`.
Không nhận giá thật thiếu bằng chứng rồi đổi nhãn thành PiT strict.
Ngày/giờ, lô, phí, volume cap và thanh toán trong demo là tham số tự tạo,
không là lịch/quy định sàn Việt Nam. Target bên ngoài chưa có kiểm tra
lineage/thông tin khả dụng; input hợp lệ không chứng minh target hợp lệ PiT.

Volume cả ngày và high/low phiên khớp chỉ là ràng buộc mô phỏng hậu nghiệm,
không tham gia tính số lượng ở phiên quyết định và không gửi cho agent.
Chúng chưa mô tả độ sâu/khả năng khớp tại open. Chưa xử lý corporate
actions, cổ tức, ngừng/hủy niêm yết, biên độ hoặc hàng đợi trong ngày.

## Chạy và tái lập

Không cần Ollama hoặc tải dữ liệu. Chạy ở thư mục gốc repository:

```powershell
.\run.ps1 backtest-synthetic --demo
.\run.ps1 backtest-synthetic --demo --baseline Q0
.\run.ps1 backtest-synthetic --demo --baseline Q1 --rebalance-every 2
.\run.ps1 backtest-synthetic --replay outputs/backtest-synthetic/20261102T142514Z-6ffe1c85
```

Tự tạo input theo schema `Scenario` trong `backtest/contracts.py`, dùng
`--scenario <file.json>`, có thể chọn `--config <file.json>`. Các target
trọng số cung cấp sẵn chưa phải output của mô hình. Replay dùng config/baseline đã
lưu, từ chối override hoặc đường dẫn ngoài `outputs/backtest-synthetic`.

Mỗi run giữ nguyên bytes input/config, scenario sau khi tạo lịch, bản
chép mã nguồn, manifest/hash, `result.json`, `orders.csv`, `trades.csv`,
`cash_ledger.csv`, `equity_curve.csv` và `positions.csv`. CSV có header
kể cả khi không có giao dịch. Replay kiểm toàn vẹn, tạo lại lịch từ
input/baseline, tính lại bằng mã hiện tại rồi đối chiếu toàn bộ JSON/CSV.
Bản chép nguồn lưu dấu phiên bản, không được tự động thực thi khi replay.
Nếu mã mới khác hành vi, replay báo sai lệch; cần môi trường/commit gốc
để đối chiếu phiên bản cũ. Checksum không là xác thực độc lập nguồn dữ liệu.

Raw outputs ở ngoài Git. Repository chỉ chứa code/config/data card và
metadata nhỏ; người khác chạy `--demo` để tạo run riêng hoặc khôi phục
đúng thư mục output khi muốn replay một ID cụ thể.

## Kiểm chứng và bước tiếp theo

44 kiểm thử mới kiểm bằng phép tính tay, không đọc đáp án OCR: gap open,
phí hai chiều, slippage, lô/volume, nghỉ phiên, FIFO/thanh toán, phần tiền
chưa về cuối kỳ, cash-only, future-price perturbation, context Decimal,
input sai, CLI và sửa artifact có reseal. Ba lượt đã chọn trước
manual/Q0/Q1 đều replay đạt; 83 hash bảo vệ cũ giữ nguyên. Không ghi
review DB thật, không thêm lượt gọi LLM hoặc tải dữ liệu thị trường.
Toàn bộ 645 kiểm thử và Ruff đạt; giữ hai cảnh báo phụ thuộc test cũ.
Frontend không đổi ở mốc này nên không chạy lại build/QA giao diện.

Study: `outputs/backtest-development/20261102T142512Z-0471bf7f/`.
Xem [data card](../../data/development/backtest-synthetic-v0.1/DATA_CARD.md)
và [validation](../../data/development/backtest-synthetic-v0.1/validation.json).
Các chỉ số lợi suất trong output chỉ kiểm tra máy tính kế toán, không
là bằng chứng chiến lược có hiệu quả tài chính.

Tiếp theo cần xác minh lịch phiên, corporate actions/điều chỉnh giá,
đơn vị, tính khả dụng và các quy tắc thực thi theo giai đoạn; tạo adapter
giá có provenance và cohort được khóa. Sau đó mở baseline còn thiếu và
policy horizon, kiểm trên cùng dữ liệu/chi phí trước khi chạy nghiên cứu.
Luồng chứng cứ/OCR và thu bằng chứng công bố tiếp tục độc lập theo mốc 32.
