# 30 — Liên kết ô OCR với ngữ cảnh để đối chiếu

Ngày 02/11/2026. Mốc này đưa chữ/số OCR đã lưu thành các ô ứng viên có
vị trí nguồn riêng cho chỉ tiêu, giá trị, cột năm, đơn vị và phạm vi.
Các ô vẫn chưa được xác nhận, chưa đưa vào context trả lời hoặc backtest.

## Luồng và quy tắc

API đọc lại OCR qua kiểm tra seal, TSV, registry, temporal gate và ảnh
render từ raw PDF trước khi liên kết. Không gọi OCR hoặc LLM, không sửa
corpus hoặc các lượt OCR cũ. Mặc định đọc bảng v0.6 vẫn giữ nguyên.

Policy `ocr_cell_links_v0.1` là thử nghiệm chưa khóa. Nhóm cột theo cạnh
phải của số lặp lại trên ít nhất ba dòng OCR khác nhau, cần 2–8 cột.
Dùng chữ trên cùng dòng đọc OCR ở bên trái vùng số làm nhãn ứng viên;
không tự nối nhãn xuống dòng. ID ứng viên gắn version/hash PDF, trang,
policy và các trường nguồn. Mỗi trường giữ chuỗi nguyên dạng, ID từng
từ, từng hộp pixel toàn trang và điểm nhận dạng thấp nhất.

Không ghép lại chuỗi số bị tách. Một cột có nhiều token trong cùng dòng
hoặc nhiều giá trị cùng căn cột được ghi chẩn đoán, không chọn một mảnh
nhỏ làm toàn bộ giá trị. Giữ dấu ngoặc/dấu phân cách; dấu gạch không đổi
thành 0. Tối đa 120 ô; vượt ngân sách trả chẩn đoán và không trả bảng
cắt bớt mà không báo.

Hàng tiêu đề kỳ phải có tiền tố nhãn bảng như “Chỉ tiêu”, đủ một kỳ cho
mỗi cột và không mơ hồ. Năm đứng lẻ hoặc hàng điều hướng không được dùng
làm kỳ. Có thể lưu năm tuyệt đối quan sát được hoặc chữ “Năm nay/Năm
trước”, nhưng không suy năm từ metadata tên/kỳ tài liệu. `resolved_year`
vẫn null vì đây là OCR chưa duyệt. Nhiều hàng tiêu đề đủ điều kiện cũng
được coi là mơ hồ trong phiên bản này.

Đơn vị tiền và phạm vi chỉ nhận từ cụm OCR tường minh gần phía trên vùng
số, có locator. Cụm “triệu đồng” ưu tiên hơn token “đồng” nằm trong nó.
Thiếu hoặc nhiều cụm thì để null; không lấy phạm vi từ ticker/metadata.
Đây là quan sát chữ OCR, chưa xác nhận đơn vị thật hoặc quy đổi số.

Tất cả ô có trạng thái cần duyệt, ghi rõ nhãn có thể thiếu/nghĩa chưa
kiểm tra; điểm thấp chỉ thêm cờ, không tự sửa. Không có nút hoặc đường
API biến những ô này thành facts được duyệt trong mốc này.

## Lỗi phát hiện trong quá trình phát triển

Bản đầu của phép liên kết đã lấy năm 2025 trên thanh điều hướng trang
MWG làm năm cột X1 của bản OCR toàn trang. Đã siết hàng tiêu đề đủ cột
và tiền tố bảng; năm này hiện chỉ xuất hiện trong chẩn đoán ứng viên bị
loại, không gán vào ô. Test hồi quy kiểm năm đứng lẻ, hàng điều hướng,
năm trùng và hai hàng kỳ mơ hồ.

Cũng phát hiện một mảnh số hợp lệ ở cuối chuỗi OCR lỗi có thể được chọn
thành toàn bộ giá trị. Đã thêm kiểm các token cùng cột/dòng, giữ lỗi và
bỏ liên kết mơ hồ. Những sửa đổi này dựa trên quan sát phát triển, không
phải tối ưu trên mẫu test giữ kín hoặc bằng chứng về accuracy.

## Kết quả trên các lượt đã có

Sau khi phát triển và xem thử nguồn, lưu cấu hình/mã nguồn cùng danh sách
bốn lượt OCR trước khi chạy bản validation lưu riêng. Không dùng bản
chép 24 ô ở mốc trước làm đầu vào hoặc bảng tra trong thuật toán.

