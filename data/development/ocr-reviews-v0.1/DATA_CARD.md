# OCR source reviews v0.1

Ngày 02/11/2026. Metadata kiểm tra luồng khai báo đối chiếu OCR local,
không phải bộ nhãn độc lập hoặc kết quả đánh giá độ chính xác.

- Protocol `ocr_cell_reviews_v0.1`; hỗ trợ links v0.1/v0.2 và nguồn tiêu đề.
- 27 kiểm thử mới hoàn toàn trên fixture giả lập; 601 kiểm thử toàn dự án đạt.
- Study chỉ đọc trên ba tổ hợp MWG: 19/24/24 ô; 13/0/0 ô có đủ trường
  nguồn cho biểu mẫu xác nhận. Số này không đo tính đúng ngữ nghĩa.
- 0 phiếu xác nhận thật, không tạo review DB thật, 0 OCR/LLM mới;
  81 hash bảo vệ giữ nguyên. Kiểm tra giao diện đọc/mở phiếu, năm và tên
  để trống, ô kiểm tra chưa chọn, nút lưu bị chặn, ảnh có locator.
- Phiếu là khai báo local, chưa xác thực người nhập hoặc tính độc lập;
  không cấp PiT strict và chưa đưa vào context trả lời/backtest.
- Các run OCR/link cũ và 24 development cases/batch giữ nguyên.

`manifest.json` ghim study và thống kê; `validation.json` ghi phạm vi QA.
Raw study, ảnh UI và SQLite nếu được người dùng tạo sau này ở `outputs/`,
ngoài Git. JSON export chỉ để đọc/lưu, chưa có chức năng import review.

Xem [quy trình, điều kiện và API](../../../docs/research/32-ocr-source-review.md).
