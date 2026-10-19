# Truy xuất theo kỳ/doanh nghiệp và màn hình chấm case

Ngày 19/10/2026. Bước phát triển sau báo cáo một agent, chưa freeze nghiên cứu.

## Vấn đề và thay đổi

BM25 rộng có thể trả bài về mã liên quan/công ty khác hoặc kế hoạch năm trước.
Ngày đăng tin không là kỳ kế toán. Luồng báo cáo mới mặc định chỉ dùng PDF
báo cáo có mã chính là doanh nghiệp được hỏi. Kỳ `YYYY`/`YYYY-Qn` so chính xác
với metadata, không chỉ lấy bốn chữ số năm. Tự nhận diện một năm và một quý
duy nhất từ câu hỏi; nhiều năm không tự chọn một năm. Có lựa chọn kỳ rõ ràng,
không lọc kỳ, hợp nhất/riêng lẻ hoặc toàn nguồn gắn mã liên quan.

Nếu đã chọn kỳ kế toán, tin bài không có metadata kỳ PDF bị loại; năm đăng
tin không được giả làm kỳ báo cáo. Chưa có nguồn đúng scope thì trả rỗng và
ABSTAIN, không fallback sang kỳ hay doanh nghiệp khác. `all_linked` chỉ có
nghĩa các nguồn gắn mã; không xác nhận entity hoặc ownership về ngữ nghĩa.

Với strict: gateway trước, giao cắt allowlist/scope trước khi mở trang và tính
BM25 trên tập đã lọc. FTS5 của chế độ đọc hiện tại vẫn dùng thống kê index
hiện tại; không gọi đó là xếp hạng lịch sử. Catalog v0.5 dùng lại nguyên bytes,
không dựng lại hoặc sửa bản phát hành cũ. Hash mã catalog trong hồ sơ v0.5
mô tả lúc dựng index; runtime mới được ghi ở hồ sơ v0.2 riêng.

Model nhận thêm mã chính/liên quan, kỳ, scope, loại và origin của tài liệu.
Metadata không thay quote để chứng minh số. Guard alias quan sát `VCBS` và
các nhãn tương ứng giữ claim ở trạng thái cần người kiểm khi phân tích VCB.
Đây là heuristic từ lỗi development đã thấy, không là graph ownership hoặc
verifier ngữ nghĩa tổng quát. Trích dẫn/số/digest/abstention vẫn bị kiểm như cũ.

## Bộ case và chấm thủ công

[Data card v0.2](../../data/development/v0.2/DATA_CARD.md) và
[so sánh metadata](../../data/development/v0.2/retrieval_comparison.json) ghi
24 câu hỏi giữ nguyên, 72 tham chiếu mới. Scope match theo metadata tăng từ
36/72 lên 72/72 theo cấu hình; không có nhãn để kết luận retrieval accuracy.

Trên **Phân tích tài liệu → Chấm case phát triển**, chọn case, mở các đoạn S1–S3
và PDF đã lưu đúng hash; kiểm bảng/số/kỳ/entity ở nguồn. Chọn answered hoặc lý
do thiếu bằng chứng/sai kỳ/cần OCR. Nhập người chấm, quote và câu trả lời; tối
đa ba đáp án. Mỗi chuỗi số ở một dòng, giữ dấu âm và đơn vị. Checkbox xác nhận
đã kiểm nguồn là khai báo của người dùng, không là xác minh danh tính độc lập.

API giữ revision append-only theo từng case, kiểm nguồn case chưa đổi, quote
duy nhất, numeric strings, declaration và parent revision. Save với revision
cũ trả 409; nguồn/hàng log sai checksum bị từ chối. Các case pending được giữ
khi export, không silently drop. Chưa có thao tác chấm thực trên 24 case này.

## Chạy CLI

```powershell
.\run.ps1 company-report --ticker VCB --query "lợi nhuận năm 2024"
.\run.ps1 company-report --ticker FPT --query "kết quả quý II năm 2024"
.\run.ps1 company-report --ticker HPG --query "kế hoạch năm 2025" --reporting-period 2024
.\run.ps1 company-report --ticker VCB --query "tin tức Vietcombank" --reporting-period all --source-policy all_linked
.\run.ps1 development-cases --scoped
```

Lệnh cuối tạo một pack mới, không tự ghi đè index metadata hoặc pack cũ.
Case hiện hành được chọn từ metadata đã phát hành, không lấy bản đang dựng.
Chế độ trích xuất một đoạn và `/api/search` rộng được giữ riêng; bộ lọc này
áp dụng cho luồng báo cáo doanh nghiệp.

## Kiểm tra thực tế và giới hạn

308 test phần mềm đạt; Ruff và frontend build đạt. Test mới bao phủ loại mirror
khỏi kỳ kế toán, mã liên quan, scope trước strict statistics/raw reads, PDF
corruption và review/CAS/append/hash/export/origin. Hai cảnh báo deprecation
TestClient và hai cảnh báo lucide khi build vẫn có, không là lỗi inference.

Ba lượt Ollama thật, mỗi mã một call: FPT bị chặn (0 claim), HPG có 3 claim
vượt kiểm nguyên văn, VCB có 2 claim vượt và 1 bị chặn. Digest ổn định. Artifact:
`outputs/development-scoped/smoke-20261019T030613Z-80d9cc98/summary.json`, raw
responses ở run folders được chỉ ra trong summary. Không bỏ lượt FPT khỏi mẫu.

Đợt này đồng thời đổi scope truy xuất, metadata trong prompt và alias guard;
không là ablation một yếu tố. Không có human gold nên các số trên không phải
accuracy, support rate được người xác nhận hoặc hiệu quả đầu tư. Nondeterminism
đã quan sát ở v0.1 vẫn là vấn đề cần đánh giá, chưa được chứng minh đã giải quyết.
Các nguồn mới vẫn không có proof PiT lịch sử. Bước tiếp là người dùng chấm case,
rồi chạy evaluator trên annotation đã qua kiểm integrity và duyệt ngữ nghĩa.
