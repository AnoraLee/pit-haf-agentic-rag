# Data card — Corpus phát triển v0.3

Chốt ngày 18/10/2026. Dữ liệu thật phục vụ phát triển truy xuất bằng chứng và chuẩn bị đánh giá KLTN PiT-HAF; không phải dữ liệu huấn luyện LLM, human gold hoặc kết quả dự báo.

## Quy mô đã kiểm tra

| Chỉ tiêu | Kết quả |
|---|---|
| Logical records cấu hình | 282 |
| Raw PDF responses đã đăng ký | 281 (gồm cả file lỗi/excluded) |
| Tài liệu được chọn vào kho hiện hành | **264** |
| PDF khác nhau theo SHA-256 trong kho hiện hành | 264 |
| Doanh nghiệp / nhóm ngành rộng gán thủ công | 13 / 9 |
| Trang PDF vật lý được chọn | **17.915** |
| Trang có text trích xuất | 12.943 |
| Trang không có text, chưa OCR | 4.972 |
| Tài liệu có ít nhất một trang text | 141 |
| Tài liệu hoàn toàn chưa có text trích xuất | 123 |
| Độ phủ thường niên 2016–2025, doanh nghiệp × năm | 75/130 |
| Báo cáo thường niên / tài chính / tổng quan kinh doanh | 76 / 171 / 17 |
| BCTC hợp nhất / công ty mẹ-riêng lẻ | 87 / 84 |
| Raw bytes riêng biệt của tài liệu được chọn | 2.189.242.878 bytes (2.04 GiB) |
| Chưa đưa vào kho hiện hành | 18: 15 parser, 2 PDF trắng, 1 vượt giới hạn tải |
| Tài liệu có cảnh báo parser / có thể thiếu nội dung | 84 / 4 |
| Đủ điều kiện gateway PiT strict | **0** |

Tăng từ 29 tài liệu/3.243 trang ở v0.2 lên 264 tài liệu/17.915 trang. Coverage theo ô năm không cộng thêm bản dịch hoặc revision; số logical records được tách khỏi số PDF khác nhau. Kho hiện hành không có hai record cùng raw hash.

## Phân bố

| Mã | Nhóm ngành thủ công | Tài liệu | Trang PDF | Trang text | Năm thường niên đã có trong mục tiêu |
|---|---|---:|---:|---:|---|
| FPT | Công nghệ | 12 | 1.674 | 1.570 | 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025 |
| HPG | Vật liệu | 103 | 4.511 | 1.512 | 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025 |
| VCB | Ngân hàng | 1 | 106 | 106 | 2024 |
| ACB | Ngân hàng | 1 | 142 | 141 | 2024 |
| VNM | Hàng tiêu dùng | 10 | 1.200 | 1.180 | 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025 |
| MWG | Bán lẻ | 2 | 193 | 97 | 2023, 2024 |
| PNJ | Bán lẻ | 45 | 2.120 | 581 | 2019, 2020, 2021, 2023, 2024, 2025 |
| REE | Hạ tầng đa ngành | 6 | 631 | 624 | 2020, 2021, 2022, 2023, 2024, 2025 |
| GAS | Năng lượng | 5 | 418 | 414 | 2019, 2020, 2021, 2022, 2023 |
| SSI | Chứng khoán | 5 | 651 | 599 | 2020, 2021, 2022, 2023, 2024 |
| DPM | Phân bón và hóa chất | 9 | 750 | 747 | 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025 |
| TCB | Ngân hàng | 64 | 5.428 | 5.283 | 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025 |
| BID | Ngân hàng | 1 | 91 | 89 | 2024 |

Báo cáo tài chính/tổng quan được bổ sung từ nhiều quý, giữa niên độ và năm, đến 2026. Nguồn chưa cân bằng: HPG và TCB có nhiều báo cáo hơn các mã còn lại. Universe là tập doanh nghiệp hiện tại chọn theo nguồn chính thức có thể truy cập và sự đa dạng hoạt động; chưa xác minh thành viên lịch sử hoặc survivorship bias.

## Nguồn, tải và bảo toàn dữ liệu

