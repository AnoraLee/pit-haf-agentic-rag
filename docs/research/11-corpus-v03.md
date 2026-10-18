# Corpus phát triển v0.3

Đợt này mở rộng bằng báo cáo thật từ website doanh nghiệp. Số lượng hoàn tất,
trang có text, backlog OCR, lỗi và độ phủ từng mã nằm trong
[data card](../../data/corpus/v0.3/DATA_CARD.md) và
[coverage](../../data/corpus/v0.3/coverage.json). Universe có 13 mã hiện tại,
mục tiêu thường niên 2016–2025, cùng báo cáo tài chính/tổng quan kinh doanh đến
2026. Đây chưa phải universe đầu tư lịch sử; chưa xử lý survivorship bias hoặc
freeze train/dev/test. Không tạo báo cáo giả hay nhãn dự báo.

## Nguồn và artifact

- [Manifest](../../configs/corpus_sources_v0_3.json): 282 logical records, URL
  HTTPS, kỳ báo cáo và phạm vi hợp nhất/riêng lẻ.
- [Discovery index](../../data/corpus/v0.3/discovery_index.json): URL và checksum
  HTML/JSON nguồn, nhãn quan sát. API JSON Techcombank là endpoint công khai
  mà script của trang danh mục gọi; không dùng tài khoản hoặc API key.
- [Acquisition plan](../../data/corpus/v0.3/acquisition_plan.json): ID từng batch,
  pin cấu hình, giới hạn và các lần retry có chỉ định. Một tiêu đề chưa đăng ký
  được trim khoảng trắng; lỗi ban đầu và hash manifest lần đó được giữ lại.
- PDF, pages JSONL, registry SQLite, HTML nguồn và ảnh kiểm tra nằm ở local,
  được Git ignore. GitHub chứa mã và metadata/checksum; chưa có quyền phân
  phối lại PDF. Snapshot v0.1/v0.2 và các attempt lỗi được giữ nguyên.

Không suy ra `available_at` từ tên file, thư mục năm/tháng, PDF creation date
hoặc lúc tải. Nhãn/ngày trên danh mục chỉ hỗ trợ phân loại, chưa chứng minh
bytes hiện tại đã tồn tại ở một thời điểm quá khứ.

## Tải theo batch

Trên máy đã có snapshot v0.2, chuẩn bị một batch như sau. Chọn tên output mới,
vì công cụ từ chối ghi đè artifact đã tồn tại:

```powershell
.venv\Scripts\python.exe -m pit_haf.data.batches `
  --sources configs/corpus_sources_v0_3.json `
  --plan data/corpus/v0.3/acquisition_plan.json `
  --batch official-reports --output outputs/run-configs/official-reports.json

.\run.ps1 pilot-data --sources outputs/run-configs/official-reports.json `
  --skip-registered --output outputs/dataset-expansion/runs/my-official-reports
```

Các batch khác: `banks-and-annual-gap`, `transport-metadata-retry`,
`large-official-pdfs`. Batch cuối nâng riêng giới hạn 64 lên 128 MiB cho ba
báo cáo SSI. Trần cứng 128 MiB và 500 trang/PDF vẫn áp dụng. Mỗi batch tải
lần lượt, nghỉ ít nhất một giây giữa các tài liệu; không vượt 403/robots hoặc
đổi danh tính/proxy. URL chứa dấu cách được encode ở lớp HTTP, vẫn giữ nguyên
locator danh mục trong metadata.

`--skip-registered` chỉ tái dùng khi record có đúng một phiên bản local và
manifest khớp metadata bất biến; không kiểm tra revision trên mạng. Nhiều
revision cần chọn rõ ràng. Cùng URL có thể trả bytes khác trên máy/ngày khác:
hash khác cần review mới, không đổi pin để giả định tái lập được bản cũ.

## Ghép và kích hoạt

Công cụ merge kiểm tra checksum tập trang, hash text, định danh nguồn, trang
liên tục và mẫu số trước khi xuất. Dòng trang được sao chép nguyên văn, không
trích lại hoặc chuẩn hóa. Mỗi record phải có kết quả thành công, lỗi hay
exclusion. Record trùng chỉ được nhận khi chỉ định retry từ một attempt lỗi;
không thay phiên bản đã thành công/đã review. Retry vẫn có thể lỗi: cả attempt
trước và sau được lưu, số lượng thành công không được tăng vì đã thử lại.

```powershell
.\run.ps1 corpus-merge --sources configs/corpus_sources_v0_3.json `
  --summary outputs/milestone-1/data-pilot/20261017-corpus-v0.2-curated/summary.json `
  --summary outputs/dataset-expansion/runs/v03-new-20261018/summary.json `
  --summary outputs/dataset-expansion/runs/v03-banks-20261018/summary.json `
  --summary outputs/dataset-expansion/runs/v03-transport-metadata-retry-20261018/summary.json `
  --summary outputs/dataset-expansion/runs/v03-large-official-pdfs-20261018/summary.json `
  --retry-failed-record PNJ-consolidated-reviewed-2025-H1 `
  --retry-failed-record PNJ-parent-reviewed-2025-H1 `
  --retry-failed-record TCB-parent-reviewed-2026-H1 `
  --retry-failed-record SSI-annual-2022-vi `
  --retry-failed-record SSI-annual-2023-vi `
  --retry-failed-record SSI-annual-2025-vi `
  --output outputs/dataset-expansion/releases/my-v03-merged

.\run.ps1 corpus-coverage `
  --summary outputs/dataset-expansion/releases/my-v03-merged/summary.json `
  --universe configs/universe_v0_3.json `
  --curation data/corpus/v0.3/curation.json `
  --curated-output outputs/milestone-1/data-pilot/my-v03-curated `
  --output outputs/my-v03-metadata
```

Tên input trên là artifact thật của đợt tải tại máy hiện tại. Curation pin đúng
record/version/raw hash của PDF trắng đã xem ảnh; không sửa PDF hoặc thêm chữ
vào scan. Bytes khác thì dừng để review. Giao diện chuyển snapshot sau khi
`summary.json` hoàn chỉnh được công bố; trong lúc tải, kho cũ vẫn dùng được.
Coverage UI chỉ nhận metadata có `summary_sha256` khớp snapshot đang mở.

## Giới hạn chất lượng

Text dùng pypdf strict, chưa OCR. Scan vẫn có thể là báo cáo thật và được tính
vào độ phủ PDF nhưng chưa truy xuất được nội dung. PDF parser từ chối được giữ
ở raw store và danh sách lỗi. Text tồn tại chưa đảm bảo font, bảng, số liệu
hoặc ngữ nghĩa chính xác. `ocr_backlog` và cảnh báo parser ghi phần còn thiếu.

Corpus mới phục vụ phát triển retrieval và chuẩn bị đánh giá. Pilot LLM 24 đoạn
cũ chưa đo trên corpus mới. Chưa có human gold độc lập, nhãn lợi suất, backtest
hoặc kết quả Agentic-RAG trên dataset này. Bước tiếp theo cần ưu tiên OCR/kiểm
tra số liệu, cân bằng nguồn, proof lịch sử, dữ liệu giá và freeze protocol.
