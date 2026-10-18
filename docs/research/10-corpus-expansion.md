# Đợt mở rộng corpus v0.2

Ngày 17/10/2026: đã push mốc dashboard/pipeline lên `main` tại commit `a159849`.
Đợt tiếp theo tập trung dữ liệu: từ 11 tài liệu/3 mã lên corpus đã lọc gồm
29 tài liệu/10 mã, 3.243 trang PDF; không chạy lại model hoặc đổi điểm pilot cũ.

Chi tiết mẫu số, bảng coverage, quyền sử dụng và ca lỗi nằm trong
[data card v0.2](../../data/corpus/v0.2/DATA_CARD.md). **29 tài liệu không phải 29
sự kiện độc lập**, và chưa đạt universe/ngữ nghĩa/gold đủ cho thực nghiệm cuối.

## Thay đổi kỹ thuật

- Manifest v0.2/universe riêng giữ nguyên metadata 11 tài liệu cũ; snapshot/ledger
  bất biến. Những bản chưa đủ proof vẫn bị gateway cách ly.
- `pilot-data --skip-registered`: tái dùng một version local, ghi rõ không kiểm
  remote revision. Nhiều versions cùng logical record phải chọn chính sách riêng,
  không âm thầm lấy một bản. Summary được xuất atomic sau khi hoàn tất.
- Parser warning collector lưu số lượng, trang và trường hợp text có thể bị cắt.
  Giữ giới hạn 64 MiB/500 trang và giới hạn chống stream phức tạp của parser.
- `corpus-coverage`: đối chiếu raw/metadata/page hashes, không tính bản dịch thành
  kỳ mới, giữ issuer chưa có và mẫu lỗi. Curation chỉ áp đúng phiên bản/hash đã
  xem, xuất snapshot mới, không thay raw hoặc xóa ca khỏi denominator.
- Dashboard dùng version IDs của snapshot hoàn tất, không bị registry đang nạp
  làm mất view hiện hành. Bảng coverage chỉ nhận report có đúng hash summary;
  thêm bảng doanh nghiệp × năm và cảnh báo text bị bỏ qua tại trang nguồn.

## Lệnh trên máy đã có môi trường

```powershell
# Tải từ các URL đã cấu hình; không tải lại 11 version local hiện có.
.\run.ps1 pilot-data --sources configs/corpus_sources_v0_2.json --skip-registered

# Chỉ đọc snapshot đang có, không network; ghi cảnh báo parser theo trang.
.\run.ps1 pilot-data --sources configs/corpus_sources_v0_2.json --extract-existing

# Ví dụ xuất một bản mới vào outputs; không ghi đè metadata release đã lưu.
.\run.ps1 corpus-coverage `
  --summary outputs/milestone-1/data-pilot/20261017-corpus-v0.2-parser-qa/summary.json `
  --universe configs/universe_v0_2.json `
  --curation data/corpus/v0.2/curation.json `
  --curated-output outputs/corpus-local-review/pages `
  --output outputs/corpus-local-review/metadata
```

Ví dụ cuối dùng tên output chưa tồn tại; đổi tên khi chạy lại. Máy khác cần giữ
raw blobs/registry/outputs riêng hoặc thu thập lại. URL hiện tại không bảo đảm bytes
còn như snapshot; rule curation pin hash sẽ từ chối áp lên bytes khác, cần review
phiên bản mới. Không hard-code thời điểm công bố từ filename hoặc năm báo cáo.

Lượt acquisition đầu có 30 tài liệu parser mở được/4 thất bại. Sau kiểm tra PDF
trực tiếp, file trắng GAS 2024 bị loại, còn 29 tài liệu; raw/manifest/lượt đầu vẫn
được giữ. Bản curated giữ 5 ca cấu hình không dùng được và 4 ô chưa cấu hình,
thành 9/30 ô năm còn thiếu. Chưa làm OCR hoặc coi parser fallback là thành công.

Mốc này bổ sung dữ liệu và công cụ kiểm chứng, chưa hoàn tất quant engine,
hybrid/graph/peer/agent hierarchy, risk/memory, gold, nhãn dự báo hoặc backtest.

Kiểm tra cuối: 216 tests local pass, Ruff/Python lock pass; frontend build và
Prettier pass. Đã đối chiếu 11 registry metadata hashes cùng toàn bộ 905 page
text hashes của v0.1: giữ nguyên. Git chuẩn hóa line ending của JSON index nhưng
không thay nội dung metadata. GitHub Actions chưa xác nhận qua API; không dùng
kết quả local để tuyên bố CI đã thành công.
