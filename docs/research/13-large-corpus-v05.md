# Corpus v0.5: nhập 30.000 bài có toàn văn và provenance

Đợt này đưa kho từ 939 lên **30.939 tài liệu**: giữ nguyên 264 PDF và 675 bài
thu thập trực tiếp, thêm 30.000 bài kinh doanh/bất động sản từ
[VietOnlineNews](https://huggingface.co/datasets/VLUS06/VietOnlineNews).
Số liệu hoàn tất và giới hạn ở [data card](../../data/corpus/v0.5/DATA_CARD.md).
Đây là tập bằng chứng phát triển truy xuất, chưa là tập đánh giá đóng băng
hay kết quả dự báo. Không huấn luyện một LLM mới.

## Nguồn và cách chọn

Revision pin: `bd8d2a865c8981d34cb9d85f69f62bda7c40b520`. File processed chứa
toàn văn; `news_metadata.csv` giữ URL, ngày đăng, tác giả và nguồn báo. Join
bằng ID và kiểm tra nhãn chuyên mục khớp. Chỉ nhận `Kinh doanh`/`Bất động sản`,
body 600–250.000 ký tự, tiêu đề có nội dung và ngày đăng parse được. Chuẩn hóa
URL HTTPS/bỏ tracking, loại trùng URL hoặc hash body sau chuẩn hóa khoảng trắng.
Nguồn hiện tại chỉ gồm Tuổi Trẻ, Thanh Niên và VietnamNet.

Đọc split nguồn theo thứ tự train → dev → test và dừng khi đủ 30.000 bài hợp
lệ. Split nguồn được giữ như metadata, chưa được coi là split đánh giá tài
chính. Không chọn mẫu theo lợi suất tương lai. Các dòng không nằm trong hai
chuyên mục được đếm riêng; lỗi join/thiếu text/ngày nằm trong rejected_rows,
không cộng vào số tài liệu nhận. Publisher/date/category là quan sát từ bên
tổng hợp, chưa phải human gold.

Một số nguồn lớn khác được khảo sát nhưng chưa đưa vào kho: bản phân loại
NamSyntax thiếu URL/ngày và nhiều dòng chỉ gồm title+description; BN-VN3S yêu
cầu quyền truy cập thủ công; corpus TiniX có khoảng 18 nghìn báo cáo nhưng
chưa tải/nhập trong đợt này. Không cộng các con số của nguồn tham khảo vào
30.939 tài liệu đã kiểm tra.

## Chạy lại

Trên máy hiện tại dùng `.venv312\Scripts\python.exe`. `run.ps1` tự ưu tiên
môi trường này nếu có; `.venv` cũ được giữ nguyên. Cấu hình nguồn và checksum
tại [`dataset_sources_v0_5.json`](../../configs/dataset_sources_v0_5.json).

```powershell
.venv312\Scripts\python.exe -m pit_haf.data.hub `
  --config configs/dataset_sources_v0_5.json `
  --root data/cache/datasets/vietonlinenews-bd8d2a8 `
  --file processed/news_metadata.csv --file processed/train.csv --file processed/dev.csv

.venv312\Scripts\python.exe -m pit_haf.data.dataset_import `
  --config configs/dataset_sources_v0_5.json `
  --input-root data/cache/datasets/vietonlinenews-bd8d2a8 `
  --output outputs/scale-expansion/my-import

.venv312\Scripts\python.exe scripts/release_dataset_corpus.py `
  --base-sources configs/corpus_sources_v0_4.json `
  --base-summary outputs/milestone-1/data-pilot/20261018-corpus-v0.4-news-curated/summary.json `
  --import-summary outputs/scale-expansion/my-import/summary.json `
  --universe configs/universe_v0_4.json `
  --staging outputs/scale-expansion/my-release `
  --activate outputs/milestone-1/data-pilot/my-v05 `
  --metadata-output outputs/my-v05-metadata --publish
```

Output phải là tên mới. Downloader giới hạn kích thước theo manifest, pin
SHA-256/revision, kiểm redirect công khai của Hub, tiếp tục `.part` khi server
chấp nhận Range; từ chối 401/403/429 và không dùng token hoặc chạy mã dataset.
Tái dùng local phải khớp checksum. Import kiểm lại toàn bộ file đầu vào, lưu
descriptor nguồn và raw JSON của từng cặp dòng CSV/metadata vào snapshot store.
Đọc lại nguồn đã pin có thể tái dùng đúng immutable version; không sửa metadata
quan sát ban đầu. Chỉ publish summary khi hoàn tất.

Release builder kiểm manifest, registry, raw/page hashes, catalog và mẫu số;
so pilot đóng băng 11 version/905 trang. Catalog được tạo ở staging, kiểm
SQLite quick_check và checksum, rồi mới chuyển thư mục đã hoàn tất vào vùng
snapshot hoạt động. Trong lúc nhập, snapshot cũ tiếp tục dùng được.

## Giao diện và tìm kiếm ở quy mô lớn

`catalog.sqlite3` là index phát sinh có thể dựng lại, không thay registry bất
biến. Trình duyệt tải 20 bản ghi/trang; API giới hạn 100. Lọc nguồn/năm/mã,
loại tài liệu và cách thu thập chạy bằng SQL trên server, tránh gửi toàn bộ
metadata và text của 30 nghìn bài vào browser. Thống kê là số liệu toàn bộ
scope trong catalog, không suy từ trang đang mở.

FTS5 chỉ xếp hạng đọc tài liệu **hiện tại**. Mỗi chunk giữ nguyên text/offset,
model vẫn nhận đoạn nguyên văn được đối chiếu. Chế độ lịch sử dùng gateway
trước; chỉ nạp các version được giao và dùng BM25 của tập đã lọc. Tập strict
rỗng không thể rơi về exploratory hoặc dùng IDF toàn catalog. Khi đọc/truy
xuất một nguồn, kiểm lại raw hash và metadata registry; index/summary bị đổi
checksum bị từ chối. Không đọc lại mọi raw blob ở mỗi request.

Giao diện ghi `Bản nhập dataset`, link vẫn trỏ bài báo gốc; provenance dataset
ID/revision/file/row/split giữ riêng. Bài JSON nhập từ dataset không bị đếm
thành PDF hoặc trang PDF. Bộ lọc `Loại nguồn` giúp phân biệt thu thập trực
tiếp với bản nhập, không che nguồn gốc để tăng số lượng.

## Giới hạn và phát hành

Dataset ghi license `other` và LICENSE rỗng ở revision này. Chưa xác lập quyền
phân phối lại toàn văn. CSV, raw, pages, SQLite và toàn văn chỉ lưu local,
được Git ignore; Git chứa code, cấu hình và index metadata nén. Ghi công
VLUS06/VietOnlineNews và nguồn báo. Nén JSONL metadata giúp tránh lặp hàng
trăm MB metadata trong repository, không nén toàn văn để đưa lên GitHub.

Ngày đăng là quan sát của mirror; không chứng minh bytes hiện tại tồn tại
trong quá khứ. `availability_basis=unverified`, `version_basis=observation_only`
và `available_at` trống. Chưa đánh giá ngữ nghĩa, human gold, survivorship,
split tài chính, graph/agents/memory hay backtest. Số tài liệu lớn không thay
thế các bước này.

Python 3.11 của máy bị Windows Application Control chặn khởi chạy ở đợt này.
Tạo môi trường `.venv312` riêng bằng runtime Python 3.12.14 có sẵn; mở phạm vi
Python 3.11–3.12 và giữ đúng phiên bản của 85 package đã khóa, chỉ bổ sung
wheel/marker cho Python 3.12. Không sửa môi trường cũ hoặc tắt chính sách bảo
vệ. Số đo pilot LLM cũ không chuyển thành benchmark trên runtime/corpus mới.
