# 37 — Lịch thanh toán có phiên bản và đối soát ngày giá

Ngày 03/11/2026. Protocol `settlement_calendar_audit_v0.1` tạo lịch
**ứng viên** cho ngày thanh toán cổ phiếu từ thông báo VSD/VSDC, có
lưu bản gốc và sửa đổi. Đối soát với snapshot KBS đã ghim, không tải
thêm giá hoặc chuyển dữ liệu vào động cơ thực thi.

## Nguồn và sửa đổi

Đã lưu chín thông báo công khai qua HTTPS bằng .NET HttpClient trên
Windows, giữ kiểm chứng chỉ mặc định, không đăng nhập/cookie, redirect
hoặc retry tự động. Mỗi nguồn có raw bytes, URL, thời điểm tải, trạng
thái và SHA-256. Một probe HTTP thành công trước đó được giữ riêng;
lượt trong sandbox lỗi DNS cũng giữ outcome, không coi là raw đã tải.
Capture chính thức có chín request thành công. Đây là thu thập phục
vụ phát triển sau khi đọc nguồn, không là thực nghiệm giữ kín đăng ký trước.

| Nguồn | Phạm vi dùng |
|---|---|
| [2021 ban đầu](https://vsdc.vn/vi/ad/68796), [2021 sửa đổi](https://vsdc.vn/vi/ad/76898) | Giữ cả hai lịch; chọn bản sửa đổi |
| [2022](https://vsdc.vn/vi/ad/144999) | Lịch nghỉ thanh toán năm 2022 |
| [2023 ban đầu](https://vsdc.vn/vi/ad/152241), [2023 sửa đổi](https://vsdc.vn/vi/ad/155165) | Chọn bản sửa đổi Quốc khánh |
| [2024 ban đầu](https://vsdc.vn/vi/ad/159293), [thông báo tháng 4](https://vsdc.vn/vi/ad/170099) | Bổ sung nghỉ 29/4, giữ phạm vi thanh toán cổ phiếu |
| [2025 công bố ban đầu](https://vsdc.vn/vi/ad/159292) | Chỉ dùng phần đuôi 01–03/01/2025; không xác minh toàn năm 2025 |
| [Thời điểm T+2 năm 2022](https://vsdc.vn/vi/ad/152750) | Lưu cơ sở thiết kế; chưa gán giờ tài sản về tài khoản |

Lịch 2021 sửa Tết từ 11–17/2 sang 10–16/2. Bản sửa đổi có hai chỗ
ghi năm 2020 trong phần chú thích nghỉ bù; raw giữ nguyên lỗi này,
curation dùng khoảng năm 2021 được ghi ở câu chính. Chưa có xác nhận
người đánh giá độc lập; không âm thầm sửa nội dung nguồn.
[Thông báo sửa đổi 2021](https://vsdc.vn/vi/ad/76898).

Lịch 2023 ban đầu nghỉ Quốc khánh 4–5/9; bản thay thế chuyển sang
1–4/9. Hệ thống chọn bản thay thế và giữ thay đổi ngày 1/9, 5/9,
không chỉ lấy tổng số ngày trong năm để kết luận đúng lịch.
[Thông báo sửa đổi 2023](https://vsdc.vn/vi/ad/155165).

Thông báo tháng 4/2024 bổ sung 29/4 vào khoảng nghỉ. Ngày làm bù
4/5 không có bù trừ/thanh toán chứng khoán cơ sở và phái sinh, nhưng
có ngoại lệ cho một số công cụ nợ. Profile chỉ dùng cho ngày thanh
toán cổ phiếu, không áp lịch này cho mọi loại tài sản.
[Thông báo tháng 4/2024](https://vsdc.vn/vi/ad/170099).

## Hợp đồng lịch và kết quả

Các khoảng nghỉ được trợ lý đọc và nhập vào config, có source ID,
hash raw/body, anchor kiểm tra và quan hệ thay thế giữa các revision.
Parser không tự hiểu ngữ nghĩa toàn thông báo. Hợp đồng chặn nguồn
thiếu/khác hash, revision trùng, nhánh thay thế mơ hồ, chọn bản cũ,
khoảng nghỉ chồng nhau hoặc lịch thiếu phần tiếp nối.

Ngày trong lịch ứng viên được tính bằng thứ Hai–thứ Sáu trừ khoảng
nghỉ đã nhập. Ngày thường còn lại chỉ có trạng thái `weekday_candidate`,
không được gọi là phiên HOSE đã xác minh. Ngày cuối tuần được ghi là
`weekend_assumption`; ngày nghỉ có reason/source riêng. Chưa thu đủ
thông báo HOSE gốc, sự cố/phiên bị rút ngắn và dữ liệu tài khoản môi giới.
Lịch được dựng hồi cứu, không chứng minh phiên bản đã biết tại cutoff cũ.

| Năm | Ngày ứng viên | FPT | HPG | VCB |
|---|---:|---:|---:|---:|
| 2021 | 250 | 250 | 250 | 250 |
| 2022 | 249 | 249 | 249 | 249 |
| 2023 | 249 | 249 | 249 | 249 |
| 2024 | 250 | 250 | 250 | 250 |
| Tổng | 998 | 998 | 998 | 998 |

Ba mã khớp toàn bộ tập ngày với lịch ứng viên: không có ngày thiếu
hoặc ngày thừa. Phép so không chỉ kiểm số lượng và không lấy giao
của các tập ngày. Giữ năm ngày thay đổi giữa lịch gốc/sửa đổi trong
`revision_changes.csv`. VNINDEX vẫn bị chặn bởi lỗi OHLC của snapshot
mốc 34, ghi vào `unassessed_instruments`, không vá giá hoặc giả vờ đã
đối soát nó qua chuẩn hóa. Nếu một cổ phiếu lỗi/thiếu dữ liệu, trạng
thái tổng không được báo khớp bằng cách bỏ mã đó đi.

Tạo 998 cặp ngày giao dịch → ngày thanh toán T+2 ứng viên, đếm trên
lịch riêng và có đuôi tới 03/01/2025. Ngày 30/12/2024 ánh xạ sang
02/01/2025; 31/12/2024 sang 03/01/2025. Đây là kết quả tính lịch từ
profile, chưa là log xác nhận thanh toán giao dịch thật.
Các trường `shares_available_at`, `sale_cash_available_at` giữ null:
thông báo thời hạn hoàn tất không tự trở thành giờ ghi có chính xác
cho một tài khoản. Không nối các ngày này vào `backtest-timed` khi
chưa có profile thời điểm/phạm vi được kiểm chứng.

## Chạy và tái lập

```powershell
# Capture nguồn mới, cần PowerShell 7.2+ và Internet.
pwsh -NoProfile -File scripts/capture-calendar-sources.ps1

# Dùng đúng archive nguồn và giá đã ghim, hoàn toàn offline.
.\run.ps1 calendar-audit --build --sources-run 20261103T025020Z-4e864c99 --market-run 20261102T145138Z-21243d88
.\run.ps1 calendar-audit --replay outputs/calendar-audits/20261103T025840Z-fa7a29cb
```

Capture là script Windows riêng; build/replay không có downloader.
Config hiện ghim bytes nguồn đã dùng. Nguồn web có thể thay đổi phần
điều hướng hoặc nội dung; archive mới khác hash cần đối chiếu và phát
hành profile mới, không sửa seal/hash của run cũ để ép replay đạt.

Mỗi audit pin seal cả source archive và snapshot giá, giữ profile
nguyên bytes, code snapshot, JSON, `calendar.csv`, `settlement_dates.csv`
và `revision_changes.csv`. Replay kiểm lại dependency, tái tính mọi
JSON/CSV và provenance; chặn override, đường dẫn ngoài outputs, file
thiếu/thừa hoặc thay đổi đã reseal. Source code snapshot chỉ để truy
nguyên, không được tự thực thi. Exit 0 chỉ báo tập ngày cổ phiếu khớp
lịch ứng viên, không cấp quyền sử dụng giá để thực thi hoặc chứng nhận PiT.

Run: `outputs/calendar-audits/20261103T025840Z-fa7a29cb/`.
Study: `outputs/calendar-development/20261103T025838Z-9308fc82/`.
Raw nguồn: `outputs/calendar-sources/20261103T025020Z-4e864c99/`.
Code/config/metadata nhỏ nằm trong Git; raw HTML/CSV/run không được push.
Clone mới muốn replay ID này cần khôi phục nguyên các dependency;
chưa xác nhận các thư mục mới đã được chủ dự án tải lên Drive.

35 test mới kiểm lịch bằng các ngày tính tay, sửa đổi có cùng tổng số
ngày, nghỉ lễ/cuối tuần, T+2, đuôi khác năm, input thiếu/mâu thuẫn,
nguồn/body hash, tamper/reseal, mã bị chặn, CLI và replay. Nhóm liên
quan có 114 test đạt; run thật và CLI replay khớp, 114 hash bảo vệ cũ
giữ nguyên. Không gọi LLM, ghi review DB thật hoặc tải thêm giá.
Toàn repository có 801 test đạt và Ruff đạt; còn hai cảnh báo phụ
thuộc cũ. Frontend không đổi nên không chạy lại build/QA giao diện.
Xem [data card](../../data/development/calendar-audit-v0.1/DATA_CARD.md)
và [validation](../../data/development/calendar-audit-v0.1/validation.json).

Tiếp theo cần nguồn HOSE cho lịch/phiên bất thường, quy tắc giờ khả
dụng theo giai đoạn và điều chỉnh giá/corporate actions. Các cờ
`venue_calendar_verified`, `broker_availability_verified`,
`eligible_for_execution`, `historical_availability_validated`,
`independent_gold`, `research_result` vẫn false; chưa chạy backtest giá thật.
