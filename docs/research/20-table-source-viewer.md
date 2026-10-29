# 20 — Mở rộng bảng và đối chiếu nguồn trên giao diện

Ngày: 25/10/2026. Đã nối lớp bằng chứng theo ô vào FastAPI + React. Người dùng
có thể đọc bảng mới hoặc mở lượt đã lưu, chọn ô để xem vùng chỉ tiêu, giá trị,
năm, đơn vị và phạm vi trên ảnh PDF. **Chưa có số liệu được xác nhận độc lập**.

## Thay đổi

Extractor `pdf_word_cells_v0.5` nằm trong
[pdf_tables_v05.py](../../src/pit_haf/data/pdf_tables_v05.py). Phiên bản này
nhận tiêu đề nhiều năm khi có ít nhất ba hàng số căn cột lặp lại và một đơn vị
tiền tệ trong vùng tiêu đề. Cột số được nhận diện từ các cạnh phải lặp lại,
giúp xử lý năm căn giữa thay vì buộc số phải căn đúng mép phải của chữ năm.

Vùng tên dòng được tách khỏi sidebar và bảng bên cạnh. Nhãn xuống dòng có thể
được gắn thêm phần tiếp nối chữ thường, giữ locator từng phần và cờ cần duyệt.
Không biến hàng tái dựng thành quote nguyên văn. Bảng tỷ số thiếu đơn vị tiền
tệ bị dừng. Đây vẫn là heuristic; chưa hỗ trợ OCR, ô gộp, đồ thị hay mọi nhãn
nhiều dòng.

Khi truy xuất mục tài chính không có kết quả, riêng profile v0.5 thử lại bằng
từ khóa với cùng doanh nghiệp, kỳ và PiT allowlist. Không đổi sang doanh nghiệp
hoặc kỳ khác. Cả bước fallback được lưu vào trace; strict allowlist rỗng thì
không fallback hoặc đọc raw PDF.

Extractor/profile v0.4, prompt/schema chọn mã dài và selector mã ngắn cũ vẫn
được giữ cho replay. CLI cũ mặc định v0.4; thêm `--profile table_cells_v0.5`
để thử bản mới. Luồng báo cáo một agent/trích quote cũ chưa đổi mặc định.

## Dùng trên giao diện

