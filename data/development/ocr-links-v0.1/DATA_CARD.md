# OCR cell links v0.1 — Development

Ngày 02/11/2026. Liên kết hình học trên các lượt OCR MWG đã lưu, không
tạo nhãn xác nhận hoặc facts. Policy chưa khóa, không là test giữ kín.

- Bốn nguồn OCR cũ, gồm một lượt có cả bốn trang lỗi. Không gọi OCR/LLM
  mới, không dùng bản chép 24 ô làm đầu vào hay bảng tra của thuật toán.
- Trang 94: v0.1 có 14 ô ứng viên; v0.2 toàn trang và vùng có 24 ô mỗi
  lượt. Có vị trí nhãn dòng và chữ VND, nhưng kỳ/phạm vi vẫn thiếu.
- Nối được nhãn không chứng minh nhãn đúng: còn chữ vô nghĩa hoặc thiếu
  phần xuống dòng. Mọi ô cần duyệt, không tự chữa số/chữ hoặc suy năm.
- Chặn năm điều hướng bị nhầm thành năm cột và mảnh số bị lấy làm toàn
  bộ giá trị; thêm test hồi quy sau quan sát phát triển.
- Bốn snapshot/replay đạt, 65 hash cũ không đổi. Không tạo review DB thật.
- 553 test phần mềm, lint, định dạng frontend và build đạt; không phải
  semantic accuracy hoặc kết quả dự báo.

Manifest/validation lưu đường dẫn, số đếm và hash; raw links/ảnh/PDF/TSV
và implementation snapshot ở outputs ngoài Git. Giữ nguyên metadata OCR
v0.1/v0.2, case pack, batch và nguồn audit cũ. Chưa push/upload artifact.

Xem [quy tắc, kết quả và cách dùng](../../../docs/research/30-ocr-cell-context.md).
