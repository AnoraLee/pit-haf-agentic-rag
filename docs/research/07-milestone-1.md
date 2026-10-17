# Milestone 1 — Hướng dẫn chạy và nghiệm thu lượt khởi đầu

Lượt khởi đầu 06/10/2026 được giữ để truy nguyên. Tiến độ mới ngày17/10
(Ollama, snapshots/gateway và local pilot) nằm trong [báo cáo08](08-local-pilot-results.md).

## Công việc có thể kiểm chứng đã làm

- Audit 63 tests ban đầu và code/docs; snapshot/diff trước sửa lưu local.
- Hồ sơ task/label/timeline, literature/contribution, architecture/contracts,
  experiments/rubric, roadmap và feasibility được lưu trong `docs/research/`.
- Đề cương chuyển thị trường chính sang Việt Nam, giữ đủ graph/peer/hierarchy/
  verifier/risk/memory/audit/baselines/robustness.
- UI dùng provider Việt Nam, FPT/VND và optional VNINDEX/điểm; không gắn thay đổi
  giá đầu/cuối thành backtest hoặc mô tả pipeline agent đã chạy.
- `pit_haf.research.doctor`: đọc RAM/GPU/package/Ollama version/tags/ps,
  lưu JSON + Git HEAD/dirty diff/hashes/code zip. Chỉ gọi loopback, không tải
  model/chạy inference. Thực thi không đồng nghĩa local model đã sẵn sàng.
- CI workflow offline được thêm, pin actions/uv; chưa chạy trên GitHub vì chưa
  push. Cài dependencies cần Internet; bản thân tests không gọi nguồn/model.
- Pytest chỉ thu thập `tests/`, tránh quét bản test trong raw/source snapshots
  ở `outputs/`. Provider/Guard hiện có và 63 tests được giữ nguyên.

## Lệnh hiện có

Trong PowerShell ở thư mục dự án, dùng `.venv` đã cài:

```powershell
.\run.ps1 test
.\run.ps1 lint
.\run.ps1 doctor
.\run.ps1 pit-demo
.\run.ps1 app
```

`doctor` tạo thư mục mới theo UTC timestamp + suffix tại `outputs/preflight/`,
không ghi đè report trước. Mở `preflight.json`, đọc `hardware`, `ollama`,
`repository`. `research_results=false` và inference_status=not_measured luôn
đúng cho loại diagnostic này. Model xuất hiện trong tags chỉ đủ để kiểm tra
model, chưa đủ để nghiệm thu quality/latency.

Gate command yêu cầu candidate có thật:

```powershell
.\.venv\Scripts\python.exe -m pit_haf.research.doctor --require-model
```

Exit2 nếu service/candidate chưa sẵn sàng; report vẫn được lưu. Không trả mock
inference để giả pass. Có thể dùng `--ollama-url http://localhost:11434` và
`--model qwen3:4b`; CLI từ chối remote URL. Chưa có API trả phí.

`data` là tải online cần Internet; app chỉ tải khi nhấn nút. Kiểm UI offline
dùng mock có nhãn test-fixture, không trở thành market snapshot/research metrics.
Không gắn badge "PiT verified" cho giá có adjustment_status=unknown.

## Kết quả kiểm tra

Trước sửa: 63 passed, Ruff pass. Lần kiểm tra cuối sau sửa: **80 passed in 3.84s**,
Ruff **All checks passed!**, `git diff --check` exit0. Git chỉ nhắc quy tắc
LF→CRLF ở đề cương, không có lỗi whitespace. Provider/Guard và hai bộ test cũ
khớp byte với snapshot trước sửa; 17 test mới kiểm UI/doctor.

`run.ps1 doctor` chạy exit0. CLI `--require-model` được kiểm exit2 vì local
endpoint từ chối kết nối; đây là gate từ chối đúng điều kiện, không mock pass.
`pit-demo` chạy exit0 với dữ liệu synthetic có nhãn.

Log máy đọc được: [validation.json](../../outputs/milestone-1/validation.json).
Báo cáo mới nhất:
[preflight.json](../../outputs/preflight/20261006T084544Z-a7b1418d/preflight.json).
Cùng thư mục có source_snapshot.zip, source_hashes.json, working-tree.patch
và git-status.bin. Snapshot có 37 tệp kể cả source chưa tracked và mô tả thời
điểm capture; các cập nhật tài liệu ghi kết quả sau đó không nằm trong snapshot.
Snapshot của lần đầu đã kiểm SHA-256 và nội dung untracked, không chứa outputs/.venv/.git.

RAM mới nhất tổng15,40GiB, trống khoảng3,83GiB; GPU4096MiB, trống3964MiB.
Số trống thay đổi theo hoạt động máy. Số disk giữa các lượt diagnostic khác
nhau; bản mới ghi rõ queried_path của repo. Chưa đối chiếu volume/quota, không
dùng các số disk đó để kết luận capacity cho dataset.

Kết quả pytest là kiểm chứng software, không là kết quả financial prediction.
Chưa chạy CI GitHub, provider online hoặc benchmark inference trong lượt này.

## M1 còn phải làm trước nghiệm thu đầy đủ

- Thu thập 20–30 case thật, raw/locators/QA, chứng minh nguồn và timestamp/version
  cho strict cohort; hiện mới khảo sát truy cập/terms và có kế hoạch.
- Tìm vị trí Ollama khác nếu người dùng đã cài; hoặc cài local official,
  tải candidate và đo24 case theo kế hoạch. Chốt model/config bằng số đo.
- Xác nhận task/sampling/corporate-action strategy/calendar và các quyết định
  cần giảng viên trước freeze; deadline/mẫu trường/ngân sách vẫn unknown.
- Hoàn thiện literature screening, không kết luận novelty từ ba bài.

Các phần M2 độc lập (snapshot/schema/gateway/calendars/quant examples) có thể
tiếp tục trong khi chuẩn bị local inference. Lượt này **bắt đầu M1**, chưa tuyên
bố M1 đã đạt toàn bộ acceptance hoặc PiT-HAF đã hoàn thành.

## Câu hỏi giúp tự bảo vệ

1. Vì sao dataset vẫn cần khi không training/fine-tuning LLM?
2. Input model khác labels evaluator như thế nào? Ngày công bố khác kỳ báo cáo?
3. Bản sửa ngày03/07 có được phân tích ở01/07 không, nếu cùng record_id?
4. Vì sao filter metadata chưa đủ với lexical statistics hoặc ANN topology?
5. Local package ollama khác server/model/digest thế nào? File2,5GB khác peak memory?
6. Vì sao 80 tests và UI chạy không chứng minh prediction/PnL vượt baseline?
7. Vì sao ABSTAIN, failures và kết quả âm phải giữ trong báo cáo?
