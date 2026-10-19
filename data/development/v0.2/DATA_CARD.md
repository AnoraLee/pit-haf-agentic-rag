# Bộ case phát triển 0.2 — lọc doanh nghiệp và kỳ báo cáo

Giữ nguyên 24 ID/câu hỏi/truy vấn của v0.1 (8 case × FPT/HPG/VCB). Chỉ tạo
pack nguồn mới; pack cũ không bị ghi đè. Trước xếp hạng, yêu cầu PDF thuộc đúng
mã chính, loại báo cáo và `reporting_period=2024`. Case kế hoạch 2025 cũng đọc
báo cáo 2024 để tìm thông tin kế hoạch; đây là lựa chọn phát triển được ghi rõ.

Pack local: `outputs/development-cases/20261019T030531Z-8ef1bf33/`.
`cases.jsonl` chứa đoạn nguyên văn, `review.md` là phiếu đọc, template vẫn giữ
24 hàng pending. Git chỉ có metadata/checksum, không chứa đoạn nguồn/đáp án.

Chẩn đoán metadata trên cùng 24 câu hỏi: 36/72 tham chiếu của bản cũ khớp bộ
lọc mới; bản mới có 72/72 khớp. Đây là kết quả của bộ lọc theo cấu hình, **không
phải precision/recall, human gold hoặc xác nhận đúng kỳ về ngữ nghĩa**. Cần
đọc nguồn để phân biệt số thực tế/kế hoạch, so sánh năm trước, mẹ/con và đơn vị.

Chấm qua **Phân tích tài liệu → Chấm case phát triển**. Mở nguồn, chọn trạng
thái, nhập người chấm/đáp án/quote, đánh dấu đã kiểm tra rồi lưu. Có thể lưu
pending làm bản nháp. Trích dẫn phải xuất hiện duy nhất trong đoạn đã pin;
mọi số cần khớp quote. PDF lưu đúng content hash có link mở ngay trong phiếu.

Các revision được nối vào `outputs/development-reviews/<pack_id>/reviews.jsonl`,
có parent revision, hash, thời điểm lưu và checksum case gốc. Backend một
process local khóa khi đọc/ghi; optimistic revision chặn ghi đè phiên chấm mới.
Không sửa template/case gốc. Hash chain không chứng minh danh tính người chấm,
độ đúng ngữ nghĩa hoặc chống được mọi rollback của chủ máy. Export JSONL để
kiểm bằng `development-cases --pack ... --check-reviews ...`.

Tại lúc tạo bộ: **0 case được người khai báo duyệt**. Không có nguồn đủ điều
kiện PiT strict; chấm câu trả lời không tự tạo proof thời gian/phiên bản. Không
đưa annotation vào context model, không tính accuracy trên case chưa duyệt.
Toàn văn và annotation chỉ lưu local theo quyền nội dung của corpus v0.5.

Xem [quy trình và các lượt chạy](../../../docs/research/15-scoped-retrieval-and-review.md).
