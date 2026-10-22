# Chạy bộ case cố định và đối chiếu annotation

Ngày 22/10/2026. Công cụ phát triển cho báo cáo một agent, chưa là thực nghiệm
cuối, đánh giá ngữ nghĩa hoặc backtest của PiT-HAF.

## Hợp đồng chạy

`development-evaluate` nạp bộ case đã công bố, kiểm checksum cấu hình,
summary/catalog và đọc đúng các trang đã pin. Không truy xuất lại theo catalog
mới. Metadata, hash văn bản trang, đoạn trích và offset phải tái tạo nguyên bộ
context trước khi gọi model. Câu hỏi gửi model là `case.question`; `case.query`
chỉ dùng để chuẩn bị bộ nguồn. Đây là kiểm tra trả lời trên context cố định,
không đo chất lượng truy xuất toàn kho hoặc hiệu quả của hệ phân cấp.

Mỗi case tối đa một call, không retry; context 4096 token, output tối đa 1024
token, ba đoạn/2100 ký tự. Model được inspect trước/sau, digest phải bằng nhau
và bằng digest đầu batch. Digest đổi trước case tiếp theo thì dừng trước call.
Lỗi model, timeout, transport hoặc OOM dừng batch; timeout không xác nhận server
đã hủy xử lý. Lỗi nguồn giữ thành hàng lỗi và tiếp tục case còn lại. Mọi case
đều có một hàng, gồm cả lỗi, ABSTAIN và `not_run`; không thay case theo thành công.

Giữ thứ tự bộ đã công bố. `--limit` chỉ lấy prefix để kiểm tra kỹ thuật; các case
còn lại vẫn được liệt kê `not_run`, không gọi đó là chạy đủ bộ. Không tự resume
hoặc chạy lại lỗi. Một batch mới tạo thư mục mới, giữ toàn bộ batch trước.
Lock `outputs/development-batches/run.lock` ngăn hai batch cùng chạy. Nếu process
bị kill, kiểm tra process/Ollama và artifact trước khi xử lý lock còn sót. Lock
này không điều phối các chương trình khác gửi yêu cầu Ollama; trên máy VRAM thấp,
chạy batch tuần tự và tránh lập báo cáo tương tác cùng lúc.

## Chạy và sử dụng

```powershell
# Chạy toàn bộ case bằng model local đã cài; có inference.
.\run.ps1 development-evaluate

# Kiểm tra prefix hai case; giữ các hàng còn lại chưa chạy.
.\run.ps1 development-evaluate --limit 2

# Chỉ đọc kết quả đã lưu và annotation hiện tại; không gọi model.
.\run.ps1 development-evaluate --evaluate-only
.\run.ps1 development-evaluate --evaluate-only --batch-id <batch-id>
```

Trên **Phân tích tài liệu → Câu hỏi và kết quả kiểm tra AI**, bấm **Cập nhật đánh giá**
sau khi lưu annotation hoặc chạy CLI. GET `/api/research/evaluation` chỉ đọc,
không khởi động model. Có thể tải JSON tổng hợp và xem đủ từng case. Bản chạy
được hiển thị khi có manifest đã seal; batch đang chạy chỉ ghi `progress.json`.

Ô **Đặt câu hỏi của bạn** dùng để tra cứu tự do và mặc định để trống. Nút
**Xem 24 câu hỏi kiểm tra** cuộn tới danh sách luôn mở, hiển thị câu hỏi đầy đủ
và có bộ lọc doanh nghiệp. API trả nội dung câu hỏi từ pack đã pin, kể cả khi
chưa chạy model; không thay bằng mã case kỹ thuật.

Mục **Tạo đáp án tham chiếu** (tên trước đây: “Chấm case phát triển”) giải thích
cách đọc PDF, nhập đáp án/trích dẫn hoặc chọn thiếu bằng chứng. Đây là ghi đáp
án tham chiếu thủ công, không phải chấm điểm tự động cho câu trả lời model.

Manifest bind pack/cases/protocol/policy, thứ tự, run ID và hash từng report.
Replay kiểm seal report/Markdown, context/câu hỏi, request/response raw và đối
chiếu parsed JSON với response gốc, rồi chạy lại verifier quote/số. Hàng không
đạt integrity giữ trong coverage nhưng loại khỏi chỉ số đối chiếu. Không sửa
report cũ để khớp verifier mới. Nếu thay prompt/schema/verifier, evaluator hiện
tại có thể từ chối replay; dùng source archive của run để kiểm tra bản cũ.