Mở [Phân tích tài liệu](http://localhost:8501/#analysis), tìm mục **Đối chiếu ô
bảng với PDF** ngay dưới báo cáo doanh nghiệp.

1. Chọn doanh nghiệp và nhập câu hỏi có năm duy nhất ở phía trên, hoặc chọn
   kỳ năm tại bộ lọc báo cáo. Phần bảng chỉ hỗ trợ năm, chưa hỗ trợ câu hỏi quý.
2. Bấm **Đọc bảng cho câu hỏi đang nhập**. Mặc định không gọi AI. Nếu bật **Nhờ
   AI chọn tối đa 3 ô liên quan**, chạy đúng một generation local, không retry.
3. Có thể chọn **Lượt đọc bảng đã lưu → Mở kết quả đọc bảng** để xem lại mà
   không inference. Lượt lỗi/không có context vẫn có trong lịch sử.
4. Chọn một chỉ tiêu, rồi bấm **Giá trị / Cột năm / Đơn vị / Phạm vi** để thay
   vùng tô trên PDF. **Phóng to trang** giúp xem chữ nhỏ; **Mở PDF** mở raw nguồn.

Khi mở run, backend kiểm checksum artifact và replay bảng từ raw PDF trước
khi trả locator. Ảnh render từ đúng raw hash/trang, dùng cùng kích thước trang
với tọa độ từ. API không cho nhập đường dẫn file tùy ý. Thao tác xem không tạo
review hoặc tự chuyển ứng viên thành facts đã duyệt. Màn hình xác nhận nhãn
ngữ nghĩa theo ô vẫn là bước tiếp theo.

Nguồn mã: [TableEvidence.jsx](../../frontend/src/TableEvidence.jsx),
[table_views.py](../../src/pit_haf/research/table_views.py),
[API](../../src/pit_haf/ui/api.py). Endpoint:

- `GET /api/research/table-evidence`: lịch sử, lọc doanh nghiệp tùy chọn.
- `POST /api/research/table-evidence`: đọc bảng, mặc định `use_model=false`,
  `profile_id=table_cells_v0.5`, dùng cùng khóa tác vụ với các luồng gọi model.
- `GET /api/research/table-evidence/<run_id>`: replay và mở dữ liệu đối chiếu.
- `GET /api/research/table-evidence/<run_id>/pages/<index>/image`: ảnh trang nguồn.

## Lượt thử phát triển thật

Study đầu `20261025T160453Z-4b798bb3` chọn trước bảy mã. Sau khi xử lý bốn mã,
kiểm tra Ollama của BID gặp `WinError 10013` do quyền socket trong sandbox.
Run lỗi được giữ, `llm_calls=0`; không gọi đó là model từ chối hay dịch vụ tắt.
Study tiếp `20261025T162300Z-3506bd35` ghi rõ lý do, xử lý BID/MWG/VNM với quyền
loopback. Có đúng **hai generation mới** cho BID và VNM, cùng digest Qwen3:4b
`359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`.

| Mã | Ô trích trên các trang, gồm nhiều năm | Ô trong context 2024 | Kết quả mô tả |
|---|---:|---:|---|
| FPT | 55 | 6 | Trích xuất, không inference |
| HPG | 78 | 7 | Trích xuất, chưa có phạm vi đầy đủ |
| VCB | 70 | 11 | Trích xuất, thêm nhãn nhiều dòng; còn ô lệch cột bị bỏ |
| ACB | 18 | 1 | Fallback tìm được ô cam kết ngoại bảng, sai chủ đề lợi nhuận |
| BID | 78 | 12 | AI chọn 3 ID hợp lệ; giữ cả lượt kiểm tra dịch vụ lỗi trước đó |
| MWG | 0 | 0 | Vẫn không có context bảng sau fallback cùng scope |
| VNM | 50 | 7 | AI chọn 3 ID hợp lệ; có nhãn lặp giữa hai vùng bảng |

Bảng dùng run mới nhất mỗi mã để mô tả độ phủ; toàn bộ tám run study được giữ
trong metadata. Không gộp số ô thành bộ facts, không gọi ACB là trả lời thành
công và không dùng số ID hợp lệ để tính accuracy. Hai lựa chọn cùng nhãn của
VNM chưa được gộp trùng hay đánh giá độc lập. Bộ truy xuất còn đưa chỉ tiêu
không liên quan vào context, nên vẫn cần xử lý độ liên quan và đầy đủ câu trả lời.

Một run chỉ trích xuất qua nút frontend cũng được lưu riêng:
`20261025T163954Z-974ed34b` (BID, 0 generation). UI đã kiểm tra mở run, chọn ô,
đổi vùng tô và ảnh nguồn; không tạo đáp án người duyệt.

## Kiểm tra

**363 test offline đạt**, Ruff và frontend build đạt. Có hai cảnh báo
deprecation TestClient/AnyIO và hai cảnh báo `use client` của lucide đã biết.
Các test mới kiểm tiêu đề không có prefix, năm căn giữa, nhãn xuống dòng,
sidebar, hai bảng lệch độ cao, thiếu đơn vị, dữ liệu giả sửa sau khi seal,
ảnh trang/bounds, mặc định không gọi model và chặn POST từ origin khác.

Replay **18 run** của hai study v0.4 và hai study v0.5 đạt, gồm cả lượt lỗi
kiểm tra model trước generation. Đây là kiểm tra tái lập/hash, không phải 18
lượt trả lời thành công. Replay bản đối chiếu 24 câu gốc đạt; case pack, batch
và audit đã công bố không bị sửa. Vẫn 0/24 đáp án được người dùng xác nhận độc
lập; không có semantic accuracy, backtest hoặc Full PiT-HAF để công bố.

## Chạy bằng CLI

```powershell
.\run.ps1 table-evidence --ticker BID --query "lợi nhuận năm 2024" --profile table_cells_v0.5
.\run.ps1 table-evidence --ticker BID --query "lợi nhuận năm 2024" --profile table_cells_v0.5 --model
.\run.ps1 table-evidence --replay outputs/table-evidence/20261025T162303Z-a21ab94f
```

Sau khi cập nhật mã, build frontend và khởi động lại backend theo README.
Metadata tại [data card v0.5](../../data/development/table-v0.5/DATA_CARD.md)
và [validation](../../data/development/table-v0.5/validation.json). Raw PDF,
bảng/word boxes, context và request/response vẫn ở `outputs/table-evidence/`
và `data/cache/evidence/`, không đẩy dataset lên Git. Artifact mới của mốc này
chưa upload lên Drive hoặc GitHub.

Bước tiếp theo là lọc ô đúng chủ đề, xử lý chỉ tiêu trùng/cùng tên khác phạm vi,
thiết kế xác nhận nhãn theo ô và đánh giá độc lập trước khi khóa cấu hình.
