# 21 — Chọn ô đúng chỉ tiêu và gộp vị trí nguồn

Ngày: 26/10/2026 (Asia/Saigon). Profile thử nghiệm `table_cells_v0.6` sửa việc
chọn ô theo từ chung của câu hỏi, bổ sung gộp bảo thủ và hiển thị từng vị trí
nguồn trên frontend. **Chưa có nhãn ngữ nghĩa được người dùng xác nhận**.

## Cách chọn và gộp

Quy tắc trong [table_context_v0_6.json](../../configs/table_context_v0_6.json)
đối chiếu cụm chỉ tiêu đầy đủ. Từ “kết” trong câu hỏi “Kết quả lợi nhuận”
không còn làm ô “Các cam kết ngoại bảng” trở thành bằng chứng lợi nhuận.
Các nhóm được hỗ trợ gồm lợi nhuận, doanh thu/thu nhập, tài sản/nợ và tiền
theo năm. Với lợi nhuận, quy tắc phân biệt trước/sau thuế, phần công ty mẹ,
hoạt động, gộp, EBIT và EBITDA. Nhãn “Lợi nhuận thuần” có cờ cần kiểm tra
riêng khi dùng như một alias sau thuế. Đây là heuristic phát triển theo nhãn,
chưa phải bộ phân tích ngữ nghĩa tổng quát.

Câu hỏi kế hoạch, tăng trưởng, tỷ suất/biên hoặc rủi ro nằm ngoài phạm vi của
profile bảng này; luồng báo cáo doanh nghiệp vẫn có thể xử lý bằng chứng dạng
đoạn. Không điền đáp án khi không có ô phù hợp. Cấu hình không chứa lookup
theo doanh nghiệp, số trang, case hoặc đáp án tham chiếu.

Hai ô chỉ được gộp khi cùng phiên bản nguồn, mã doanh nghiệp, nhãn đầy đủ đã
chuẩn hóa, năm, đơn vị đã biết, phạm vi báo cáo quan sát đã biết và **chuỗi số
y hệt**. Thiếu đơn vị hoặc phạm vi thì giữ riêng; không gộp qua phiên bản,
công ty mẹ/con, dấu âm hay cách ghi dấu chấm/phẩy. Mỗi nhóm giữ toàn bộ
`equivalent_candidates` để truy nguyên từng ô.

Cùng khóa chỉ tiêu nhưng khác chuỗi số thì giữ các giá trị riêng và đánh dấu
`conflicting_values_same_label_requires_review`. Verifier v0.6 chặn các lựa
chọn AI thuộc nhóm đó. Khác chuỗi số có thể do định dạng hoặc ngữ cảnh mà
heuristic chưa nhận biết, nên cờ này yêu cầu kiểm tra, không khẳng định nguồn sai.

[table_context.py](../../src/pit_haf/research/table_context.py) lưu
`context-audit.json` gồm các ô bị loại, nhóm trùng, nhóm mâu thuẫn, phần vượt
ngân sách và loại câu hỏi. Trace được hash và kiểm lại khi replay; không đưa
trace chẩn đoán vào prompt. [Runner](../../src/pit_haf/research/table_evidence.py)
giữ các protocol v0.4/v0.5 để mở lại lịch sử theo đúng cấu hình ban đầu.

## Nguồn và ngân sách

V0.6 dùng nguyên extractor `pdf_word_cells_v0.5`, truy xuất
`financial_sections_v0.3` và fallback từ khóa trong cùng scope. So sánh byte/hash
cho thấy danh sách nguồn và từng bundle `table-XX.json` của bảy lượt tổng quát
khớp đúng các lượt v0.5 tương ứng. Vì vậy giảm số ô context không biểu thị
parser đã tìm thêm bảng hoặc có độ chính xác tài chính cao hơn.

Ngân sách giữ nguyên: tối đa ba trang PDF, 18 ô, 9.000 ký tự context, một
generation local, không retry; `num_ctx=4096`, `num_predict=512`. Selector mã
ngắn và schema cũ được giữ. Không so các con số này như một ablation công bằng
với luồng sinh nhận định/quote tự do, vốn có tác vụ và schema khác.

## Mười lượt phát triển thật

Study `20261025T172647Z-b5d2d252` ghi trước bảy câu lợi nhuận tổng quát và ba
câu cụ thể, cho phép tối đa hai generation mới. Run ID dùng giờ UTC. Hai lượt
Qwen3:4b cho BID/VNM dùng digest
`359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`.
Không retry hoặc thay kết quả chưa đạt.

| Mã | Ô trích, gồm nhiều năm | Context 2024 v0.5 | Context v0.6 | Generation mới |
|---|---:|---:|---:|---:|
| FPT | 55 | 6 | 6 | 0 |
| HPG | 78 | 7 | 7 | 0 |
| VCB | 70 | 11 | 3 | 0 |
| ACB | 18 | 1 | 0 | 0 |
| BID | 78 | 12 | 4 | 1 |
| MWG | 0 | 0 | 0 | 0 |
| VNM | 50 | 7 | 4 | 1 |

