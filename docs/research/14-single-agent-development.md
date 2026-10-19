# Báo cáo một agent và bộ case phát triển

Cập nhật 19/10/2026. Đây là bước phát triển tiếp theo trên corpus v0.5, chưa
hoàn thành PiT-HAF hoặc freeze protocol thực nghiệm.

## Cấu hình và phạm vi

[`research_development_v0_1.json`](../../configs/research_development_v0_1.json)
ghi ba mã pilot FPT/HPG/VCB, 8 chủ đề câu hỏi/mã, ngân sách báo cáo và các quyết
định còn mở. Tác vụ chính dự kiến vẫn là sự kiện BCTC hợp nhất, nhãn lợi suất
5 phiên. Các case hỏi đáp ở bước này dùng để phát triển và chấm bằng chứng,
không được tính thành 24 sự kiện có nhãn lợi suất hoặc tập test độc lập.

`approved_for_final_experiments=false`. Giảng viên, universe cuối, khoảng năm,
lịch phiên/corporate actions, split, gold và cấu hình model cuối chưa được
xác nhận. Runner từ chối cấu hình bị sửa thành final hoặc vượt ngân sách đã
kiểm thử; không đổi những điều này để làm một lượt chạy trông tốt hơn.

## Luồng đã triển khai

`Câu hỏi + mã + chế độ thời gian → gateway khi strict → BM25 → chọn tối đa ba
đoạn/2.100 ký tự → một lần gọi Ollama → đối chiếu từng claim → báo cáo/ABSTAIN`.
Mỗi đoạn tối đa 700 ký tự; ưu tiên các revision khác nhau trước khi lấy đoạn
thứ hai cùng tài liệu. Đây là single-agent RAG có ngân sách cố định, chưa có
planner tự tìm thêm hoặc hệ phân cấp.

Ollama qwen3:4b, context 4.096, output tối đa 1.024 token, temperature 0,
seed 42, thinking tắt, không retry hoặc đổi model âm thầm. Schema báo cáo tách
khỏi schema trích xuất cũ. Model chỉ nhận câu hỏi, mã, ID và đoạn nguyên văn;
không nhận nhãn đánh giá hoặc audit liệt kê nguồn tương lai.

Mỗi claim phải tham chiếu nguồn đã giao, có quote khớp duy nhất, đúng offset;
kiểm mọi số trong statement và số model kê khai so với quote, giữ dấu âm và
ngoặc kế toán. Model đổi digest hoặc tự báo thiếu bằng chứng thì chặn claim.
Claim bị chặn vẫn có trong dấu vết, không xuất thành nội dung được chấp nhận.
Khớp nguyên văn không chứng minh diễn giải, entity, đơn vị/kỳ hoặc quan hệ
nhân quả đúng. Giao diện và Markdown ghi rõ ngữ nghĩa chưa được duyệt, kể cả
phần model báo thiếu thông tin.

Lưu `report.json`, `report.md`, raw request/response, model trước/sau, hashes,
source snapshot/Git dirty diff và `gateway-audit.json` dưới một run ID mới.
Audit gateway đầy đủ ở file local riêng; API chỉ trả checksum và bộ đếm của
audit để tránh gửi hàng chục nghìn record vào browser hoặc model.

Lịch sử UI giữ cả lượt hoàn thành và bị chặn. Mở báo cáo đã lưu là replay file,
không inference mới; checksum JSON/Markdown sai thì từ chối. Các lượt thử đầu
được bổ sung seal sau khi đối chiếu request/response, context, raw source và
quote checks, ghi `post_run_integrity_review_not_original_time_proof`; không
gọi seal bổ sung là bằng chứng thời gian thực thi gốc hoặc proof lịch sử.

`verification/arithmetic.py` có phép tăng trưởng và biên lợi nhuận thuần dùng
Decimal, yêu cầu fact có người duyệt, evidence ID, đơn vị/tiền tệ/phạm vi tương
thích. Không tự coi số do model trích xuất là fact đã duyệt. Chưa có fact thật
được người duyệt nên báo cáo hiện ghi `no_reviewed_structured_facts`; chưa chạy
tính chỉ tiêu công ty hoặc dự báo lợi suất.

