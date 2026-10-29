# Lớp chữ PDF thay thế v0.7 — development

Ngày: 29/10/2026. Metadata của study `20261029T015054Z-2b5a187a`, không phải
dataset nhãn hoặc kết quả accuracy. Corpus/case/batch/audit gốc không bị thay.

- `manifest.json`: bảy mã và câu hỏi chọn trước kết quả, tối đa 0 model call;
  giữ sáu run và lỗi FPT vượt ngân sách trước khi tạo raw run.
- `validation.json`: số context trước/sau, trạng thái kiểm thử và giới hạn.
- `integrity.json`: hash manifest/validation và hai cấu hình mới. Data card
  không nằm trong checksum để mô tả có thể cập nhật độc lập kết quả.

Context v0.6 → v0.7: FPT 6 → bị chặn (>400 trang), HPG 7 → 7, VCB 3 → 0,
ACB 0 → 2, BID 4 → 4, MWG 0 → 0, VNM 4 → 4. Các ô đều chưa được người dùng
duyệt. ACB có ứng viên mới nhưng VCB hồi quy; không thay v0.6 làm mặc định.
Không retry hoặc bỏ kết quả xấu. MWG 96 trang không có lớp chữ; chưa OCR.

V0.7 dùng pdfplumber 0.11.9 đọc lại tối đa 400 trang sau lọc metadata/allowlist,
rồi dùng cùng xếp hạng mục tài chính v0.3, parser ô v0.5 và policy v0.6.
Ngân sách model không đổi, nhưng có thêm chi phí đọc lại PDF nên không gọi là
so sánh cùng ngân sách tính toán. Câu hỏi ngoài topic hỗ trợ dừng.

Sáu run mới và 28 run study cũ đều replay đạt (34 tổng); lỗi FPT chỉ nằm trong
manifest, không được tính replay thành công. Replay không phải độ chính xác
ngữ nghĩa. 426 kiểm thử phần mềm, Ruff và frontend build/format đạt. Lỗi
guard đường dẫn Windows khi hai writer tạo database duyệt lần đầu đã được
sửa, kiểm lại bốn lần đồng thời trong suite cuối.

`human_reviewed_facts=0`, `semantic_accuracy=null`, `independent_gold=false`.
Chưa có kết quả PiT strict, backtest hoặc Full PiT-HAF mới. Chỉ metadata nhỏ
được đưa vào Git; raw PDF, lớp chữ, run, ảnh kiểm tra và request/response ở
`data/cache/evidence/` và `outputs/`, cần gói riêng để mở/replay. Chưa upload
artifact mới lên Drive.

Xem [hướng dẫn và kết quả đầy đủ](../../../docs/research/23-alternate-pdf-text.md).
