# Audit hiện trạng — 06/10/2026

## Mốc quan sát trước sửa

Git HEAD: `a20920b6f100499ef83e3b87eb3054890991ca87`. Working tree chưa commit:
README, bài 1, ghi chú khôi phục, pyproject và run.ps1 đã sửa; bài 2, Guard và
test Guard là tệp mới. Không reset/stash/commit hoặc ghi đè Guard/provider.
Bản chụp 23 tệp ban đầu, hashes và diff được lưu tại
`outputs/milestone-1/before/`; outputs bị Git ignore.

Không thấy AGENTS.md trong cây dự án hoặc các thư mục cha đã kiểm tra.
Đã đọc README, app, cấu hình, lockfile, script, provider, Guard, hai bộ test và
tài liệu phương pháp/đề cương/ghi chú/bản dịch. Lockfile có 81 gói của môi trường
đã cài; không dùng số package/test làm bằng chứng hiệu quả nghiên cứu.

Kiểm tra vừa chạy trước sửa: `run.ps1 test` **63 passed in 1.29s**;
`run.ps1 lint` **All checks passed!**. Test provider dùng mock kết nối; test
Guard dùng bản ghi giả định. Đây là kiểm tra code offline, không phải tải dữ
liệu thật hoặc suy luận LLM. `outputs/` trước lượt khảo sát chỉ có `.gitkeep`.

## Bảng thành phần

P0: cần cho tính hợp lệ; P1: cần cho hệ thống đầy đủ; P2: mở rộng/hoàn thiện.
"Kế hoạch" chỉ là tài liệu, chưa có hiện thực. Trạng thái dưới đây là trước sửa.

| Thành phần | Trạng thái có thật / bằng chứng | Thiếu sót | Ưu tiên | Phụ thuộc | Tiêu chí nghiệm thu |
|---|---|---|---|---|---|
| Môi trường | Đã chạy Python 3.11.17, pyproject/uv.lock, run.ps1 | uv/Python không có trên PATH của shell; run dùng .venv | P0 | máy/lock | sync locked và test/lint chạy trên máy mới |
| OHLCV/VNINDEX | Code + test: `VietnamMarketDataProvider.get_prices`, `normalize_ohlcv` | online chưa kiểm tra lại; lịch phiên, adjustment và availability chưa xác minh | P0 | Vnstock/KBS | raw snapshot + đối chiếu mẫu/lịch/đơn vị + metadata |
| Guard | Đã chạy độc lập: `select_as_of`, 40 test | schema nhỏ, tin timestamp đầu vào; không bao phủ pipeline | P0 | nguồn versioned | test version/future injection xuyên mọi đường đọc |
| Provenance/versioning | Kế hoạch bài 2; provider dùng attrs | không checksum/raw file/source URL/version proof | P0 | nguồn | lưu bytes + metadata có hash, phân loại verified/quarantine |
| Gateway xuyên suốt | Chưa có | tool/chunk/fact/cache/memory/memo chưa được gác | P0 | snapshot/schema | future injection không đổi context hợp lệ |
| Văn bản Việt Nam | Chưa thu thập trong repo | nguồn/điều khoản/timestamp/OCR | P0 | feasibility | data card pilot, raw + locators + coverage |
| Structured/lexical/vector | Kế hoạch đề cương | chưa index, chunking, embeddings Việt Nam/gold | P1 | gateway/chunks | precision/recall + statistics chỉ từ corpus hợp lệ |
| Graph/peer | Kế hoạch, tham khảo CARAG | chưa nodes/edges/time/industry schemas | P1 | facts/peers | cạnh có lineage; traversal cắt thời gian; peer hợp ngành |
| Local LLM | Package `ollama` đã cài | package không phải Ollama server/model; chưa inference | P0 | RAM/service/model/pilot | digest/quantization + benchmark 20–30 mẫu thật |
| Planner/agents/hierarchy | Thư mục agents có .gitkeep | chưa contracts, workflow/tool budgets | P1 | retrieval/adapter | bounded trace, specialist + verifier/risk/synthesis |
| Verifier/risk | Kế hoạch | chưa kiểm quote, số liệu, conflict hoặc ABSTAIN | P0 | evidence/output | gold invalid-quote/numeric/conflict cases + fail paths |
| Memory/cache/audit | Kế hoạch | audit Guard chỉ trong RAM; chưa isolation | P0 | gateway/manifest | future replay, branch isolation, durable events |
| Backtest | Thư mục backtest có .gitkeep | chưa timeline, fees/cash/holdings/settlement | P0 | lịch/quy định/giá | ví dụ tính tay + next executable order ledger |
| Evaluation/runner | Evaluation có .gitkeep | chưa labels/split/gold/metric/statistics | P0 | protocol/samples | matrix cố định + outputs thật + paired/block CI |
| UI | app.py chạy thử AAPL/Yahoo/USD | caption gợi pipeline chưa có; first/last return không là engine | P1 | data/pipeline | Việt Nam/VND; nhãn đúng trạng thái; nguồn lỗi rõ |
| Tài liệu | Đề cương/ghi chú/bản dịch có thật | đề cương Mỹ là chính, không khớp yêu cầu | P0 | audit/literature | task Việt Nam nhất quán, contribution có artifact |
| CI/tái lập | uv.lock + test/lint; chưa CI | chưa run manifest/source snapshot/model/raw outputs | P1 | runner | CI offline; replay tách inference mới; hashes/diff |

## Phần cứng đã đo

- AMD Ryzen 5 5600H, 6 nhân/12 luồng.
- NVIDIA GeForce RTX 3050 Laptop GPU: 4096 MiB VRAM, lúc đo còn 3964 MiB;
  driver 566.07. Đây là số đo `nvidia-smi`, chưa đo placement/inference.
- RAM dùng được tổng khoảng 15,40 GiB; RAM trống tại một lần đo khoảng 2,70 GiB.
  Không được hiểu 15,4 GiB là lượng còn trống để tải model.
- Ổ C trống khoảng 132,47 GiB lúc khảo sát; có thể thay đổi.
- Không tìm được `ollama` trên PATH, các vị trí user/Program Files thông dụng
  hoặc đăng ký uninstall đã kiểm tra; không thấy process Ollama.
  GET `127.0.0.1:11434/api/version` trả connection refused.
  Kết luận: dịch vụ default không chạy; chưa chứng minh Ollama không nằm ở ổ khác.
- Chưa có digest/model local, throughput, latency, valid JSON, fidelity tiếng Việt
  hay VRAM peak. Không có kết quả benchmark để chốt qwen3:4b.

## Sai lệch tài liệu cần sửa

Đề cương mục 7 chọn Mỹ làm chính, Việt Nam case study; phần agent bổ sung để sau;
milestone 48 giờ không phản ánh phạm vi nhiều tháng. app dùng `yf.download` với
`auto_adjust=True`, tính close cuối/đầu và gắn tên Buy & Hold. Dòng caption mô tả
agent/backtest/evaluation chưa được code thực hiện. Sửa các điểm này trong lượt
đầu, giữ nguồn/bản dịch paper để tham khảo đúng xuất xứ.

Trạng thái **sau sửa** và kết quả test mới được ghi riêng trong
[milestone 1](07-milestone-1.md); không viết lại lịch sử audit thành "đã có".
