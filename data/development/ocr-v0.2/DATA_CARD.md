# OCR vùng v0.2 — Development diagnostic

Ngày 30/10/2026. Mẫu một trang PDF MWG (trang 94), không thay corpus,
24 development cases hoặc nguồn trích xuất bảng hiện có.

- Profile opt-in: Tesserocr 2.12.0 / Tesseract 5.5.3, cùng model vie+eng
  đã pin, 240 dpi / PSM 6, một trang mỗi lượt, vùng chọn tường minh.
- Trợ lý chọn trang/vùng và chép 24 ô từ ảnh sau khi thấy lỗi v0.1.
  Chưa là nhãn độc lập hoặc test giữ kín; không công bố semantic accuracy.
- Khớp nguyên chuỗi bản chép: v0.1 14/24; v0.2 toàn trang 24/24; v0.2
  vùng bảng 24/24. Chỉ bỏ khoảng trắng: 16/24, 24/24, 24/24.
- Chưa chứng minh lợi ích riêng của crop; DPI/PSM cũng cùng thay đổi.
  Chữ/header ngoài mẫu vẫn có lỗi. Không suy năm từ “Năm nay/Năm trước”.
- Hai run mới, sáu trang full replay và numeric audit replay đạt; tám
  native OCR, không LLM; 61 artifact hash bảo vệ không đổi.
- 534 test phần mềm, lint, định dạng/build frontend đạt. UI mở lại được
  vùng, hộp từ và lịch sử lỗi. Chưa có facts được xác nhận/ngữ cảnh OCR.

Manifest/validation chỉ lưu metadata, đường dẫn local, tổng số và hash.
Bản chép 24 ô, PDF, ảnh, TSV, text, audit chi tiết giữ ngoài Git, không
được coi metadata này là bộ dữ liệu để tính accuracy. Cần khôi phục raw
artifacts đúng hash để chạy lại. Không sửa metadata v0.1 hoặc run gốc.

Xem [protocol, kết quả và giới hạn](../../../docs/research/29-ocr-region-numeric-diagnostic.md).
