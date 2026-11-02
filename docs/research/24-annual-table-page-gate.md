# 24 — Chọn trang bảng theo tiêu đề cột năm

Ngày: 29/10/2026. Profile thử nghiệm `table_cells_v0.8` xử lý hồi quy chọn
trang của VCB ở v0.7 bằng điều kiện cột năm. Không sửa protocol, cấu hình
hoặc kết quả v0.4–v0.7; mặc định frontend/API vẫn v0.6.

## Nguyên nhân và quy tắc mới

Trên lớp chữ đọc lại, trang trình bày lại có các cụm lợi nhuận nên xếp hạng
cao, nhưng tiêu đề `31/12/2023 31/12/2023 Chênh lệch` chưa được nhận diện là
cột năm. Nội dung/trang bên cạnh lại nhắc 2024 và 2025. Vì vậy năm trong thân
bài không đủ để quyết định bảng thuộc kỳ đang hỏi.

[table_page_policy.py](../../src/pit_haf/data/table_page_policy.py) nhận diện
dòng cột có năm hoặc `31/12/YYYY`, cho phép ngày/năm lặp, chữ Năm, Chênh lệch
và một tập từ tiêu đề như STT/Chỉ tiêu/Thuyết minh. Dòng phải có đơn vị tiền
tệ trong cửa sổ lân cận giới hạn; câu kể, ngày phê duyệt hoặc footer thường
niên không được dùng như tiêu đề cột. Cấu hình ở
[table_page_policy_v0_8.json](../../configs/table_page_policy_v0_8.json).

Với truy vấn bảng số liệu thuộc lợi nhuận, thu nhập/doanh thu, tài sản/nợ hoặc
tiền, năm yêu cầu phải nằm trong tiêu đề được nhận diện. Không có tiêu đề thì
dừng ở trang đó; tiêu đề chỉ có năm khác cũng bị loại. Các phép kiểm này áp
dụng sau lọc doanh nghiệp/kỳ/allowlist và trước xếp hạng cửa sổ. Không dùng
lookup theo doanh nghiệp, số trang, case hoặc đáp án tham chiếu.

Vẫn dùng parser chữ v0.7, giới hạn đọc lại 400 trang, xếp hạng mục v0.3, parser
ô v0.5 và policy lọc/gộp context v0.6. Ngân sách vào model không đổi: tối đa ba
trang PDF, 18 ô, 9.000 ký tự, một generation nếu bật, không retry. Không gọi
đây là đánh giá độc lập hay bằng chứng loại bỏ hoàn toàn rò rỉ thời gian.

Trace có `annual_page_policy` với hash cấu hình và `page_year_checks` cho mỗi
trang, gồm các tiêu đề quan sát, năm và lý do giữ/loại. Run pin hash policy.
Replay đọc lại selected text từ raw PDF, kiểm policy và điều kiện năm của
trang được chọn, rồi replay ô/context như cũ. Chưa tái chạy toàn bộ xếp hạng
mọi trang khi replay; hash không chứng minh ý nghĩa hoặc độ phủ.

## Study bảy mã, không gọi model

`20261029T024503Z-34ac0409` ghi trước cùng bảy mã/câu hỏi lợi nhuận 2024 như
mốc v0.7. Hash cấu hình trước/sau khớp; giữ mọi lỗi, không retry hoặc thay kết
quả bằng profile khác. Đây là development đã quan sát để sửa lỗi, chưa phải
tập test cuối.

| Mã | Context v0.7 | Context v0.8 | Kết quả |
|---|---:|---:|---|
| FPT | — | — | Metadata có 426 trang, vượt giới hạn 400; lỗi preflight được giữ |
| HPG | 7 | 7 | Chọn trang 12, ứng viên chưa duyệt |
| VCB | 0 | 5 | Ba ô trang 67 và hai ô tóm tắt trang 16 |
| ACB | 2 | 2 | Giữ trang 64 |
| BID | 4 | 4 | Chọn trang 76/80; số ô context giữ nguyên |
| MWG | 0 | 0 | 96 trang chưa có chữ; chưa OCR |
| VNM | 4 | 4 | Chọn trang 92, ứng viên chưa duyệt |

