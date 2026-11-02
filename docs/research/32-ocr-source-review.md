# 32 — Phiếu đối chiếu OCR gắn với nguồn

Ngày 02/11/2026. Protocol `ocr_cell_reviews_v0.1` bổ sung phiếu ghi bản
chép, nhận xét và lịch sử cho từng ô OCR. Phiếu tách khỏi các lượt OCR và
snapshot liên kết đã lưu; chưa đưa số vào context trả lời hoặc backtest.

## Cách dùng

1. Chọn doanh nghiệp, kỳ và một PDF ở **Phân tích tài liệu**. Mở một lượt
   OCR đã lưu, liên kết ô số và chọn ô cần kiểm tra.
2. Bấm từng trường để xem vị trí chữ trên ảnh. Trong **Ghi kết quả đối
   chiếu ô số**, bấm **Mở phiếu đối chiếu**. Đọc phiếu không tạo database.
3. Nhập tên/ký hiệu người đối chiếu và trạng thái: đang đối chiếu, cần
   thêm bằng chứng, không chấp nhận hoặc đã đối chiếu đủ. Hai trạng thái
   cần bằng chứng/không chấp nhận yêu cầu lý do và khai báo đã xem PDF.
4. Khi xác nhận đủ, kiểm tra năm mục chỉ tiêu, chuỗi số, năm, đơn vị và
   phạm vi. Tự nhập năm đã đọc, chọn cơ sở xác định năm và khai báo đã
   đối chiếu ảnh. Có thể sửa bản chép chỉ tiêu/chuỗi số nhưng phải ghi
   lý do. Đơn vị/phạm vi phải khớp locator nguồn; nếu sai thì yêu cầu
   thêm bằng chứng thay vì điền đè để bỏ qua kiểm tra.
5. Lưu phiếu, xem lịch sử hoặc tải JSON. Khi có xung đột, tải lại phiếu
   và kiểm tra bản mới trước khi lưu. Chuyển về đang đối chiếu giữ lại
   lần xác nhận cũ trong lịch sử. Mỗi thay đổi biểu mẫu yêu cầu khai báo
   lại; thay chỉ tiêu/giá trị/năm cũng bỏ đánh dấu phần kiểm tra liên quan.

Ảnh PDF nằm cạnh biểu mẫu và giữ trên màn hình khi cuộn cột trái trên
desktop; màn hình hẹp xếp nối tiếp. Không tự điền tên người đối chiếu,
năm hoặc các ô kiểm tra cho phiếu mới.

## Điều kiện nguồn và năm

Phiếu ghim version/hash PDF, seal lượt OCR thân bảng và tiêu đề, policy
và hash policy, candidate, trang, cột, tất cả trường/locator/word refs,
nhãn nhiều dòng và lý do cần kiểm tra. API tái kiểm nguồn qua luồng
cell-links trước cả đọc lẫn lưu; thay nguồn không âm thầm giữ xác nhận.

Thiếu nhãn, giá trị, tiêu đề kỳ, đơn vị, phạm vi hoặc cơ sở năm được hỗ
trợ thì không xác nhận được. Ô dấu gạch chưa được diễn giải thành số 0.
Chuỗi số được lưu nguyên văn, không tự đổi dấu/chấm/phẩy hoặc tính giá trị.

- Cột có năm tường minh: năm nhập phải đúng năm của locator cột.
- Cột “Năm nay/Năm trước”: chỉ hỗ trợ dòng kỳ tài chính **năm** ngay trên
  cùng trang, ghi ngày kết thúc hợp lệ **31/12**, nhất quán với năm trong
  dòng. Người đối chiếu phải xác nhận cách quy theo năm dương lịch và
  ghi giải thích. Backend kiểm năm nhập theo phương pháp đã chọn; không
  tự điền năm trước vào biểu mẫu. Kỳ không trùng năm dương lịch bị chặn.
- Không lấy năm từ tên PDF, metadata doanh nghiệp hoặc trang trước.