## 24 case để người dùng duyệt

Pack local hiện tại:
`outputs/development-cases/20261019T024426Z-202a2c66/`.

- `cases.jsonl`: câu hỏi và các đoạn nguồn đã pin, dùng local.
- `review.md`: phiếu đọc theo từng case, URL và vị trí nguồn.
- `annotations.template.jsonl`: 24 hàng pending, chưa có đáp án.
- `summary.json`: phương pháp chọn, hashes, snapshot nguồn và mã.

Chỉ metadata/locators tại [`case_index.json`](../../data/development/v0.1/case_index.json)
được đưa vào Git. Có 8 case/mã, cả 24 có đoạn nguồn; **0 case được người duyệt**.
Không chọn case theo lợi suất hoặc kết quả model. Chủ đề, kỳ, gán mã và độ
đầy đủ vẫn phải duyệt; bài về công ty con không tự là kết quả hợp nhất của mẹ.
Xem [hướng dẫn annotation](../../data/development/v0.1/DATA_CARD.md).

## Tự chạy

```powershell
.\run.ps1 company-report --ticker HPG --query "lợi nhuận trước thuế sau thuế năm 2024"
.\run.ps1 company-report --ticker FPT --query "lợi nhuận năm 2024" `
  --mode strict_point_in_time --decision-at "2025-04-01T16:00:00+07:00"
.\run.ps1 development-cases
```

Mỗi lệnh tạo output mới. Trên UI chọn **Phân tích tài liệu → Doanh nghiệp →
Lập báo cáo doanh nghiệp**. Có nút tải Markdown và JSON. Strict không có nguồn
sẽ trả báo cáo từ chối, 0 lần gọi model; không chuyển sang dữ liệu hiện tại.

## Kết quả kiểm tra phát triển

Ba lượt CLI thật cho cùng truy vấn lợi nhuận 2024: FPT bị chặn, HPG có 3
trích dẫn vượt kiểm nguyên văn, VCB bị chặn. Cả ba chỉ gọi model một lần,
digest ổn định. Lưu đầy đủ tại
`outputs/development-cases/report-smoke-summary.json`, các run ở
`outputs/company-reports/`; đây không phải kết quả chấm chất lượng hay dự báo.

FPT truy xuất cả nội dung kế hoạch, model báo thiếu kết quả thực tế. VCB còn
nguy cơ lẫn ngữ cảnh công ty con VCBS với ngân hàng và số trong statement chưa
được quote hỗ trợ. Các trường hợp này là đầu vào cho annotation/error analysis;
không nới kiểm tra để ghi nhận thành công. HPG khớp quote vẫn cần người kiểm
ngữ nghĩa, entity, kỳ và đơn vị.

Lượt HPG từ UI sau đó trả `insufficient_evidence=true`, nên chặn toàn bộ claim.
Đã đối chiếu SHA request, context và model digest: trùng lượt HPG CLI trước,
nhưng output khác. Giữ cả hai lượt; không chỉ giữ run tốt. Quan sát này chưa
đủ để định lượng độ ổn định hoặc kết luận nguyên nhân; cần protocol repeat
trên bộ đã chấm và kiểm soát tài nguyên/cold-load. Temperature 0/seed cố định
không bảo đảm output byte-identical trên môi trường local này.

Kiểm thử phần mềm: **294 passed**, Ruff và frontend build đạt; còn hai cảnh báo
deprecation TestClient và hai cảnh báo directive của lucide khi build. Lượt
TestClient trong sandbox bị treo, được dừng rồi chạy thành công ngoài sandbox
bằng fixture offline. Kết quả local không thay trạng thái GitHub Actions.

## Việc tiếp theo

Duyệt 24 case, phân loại wrong period/needs OCR/unanswerable và tạo đáp án có
locator. Tiếp đó đo retrieval và câu trả lời trên case đã duyệt, cải thiện
lọc kỳ/entity/structured facts trên development. Tìm proof lịch sử cho cohort
riêng; không suy `available_at` từ ngày đăng mirror. Graph/peer, planner,
hierarchy, semantic verifier, risk, memory và backtest vẫn theo roadmap.
