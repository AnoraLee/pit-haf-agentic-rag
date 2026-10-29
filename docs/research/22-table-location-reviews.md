# 22 — Duyệt từng vị trí bằng chứng bảng

Ngày: 26/10/2026. Bổ sung biểu mẫu duyệt vào phần đối chiếu PDF và API lưu lịch
sử `table_location_reviews_v0.1`. Người dùng có thể ghi xác nhận, loại bỏ,
yêu cầu thêm ngữ cảnh hoặc rút xác nhận. **Chưa gán nhãn cho dữ liệu KLTN thật**.

## Cách sử dụng

Tại [Phân tích tài liệu](http://localhost:8501/#analysis), mở một lượt đọc bảng,
chọn ô và vị trí nguồn cần kiểm tra. Biểu mẫu **Duyệt vị trí nguồn đang chọn**
nằm dưới các nút Chỉ tiêu/Giá trị/Cột năm/Đơn vị/Phạm vi.

1. Đọc PDF và từng vùng nguồn, ghi tên hoặc ký hiệu người duyệt.
2. Chọn kết luận. Với **Đã xác nhận vị trí này**, tự ghi ý nghĩa chỉ tiêu và
   đánh dấu đã đối chiếu tên chỉ tiêu, chuỗi số/dấu âm, năm, đơn vị và phạm vi.
3. Xác nhận đã trực tiếp đọc vị trí nguồn rồi bấm **Lưu đánh giá vị trí này**.
   Kết luận không phù hợp/cần ngữ cảnh phải có lý do. Nút lưu chỉ bật khi đủ
   dữ liệu; backend kiểm tra lại toàn bộ điều kiện.
4. **Tải lại đánh giá** để đọc bản mới nhất; **Lịch sử vị trí này** giữ các
   phiên bản cũ. Chọn **Chưa duyệt / đã rút xác nhận** và lưu để rút kết luận
   hiện hành mà không xóa lịch sử.
5. **Tải lịch sử duyệt JSON** xuất toàn bộ vị trí và revision của lượt đọc
   bảng. Chưa có chức năng import JSON.

Năm, đơn vị và phạm vi dùng đúng giá trị chuẩn hóa của locator đang xem;
không sửa chuỗi số gốc. Nếu locator đơn vị/phạm vi thiếu, hoặc ô thuộc nhóm
cùng chỉ tiêu nhưng khác số, chưa được xác nhận: ghi cần thêm ngữ cảnh hoặc
loại bỏ. Chưa có luồng bổ sung locator thủ công để giải quyết các trường hợp
này. Chỉ tiêu diễn giải là kết luận tự khai báo, chưa được phần mềm xác minh
ngữ nghĩa.

Xác nhận gắn với **run + candidate + source cell**, nên duyệt một vị trí không
duyệt các vị trí cùng nhóm. Chuyển vị trí/ô sẽ mở biểu mẫu riêng; dữ liệu đang
nhập chưa lưu không được chuyển theo. Sau mỗi lần lưu, các dấu đối chiếu và
tuyên bố được bỏ chọn để lần sửa tiếp theo cần xác nhận lại.

## Lưu trữ và toàn vẹn

[table_reviews.py](../../src/pit_haf/research/table_reviews.py) lưu trong
`outputs/table-reviews/reviews.sqlite3`. Chỉ thao tác lưu mới tạo database;
mở lịch sử chưa duyệt không tạo nhãn hay file đánh giá. API chỉ thêm sự kiện,
không cập nhật/xóa revision cũ. SQLite dùng transaction `BEGIN IMMEDIATE` và
so `previous_revision`: hai cửa sổ cùng lưu từ một bản cũ thì chỉ một bản
thành công, cửa sổ còn lại nhận 409 và phải tải lại.

Mỗi sự kiện có timestamp UTC, người duyệt tự khai báo, kết luận, năm mục đã
đối chiếu, diễn giải, lý do, revision trước và SHA-256 của payload chuẩn hóa.
Binding ghim checksum manifest của lượt gốc, phiên bản/hash PDF, extractor,
trang và toàn bộ trường locator của vị trí đang duyệt. Trước khi mở/lưu/export,
backend kiểm run từ raw PDF và kiểm lại hash/binding/chuỗi revision của lịch sử.

Các hash hỗ trợ phát hiện hỏng hoặc sửa sai dữ liệu, không phải chữ ký người
duyệt. Chưa xác thực danh tính hay tính độc lập; người có quyền sửa toàn bộ
database có thể viết lại chuỗi, hoặc cắt đuôi lịch sử nếu không có bản đối
chiếu tin cậy. Không dùng cơ chế này để tuyên bố audit chống giả mạo tuyệt đối.

Lịch sử nằm ngoài raw run đã seal. Không sửa case pack, batch 24 câu, source
audit, context, request/response, lựa chọn model hoặc các profile v0.4–v0.6.
Các đánh giá mới không được đưa ngược vào prompt, không thay `human_reviewed_facts`
trong run gốc và không được dùng tính semantic accuracy. Số xác nhận local được
trả riêng qua `reviews.declared_confirmed_locations`; `independent_gold=false`.

Nguồn mã giao diện: [TableReview.jsx](../../frontend/src/TableReview.jsx),
[TableEvidence.jsx](../../frontend/src/TableEvidence.jsx). API:

- `GET /api/research/table-evidence/<run_id>`: thêm `reviews` vào view đã replay.
- `POST /api/research/table-evidence/<run_id>/reviews`: lưu revision, kiểm body
  chặt và cùng origin local; không gọi model.
- `GET /api/research/table-evidence/<run_id>/reviews/export`: xuất JSON có
  binding và lịch sử, không gọi model.

Khôi phục trên máy khác cần raw run/PDF và database đánh giá. Dừng backend
trước khi sao chép database, hoặc dùng SQLite backup nếu ứng dụng đang chạy.
File JSON xuất hiện chỉ để lưu trữ/đối chiếu, chưa thay thế database cho việc
khôi phục. Thư mục outputs tiếp tục bị Git ignore; chưa upload Drive/push GitHub.

## Kiểm chứng

**409 kiểm thử phần mềm đạt**, tăng 19 trường hợp từ mốc trước. Ruff và
frontend build đạt. Hai cảnh báo TestClient/AnyIO và hai cảnh báo bundler
lucide đã biết vẫn còn. Kiểm thử mới dùng hoàn toàn nguồn/nhãn giả, gồm:

- Chặn thiếu tuyên bố/năm mục, sai năm/đơn vị/phạm vi, thiếu lý do, vị trí không
  tồn tại và body cố thêm số thay thế.
- Duyệt một vị trí không lan sang nhóm; rút xác nhận giữ lịch sử và nguyên byte
  artifact gốc; thiếu nguồn hoặc mâu thuẫn chỉ cho kết luận cần ngữ cảnh/loại bỏ.
- Hai yêu cầu lưu đồng thời tạo một revision và một conflict; bản cũ không ghi đè.
- Sửa payload, bỏ revision đầu hoặc tách binding khỏi nguồn đều bị phát hiện;
  chặn POST từ origin khác và export thất bại khi raw run không còn toàn vẹn.

Đã kiểm giao diện bằng fixture riêng tại `outputs/ui-review-fixtures/`, cổng
8503: xác nhận một vị trí giả, tải lại, kiểm vị trí trùng chưa được duyệt rồi
rút xác nhận, giữ hai revision. Fixture ghi rõ “Synthetic UI QA only”,
`llm_calls=0`; không trộn database này với đánh giá thật ở cổng 8501.
Trên nguồn thật chỉ mở biểu mẫu, không lưu xác nhận.

Chưa có nhãn người dùng trên dữ liệu thật, semantic accuracy, cohort PiT strict,
backtest hay kết quả Full PiT-HAF mới. Bước kế tiếp là mở rộng ngữ cảnh/locator
còn thiếu, thu thập nhãn độc lập theo rubric, xác định split và khóa cấu hình
trước thực nghiệm định lượng.
