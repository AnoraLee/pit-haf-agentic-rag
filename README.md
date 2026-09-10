# PiT-HAF — Dự án khóa luận được phục hồi

Phục hồi ngày 10/09/2026 từ cuộc trò chuyện do chủ dự án cung cấp:
https://chatgpt.com/s/cx_6aa22a7bbaa481918f53df4155f19eb1

## Mở và chạy trên máy này

Mở thư mục chứa README này trong VS Code. Trong PowerShell tại thư mục này:

```powershell
.\run.ps1 test
.\run.ps1 lint
.\run.ps1 app
```

Frontend: http://localhost:8501. Chạy kiểm tra nguồn FPT bằng `.\run.ps1 data`.
Không cần kích hoạt môi trường bằng Activate.ps1; script gọi Python trong `.venv`.

Môi trường mới được dựng bằng uv, Python 3.11, với các phiên bản đã xác nhận
trong lịch sử: NumPy 2.2.6, Pandas 2.3.3, Vnstock 4.0.7. `uv.lock` ghi các
dependency của lần phục hồi này, không phải lockfile của máy cũ.
Khi chuyển máy, cài uv rồi chạy `uv sync --python 3.11` tại thư mục dự án.

## Phạm vi phục hồi

- `src/pit_haf/data/vnstock_provider.py`: trích từ bản diff gốc và áp dụng bản sửa ISO8601 cuối.
- `tests/test_vnstock_provider.py`: lấy bộ kiểm thử gốc và bản sửa cuối; có thể khác định dạng sau Ruff.
- `app.py`: lấy khối mã frontend cuối được chia sẻ và áp dụng bản sửa import. Vẫn là prototype AAPL/Yahoo/USD.
- `docs/01-market-data.md`: bài hướng dẫn gốc về provider.
- `docs/de-cuong-nghien-cuu-pit-haf.md` và báo cáo đọc paper: tài liệu lịch sử, chưa cập nhật theo hướng Việt Nam cuối cùng.
- `docs/translations/`: khôi phục nội dung Markdown bản dịch; chưa có lại DOCX và các hình gốc.
- `docs/lich-su-khoi-phuc.txt`: bản chép nội dung trao đổi để tra cứu; định dạng có thể bị gộp và chứa các đề xuất cũ.
- `pyproject.toml`, `uv.lock`, `run.ps1`, README và ghi chú tiến độ: tạo lại cho máy này.

Không tìm thấy thư mục cũ `D:\CODE\KLTN\KhoaLuan\pit-haf` trên máy này.
Đây là khôi phục từ nội dung chia sẻ, không phải bản sao ổ đĩa hay lịch sử Git.
Không có lại API key, model Ollama, cache giá, môi trường Poetry và repository
thực nghiệm AI Hedge Fund riêng trên máy cũ.

## Mốc nghiên cứu cần tiếp tục

Hướng mới nhất: Point-in-Time Agentic-RAG hỗ trợ phân tích cổ phiếu Việt Nam.
Đánh giá chất lượng bằng chứng, rò rỉ thời gian và khả năng tái lập; hiệu quả
giao dịch là một khía cạnh đánh giá, không phải cam kết sinh lời.

Đã có tầng tải/chuẩn hóa dữ liệu. `session_date` chưa phải `available_at`;
lọc ngày chưa bảo đảm Point-in-Time và không loại bỏ kiến thức tương lai của LLM.

Thứ tự tiếp tục: hiểu provider → Point-in-Time Guard → Buy & Hold/VNINDEX/MA
→ frontend Việt Nam → single LLM/Ollama → Naive RAG → Agentic-RAG/verifier
→ ablation và thí nghiệm khóa → luận văn.

Mỗi bước nên kèm input/output, kiểm thử lỗi và phần tự giải thích khi bảo vệ,
theo mong muốn học từng module trong cuộc trò chuyện gốc.
