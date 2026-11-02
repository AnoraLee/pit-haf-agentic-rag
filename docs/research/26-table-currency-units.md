# 26 — Gắn đơn vị tiền tệ với cột năm

Ngày: 29/10/2026. Profile thử nghiệm `table_cells_v0.9`, parser
`pdf_word_cells_v0.9`. Mặc định frontend/API vẫn v0.6; lựa chọn lớp chữ
ban đầu vẫn v0.7 và gọi model vẫn tắt. Không sửa cấu hình hay kết quả
v0.4–v0.8 và document-scope-v0.1.

## Lỗi và quy tắc bổ sung

Bảng FPT đã được chọn đúng kỳ ở v0.8 nhưng chưa tạo ô vì đơn vị là `VND`
nằm dưới từng năm; parser v0.5 chỉ nhận các cụm có hệ số như triệu VND,
tỷ đồng. Từ khóa VND trong thân văn bản không đủ để gắn đơn vị cho bảng.

[pdf_tables_v09.py](../../src/pit_haf/data/pdf_tables_v09.py) bổ sung hai
dạng locator: token tiền tệ căn với từng cột năm trong cửa sổ header hẹp,
hoặc dòng khai báo rõ `Đơn vị: VND/VNĐ/đồng` gần header. Với dạng theo cột,
mọi cột phải có đúng một token phù hợp. Token lệch cột, thiếu, lặp, trộn
tiền tệ không hỗ trợ hoặc mâu thuẫn với hệ số sẽ chặn gắn đơn vị. Không
lấy token từ bảng bên cạnh hoặc câu kể để bù phần còn thiếu.

Locator giữ word ID, bounding box và chuỗi nguồn; mỗi cột năm có vị trí
đơn vị riêng. Đơn vị trần chuẩn hóa nhãn thành VND, giữ nguyên chuỗi số,
dấu âm và dấu phân cách của ô. Không suy triệu/tỷ từ độ lớn hoặc chuyển
đổi số. Các cụm đơn vị có hệ số giữ cách xử lý trước; vị trí/phạm vi và
ngữ nghĩa vẫn cần người đọc đối chiếu.

Quy tắc pin ở [table_units_v0_9.json](../../configs/table_units_v0_9.json).
Run lưu hash policy; replay đọc lại raw PDF và kiểm đúng policy/locator.
Layout v0.5 có điểm mở rộng resolver nhưng nhánh mặc định và cấu trúc
artifact cũ giữ nguyên, được kiểm lại bằng replay.

V0.9 dùng cùng truy xuất chữ, page gate v0.8, context policy v0.6, scope
doanh nghiệp/kỳ/allowlist và các giới hạn trước: 400 trang đọc lại, tối đa
3 trang bảng, 18 ô/9.000 ký tự, một generation nếu bật, không retry. Đây
là thay đổi parser theo phiên bản, không phải mở rộng ngân sách model.

## Study phát triển

Study `20261029T152456Z-e0c716d3` khai báo trước tám hành động: hai version
FPT đã dùng ở study chọn tài liệu, rồi HPG, VCB, ACB, BID, MWG và VNM với
phạm vi cũ. Cùng câu hỏi lợi nhuận 2024; không gọi model, không retry hoặc
đổi cấu hình sau khi thấy kết quả. Lựa chọn do trợ lý thực hiện, chưa là
test giữ kín hoặc nhãn độc lập.

| Mã / bản | Context trước | Context v0.9 | Run mới |
|---|---:|---:|---|
| FPT English | 0 | 0 | `20261029T152632Z-dad65562` |
| FPT Vietnamese | 0 | 4 | `20261029T152809Z-d6a89a33` |
| HPG | 7 | 7 | `20261029T152926Z-13228ced` |
| VCB | 5 | 5 | `20261029T153020Z-10f69baa` |
| ACB | 2 | 2 | `20261029T153132Z-c1fbb3df` |
| BID | 4 | 4 | `20261029T153243Z-943d6c42` |
| MWG | 0 | 0 | `20261029T153301Z-2f36e523` |
| VNM | 4 | 4 | `20261029T153338Z-8f78b9cd` |

