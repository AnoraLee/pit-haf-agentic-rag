# PiT-HAF

Đồ án nghiên cứu **Point-in-Time Hierarchical Agentic Framework** hỗ trợ phân
tích cổ phiếu Việt Nam bằng bằng chứng có thể truy nguyên. Hệ thống hiện có
kho tài liệu, truy xuất theo doanh nghiệp/kỳ báo cáo, báo cáo một agent và
đối soát trích dẫn. Dữ liệu phục vụ truy xuất và đánh giá; dự án dùng LLM có
sẵn, không huấn luyện một LLM mới.

**Backend:** FastAPI · **Frontend:** React + Vite · **LLM local:** Ollama/Qwen3:4b.

[Đối soát lịch thanh toán](docs/research/37-settlement-calendar-audit.md) ·
[Thanh toán theo thời điểm](docs/research/36-timestamp-settlement.md) ·
[Đối soát VNINDEX](docs/research/35-index-vendor-crosscheck.md) ·
[Snapshot giá 2021–2024](docs/research/34-market-price-snapshots.md) ·
[Backtest giả lập](docs/research/33-synthetic-execution-engine.md) ·
[Phiếu đối chiếu OCR](docs/research/32-ocr-source-review.md) ·
[Tiến độ 29/10/2026](docs/research/27-progress-20261029.md) ·
[Hồ sơ nghiên cứu](docs/research/README.md) ·
[Đáp án và đối chiếu 24 câu](docs/research/development-source-audit-v0.1.md)

## 1. Yêu cầu trên máy mới

Hướng dẫn dưới đây dành cho **Windows và PowerShell**, chạy tại thư mục gốc
repository. Các artifact dữ liệu hiện được tạo trên Windows.

| Thành phần | Yêu cầu |
|---|---|
| Git | Clone repository; tài khoản cần được cấp quyền nếu repository private |
| Python | 3.11 hoặc 3.12; hướng dẫn sử dụng 3.12 |
| uv | Cài dependency Python theo `uv.lock` |
| Node.js | 22.12+ hoặc 24 |
| pnpm | 11.25.0 |
| Ollama | Cần khi chạy trích xuất/báo cáo mới; không bắt buộc để xem PDF và kết quả đã lưu |
| Dữ liệu local | Tải riêng từ Google Drive ở mục 3 |