`resolved_year`, `human_reviewed` và `automatic_fact` trong kết quả OCR
gốc không thay đổi sau phiếu. Năm/bản chép do người đối chiếu nhập chỉ
nằm trong `interpretation` của revision xác nhận.

## Lưu trữ và ý nghĩa của xác nhận

SQLite local: `outputs/ocr-reviews/reviews.sqlite3`, được tạo khi có lần
lưu hợp lệ đầu tiên. Mỗi lần lưu thêm event mới, giữ bản gốc và chuỗi
`previous_revision`; SHA-256 kiểm payload và source binding. Transaction
`BEGIN IMMEDIATE` chặn hai người ghi đè từ cùng bản cũ. Cùng ứng viên
nhưng khác policy hoặc nguồn tiêu đề có kênh lịch sử riêng.

Đây là **khai báo của người đối chiếu tại máy**, không có xác thực danh
tính hoặc kiểm tra năng lực/độ độc lập của người nhập. Hash/revision
giúp phát hiện sai lệch thông thường; không chống người quản trị sửa,
xóa rồi tính lại toàn bộ database. Sao lưu SQLite khi ứng dụng đã dừng;
JSON export giữ provenance/lịch sử để đọc, chưa có chức năng nhập lại.

Kể cả trạng thái xác nhận, `independent_gold`,
`independent_semantic_validation`, `historical_availability_validated`
và `eligible_for_answer_context` vẫn false; semantic accuracy vẫn null.
Phiếu không xác nhận ngày công bố hoặc cấp điều kiện PiT strict. Chưa
có quy trình nhãn độc lập/phân xử hoặc đánh giá ngoài mẫu.

## Kiểm tra phát triển

Kiểm tra chỉ đọc trên MWG cùng PDF ở mốc 31:

| Nguồn | Ô ứng viên | Đủ trường để mở phần xác nhận | Phiếu thật đã lưu |
|---|---:|---:|---:|
| Trang 93 sparse + tiêu đề riêng, links v0.2 | 19 | 13 | 0 |
| Trang 94 PSM 6 + tiêu đề riêng, links v0.2 | 24 | 0 | 0 |
| Trang 94 PSM 6 không tiêu đề riêng, links v0.1 | 24 | 0 | 0 |

13 chỉ là số ô không thiếu điều kiện nguồn của biểu mẫu, **không phải
số ô đúng**. Trang 94 vẫn thiếu phạm vi/kỳ tài chính, không truyền từ
trang 93. Không ghi review DB thật, không tự nhận vai người duyệt.
81 hash artifact cũ giữ nguyên. Mốc này gọi thêm 0 OCR và 0 LLM.
Study: `outputs/ocr-review-development/20261102T135328Z-f23153f3/`.

27 kiểm thử mới dùng nguồn giả lập để kiểm điều kiện xác nhận/sửa bản
chép, kỳ tương đối/ngoài 31/12, rút xác nhận, cạnh tranh ghi, sửa payload,
source binding và chuỗi revision; API kiểm Origin, nguồn thật trong
fixture, conflict 409, lỗi nguồn và export. Không ghi nhãn lên corpus.
Toàn bộ kiểm thử và QA giao diện được ghi tại
[validation](../../data/development/ocr-reviews-v0.1/validation.json).

## API

`GET /api/research/ocr-previews/{run_id}/cell-links/reviews` trả điều kiện,
binding và lịch sử. Query `policy_id` mặc định v0.1, `header_run_id` tùy
chọn giống cell-links. POST cùng đường dẫn nhận `OcrReviewInput`, phải
khớp run/candidate/binding và revision mới nhất. GET thêm `/export` tải
JSON không cache. Không dùng các endpoint này để cấp xác nhận độc lập.

Mốc tiếp theo: liên kết ngữ cảnh nhiều trang có điều kiện và thu bằng
chứng công bố cho cohort, sau đó kiểm chứng độc lập trước khi đưa facts
vào câu trả lời/thực nghiệm. Động cơ backtest có thể phát triển riêng
với dữ liệu giả lập và giá được xác minh theo roadmap.