ACB không còn dùng ô cam kết ngoại bảng cho câu hỏi lợi nhuận, nhưng vẫn chưa
có câu trả lời phù hợp. MWG vẫn không có context bảng. BID/VNM mỗi lượt chọn
ba ID qua kiểm tra cấu trúc/nguồn; chưa đánh giá độc lập ý nghĩa hoặc tính đầy
đủ của lựa chọn. VNM gộp một cặp “Lợi nhuận thuần” cùng chuỗi số tại hai vùng
bảng của trang 92; hai vị trí nguồn được giữ. Không có nhóm khác số trong các
lượt thật này; kiểm thử chặn mâu thuẫn sử dụng dữ liệu giả.

Ba lượt chỉ trích xuất bổ sung:

| Câu hỏi | Run ID | Context |
|---|---|---:|
| FPT — Lợi nhuận sau thuế năm 2024 | `20261025T172826Z-7be64de5` | 1 ô |
| HPG — Lợi nhuận trước thuế năm 2024 | `20261025T172835Z-14785c7f` | 1 ô |
| VCB — Lợi nhuận cổ đông ngân hàng năm 2024 | `20261025T172842Z-f18d727b` | 1 ô |

Một ô gợi ý không đồng nghĩa một đáp án đúng. Các lượt này chưa gọi model,
chưa là tập held-out và chưa được dùng tính accuracy/recall.

## Dùng trên frontend và CLI

Tại [Phân tích tài liệu](http://localhost:8501/#analysis), phần **Đối chiếu ô
bảng với PDF** dùng v0.6 khi đọc mới; API cũng mặc định v0.6 và
`use_model=false`. Có thể mở lịch sử mà không gọi model. Khi chọn nhóm có
nhiều vị trí, dùng **Vị trí nguồn của nhóm ô** để đổi vùng bảng/trang, rồi chọn
**Chỉ tiêu / Giá trị / Cột năm / Đơn vị / Phạm vi** để xem locator từng phần.
Đổi vị trí nguồn không tạo nhãn hoặc thay giá trị của nhóm.

Đã kiểm tra trên giao diện thật: mở run VNM `20261025T172814Z-a7e00fe7`, chọn
nhóm hai vị trí, đổi từ vùng bảng 1 sang vùng bảng 2 cùng trang 92; tọa độ vùng
tô thay đổi đúng theo locator đã lưu. Không có lỗi console trong lượt kiểm tra.
Ảnh kiểm tra local: `outputs/ui-preview/table-context-v06-20261026.png`.

CLI vẫn mặc định v0.4 để giữ hành vi cũ. Chọn v0.6 rõ ràng:

```powershell
.\run.ps1 table-evidence --ticker BID --query "lợi nhuận năm 2024" --profile table_cells_v0.6
.\run.ps1 table-evidence --ticker BID --query "lợi nhuận năm 2024" --profile table_cells_v0.6 --model
.\run.ps1 table-evidence --replay outputs/table-evidence/20261025T172814Z-a7e00fe7
```

## Kiểm tra và giới hạn

390 kiểm thử phần mềm đạt; Ruff và frontend build đạt. Replay 28 run study
v0.4–v0.6 đạt, gồm lượt lỗi kiểm tra dịch vụ trước generation: đây là tái lập
artifact/hash, không phải 28 câu trả lời thành công. Replay đối chiếu 24 câu
gốc đạt; hash case pack, batch và audit không đổi. Hai cảnh báo deprecation
TestClient/AnyIO và hai cảnh báo `use client` của lucide vẫn như mốc trước.

Metadata tại [data card](../../data/development/table-v0.6/DATA_CARD.md),
[manifest](../../data/development/table-v0.6/manifest.json) và
[validation](../../data/development/table-v0.6/validation.json). Raw PDF,
bảng/word boxes, context và request/response ở `outputs/table-evidence/`
và `data/cache/evidence/`; chưa upload artifact mới lên Drive hoặc push GitHub.

`human_reviewed_facts=0`, `semantic_accuracy=null`. Chưa có bằng chứng đủ điều
kiện PiT strict, backtest hoặc Full PiT-HAF để công bố. Hạn chế còn lại gồm
truy xuất thiếu bảng ACB/MWG, OCR/ô gộp và nhãn ngoài tập heuristic; gộp bằng
khóa không chứng minh hai ô tương đương ngữ nghĩa. Bước tiếp theo là hoàn thiện
luồng duyệt chỉ tiêu/năm/đơn vị/phạm vi có version, rồi đánh giá độc lập và khóa
cấu hình trước khi mở rộng thực nghiệm.
