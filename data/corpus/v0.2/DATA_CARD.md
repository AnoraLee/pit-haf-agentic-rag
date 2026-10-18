# Development corpus v0.2 — 17/10/2026

Corpus dùng cho phát triển truy xuất và kiểm tra nguồn. Chưa là dataset đánh giá
dự báo/backtest, không dùng để huấn luyện LLM. Giữ nguyên pilot v0.1, 24 đoạn
trích thử và mọi kết quả inference trước đó.

## Quy mô và mẫu số

- Manifest `configs/corpus_sources_v0_2.json`: 34 URL tài liệu được chọn; mục tiêu
  38 tài liệu gồm 30 ô doanh nghiệp × năm 2022–2024 và 8 tài liệu khác/bản dịch
  từ pilot. Bản dịch không tạo thêm một ô năm hoặc sự kiện độc lập.
- 32 phiên bản PDF đã lưu; 29 tài liệu qua parser và curation được đưa lên UI.
  3.243 trang PDF vật lý, 2.950 có lớp văn bản, 293 không text/chưa OCR.
- 10 mã: ACB, FPT, GAS, HPG, MWG, PNJ, REE, SSI, VCB, VNM; 8 nhóm kinh doanh
  gán thủ công. Không phải phân loại chỉ số chính thức hoặc universe lịch sử.
- Phủ 21/30 ô báo cáo thường niên mục tiêu. Còn thiếu 9 ô, hiển thị đầy đủ
  trong `coverage.json`; không lấp bằng bản dịch, chương báo cáo hoặc snippet.
- Strict Point-in-Time: **0 tài liệu đủ điều kiện**. Ngày trên listing là dữ
  liệu quan sát hiện tại; không chứng minh thời điểm và đúng bytes của quá khứ.

| Mã | Tài liệu trong corpus | Trang PDF | Có text |
|---|---:|---:|---:|
| ACB | 1 | 142 | 141 |
| FPT | 5 | 782 | 734 |
| GAS | 2 | 184 | 184 |
| HPG | 9 | 633 | 497 |
| MWG | 2 | 193 | 97 |
| PNJ | 2 | 228 | 225 |
| REE | 3 | 398 | 392 |
| SSI | 1 | 129 | 127 |
| VCB | 1 | 106 | 106 |
| VNM | 3 | 448 | 447 |

Số liệu theo issuer trong `coverage.json` là bản kiểm chứng; bảng trên cần đối
chiếu với artifact khi thay release. Tài liệu nguồn có nhiều trang in trên cùng
một trang PDF: số trang ở đây không phải nhãn trang in trong báo cáo.

## Các ca còn thiếu và chất lượng

5/34 tài liệu cấu hình không vào corpus đang dùng:

1. SSI 2022/2023 vượt giới hạn tải 64 MiB. Không tăng giới hạn ngầm; hai ca
   chưa đăng ký raw version, acquisition error còn trong ledger/lượt đầu.
2. PNJ 2022 bị giới hạn số token trong stream của pypdf; renderer độc lập đọc
   được cấu trúc 125 trang và render trang bìa, nhưng chưa phục hồi extraction.
   Không gọi là PDF không có nội dung.
3. MWG 2022 lỗi xref ở pypdf; PDFium cũng không mở được bytes đã tải. Giữ raw
   và lỗi, chưa sửa/đổi parser để coi như thành công.
4. Link GAS 2024 hiện trả một trang trắng. Đã render và kiểm tra trực tiếp;
   `curation.json` loại đúng `version_id` + raw SHA-256, không sửa registry hoặc
   xóa bản gốc. Không đếm file trắng thành một báo cáo thường niên hoàn chỉnh.

4 ô chưa có URL đầy đủ được đưa vào manifest: ACB 2022/2023 và VCB 2022/2023.
Ứng viên VIC gặp HTTP 403 ở listing, được ghi trong discovery index; không bypass.
Lựa chọn theo khả năng truy cập có selection bias; chưa xác minh delisting hoặc
membership lịch sử, chưa xử lý survivorship bias.

13 tài liệu có cảnh báo parser, phần lớn về xref được thư viện xử lý. Riêng
FPT 2022 trang PDF 27 chạm giới hạn form XObject và có thể mất một phần text.
UI hiển thị cảnh báo tại trang này; không coi `text_present` là bằng chứng text
đầy đủ/đúng. Chưa OCR, chưa QA số/bảng/ngữ nghĩa trên toàn corpus. Spot-check do
trợ lý thực hiện không phải gold do người chấm độc lập.

## Provenance và các file

- `snapshot_index.json`: 29 versions được chọn, URL, raw/metadata hashes,
  cảnh báo trích xuất và thời gian quan sát; không chứa raw PDF hoặc text toàn bộ.
- `discovery_index.json`: URL mới cùng hash listing dùng để phát hiện; MWG và
  ACB có locator PDF được tìm qua chỉ mục công khai của domain/CDN chính thức,
  không coi kết quả search là bằng chứng ngày công bố.
- `coverage.json`: mẫu số, gaps, ngành gán thủ công, failures, eligibility và
  hash summary/universe tương ứng với snapshot được UI dùng.
- `curation.json`: một quyết định loại bytes cụ thể, reviewer là kiểm tra
  phát triển của trợ lý, không giả danh independent human annotation.
- Raw blobs/SQLite: `data/cache/evidence/`; các lượt acquisition, parser QA và
  curated pages ở `outputs/milestone-1/data-pilot/20261017-corpus-v0.2*`.
  Hash và raw của v0.1 giữ nguyên; local reuse không kiểm tra remote revision mới.

## Quyền sử dụng và tái lập

Nguồn là trang IR/domain/CDN của doanh nghiệp; public URL không phải giấy phép
phân phối. Chính sách/robots được lưu ở lượt acquisition. Raw PDF/text và outputs
không push GitHub. Quyền tái phân phối của nguồn mới chưa xác lập; giữ attribution
và chỉ kiểm tra tại máy. Không gọi corpus này là dataset đã được cấp phép mở.

Chạy `pilot-data` với manifest v0.2 để tải, `--skip-registered` để tái dùng đúng
một version local mà không kiểm lại remote; `--extract-existing` replay offline.
`corpus-coverage` kiểm checksum, áp curation vào một snapshot mới và export
metadata, không ghi đè snapshot hoặc raw cũ. Xem hướng dẫn trong báo cáo 10.

Các bước tiếp theo: bù gaps; parser/OCR và numeric QA; thu thập proof lịch sử;
gold độc lập/splits; giá, lịch giao dịch và nhãn 5 phiên. Không chốt chất lượng
mô hình từ số tài liệu hoặc từ kết quả 24 đoạn pilot cũ.
