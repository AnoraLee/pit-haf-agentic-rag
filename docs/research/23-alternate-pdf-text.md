# 23 — Lớp chữ PDF thay thế cho truy xuất bảng

Ngày: 29/10/2026. Profile thử nghiệm `table_cells_v0.7` đọc lại văn bản raw PDF
bằng pdfplumber trước khi xếp hạng mục tài chính. Corpus, metadata khả dụng,
case pack, các batch và audit đã công bố được giữ nguyên. Chưa thay mặc định
v0.6 hoặc gán nhãn độc lập cho ứng viên mới.

## Vấn đề và thay đổi

Chẩn đoán local phát hiện văn bản ACB 2024 từ bộ trích xuất cũ có ký hiệu như
`/uni1EE3`, làm cụm chỉ tiêu không khớp truy xuất. Đọc lại bằng pdfplumber cho
141/142 trang có chữ. MWG 2024 vẫn có 0/96 trang có chữ; đổi parser không thay
thế OCR. Các số đếm này là kiểm tra lớp chữ, không phải chất lượng số liệu.

[pdf_text.py](../../src/pit_haf/data/pdf_text.py) cung cấp lớp đọc thay thế,
chỉ dùng khi bật v0.7. Vẫn áp dụng đúng doanh nghiệp/kỳ và PiT allowlist trước
khi đọc raw PDF hoặc tính thống kê. Allowlist rỗng không chạm raw nguồn. Mỗi
PDF được xác minh content hash; parser giữ văn bản nó đọc được, không thay
glyph bằng heuristic hoặc bổ sung chữ bằng LLM.

Chỉ sau khi lọc metadata mới kiểm tổng số trang; vượt 400 trang thì dừng trước
khi đọc lại. Trong khi đọc vẫn kiểm số trang thực tế để metadata không nâng
ngân sách. Không tự chọn lại tài liệu hoặc tăng ngân sách sau khi thấy lỗi.
Câu hỏi ngoài topic được hỗ trợ dừng, không lấy lớp chữ cũ rồi gắn nhãn mới.

Xếp hạng dùng nguyên quy tắc `financial_sections_v0.3`. Locator/geometry vẫn
là `pdf_word_cells_v0.5`; lọc, gộp và chặn mâu thuẫn dùng policy v0.6. Ngân
sách model vẫn ba trang, 18 ô, 9.000 ký tự, một generation tối đa, không retry.
**Có thêm ngân sách đọc lại tối đa 400 trang** nên không gọi là cùng chi phí
truy xuất với v0.6. Lượt đọc lại trên báo cáo dài có thể chậm.

Run v0.7 lưu `selected-text-pages.json`, hash cấu hình lớp chữ, thống kê trang
có/không có chữ và trace xếp hạng. Replay đối chiếu văn bản các trang được chọn
trực tiếp từ raw PDF, bên cạnh replay word boxes/context như trước. Không cần
cache văn bản có thể bị sửa. Replay chưa tái tính toàn bộ xếp hạng mọi trang;
không dùng nó như bằng chứng recall hoặc semantic accuracy.

Nguồn mã: [truy xuất](../../src/pit_haf/data/financial_sections.py),
[runner/replay](../../src/pit_haf/research/table_evidence.py),
[cấu hình lớp chữ](../../configs/pdf_text_v0_7.json),
[cấu hình bảng](../../configs/table_evidence_v0_7.json).

## Bảy lượt phát triển đã định trước

Study `20261029T015054Z-2b5a187a` dùng cùng câu hỏi lợi nhuận tổng quát trên bảy
mã như mốc v0.6, cho phép **0 generation mới**. Đây là development đã quan sát,
không phải tập test khóa trước. Không retry hoặc thay kết quả thất bại.

