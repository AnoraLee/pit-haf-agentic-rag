# 29 — OCR theo vùng và đối chiếu chuỗi số

Ngày 30/10/2026. Mốc này bổ sung OCR khoanh vùng và chẩn đoán 24 ô trên
một trang MWG; chưa xác nhận số liệu tài chính hoặc hoàn thành đọc bảng MWG.

## Thay đổi

Profile tùy chọn `pdf_ocr_region_v0.2` dùng cùng runtime và model vie+eng
đã pin ở [v0.1](28-local-ocr-preview.md), render 240 dpi, PSM 6, OEM 1.
Người dùng nhập vùng `[trái, trên, phải, dưới]` theo tỷ lệ toàn trang;
gốc trên trái. Mỗi lượt đúng một trang, các giới hạn PDF/pixel/từ/thời
gian giữ nguyên. `[0,0,1,1]` cho phép đọc toàn trang bằng cùng profile.
Mặc định vẫn là v0.1 (180 dpi, PSM 3, tối đa bốn trang), chưa khóa cấu hình.

Lưu cả ảnh toàn trang và ảnh cắt thực sự đưa vào OCR. Tọa độ OCR tương
đối trong ảnh cắt được cộng offset về ảnh toàn trang rồi đổi sang PDF
points. UI hiển thị vùng đã chạy bằng nét đứt và từ đang chọn bằng vùng
tô; mở kết quả kiểm lại hash, ảnh render và ảnh cắt từ raw PDF, không gọi
OCR. Full replay gọi lại OCR trong thư mục mới và đối chiếu đầu ra.

PSM 6 giả định một khối chữ đồng nhất; PSM 3 tự phân tích bố cục. Đây là
lựa chọn thử nghiệm cho trang bảng, không đảm bảo phù hợp mọi trang.
Cơ sở: [hướng dẫn chất lượng và phân đoạn của Tesseract](https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html).

## Thiết kế phép thử

PDF MWG có version `d4886fc5337ce1d593ed8a3a09f4ae0c73a228d70bad66854dbbeca816d78acf`,
content SHA-256 `e98227cb400d043c1a0e95eaa2706b397fb61001c342713e27b49ad04c17fca7`.
Chọn trang PDF 94 sau khi xem ảnh và lỗi v0.1. Trợ lý chép 12 dòng × hai
cột thành 24 chuỗi đối chiếu, gồm dấu ngoặc và một ô dấu gạch. Đây là
mẫu phát triển cùng nguồn do trợ lý chọn/chép; chưa là nhãn người dùng
độc lập, mẫu giữ kín hoặc benchmark đại diện.

Trước hai lượt OCR mới, lưu plan, hash cấu hình/mã nguồn và bản chép.
Hai nhánh khai báo trước: v0.2 toàn trang và vùng `[.15,.12,.85,.84]`;
giữ cả hai kết quả, không retry hoặc chọn nhánh theo kết quả tốt nhất.
Vùng được chọn có cả tiêu đề/đơn vị trên ảnh. Không bổ sung suy luận
năm nếu OCR không nhận được header.

Đối chiếu gán từ bằng tâm hộp OCR nằm trong từng vùng ô đã khai báo,
giữ nguyên nội dung TSV. Báo hai phép so sánh riêng: khớp nguyên chuỗi,
và khớp khi chỉ bỏ khoảng trắng. Không sửa dấu phân cách, dấu ngoặc, chữ
thành số; dấu `-` không được đổi thành số 0. Lưu ID từ, vùng ô và lỗi
chuỗi/ngoặc/ký tự để kiểm lại. Cách gán theo tâm hộp có thể sai trên bố
cục khác, cần kiểm tra lại trước khi mở rộng.

## Kết quả phát triển

| Cấu hình | Từ OCR | Điểm dưới 80 | Khớp nguyên chuỗi / 24 | Chỉ bỏ khoảng trắng / 24 |
|---|---:|---:|---:|---:|
| v0.1, toàn trang, 180 dpi / PSM 3 | 201 | 68 | 14 | 16 |
| v0.2, toàn trang, 240 dpi / PSM 6 | 182 | 35 | 24 | 24 |
| v0.2, vùng bảng, 240 dpi / PSM 6 | 117 | 21 | 24 | 24 |

