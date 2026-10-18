# PiT-HAF

Đồ án nghiên cứu Point-in-Time Agentic-RAG hỗ trợ phân tích cổ phiếu Việt Nam.
Trọng tâm là chất lượng bằng chứng, kiểm soát rò rỉ thời gian và khả năng tái lập.
Dự án dùng LLM có sẵn; dữ liệu phục vụ truy xuất và đánh giá, không dùng để
huấn luyện một LLM mới.

## Cài đặt và chạy

Yêu cầu Python 3.11 và uv. Giao diện chính dùng React + Vite, backend FastAPI.
Để build frontend từ source cần Node.js 22.12+ hoặc 24 và pnpm 11.25.0.
Trong PowerShell tại thư mục dự án:

```powershell
uv sync --locked --python 3.11
.\run.ps1 frontend-install
.\run.ps1 frontend-build
.\run.ps1 test
.\run.ps1 lint
.\run.ps1 doctor
.\run.ps1 pit-demo
.\run.ps1 pilot-data --extract-existing
.\run.ps1 llm-pilot --cases configs/smoke_cases.jsonl --smoke
.\run.ps1 app
```

Trên máy hiện tại, `.venv` đã được tạo và có các thư viện cần thiết. Các lệnh
`run.ps1` gọi trực tiếp Python trong `.venv`, không cần kích hoạt bằng Activate.ps1.

Frontend React: <http://localhost:8501>. `app` phục vụ bản build frontend và API
trên cùng cổng, chỉ bind loopback. Máy này đã cài thư viện và build frontend;
chỉ cần `.\run.ps1 app` sau khi tắt server cũ. Không cần chạy Streamlit.
Nếu máy khác chưa có pnpm, cài Node.js rồi chạy `npm install --global pnpm@11.25.0`.
Script tự nhận pnpm trong runtime Node của máy hiện tại nếu chưa có trên PATH.
Khi sửa giao diện: chạy `frontend-dev` ở terminal thứ hai, truy cập cổng Vite
hiển thị (mặc định 5173); `/api` được proxy tới backend 8501.
Giao diện Streamlit cũ được giữ qua `.\run.ps1 streamlit` trên cổng 8502.

Chạy `.\run.ps1 data` để tải giá FPT từ
Vnstock/KBS; lệnh này cần Internet. Test, lint và `pit-demo` chạy offline.
`pit-demo` chỉ dùng ví dụ giả định, không tạo kết quả thực nghiệm tài chính.
`doctor` lưu số đo môi trường, trạng thái dịch vụ Ollama và snapshot mã nguồn
tại `outputs/preflight/`. Lệnh này không chạy inference hoặc tải model.

Các phiên bản chính được khóa trong `uv.lock`: NumPy 2.2.6, Pandas 2.3.3,
Vnstock 4.0.7. Môi trường trên máy hiện tại dùng Python 3.11.17.

## Những phần đã có

- `src/pit_haf/data/vnstock_provider.py`: tải OHLCV cho cổ phiếu Việt Nam/VNINDEX,
  kiểm tra dữ liệu và chuẩn hóa giá sang VND hoặc điểm chỉ số.
- `src/pit_haf/data/point_in_time.py`: chọn dữ liệu có `available_at <= decision_at`,
  xử lý các phiên bản sửa đổi và trả audit về kết quả lọc.
- `tests/`: kiểm thử offline cho provider, Guard, snapshots/gateway, local adapter,
  resource sampling, diagnostic và UI; kết quả mới trong báo cáo milestone.
- `frontend/`: dashboard React responsive gồm tổng quan, kho bằng chứng,
  bàn phân tích, thị trường và thực nghiệm. Số liệu từ artifact thật trên máy.
- `src/pit_haf/ui/`: API FastAPI, loader kiểm checksum PDF/trang, BM25 baseline
  lọc gateway trước khi tính thống kê corpus, trích xuất local có dấu vết và
  đối chiếu trích dẫn/số liệu. Chưa phải toàn bộ hệ agent phân cấp/backtest.
- `app.py`: giao diện Streamlit cũ, giữ để đối chiếu provider; không còn là
  frontend mặc định.
- `src/pit_haf/research/doctor.py`: kiểm tra môi trường/local service, lưu
  Git revision, dirty diff, hashes và source snapshot, không trả mock inference.
- `.github/workflows/offline-checks.yml`: CI test/lint đã push; kết quả GitHub Actions
  chưa xác nhận qua API. Kết quả local được ghi riêng, không thay kết quả CI.
- `src/pit_haf/data/`: evidence/snapshots/gateway cho provenance, raw blobs
  SHA-256, SQLite append-only và giao đúng revision qua Guard. Bằng chứng thiếu
  thời điểm/phiên bản lịch sử bị quarantine; fixture bị loại theo mặc định.
- `src/pit_haf/data/pilot.py`: thu thập PDF theo danh sách nguồn official, lưu acquisition
  failures, trích text theo trang và replay snapshot offline; chưa OCR.
- `src/pit_haf/llm/`: structured local adapter, retry/timeout hữu hạn,
  digest/raw outputs và pilot trích xuất; chưa phải Agentic-RAG/dự báo.
