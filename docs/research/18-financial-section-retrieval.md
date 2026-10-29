# 18 — Truy xuất mục báo cáo tài chính, thử nghiệm v0.3

Ngày: 23/10/2026. Mốc này tiếp tục xử lý chất lượng ngữ cảnh trước khi chuyển
sang backtest. Đã thêm cách tìm mục báo cáo và bảng số liệu, nhưng **chưa chứng
minh cải thiện câu trả lời của model**. Luồng theo từ khóa vẫn là mặc định.

## Vấn đề và thay đổi

Truy xuất theo từ khóa có thể chọn trang chính sách kế toán hoặc cắt mất tiêu
đề năm, đơn vị và chỉ tiêu. Profile `financial_sections_v0.3` dùng các nhóm chủ
đề tiếng Việt, tiêu đề mục và dấu hiệu bảng để xếp hạng trang, rồi chọn các đoạn
bổ sung thông tin cho nhau. Các dòng lặp trong cùng tài liệu chỉ bị bỏ qua khi
tính điểm; ngữ cảnh gửi model giữ nguyên văn bản nguồn.

Phạm vi doanh nghiệp, kỳ báo cáo và allowlist PiT được áp dụng trước khi đọc
văn bản/thống kê trang. Năm trong tiêu đề cột giúp bỏ bảng chỉ chứa năm khác;
đây là heuristic, chưa phải parser bảng hoàn chỉnh. Mỗi đoạn giữ trang, offset
và hash, được đối chiếu lại với Catalog. Không ghép các ô thành trích dẫn mới.

Ngân sách giữ ở **3 đoạn, tối đa 700 ký tự/đoạn, tổng 2.100 ký tự**. Prompt,
JSON Schema và bộ kiểm trích dẫn/số không đổi. Trace xếp hạng được lưu riêng
cho người đánh giá, không đưa vào prompt. Runtime không đọc bản đáp án trợ lý.

Luồng hiện tại vẫn có **một agent lập báo cáo** qua một lần gọi Qwen3:4b.
Truy xuất, PiT Guard và verifier là module mã nguồn; thay đổi này chưa tạo
planner, các agent chuyên môn hoặc hệ phân cấp Full PiT-HAF.

## Chẩn đoán trên 24 câu

Study `20261023T133509Z-75d1ccc1` tạo ngữ cảnh riêng cho cùng câu hỏi và phạm vi
của bộ v0.2, không thay bộ đang hoạt động. Artifact giữ cấu hình, checksum,
source snapshot, 24 ngữ cảnh và trace. Các lượt thử phát triển trước đó cũng
được giữ trong `outputs/retrieval-development/`.

| Chỉ số chẩn đoán | Bộ cũ | Profile mới |
|---|---:|---:|
| Câu hỏi | 24 | 24 |
| Đoạn tham chiếu | 72 | 72 |
| Chuỗi mốc có mặt trong ngữ cảnh, trên 124 chuỗi | 56 | 103 |

20 câu tăng số chuỗi có mặt, 4 câu giữ nguyên, không có câu giảm theo phép đo
này. Đây chỉ là **kiểm tra sự xuất hiện của chuỗi** lấy từ bản đối chiếu do trợ
lý soạn. Không suy ra mức đầy đủ bằng chứng, đúng hàng/cột, precision/recall hay
semantic accuracy. Heuristic được phát triển sau khi xem lỗi các câu này, nên
chúng không phải tập test độc lập. Một số câu về tăng trưởng/phân khúc, tài sản
và rủi ro vẫn thiếu thông tin hoặc chưa đúng trọng tâm.

## Ba lượt Qwen thật

Chọn trước câu lợi nhuận đầu tiên của FPT, HPG, VCB; mỗi câu chạy một lần,
không thay lượt lỗi bằng lượt thành công. Cùng digest model với batch cũ:
`359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`.

| Câu | Nhận định qua kiểm tra ở batch cũ | Profile mới | Nhận định mới bị chặn |
|---|---:|---|---:|
| FPT — lợi nhuận | 0 | Từ chối | 3 |
| HPG — lợi nhuận | 3 | Từ chối | 3 |
| VCB — lợi nhuận | 0 | Từ chối | 3 |