| Nguồn OCR, trang 94 | Ô ứng viên | Có nhãn OCR | Có đơn vị OCR | Có cột kỳ đủ điều kiện | Có phạm vi | Ô có trường điểm thấp |
|---|---:|---:|---:|---:|---:|---:|
| v0.1 toàn trang | 14 | 14 | 14 | 0 | 0 | 11 |
| v0.2 toàn trang | 24 | 24 | 24 | 0 | 0 | 10 |
| v0.2 vùng bảng | 24 | 24 | 24 | 0 | 0 | 13 |

Nhãn được nối không đồng nghĩa đúng hoặc đầy đủ. Có nhãn OCR nhận sai
thành các chữ vô nghĩa; nhãn xuống dòng có thể mất phần đầu/cuối. Các ô
đó vẫn hiển thị chữ gốc và cờ cần đối chiếu. Cả hai lượt mới quan sát
được “VND”, nhưng vẫn thiếu kỳ/phạm vi; không có facts đủ điều kiện.

Run v0.1 lỗi tích hợp cũ giữ cả bốn trang lỗi, mỗi trang không có ô.
Ba trang 2, 3, 48 của run v0.1 thành công không đủ cột cho policy nên
trả 0 ô với chẩn đoán, không tự chuyển trang. Bản v0.1 trang 94 còn bốn
cột/dòng bị loại vì nhiều token; số 14 ô không phải metric khớp chuỗi
14/24 ở mốc trước, dù trùng giá trị đếm.

Bốn snapshot liên kết tái tính đạt đối chiếu, gồm cả bản ghi các trang
lỗi. Đây là replay từ artifact OCR đã lưu với kiểm ảnh PDF; không chạy
lại engine OCR. Không có lượt OCR, LLM hay review người dùng mới. 65
hash bảo vệ gồm 52 run bảng, bốn run OCR và case/batch/source audit,
metadata, numeric audit cũ giữ nguyên. Review DB thật chưa được tạo.

Study local: `outputs/ocr-link-development/20261102T093935Z-efea4dc8/`.
Raw snapshot ở `outputs/ocr-cell-links/`, ngoài Git. Metadata nhỏ ở
[data card](../../data/development/ocr-links-v0.1/DATA_CARD.md),
[manifest](../../data/development/ocr-links-v0.1/manifest.json),
[validation](../../data/development/ocr-links-v0.1/validation.json).

## Giao diện và tái lập

Trong **Phân tích tài liệu**, chọn PDF rồi mở một lượt OCR đã lưu. Bên
trong **Ô số OCR và thông tin đi kèm**, bấm **Liên kết ô số từ OCR đã
lưu**. Chọn ô và bấm từng trường để xem đúng từng hộp từ trên ảnh toàn
trang. Cột X1/X2 chỉ biểu thị thứ tự từ trái sang phải, không thay năm.
Trường thiếu ghi “Chưa đủ bằng chứng”; không tự suy số/năm.

```powershell
.\run.ps1 ocr-cell-links --ocr-run 20261030T015504Z-6d5f47c2
.\run.ps1 ocr-cell-links --replay outputs/ocr-cell-links/20261102T093944Z-6e037216
```

API GET `/api/research/ocr-previews/{run_id}/cell-links` trả bản xem sau
kiểm nguồn; GET không lưu snapshot. CLI tạo thư mục mới chứa links,
policy, implementation và seal; replay kiểm hash rồi tái tính các trường
để chặn cả sửa kết quả rồi reseal. Cần raw PDF/registry/OCR tương ứng để
chạy lại; metadata Git không thay các artifact đó.

553 test toàn bộ, Ruff, Prettier và build frontend đạt. Test mới kiểm
cột riêng, năm tương đối không suy metadata, đơn vị chồng cụm/mâu thuẫn,
scope thiếu, nhãn sai/thiếu/xuống dòng, số tách/ngoặc/gạch, budget, nguồn
identity, API không gọi OCR, replay và artifact bị sửa. UI đã kiểm chọn
ô âm, tô năm hộp từ nhãn, tô nguồn VND và cảnh báo nhãn điểm thấp. Hai
cảnh báo phụ thuộc test và hai cảnh báo bundler lucide vẫn như trước.

## Phần tiếp theo

Cần nhận diện lại tiêu đề/nhãn xuống dòng, liên kết năm với bằng chứng
đúng vị trí (kể cả trường hợp sang trang), kiểm scope và đưa kết quả vào
quy trình duyệt có provenance. Đồng thời bổ sung cohort có bằng chứng
ngày công bố và nhãn độc lập. Chưa có semantic accuracy, cohort PiT
strict, kết quả backtest hoặc Full PiT-HAF từ mốc này. Chưa push GitHub.