Trang cài đặt: [Git](https://git-scm.com/downloads),
[Python](https://www.python.org/downloads/),
[uv](https://docs.astral.sh/uv/getting-started/installation/),
[Node.js](https://nodejs.org/en/download), [Ollama](https://ollama.com/download).

## 2. Clone và cài thư viện

```powershell
git clone https://github.com/tuankhoi1205/pit-haf.git
cd pit-haf

$env:UV_PROJECT_ENVIRONMENT = ".venv312"
uv sync --locked --dev --python 3.12

npm install --global pnpm@11.25.0
.\run.ps1 frontend-install
.\run.ps1 frontend-build
```

Nếu đã clone, chạy `git pull --ff-only` trong repository trước khi cài/build.
Bỏ qua lệnh cài pnpm nếu đã có đúng phiên bản. `run.ps1` gọi trực tiếp Python
trong `.venv312`, hoặc `.venv` nếu không có `.venv312`; không cần activate môi
trường. Không sao chép môi trường Python hay `node_modules` từ máy khác.
Giữ `uv.lock` và `frontend/pnpm-lock.yaml` để cài đúng dependency của dự án.
Giữ `.gitattributes` khi clone: một số cấu hình lịch sử được ghim checksum
theo byte CRLF, các cấu hình khác theo LF. Không tự đổi xuống dòng hoặc
format lại JSON đã có checksum.

OCR là tùy chọn, chỉ cần nếu muốn đọc PDF dạng ảnh:

```powershell
$env:UV_PROJECT_ENVIRONMENT = ".venv312"
uv sync --locked --dev --extra ocr --python 3.12
.\run.ps1 ocr-preview --setup-models
```

Wheel `tesserocr` đã gồm Tesseract; không cần cài chương trình riêng trên
Windows x64 có wheel phù hợp. Lệnh setup tải hai bộ nhận diện vie/eng từ
revision chính thức và kiểm SHA-256, vào `data/cache/ocr/`. Khi chạy OCR,
PDF được xử lý local và không tự tải model. Xem
[cài đặt upstream](https://github.com/sirfz/tesserocr#installation).

## 3. Tải dữ liệu từ Google Drive

**[Mở thư mục dữ liệu PiT-HAF trên Google Drive](https://drive.google.com/drive/folders/1YIutetuTH-COMZjgbIAand0mwg3hiBr4?usp=sharing)**

Mã nguồn, cấu hình, data card và checksum được lưu trên GitHub. PDF, bài báo,
SQLite catalog và các artifact chạy local nằm trên Drive, nên **chỉ clone
repository chưa có đủ dữ liệu để dùng kho tài liệu và bộ 24 câu**.
Chủ dự án đang tải dữ liệu lên thư mục này ngày 23/10/2026; cần đợi các phần
liên quan hoàn tất. Nếu Drive yêu cầu quyền truy cập, liên hệ chủ dự án để
được cấp quyền xem/tải. Repository và Drive có quyền truy cập riêng.

Tải đủ các thư mục hoặc file nén tương ứng, giải nén/copy **vào thư mục gốc
`pit-haf`**, giữ nguyên cấu trúc sau:

```text
pit-haf/
├── README.md
├── run.ps1
├── frontend/
├── src/
├── data/
│   ├── development/                    # metadata, cấu hình và đối chiếu từ Git
│   └── cache/
│       └── evidence/
│           ├── registry.sqlite3
│           └── blobs/
│               └── <2 ký tự hash>/<SHA-256>
└── outputs/
    ├── milestone-1/
    │   └── data-pilot/
    │       └── 20261018-corpus-v0.5-scale-curated/
    │           ├── summary.json
    │           ├── pages.jsonl
    │           ├── catalog.json
    │           └── catalog.sqlite3
    ├── development-cases/
    │   └── 20261019T030531Z-8ef1bf33/     # giữ toàn bộ thư mục
    ├── development-batches/
    │   └── 20261022T030940Z-22f948f0/    # giữ toàn bộ thư mục
    └── company-reports/
        └── <run_id>/                   # giữ các bản chạy từ Drive
```

| Thư mục cần tải | Dùng để làm gì |
|---|---|
| `data/cache/evidence/` | Raw PDF/bài viết theo hash và registry phiên bản |
| `outputs/milestone-1/data-pilot/20261018-corpus-v0.5-scale-curated/` | Corpus hiện hành, văn bản từng trang và chỉ mục tìm kiếm |
| `outputs/development-cases/` | 24 câu hỏi với các đoạn bằng chứng cố định |
| `outputs/development-batches/` | Manifest, trạng thái và liên kết các lượt chạy |
| `outputs/company-reports/` | Câu trả lời gốc, request/response, nguồn và checksum của từng lượt |
| `outputs/table-evidence/` | Lượt đọc ô bảng, locator và context; tải thêm nếu cần xem lịch sử bảng |

`data/cache/datasets/` chứa CSV gốc để tái nhập/mở rộng corpus, không bắt buộc
cho giao diện nếu đã có đầy đủ snapshot hiện hành. Nếu Drive có
`outputs/llm-pilot/` và `outputs/quote-replay/`, có thể copy thêm để xem các
chỉ số pilot cũ; đây là các artifact riêng với batch 24 câu.

`outputs/table-reviews/reviews.sqlite3` được tạo khi bạn lưu đánh giá ô bảng
đầu tiên, không bắt buộc để khởi động ứng dụng. Đây là lịch sử duyệt tại máy,
cần sao lưu riêng nếu muốn chuyển sang máy khác; dừng backend trước khi copy
file. Có thể tải lịch sử JSON của từng lượt ngay trên giao diện. JSON hiện
dùng để đối chiếu/lưu trữ, chưa có chức năng nhập lại.

Các đường dẫn trong `.gitignore` vẫn cần giữ: Git bỏ qua chúng khi push,
nhưng ứng dụng đọc được file đã tải về. `data/development/` trong repository
chứa metadata/checksum; dữ liệu nguồn đã ghim ở `outputs/development-cases/`
là phần cần khôi phục thêm từ Drive. Giữ nguyên tên thư mục và tên file hash.
Tránh giải nén thành `pit-haf/pit-haf-data/data/...` hoặc `data/data/cache/...`.

Kiểm tra nhanh các file bắt buộc:

```powershell
Test-Path .\data\cache\evidence\registry.sqlite3
Test-Path .\outputs\milestone-1\data-pilot\20261018-corpus-v0.5-scale-curated\catalog.sqlite3
Test-Path .\outputs\development-cases\20261019T030531Z-8ef1bf33\cases.jsonl
Test-Path .\outputs\development-batches\20261022T030940Z-22f948f0\manifest.json
```

Cả bốn lệnh cần trả `True`. Khi đã tải đủ, kiểm tra sâu bản đối chiếu 24 câu,
checksum, nguồn PDF và đầu ra gốc bằng:

```powershell
.\.venv312\Scripts\python.exe -X utf8 -m pit_haf.research.source_audit
```

Lệnh này đọc dữ liệu đã lưu, không gọi model và không tạo nhãn người duyệt.
Không dùng `--publish` để sửa lỗi thiếu file/checksum; hãy tải lại đúng file
hoặc phần dữ liệu còn thiếu từ Drive.

## 4. Chạy ứng dụng

```powershell
.\run.ps1 app
```

Mở **[http://localhost:8501](http://localhost:8501)**. Backend phục vụ frontend
đã build và API trên cùng cổng, chỉ lắng nghe `127.0.0.1`. API docs:
[http://localhost:8501/api/docs](http://localhost:8501/api/docs).

- **Kho bằng chứng:** duyệt/lọc tài liệu, xem trang và mở PDF đã lưu.
- **Phân tích tài liệu:** đặt câu hỏi, tìm bằng chứng và lập báo cáo doanh nghiệp.
- **Câu hỏi và kết quả kiểm tra AI:** xem 24 câu, trạng thái lần chạy và mở
  **Đáp án và đối chiếu nguồn** dưới từng câu.
- **Tạo đáp án tham chiếu:** ghi nhận kiểm tra của người dùng; tách khỏi đáp án
  do trợ lý soạn.
- **Đối chiếu ô bảng với PDF:** đọc bảng, mở lượt đã lưu và chọn vùng chỉ tiêu,
  số, năm, đơn vị trên PDF; mặc định không gọi AI, chưa tạo facts đã duyệt.
- **Dữ liệu thị trường:** lấy OHLCV qua provider; cần kết nối Internet.

Không cần chạy lại pilot, thu thập dữ liệu hoặc inference để mở ứng dụng và
xem các kết quả đã lưu. Nếu đã có server cũ, dừng server bằng `Ctrl+C` tại
terminal của server rồi chạy lại sau khi cập nhật mã/build frontend.

### Bật Ollama khi cần sinh báo cáo mới

Cài Ollama trên chính máy chạy backend, mở Ollama rồi thực hiện:

```powershell
ollama pull qwen3:4b
ollama list
```

Nếu chưa có dịch vụ lắng nghe ở `localhost:11434`, chạy `ollama serve` trong
terminal riêng. Nếu cổng đã được Ollama sử dụng thì giữ dịch vụ đang chạy.
Trên giao diện, chọn **Kiểm tra Ollama** trước khi chạy báo cáo mới.
Model được tải riêng trên từng máy; không nằm trong gói dữ liệu Drive.

## 5. Phát triển và kiểm tra

```powershell
.\run.ps1 test
.\run.ps1 lint
.\run.ps1 doctor
.\run.ps1 pit-demo
```

`test`, `lint` và `pit-demo` chạy offline. `pit-demo` sử dụng ví dụ giả định.
`doctor` lưu chẩn đoán môi trường/Ollama ở `outputs/preflight/`, không tải model
hoặc chạy inference. Lượt kiểm tra local gần nhất đạt **801 test** và lint.
Frontend giữ bản build đã kiểm tra ở mốc OCR, không đổi trong mốc đối soát
chỉ số. Đây là kiểm thử phần mềm, không phải độ chính xác tài chính
hoặc kết quả GitHub Actions. CI test/lint được cấu hình tại
[offline-checks.yml](.github/workflows/offline-checks.yml).

Khi sửa giao diện, chạy backend bằng `app` ở terminal thứ nhất và lệnh sau ở
terminal thứ hai:

```powershell
.\run.ps1 frontend-dev
```

Mở địa chỉ Vite hiển thị trên terminal, thường là `http://localhost:5173`;
`/api` được proxy về backend 8501. Chạy lại `frontend-build` để cập nhật giao
diện được phục vụ tại 8501. Streamlit cũ được giữ qua `run.ps1 streamlit` trên
cổng 8502; giao diện chính là React.

| Lệnh bổ sung | Chức năng |
|---|---|
| `.\run.ps1 company-report --ticker HPG --query "lợi nhuận năm 2024"` | Chạy báo cáo mới qua model local |
| `.\run.ps1 company-report --ticker HPG --query "lợi nhuận năm 2024" --retrieval-profile financial_sections_v0.3` | Dùng truy xuất mục báo cáo/bảng số liệu đang thử nghiệm |
| `.\run.ps1 retrieval-study` | Tạo chẩn đoán truy xuất riêng cho 24 câu, không inference hoặc thay bộ case gốc |
| `.\run.ps1 table-evidence --ticker HPG --query "lợi nhuận năm 2024"` | Trích ô bảng kèm locator nguồn, chưa gọi model hoặc xác nhận facts |
| `.\run.ps1 table-evidence --ticker HPG --query "lợi nhuận năm 2024" --model` | Một lượt Qwen chọn mã ô; ứng viên vẫn cần người duyệt |
| `.\run.ps1 table-evidence --ticker BID --query "lợi nhuận năm 2024" --profile table_cells_v0.5` | Parser mới cho một tập con tiêu đề/nhãn bảng, chưa gọi model |
| `.\run.ps1 table-evidence --ticker BID --query "lợi nhuận năm 2024" --profile table_cells_v0.6` | Lọc theo cụm chỉ tiêu, gộp ô trùng và giữ các vị trí nguồn; chưa gọi model |
| `.\run.ps1 table-evidence --ticker ACB --query "lợi nhuận năm 2024" --profile table_cells_v0.7` | Đọc lại lớp chữ PDF trước truy xuất; thử nghiệm chậm hơn, chưa gọi model/OCR |
| `.\run.ps1 table-evidence --ticker VCB --query "lợi nhuận năm 2024" --profile table_cells_v0.8` | Thêm kiểm tra tiêu đề cột năm, bỏ trang khác kỳ hoặc thiếu tiêu đề; chưa gọi model |
| `.\run.ps1 development-evaluate --evaluate-only --batch-id 20261022T030940Z-22f948f0` | Đánh giá lại batch đã lưu, không inference |
| `.\run.ps1 development-evaluate` | Chạy inference mới cho 24 case; cần Ollama và có thể tốn thời gian |
| `.\run.ps1 pilot-data --extract-existing` | Trích lại từ raw snapshot đã lưu; dùng khi phát triển dữ liệu |

Giữ bộ case và kết quả gốc khi xem lại batch đã công bố; tạo pack mới chỉ khi
chủ ý thay đổi nguồn/cấu hình phát triển. Mẫu tham chiếu và checksum không
thay thế các file nguồn trong gói Drive.

Trên giao diện báo cáo doanh nghiệp có tùy chọn **Cách tìm bằng chứng** mới.
Profile tài chính vẫn ở chế độ thử nghiệm: chẩn đoán chuỗi nguồn cải thiện,
nhưng cả ba lượt Qwen thử mới đều bị chặn. Chưa chứng minh tăng độ chính xác,
nên luồng theo từ khóa vẫn là mặc định. Xem
[kết quả và giới hạn thử nghiệm](docs/research/18-financial-section-retrieval.md).

Lớp bảng bổ sung locator riêng cho chỉ tiêu, ô số, cột năm, đơn vị và phạm vi.
Phần **Đối chiếu ô bảng với PDF** trên frontend cho phép chọn ô để tô vị trí
nguồn, mở lịch sử hoặc đọc bảng mới. Frontend/API hiện dùng profile thử nghiệm
v0.6, mặc định không gọi model: lọc theo cụm chỉ tiêu, gộp cùng nhãn/năm/số khi
đủ đơn vị và phạm vi, giữ toàn bộ vị trí nguồn để đổi bằng **Vị trí nguồn của
nhóm ô**. Nhóm cùng nhãn nhưng khác số được giữ để kiểm tra và bị chặn khi AI
chọn. CLI vẫn mặc định v0.4 để giữ hành vi cũ; truyền profile rõ ràng để thử v0.6.
Đây là ứng viên chưa duyệt, chưa phải bộ số liệu chuẩn hóa hoặc kết quả accuracy.
Xem [kết quả và giới hạn v0.6](docs/research/21-cell-relevance-and-grouping.md),
[giao diện v0.5](docs/research/20-table-source-viewer.md) và
[lịch sử v0.4](docs/research/19-table-cell-evidence.md).

Ngay dưới các phần bằng chứng của ô có **Duyệt vị trí nguồn đang chọn**:
ghi người duyệt, kết luận và chỉ tiêu diễn giải, đối chiếu đủ năm mục rồi lưu.
Mỗi lần sửa hoặc rút xác nhận tạo phiên bản riêng; vị trí trùng không được xác
nhận theo. Đánh giá là người dùng tự khai báo, chưa tự trở thành nhãn độc lập,
đầu vào model hay dữ liệu backtest. Xem
[quy trình duyệt và giới hạn](docs/research/22-table-location-reviews.md).

Tùy chọn **Đọc lại lớp chữ PDF · thử nghiệm** bật profile v0.7; mặc định vẫn
tắt. Bản này đọc raw PDF lại bằng pdfplumber, không sửa corpus hoặc ký hiệu
font bằng phép thay chuỗi. Lượt thử tìm được hai ô ứng viên cho ACB, nhưng
VCB mất context và FPT vượt giới hạn 400 trang, nên chưa thay mặc định v0.6.
MWG vẫn cần OCR. Xem [kết quả đầy đủ và giới hạn](docs/research/23-alternate-pdf-text.md).

Khi bật lớp chữ thử nghiệm, **Cách chọn trang thử nghiệm** cho phép chọn v0.7
hoặc **Lớp chữ + kiểm tra cột năm · v0.8**. V0.8 loại được trang trình bày lại
2023 ở VCB và có 5 ô gợi ý, gồm 2 ô tóm tắt chưa rõ phạm vi. Giao diện hiển
thị đơn vị từng dòng và lý do loại trang theo năm. Mặc định vẫn v0.6; các ô
mới chưa là facts được duyệt. Xem [kết quả và giới hạn v0.8](docs/research/24-annual-table-page-gate.md).

Nút **Xem tài liệu phù hợp** liệt kê PDF đúng doanh nghiệp/năm và cho chọn
**Tài liệu dùng để đọc bảng**. Nếu tổng số trang vượt 400 ở v0.7/v0.8, chọn
một bản trong giới hạn trước khi đọc. Không tự chọn tài liệu hoặc tăng ngân
sách; lựa chọn được lưu cùng run và vẫn phải qua gateway PiT. Với hai bản
FPT 2024, từng bản 213 trang đã chạy được, nhưng chưa tạo được ô đủ điều kiện
ở lượt thử này. Kết quả rỗng có lý do dừng và link trang PDF để kiểm tra.
Xem [chọn tài liệu và thử nghiệm FPT](docs/research/25-table-document-scope.md).

Tùy chọn **Kiểm tra cột năm và đơn vị · v0.9** bổ sung locator VND theo
từng cột năm hoặc dòng khai báo Đơn vị. Lượt thử FPT tiếng Việt có 4 ô
lợi nhuận chưa duyệt, giữ nguyên chuỗi số và nguồn; không suy hệ số hay
đổi giá trị sang triệu/tỷ. Các bản trước vẫn mở lại được. Xem
[đơn vị theo cột năm](docs/research/26-table-currency-units.md) và
[phần đã có/các bước còn lại](docs/research/27-progress-20261029.md).

Phần **OCR trang PDF · thử nghiệm** nằm dưới bộ chọn tài liệu. Chọn riêng
một PDF, nhập tối đa bốn số trang rồi OCR, hoặc mở lượt đã lưu. Có tìm
chữ, điểm nhận dạng từng từ và vùng tô trên ảnh từ PDF; có cả lỗi trong
lịch sử. OCR chưa sửa corpus, chưa đi vào câu trả lời hoặc facts đã duyệt.
Thử nghiệm MWG mới nhận 509 từ trên bốn trang nhưng còn lỗi chữ/số rõ rệt.
Xem [kết quả, cách dùng và giới hạn OCR](docs/research/28-local-ocr-preview.md).

Có thêm tùy chọn **Khoanh vùng OCR một trang**, hiển thị vùng đã chạy và
hộp từ trên ảnh toàn trang. Trên 24 ô mẫu MWG do trợ lý chép từ ảnh,
bản v0.2 khớp 24 chuỗi so với 14 ở v0.1; cả nhánh v0.2 toàn trang cũng
đạt 24/24, chưa chứng minh lợi ích riêng của crop. Đây là chẩn đoán phát
triển, chưa là nhãn độc lập hoặc số liệu đã duyệt. Xem
[phép thử OCR vùng và giới hạn](docs/research/29-ocr-region-numeric-diagnostic.md).

Trong kết quả OCR đã lưu, mở **Ô số OCR và thông tin đi kèm** để chọn từng
ô và tô riêng nguồn chỉ tiêu, giá trị, đơn vị trên PDF. Kỳ hoặc phạm vi
chưa đọc rõ được ghi là thiếu; không suy năm từ tên báo cáo hoặc lấy
mảnh số bị tách làm cả giá trị. Đây là ô ứng viên chưa duyệt, chưa đi
vào câu trả lời. Xem [liên kết ngữ cảnh OCR](docs/research/30-ocr-cell-context.md).

Có thêm cách liên kết **Theo vị trí và nhãn xuống dòng · v0.2** và chọn
riêng một lượt OCR vùng hẹp để bổ sung tiêu đề trên cùng trang. Mỗi từ
giữ nguồn OCR riêng; vùng bổ sung không được ghi đè số. Trên mẫu MWG,
cách này đã đọc được tiêu đề cột tương đối; trang đầu có thêm kỳ tài
chính và phạm vi hợp nhất, nhưng vẫn còn ô/nhãn lỗi và chưa xác nhận năm
cho từng số. Xem [kết quả và cách dùng](docs/research/31-ocr-header-spatial-links.md).

Mở **Ghi kết quả đối chiếu ô số** để lưu bản chép đã kiểm tra, lý do sửa
và lịch sử riêng cho từng ô OCR. Xác nhận cần đủ nguồn, kiểm năm mục và
tự nhập năm theo locator; thiếu phạm vi/kỳ thì vẫn bị chặn. Có export
JSON và phát hiện phiếu cũ khi lưu. Đây là khai báo của người đối chiếu
local, chưa là nhãn độc lập và chưa đưa vào câu trả lời hoặc backtest.
Phiếu nằm trong `outputs/ocr-reviews/reviews.sqlite3`, ngoài Git; không
tạo database chỉ vì mở xem. Xem [quy trình và giới hạn](docs/research/32-ocr-source-review.md).

### Backtest giả lập

Đã có động cơ thực thi long-only/cash để kiểm tra độ trễ phiên, phí,
slippage, lô, thanh toán và sổ danh mục bằng dữ liệu tự tạo:

```powershell
.\run.ps1 backtest-synthetic --demo
.\run.ps1 backtest-synthetic --demo --baseline Q0
.\run.ps1 backtest-synthetic --demo --baseline Q1 --rebalance-every 2
```

Kết quả JSON/CSV và nguồn/config/hash nằm ở `outputs/backtest-synthetic/`.
Dùng `--replay <thư mục run>` để tái tính. Không cần Ollama hoặc tải giá.
Q0/Q1 mới có cơ chế tạo lịch trên kịch bản giả lập; chưa là kết quả của
hai baseline nghiên cứu. Runner chưa nhận giá thị trường, chưa xác minh
lịch/điều chỉnh giá/quy tắc thực thi sàn hoặc chạy đủ năm baseline.
Xem [quy tắc, kiểm chứng và giới hạn](docs/research/33-synthetic-execution-engine.md).

Phiên bản có thời điểm thanh toán riêng:

```powershell
.\run.ps1 backtest-timed --demo
.\run.ps1 backtest-timed --demo --baseline Q1 --rebalance-every 2
.\run.ps1 backtest-timed --replay outputs/backtest-timed-synthetic/<run-id>
```

Tách lịch giao dịch/lịch thanh toán và giờ khả dụng của tiền/cổ phiếu;
tài sản về buổi trưa chưa được dùng lúc mở cửa. Có ledger sự kiện,
`settlement_schedule.csv`, `settlement_events.csv` và replay offline.
Giữ nguyên protocol giả lập cũ. Đây là mô hình kiểm tra kế toán, lịch
HOSE/VSDC và thời điểm tài khoản khách hàng vẫn cần xác minh trước khi
dùng giá thật. Xem [thanh toán theo thời điểm](docs/research/36-timestamp-settlement.md).

### Snapshot giá thị trường

Đối soát ngày giá với thông báo thanh toán VSD/VSDC:

```powershell
.\run.ps1 calendar-audit --build --sources-run <run-nguồn> --market-run <run-giá>
.\run.ps1 calendar-audit --replay outputs/calendar-audits/<run-id>
```

Ba mã FPT/HPG/VCB khớp toàn bộ **998 ngày** với lịch ứng viên 2021–2024,
có giữ bản gốc/sửa đổi và cặp ngày T+2 qua đầu năm 2025. Chưa xác minh
đầy đủ lịch HOSE hoặc giờ tài sản về tài khoản; chưa nối vào thực thi.
Build/replay cần archive nguồn và snapshot giá local. Capture nguồn mới
cần PowerShell 7.2+; xem [nguồn, lệnh và giới hạn](docs/research/37-settlement-calendar-audit.md).

```powershell
.\run.ps1 market-snapshot --capture
.\run.ps1 market-snapshot --replay outputs/market-snapshots/<run-id>
```

Capture cần Internet, mặc định bốn nguồn FPT/HPG/VCB/VNINDEX giai đoạn
2021–2024. Lưu raw HTTP, normalized JSON, CSV, nguồn/hash và quality report
ở `outputs/market-snapshots/`, ngoài Git. Replay không tải lại dữ liệu.
Không cần Ollama hoặc cài thêm thư viện.

Mốc đã lưu có **2.994 bar** của ba cổ phiếu. VNINDEX có ba hàng không thỏa
quan hệ OHLC nên bị chặn chuẩn hóa, raw vẫn giữ. CLI trả exit 2 khi có
nguồn lỗi chất lượng, kể cả khi replay khớp. Giá điều chỉnh, availability,
lịch sở và quy tắc thực thi chưa được xác nhận; snapshot chưa chuyển sang
engine hoặc tạo lợi suất. Xem [kết quả và giới hạn](docs/research/34-market-price-snapshots.md).

### Đối soát VNINDEX và so chuẩn giá đóng cửa

```powershell
.\run.ps1 index-crosscheck --capture --kbs-run <run-id-KBS>
.\run.ps1 index-crosscheck --replay outputs/index-crosschecks/<run-id>
```

Đọc chart công khai Vietcap và pin nguồn KBS đã lưu, đối chiếu từng trường,
giữ mọi sai lệch/lỗi OHLC. Mốc 2021–2024 có **998/998 close khớp**, còn
open/high/low và volume khác biệt. Tạo comparator close-only, curve gốc
100 và CSV để phát triển Q2; không phát sinh lệnh hoặc sửa bộ OHLCV gốc.
Exit 0 chỉ thể hiện đồng thuận close-only, chưa cấp điều kiện thực thi hay
xác nhận PiT. Không chứng minh các vendor độc lập upstream. Xem
[quy tắc và kết quả](docs/research/35-index-vendor-crosscheck.md).

## 6. Xử lý lỗi thường gặp

| Hiện tượng | Cách xử lý |
|---|---|
| Git clone/Drive báo không có quyền | Đăng nhập đúng tài khoản và nhờ chủ dự án cấp quyền cho từng dịch vụ |
| `Missing .venv` | Chạy lại `uv sync` với `UV_PROJECT_ENVIRONMENT=.venv312` theo mục 2 |
| Không tìm thấy pnpm | Cài Node.js và pnpm, mở terminal mới rồi kiểm tra `node --version`, `pnpm --version` |
| `Missing frontend build` hoặc trang chủ trả 503 | Chạy `frontend-install`, sau đó `frontend-build` |
| Kho trống, báo thiếu snapshot/registry | Khôi phục `data/cache/evidence` và snapshot corpus từ Drive đúng cấu trúc mục 3 |
| 24 câu/đối chiếu trả lỗi thiếu `cases.jsonl`, manifest hoặc report | Copy đủ ba thư mục `development-cases`, `development-batches`, `company-reports` từ Drive |
| Checksum không khớp | Kiểm tra tải/giải nén đã hoàn tất; tải lại file nguyên bản, không sửa hash để bỏ qua |
| Ollama chưa kết nối/model chưa cài | Kiểm tra dịch vụ local 11434 và `ollama list`; tải `qwen3:4b` nếu còn thiếu |
| Cổng 8501 đã được sử dụng | Dừng đúng server cũ rồi chạy lại ứng dụng |
| Sửa frontend nhưng giao diện chưa đổi | Build lại, khởi động lại backend nếu đổi API và refresh trình duyệt |

## 7. Phạm vi hiện tại

- Corpus v0.5 có **30.939 tài liệu**: 264 PDF, 675 bài thu thập trực tiếp và
  30.000 bài nhập từ VietOnlineNews. Giữ riêng provenance bản nhập dataset;
  nguồn mirror không được gọi là HTML tải trực tiếp từ báo.
- Bộ phát triển có **24 câu, 72 tham chiếu** cho FPT/HPG/VCB. Batch đã lưu có
  8 câu với nhận định qua kiểm tra trích dẫn, 15 câu từ chối và 1 lượt sinh
  đầu ra chưa hợp lệ. Các trạng thái này không phải tỷ lệ trả lời đúng.
- Đã có bản đối chiếu PDF đủ 24 câu do trợ lý soạn. Ngữ cảnh ghim đủ thông tin
  cho 8 câu, hỗ trợ một phần cho 12 câu và thiếu/sai chủ đề cho 4 câu theo bản
  đối chiếu này; chưa có bộ nhãn người dùng xác nhận độc lập.
- PiT Guard lọc theo timestamp/phiên bản đã cung cấp. Corpus hiện chưa có bằng
  chứng đủ điều kiện PiT strict; ngày đăng/ngày tải không tự chứng minh
  `available_at`. Guard không loại bỏ kiến thức tương lai trong trọng số LLM.
- Quote Resolution kiểm nguyên văn/chuỗi số trên văn bản trích xuất, gắn trang,
  offset và hash; chưa bảo đảm đúng ngữ nghĩa, chỉ tiêu, đơn vị hoặc loại bỏ
  mọi ảo giác. Đây chưa phải toàn bộ hệ agent phân cấp PiT-HAF.
- Có nền tảng thực thi trên dữ liệu giả lập với lịch Q0/Q1, phí/thanh toán
  và ledger; chưa có backtest giá thật hoặc kết quả đủ 5 baseline. Phần
  graph/peer/memory và ablation đầy đủ còn theo lộ trình; chưa có kết quả
  dự báo lợi suất hoặc giao dịch thực nghiệm để công bố.
- Có snapshot giá KBS 2021–2024 cho ba mã phát triển và raw VNINDEX bị
  chặn chất lượng. Chưa xác minh điều chỉnh giá/phiên bản khả dụng, chưa
  dùng các bar này làm cohort PiT strict hoặc dữ liệu thực thi.
- Có đối soát VNINDEX với Vietcap và comparator giá đóng cửa Q2 phát
  triển. Các sai lệch OHLC/volume còn giữ; chưa có Q2 nghiên cứu đã khóa,
  Q3/Q4 hoặc bộ kết quả so sánh giao dịch hoàn chỉnh.

## 8. Tài liệu và cấu trúc mã nguồn

| Đường dẫn | Nội dung |
|---|---|
| `src/pit_haf/data/` | OHLCV, evidence/registry, PiT gateway, nhập dữ liệu và catalog |
| `src/pit_haf/llm/` | Adapter Ollama, schema, giới hạn gọi model và pilot trích xuất |
| `src/pit_haf/verification/` | Đối soát quote và kiểm tra số học |
| `src/pit_haf/research/` | Case pack, batch/evaluator, review và đối chiếu nguồn |
| `src/pit_haf/backtest/` | Hợp đồng, động cơ thực thi và runner giả lập; lịch Q0/Q1, ledger, replay |
| `src/pit_haf/ui/`, `frontend/` | API FastAPI và giao diện React/Vite |
| `configs/`, `data/development/`, `data/corpus/` | Cấu hình, data card, metadata/checksum |
| `tests/` | Kiểm thử offline với fixture tách khỏi dữ liệu thực |
| `docs/research/` | Kiến trúc, protocol, kết quả phát triển và lộ trình |

Đọc [đề cương](docs/de-cuong-nghien-cuu-pit-haf.md),
[hồ sơ nghiên cứu](docs/research/README.md),
[data card v0.5](data/corpus/v0.5/DATA_CARD.md),
[hướng dẫn batch/evaluator](docs/research/16-development-batch-evaluation.md)
và [bản đối chiếu 24 câu](docs/research/development-source-audit-v0.1.md).
Ghi chú đọc paper và bản dịch là tài liệu tham khảo, không phải kết quả thực
nghiệm của đề tài. [Lịch sử khôi phục](docs/RECOVERY-VERIFICATION.md) giữ các
mốc kiểm tra cũ để truy nguyên.