- [Manifest URL](../../../configs/corpus_sources_v0_3.json), [universe](../../../configs/universe_v0_3.json), [discovery index](discovery_index.json) và [kế hoạch batch](acquisition_plan.json) ghi nguồn, nhãn và checksum HTML/JSON. Không dùng nguồn do mô hình tạo.
- Chỉ thu thập URL HTTPS official/CDN được liệt kê. HTML/robots/rights và lỗi được lưu local. 403 không bị vượt bằng đổi danh tính hoặc proxy. Không dùng API key/tài khoản trả phí.
- Mặc định giới hạn 64 MiB, riêng batch SSI lớn thử lại với 128 MiB; hard cap 128 MiB và 500 trang/PDF. SSI 2022/2023 được bổ sung sau retry; SSI 2025 vẫn vượt giới hạn và còn thiếu.
- Ba lỗi đường dẫn/khoảng trắng metadata được sửa trước khi đăng ký phiên bản thành công. Sáu logical records được retry có chỉ định (năm thành công, một vẫn lỗi). Mọi attempt ban đầu vẫn nằm trong ledger và provenance của snapshot ghép.
- [Raw inventory](raw_inventory.json) có 281 phiên bản đã tải, trạng thái sử dụng và hash metadata; raw lỗi được giữ lại. [Snapshot index](snapshot_index.json) chỉ gồm 264 tài liệu được chọn.
- [Integrity verification](verification.json) xác nhận 11 metadata phiên bản và 905 hash văn bản trang của pilot v0.1 được giữ nguyên trong kho mới. Không sửa text để làm đẹp kết quả.

## Chất lượng trích xuất và dữ liệu còn thiếu

- pypdf strict, chưa OCR. Trang không có text có thể là scan/font không trích được, không đồng nghĩa trang trắng. 123 tài liệu hiện chưa tìm kiếm nội dung được; chỉ có raw PDF và metadata. `ocr_backlog` trong coverage xếp các tài liệu cần xử lý tiếp.
- 13 BCTC PNJ bị pypdf từ chối do dictionary có nhiều định nghĩa `/Info`. Raw được giữ; chưa đánh giá nội dung bằng parser thay thế. PNJ thường niên 2022 chạm giới hạn token stream; MWG thường niên 2022 có xref hỏng.
- Link GAS 2024 và 2025 hiện trả PDF trắng một trang, đã render và xem ảnh; curation pin đúng version/hash, không tính vào báo cáo thường niên. PDF và lịch sử tải ban đầu vẫn giữ nguyên.
- 84 tài liệu phát cảnh báo parser; 4 có dấu hiệu nội dung bị bỏ qua. Giao diện và trace mang cảnh báo đó. Text có mặt hoặc quote khớp chuỗi chưa chứng minh bảng/số liệu đầy đủ và chính xác.
- Một link signed Q1/2026 trong danh mục TCB trỏ filename 2q26; dùng bản searchable Q1 được danh mục liên kết riêng, đã đối chiếu trang tiêu đề có kỳ kết thúc 31/03/2026. Đây là spot check của công cụ, không phải human gold độc lập.

Chi tiết 18 ca chưa dùng được, 55 ô năm thiếu và backlog OCR nằm trong [coverage.json](coverage.json). Không loại các ca lỗi khỏi mẫu số.

## Giới hạn nghiên cứu và quyền sử dụng

Không có human gold độc lập, nhãn lợi suất, split đánh giá được freeze hoặc kết quả dự báo/backtest trên corpus này. Pilot LLM 24 đoạn cũ vẫn là pilot cũ; chưa đánh giá model trên 264 tài liệu. Không suy ra thời điểm khả dụng lịch sử từ tên file, PDF creation date hoặc ngày tải. Toàn bộ bằng chứng vẫn bị quarantine cho chế độ lịch sử strict vì thiếu proof thời điểm/phiên bản.

Copyright/quyền phân phối lại chưa được xác lập. PDF và nội dung trang giữ ở `data/cache/evidence` và `outputs` tại máy, không commit GitHub; bản này chỉ công bố mã, metadata và checksum.

## Mở và tái chạy

- Giao diện: [Kho bằng chứng](http://localhost:8501/#documents) — có lọc mã, năm, loại, hợp nhất/riêng lẻ và phân trang 20 tài liệu.
- Snapshot local: `outputs/milestone-1/data-pilot/20261018-corpus-v0.3-curated/summary.json`.
- SHA-256 summary: `ed471500b9fe694f9e0221f58805150d1a1573c5087e847d341718c64ce68f97`.
- [Lệnh batch/merge/curation](../../../docs/research/11-corpus-v03.md). URL hiện tại có thể đổi bytes; hash không khớp cần review mới. Bản raw đã lưu mới cho phép replay đúng bytes của lần này.