| Mã | Context v0.6 | Context v0.7 | Kết quả |
|---|---:|---:|---|
| FPT | 6 | — | Dừng trước khi tạo run do tổng trang vượt 400; lỗi giữ trong study manifest |
| HPG | 7 | 7 | Trích xuất, chưa duyệt |
| VCB | 3 | 0 | Chọn sang trang 105, không có ô phù hợp; hồi quy cần xử lý |
| ACB | 0 | 2 | Chọn trang 64, có ứng viên trước/sau thuế hợp nhất chưa duyệt |
| BID | 4 | 4 | Trích xuất, chưa duyệt |
| MWG | 0 | 0 | Không có lớp chữ; chưa OCR |
| VNM | 4 | 4 | Trích xuất, chưa duyệt |

ACB trích 64 ô trên trang đã chọn, rồi lọc còn hai ô context 2024; số ô không
phải số facts đã xác nhận. Đã xem ảnh trang 64 để kiểm bố cục hàng/cột, năm,
đơn vị và phạm vi, nhưng không lưu xác nhận dưới tên người dùng. Việc đọc lại
làm thay đổi thứ tự văn bản và trang xếp hạng, nên kết quả VCB bị giữ lại như
một hồi quy, không lấy v0.6 thay vào cột v0.7 để cải thiện bảng kết quả.

Sáu lượt có raw run đều replay đạt; FPT chỉ có bản ghi lỗi trong manifest,
không tính vào mẫu replay. Toàn bộ 28 run study cũ và sáu run mới (34 tổng)
replay đạt. Trong 28 run cũ có lỗi trước generation: replay đạt nghĩa toàn vẹn/
tái lập, không phải 34 câu trả lời thành công. Case/batch/source audit gốc và
manifest 28 run cũ giữ nguyên hash. Đối chiếu 24 câu vẫn 8 sufficient,
12 partial, 4 insufficient, chưa là gold độc lập.

## Sử dụng

Trên [Phân tích tài liệu](http://localhost:8501/#analysis), bật **Đọc lại lớp
chữ PDF · thử nghiệm** trước khi đọc bảng mới. Tùy chọn này mặc định tắt và
độc lập với **Nhờ AI chọn tối đa 3 ô**. Mở lịch sử không gọi lại model.

```powershell
.\run.ps1 table-evidence --ticker ACB --query "lợi nhuận năm 2024" --profile table_cells_v0.7
.\run.ps1 table-evidence --replay outputs/table-evidence/20261029T015441Z-6e5bad84
```

API chấp nhận `profile_id=table_cells_v0.7`; mặc định vẫn v0.6,
`use_model=false`. Chưa bật lại lớp chữ cho luồng báo cáo quote tự do. Luồng
duyệt từng vị trí và lịch sử vẫn dùng nguồn đã replay của run đang mở.

## Kiểm tra và giới hạn còn lại

426 kiểm thử đạt, lint/format và frontend build đạt. Thêm kiểm tra nguồn/kỳ/
allowlist trước đọc PDF, giới hạn trang, PDF không có chữ, hash/offset lớp chữ
và sửa văn bản kèm hash giả vẫn bị raw replay chặn. Hai cảnh báo TestClient/
AnyIO và hai cảnh báo lucide đã biết vẫn còn.

Lượt test toàn bộ đầu tiên phát hiện guard đường dẫn Windows có race khi hai
writer cùng tạo file đánh giá lần đầu. Đã tránh resolve một leaf còn thiếu
trong lúc file được tạo, vẫn kiểm parent và symlink; bốn lượt kiểm thử đồng
thời đều đạt trong suite cuối. Không bỏ qua lỗi hoặc nới điều kiện lưu đánh giá.

Metadata nhỏ tại [data card v0.7](../../data/development/table-v0.7/DATA_CARD.md).
Raw PDF, lớp chữ từng trang, output, ảnh kiểm tra và request/response vẫn ngoài
Git; cần gói dữ liệu riêng để mở lịch sử/replay trên máy khác. Chưa upload
artifact mới lên Drive. Không có nhãn người dùng, semantic accuracy, cohort
PiT strict, backtest hay kết quả Full PiT-HAF mới để công bố.

Ưu tiên tiếp theo: sửa chọn trang gây hồi quy, xây nhánh OCR có kiểm chứng cho
nguồn không có chữ, và thu thập nhãn theo rubric trước khi khóa cấu hình.