Mỗi lần CLI evaluate lưu JSON mới, bind hash snapshot revision của các review.
API tính lại trên ledger hiện tại dưới lock của process API. Ledger/source hỏng
thì từ chối, không lấy review cũ hoặc bỏ hàng lỗi âm thầm. Hash ở đây phát hiện
sai lệch tương đối với manifest đã lưu, không là chữ ký chống việc sửa toàn bộ
manifest và artifact. Reviewer vẫn là tự khai báo; không xác minh danh tính.

## Ý nghĩa các chỉ số

- Coverage: tổng case, số run qua integrity, chưa chạy, lỗi nguồn, lỗi model và
  lỗi integrity. JSON/schema lỗi được ghi `generation_failed`, tách khỏi ABSTAIN.
- Quote/số: số claim được chấp nhận/bị chặn và tần suất block reason. Một claim
  có thể có nhiều reason; tổng reason không phải số claim.
- Compute: tổng call/token do Ollama trả, thời gian generation gồm các attempt,
  median và p95 theo nearest rank; không gồm toàn bộ thời gian ingest/retrieval.
- Vị trí tham chiếu: với case `answered` và JSON/digest hợp lệ, tỷ lệ đáp án đã
  khai báo có ít nhất một quote model giao khoảng ký tự trên đúng version,
  page và page-text hash. Không so khớp chuỗi statement thành semantic accuracy.
- Chuỗi số tham chiếu: trong các đáp án có số, quote model giao vị trí phải chứa
  đủ chuỗi số của đáp án (kể cả số trong statement), qua bộ kiểm dấu/chuỗi số.
  Không tự kiểm đúng chỉ tiêu, đơn vị, kỳ hoặc liên hệ số liệu theo ngữ nghĩa.
- Case `unanswerable`/`wrong_period`: đếm riêng số có JSON hợp lệ và không có
  claim được chấp nhận. JSON lỗi không được tính là quyết định từ chối đúng.
  `needs_ocr` không đưa vào mẫu số này; `pending` không có điểm đối chiếu.

Mẫu số bằng 0 trả `null`, không trả 0% hay 100%. Annotation chưa độc lập nên
đây là đối chiếu với khai báo người chấm, chưa là human gold. Các vị trí giao
nhau hoặc số trùng nhau vẫn có thể nói về chỉ tiêu/đối tượng khác nhau.

## Artifact và giới hạn

Lượt thật `20261022T030940Z-22f948f0`: 24 call, cùng digest qwen3:4b;
8 case có claim qua kiểm nguyên văn/số, 15 ABSTAIN và 1 generation không hoàn
tất trong budget (`incomplete_generation`). Giữ đủ 24 hàng, không chạy lại.
Có 13 claim được chấp nhận và 50 bị chặn; các reason có thể chồng nhau.
Tổng thời gian generation khoảng 936,70 giây, median 36,62 giây và p95 nearest
rank 61,99 giây. Cả 24 report/raw request-response replay qua kiểm integrity.
324 test phần mềm đạt; Ruff/Prettier/frontend build đạt, còn hai cảnh báo
deprecation TestClient và hai cảnh báo directive lucide khi build.

Đây là chạy câu hỏi thực trên context đã chọn, không là accuracy hoặc ablation
với các lượt smoke trước (câu hỏi/prompt development và cách chạy có khác biệt).
Vẫn 24 case pending; mẫu số đối chiếu annotation bằng 0 nên các tỷ lệ là `null`.

`outputs/development-batches/<batch-id>/` chứa source archive, progress, manifest,
seal và các lần evaluation. Report cùng request/response gốc ở
`outputs/company-reports/<run-id>/`. Review ở ledger riêng. Toàn bộ nội dung
nguồn, model output và annotation ở local; hồ sơ công khai chỉ giữ metadata.

Phiên chạy thực và kiểm tra phần mềm được ghi trong
[hồ sơ validation](../../data/development/evaluation-v0.1/validation.json).
Không có annotation thủ công mới do công cụ tự tạo. Chưa xác nhận semantic
accuracy, availability lịch sử, dự báo lợi suất, graph/peer hoặc full hierarchy.
