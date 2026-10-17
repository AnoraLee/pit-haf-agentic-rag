# Local inference và snapshot pilot — 17/10/2026

Đã cài Ollama và bắt đầu đo qwen3:4b trên máy thật; đã hiện thực raw snapshot,
provenance, registry và gateway. Đây là pilot engineering/trích xuất trên
development, chưa là kết quả dự báo hướng giá hoặc backtest của khóa luận.

## Cài đặt đã xác minh

Ollama 0.40.5 từ [release chính thức](https://github.com/ollama/ollama/releases/tag/v0.40.5).
Bộ cài SHA-256 `ea0b50685d382bc0af164abdbf9b41bd89abb98de14fc51e4890a7176757a519`,
Authenticode Valid, signer Ollama Inc. Metadata trong
`outputs/setup/ollama-v0.40.5/verified-installer.json`; installer log được giữ.
Cài ở `%LOCALAPPDATA%\Programs\Ollama`, model ở thư mục Ollama mặc định của user.

API thực tế trả version 0.40.5. Model qwen3:4b, GGUF/Q4_K_M, digest đầy đủ
`359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`.
Metadata model local: `outputs/setup/ollama-v0.40.5/installed-models.json`.
Đây là digest đã tải; context tối đa quảng cáo không phải context chạy được
trên máy. Chưa xác minh training cutoff, không gắn period nào là post-cutoff.

Dịch vụ local được khởi chạy nền tại127.0.0.1:11434, concurrency 1,
max_loaded_models 1, context mặc định 2048, cloud disabled cho process này.
Launch metadata/log trong `outputs/setup/ollama-server-8cac695f09c84a87aa20567037ed2525/`.
Đây là environment của process, không sửa vĩnh viễn cấu hình user. Sau restart
máy, mở Ollama rồi dùng doctor kiểm lại. Không gọi API trả phí.

Thêm pypdf 6.21.0, tổng 82 package trong lock. Metadata registry của Vnstock,
vnai và vnstock-ezchart không còn truy cập được lúc sync (404). Dùng immutable
wheel URL trên files.pythonhosted.org và so checksum với lock trước sửa:
giữ nguyên vnstock 4.0.7 / vnai 2.5.9 / ezchart 1.0.2 và mọi package version cũ.
`uv sync --locked --offline` trên cache máy này đã đạt; CI GitHub chưa chạy.

## Code và đường dữ liệu mới

- EvidenceVersion giữ record/version/source, raw hash/locator, availability
  basis/precision, revision proof/review, reporting scope và data_kind.
- SnapshotStore lưu blobs theo SHA-256, SQLite metadata+acquisition hashes và
  triggers append-only. Gặp bytes/metadata sai checksum thì từ chối.
- Gateway lọc future, chọn latest known version tại cutoff rồi kiểm proof;
  latest thiếu proof/hỏng không âm thầm fallback bản cũ. Fixture bị loại khỏi
  đường real mặc định. Audit giữ riêng cho evaluator.
- PDF collector dùng allowlist official HTTPS, lưu robots/terms/listing và
  acquisition failures. Text giữ page, hash, extractor; không giả OCR.
- Local adapter chỉ loopback, chặn redirects/cloud routing, JSON/Pydantic,
  timeout/retry ≤1. OOM/timeout không tự đổi model; timeout không auto-retry khi
  chưa biết server đã hủy. Raw request/response từng attempt được giữ.
- Pilot lưu config, prompt/raw/case hashes, Git HEAD+dirty diff/source zip,
  model metadata/placement trước và sau, resources/errors và denominators.

Mọi availability/proof flag vẫn cần nguồn và review; schema không tự chứng minh
timestamp đúng. Registry v0.1 đóng băng metadata quan sát đầu tiên. Khi bổ sung
proof cần dataset/protocol release mới giữ registry cũ; append-only attestation
và query bitemporal đầy đủ chưa được hiện thực.

## Smoke đã chạy

[Artifacts](../../outputs/llm-smoke/20261017T092857Z-a86758b7/metrics.json):
3 fixtures, schema-valid 3/3, accepted 2, abstained 1, exact quote proposal 3/3,
literal numeric matches 3/3, retries 0. Đây là dữ liệu synthetic có nhãn,
không đưa vào bảng nghiên cứu hoặc dùng để kết luận chất lượng tài chính.
Median 2,53s, p95 nearest-rank 8,75s trên 3 case gồm cold load; cỡ mẫu quá nhỏ
để xem là benchmark latency ổn định. Sampling GPU toàn máy đỉnh 2461 MiB;
RAM toàn máy dùng đỉnh khoảng 13,18 GiB, không phải RAM riêng model.

## Corpus và pilot thật

Snapshot release offline: [summary](../../outputs/milestone-1/data-pilot/20261017-final-offline/summary.json),
11 documents (FPT 3 / HPG 7 / VCB 1), 905 pages, 730 có text layer, 175 trống/chưa OCR.
Còn thiếu 13 documents so với mục tiêu 24; số có text layer không chứng minh
fidelity. HPG BCTC Q1/2026 có chữ/số méo dù extract được text, ba BCTC khác
và FPT Q4/2024 là scan không có text. Đã bổ sung annual reports/overviews
born-digital có ghi source discovery; không bỏ các bản khó khỏi coverage.
Các URL FPT cũ trả404 và lỗi extraction lúc dependency đang cài vẫn giữ trong
acquisition ledger. Replay mới không truy cập network, không xóa lỗi cũ.

Đã hoàn tất phép đo 24 đoạn narrative tiếng Việt từ 3 báo cáo thường niên
FPT/HPG/VCB, 8 đoạn/mã. Input và selection audit:
`outputs/milestone-1/pilot-cases/20261017/`. Đây là 24 snippets từ 3 documents,
không phải 24 sự kiện độc lập hoặc 24 documents. Mẫu được chọn trước output model,
không dựa vào future return. Quote proposals là silver exact spans;
numeric-unit gold và semantic-support gold chưa được người chấm xác minh.
Đã spot-check trực quan ba trang narrative đại diện và một trang BCTC bị méo
text layer; đây là QA của assistant, không là đánh giá độc lập của người chấm.
Ảnh và mapping/offsets nằm trong selection audit và `outputs/milestone-1/pdf-qa-20261017/`.

Các tài liệu scan/text méo vẫn được giữ trong corpus/failure counts; không
lấy chất lượng sinh văn bản để sửa âm thầm bytes nguồn. Tài liệu tải hôm nay
chưa có proof giờ/bytes lịch sử nên strict gateway delivery bằng 0 là đúng
trạng thái hiện tại, không có nghĩa đã thu được dataset PiT dùng backtest.
Pilot đọc các đoạn text để kiểm trích xuất ở hiện tại, chưa đi qua luồng
Agentic-RAG lịch sử. Không dùng kết quả này để khẳng định PiT xuyên suốt.

[Run gốc](../../outputs/llm-pilot/20261017T093631Z-2e14228d/metrics.json),
context 2048, num_predict 512, think=false, temperature 0, seed 42:

| Chỉ tiêu | Kết quả / mẫu số |
|---|---|
| Schema-valid | 24/24 |
| Exact quote + numeric-span checks được chấp nhận | 7/24 |
| Abstention / generation failure / retry | 0 / 0 / 0 |
| Quote proposal khớp nguyên cả đoạn | 6/24; chỉ diagnostic, không gold support |
| Numeric-unit gold accuracy / semantic support | N/A; chưa gán nhãn độc lập |
| Tổng wall generation | 266,46s |
| Median / p95 nearest-rank per sample | 10,51s / 16,47s |
| Output tokens do backend báo | 6.788 |
| Sampling GPU toàn máy đỉnh quan sát | 2.461MiB |
| RAM toàn máy đỉnh quan sát | khoảng15,00GiB; không phải memory riêng model |

Model digest trước/sau khớp. Placement có CPU/GPU offload, chưa phải 100% GPU.
Có hoạt động phát triển/test/PDF trên máy trong lượt đo; cold/warm chưa được
kiểm soát như benchmark cuối. Các con số chỉ mô tả workload extraction nhỏ.
Ví dụ scale giả định 18.000 calls × 10,51s ≈ 52,6 giờ trước overhead, không phải ETA
full PiT-HAF vì role prompts/context/tools/output/retries khác workload này.

## Phân tích lỗi và verifier replay riêng

Trong 17 case không qua check gốc, 4 case chỉ khác whitespace/newline; 13 case còn
lại không tìm được quote nguyên văn sau chuẩn hóa whitespace. Có output thêm
dấu ba chấm, sửa câu, đổi ký tự hoặc liệt kê số ngoài quote. Vì thế JSON 100%
chưa đủ để chốt model đáng tin cậy. Phân loại định tính này còn cần người chấm.

Đã thêm resolver deterministic: chỉ ánh xạ quote duy nhất về source offsets,
cho phép whitespace khác do xuống dòng PDF. Không fuzzy match, sửa spelling,
đổi số, dấu âm, đơn vị hoặc bổ sung nội dung. Repeated quote không rõ locator
bị ambiguous. Đầu ra gốc và kết quả check gốc được giữ nguyên.

[Replay verifier](../../outputs/quote-replay/20261017T094348Z-1ba530b0/summary.json):
0 inference mới, SHA raw request/response và parsed output được đối chiếu trước
rescoring; exact 7 + whitespace-mapped 4, accepted11/24, còn 13 case bị chặn.
Đây là thay đổi policy kiểm trích dẫn trên cùng raw outputs, không là lần chạy
model tốt hơn hoặc kết quả dự báo. Offsets là ký tự trong context; cộng offset
của selection audit để về text trang. Semantic support vẫn chưa được xác minh.

## Độ ổn định và kiểm tra phần mềm

[Repeat comparison](../../outputs/milestone-1/pilot-cases/20261017/repeat_comparison.json):
6 case (hai case đầu/mã theo input order), quan sát 3 lần gồm lượt chính và hai
lượt lặp mới. Request payload và model digest đều trùng. Schema-valid 6/6 và
strict-accepted 1/6 ở cả ba; 5/6 parsed outputs giống hoàn toàn, 6/6 quote giống
nhau. Có một summary khác dù temperature 0 / seed 42. Median trên cùng 6 case là
12,42s /11,36s /11,30s. Không chọn run tốt nhất.

Subset rule được đặt trong development sau lượt đầu, không phải thí nghiệm
preregistered. Cache/load/history và workload nền chưa được cô lập. Chưa đo
context 4096 hoặc chất lượng model khác; chưa chốt config nghiên cứu cuối.

Kiểm tra code cuối: **191 tests passed in 9,43s**, Ruff pass, git diff --check
exit0 (chỉ nhắc LF/CRLF). Tests cũ provider/Guard khớp byte snapshot trước.
Tests mới bao phủ version/time/proof/fixture isolation, corruption/relabel,
timeout/JSON/OOM/retries/digest, numeric signs, source-offset mapping và replay
refuse raw tampering. CI GitHub chưa chạy.

Doctor sau cài:
[preflight](../../outputs/preflight/20261017T095143Z-eb066724/preflight.json)
trả reachable/candidate present và require-model exit 0. Field inference của
doctor chỉ mô tả diagnostic không sinh response; inference thật nằm ở các
run pilot riêng. Metadata/source zip trong mỗi report mô tả thời điểm capture,
không bao gồm sửa tài liệu báo cáo kết quả sau đó.

[Validation JSON](../../outputs/milestone-1/validation-20261017.json) tập hợp
các lệnh/checks, run paths, preservation và giới hạn. Source snapshot cuối
có58tệp, đã đối chiếu SHA-256 của archive.

[Data card](../../data/pilot/DATA_CARD.md) và provenance index được thêm để
truy nguyên các file raw đang giữ local; không phát hành dataset ra ngoài.

## Tự chạy

```powershell
.\run.ps1 doctor
.\run.ps1 test
.\run.ps1 lint
.\run.ps1 llm-pilot --cases configs/smoke_cases.jsonl --smoke
.\run.ps1 pilot-data --extract-existing
.\run.ps1 llm-pilot --cases outputs/milestone-1/pilot-cases/20261017/cases.jsonl --num-ctx 2048
.\run.ps1 quote-audit --source-run outputs/llm-pilot/20261017T093631Z-2e14228d
```

`pilot-data` không có --extract-existing sẽ truy cập nguồn online.
Mỗi lần chạy tạo output mới; giữ raw response khác với gọi inference lại.
Chạy test dùng unique basetemp dưới outputs/ và khôi phục TEMP/TMP sau lệnh,
tránh ACL của sandbox temp. Không xóa thư mục test cũ hoặc dữ liệu người dùng.
Các lệnh run.ps1 gọi trực tiếp .venv nên không cần activate. uv helper dùng
trong lượt setup nằm ở `outputs/setup/python-tools/bin/uv.exe`; chưa thêm
vào PATH của user. Lock/cache đã được kiểm tra độc lập với PATH.

## Điều kiện còn lại

M1 chưa đóng: còn gold numeric/semantic annotation, coverage tài liệu/sự kiện,
đánh giá nondeterminism và feasibility strict availability/version. Model là
ứng viên development, chưa chốt vì JSON đúng không chứng minh report đúng.
M2 tiếp theo: curation/time proofs, dataset releases, lịch phiên và quant engine
với phí/cash/holdings/settlement được xác minh. Full retrieval/graph/peer,
hierarchy/verifier/risk/memory, ablation/robustness vẫn giữ theo roadmap.
