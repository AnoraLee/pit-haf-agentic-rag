# Chọn và gộp ô bảng v0.6 — development

Ngày: 26/10/2026 (Asia/Saigon). Run ID dùng UTC nên có tiền tố `20261025`.
Profile `table_cells_v0.6` giữ extractor, nguồn và ngân sách v0.5; bổ sung quy
tắc cụm chỉ tiêu, gộp trùng có giữ vị trí nguồn và chặn nhóm khác chuỗi số.
Cấu hình đang phát triển, chưa khóa cho thực nghiệm cuối.

- `manifest.json`: kế hoạch chọn trước mười lượt, tối đa hai generation mới,
  toàn bộ kết quả và hash bộ case/batch/audit gốc trước/sau.
- `validation.json`: số ô, trace lọc/gộp, nguồn của nhóm trùng và kiểm tra;
  không phải precision, recall hoặc accuracy.
- `integrity.json`: SHA-256 của metadata và hai cấu hình v0.6. Data card không
  nằm trong danh sách hash để có thể cập nhật mô tả mà không đổi kết quả.

Bảy câu lợi nhuận tổng quát trên FPT/HPG/VCB/ACB/BID/MWG/VNM có lần lượt
6/7/3/0/4/0/4 ô trong context, so với 6/7/11/1/12/0/7 ở v0.5. Hash các bundle
bảng gốc và danh sách nguồn khớp v0.5 ở cả bảy mã. Thay đổi nằm ở việc chọn
context, không phải thêm bảng hoặc chứng minh trích xuất đúng.

Ba câu cụ thể về lợi nhuận sau thuế FPT, trước thuế HPG và phần cổ đông ngân
hàng VCB mỗi câu còn một ô gợi ý; cả ba không gọi model. Hai generation mới
dùng cùng digest Qwen3:4b cho BID và VNM, mỗi lượt chọn ba ID hợp lệ chưa duyệt.
VNM gộp một cặp cùng nhãn/số, giữ hai vị trí ở trang 92. ACB loại ô cam kết
ngoại bảng; ACB và MWG vẫn chưa có câu trả lời lợi nhuận từ luồng bảng.

Không có nhóm mâu thuẫn thật trong mười lượt này; hành vi chặn nhóm khác số
được kiểm tra bằng dữ liệu giả. Gộp chỉ áp dụng cùng phiên bản nguồn, mã, nhãn
đầy đủ, năm, đơn vị đã biết, phạm vi quan sát đã biết và chuỗi số y hệt.
Thiếu đơn vị/phạm vi thì giữ riêng. Đây không phải xác nhận tương đương ngữ nghĩa.

390 kiểm thử đạt, Ruff/frontend build đạt; 28 run study v0.4–v0.6 replay đạt,
gồm cả lượt lỗi kiểm tra dịch vụ trước generation. Replay kiểm tra toàn vẹn
và tái lập, không đồng nghĩa 28 câu trả lời đúng. Đối chiếu 24 câu gốc replay
đạt; các artifact gốc không đổi. `human_reviewed_facts=0`,
`semantic_accuracy=null`; chưa có cohort PiT strict hoặc kết quả backtest.

Raw PDF, context, bảng/word boxes và request/response vẫn ở
`outputs/table-evidence/` và `data/cache/evidence/`, cần tải riêng để replay.
Artifact mới chưa upload Drive hoặc push GitHub trong mốc này.

Xem [hướng dẫn và giới hạn v0.6](../../../docs/research/21-cell-relevance-and-grouping.md).
