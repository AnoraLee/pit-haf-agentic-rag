# OCR spatial/header links v0.2 — Development

Ngày 02/11/2026. Bổ sung nguồn chữ tiêu đề cùng trang và nhãn nhiều dòng;
chưa khóa cấu hình, chưa là benchmark giữ kín hoặc facts được xác nhận.

- Bốn run OCR mới: sparse trang 93/94 và hai dải tiêu đề PSM 6. Tổng
  chín native OCR gồm năm replay; không LLM. Các run cũ giữ nguyên.
- Sparse đọc thêm ngữ cảnh/nhãn nhưng kém hơn PSM 6 về chuỗi số trang 94:
  13/24 so với 24/24 chuỗi trợ lý chép. Đây chưa là gold độc lập.
- Ghép tường minh OCR tiêu đề vào thân bảng khi cùng PDF/trang/ảnh/dpi
  và chỉ thay chữ phía trên số. Mỗi từ giữ run/word ID nguồn riêng.
- Trang 93 có 19 ô ứng viên: 13 nhãn, 19 cột kỳ/đơn vị/scope/kỳ tài chính;
  7 ô có nhãn ghép nhiều dòng. Còn lỗi nhãn, số và thiếu ô.
- Trang 94 giữ thân PSM 6 có 24 ô, 18 nhãn, 24 cột kỳ/đơn vị và 4 ô có
  nhãn nhiều dòng; scope/kỳ tài chính vẫn thiếu, không lấy từ trang 93.
- Năm tuyệt đối của các ô vẫn chưa xác nhận; không tự trừ một cho “Năm
  trước”. Không suy nguồn từ metadata hoặc tự sửa chữ/số.
- Sáu snapshot mới và bốn cũ replay đạt; 574 test phần mềm, lint/format/
  build đạt. Chưa có review người dùng, semantic accuracy hoặc facts.

Raw PDF/PNG/TSV/text/snapshot và bản chép đối chiếu nằm ngoài Git. File
manifest/validation chỉ lưu provenance, số đếm, hash và đường dẫn. Xem
[protocol, kết quả và giới hạn](../../../docs/research/31-ocr-header-spatial-links.md).
