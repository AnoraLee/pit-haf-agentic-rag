# Table cells v0.9 — Development

Ngày: 29/10/2026. Bổ sung đơn vị VND với locator theo cột năm hoặc dòng
khai báo Đơn vị; giữ profile truy xuất và ngân sách v0.8. Không suy hệ số
triệu/tỷ, đổi chuỗi số, OCR hoặc tự xác nhận ngữ nghĩa.

- Study: `20261029T152456Z-e0c716d3`, tám hành động khai báo trước: hai
  version FPT và sáu mã HPG/VCB/ACB/BID/MWG/VNM như trước.
- FPT Vietnamese có 36 ô trích xuất, bốn ô lợi nhuận 2024 vào context,
  so với không có ô ở baseline đọc riêng version v0.8.
- FPT English vẫn không có trang được chọn; MWG vẫn thiếu lớp chữ.
- Sáu mã còn lại giữ các trường context như v0.8, không tính ID/thứ tự.
- Không gọi model, không retry; giữ đủ tám kết quả, kể cả hai từ chối.
- Tám replay mới và 44 replay cũ đạt. 474 kiểm thử phần mềm, Ruff,
  định dạng frontend và build đạt; không phải metric ngữ nghĩa.
- Chưa có facts được người dùng duyệt hoặc gold độc lập;
  `semantic_accuracy=null`, `historical_availability_validated=false`.

`manifest.json` lưu lựa chọn/kết quả và hash cấu hình/artifact trước/sau.
`validation.json` ghi số đo, đối chiếu trường context với baseline và
giới hạn. `integrity.json` pin metadata/cấu hình. Raw PDF/run/ảnh không
đưa vào Git; chưa upload mốc mới lên Drive.

Xem [quy tắc, kết quả và cách dùng](../../../docs/research/26-table-currency-units.md).
