# 38 — Sổ cổ tức, cổ phiếu thưởng và bất đồng nguồn

Ngày 06/11/2026. Protocol `corporate_action_development_v0.1` bổ sung
thành phần kế toán quyền nhận tiền/cổ phiếu, kèm đối soát ba sự kiện
nguồn. Đây là bước phát triển trước khi tích hợp corporate actions
vào động cơ thực thi; chưa có backtest giá thật hoặc kết quả dự báo.

## Thành phần kế toán đã có

`CorporateLedger` nhận instruction giả lập và số cổ phiếu đủ điều
kiện do bên gọi khai báo. Nó ghi nhận tiền phải thu ròng, cổ phiếu
chờ khả dụng, phần lẻ bị hủy và receipt khi đến giờ. Không tự suy
ngày không hưởng quyền, số lượng được hưởng hoặc giờ ghi có từ
ngày đăng ký cuối cùng. Bộ sự kiện thật chưa được chuyển thành
instruction kế toán để tính danh mục.

- Tiền gross = số cổ phiếu khai báo × tiền/cổ phiếu. Thuế là tham
  số giả lập `cash_tax_bps`; ledger giữ gross, thuế và net riêng.
  Không coi mức thuế demo/test là chính sách thuế thị trường.
- Cổ phiếu mới = floor(số cổ phiếu của **toàn chủ sở hữu** × new/old).
  Giữ phần dư bằng tử/mẫu số nguyên; không làm tròn từng lot riêng
  hoặc tự đổi phần lẻ thành tiền. Chỉ hỗ trợ chính sách hủy phần lẻ.
- `available_at <= now` giải phóng đúng ranh giới, phân biệt một
  microsecond trước đó; receipt giữ giờ đến hạn và giờ quan sát.
  Cấm thời gian đi ngược và nhận cùng event ID lần thứ hai.
- Tiền/cổ phiếu chưa về vẫn có giá trị quyền phải thu. Receipt chỉ
  bàn giao cho bên gọi; module chưa tự sửa vị thế, tiền và lệnh
  trong `backtest-timed`. Chưa có FIFO/điều kiện hưởng quyền thật
  hoặc bút toán tách cổ phiếu/rights issue/cash in lieu.
- Chỉ nhận `synthetic_unadjusted_marks`. Chặn khai báo basis unknown
  hoặc đã điều chỉnh, nhằm ngăn nối feed không rõ semantics. Không
  tự điều chỉnh giá hoặc cộng thêm cổ tức vào chuỗi total-return.

Ca kiểm tra bằng phép tính tay: nắm 20 cổ phiếu giá 116, nhận 1 đơn
vị tiền/cổ phiếu và 3 cổ phiếu mới cho mỗi 20 cổ phiếu. Với giá sau
quyền 100, giá trị là 20×100 + 3×100 + 20 = 2.320, bằng trước quyền.
Đây là giá/đơn vị tiền tự tạo, không là giá FPT hoặc lợi suất chiến lược.

| Checkpoint giả lập | Tiền cổ tức dùng được | Cổ phiếu dùng được | Quyền chưa về |
|---|---:|---:|---|
| 03/01, sau ghi nhận | 0 | 20 | 20 tiền + 3 cổ phiếu |
| 05/01, 09h | 0 | 20 | 20 tiền + 3 cổ phiếu |
| 05/01, sau 13h | 20 | 20 | 3 cổ phiếu |
| 08/01, 09h | 20 | 23 | Không còn |

Mọi checkpoint đều có tổng giá trị 2.320. Đây kiểm tra bảo toàn kế
toán; không gán đơn vị VND, không phát sinh lệnh hoặc chứng minh khả
năng khớp lệnh thật. Tính bằng Decimal context 50 chữ số; chưa áp
rounding tiền/phí theo quy tắc môi giới.

## Sự kiện nguồn và điều kiện còn thiếu

Đã tải sáu thông báo VSD/VSDC bằng HTTPS có kiểm chứng chỉ, tái sử
dụng downloader giới hạn của mốc 37. Mỗi nguồn có raw/hash và metadata;
không cookie/đăng nhập, retry tự động, import Vnstock hoặc API key.
Config gắn 20 locator token với hash body; tách tỷ lệ old:new khỏi
phần trăm mệnh giá, tách ngày chốt quyền khỏi ngày trả tiền/giao dịch.
Locator kiểm sự khớp byte/vị trí/giá trị, chưa thay xác nhận ngữ nghĩa
độc lập. Curation và kiểm ảnh do trợ lý thực hiện, không là nhãn người dùng.

| Sự kiện chọn để đối soát | Ngày record trong thông báo | Tiền trong thông báo này | Tỷ lệ cổ phiếu old:new | Ngày cổ phiếu mới giao dịch |
|---|---|---|---|---|
| FPT 2024 | 13/06/2024 | 1.000 đồng/cổ phiếu, lịch trả 20/06/2024 | 20:3 | 01/08/2024 |
| HPG 2024 | 24/05/2024, có bất đồng nguồn | Không nêu trong thông báo quyền cổ phiếu | 10:1 | 28/06/2024 |
| VCB 2023 | 26/07/2023 | Không nêu trong thông báo quyền cổ phiếu | 1.000:181 | 15/09/2023 |