Cả ba đầu ra mới hợp lệ về schema, nhưng không có nhận định được chấp nhận.
FPT gặp quote mơ hồ hoặc phát biểu chứa năm ngoài câu trích. HPG đọc sai quan
hệ hàng/cột từ văn bản trích xuất theo cột. VCB có câu trích khớp nhưng model
báo thiếu bằng chứng toàn cục; các phát biểu khác thêm năm ngoài quote.

Tổng lý do chặn: `numbers_not_supported_by_quote` 8,
`model_abstained` 6, `quote_not_found` 2, `quote_ambiguous` 1. Một nhận định có
thể có nhiều lý do. Ngữ cảnh có thêm chuỗi liên quan chưa đủ làm model đọc bảng
đúng. Ba lượt riêng lẻ chưa đủ xác lập chênh lệch hiệu năng; không giả định sinh
đầu ra hoàn toàn xác định, dù cùng model và cấu hình.

Các run được giữ đầy đủ:

- FPT: `20261023T134026Z-f33896ab`.
- HPG: `20261023T134116Z-c381db3a`.
- VCB: `20261023T134155Z-392396cc`.

## Chạy và kiểm tra

Trên **Phân tích tài liệu → Báo cáo doanh nghiệp**, chọn **Cách tìm bằng chứng
→ Ưu tiên mục báo cáo và bảng số liệu · thử nghiệm**. Chọn doanh nghiệp và nhập
câu hỏi trước khi lập báo cáo. API nhận trường `retrieval_profile`; bỏ trường
này sẽ dùng `lexical_v0.2`. Truy xuất nhanh ở nút **Tìm bằng chứng** vẫn dùng
luồng từ khóa hiện hành.

```powershell
# Một báo cáo mới, cần Ollama và corpus local
.\run.ps1 company-report --ticker HPG --query "lợi nhuận năm 2024" --retrieval-profile financial_sections_v0.3

# Tạo study mới, chỉ truy xuất/chẩn đoán, không gọi model
.\run.ps1 retrieval-study

# Chạy ba lượt thật trên study vừa tạo; mỗi study chỉ chạy smoke một lần
.\run.ps1 retrieval-study --smoke-study outputs/retrieval-development/<study_id>

# Kiểm tra lại 24 kết quả gốc, không inference
.\.venv312\Scripts\python.exe -X utf8 -m pit_haf.research.source_audit
```

Metadata nhỏ được lưu tại [data card v0.3](../../data/development/retrieval-v0.3/DATA_CARD.md),
[summary](../../data/development/retrieval-v0.3/summary.json),
[smoke](../../data/development/retrieval-v0.3/smoke.json) và
[validation](../../data/development/retrieval-v0.3/validation.json).
Nguồn và raw request/response vẫn ở thư mục local; chưa tải các artifact mới
này lên Drive hoặc GitHub trong mốc này.

Kiểm tra local: **345 test đạt**, Ruff đạt, frontend build đạt; có hai cảnh báo
deprecation TestClient/AnyIO và cảnh báo `use client` của lucide khi build.
Replay đối chiếu nguồn 24 câu gốc và raw request/response/verifier của cả ba
lượt mới đều đạt. UI đã kiểm tra tùy chọn mới và sửa bố cục bộ lọc để xuống dòng.
Những kiểm tra này không xác nhận đúng ngữ nghĩa tài chính. Không tạo nhãn
người duyệt; vẫn 0/24 đáp án được xác nhận độc lập.

## Bước tiếp theo

1. Trích bảng có cấu trúc hàng/cột, gắn năm, đơn vị và phạm vi với từng ô, giữ
   provenance tới vị trí nguồn. Cần kiểm tra ngoài ba tài liệu phát triển này.
2. Thiết kế bằng chứng riêng cho tiêu đề năm/đơn vị và ô số; đánh giá thay đổi
   schema/verifier bằng phiên bản mới, giữ replay của kết quả cũ.
3. Xác nhận đáp án độc lập, tách development/test và khóa cấu hình trước đánh
   giá cuối. Chỉ sau đó mới chuyển sang cohort PiT và backtest theo lộ trình.

Không đổi mặc định hoặc nới bộ kiểm chỉ để các lượt trên được chấp nhận.
Chưa có kết quả PiT strict lịch sử, dự báo, backtest hoặc ablation Full PiT-HAF.