Hai baseline FPT là lượt đọc riêng version của study chọn tài liệu; các
mã khác đối chiếu v0.8 với toàn bộ scope cũ. Sáu mã khác giữ cùng tập
nhãn, chuỗi số, năm, đơn vị, phạm vi và cờ review trong context, sau khi
bỏ thứ tự và ID thay theo phiên bản parser. Điều này chưa là xác nhận
đúng ngữ nghĩa của các trường đó.

FPT tiếng Việt có 36 ô được parser trích xuất ở trang PDF 151, trong đó
4 ô năm 2024 qua lọc chỉ tiêu để vào context, so với 0 ở v0.8. Các nhóm
nhãn gồm lợi nhuận hoạt động, gộp, khác và kế toán trước thuế. Mỗi ô giữ
locator VND dưới cột năm tương ứng. Trang 50 vẫn bị chặn; không mượn đơn
vị từ một bảng khác trên cùng trang. Bản tiếng Anh vẫn không có trang
được chọn bởi bộ truy xuất hiện tại.

Đây là ứng viên chưa duyệt, không phải bốn câu trả lời đúng hoặc facts
được xác nhận. Bốn ô này chưa có chỉ tiêu lợi nhuận sau thuế; parser đơn
vị không giải quyết lỗi truy xuất, chọn
trang, nhãn viết tắt hoặc phạm vi còn thiếu. Các kết quả gốc 24 case và
source audit không được thay bằng các ô mới.

Tám run mới replay đạt; 44 run cũ cũng replay đạt sau khi tách resolver,
tổng 52 lượt. Gồm cả từ chối/lượt lỗi trước generation cũ, không phải
52 câu trả lời thành công. Hash case pack, batch, source audit, 44 seal
cũ và metadata các mốc trước không đổi; cấu hình trước/sau study khớp.

## Sử dụng

Trong [Phân tích tài liệu](http://localhost:8501/#analysis), bật đọc lại
lớp chữ và chọn **Kiểm tra cột năm và đơn vị · v0.9**. Với FPT, xem tài
liệu phù hợp và chọn riêng bản tiếng Việt để nằm trong giới hạn trang.
Mở lượt đã lưu `20261029T152809Z-d6a89a33`, chọn **Đơn vị** để xem vùng
VND dưới cột năm trên PDF; không cần chạy lại hoặc gọi model.

```powershell
.\run.ps1 table-evidence --ticker FPT --query "lợi nhuận năm 2024" --profile table_cells_v0.9 --list-documents
.\run.ps1 table-evidence --ticker FPT --query "lợi nhuận năm 2024" --profile table_cells_v0.9 --document-version e8509e72eea789549b90734a1bdf3f025967838c9ecdfe2c6faa82259dde6ab2
.\run.ps1 table-evidence --replay outputs/table-evidence/20261029T152809Z-d6a89a33
```

API nhận `profile_id=table_cells_v0.9`; `document_version_id` tiếp tục
giới hạn bên trong scope và gateway, không thay thế điều kiện thời gian.

Metadata nhỏ ở [data card](../../data/development/table-v0.9/DATA_CARD.md),
[manifest](../../data/development/table-v0.9/manifest.json) và
[validation](../../data/development/table-v0.9/validation.json). Raw PDF,
run, lớp chữ và ảnh ở outputs/cache ngoài Git.

## Kiểm tra và phần còn lại

474 kiểm thử phần mềm đạt; Ruff, định dạng frontend và build đạt. Test
đơn vị kiểm VND/VNĐ/đồng theo cột và dòng khai báo, thiếu/lệch/lặp cột,
trộn VND/USD, mâu thuẫn hệ số, văn bản ngoài header, bảng cạnh nhau, raw
replay phát hiện locator giả và thay policy bị chặn. Không gọi đây là
độ chính xác ngữ nghĩa. Vẫn còn hai cảnh báo TestClient/AnyIO và hai cảnh
báo lucide bundler như trước.

MWG cần OCR; cần xây cohort có nguồn thời gian và nhãn độc lập trước
thực nghiệm cuối. Tổng thể dự án và thứ tự tiếp theo ở
[tiến độ 29/10](27-progress-20261029.md). Chưa push hoặc upload artifact
mới lên Drive trong mốc này.
