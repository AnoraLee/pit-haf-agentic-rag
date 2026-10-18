# Corpus phát triển v0.5 — quy mô 30 nghìn bài nhập thêm

Kho hoạt động có **30,939 tài liệu**, gồm 264 PDF, 675 bài thu thập trực tiếp và **30,000 bài toàn văn nhập từ dataset**. Giữ nguyên 17,915 trang PDF; bài viết có 1 section riêng, không cộng thành trang PDF.

Nguồn nhập: [VLUS06/VietOnlineNews](https://huggingface.co/datasets/VLUS06/VietOnlineNews), revision `bd8d2a865c8981d34cb9d85f69f62bda7c40b520`. Lọc các nhãn nguồn `Kinh doanh` và `Bất động sản`, ghép ID với `processed/news_metadata.csv` để giữ URL, tác giả, báo đăng và ngày công bố. Bài không đủ body 600 ký tự, lỗi join/ngày, trùng URL hoặc hash body chuẩn hóa bị loại; không dùng tóm tắt sinh để tăng số lượng. Kho không huấn luyện một LLM mới.

## Số liệu đã kiểm tra

- Mới nhập: 30,000 bài; ngày đăng quan sát 2023-01-01 đến 2025-12-31.
- Phân bố báo của bài mới: {"Tuổi Trẻ": 7091, "Thanh Niên": 7671, "VietnamNet": 15238}.
- Split phân loại gốc được giữ để truy vết: {'dev': 2230, 'train': 27770}. Đây chưa phải split đánh giá tài chính độc lập.
- Selection: {'scanned_rows': 201011, 'outside_categories': 170860, 'domain_candidate_rows': 30151}; 151 dòng ứng viên bị từ chối. Các dòng ngoài hai nhóm chủ đề không được tính là tài liệu đã nhập.
- Mẫu số manifest sau ghép: 31,163 records; 224 record lỗi/exclusion cũ vẫn được giữ. Bộ đếm selection CSV ở trên là mẫu số riêng.
- PiT strict: 0. Không suy `available_at` từ ngày đăng/URL hoặc thời điểm tải dataset.
- Pilot đóng băng: 11 metadata registry và 905 hash văn bản trang giữ nguyên. Không chạy LLM/dự báo/backtest trong đợt nhập này.

## Provenance và quyền nội dung

`origin=dataset_mirror`, raw snapshot là JSON của dòng CSV và metadata ghép, **không phải HTML tải trực tiếp từ báo**. `source_url` vẫn trỏ đến bài gốc; dataset ID/revision/file/row/split được lưu riêng. Giờ/ngày xuất bản là quan sát của bên tổng hợp, chưa có bằng chứng revision lịch sử. Việc có nhiều tài liệu không tự chứng minh chất lượng dự báo.

Dataset ghi license `other`; file LICENSE rỗng tại revision đã pin. Chưa xác lập quyền phân phối lại toàn văn. Dữ liệu chỉ lưu local cho nghiên cứu KLTN; ghi công VLUS06/VietOnlineNews và ba báo gốc. Git chỉ chứa mã, cấu hình, metadata/checksum nén, không chứa body bài báo, CSV, PDF hoặc database.

`registry_index.jsonl.gz` là JSONL metadata không chứa nội dung bài, gồm cả version lỗi/đã loại; dùng gzip để tránh lặp metadata lớn trong Git. Hash registry là hash JSON gốc trước các default mới. `coverage.json` tách PDF/HTML/bản nhập dataset. `verification.json` ghi integrity, nguồn và môi trường; không phải đánh giá ngữ nghĩa/human gold. `validation.json` ghi 274 test phần mềm đạt, kiểm tra HTTP trên kho thật và kiểm tra giao diện local; chưa xác nhận GitHub Actions hoặc chất lượng dự báo.

## Truy xuất và giới hạn

Catalog SQLite/FTS5 phục vụ phân trang/lọc trên server; trình duyệt nhận tối đa 20 hàng mỗi trang, API chặn limit trên 100. Truy xuất hiện tại dùng FTS5 BM25, offset trỏ nguyên văn. Chế độ lịch sử lọc gateway trước, chỉ nạp tập được giao và dùng BM25 trên tập đó; không dùng thống kê FTS toàn kho để xếp hạng lịch sử. Raw hash được kiểm khi tạo index và khi mở đoạn/trang, không đọc toàn bộ raw ở mỗi request.

Thiên lệch nguồn, phân bố năm/ngành và selection vẫn tồn tại. Nhãn chuyên mục và liên kết 13 mã trong cấu hình chưa được người độc lập duyệt. `MARKET` là bối cảnh chưa gắn một trong 13 mã, không phải kết luận bài không nhắc doanh nghiệp khác. Chưa dedup ngữ nghĩa giữa các báo; chưa có protocol/split/gold đóng băng hoặc full agents/graph/memory/backtest.

Python 3.11 cũ trên máy bị Windows Application Control chặn khởi chạy. Tạo `.venv312` riêng từ runtime Python 3.12.14 có sẵn, không tắt bảo vệ hoặc sửa `.venv` cũ. Giữ các phiên bản dependency đã khóa; pilot LLM cũ thuộc môi trường cũ, không gộp số đo hiệu năng.

Xem [quy trình nhập và chạy lại](../../../docs/research/13-large-corpus-v05.md).
