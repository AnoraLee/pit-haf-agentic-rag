# Hồ sơ nghiên cứu PiT-HAF

Cập nhật: 23/10/2026. Đây là đặc tả và kế hoạch phát triển toàn bộ đề tài,
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

Tài liệu trong thư mục này là protocol đang phát triển. Ghi chú đọc paper
03/09/2026 và bản dịch trong `docs/translations/` là tài liệu tham khảo; dữ liệu,
quy tắc Mỹ và số liệu paper không trở thành protocol/kết quả Việt Nam của đề tài.

Trường, giảng viên, mẫu luận văn, deadline cụ thể, số giờ làm mỗi tuần và ngân sách
tài nguyên bổ sung: **chưa xác định**. Chưa có run dự báo, backtest hoặc bảng kết
quả nghiên cứu. Mọi ngưỡng pilot trong hồ sơ là đề xuất để phát triển, chưa phải
đăng ký thực nghiệm cuối. Thay đổi protocol phải có version/changelog trước khi
mở test; không chọn lại theo kết quả thuận lợi.
