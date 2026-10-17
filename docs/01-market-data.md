# Bài 1 — Dữ liệu cổ phiếu Việt Nam

Mốc này thêm `VietnamMarketDataProvider` vào repository. Giao diện hiện có dùng
provider Việt Nam với FPT/VND và VNINDEX/điểm. Chưa có backtest, LLM hoặc RAG. Guard lọc theo thời điểm
khả dụng đã được thêm ở [Bài 2](02-point-in-time.md), chưa tích hợp với provider.

## Mục tiêu và cách đọc code

Một provider là module đứng giữa nguồn dữ liệu và chương trình của mình.
Frontend/chiến lược chỉ cần gọi `get_prices()`; chi tiết Vnstock nằm trong module.

Đọc `src/pit_haf/data/vnstock_provider.py` theo thứ tự:

1. `get_prices()`: kiểm tra yêu cầu, tải dữ liệu, chuẩn hóa và gắn metadata.
2. `_download()`: gọi Vnstock với nguồn KBS, `interval="1D"`, `count=None`.
3. `normalize_ohlcv()`: kiểm tra dữ liệu, giới hạn ngày và chuẩn hóa đơn vị.

Ví dụ dùng trong Python (sau khi chạy `uv sync --locked --python 3.11`):

```python
from pit_haf.data.vnstock_provider import VietnamMarketDataProvider

provider = VietnamMarketDataProvider()
prices = provider.get_prices("FPT", "2024-01-01", "2024-03-31")
benchmark = provider.get_prices(
    "VNINDEX", "2024-01-01", "2024-03-31", asset_type="index"
)
print(prices.head())
print(prices.attrs)
```

## Chạy từ thư mục gốc của repo

```powershell
.\run.ps1 test
.\run.ps1 lint
.\.venv\Scripts\python.exe -m pit_haf.data.vnstock_provider --symbol FPT --start 2024-01-01 --end 2024-03-31
.\.venv\Scripts\python.exe -m pit_haf.data.vnstock_provider --symbol VNINDEX --asset-type index --start 2024-01-01 --end 2024-03-31
```

Hai lệnh kiểm thử đầu chạy offline. Hai lệnh sau lấy dữ liệu thật và cần Internet.
Nếu nguồn không trả dữ liệu, chương trình báo lỗi; không biến lỗi thành giá 0.

## Input và output

Input: mã cổ phiếu 3 ký tự hoặc VNINDEX, ngày đầu/cuối dạng YYYY-MM-DD,
loại tài sản. Ngày cuối phải trước hôm nay để tránh lấy nến ngày chưa hoàn tất.

Output: DataFrame gồm `session_date, open, high, low, close, volume`.
Các dòng được sắp theo phiên tăng dần và nằm trong khoảng ngày yêu cầu (bao gồm
cả hai đầu). Không tự tạo phiên ngày nghỉ, không tự điền giá còn thiếu.

Nguồn KBS của Vnstock 4.0.7 trả giá cổ phiếu theo nghìn VND. Module nhân OHLC
cổ phiếu với 1000 để trả VND/cổ phiếu; VNINDEX giữ đơn vị điểm. Khối lượng giữ
nguyên. Việc chuyển đổi dựa vào nguồn và loại tài sản, không đoán theo độ lớn giá.

Metadata trong `prices.attrs` có mã, nguồn KBS, đơn vị, khoảng ngày và thời điểm
tải UTC (`retrieved_at`). Metadata này đang nằm trong bộ nhớ; gọi `to_csv()`
không tự lưu metadata. Snapshot và file metadata riêng là công việc ở mốc sau.

## Giới hạn cần hiểu trước khi dùng cho khóa luận

- `session_date` chỉ là nhãn ngày của nến. Giờ `07:00` ở dữ liệu gốc không
  chứng minh giá đóng cửa đã tồn tại lúc 7 giờ sáng.
- Lọc `[start, end]` chưa bảo đảm Point-in-Time. Bước sau cần `available_at`
  (thời điểm thực sự có thể biết dữ liệu) và `decision_at` (thời điểm quyết định).
- `retrieved_at` là lúc tải về hiện tại, khác với thời điểm công bố lịch sử.
- Tình trạng điều chỉnh cổ tức/chia tách chưa xác minh (`adjustment_status=unknown`).
  Không xem chuỗi này là bản lưu nguyên trạng tại thời điểm lịch sử.
- Lọc dữ liệu ngoài không loại bỏ kiến thức tương lai đã học trong trọng số LLM.
- Nguồn trực tuyến có thể thay đổi hoặc thiếu phiên. Số dòng hợp lệ không chứng
  minh lịch giao dịch đầy đủ. Mốc sau cần đối chiếu lịch và lưu snapshot.

## Bài tập nhỏ

1. Giải thích vì sao FPT giá 100 ở nguồn có thể thành 100000 ở output,
   nhưng VNINDEX 1200 vẫn là 1200.
2. Chạy với `--end 2024-01-10`. Ngày lớn nhất trong output phải như thế nào?
3. Đọc test `test_inclusive_range_excludes_later_data`: dòng ngày 03/01
   phải biến mất khi ngày cuối là 02/01. Đây đã đủ chứng minh PiT chưa? Vì sao?

Khi báo cáo: “Em đã tách kết nối Vnstock khỏi giao diện, chuẩn hóa đơn vị,
kiểm tra dữ liệu và viết kiểm thử offline. Module này là nền tảng cho baseline;
kiểm soát thời điểm công bố và backtesting sẽ được bổ sung ở các bước tiếp theo.”
