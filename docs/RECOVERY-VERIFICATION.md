# Kiểm tra bản phục hồi — 10/09/2026

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