Tại VCB, trang PDF 105 chỉ có cột 2023 nên bị loại; trang 67 có cột 2024/2023
được giữ. Đã xem ảnh cả hai trang để kiểm bố cục. Tổng cộng loại 6 trang có
tiêu đề khác kỳ và 79 trang chưa nhận diện được tiêu đề năm. Ba ô từ trang
67 không tự trở thành facts. Hai ô trang tóm tắt dùng đơn vị tỷ đồng và thiếu
locator phạm vi; giữ riêng, không gộp với triệu VND và không cho xác nhận khi
thiếu locator theo luồng duyệt hiện tại. Cờ nhãn xuống dòng cũng được giữ.

Sáu raw run mới replay đạt; FPT chỉ có lỗi trong manifest, không tính replay.
40 raw run study v0.4–v0.8 replay đạt, gồm cả run lỗi trước generation cũ:
đây là toàn vẹn/tái lập, không phải 40 câu trả lời thành công. Hash 34 run cũ,
case pack, batch và source audit không đổi. Đối chiếu 24 câu gốc vẫn 8 đủ ngữ
cảnh, 12 một phần, 4 thiếu; chưa là nhãn độc lập.

## Sử dụng và kiểm tra giao diện

Tại [Phân tích tài liệu](http://localhost:8501/#analysis), bật **Đọc lại lớp
chữ PDF · thử nghiệm**, rồi chọn **Lớp chữ + kiểm tra cột năm · v0.8** trong
**Cách chọn trang thử nghiệm**. Tùy chọn lớp chữ mặc định vẫn tắt; khi bật,
v0.7 vẫn là lựa chọn đầu tiên để giữ hành vi trước. Nút gọi AI độc lập và
mặc định tắt.

Kết quả v0.8 hiển thị số trang bị loại do sai kỳ/thiếu tiêu đề. Mỗi dòng ô
hiển thị đơn vị riêng; dòng thiếu phạm vi có cảnh báo để không đọc nhầm các
số từ bảng tóm tắt và bảng chính. Lịch sử duyệt vẫn gắn từng vị trí nguồn,
không tự điền xác nhận sau khi mở run.

```powershell
.\run.ps1 table-evidence --ticker VCB --query "lợi nhuận năm 2024" --profile table_cells_v0.8
.\run.ps1 table-evidence --replay outputs/table-evidence/20261029T024654Z-48878cc7
```

API hỗ trợ `profile_id=table_cells_v0.8`. CLI mặc định vẫn v0.4, frontend/API
vẫn v0.6. Metadata nhỏ ở [data card](../../data/development/table-v0.8/DATA_CARD.md),
[manifest](../../data/development/table-v0.8/manifest.json) và
[validation](../../data/development/table-v0.8/validation.json). Raw PDF/lớp
chữ/run/ảnh vẫn tải riêng; chưa upload artifact mới lên Drive hoặc push thay
đổi v0.8 trong mốc này.

## Kiểm tra và giới hạn

443 kiểm thử phần mềm đạt, Ruff và frontend build đạt. Test mới kiểm tiêu đề
ngày lặp, cột năm có/không đơn vị, năm trong thân bài/footer/ngày phê duyệt,
scope/allowlist trước đọc PDF, replay sai năm và thay policy bị chặn. Hai cảnh
báo TestClient/AnyIO và hai cảnh báo bundler lucide vẫn như mốc trước.

Header bị chia quá xa, dạng ngày ngoài quy tắc hoặc bảng không có lớp chữ vẫn
có thể bị loại dù chứa thông tin đúng. Policy bảo thủ không chứng minh không
bỏ sót. Kiểm năm của trang không thay thế kiểm năm của từng ô, đơn vị, phạm
vi, ý nghĩa chỉ tiêu hoặc thời điểm công bố. Chưa có nhãn người dùng,
semantic accuracy, cohort PiT strict, backtest hoặc Full PiT-HAF mới.

Bước tiếp theo là xử lý nguồn cần OCR với locator kiểm chứng được và xây bộ
nhãn độc lập, đồng thời giải quyết tài liệu vượt ngân sách mà không chọn lại
theo kết quả thuận lợi.
