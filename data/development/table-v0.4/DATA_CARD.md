# Bằng chứng theo ô PDF v0.4 / selector v0.4.1

Ngày: 24/10/2026. Đây là dữ liệu chẩn đoán phát triển, không phải nhãn độc lập,
bộ số liệu tài chính chuẩn hóa đã duyệt hoặc kết quả Full PiT-HAF.

- `hash_refs.json`: kế hoạch được lưu trước kết quả; ba lượt Qwen với ID dài và
  bốn lượt chỉ trích xuất cho ACB/BID/MWG/VNM. Giữ cả lỗi và trường hợp trống.
- `short_refs.json`: ba lượt mới cho cùng FPT/HPG/VCB với cùng bảng ứng viên,
  thay giao diện chọn ID dài bằng C1…C18; không sửa câu trả lời trước đó.
- `validation.json`: nguồn theo hash/trang, ứng viên được chọn, lý do chặn và
  kiểm tra phần mềm. `human_reviewed_facts=0`, `semantic_accuracy=null`.
- `integrity.json`: checksum metadata và hai cấu hình phát triển.

Ba lượt chọn ID dài có 8 lựa chọn bị chặn vì ID không tồn tại. Với mã ngắn,
mỗi lượt chọn 3 ID hợp lệ, không có ID bị chặn. **ID hợp lệ không đồng nghĩa
chọn đúng/đủ chỉ tiêu**. Phạm vi báo cáo HPG vẫn thiếu trong đoạn tiêu đề đã
đọc; FPT chưa bao quát hết các loại lợi nhuận, VCB có lựa chọn chỉ tiêu liên
quan nhưng chưa đủ kết luận cho toàn câu hỏi. Chưa có đánh giá ngữ nghĩa độc lập.

Kiểm tra độ phủ bổ sung không tạo ngữ cảnh lợi nhuận dùng được cho cả bốn mã:
ACB/MWG dừng ở truy xuất; BID chưa nhận diện mẫu tiêu đề; VNM chỉ tạo ứng viên
từ bảng tỷ số, chưa trích được bảng lợi nhuận. Giữ cả bốn kết quả trống này.

Raw PDF vẫn ở `data/cache/evidence/`. Các bảng, word boxes, context,
request/response và snapshot mã nguồn nằm ở `outputs/table-evidence/<run_id>/`.
Metadata Git không đủ để replay nếu thiếu những file local này. Chưa upload
artifact mới lên Drive trong mốc này. Luồng trên frontend và bộ 24 case gốc
được giữ nguyên.

Chi tiết và lệnh chạy: [hồ sơ v0.4](../../../docs/research/19-table-cell-evidence.md).
