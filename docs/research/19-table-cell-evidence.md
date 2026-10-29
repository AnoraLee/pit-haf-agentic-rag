# 19 — Bằng chứng theo ô PDF, development v0.4

Ngày: 24/10/2026. Mốc này bổ sung lớp liên kết hàng/cột và một runner thử nghiệm
chọn ô bằng Qwen. **Chưa có bộ số liệu tài chính được người duyệt xác nhận**.
Luồng báo cáo/kiểm quote cũ trên frontend vẫn được giữ nguyên.

## Đã triển khai

[Bộ đọc bảng](../../src/pit_haf/data/pdf_tables.py) dùng pdfplumber 0.11.9 để
lấy từ và bounding box trên PDF gốc. Nó nhóm các từ theo hàng, tìm tiêu đề năm
và liên kết token số với cột căn phải tương ứng. Tên chỉ tiêu, giá trị, năm,
đơn vị và cụm mô tả phạm vi được lưu bằng các locator riêng. Mỗi locator có
word IDs và box; mỗi bảng gắn hash PDF, trang và phiên bản extractor.

Tọa độ dùng đơn vị PDF point, gốc trên trái. Đây là **box của từ**, không phải
offset ký tự của corpus cũ hay chứng nhận vị trí hiển thị tuyệt đối. Dữ liệu
được trích trực tiếp từ raw PDF đã kiểm hash; không biến hàng tái dựng thành
một quote nguyên văn giả. Giữ nguyên dấu âm trong ngoặc, dấu phân cách và đơn
vị nguồn; chưa đổi đơn vị hoặc tính toán số học.

Runner [table_evidence.py](../../src/pit_haf/research/table_evidence.py) áp dụng
scope doanh nghiệp/kỳ và PiT Guard trước khi đọc raw PDF. Sau đó đọc tối đa
3 trang do truy xuất v0.3 lựa chọn; lọc ứng viên theo năm và câu hỏi. Nếu thiếu
ngữ cảnh, không gọi LLM. Mốc này chỉ hỗ trợ cột năm, từ chối câu hỏi theo quý.

Ngân sách mới: tối đa 18 ô, 9.000 ký tự của danh sách ô, một lần gọi Qwen3:4b,
`num_ctx=4096`, `num_predict=512`, temperature 0, seed 42, không retry. Các giới
hạn ký tự không thay thế phép đo token. Adapter giữ raw request/response, lỗi
schema/transport và kiểm tra digest model trước/sau.

Model chỉ chọn ID; server lấy lại tên/số/năm/đơn vị từ ứng viên. Model không
được trả số mới trong nhận định. Mã nguồn kiểm ID tồn tại, trùng ID, trạng thái
từ chối và thay đổi model. Chọn ID hợp lệ vẫn có thể sai ý câu hỏi, nên mọi kết
quả đều là **ứng viên chưa duyệt**, `semantic_support=not_assessed`.

## Hai lượt thử có lưu phiên bản

Study đầu `20261024T014351Z-e0143234` lưu trước danh sách FPT/HPG/VCB chạy model
và ACB/BID/MWG/VNM chỉ trích xuất. Câu hỏi model là câu lợi nhuận 2024 của bộ
phát triển. Study giữ 3 lượt Qwen: FPT/HPG đều bị chặn hết vì model chép sai ID;
VCB có 1 ID hợp lệ và 2 ID sai. Tổng 8 ID sai bị chặn. ID hợp lệ của VCB vẫn
chưa đủ để kết luận trả lời đúng câu lợi nhuận.

Selector `short_cell_refs_v0.4.1` đổi phần model nhìn thấy sang C1…C18, giữ ánh
xạ tới ID đầy đủ trong context local. Prompt/schema chọn mã được version riêng;
replayer vẫn dùng đúng prompt/schema cũ khi đọc ba run đầu. Không sửa hash, ánh
xạ hoặc đầu ra của các run trước.

Study sau `20261024T015107Z-9bc42a6e` chạy lại đúng ba mã, mỗi mã một lần, cùng
bảng ứng viên byte-for-byte. Đây là thử nghiệm giao diện chọn ID, không phải
retry ghi đè và không phải đánh giá ngữ nghĩa độc lập.

| Doanh nghiệp | Ô trích được, gồm các năm | Ô trong ngữ cảnh 2024 | ID hợp lệ, selector dài | ID hợp lệ, selector ngắn |
|---|---:|---:|---:|---:|
| FPT | 55 | 6 | 0 | 3 |
| HPG | 69 | 7 | 0 | 3 |
| VCB | 68 | 10 | 1 | 3 |

Không có ID sai trong ba lượt mã ngắn; tổng 9 ứng viên được chọn vẫn chưa là
9 đáp án đúng. FPT ưu tiên một số biến thể lợi nhuận trước thuế, chưa bao quát
đầy đủ lợi nhuận sau thuế. HPG còn thiếu bằng chứng phạm vi báo cáo trên trang
được đọc. VCB chọn cả một chỉ tiêu liên quan đến cổ đông không kiểm soát. Các
trường hợp này cần rubric và người duyệt, không chỉ kiểm ID.

Tổng cộng **6 lần gọi model mới**, giữ cả hai study; cùng digest
`359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`.
Không suy ra semantic accuracy hoặc độ ổn định từ các lượt đơn lẻ.

## Kiểm tra thêm bốn doanh nghiệp

Đây là kiểm tra độ phủ phát triển, không gọi model và không có human gold.