Nguồn: [quyền FPT](https://vsdc.vn/vi/ad/171655),
[giao dịch FPT](https://vsdc.vn/vi/ad/173404),
[quyền HPG](https://vsdc.vn/vi/ad/170903),
[giao dịch HPG](https://vsdc.vn/vi/ad/172369),
[quyền VCB](https://vsdc.vn/vi/ad/159971),
[giao dịch VCB](https://vsdc.vn/vi/ad/161434).
Số 0 cho cash trong config HPG/VCB mang basis
`not_reported_in_selected_notice`; không kết luận không có cổ tức tiền
trong toàn giai đoạn hoặc năm. Đây là các ví dụ chọn trước để phát
triển sau khi đọc nguồn, không phải lịch sử sự kiện đầy đủ 2021–2024.

Snapshot KBS có các ngày record/giao dịch nói trên, nhưng cả ba mã
vẫn có `adjustment_status=unknown`. Điều đó không chứng minh giá
chưa điều chỉnh, đã điều chỉnh đúng hoặc có factor theo cutoff. Mọi
event giữ `ex_date`, giờ tài sản khả dụng và số lượng được hưởng là
null; không lấy ngày record làm ex-date hoặc áp bonus ngay ngày đó.

HPG có điểm chưa thống nhất: hai thông báo VSDC ghi 24/05/2024,
trong khi mục 28 của BCTC hợp nhất 2024 ghi chốt danh sách ngày
03/06/2024. Đã đọc ảnh trang PDF 57 (trang in 56) từ blob có SHA-256
`304a93a65e1587f625e0045d6ec9bcfba6647d19df4034cfd8fc1ec7b62eeb64`.
Đây là PDF đã có trong corpus, không tải lại hoặc sửa blob.
[BCTC của doanh nghiệp](https://file.hoaphat.com.vn/hoaphat-com-vn/2025/03/bao-cao-tai-chinh-hop-nhat-nam-2024-da-kiem-toan-1.pdf).

Book giữ ngày quan sát trong thông báo, lưu ngày khác/PDF/hash/page
trong `disagreements`, báo `unresolved_disagreement` và thêm lý do
chặn. Không chọn ngày mới hơn làm chuẩn hoặc tuyên bố nguồn nào sai.
Replay kiểm cả blob PDF và số trang; hash/page chỉ bảo đảm đúng file,
không tự đọc/xác nhận câu trên ảnh. Cần thêm thông báo gốc/sửa đổi
hoặc xác nhận độc lập để giải quyết trước khi tạo entitlement thật.

## Bổ sung nguồn HOSE có phạm vi hẹp

Đã lấy được bản PDF thông báo 803/TB-SGDHCM ngày 19/04/2024 qua
[liên kết PHS](https://www.phs.vn/tin-tuc/hose-cap-nhat-lich-nghi-giao-dich-nam-2024/6167965)
tới [bản mirror](https://static2.vietstock.vn/vietstock/2024/4/19/20240419_19042024___cap_nhat_lich_nghi_giao_dich_2024_.pdf).
Đọc ảnh trang 1 xác nhận nghỉ 29/4–1/5 và không giao dịch ngày làm
bù 4/5. Bốn ngày này khớp trạng thái đóng trong lịch ứng viên mốc 37.
Lớp chữ trích số thông báo thành 905, trong khi ảnh ghi 803; giữ raw,
ghi riêng quan sát trực quan, không sửa text nguồn hoặc coi text là gold.
Đây là tài liệu do HOSE phát hành được lấy từ mirror; chưa xác thực
chữ ký, chưa đủ để chứng nhận toàn bộ lịch HOSE/phiên bất thường.

## Chạy, lưu trữ và kiểm chứng

```powershell
.\run.ps1 corporate-actions --demo
.\run.ps1 corporate-actions --audit --sources-run 20261106T065017Z-5e9486ce --market-run 20261102T145138Z-21243d88
.\run.ps1 corporate-actions --replay outputs/corporate-actions/20261106T071034Z-aa43ce9a
.\run.ps1 corporate-actions --replay outputs/corporate-actions/20261106T071036Z-b53cb8b3
```

Demo hoàn toàn offline, không cần corpus/Ollama. Audit cần archive sáu
nguồn, snapshot KBS và blob PDF HPG đã ghim. Có thể dùng `--book` khi
build audit mới, replay không nhận override. JSON/CSV có hash, snapshot
code, input nguyên bytes và dependency seal. CSV events/receipts/
checkpoints vẫn có header khi không có dữ liệu ở mode tương ứng.
Code snapshot không tự thực thi; replay tái tính bằng code hiện tại.
Code/config/metadata nhỏ trong Git, raw/PDF/CSV/run ở local ngoài Git.

Study: `outputs/corporate-development/20261106T071032Z-1ec973eb/`.
Hai run audit/demo đều replay khớp. 54 test mới kiểm tính tay, thuế
giả lập/phần lẻ, từng thời điểm khả dụng, duplicate/backward time,
Decimal, basis, source token/identity, xung đột PDF, dependency,
tamper/reseal và CLI. Nhóm liên quan 133 test đạt; 127 hash bảo vệ
giữ nguyên, không tạo review DB thật, gọi LLM hoặc tải thêm giá.
Toàn repository có 855 test và Ruff đạt, còn hai cảnh báo phụ thuộc
cũ. Frontend không đổi nên không chạy lại build/QA giao diện.
Xem [data card](../../data/development/corporate-actions-v0.1/DATA_CARD.md)
và [validation](../../data/development/corporate-actions-v0.1/validation.json).

Tiếp theo: xác lập ex-date/phiên bản sự kiện, giải quyết bất đồng HPG,
mở rộng lịch sử corporate actions/factor theo thời gian và tích hợp
entitlement ledger vào một protocol thực thi mới có kiểm chứng. Không
nâng snapshot hiện tại thành dữ liệu thực thi hoặc cohort PiT strict.
