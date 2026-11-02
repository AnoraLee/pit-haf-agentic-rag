# 25 — Chọn tài liệu trước khi đọc bảng

Ngày: 29/10/2026. Bổ sung khả năng giới hạn một version tài liệu cho các
profile bảng hiện có. Không tạo profile trích xuất mới, đổi ngân sách hoặc
sửa kết quả v0.4–v0.8 đã lưu. Mặc định frontend/API vẫn v0.6; gọi model vẫn
là tùy chọn tắt ban đầu.

## Vấn đề và hành vi mới

FPT 2024 có hai PDF, mỗi bản 213 trang. Khi đọc lại cả hai, tổng 426 trang
vượt giới hạn 400 của v0.7/v0.8. Đây là giới hạn phạm vi truy xuất, không
phải thiếu raw PDF. Trước đây người dùng chưa chọn được một version từ
giao diện hoặc CLI đọc bảng.

**Xem tài liệu phù hợp** chỉ đọc metadata catalog, liệt kê PDF đúng doanh
nghiệp/kỳ và giao với allowlist của gateway nếu dùng PiT strict. Danh sách
có ID, tiêu đề, số trang, số trang có chữ theo catalog cũ, URL và hash nguồn.
Không đọc nội dung trang hoặc gọi model để tạo danh sách; số trang có chữ
không phải đánh giá OCR mới. Không tự ưu tiên hoặc bỏ một bản theo kết quả.

Người gọi có thể giữ toàn bộ phạm vi hoặc chọn **Tài liệu dùng để đọc bảng**.
Nếu phạm vi xem trước vượt giới hạn, giao diện chặn nút chạy cho tới khi
chọn một tài liệu trong giới hạn. Tài liệu riêng lẻ vượt giới hạn không
được chọn. Đổi câu hỏi, doanh nghiệp, kỳ, chế độ, mốc thời gian hoặc cách
đọc lớp chữ sẽ xóa lựa chọn cũ để tránh dùng nhầm nguồn.

`DocumentReportScope` bổ sung điều kiện `version_id` bằng SQL tham số và
kiểm lại doanh nghiệp/kỳ/allowlist trước khi đọc trang. ID thiếu, khác mã,
khác năm hoặc chưa được gateway cấp không dẫn tới fallback sang nguồn khác.
Nếu không chọn version, JSON scope cũ được giữ nguyên. Lựa chọn được lưu
trong `result.json.scope`; replay chặn bundle/lớp chữ không thuộc version đó.
Chọn tài liệu không xác nhận tính đúng số liệu hoặc bằng chứng lịch sử.

Giao diện mở lại run hiển thị nguồn đã giới hạn. Khi không có ô context,
các trang đã chọn có lý do dừng và link đến đúng trang PDF. Chẩn đoán chỉ
phản ánh quy tắc parser, không kết luận PDF không chứa thông tin.

## Hai lượt phát triển FPT, giữ toàn bộ kết quả

Study `20261029T080618Z-f234f57d` khai báo trước cả hai version từ metadata,
sắp theo ID. Cùng câu hỏi lợi nhuận 2024, profile `table_cells_v0.8`, tối đa
400 trang đọc lại mỗi run; không retry, không gọi model, không chọn lại
trang/đổi cấu hình sau khi thấy kết quả. Người chọn trong study là trợ lý,
không phải người chấm nhãn độc lập.

| Bản | Run | Trang đọc lại | Trang bảng được chọn | Ô context | Kết quả |
|---|---|---:|---|---:|---|
| English, `0a8c4da3…` | `20261029T080737Z-9f70783b` | 213 | Không có | 0 | Chưa có ô phù hợp |
| Vietnamese, `e8509e72…` | `20261029T080853Z-9628ff81` | 213 | 50, 151 | 0 | Chưa có ô phù hợp |

Đã giải quyết lỗi vượt ngân sách bằng phạm vi tường minh. Chưa giải quyết
trọn vẹn trích xuất FPT: bản tiếng Anh không có trang được chọn bởi bộ
truy xuất hiện tại. Bản tiếng Việt có header năm và hàng số, nhưng parser
ô v0.5 dừng cả hai trang với `missing_or_ambiguous_currency_unit`. Đã xem
ảnh đầy đủ hai trang; các dạng đơn vị và vị trí nguồn cần được hỗ trợ,
kiểm tra trong một thay đổi parser có phiên bản riêng. Không tự điền đơn
vị hoặc lấy ứng viên từ một run khác để thay kết quả rỗng.

Hai raw run replay đạt. Đã replay toàn bộ 44 run có seal trong workspace:
40 run từng được liệt kê ở mốc v0.8, hai diagnostic v0.5 đã tồn tại ngoài
danh sách đó và hai run mới. Có cả ABSTAIN/lượt lỗi trước generation cũ;
44 replay không có nghĩa 44 câu trả lời đúng. Hash 42 seal cũ, case pack,
batch, source audit và metadata v0.8 không đổi; hash các config trước/sau
study khớp. Không có nhãn người dùng mới hoặc semantic accuracy.

## Cách dùng

Tại [Phân tích tài liệu](http://localhost:8501/#analysis), chọn FPT và hỏi
lợi nhuận năm 2024. Bật lớp chữ thử nghiệm, chọn v0.8, bấm **Xem tài liệu
phù hợp**, chọn một PDF rồi đọc bảng. Có thể bấm **Mở PDF đã chọn** để xem
nguồn trước khi chạy. Các lượt study đã có trong lịch sử; không cần gọi
model để mở lại.

```powershell
.\run.ps1 table-evidence --ticker FPT --query "lợi nhuận năm 2024" --profile table_cells_v0.8 --list-documents
.\run.ps1 table-evidence --ticker FPT --query "lợi nhuận năm 2024" --profile table_cells_v0.8 --document-version e8509e72eea789549b90734a1bdf3f025967838c9ecdfe2c6faa82259dde6ab2
```

API: `POST /api/research/table-evidence/documents` để xem metadata; request
đọc bảng có `document_version_id` tùy chọn. Preview không sinh run kể cả
khi caller gửi `use_model=true`; model chỉ thuộc thao tác chạy riêng.

Metadata nhỏ ở [data card](../../data/development/document-scope-v0.1/DATA_CARD.md),
[manifest](../../data/development/document-scope-v0.1/manifest.json) và
[validation](../../data/development/document-scope-v0.1/validation.json).
Raw PDF/run/ảnh vẫn lưu ngoài Git. Chưa upload lên Drive hoặc push mốc này.

## Kiểm tra và công việc còn lại

454 kiểm thử toàn bộ đạt; sau bổ sung hiển thị lý do dừng, 51 kiểm thử liên
quan API/bảng/duyệt nguồn đạt. Ruff, định dạng frontend và build đạt. Hai
cảnh báo TestClient/AnyIO và hai cảnh báo lucide bundler vẫn như trước.
Kiểm thử mới bao phủ phạm vi 426 → 213 ở preflight, ID sai mã/năm/không
tồn tại, gateway rỗng trước đọc nội dung, preview không sinh run/model,
JSON scope cũ, replay phát hiện thay version và kiểm Origin.

Kết quả này không nâng độ chính xác đã xác nhận của hệ thống. Bước tiếp
theo về bảng là mở rộng nhận diện đơn vị có locator cho FPT, xử lý nguồn
cần OCR như MWG và có nhãn độc lập; vẫn cần dữ liệu thời gian đủ điều kiện
trước cohort PiT strict, backtest và thực nghiệm Full PiT-HAF.
