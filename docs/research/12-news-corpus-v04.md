# Corpus v0.4: báo chí, chính sách và tin doanh nghiệp

Đợt này bổ sung bài viết HTML vào kho PDF. Đây là dữ liệu nguồn phục vụ truy
xuất và phát triển đánh giá, không phải dữ liệu huấn luyện LLM. Kết quả tải,
lỗi, ngày quan sát, độ phủ và giới hạn nằm trong
[data card](../../data/corpus/v0.4/DATA_CARD.md). Nội dung bài báo không phải
human gold hoặc kết quả của hệ PiT-HAF.

## Các loại bằng chứng

- `news_article`: bài báo kinh tế, tài chính và ngành từ VnExpress, CafeF,
  Báo Đầu tư và VietnamBiz. Phân biệt nguồn báo chí với nội dung được xác minh.
- `official_policy_news`: tin kinh tế từ Báo điện tử Chính phủ. Bài giới thiệu
  chính sách không thay thế văn bản pháp quy gốc.
- `issuer_news`: tin do Hòa Phát, FPT hoặc REE tự công bố. Đây là phát biểu của
  doanh nghiệp, cần đối chiếu khi dùng để kết luận.
- `MARKET`: phạm vi thị trường/vĩ mô khi tiêu đề và mô tả đầu bài không gắn
  với một trong 13 mã đang theo dõi. Không tính thành doanh nghiệp thứ 14.

Mã cổ phiếu/alias chỉ được tìm ở tiêu đề và mô tả đầu bài, hoặc theo nguồn
doanh nghiệp. `related_tickers` giữ nhiều mã trên cùng một bài; không nhân bản
bài để tăng số lượng. Liên kết này chưa được con người duyệt. Tin về doanh
nghiệp ngoài universe vẫn có thể mang nhãn MARKET; nhãn này chỉ là bối cảnh
truy xuất, không khẳng định bài viết không nhắc doanh nghiệp.

## Thu thập và tái lập

Các lệnh gọi Python trong `.venv`. Luôn chọn thư mục output mới; không ghi đè
artifact cũ. Cấu hình nguồn được pin tại
[`news_sources_v0_4.json`](../../configs/news_sources_v0_4.json).

```powershell
.venv\Scripts\python.exe -m pit_haf.data.news discover `
  --config configs/news_sources_v0_4.json --output outputs/news/my-discovery

.venv\Scripts\python.exe -m pit_haf.data.news acquire `
  --discovery outputs/news/my-discovery/discovery.json `
  --output outputs/news/my-acquisition --skip-registered

.venv\Scripts\python.exe -m pit_haf.data.news reextract `
  --summary outputs/news/my-acquisition/summary.json `
  --discovery outputs/news/my-discovery/discovery.json `
  --output outputs/news/my-offline-review
```

Discovery đọc RSS và các danh mục công khai theo giới hạn nguồn, loại URL
trùng và chỉ theo phân trang đã quan sát. Nội dung HTML/feed giới hạn 3 MiB
sau giải nén, body 400–250.000 ký tự, một request tuần tự mỗi giây trong mỗi
batch. URL phải nằm trong allowlist HTTPS; robots disallow được tôn trọng.
Không vượt paywall, TLS, HTTP 403/429 hoặc đổi danh tính truy cập. robots
không tải được được ghi rõ là policy unknown, không coi là giấy phép.

`acquire` chỉ lấy body theo selector đã kiểm tra; không dùng mô tả RSS như
toàn văn. Trang danh mục/lỗi, body ngắn, nội dung ngoài phạm vi và nguồn bị
chặn vẫn nằm trong mẫu số thất bại. Raw response, hash, URL, thời điểm tải,
nguồn phát hiện và quan sát ngày đăng được lưu lại. `--skip-registered`
tái dùng đúng một phiên bản local, không kiểm tra revision từ xa.

`reextract` kiểm checksum đầu vào và đọc raw local với phiên bản extractor
hiện tại, không gửi HTTP. Phiên bản/metadata quan sát ban đầu không đổi;
trang trích xuất mới, hash text thay đổi và nguồn đầu vào được xuất riêng.
Đợt v0.4 review bằng `html-article/2`, bỏ nội dung ẩn inline và kiểm tra
metadata paywall lồng nhau. Các trang trích xuất lần đầu được giữ nguyên.

Nguồn tin mới dùng `news acquire`, không đưa HTML vào lệnh tải PDF. Để ghép
với corpus cũ, tạo manifest hợp nhất từ manifest PDF và `sources.json` của
từng batch tin. Dùng `pit_haf.data.corpus` để kiểm định danh/hash/trang và
`pit_haf.data.coverage` để xuất coverage với `universe_v0_4.json`. Manifest
đã hoàn tất tại [`corpus_sources_v0_4.json`](../../configs/corpus_sources_v0_4.json).
Mỗi record phải có kết quả thành công, thất bại hoặc curation exclusion.

## Thời gian và chất lượng

`published_at` chỉ là chuỗi có timezone quan sát ở RSS/HTML/JSON-LD. Ngày
không có timezone được giữ ở `publication_date`, không tự gán giờ Việt Nam.
Không lấy năm trong URL làm ngày đăng. `available_at` tiếp tục để trống;
`availability_basis=unverified`, `version_basis=observation_only`. Bytes tải
hôm nay có thể đã được chỉnh sửa sau ngày đăng, nên bài cũ không tự trở thành
bằng chứng lịch sử. Tin chưa có proof/review vẫn bị chặn khỏi PiT strict.

Mỗi HTML article có một section văn bản, không phải một trang PDF vật lý.
Coverage tách `pdf_page_count`, `text_pdf_page_count`, `html_articles` và
`html_section_count`. Kiểm tra SHA-256 xác nhận toàn vẹn artifact; không chứng
minh tính chính xác của báo chí, liên kết mã, nội dung bảng hoặc thời gian.
Các defaults mới khi đọc metadata PDF cũ không sửa JSON/hash bất biến trong
registry. Pilot 11 phiên bản/905 trang và kết quả LLM cũ được kiểm riêng.

RSS/danh mục hiện tại thiên về tin mới và nguồn dễ truy cập. Kho chưa cân
bằng theo mã/ngành/năm, chưa có dedup ngữ nghĩa giữa các báo hoặc split đánh
giá đóng băng. Không lấy số bài tăng lên làm bằng chứng chất lượng dự báo.
Full agents/graph/memory và backtest tiếp tục là phần chưa triển khai.

Raw HTML, PDF, full text và SQLite ở local được Git ignore. Git chỉ chứa mã,
URL/tiêu đề/metadata và checksum, không chứa toàn văn bài báo. Chưa xác lập
quyền phân phối lại nội dung; tải trên máy khác có thể trả bytes khác và phải
kiểm hash/review lại. Hướng dẫn RSS của nguồn:
[VnExpress](https://vnexpress.net/rss), [CafeF](https://cafef.vn/rss.chn),
[Báo Đầu tư](https://baodautu.vn/rssMain.html).
