# 31 — Đọc riêng tiêu đề và liên kết nhãn nhiều dòng

Ngày 02/11/2026. Bổ sung profile OCR chữ rời và policy liên kết theo vị
trí, cho phép chọn tường minh một lượt OCR tiêu đề trên cùng trang.
Không thay mặc định hoặc các artifact v0.1/v0.2 đã lưu; chưa tạo facts.

## Vì sao tách phần chữ và số

Thử `pdf_ocr_sparse_v0.3` trên hai trang MWG 93/94, sau khi xem ảnh đầy
đủ các trang 90–94. Giữ model/runtime/dpi/ngân sách như vùng v0.2, chỉ
đổi PSM 6 thành 11. Theo [tài liệu Tesseract](https://github.com/tesseract-ocr/tesseract/blob/main/doc/tesseract.1.asc),
PSM 11 tìm các cụm chữ rời và không bảo đảm thứ tự đọc. Lượt mới đọc được
tiêu đề, kỳ tài chính và nhiều nhãn ở trang 93, nhưng vẫn không nhận đủ
hàng “Chỉ tiêu/Năm nay/Năm trước”.

Trên trang 94 cùng vùng/dpi, PSM 11 làm một số chuỗi số bị tách/nhận sai.
Đối chiếu 24 chuỗi do trợ lý chép ở mốc trước: PSM 6 cũ khớp nguyên chuỗi
24/24, PSM 11 khớp 13/24; nếu chỉ bỏ khoảng trắng là 24/24 và 16/24.
Không dùng bản chép này làm đầu vào hoặc bảng tra của linker. Đây là
chẩn đoán phát triển cùng nguồn, chưa là gold độc lập hoặc accuracy.

Vì vậy bổ sung hai lượt PSM 6 chỉ đọc dải tiêu đề. Cả hai nhận được sáu
từ “CHỈ TIÊU Năm nay Năm trước”, có hộp từ. Giữ cả các lượt sparse ít
phù hợp cho số; không chọn hoặc sửa từng chuỗi theo đáp án. Trên trang
94, người dùng có thể giữ phần số PSM 6 đã lưu và chọn riêng nguồn chữ
tiêu đề thay cho việc OCR lại toàn bộ bảng.

## Nguồn và ngân sách

PDF version `d4886fc5337ce1d593ed8a3a09f4ae0c73a228d70bad66854dbbeca816d78acf`,
content SHA-256 `e98227cb400d043c1a0e95eaa2706b397fb61001c342713e27b49ad04c17fca7`.

| Lượt | Trang | Profile | Vùng toàn trang chuẩn hóa | Từ / điểm dưới 80 |
|---|---:|---|---|---:|
| `20261102T100603Z-536212bf` | 93 | sparse v0.3 | .07,.11,.86,.88 | 150 / 9 |
| `20261102T100612Z-960dcd83` | 94 | sparse v0.3 | .15,.12,.85,.84 | 181 / 39 |
| `20261102T101117Z-565444da` | 93 | region v0.2 | .15,.244,.85,.289 | 6 / 0 |
| `20261102T101123Z-fc4bf688` | 94 | region v0.2 | .15,.147,.85,.19 | 6 / 0 |

Hai study ghi trước trang/vùng/profile, không retry. Dải tiêu đề được
chọn sau khi thấy hạn chế của lượt sparse, không gọi đây là cấu hình
đăng ký trước cho test giữ kín. Bốn run mới và năm native replay (gồm
một control PSM 6 cũ) dùng tổng chín lượt OCR, không LLM. Năm replay
đều đạt đối chiếu. 70 hash bảo vệ trước các lượt sparse không đổi.

## Policy `ocr_cell_links_v0.2`

Nhóm dòng theo hộp từ, không dùng thứ tự block/line do sparse OCR xuất
ra. Dựa trên cột số lặp lại như v0.1; không sửa hoặc ghép mảnh số. Nhãn
được lấy trong dải giữa các hàng số lân cận, tối đa ba dòng gần và thẳng
hàng; dòng nối cần có dấu hiệu tiếp tục. Tiêu đề/nhóm chữ hoa, dòng kết
thúc dấu hai chấm hoặc nhiều nhãn không phân định được bị bỏ qua/để
trống. Mỗi phần nhãn giữ hộp từng từ và cần người đối chiếu. Quy tắc
hình học có thể bỏ nhãn đúng hoặc nối nhầm, không là kiểm chứng ý nghĩa.

Nhận dòng ghi đầy đủ “cho năm tài chính kết thúc ngày … tháng … năm …”
ở phía trên bảng, kiểm ngày hợp lệ và tính duy nhất. `statement_period`
là bằng chứng kỳ tài chính trên trang, tách khỏi cột kỳ. Không tự lấy
năm từ metadata, footer hoặc suy năm trước bằng cách trừ một. Tất cả
`resolved_year` giữ null; các cột tương đối cũng giữ `observed_year` null.

Chặn thêm nhầm lẫn do bỏ dấu: chữ “ĐỘNG” trong “hoạt động” không được
coi là đơn vị “đồng”. Dấu gốc được giữ nguyên, cụm không phải tiền được
ghi chẩn đoán; không sửa policy v0.1 hoặc các snapshot trước.

Nguồn tiêu đề là lựa chọn riêng, không tự tìm/lấy từ trang trước. Cần:

- Cùng version/hash PDF, cùng trang thành công và cùng ảnh PNG toàn trang,
  dpi, rotation, kích thước. Nguồn khác trang/PDF/ảnh bị chặn.
- Vùng tường minh cao tối đa 10% trang, nằm trên mọi hàng số và phủ đủ
  các cột. Không cho lượt bổ sung ghi đè vùng giá trị.
- Chỉ thay các từ có tâm nằm trong dải đã chọn, giữ chẩn đoán từ bị thay.
  Số ở thân bảng giữ nguyên. Mỗi trường có `word_refs` gồm run OCR gốc và
  ID từ; cả hai seal được pin và kiểm lại khi mở/replay.

## Kết quả liên kết phát triển

| Thân bảng + nguồn tiêu đề, policy | Ô | Có nhãn | Có cột kỳ | Có đơn vị | Có scope | Có kỳ tài chính | Ô có nhãn nhiều dòng |
|---|---:|---:|---:|---:|---:|---:|---:|
| Trang 93 sparse, spatial, không bổ sung | 19 | 13 | 0 | 19 | 19 | 19 | 7 |
| Trang 93 sparse + tiêu đề riêng, spatial | 19 | 13 | 19 | 19 | 19 | 19 | 7 |
| Trang 94 PSM 6, policy v0.1 cũ | 24 | 24 | 0 | 24 | 0 | 0 | 0 |
| Trang 94 PSM 6, spatial, không bổ sung | 24 | 18 | 0 | 24 | 0 | 0 | 4 |
| Trang 94 PSM 6 + tiêu đề riêng, spatial | 24 | 18 | 24 | 24 | 0 | 0 | 4 |
| Trang 94 sparse + tiêu đề riêng, spatial | 13 | 10 | 13 | 13 | 0 | 0 | 8 |

Đây là số trường được nối, không phải số trường đúng. Policy spatial
để trống thêm một số nhãn vì không phân định được dòng; không gọi việc
giảm điểm thấp hoặc tăng số nhãn ghép là tăng accuracy. 19 ô trang 93
chưa bao phủ đủ bảng: còn chuỗi bị tách và nhãn mất/nhận sai. Trang 94
không có scope/kỳ tài chính tường minh nên giữ thiếu, không truyền từ
trang 93. Chưa có người xác nhận các giá trị, đơn vị, nhãn hoặc năm.

Sáu snapshot mới và bốn snapshot v0.1 cũ tái tính đạt đối chiếu, không
gọi OCR/LLM trong bước linking. 75 hash trước validation này giữ nguyên
(gồm cả các run mới vừa tạo). Chưa ghi review DB thật hoặc thêm cohort
PiT strict. Không đưa các ô vào context trả lời hay backtest.

Raw study: `outputs/ocr-spatial-development/20261102T102708Z-bf83edf9/`;
sparse/header studies và numeric audit được pin trong
[manifest](../../data/development/ocr-links-v0.2/manifest.json).
Xem [data card](../../data/development/ocr-links-v0.2/DATA_CARD.md) và
[validation](../../data/development/ocr-links-v0.2/validation.json).

## Dùng thử

Mở OCR thân bảng đã lưu, chọn **Theo vị trí và nhãn xuống dòng · v0.2**
trong **Ô số OCR và thông tin đi kèm**. Ở **Lượt OCR bổ sung tiêu đề trên
cùng trang**, chọn lượt vùng hẹp tương ứng rồi bấm liên kết. Mỗi trường
tiêu đề ghi rõ chữ đến từ lượt bổ sung; bấm trường để tô từng từ trên
ảnh nguồn. Có thể chọn policy v0.1 để đối chiếu kết quả cũ.

```powershell
.\run.ps1 ocr-cell-links --ocr-run 20261102T100603Z-536212bf --policy ocr_cell_links_v0.2 --header-run 20261102T101117Z-565444da
.\run.ps1 ocr-cell-links --ocr-run 20261030T015504Z-6d5f47c2 --policy ocr_cell_links_v0.2 --header-run 20261102T101123Z-fc4bf688
.\run.ps1 ocr-cell-links --replay outputs/ocr-cell-links/20261102T102717Z-f2d5a41f
```

API GET cell-links nhận `policy_id` và `header_run_id` tùy chọn; replay
dùng đúng policy/header đã lưu, không nhận override. 574 test toàn bộ,
Ruff, Prettier và frontend build đạt. Test mới kiểm ghép cùng nguồn,
chặn khác trang/ảnh/dpi, vùng ghi đè số, provenance bị sửa rồi reseal,
nhãn xuống dòng/mơ hồ, kỳ tài chính/ngày sai và đơn vị bị nhầm khi bỏ dấu.
Giữ nguyên hai cảnh báo test phụ thuộc và hai cảnh báo bundler lucide.

Bước tiếp theo là quy trình xác nhận dữ liệu với provenance, kiểm nhãn
và liên kết ngữ cảnh nhiều trang có điều kiện; thu bằng chứng ngày công
bố và nhãn độc lập cho cohort. Chưa push/upload các artifact mới.
