# Data feasibility và local LLM pilot — 06/10/2026

Đây là kế hoạch và số đo tại06/10. Trạng thái cài Ollama và kết quả chạy mới
ngày17/10 được ghi riêng trong [báo cáo08](08-local-pilot-results.md).

## Đã kiểm tra nguồn nào?

Đã mở trang công khai qua web để khảo sát. Không đồng nhất việc trang đọc được
với pipeline ingestion chạy, timestamp lịch sử xác minh hoặc quyền phát hành
lại một dataset. Chưa thu thập corpus/raw snapshots tài chính vào repository.

| Nguồn | Quan sát có thật | Availability/version | Điều khoản và hành động tiếp |
|---|---|---|---|
| [FPT IR reports](https://fpt.com/en/ir/report?tab=3) | listing annual reports nhiều năm; [PDF 2024 trên domain FPT](https://fpt.com/-/media/project/fpt-corporation/fpt/ir/information-disclosures/year-report/2025/april/20250402---fpt---bao-cao-thuong-nien-nam-2024.pdf) được tìm thấy | listing/file name chưa chứng minh giờ công bố hoặc bytes revision lịch sử | [terms](https://fpt.com/en/terms-of-use): sử dụng cá nhân/phi thương mại có attribution; xác minh quyền chia sẻ/raw trước phát hành |
| [Hòa Phát BCTC](https://www.hoaphat.com.vn/quan-he-co-dong/bao-cao-tai-chinh) | listing có ngày; BCTC hợp nhất Q1/2026 ghi 29/04/2026; [PDF](https://file.hoaphat.com.vn/hoaphat-com-vn/2026/04/bctc-hop-nhat-quy-i-2026.pdf) mở được, 37 trang | chỉ quan sát date precision trên listing; PDF parser có text, chưa QA/OCR/số liệu; chưa chứng minh revision integrity | [terms](https://www.hoaphat.com.vn/trang/dieu-khoan-su-dung.html): cá nhân/phi thương mại kèm bản quyền; không suy ra bulk download/redistribution vô điều kiện |
| [Vietcombank IR](https://www.vietcombank.com.vn/vi-VN/Nha-dau-tu) | trang IR mở được; có thông tin báo cáo/nhà đầu tư | chưa xác nhận API/listing/PDF revision/timestamp để ingest | terms/robots/download permission chưa xác minh; khảo sát chi tiết trước adapter |
| [HOSE](https://www.hsx.vn/) | HTML qua công cụ chỉ yêu cầu JavaScript | chưa lấy công bố/lịch/giờ từ site bằng pipeline | khảo sát endpoint public/robots/terms; không bypass access control |
| [HNX](https://hnx.vn/) | một lần fetch timeout | không kết luận nguồn không tồn tại hoặc không truy cập được bằng cách khác | retry có backoff, xem nguồn official thay thế; coverage còn unknown |
| Vnstock 4.0.7/KBS | provider và 23 offline tests đang chạy | lịch phiên, adjustment/version availability chưa xác minh lại online | audit package/data-source terms và sample downloads trước snapshot rộng |

Các ngày nêu trên là metadata đang hiển thị, không tự đưa vào strict cohort.
Đặc biệt ngày ký trong PDF và kỳ báo cáo không thay published/available time.
Terms được kiểm tra cho FPT/HPG; robots, hạn mức và điều khoản từng file/nguồn
còn phải ghi vào source register trước thu thập tự động rộng. Không gửi email
xin phép hoặc đăng tải raw dataset khi chưa có yêu cầu cụ thể.

## Pilot thu thập và data card

Mục tiêu ban đầu: FPT, HPG, VCB, mỗi mã 8 tài liệu/case thật = 24 case bao gồm
BCTC/giải trình/thường niên, text/scanned và period/units khác nhau. Đây là mục
tiêu kiểm tra, **hiện chưa có 24 case**. Missing category được ghi thiếu; không
phát minh scanned/revision cases để đủ quota. Có peer documents bổ sung cho
từng ngành sau khi xác minh tính so sánh.

Universe khảo sát 10 mã đề xuất: FPT/CMG/ELC; HPG/HSG/NKG; VCB/CTG/MBB/ACB.
Đây là danh sách candidate theo nhóm hoạt động, chưa xác minh listing history,
ngành chi tiết hoặc PiT coverage. Không là universe đã chọn. Cửa sổ khảo sát
đề xuất 2021–2025, mở rộng khi đủ nguồn để có nhiều giai đoạn. Quyết định cuối
dựa vào registry lịch sử/coverage, không future returns. Nếu chỉ có survivors,
data card công bố bias và cần tìm lịch sử delisting/constituents bổ sung.

Source register lưu URL, publisher, loại nguồn, retrieval result/date, terms/
robots reference, rate policy, timestamp precision/proof và revision proof.
Acquisition log lưu response status/headers; HTTP Last-Modified chỉ là metadata
server, không xác nhận lịch sử publication. Lưu raw bytes bất biến theo SHA-256,
metadata JSON/SQLite, extractor version và hash text. Lỗi/missing -> quarantine
với reason; giữ coverage counts. CSV/attrs đơn lẻ chưa đủ.

Data card cần: population/selection criteria; industry/listing history; periods;
download success/failure; text/scanned; language; verified/date-only/unverified
timestamps; original/revision coverage; strict/conservative cohort counts;
rights/attribution; adjustment/corporate actions; exclusions và survivorship.

QA mẫu: so raw page với text/OCR, số âm trong ngoặc, dấu phân cách/dấu thập
phân, triệu/tỷ/VND, YoY/QoQ, quý/năm, hợp nhất/riêng lẻ, audited/restated.
Chọn ít nhất 5 bảng/case/loại nguồn cho pilot QA (đề xuất); kiểm tổng/đơn vị bằng
calculator/Decimal và label người chấm. Ngân hàng dùng cấu trúc NIM/nợ xấu/vốn
phù hợp, không ép cùng revenue/margin schema của thép/công nghệ. Không dùng số
liệu hiện tại đã sửa với ngày bản gốc.

Acceptance feasibility M1: URL/terms/access có evidence, có raw sample+locator,
có thống kê thiếu metadata và policy quarantine, đủ case kiểm parser/model.
Acceptance dataset M2: version/time proof cho strict samples, calendar/price
coverage, hash manifest, gold labels tách evaluator. Date-only cohort theo
[policy](01-task-protocol.md) là sensitivity riêng; không gọi nguồn thiếu giờ
là verified second-precision.

## Hardware và model: đo so với giả định

Đã đo: Ryzen5 5600H 6/12; RTX3050 Laptop4096MiB, driver566.07; RAM tổng15,4GiB,
RAM trống khoảng2,7GiB ở lần audit. Ollama default11434 connection refused, chưa
thấy executable/process trong phạm vi kiểm tra. `ollama` Python package không
cài server/model. Chưa đo bất cứ prediction/JSON/fidelity/throughput nào.

[qwen3:4b library](https://ollama.com/library/qwen3:4b) hiện ghi 4,02B/Q4_K_M và
artifact khoảng2,5GB. Đây là **ứng viên**, không cấu hình được chốt. Dung lượng
file không phải tổng RAM/VRAM, còn KV cache/context/runtime/offload.
[Ollama GPU docs](https://docs.ollama.com/gpu) và
[FAQ](https://docs.ollama.com/faq) là nguồn kiểm support/placement/concurrency;
phải đo placement thực tế bằng `ollama ps` và resource sampling. Không kết luận
"vừa 4GB nên chạy tốt". 8b chỉ cân nhắc sau benchmark, không mặc định thay4b.

Không tự đóng ứng dụng để lấy RAM. Chưa tải model/server trong lượt khảo sát:
RAM trống ít và chưa có corpus24 case để đo fidelity. Điều này không cản viết
adapter/tests hoặc xây data/gateway. Cài official Ollama+candidate là bước pilot
local khi môi trường/corpus chuẩn bị đủ; không cần API trả phí cho bước đầu.

## Benchmark 24 case thật và cấu hình cố định

1. Khóa samples/locators/hash: 8 case mỗi ngành, gồm quote+number/unit,
   summarization, conflict/insufficient evidence và một nhóm verifier errors.
   Chỉ dùng development, không chọn model trên final test.
2. Lưu `ollama --version`, `/api/tags` digest, `/api/show` details, quantization,
   context, thinking mode, generation settings và prompt hash. Không chỉ tag.
3. Config thử: qwen3:4b, num_ctx4096, temperature0, seed42, num_predict512,
   thinking=false (xác nhận model/API hỗ trợ), một request; cold/warm runs riêng.
   Đo context2048/4096 trên development; không đổi âm thầm khi OOM.
4. Structured JSON + Pydantic validation; timeout đề xuất180s và retry≤1.
   Lưu raw request/response và từng attempt, token counters, duration, done/fail.
   Chưa có adapter/benchmark runner thực hiện bước này trong mốc hiện tại.
5. Tách scoring deterministic (quote/value/unit/calc) và human rubric tiếng
   Việt/semantic support. Gold không lấy từ chính model đang thử.
6. Sample RAM/VRAM mỗi0,5–1s, process/runtime memory khi khả thi; peak đo sampling
   được ghi có thể bỏ lỡ spike. Đo cold load, median/p95 và output tokens/s;
   actual token count từ backend, không đoán theo số từ tiếng Việt.
7. Lặp3 lần một subset6 case chọn trước; lưu mọi run để đo nondeterminism.

Ngưỡng engineering **đề xuất trước pilot**, chưa là research achievement:
≥95% schema-valid sau retries, quote/time checks100% cho output được chấp nhận,
≥90% numeric-unit correctness trên gold; failure/OOM phải được báo, không có
silent model swap. Không dùng ngưỡng JSON để kết luận prediction tốt. Latency
acceptance phải đối chiếu matrix calls và deadline/số giờ máy rảnh chưa xác định.
Nếu numeric/semantic chưa đạt: error analysis + prompt/context trên dev rồi
đo lại; nếu compute không đạt: đề xuất RAM/GPU/budget với số đo, giữ phạm vi.

Pilot JSONL contract dự kiến: sample_id, ticker, data_kind=real_document,
raw_snapshot_hash, document/version IDs, decision_at, eligibility cohort,
allowed text/locator, task, expected quote/numeric unit hoặc human rubric.
File synthetic fixtures dùng unit tests riêng; benchmark aggregator phải từ
chối data_kind synthetic/mock. Không tạo gold UP/DOWN bằng LLM rồi gọi là nhãn thật.

Từ traces pilot ước lượng thời gian matrix theo [roadmap](05-roadmap.md).
Digest/cutoff model chưa biết -> không gắn period Việt Nam nào là post-cutoff;
masking/counterfactual chỉ là diagnostics, không chứng minh hết memorization.
