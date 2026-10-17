# Pilot data card — 17/10/2026, v0.1

Mục đích: kiểm nguồn, parser, metadata/gateway và khả năng local LLM trích
đoạn tài chính tiếng Việt. Không dùng làm dataset dự báo/backtest cuối.

## Population và lựa chọn

Manifest `configs/pilot_sources.json`:11 tài liệu official public, FPT3 (công
nghệ), HPG7 (thép/công nghiệp), VCB1 (ngân hàng). Báo cáo thường niên/BCTC/
tổng quan kinh doanh chủ yếu kỳ2024–2026; chưa là universe lịch sử có đại diện.
Chọn URL theo khả năng truy cập và kiểu tài liệu, không theo future returns.
Sau khi thấy scan/text méo, bổ sung annual/overview để kiểm extraction;
đây là lựa chọn phát triển có ghi nhận, không freeze nghiên cứu.

Mục tiêu24documents còn thiếu13. Không có listing/delisting history, nên chưa
đánh giá survivorship bias hoặc coverage toàn thị trường. Các mã đang có là
case study feasibility, không đại diện universe được chọn cho thực nghiệm.

## Files và chất lượng

- Raw bytes, source/listing/rights/robots và acquisition ledger tại
  `data/cache/evidence/`; SQLite giữ hash nguyên metadata quan sát đầu.
- `snapshot_index.json` có11 phiên bản, sourceURL/rawSHA và tình trạng trang;
  `registry_metadata_sha256` gắn raw JSON trong DB, không phải JSON export đã
  thêm derived locator. Registry có checksum/append-only, chưa bitemporal.
- Replay offline:905pages,730 có text,175 không text/chưa OCR. Text-present
  không đồng nghĩa text đúng: HPGQ1/26 có chữ/số bị méo. pypdf6.21.0 có phát
  cảnh báo xref index trên một sốPDF; raw bytes được giữ nguyên.
- Có tiếng Việt/Anh và scan. Không tự sửa số âm, dấu phân cách hoặc bảng.
  OCR, table alignment, numeric/unit/scope QA diện rộng chưa thực hiện.
- Nguồn/URL cũ404 và lỗi extract trong lượt chuẩn bị dependencies được lưu;
  lượt offline thành công không xóa các failure trước.

## Thời gian và phiên bản

Tất cả11 versions hiện `availability_basis=unverified`, không có proof bytes
và giờ công bố lịch sử. Listing date chỉ là metadata ngày đang hiển thị.
`retrieved_at` là lúc tải hiện tại; không thay thế availability. Strict
gateway deliveries=0; không diễn giải thành0%leakage khi chưa giao evidence.
Chưa có conservative cohort đủ proof để sử dụng cho kết luận lịch sử.

Metadata v0.1 đóng băng first observation. Bổ sung/correct proof phải tạo
dataset/protocol release mới giữ registry cũ; chưa có attestation query đầy đủ.
Nguồn có thể thay bytes ở cùng URL; phải sohash khi tái tải.

## Extraction cases và gold

24snippets tiếng Việt từ3 annual reports,8/mã, cópage/char offsets/raw/text/
context hashes trong `outputs/milestone-1/pilot-cases/20261017/selection_audit.json`.
Không là24documents hoặc24 independent events. Bỏ text scan/méo khỏi tập
trích narrative này nhưng giữ chúng trong coverage/parser failure counts.

Quote proposals là silver source spans, không ground truth semantic/numeric
do người chấm độc lập. Numericgold=null, chưa nhãn UP/DOWN, chưa split train/
dev/test nghiên cứu. Đã assistant spot-check3 trang narrative đại diện và
một bảng có text méo; chưa có human inter-rater agreement.

## Rights và tái lập

FPT/HPG terms đã được khảo sát cho personal/noncommercial attribution.
VCB rights/redistribution chưa xác lập. Giữ attribution; chưa phát hành raw
corpus hoặc coi public URL là giấy phép tái phân phối. `data/cache/`, `outputs/`
bịGitignore; khi chuyển máy cần giữ riêng snapshot/raw outputs để replay.
Manifest/hash/index không bao gồm rawPDF. Thu thập mới có thể gặp API/URL đổi.

Lệnh tái trích không network: `./run.ps1 pilot-data --extract-existing`.
Chi tiết code, model, kết quả/lỗi và các bước cần hoàn thiện nằm trong
[báo cáo milestone](../../docs/research/08-local-pilot-results.md).
