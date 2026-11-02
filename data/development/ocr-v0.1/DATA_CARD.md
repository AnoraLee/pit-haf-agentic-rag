# OCR preview v0.1 — Development

Ngày: 29/10/2026. Bản xem trước OCR local, không thay corpus hoặc facts.
Tesserocr 2.12.0 / Tesseract 5.5.3, bộ vie+eng tessdata_fast ghim revision
và hash, 180 dpi, PSM 3, OEM 1, tối đa bốn trang mỗi run và 60 giây/trang.

Trợ lý chọn trước các trang PDF 2, 3, 48, 94 của MWG 2024 sau khi xem ảnh:
mẫu ký, bìa, nội dung và bảng; chưa là test giữ kín hoặc nhãn độc lập.

- Run `20261029T155343Z-f1c67278`: giữ bốn lỗi adapter chờ TSV header.
- Sửa adapter để đọc TSV native, không đổi model/trang/cấu hình.
- Run `20261029T155531Z-79d9ef89`: 509 từ; 133 từ có điểm dưới 80.
  Cả bốn trang chạy lại OCR đạt đối chiếu. Tổng gồm 12 lượt native OCR
  qua hai run và một replay; không gọi LLM.
- Có lỗi dấu, chữ và chuỗi số bị chia/nhận sai; điểm cao vẫn có thể sai.
  Chưa có gold độc lập, CER/WER, facts được duyệt hoặc PiT strict.
- 503 kiểm thử phần mềm đạt; không phải accuracy OCR/tài chính.
- Hash case pack, batch, source audit, 52 run bảng cũ và run OCR lỗi
  được giữ nguyên. Chưa upload raw artifacts lên Drive hoặc push.

`manifest.json` giữ cả hai study, không thay lượt lỗi bằng lượt sau.
`validation.json` ghi kết quả/giới hạn. `integrity.json` pin metadata và
cấu hình. Raw PNG/text/TSV/JSON và snapshot implementation ở outputs.

Xem [đặc tả, kết quả và cách chạy](../../../docs/research/28-local-ocr-preview.md).
