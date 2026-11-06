# Hồ sơ nghiên cứu PiT-HAF

Cập nhật: 06/11/2026. Đây là đặc tả và kế hoạch phát triển toàn bộ đề tài,
không phải tuyên bố hệ thống đã hoàn thành hoặc đã có kết quả khoa học.

| Hồ sơ | Nội dung |
|---|---|
| [00 — Audit](00-audit.md) | Hiện trạng trước khi sửa, bằng chứng, ưu tiên, phụ thuộc và nghiệm thu |
| [Đề cương Việt Nam](../de-cuong-nghien-cuu-pit-haf.md) | Phạm vi, tên đề tài, RQ và đóng góp dự kiến |
| [01 — Task và dữ liệu](01-task-protocol.md) | Mẫu, nhãn 5 phiên, timeline, provenance, quyết định còn mở |
| [02 — Literature/contribution](02-literature-contributions.md) | Paper gốc, phần kế thừa/tích hợp/đề xuất và claim chưa xác nhận |
| [03 — Kiến trúc](03-architecture.md) | Luồng, contracts, budgets, gateway, memory và threat model |
| [04 — Thực nghiệm](04-experiments-metrics.md) | Baseline, ablation, diagnostics, split, metric và rubric |
| [05 — Roadmap](05-roadmap.md) | Mốc 8–12 tuần, dependencies, pass/fail và tài nguyên |
| [06 — Feasibility/pilot](06-data-local-pilot.md) | Nguồn Việt Nam đã kiểm tra, kế hoạch thu thập và benchmark local |
| [07 — Chạy milestone 1](07-milestone-1.md) | Lệnh tự chạy, kết quả kiểm chứng và câu hỏi bảo vệ |
| [08 — Local pilot](08-local-pilot-results.md) | Ollama đã cài, source snapshots/gateway và các số đo pilot thật |
| [09 — React workspace](09-react-workspace.md) | Dashboard, truy xuất BM25, luồng trích xuất local và kiểm tra trên UI |
| [10 — Corpus v0.2](10-corpus-expansion.md) | Mở rộng 10 mã, coverage theo năm, parser QA và curation có audit |
| [11 — Corpus v0.3](11-corpus-v03.md) | Mở rộng nhiều năm/quý, 13 mã, tải theo batch, retry và bộ lọc kho lớn |
| [12 — Corpus v0.4](12-news-corpus-v04.md) | Bổ sung bài báo, tin chính sách và tin doanh nghiệp; tách HTML/PDF, nguồn đăng và ngày quan sát |
| [13 — Corpus v0.5](13-large-corpus-v05.md) | Thêm 30.000 bài có join URL/ngày gốc; catalog SQLite/FTS5, phân trang server và provenance bản nhập |
| [14 — Single-agent development](14-single-agent-development.md) | Báo cáo nhiều đoạn có kiểm quote/số, 24 case chờ annotation và cấu hình phát triển chưa freeze |
| [15 — Scoped retrieval/review](15-scoped-retrieval-and-review.md) | Lọc đúng mã/kỳ trước truy xuất và màn hình chấm case có revision/hash/export, chưa có human gold |
| [16 — Development batch evaluation](16-development-batch-evaluation.md) | Chạy case trên context cố định, giữ lỗi/ABSTAIN, replay request/response và đối chiếu annotation theo vị trí/chuỗi số |
| [Đối chiếu nguồn 24 câu](development-source-audit-v0.1.md) | Đáp án trợ lý soạn từ PDF đầy đủ, tách đánh giá ngữ cảnh và kết quả gốc; chưa là nhãn độc lập |
| [17 — Tiến độ 23/10/2026](17-progress-20261023.md) | Phần đã triển khai, công việc đang làm và các bước tiếp theo, đối chiếu với artifact hiện có |
| [18 — Truy xuất mục báo cáo tài chính](18-financial-section-retrieval.md) | Profile thử nghiệm, chẩn đoán 24 câu và ba lượt Qwen bị chặn; chưa thay mặc định |
| [19 — Bằng chứng theo ô PDF](19-table-cell-evidence.md) | Locator hàng/cột/năm/đơn vị, selector mã ngắn, sáu lượt Qwen và giới hạn trên bốn mã bổ sung |
| [20 — Đối chiếu bảng trên giao diện](20-table-source-viewer.md) | Parser v0.5 cho tiêu đề/nhãn mới, ảnh PDF có vùng tô, study bảy mã và các kết quả chưa đạt |
| [21 — Chọn và gộp ô theo chỉ tiêu](21-cell-relevance-and-grouping.md) | Lọc cụm chỉ tiêu, gộp bảo thủ có giữ nguồn, chặn số mâu thuẫn và mười lượt phát triển v0.6 |
| [22 — Duyệt từng vị trí ô bảng](22-table-location-reviews.md) | Xác nhận năm phần bằng chứng, lịch sử revision, phát hiện lưu cũ và export; chưa có nhãn thật |
| [23 — Lớp chữ PDF thay thế](23-alternate-pdf-text.md) | Truy xuất từ lớp chữ đọc lại, ACB có ứng viên mới nhưng VCB hồi quy/FPT vượt ngân sách; chưa đổi mặc định |
| [24 — Chọn trang theo cột năm](24-annual-table-page-gate.md) | Nhận diện cột ngày lặp, chặn trang thiếu/sai năm, phục hồi ứng viên VCB và hiển thị đơn vị từng dòng |
| [25 — Chọn tài liệu trước khi đọc bảng](25-table-document-scope.md) | Xem metadata/ngân sách, ghim một version trong phạm vi doanh nghiệp/kỳ/PiT, hai lượt FPT và lý do dừng có link PDF |
| [26 — Đơn vị tiền tệ theo cột năm](26-table-currency-units.md) | Parser v0.9 giữ locator VND của từng cột, chặn đơn vị thiếu/mâu thuẫn và so sánh trên cohort phát triển |
| [27 — Tiến độ 29/10/2026](27-progress-20261029.md) | Phần sử dụng được, bằng chứng còn thiếu và thứ tự từ cohort/OCR đến backtest, Full PiT-HAF và khóa luận |
| [28 — OCR local có locator](28-local-ocr-preview.md) | Tùy chọn Tesseract vie/eng, worker có giới hạn, xem từng từ trên PDF, lưu lỗi và replay OCR bốn trang MWG |
| [29 — OCR vùng và đối chiếu chuỗi số](29-ocr-region-numeric-diagnostic.md) | Chọn vùng một trang, khôi phục tọa độ toàn trang, so sánh 24 chuỗi do trợ lý chép; chưa là nhãn độc lập |
| [30 — Ô OCR và ngữ cảnh nguồn](30-ocr-cell-context.md) | Liên kết số/nhãn/đơn vị, chặn năm điều hướng và số bị tách, hiển thị trường thiếu và hộp từ để đối chiếu |
| [31 — Tiêu đề OCR và nhãn nhiều dòng](31-ocr-header-spatial-links.md) | Ghép nguồn tiêu đề cùng trang, giữ số từ thân bảng, đọc kỳ tài chính/phạm vi và kiểm nhãn xuống dòng; chưa xác nhận facts |
| [32 — Phiếu đối chiếu OCR](32-ocr-source-review.md) | Bản chép có lý do sửa, năm tự nhập theo nguồn, điều kiện xác nhận, revision/conflict và export; chưa là nhãn độc lập |
| [33 — Động cơ thực thi giả lập](33-synthetic-execution-engine.md) | Lệnh trễ phiên, phí/slippage, settlement, sổ tiền/vị thế, lịch Q0/Q1 và replay; chưa có backtest thị trường |
| [34 — Snapshot giá 2021–2024](34-market-price-snapshots.md) | Raw KBS và Decimal, 2.994 bar cổ phiếu, chặn VNINDEX lỗi OHLC, replay và báo điều kiện còn thiếu; chưa chạy lợi suất |
| [35 — Đối soát VNINDEX](35-index-vendor-crosscheck.md) | KBS/Vietcap theo trường, 998 close khớp, giữ lỗi OHLC/volume và tạo comparator close-only; chưa xác nhận dữ liệu thực thi/PiT |
| [36 — Thanh toán theo thời điểm](36-timestamp-settlement.md) | Hai lịch tường minh, giờ về tiền/cổ phiếu, ranh giới open/close/decision và replay; chưa xác minh lịch HOSE/VSDC |
| [37 — Đối soát lịch thanh toán](37-settlement-calendar-audit.md) | Chín thông báo VSD/VSDC, revision, 998 ngày khớp ba mã và T+2 qua đầu năm; lịch HOSE/giờ tài khoản chưa xác minh |
| [38 — Sổ quyền nhận cổ tức/cổ phiếu](38-corporate-action-ledger.md) | Entitlement ledger giả lập, ba sự kiện có nguồn, giữ bất đồng HPG và đối chiếu một thông báo HOSE; chưa tích hợp thực thi giá thật |

Tài liệu trong thư mục này là protocol đang phát triển. Ghi chú đọc paper
03/09/2026 và bản dịch trong `docs/translations/` là tài liệu tham khảo; dữ liệu,
quy tắc Mỹ và số liệu paper không trở thành protocol/kết quả Việt Nam của đề tài.

Trường, giảng viên, mẫu luận văn, deadline cụ thể, số giờ làm mỗi tuần và ngân sách
tài nguyên bổ sung: **chưa xác định**. Chưa có run dự báo, backtest hoặc bảng kết
quả nghiên cứu. Mọi ngưỡng pilot trong hồ sơ là đề xuất để phát triển, chưa phải
đăng ký thực nghiệm cuối. Thay đổi protocol phải có version/changelog trước khi
mở test; không chọn lại theo kết quả thuận lợi.