| Mã | Kết quả |
|---|---|
| ACB | Có trang trong scope nhưng truy xuất v0.3 không chọn được mục tài chính phù hợp |
| BID | Chọn trang 76; parser chưa hỗ trợ mẫu tiêu đề không có STT/Chỉ tiêu |
| MWG | Có trang trong scope nhưng truy xuất v0.3 không chọn được mục tài chính phù hợp |
| VNM | Chọn trang 92 và 15; bảng lợi nhuận chưa được nhận diện, 20 ứng viên từ bảng tỷ số không tạo ngữ cảnh lợi nhuận |

Đã xem toàn trang PDF được chọn của BID/VNM để phân biệt thiếu dữ liệu với
chưa hỗ trợ bố cục. Không kết luận các doanh nghiệp này không có tài liệu hay
không có số lợi nhuận. Kết quả cho thấy chưa thể dùng parser này trên toàn rổ.

## Chạy và replay

Sau khi cập nhật mã nguồn, đồng bộ môi trường có dependency/lockfile mới:

```powershell
$env:UV_PROJECT_ENVIRONMENT = ".venv312"
uv sync --locked --dev --python 3.12

# Chỉ trích xuất và lưu bảng/locator, không gọi model
.\run.ps1 table-evidence --ticker HPG --query "lợi nhuận năm 2024"

# Thêm một lượt chọn ô bằng Qwen local; kết quả vẫn chưa duyệt
.\run.ps1 table-evidence --ticker HPG --query "lợi nhuận năm 2024" --model

# Đọc lại PDF và kiểm raw request/response của một run đã lưu, không inference
.\run.ps1 table-evidence --replay outputs/table-evidence/<run_id>
```

`--reporting-period YYYY` chỉ định kỳ rõ ràng; bỏ qua thì nhận diện năm duy nhất
trong câu hỏi. `--mode strict_point_in_time --decision-at <ISO có timezone>` đi
qua gateway cũ; thiếu nguồn đủ điều kiện sẽ dừng trước raw PDF/inference.
Corpus hiện chưa có nguồn đủ điều kiện strict. Không dùng mốc tạo bảng mới làm
thời điểm công bố lịch sử.

Các run mã ngắn để replay:

- FPT: `20261024T015111Z-17b4dda5`.
- HPG: `20261024T015135Z-3671037b`.
- VCB: `20261024T015146Z-73323f4d`.

Mỗi thư mục có `result.json`, `context.json`, `table-01.json`…,
`retrieval-trace.json`, `gateway-audit.json`, source snapshot và checksum.
Nếu có inference, giữ thêm `generation/` cùng kiểm tra model trước/sau.
`selected_candidates` là dữ liệu xem xét, không đưa thẳng vào backtest như facts
đã duyệt. Lớp bảng này hiện chạy qua CLI; chưa có màn hình hoặc endpoint mới.

## Kiểm tra và giới hạn

- **356 test offline đạt**, Ruff đạt; còn hai cảnh báo deprecation TestClient/
  AnyIO đã biết. Dependency được thêm vào `.venv312`, `pyproject.toml`, `uv.lock`.
- 10 run mới (6 có model, 4 chỉ trích xuất) replay raw PDF thành công. Ba run
  dùng ID dài vẫn replay sau khi thêm selector ngắn.
- Replay bản đối chiếu 24 câu gốc đạt; các checksum case pack, batch và bản
  đối chiếu trợ lý không đổi. Không tạo nhãn thủ công, vẫn 0/24 xác nhận độc lập.
- Parser mới nhận một tập con bảng: tiêu đề nhiều năm, có STT/Chỉ tiêu và token
  số tách rời, căn cột rõ. Bỏ hàng thiếu/trùng cột, lệch cột, nghi ngờ nhãn xuống
  dòng, phần trăm; không suy dấu gạch ngang là số 0. Mẫu OCR, xoay trang, ô gộp,
  biểu đồ và các mẫu tiêu đề khác cần phát triển/kiểm tra riêng.
- Cụm phạm vi và đơn vị chỉ được quan sát trong vùng tiêu đề lân cận; có thể
  chưa đại diện đúng toàn bảng. Locator đúng không tự xác nhận đúng chỉ tiêu,
  chủ thể, kỳ hay ngữ nghĩa. Offset corpus cũ không được thay bằng box mới.
- Tác vụ chọn ô, schema/prompt và ngân sách khác luồng trích quote v0.3. Không
  so sánh số ID hợp lệ với số claim qua verifier cũ như một ablation công bằng.
- Chưa có PiT strict lịch sử, dự báo, backtest, human gold hoặc Full PiT-HAF.

Metadata nhỏ ở [data card](../../data/development/table-v0.4/DATA_CARD.md),
[study ID dài](../../data/development/table-v0.4/hash_refs.json),
[study mã ngắn](../../data/development/table-v0.4/short_refs.json),
[validation](../../data/development/table-v0.4/validation.json).
Artifact raw local mới chưa upload lên Drive/GitHub. Chỉ metadata không đủ để
replay khi thiếu thư mục nguồn.

API kỹ thuật tham khảo: [pdfplumber — từ và bounding box](https://github.com/jsvine/pdfplumber#extracting-text)
và [pypdf — giới hạn thứ tự/vị trí văn bản](https://pypdf.readthedocs.io/en/stable/user/extract-text.html).

## Bước tiếp theo

Mở rộng parser cho tiêu đề không có STT/Chỉ tiêu và nhãn nhiều dòng, tách biểu
đồ khỏi bảng, kiểm tra phạm vi/đơn vị bằng bằng chứng riêng. Sau đó xây màn hình
duyệt các ô liên kết, xác nhận nhãn độc lập và khóa cấu hình trên split mới.
Chất lượng truy xuất và chọn đủ chỉ tiêu vẫn cần cải thiện trước cohort/backtest.
