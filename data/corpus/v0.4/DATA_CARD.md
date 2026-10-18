# Corpus phát triển v0.4 — báo cáo và bài viết thật

Phát hành: 18/10/2026. Đây là kho bằng chứng phục vụ phát triển truy xuất; không huấn luyện LLM, không có nhãn dự báo hay kết quả backtest.

| Chỉ số | Giá trị |
|---|---:|
| Bản ghi cấu hình (gồm cả lỗi/exclusion) | 1163 |
| Tài liệu/bài viết đang hoạt động | 939 |
| PDF khác nhau | 264 |
| Bài viết HTML | 675 |
| Trang PDF vật lý | 17915 |
| Trang PDF có text | 12943 |
| Trang PDF chưa có text / chưa OCR | 4972 |
| HTML sections (1/bài; không phải trang PDF) | 675 |
| Doanh nghiệp trong universe | 13 |
| Ô báo cáo thường niên 2016–2025 đã có | 75/130 |
| Đủ điều kiện PiT strict | 0 |

## Nguồn tin mới

Khám phá 881 URL ứng viên; 675 URL qua trích xuất/review trước curation, 206 URL thất bại. URL trùng discovery không tăng số bài. Có 675 body hash khác nhau; chưa dedup ngữ nghĩa/tin đăng lại giữa báo.

| Nguồn | Bài qua trích xuất/review |
|---|---:|
| Báo Tài chính - Đầu tư | 88 |
| CafeF | 206 |
| Báo điện tử Chính phủ | 91 |
| Tập đoàn FPT | 12 |
| Tập đoàn Hòa Phát | 104 |
| Công ty Cổ phần Cơ Điện Lạnh REE | 17 |
| VietnamBiz | 14 |
| VnExpress | 143 |

Phân loại HTML: 451 bài báo, 91 tin chính sách/vĩ mô và 133 tin doanh nghiệp tự công bố.
Ngày đăng quan sát từ 2020-02-16 đến 2026-10-18; 0 bài chưa lấy được ngày đăng. Phạm vi ngày này không chứng minh kho lịch sử đã đầy đủ.

## Provenance, thời gian và quyền nội dung

Manifest [corpus_sources_v0_4.json](../../../configs/corpus_sources_v0_4.json) giữ nguyên 282 record PDF của v0.3 và thêm từng URL tin, kể cả lỗi. [Cấu hình nguồn tin](../../../configs/news_sources_v0_4.json) ghi RSS/danh mục, selector, trần và alias. [news_audit.json](news_audit.json) pin snapshot discovery/acquisition/review, từng URL, lỗi, ngày quan sát, body hash và liên kết mã. [raw_inventory.json](raw_inventory.json) và [snapshot_index.json](snapshot_index.json) giữ metadata/hash; [coverage.json](coverage.json) có mẫu số và backlog.

Raw HTML/PDF, toàn văn và SQLite lưu local trong `data/cache/evidence` và `outputs/`, không đưa GitHub. Metadata không cấp quyền phân phối lại bài báo. Nguồn báo chí, Chính phủ và doanh nghiệp tự công bố được phân biệt; không coi phát biểu là kết luận đã xác minh.

Ngày không có timezone chỉ giữ `publication_date`; không suy ra thời điểm từ URL, năm, file hay lúc tải. `available_at` trống, version observation-only; tất cả bài mới vẫn quarantine khỏi lịch sử strict. `MARKET` là bối cảnh thị trường, không là doanh nghiệp thứ 14. Alias chỉ gắn từ tiêu đề/lede hoặc nguồn doanh nghiệp, chưa phải human gold; một bài có nhiều related_tickers vẫn chỉ tính một lần.

## Kiểm tra và giới hạn

HTML review dùng extractor `html-article/2`, đọc raw local và xuất bản trích mới có hash riêng; giữ nguyên metadata/ngày tải và artifact lần đầu. Bỏ script/quảng cáo/liên kết liên quan/nội dung ẩn, từ chối metadata paywall và body quá ngắn. Trang danh mục/lỗi, bài ngoài chủ đề hoặc lỗi mạng được giữ trong mẫu số. Việc có text không chứng minh trích xuất đủ ngữ nghĩa, bảng/số chính xác hoặc báo chí đúng.

Review offline thay đổi hash text của 17 bài do loại thêm nội dung ẩn; không thay raw hoặc metadata ban đầu. Cấu hình discovery ban đầu và cấu hình review được pin riêng trong `news_audit.json`. Discovery đầu có lỗi kiểm trần các trang đã xếp hàng: HPG tải 8 trang danh mục thay vì 7, REE 4 thay vì 3; toàn bộ resource được giữ trong audit, trần số ứng viên vẫn được giữ. Lỗi kiểm trần đã sửa cho các lần chạy sau.

[verification.json](verification.json) xác nhận 11 phiên bản registry và 905 hash text trang của pilot đóng băng không đổi. Defaults HTML/related_tickers khi đọc PDF cũ không ghi lại JSON/hash bất biến. Pilot LLM 24 đoạn cũ chưa đo lại trên kho mới.

RSS/danh mục hiện tại thiên về tin mới và nguồn truy cập được; chưa cân bằng ngành/mã/năm, không có universe lịch sử, proof revision độc lập, human gold, split train/dev/test đóng băng hay đánh giá dự báo. Backlog OCR PDF cũ được giữ nguyên. Tin nhanh chứng khoán bị loại do lỗi TLS; không bỏ xác minh chứng chỉ. Feed Báo Đầu tư trả rỗng được ghi là thất bại, tin lấy từ danh mục công khai.

Xem [lệnh thu thập, replay offline và giới hạn](../../../docs/research/12-news-corpus-v04.md). Full agents/graph/memory và backtest của PiT-HAF chưa triển khai.