- [Pilot data card](data/pilot/DATA_CARD.md): nguồn, coverage, provenance index,
  extraction quality, rights và giới hạn chưa có proof lịch sử.
- [Corpus v0.2](data/corpus/v0.2/DATA_CARD.md): 29 tài liệu được chọn từ 32 raw
  versions/34 URL cấu hình, 10 mã/8 nhóm ngành, 3.243 trang. Phủ 21/30 ô báo cáo
  thường niên 2022–2024; vẫn chưa có evidence đủ điều kiện PiT strict. Pilot cũ
  và kết quả 24 đoạn được giữ nguyên; không phải đánh giá model trên corpus mới.

Corpus hiện hành được mở rộng ở [v0.3](data/corpus/v0.3/DATA_CARD.md): 13 mã,
264 PDF khác nhau/17.915 trang; manifest gồm 282 báo cáo nhiều năm/quý.
Số PDF đã chọn, trang có text, lỗi, backlog
OCR và độ phủ thực tế được ghi trong data card; số URL cấu hình không phải số
báo cáo đã qua kiểm tra. Có bộ lọc năm/phạm vi và phân trang trong kho tài liệu.
PDF lưu local; GitHub chứa mã, danh mục và checksum. Xem
[hướng dẫn batch, retry và ghép snapshot](docs/research/11-corpus-v03.md).

Để mở rộng/tái trích corpus v0.2 dùng
`.\run.ps1 pilot-data --sources configs/corpus_sources_v0_2.json --skip-registered`
hoặc `--extract-existing` khi chỉ replay local. Công cụ `corpus-coverage` tạo
bảng coverage và bản lọc theo review có pin hash; xem
[lệnh và giới hạn v0.2](docs/research/10-corpus-expansion.md).

Ngày 17/10/2026: Ollama 0.40.5 và qwen3:4b Q4_K_M đã cài trên máy này.
[Báo cáo cài đặt và pilot](docs/research/08-local-pilot-results.md) ghi artifact,
cấu hình và số đo thực tế; model vẫn là ứng viên phát triển.

Môi trường có thêm pypdf trong `uv.lock`. Registry metadata của Vnstock/vnai/
ezchart trả 404 lúc cài; project dùng URL wheel bất biến từ files.pythonhosted.org,
giữ đúng ba phiên bản và SHA-256 của lock cũ. Không thay phiên bản package cũ.

## Giới hạn hiện tại

`session_date` là nhãn phiên, `retrieved_at` là lúc tải dữ liệu. Cả hai không
thay thế `available_at`, thời điểm phiên bản dữ liệu thực sự có thể quan sát.
Provider hiện chưa có lịch sử công bố/phiên bản đủ để đưa giá vào Guard; Guard
sẽ từ chối dữ liệu thiếu các trường bắt buộc. Không tự gán giờ đóng cửa thành
thời điểm khả dụng đã xác minh.

Guard kiểm soát timestamp được cung cấp, không chứng minh nguồn đã gắn đúng
timestamp hoặc dữ liệu giá chưa bị điều chỉnh. Lọc dữ liệu ngoài cũng không
loại bỏ kiến thức tương lai trong trọng số LLM. Đã có adapter và pilot trích xuất
local; retrieval, graph/agent/memory và backtest đầy đủ còn theo roadmap.

## Hồ sơ nghiên cứu và lộ trình

[Hồ sơ nghiên cứu](docs/research/README.md) tập hợp audit, task/label/timeline,
literature/contribution, contracts và sơ đồ, experiment matrix/rubric, roadmap
và data/local feasibility. [Đề cương](docs/de-cuong-nghien-cuu-pit-haf.md) lấy
Việt Nam làm thị trường chính. Task đề xuất là báo cáo doanh nghiệp có bằng
chứng tại `decision_at` và dự đoán hướng lợi suất 5 phiên; protocol chưa freeze.

Giữ đầy đủ scope qua 7 mốc: audit/pilot; dữ liệu/gateway/baseline định lượng;
LLM và PiT single-agent retrieval; graph/peer và phân cấp; verifier/risk/memory/
audit/UI; full experiment matrix; gói tái lập và luận văn. Khung 8–12 tuần là
ước lượng ban đầu, không bảo đảm hoàn tất theo lịch hoặc thu gọn thành phần.

Model nhỏ như qwen3:4b đang được đo ở pilot; chưa chốt chất lượng tài chính.
Dataset phục vụ bằng chứng truy xuất, nhãn đánh giá, split phát triển/test và
baseline định lượng. Không training LLM vẫn cần những dữ liệu này để kiểm chứng.

Đọc [Bài 1](docs/01-market-data.md), [Bài 2](docs/02-point-in-time.md), rồi
[hướng dẫn M1](docs/research/07-milestone-1.md) để tự chạy và giải thích thiết kế.
Các paper/bản dịch là tài liệu tham khảo, không phải kết quả của dự án.
Lịch sử khôi phục và các kiểm tra cũ nằm trong
[ghi chú lịch sử](docs/RECOVERY-VERIFICATION.md).
