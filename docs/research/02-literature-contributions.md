# Literature và contribution matrix — 06/10/2026

## Phạm vi đối chiếu

Đã kiểm tra paper gốc CARAG (EACL PDF: phương pháp, ablation, hạn chế),
Look-Ahead-Bench v1 (phương pháp), Profit Mirage v1 (chẩn đoán và FactFin), cùng
trang repository tác giả CARAG/Look-Ahead-Bench. TradingAgents/FinMem/MASTER mới
đối chiếu abstract và metadata, chưa đủ để kết luận audit toàn bộ code/protocol.
Đây chưa phải systematic literature review đầy đủ.

| Nguồn gốc | Ý tưởng đã đối chiếu | Dùng trong PiT-HAF | Điều chưa được chứng minh |
|---|---|---|---|
| [CARAG, EACL 2026](https://aclanthology.org/2026.eacl-long.141.pdf), §3/§4/§6 | Specialist lịch sử/peer, CTKG và tổng hợp; timestamp công bố, masking; hạn chế ground truth tại thời điểm công bố | Kế thừa phân vai và contextual retrieval; chuyển sang BCTC/công bố Việt Nam | Không coi peer/multi-agent/graph là ý tưởng mới của đề tài; chưa xác nhận version-aware gateway xuyên cache/memory |
| [Look-Ahead-Bench v1](https://arxiv.org/html/2601.13770v1), §3 | Hai period, 5 mã công nghệ Mỹ, relative-return decay và quant baselines | Kế thừa chẩn đoán thời gian; thiết kế universe/protocol Việt Nam riêng | Decay chịu regime/selection confounding; không tự chứng minh memorization hoặc cutoff của model hiện tại |
| [Profit Mirage v1](https://arxiv.org/html/2510.07920v1), §2/§3 | Temporal segmentation, counterfactual, FactFin tạo chiến lược với RAG/MCTS | Chẩn đoán nhạy đầu vào và hạn chế pretraining leakage | Không tái hiện FactFin chỉ bằng sửa prompt; không suy ra mọi kết quả xấu là leakage |
| [TradingAgents v7](https://arxiv.org/abs/2412.20138v7) | Phân vai analyst/researcher/risk/trader, đối thoại cộng tác | Đối chứng đa agent và quyền/budget vai trò | Mới đọc abstract; cần audit tool/memory/time trong code trước tái hiện |
| [FinMem v2](https://arxiv.org/abs/2311.13743v2) | Layered memory và decision-making | Tham khảo memory có importance/recency | Cần xem full protocol; không đồng nhất layered memory với memory PiT |
| [MASTER v1](https://arxiv.org/abs/2312.15235v1) | Market-guided feature selection, intra/inter-stock aggregation | Đối chứng ngoài nếu đủ dữ liệu/tài nguyên | Không là baseline đầu bắt buộc; cần thiết kế chuyển miền và training protocol riêng |

Repository [CARAG](https://github.com/luweihai/CARAG) cung cấp artifact tham khảo;
chưa chạy tái hiện. Cây root [Look-Ahead-Bench](https://github.com/benstaf/lookaheadbench)
đã quan sát có package frontend/leaderboard; chưa xác nhận có Python runner tái
hiện thí nghiệm từ cây đó. Không dùng câu "code available" làm bằng chứng đã
tái hiện hoặc tự nhận bản cài quant là tái hiện chính xác paper.

Tên benchmark trong Profit Mirage v1 được ghi **FinLake-Bench** trên paper
đã kiểm tra; các ghi chú/bản dịch khác có cách viết FinLeak-Bench. Khi trích
dẫn cần ghi version và theo nguồn gốc, không tự thống nhất sai tên. Bản dịch
CARAG có các kết luận mạnh về loại bỏ leakage; đó là phát biểu nguồn, không
được dùng như chứng minh rằng Guard của dự án loại hết pretraining leakage.

## Ma trận đóng góp dự kiến

| ID | Loại công việc | Artifact cần có | Đánh giá/đối chứng | Trạng thái |
|---|---|---|---|---|
| C1 | Tích hợp + đặc tả được đề xuất | evidence schema, raw snapshots, version/timestamp proofs, quarantine | gold late/revised documents; đúng version/hash/coverage | mới có contract; Guard schema nhỏ đang chạy |
| C2 | Cơ chế hệ thống được đề xuất | gateway cho retrieval/tools/graph/cache/memory/memos + audit | future injection, replay quá khứ, metamorphic invariance | chưa triển khai xuyên suốt |
| C3 | Kế thừa kiến trúc + tích hợp kiểm chứng | specialist hierarchy, verifier deterministic/semantic, risk/ABSTAIN | single-agent cùng dữ liệu/model/budget; bỏ verifier | chưa triển khai |
| C4 | Artifact đánh giá Việt Nam được đề xuất | data card, samples/splits, gold evidence/claims, rubric | annotation agreement, prediction/evidence/coverage, CI | chưa thu thập/nhãn |
| C5 | Engineering/tái lập | locked deps, manifest/diff/hashes, raw outputs, replay, UI | chạy lại snapshot; audit failures/config/model | bắt đầu bằng doctor + source snapshot; runner thí nghiệm chưa có |

Contribution mới chỉ được gọi là **dự kiến**. Triển khai nhiều agent, ghép
graph với RAG hoặc chuyển sang tiếng Việt không tự chứng minh novelty khoa học.
Đánh giá C2 có thể có giá trị ngay cả khi prediction/PnL không hơn baseline.

## Claim ledger phải xác minh trước khi viết kết luận

| Claim | Bằng chứng tối thiểu | Hiện trạng |
|---|---|---|
| Chưa có cơ chế tương tự trong literature | search log có query/date, criteria, screening và paper full text | chưa làm systematic review; không tuyên bố "đầu tiên" |
| External future exposure bằng 0 trong contract | audit thực sự agent-visible + tests mọi đường I/O trên snapshot thật | mới tests Guard độc lập |
| Versioning cải thiện quyết định | original/revised ground truth + paired runs | chưa có |
| Hierarchy/graph/verifier/memory hữu ích | ablation cố định, kiểm soát data/model/budget, CI/effect size | chưa có |
| Local model đủ tiếng Việt/tài chính | pilot thật: JSON, quote, số liệu, human rubric, resource/latency | chưa inference |
| Không có pretraining leakage | model snapshot/cutoff có bằng chứng và diagnostics; vẫn cần giới hạn | chưa thể kết luận từ temporal gate |
| Backtest khả thi Việt Nam | calendar/lot/settlement/liquidity/corporate actions và ledger | chưa engine |

SLR tiếp theo: tra cứu các cụm point-in-time/bitemporal/version-aware RAG,
financial agents, temporal graph, memory leakage, evidence verification;
ghi source/date/version, criteria nhận/loại và snowball references. Đọc hai
paper gần nhất mỗi nhánh, audit code có điều kiện truy cập. Mọi khoảng trống
ở đây là giả thuyết cần kiểm chứng, không kết luận từ việc chưa thấy trong ba bài.
