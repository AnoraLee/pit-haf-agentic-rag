# Chọn trang theo cột năm v0.8 — development

Ngày: 29/10/2026. Metadata study `20261029T024503Z-34ac0409`; không phải gold,
accuracy hoặc tập test độc lập. Danh sách bảy mã và cấu hình được ghi trước
kết quả; giữ nguyên cấu hình trong suốt study, tối đa 0 generation mới.

- `manifest.json`: kế hoạch, sáu raw run, lỗi FPT trước khi tạo run và hash
  cấu hình/artifact gốc trước/sau.
- `validation.json`: số context, cảnh báo phạm vi, số trang bị loại và kiểm tra.
- `integrity.json`: checksum hai file trên và hai cấu hình v0.8. Data card
  không nằm trong checksum để mô tả có thể cập nhật độc lập kết quả.

Context v0.7 → v0.8: FPT vẫn bị chặn (>400 trang), HPG 7 → 7, VCB 0 → 5,
ACB 2 → 2, BID 4 → 4, MWG 0 → 0, VNM 4 → 4. VCB có ba ô trang 67 và hai ô
tóm tắt trang 16 thiếu phạm vi. Chưa thể tính các số đếm này như đáp án đúng.

Policy dùng tiêu đề năm/ngày dạng cột với đơn vị gần đó, không dùng năm xuất
hiện đơn thuần trong nội dung/chân trang. Trang không nhận diện đủ tiêu đề năm
bị loại trong truy vấn bảng số liệu. Không có lookup doanh nghiệp/trang/đáp án.
Giữ parser chữ v0.7, parser ô v0.5, policy context v0.6 và giới hạn 400 trang,
ba trang vào bảng, 18 ô/9.000 ký tự context, một model call tối đa nếu bật.
Study này không gọi model.

443 kiểm thử phần mềm đạt, Ruff và frontend build đạt; 40 raw run study
v0.4–v0.8 replay đạt (34 cũ + 6 mới), gồm lỗi trước generation đã lưu ở mốc
cũ. FPT là lỗi preflight trong manifest, không nằm trong 40 raw run. Case,
batch và source audit gốc không đổi; sáu run mới replay và so điều kiện cột
năm từ văn bản PDF đã đối chiếu raw.

`human_reviewed_facts=0`, `semantic_accuracy=null`, `independent_gold=false`.
Thiếu OCR/tiêu đề xa hoặc nhãn phức tạp vẫn có thể bỏ sót bảng đúng. Kiểm tra
năm không thay thế PiT availability, phạm vi hay ý nghĩa chỉ tiêu. Chưa có kết
quả backtest hoặc Full PiT-HAF mới.

Raw PDF/lớp chữ, các run và ảnh kiểm tra ở `data/cache/evidence/` và `outputs/`,
không nằm trong metadata này. Chưa upload artifact mới lên Drive hoặc push
thay đổi v0.8 trong mốc này.

Xem [quy tắc, kết quả và hướng dẫn](../../../docs/research/24-annual-table-page-gate.md).