Run gốc `20261029T155531Z-79d9ef89`; hai run mới lần lượt
`20261030T015455Z-fe097131` và `20261030T015504Z-6d5f47c2`.
V0.1 có 10 ô không khớp nguyên chuỗi: hai ô chỉ khác khoảng trắng và tám
ô còn sai chữ/số/dấu. Cả hai cấu hình mới khớp 24 chuỗi trợ lý đã chép.
Vì nhánh toàn trang cũng đạt cùng kết quả, chưa có bằng chứng vùng cắt
làm tăng số ô khớp trên mẫu này. DPI và PSM cùng thay đổi, chưa tách được
đóng góp của từng tham số. Số từ thấp hơn không là bằng chứng accuracy.

Hai lượt mới và sáu trang replay (bốn trang v0.1, một trang cho mỗi nhánh
mới) dùng tổng tám lượt native OCR. Cả ba full replay và numeric audit
replay đạt; không gọi LLM. 61 hash bảo vệ, gồm 52 run bảng, hai run OCR
cũ và các artifact case/batch/source audit/metadata, không đổi. Các lượt
lỗi cũ vẫn có trong lịch sử. Không ghi lượt duyệt vào cơ sở dữ liệu thật.

Study local: `outputs/ocr-region-study/20261030T015452Z-e4db3ecd/`.
Raw ảnh/text/TSV, bản chép ô số và numeric audit nằm ngoài Git. Metadata
nhỏ và hash ở [data card](../../data/development/ocr-v0.2/DATA_CARD.md),
[manifest](../../data/development/ocr-v0.2/manifest.json) và
[validation](../../data/development/ocr-v0.2/validation.json).

## Giới hạn và kiểm tra

24/24 chỉ là số chuỗi khớp bản chép phát triển, không phải độ chính xác
OCR tổng thể, ngữ nghĩa, tài chính hay dự báo. Vẫn có lỗi chữ/header ngoài
24 ô. Hai cột trên ảnh là “Năm nay/Năm trước”; `resolved_year` giữ null.
Chưa xác nhận phạm vi doanh nghiệp, mối quan hệ dòng/chỉ tiêu hoặc locator
đơn vị/năm đủ điều kiện cho facts. Chưa nối OCR vào corpus hoặc context
agent; không dùng kết quả này vượt Guard PiT, tạo facts hoặc backtest.

534 kiểm thử toàn bộ, Ruff, Prettier và frontend build đạt. Test mới kiểm
tọa độ ảnh cắt về toàn trang, giới hạn vùng/trang, boolean/NaN, artifact
bị sửa rồi reseal, full replay, dấu âm/dấu phân cách, ô bên cạnh, nguồn
sai, năm chưa xác nhận và tái tính numeric audit. Giữ hai cảnh báo test
phụ thuộc và hai cảnh báo bundler lucide đã có.

UI đã kiểm trên Chrome: mặc định vùng 0–100%, chặn hai trang/vùng đảo
chiều, mở lại nhánh vùng 117 từ/21 điểm thấp, tìm ô có ngoặc âm và xem
overlay trên ảnh. Không chạy OCR hoặc model mới trong kiểm tra UI.

## Dùng thử

Trong **Phân tích tài liệu → Đối chiếu ô bảng với PDF**, chọn riêng PDF,
mở **OCR trang PDF · thử nghiệm** và bật **Khoanh vùng OCR một trang**.
Nhập phần trăm bốn cạnh và một trang. Lịch sử ghi rõ profile; vùng đã
chạy được đọc từ artifact lưu, không lấy từ biểu mẫu đang sửa.

```powershell
.\run.ps1 ocr-preview --ticker MWG --query "lợi nhuận năm 2024" --document-version d4886fc5337ce1d593ed8a3a09f4ae0c73a228d70bad66854dbbeca816d78acf --pages 94 --profile pdf_ocr_region_v0.2 --region .15 .12 .85 .84
.\run.ps1 ocr-preview --replay outputs/ocr-previews/20261030T015504Z-6d5f47c2
.\run.ps1 ocr-numeric-audit --references outputs/ocr-region-study/references/mwg-page94-assistant.json --runs 20261029T155531Z-79d9ef89 20261030T015455Z-fe097131 20261030T015504Z-6d5f47c2
```

Lệnh đối chiếu cần bản chép local; chỉ có metadata Git chưa đủ chạy lại.
`ocr-numeric-audit --replay <thư mục audit>` kiểm và tái tính từ raw đã
lưu, không chạy OCR. Bước tiếp theo là nối locator nhãn/chỉ tiêu, năm,
đơn vị/phạm vi và quy trình duyệt; kiểm thêm trang/doanh nghiệp trước
khi chọn cấu hình cho cohort. Chưa push hoặc upload các artifact mới.
