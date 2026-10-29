# PiT-HAF

Đồ án nghiên cứu **Point-in-Time Hierarchical Agentic Framework** hỗ trợ phân
tích cổ phiếu Việt Nam bằng bằng chứng có thể truy nguyên. Hệ thống hiện có
kho tài liệu, truy xuất theo doanh nghiệp/kỳ báo cáo, báo cáo một agent và
đối soát trích dẫn. Dữ liệu phục vụ truy xuất và đánh giá; dự án dùng LLM có
sẵn, không huấn luyện một LLM mới.

**Backend:** FastAPI · **Frontend:** React + Vite · **LLM local:** Ollama/Qwen3:4b.

[Tiến độ 23/10/2026](docs/research/17-progress-20261023.md) ·
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
hoặc chạy inference. Lượt kiểm tra local gần nhất đạt **426 test**; lint và
frontend build đạt. Đây là kiểm thử phần mềm, không phải độ chính xác tài chính
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
- Backtest, 5 baseline định lượng, graph/peer/memory và ablation đầy đủ còn
  theo lộ trình; chưa có kết quả dự báo lợi suất hoặc giao dịch để công bố.

## 8. Tài liệu và cấu trúc mã nguồn

| Đường dẫn | Nội dung |
|---|---|
| `src/pit_haf/data/` | OHLCV, evidence/registry, PiT gateway, nhập dữ liệu và catalog |
| `src/pit_haf/llm/` | Adapter Ollama, schema, giới hạn gọi model và pilot trích xuất |
| `src/pit_haf/verification/` | Đối soát quote và kiểm tra số học |
| `src/pit_haf/research/` | Case pack, batch/evaluator, review và đối chiếu nguồn |
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
