# Corporate actions development v0.1

Ngày 06/11/2026. Protocol `corporate_action_development_v0.1` gồm
sổ quyền nhận tiền/cổ phiếu trên fixture tự tạo và đối soát ba sự
kiện chọn từ nguồn. Không có dự báo, backtest thị trường hoặc nhãn
người dùng xác nhận độc lập.

## Phạm vi

`CorporateLedger` ghi nhận gross/tax/net cash, cổ phiếu chờ khả dụng,
phần lẻ bị hủy và receipt theo timestamp. Số lượng được hưởng và
thời điểm kinh tế do bên gọi khai báo; chưa suy từ lịch thanh toán
hoặc holdings. Chỉ hỗ trợ mark giả lập chưa điều chỉnh và hủy phần
lẻ sau khi làm tròn tổng của chủ sở hữu. Chưa tự cập nhật tiền/vị
thế/lệnh trong `backtest-timed`, chưa có stock split hoặc rights issue.

Demo 20 cổ phiếu giá 116, quyền nhận 1 đơn vị tiền/cổ phiếu và tỷ lệ
old:new 20:3, giá sau quyền 100. Giá trị tổng bằng 2.320 qua bốn
checkpoint, trong khi tiền và cổ phiếu khả dụng thay đổi đúng lịch.
Thuế demo bằng 0; các mức thuế trong test chỉ là tham số giả lập.
Giá trị này kiểm kế toán, không là lợi suất hoặc giá cổ phiếu thật.

## Nguồn và giới hạn curation

Sáu thông báo quyền/giao dịch VSD/VSDC cho FPT 2024, HPG 2024 và
VCB 2023 được lưu qua HTTPS có kiểm chứng chỉ, mỗi URL một request,
không retry/redirect/cookie/xác thực. Tái sử dụng downloader giới hạn
`capture-calendar-sources.ps1`; archive vẫn ở `outputs/calendar-sources/`.
Có 20 locator token với raw/body hash. Giá trị được trợ lý nhập sau
khi đọc nguồn, chưa xác nhận ngữ nghĩa độc lập.

Book giữ record date, lịch trả tiền, tỷ lệ cổ phiếu và ngày giao
dịch mới riêng. HPG/VCB có cash basis `not_reported_in_selected_notice`,
không kết luận không có cổ tức tiền trong cả năm. `ex_date`, giờ
ghi có và số lượng được hưởng thật giữ null; lịch sử sự kiện chưa
đầy đủ. Snapshot giá của ba mã vẫn có adjustment basis unknown.

Một bất đồng nguồn HPG được giữ bằng hash/page của BCTC PDF có sẵn
trong corpus, cùng hai giá trị ngày; không tự giải quyết hoặc đổi
ngày trong thông báo. PDF trang được trợ lý xem trực quan; replay chỉ
kiểm đúng bytes/page, không tự xác minh ngữ nghĩa trên ảnh. Một bản
thông báo HOSE được lấy từ mirror và đối chiếu bốn ngày đóng; chưa
chứng nhận toàn bộ lịch HOSE hoặc chữ ký tài liệu. Chi tiết và URL
nằm ở [mốc 38](../../../docs/research/38-corporate-action-ledger.md).

## Kiểm chứng và tái lập

54 test mới và nhóm 133 test liên quan đạt; toàn repository 855 test
đạt, Ruff đạt, còn hai cảnh báo phụ thuộc cũ. Hai run audit/demo và
CLI replay khớp; 127 hash bảo vệ giữ nguyên. Không ghi review DB thật,
gọi LLM, tải thêm giá hoặc sửa blob/case/output cũ. Frontend không
đổi nên không chạy lại build/QA giao diện.

```powershell
.\run.ps1 corporate-actions --demo
.\run.ps1 corporate-actions --replay outputs/corporate-actions/20261106T071034Z-aa43ce9a
.\run.ps1 corporate-actions --replay outputs/corporate-actions/20261106T071036Z-b53cb8b3
```

Demo không cần dữ liệu. Replay audit cần source archive, snapshot KBS
và blob PDF HPG được pin trong manifest; muốn replay mốc cũ phải
khôi phục nguyên các dependency. Chưa xác nhận chủ dự án đã tải các
thư mục mới lên Drive. Git chỉ lưu code/config/metadata nhỏ; raw/PDF/
CSV/run ở local. Source code snapshot không được tự thực thi khi replay.

`eligible_for_execution`, `historical_availability_validated`,
`independent_gold`, `research_result` đều false. Chưa nâng cohort
PiT strict hoặc chạy chiến lược bằng giá thật. Tiếp theo cần xác minh
ex-date/phiên bản sự kiện, bất đồng nguồn, factor theo thời gian và
tích hợp ledger vào protocol thực thi mới.
