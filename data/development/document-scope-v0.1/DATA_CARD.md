# Document scope v0.1 — Development

Ngày: 29/10/2026. Hai lượt đọc riêng hai bản FPT 2024, profile bảng v0.8
và ngân sách 400 trang mỗi lượt giữ nguyên. Lựa chọn do trợ lý khai báo
trước; không phải tập test giữ kín hoặc nhãn người dùng độc lập.

- Study: `20261029T080618Z-f234f57d`.
- Hai run đều đọc lại 213 trang, không gọi model, không retry.
- Bản English chưa có trang bảng được chọn. Bản Vietnamese chọn trang 50
  và 151 nhưng parser chưa liên kết được đơn vị, nên cả hai run có 0 ô context.
- Hai replay mới đạt; toàn bộ 44 run có seal trong workspace replay đạt,
  gồm 42 run đã tồn tại. Không diễn giải số replay thành tỷ lệ trả lời đúng.
- Không có facts được người dùng duyệt; `semantic_accuracy=null`.
- Corpus/case pack/batch/source audit và cấu hình study được giữ nguyên.

`manifest.json` giữ khai báo, kết quả, hash trước/sau; `validation.json`
ghi kiểm thử và giới hạn. `integrity.json` pin các metadata và cấu hình
đã dùng. Raw PDF, text, output và ảnh nằm ngoài Git; chưa upload mốc mới
lên Google Drive.

Xem [đặc tả và cách chạy](../../../docs/research/25-table-document-scope.md).
