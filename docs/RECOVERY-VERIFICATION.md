# Kiểm tra bản phục hồi — 10/09/2026

Đây là ghi chú lịch sử, không phải kết quả kiểm tra của môi trường hiện tại.
Xem README và tài liệu module để biết trạng thái triển khai mới nhất.

- Python 3.11.9, môi trường `.venv` riêng.
- Pytest: **23 passed in 5.20s**.
- Ruff: **All checks passed!**.
- FPT qua module gốc: **120 dòng**, từ 02/01/2024 đến 28/06/2024,
  khi yêu cầu khoảng 01/01/2024–30/06/2024. Đơn vị VND, nguồn KBS.
- Streamlit khởi động thành công tại `http://127.0.0.1:8501`.
- Chưa chạy lại backtest hay LLM: các phần này chưa được triển khai trong PiT-HAF gốc.
- Chưa khôi phục DOCX, hình gốc, model Ollama hoặc repository benchmark riêng.

Các kiểm thử trên xác nhận tầng dữ liệu và khả năng khởi động. Chúng không
chứng minh dữ liệu Point-in-Time hoàn chỉnh hay hiệu quả đầu tư.

## Nguồn và phạm vi khôi phục

Dự án được khôi phục ngày 10/09/2026 từ nội dung trao đổi do chủ dự án cung cấp:
https://chatgpt.com/s/cx_6aa22a7bbaa481918f53df4155f19eb1

- Provider và các kiểm thử được lấy từ bản diff đã chia sẻ, có bản sửa ISO8601.
- `app.py` được lấy từ mã frontend đã chia sẻ, có bản sửa import; vẫn là prototype
  AAPL/Yahoo/USD.
- Tài liệu nghiên cứu và bản dịch được khôi phục ở dạng Markdown; chưa có lại
  DOCX và hình gốc.
- `pyproject.toml`, `uv.lock`, `run.ps1` và ghi chú môi trường được tạo cho lần
  khôi phục này. Lockfile không phải bản sao lockfile của máy cũ.
- Không tìm thấy thư mục cũ `D:\CODE\KLTN\KhoaLuan\pit-haf` trên máy này.
  Việc khôi phục dựa trên nội dung chia sẻ, không phải bản sao ổ đĩa/lịch sử Git.
- Chưa có lại API key, model Ollama, cache giá, môi trường Poetry hoặc repository
  thực nghiệm AI Hedge Fund riêng trên máy cũ.

README đã được biên tập ngày 06/10/2026 để tập trung vào cách cài đặt và trạng
thái dự án; thông tin lịch sử được gom tại đây. Các nguồn và trích dẫn nghiên
cứu được giữ nguyên.

## Kiểm tra mốc Point-in-Time Guard — 06/10/2026

- Python 3.11.17, thư viện theo `uv.lock` trong `.venv`.
- `run.ps1 test`: **63 passed**, gồm 23 kiểm thử provider và 40 kiểm thử Guard.
- `run.ps1 lint`: **All checks passed!**.
- `run.ps1 pit-demo`: chọn bản gốc; loại bản sửa và tin có thời điểm khả dụng
  sau thời điểm quyết định. Đầu vào là dữ liệu giả định.
- `git diff --check`: không có lỗi khoảng trắng trong diff.
- Chưa kiểm tra lại nguồn dữ liệu trực tuyến ở mốc này. Guard chưa nối với
  provider/frontend; chưa có backtest, LLM hoặc kết quả nghiên cứu mới.
