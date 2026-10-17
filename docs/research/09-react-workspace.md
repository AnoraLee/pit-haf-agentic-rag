# Dashboard React và luồng phân tích tài liệu

Ngày triển khai: 17/10/2026. Frontend mặc định đổi từ Streamlit sang React/Vite;
FastAPI phục vụ API và bản build trên cùng `http://localhost:8501`, chỉ loopback.
Không triển khai lên Internet, không gọi model cloud hoặc API trả phí.

## Phần đã nối với hệ thống thật

- Tổng quan: số tài liệu/trang, coverage theo mã, trạng thái eligibility và
  kết quả pilot đọc từ artifact trên máy. Không tạo chuỗi giá hoặc điểm số giả.
- Kho bằng chứng: lọc mã/loại/tên, đọc văn bản từng trang, mở URL PDF nguồn,
  xem hash/version và lý do quarantine. Trang scan hiển thị chưa OCR.
- Bàn phân tích: BM25 trên các đoạn nguyên văn tối đa 900 ký tự, overlap 120,
  giữ offset Python trong trang. Điểm là relevance, không phải confidence.
  Chế độ strict giao tài liệu qua gateway **trước** khi tạo đoạn/thống kê BM25;
  danh sách rỗng từ gateway không được đổi thành toàn bộ corpus.
- Trích xuất: người dùng chọn đoạn; backend tìm lại đoạn trên server, không
  nhận context tùy ý từ client. Ollama qwen3:4b chạy tuần tự, context 2048,
  temperature 0, seed 42, tối đa 512 output tokens, không retry tự động ở UI.
  Định danh model được kiểm tra trước/sau; quote/numeric được đối chiếu với nguồn.
- Thị trường: tải Vnstock/KBS theo thao tác; VND cho cổ phiếu, điểm cho VNINDEX,
  lỗi nguồn hiển thị rõ. Thay đổi close đầu/cuối chưa phải backtest.
- Thực nghiệm: chỉ đọc pilot thật hoàn tất, model digest ổn định và replay
  tham chiếu đúng hash manifest/results. Fixture và run dở không thay cho kết quả.

`outputs/interactive-analysis/<run-id>/` giữ metadata tài liệu, context/hash,
config, model inspection, request/response raw và kết quả verifier. Các lần chạy
mới còn giữ query, thứ tự retrieval, score/context hashes và audit gateway riêng
cho evaluator; audit không đưa vào prompt. Kết quả lỗi hoặc bị chặn vẫn được lưu.
Những artifact tương tác này là dấu vết phát triển, không tự cộng vào pilot/benchmark.

Loader xác minh checksum file pages, hash từng trang, identity với registry và
raw PDF. Cache làm mới khi artifact thay đổi. Integrity không chứng minh text
được pypdf đọc đúng; kiểm tra ngữ nghĩa và fidelity với PDF vẫn cần người duyệt.

## Kiểm tra sử dụng thật

- Đã mở bản React trong trình duyệt, xác nhận 11 tài liệu/905 trang/730 trang
  có text và kết nối Ollama. Đã thử menu trên viewport hẹp.
- Tìm "doanh thu lợi nhuận năm 2024": truy xuất được 6 đoạn nguồn. Chạy đoạn
  HPG báo cáo thường niên 2024 trang 29 bằng thao tác UI. Run
  `20261017T101144Z-2c9e299f`, 20,7 giây theo generation wall time.
  Model trả JSON hợp lệ nhưng chép sai đầu câu ("Doanh thu năm 2: ..."); quote
  không tìm thấy trong nguồn nên verifier **chặn**. Không sửa đầu ra để đạt.
- Chọn PiT strict, mốc `2025-04-01T16:00:00+07:00`: UI báo không có bằng chứng
  đủ điều kiện, không gọi model. Không dùng snapshot tải năm 2026 để giả lịch sử.
- Các kiểm thử offline bao phủ raw/page corruption, allowlist rỗng, bất biến
  BM25 trước dữ liệu tương lai, sai quote/numeric/model identity, API không nhận
  context client, timezone thiếu, lỗi dịch vụ và market theo thao tác.
- Bản cuối: 204 tests pass, Ruff và Python lock check pass; frontend build và
  Prettier check pass. Có 2 cảnh báo deprecation từ Starlette/httpx/anyio trong
  tests và cảnh báo directive `use client` từ icon package khi build SPA;
  không có lỗi build. CI GitHub chưa chạy.
- Đã mở FPT báo cáo tiếng Việt trang 49 qua drawer, xem được text và URL nguồn.
  Đã tải FPT 01/01–30/06/2024 qua UI: 120 phiên; giữ nhãn unknown adjustment,
  không gọi biến động close đầu/cuối là kết quả đầu tư. Đã mở trang thực nghiệm.
  Ảnh kiểm tra local ở `outputs/ui-preview/`, viewport hẹp; chưa thay bằng chứng
  kiểm tra giao diện trên nhiều thiết bị/trình duyệt độc lập.

## Chạy và phát triển

```powershell
.\run.ps1 frontend-install
.\run.ps1 frontend-build
.\run.ps1 app
```

Node/pnpm chỉ cần khi cài/build hoặc dùng dev server. Backend phục vụ bản build
qua uvicorn. Sau khi sửa Python cần khởi động lại backend; sau khi sửa React cần
build và tải lại trang, hoặc dùng `frontend-dev` tại cổng 5173 có proxy `/api`.
Mã Streamlit cũ vẫn ở `app.py`, chạy riêng bằng `run.ps1 streamlit` trên 8502.

Kiến trúc tham khảo tài liệu chính thức [Vite](https://vite.dev/guide/) và
[FastAPI](https://fastapi.tiangolo.com/tutorial/first-steps/). Phiên bản thực tế
được khóa trong `frontend/pnpm-lock.yaml` và `uv.lock`.

## Giới hạn và phần tiếp tục

Đã có baseline lexical retrieval và luồng khám phá có kiểm chứng quote, chưa có
hybrid/vector retrieval, graph/peer, phân cấp agent, risk/memory hoặc quant engine.
Không gọi luồng này là toàn bộ PiT-HAF đã hoàn tất. Corpus strict hiện chưa có
tài liệu đủ proof; chưa có nhãn độc lập về số/ngữ nghĩa và chưa có dự báo/backtest.
Các mốc dữ liệu thời gian, gold annotation, quant baseline và phương pháp đầy đủ
tiếp tục theo roadmap; giao diện mới là nơi trình bày kết quả khi các module đạt.
