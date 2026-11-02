# 28 — OCR local có vị trí nguồn

Hoàn tất giao diện: 30/10/2026; các lượt OCR bên dưới chạy ngày 29/10/2026.
Cập nhật tiếp theo: [v0.2 khoanh vùng và chẩn đoán 24 ô](29-ocr-region-numeric-diagnostic.md).
Tùy chọn `pdf_ocr_preview_v0.1` là lớp xem trước OCR,
không thay parser bảng v0.9 hoặc corpus đã công bố. Mặc định đọc bảng,
agent và tập 24 case vẫn giữ nguyên.

## Luồng xử lý

Chọn tường minh version PDF trong scope doanh nghiệp/kỳ; giao với gateway
trước đọc raw PDF. Tối đa bốn số trang PDF khác nhau, không tự mở rộng ra
toàn bộ tài liệu hoặc chọn trang khác khi có lỗi. Mỗi trang chạy trong
một process riêng, tối đa 60 giây gồm render/OCR, một luồng OpenMP, không
retry. Giới hạn PDF 128 MiB, ảnh 8 triệu pixel, 8.000 từ mỗi trang; render
180 dpi, Tesseract OEM=1/PSM=3, ngôn ngữ `vie+eng`.

Dependency tùy chọn `tesserocr==2.12.0` được ghim trong lockfile; wheel
Windows đã đo có Tesseract 5.5.3 và Leptonica 1.87.0. Hai traineddata
`tessdata_fast` vie/eng được pin revision và SHA-256 trong
[cấu hình](../../configs/pdf_ocr_v0_1.json). Setup chủ động mới tải file;
worker không tự tải và không truyền PDF ra ngoài. Tài liệu upstream:
[tesserocr](https://github.com/sirfz/tesserocr),
[bộ ngôn ngữ Tesseract](https://tesseract-ocr.github.io/tessdoc/Data-Files-in-different-versions.html).

Mỗi run lưu metadata nguồn, audit gateway, bản cấu hình, snapshot ba module
OCR và lockfile, ảnh render, UTF-8 text, TSV nguyên gốc, tọa độ từng từ,
điểm nhận dạng và stderr/stdout. Mọi file được pin trong seal. Có lỗi ở
một trang vẫn giữ đúng trang đó và tiếp tục các trang đã yêu cầu.

Tọa độ pixel trên ảnh được quy đổi sang PDF points của trang hiển thị,
gốc trên trái sau khi áp dụng rotation PDF. Đây là hộp từ OCR, không phải
offset ký tự trong lớp chữ PDF gốc. Không sửa lỗi chính tả/dấu hoặc ghép
lại chuỗi số; từ có điểm thấp vẫn giữ nguyên và được đánh dấu.

Mở UI kiểm hash/nguồn registry, parse lại TSV và render lại ảnh từ raw PDF;
không tự chạy lại OCR. CLI replay tạo một thư mục mới, chạy OCR lại bằng
cùng model/runtime rồi đối chiếu toàn bộ JSON text/TSV/ảnh/tọa độ. Run chỉ
có các trang lỗi không được gọi là OCR replay thành công. Model/hash hay
policy khác sẽ bị chặn, không tự thay engine hoặc bộ ngôn ngữ.

## Hai lượt triển khai MWG được giữ lại

Chọn bốn trang PDF 2, 3, 48, 94 trước khi OCR, sau khi xem ảnh để có mẫu
trang ký, bìa, nội dung và bảng. Đây là mẫu phát triển do trợ lý chọn,
không là test giữ kín hoặc gold độc lập.

Lượt `20261029T155343Z-f1c67278` giữ cả bốn lỗi tích hợp: API
`GetTSVText` trả dữ liệu không có dòng header, trong khi adapter ban đầu
chờ header như TSV từ CLI. Raw ảnh/text/TSV và log lỗi vẫn còn. Không
đổi mô hình, dpi, PSM hoặc trang để sửa kết quả; adapter được sửa để đọc
đúng định dạng native, có thêm test hồi quy và chạy một run mới.

Lượt sau `20261029T155531Z-79d9ef89`:

| Trang PDF | Số từ OCR | Số từ có điểm dưới 80 |
|---|---:|---:|
| 2 | 26 | 5 |
| 3 | 16 | 13 |
| 48 | 266 | 47 |
| 94 | 201 | 68 |
| Tổng | 509 | 133 |

Cả bốn trang chạy lại OCR đạt đối chiếu. Tổng hai lần triển khai và một
lần replay có 12 lượt native OCR; không gọi LLM. Hash 52 run bảng cũ,
case pack, batch, source audit, metadata v0.9 và run OCR lỗi không đổi.
Hai manifest study giữ nguồn gốc lựa chọn, lỗi, hash trước/sau. Raw run
nằm ngoài Git; metadata nhỏ ở [data card](../../data/development/ocr-v0.1/DATA_CARD.md),
[manifest](../../data/development/ocr-v0.1/manifest.json),
[validation](../../data/development/ocr-v0.1/validation.json).

## Chất lượng và giới hạn

503 kiểm thử toàn bộ, Ruff, định dạng frontend và build đạt. Test mới
kiểm TSV native không header, giới hạn trang/pixel/từ/thời gian, gate
trước đọc nguồn, checksum model, tọa độ, sửa artifact rồi reseal, full
OCR replay, lỗi một phần, kiểm Origin và API ảnh. Hai cảnh báo TestClient/
AnyIO và hai cảnh báo bundler lucide vẫn như trước.

Số từ và điểm nhận dạng không đo accuracy. Quan sát phát triển thấy lỗi
dấu, chữ, header và chuỗi số bị tách/nhận sai ở bảng; ngay cả từ có điểm
cao vẫn có thể sai. Không tạo đáp án hoặc xác nhận số tài chính từ OCR.
Chưa có người chấm độc lập hoặc CER/WER. Không lấy văn bản này thay corpus
cũ, source audit hoặc context của agent.

Một số bảng dùng cột “Năm nay/Năm trước”; riêng OCR không đủ xác lập năm
cho từng ô. Cần locator bổ sung và quy tắc đã kiểm chứng trước khi nối vào
luồng facts. OCR cũng không bổ sung bằng chứng ngày công bố hay phiên bản
lịch sử để vượt Guard PiT.

## Cài và dùng

```powershell
$env:UV_PROJECT_ENVIRONMENT = ".venv312"
uv sync --locked --dev --extra ocr --python 3.12
.\run.ps1 ocr-preview --setup-models
.\run.ps1 ocr-preview --ticker MWG --query "lợi nhuận năm 2024" --document-version d4886fc5337ce1d593ed8a3a09f4ae0c73a228d70bad66854dbbeca816d78acf --pages 2 3 48 94
.\run.ps1 ocr-preview --replay outputs/ocr-previews/20261029T155531Z-79d9ef89
```

Tại [Phân tích tài liệu](http://localhost:8501/#analysis), chọn MWG, năm
2024, **Xem tài liệu phù hợp**, chọn riêng PDF. Mở **OCR trang PDF · thử
nghiệm**, nhập số trang hoặc chọn lượt đã lưu và bấm **Mở bản OCR**.
Chọn trang, tìm chữ/số rồi chọn từ để xem vùng tô trên ảnh. Không cần gọi
model hoặc OCR lại để mở kết quả đã lưu.

API tạo/xem lịch sử ở `/api/research/ocr-previews`; body tạo có
`document_version_id` và `pages`, cùng scope thời gian. Cùng khóa tài
nguyên phân tích với báo cáo local; kiểm Origin và số trang ở server.

Chưa push hoặc upload artifact mới lên Drive. Bước tiếp theo là kiểm
chất lượng OCR trên các vùng/bảng có nhãn đối chiếu độc lập và nối bằng
chứng đủ năm/đơn vị/phạm vi vào pipeline; không đánh dấu MWG đã giải quyết
trích xuất số liệu chỉ vì OCR chạy được.
