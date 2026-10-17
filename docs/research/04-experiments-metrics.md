# Experiment matrix, protocol và rubric — bản phát triển 0.1

Chưa có kết quả thí nghiệm. Các hàng dưới đây là arm dự kiến, phải có config
version và artifacts trước khi gọi là đã chạy. Horizon chính 5 phiên theo
[task contract](01-task-protocol.md); cùng universe/sample IDs/split/model
snapshot/policy timeline cho các phép so sánh áp dụng được.

## Baseline hợp lệ

| ID | Hệ thống | Input | Metric áp dụng | Giữ điều kiện gì? |
|---|---|---|---|---|
| Q0 | Buy & Hold cùng universe | initial eligible universe/prices | portfolio return/risk/cost | cùng vốn, lịch, fees/liquidity |
| Q1 | Equal Weight, rebalance cố định | eligible prices | portfolio | cùng engine, schedule preregistered |
| Q2 | VNINDEX price-return comparator | official index bars | relative price return, không F1 | calendar align, không coi là tradable |
| Q3 | Momentum (lookback 63 phiên), MA 50/100 | only eligible price history | portfolio; prediction chỉ nếu mapping đăng ký | đủ warm-up, không fallback theo test |
| Q4 | Logistic Regression | technical/market features cùng cutoff | prediction + policy portfolio | fit scaler/model/calibration chỉ trên train/dev |
| L0 | Single LLM không retrieval | task + gói facts/bar summary cố định | prediction/report/system | xác định rõ vẫn có input; không labels tương lai |
| L1 | Naive vector RAG trên corpus **đã cắt thời gian** | vector-only eligible snapshot | prediction/evidence/system/portfolio | giản đơn retrieval, vẫn hợp lệ PiT ngoài |
| L2 | PiT single-agent RAG | full eligible hybrid corpus | cùng nhóm LLM | cùng evidence access/model, bounded tool rounds |
| L3 | Multi-agent workflow cố định | cùng eligible access, 4 specialists độc lập và một lượt tổng hợp | cùng nhóm LLM | không retrieval bổ sung theo planner/verifier; giữ verifier/risk/memory như HAF, cùng call/token ceiling |
| HAF | PiT-HAF đầy đủ | gateway + hybrid/graph/peers + memory | toàn bộ metric hợp lệ | specialists→verifier→risk→hierarchical synthesis |

Portfolio baseline không tự có nhãn dự đoán: Macro-F1/MCC/Brier ghi **N/A**.
L0 vs RAG có khác input access được công bố; L2 vs HAF dùng cùng corpus/access
để đo kiến trúc. Ngoài budget tự nhiên, chạy subcomparison cùng tổng token/
call ceiling; nhiều lần gọi hơn có thể là nguyên nhân cải thiện. Q4 bắt đầu
Logistic Regression để có đối chứng học máy rõ; LightGBM/XGBoost là mở rộng
nếu có lý do sau development. MASTER/CARAG/TradingAgents là đối chứng ngoài
nếu tái hiện/chuyển miền được; ghi "adaptation" khi chưa đúng original.

## Ablation và chẩn đoán tách biệt

| ID | Thay đổi duy nhất so với reference | Phép đo | Loại bảng |
|---|---|---|---|
| A1 | HAF vector-only, bỏ lexical/structured/graph package theo định nghĩa | retrieval/support/prediction/system | hợp lệ; ablation package, không tách hiệu ứng từng thành phần |
| A1b | Bỏ từng lexical hoặc structured riêng, hai configs | marginal retrieval/quality | hợp lệ; tách hiệu ứng ngoài ablation package A1 |
| A2 | Bỏ graph, giữ peer lookup bằng bảng | reasoning/evidence/prediction/cost | hợp lệ |
| A3 | Bỏ peer context, giữ graph nội doanh nghiệp | cross-firm grounding | hợp lệ |
| A4 | Bỏ hierarchy, gộp specialist vào single-agent cùng budget/access | report/prediction/cost | hợp lệ |
| A5 | Bỏ verifier | unsupported/invalid citation/numeric + downstream quality | hợp lệ, ngoại trừ dữ liệu future vẫn luôn bị gateway chặn |
| A6 | Bỏ memory, cùng episodic initialization | consistency/performance/latency | hợp lệ |
| D1 | Tắt temporal gate trên corpus có future/revision injection | exposure/version error, invariance | **leakage diagnostic**, không thành tích đầu tư |
| D2 | Naive vector RAG trên corpus toàn thời gian | exposure/quality inflation | diagnostic, tách L1 corpus hợp lệ |
| D3 | Entity masking, kiểm mapping không đổi số/ý nghĩa | prediction/support/identity sensitivity | diagnostic/robustness |
| D4 | Counterfactual controlled inputs | quote/numeric consistency, response sensitivity | stress test, không historical PnL |

Counterfactual không mặc định ép mọi thay đổi thành đảo hướng dự báo; rubric
xác định trước thay đổi nào chỉ ảnh hưởng claim, confidence hoặc ABSTAIN.
Các ngành, regime và horizon phụ dùng cohort được đăng ký. Thử model/context/
chunking/embedding trên dev; robustness model giữ split và corpus cố định.
Không so "bỏ graph+peer+verifier" rồi quy tất cả hiệu ứng cho graph.

## Split và sampling

Đề xuất sau khi biết coverage: oldest 50% thời gian cho train/classifier;
20% development cho prompt/model/chunking; 10% validation cho threshold và
calibration; latest 20% test mở một lần. Đây là tỉ lệ phát triển, chưa có ngày
split thực vì chưa có dataset. Split theo date blocks, không random từng mã.
LLM không training vẫn cần dev/test; train phục vụ classifier hoặc chuẩn hóa.

Purge mọi sample ở phần trước có label interval chạm phần sau; embargo tối
thiểu bằng horizon lớn nhất của comparison quanh boundary. Kiểm interval theo
lịch giao dịch và thông tin availability, không chỉ trừ 5 ngày dương lịch.
Chọn scaler/features/threshold/peer schema ở phần được phép; không dùng test
để sửa prompt rồi tiếp tục gọi đó là test chưa thấy.

Selection trước khi biết return: nguồn/coverage/niêm yết/ngành/khả dụng,
calendar lookback và disclosure types. Không dùng actual_return, độ lớn return,
khả năng model đúng hoặc gold support tốt để chọn mẫu. Lưu sample-flow counts:
collected→quarantined→eligible→label-available→processed→answered/abstained/failed.
Ghi mọi mẫu bị loại và lý do; freeze sample IDs và hash trước chạy matrix.

## Metric: định nghĩa trước kết quả

| Nhóm | Công thức/mẫu số | Ghi chú bắt buộc |
|---|---|---|
| Coverage | answered / tất cả mẫu eligible có label | failure và abstention báo riêng; không giấu mẫu khó |
| Macro-F1 | trung bình F1 của UP/DOWN trên answered | zero-division policy=0; full-vs-common answered subset; coverage curves |
| Balanced accuracy | (TPR_UP + TPR_DOWN)/2 trên answered | absent class -> unavailable, không tự bù |
| MCC | (TP·TN−FP·FN)/sqrt((TP+FP)(TP+FN)(TN+FP)(TN+FN)) | denominator 0 -> N/A, không claim perfect |
| Brier/ECE | Brier=mean((p_UP−y_UP)^2); ECE=sum_b (n_b/N)·abs(mean_b(y_UP)−mean_b(p_UP)) | N answered có probability hợp lệ; bins theo p_UP chọn trước; reliability/coverage |
| Retrieval P@k / recall | gold relevant versions trong top-k / k; / total gold relevant eligible | query gold, gold version, cutoff cố định; xử lý top<k ghi trước |
| Citation validity | valid citations / tất cả citations phát ra | source/version/quote/locator/time; không chứng minh semantic support |
| Claim support | human-supported factual claims / tất cả factual claims | support/contradicted/insufficient rubric; không model tự chấm duy nhất |
| Evidence coverage | gold-required claims có supporting evidence / total gold-required claims | không đồng nhất nhiều citations với chất lượng |
| Unsupported rate | contradicted hoặc insufficient factual claims / all factual claims | confidence không thay ground truth |
| Numeric error | claims định lượng sai value/unit/period/scope/calculation / numeric claims | sai scope và sai đơn vị đều tính lỗi |
| Future exposure | violating deliveries / all agent-visible evidence deliveries | delivery=(sample,agent-call,version/chunk); lặp qua calls đếm lại; blocked không là exposed |
| Version error | wrong selected versions / gold record-cutoff selections | gold original/revised; quarantine báo riêng |
| Net/gross return | equity_last/equity_first−1 | net sau costs; index price-vs-total return rõ |
| Annualized return | (equity_last/equity_first)^(365.25/elapsed_days)−1 | cảnh báo period ngắn; không suy rộng 5 phiên thành kết quả năm chắc chắn |
| Sharpe/volatility | mean(daily excess)/sd·sqrt(A); sd·sqrt(A) | A phiên/năm và rf scenario đăng ký; sd0 -> N/A |
| Sortino | mean(r_daily−target)/sqrt(mean(min(r_daily−target,0)^2))·sqrt(A) | mẫu số dùng tất cả phiên; target/annual conversion đăng ký; downside0 -> N/A |
| Max drawdown | max_t(1−equity_t/running_max_t) | positive loss magnitude |
| Turnover | sum absolute traded notional / mean NAV | gọi two-sided; không đổi hệ số 1/2 giữa arms |
| Relative return | return(strategy)−return(comparator) | không gọi Jensen alpha nếu không regression |
| System | median/p95 per sample/call; tokens; peak RAM/VRAM; retries/attempts, failures/samples | tính cả warm-up/cold start riêng; tất cả attempts, không chỉ thành công |

Exposure denominator bằng 0 -> N/A, không "0% leakage" khi agent không nhìn
bằng chứng nào. Future blocked count là riêng. Audit chỉ chứa candidate info
không chứng minh delivered context; phải log context hash/IDs tại adapter.
ABSTAIN không bị bịa nhãn; so coverage-risk và cùng answered subset để tránh
phương pháp từ chối hết mẫu khó được gọi là tốt hơn. Các failure vẫn tính vào
coverage/system và sample-flow; điều kiện denominator phải xuất cùng metrics.

## Rubric gold/human

Pilot target 24 tài liệu/case thật, ≥3 ngành, có positive/negative numbers,
tables, revisions/late publication và thiếu bằng chứng. Chọn theo loại tài
liệu/mốc/ngành, không chọn theo actual return. Gold evidence gồm IDs/version,
locators và relevant/non-relevant cho query; gold claim gồm type/numbers/units,
support label và reasoning giải thích ngắn. Annotation không đọc model output
để quyết định trước gold relevance; blind arm/model khi chấm report nếu khả thi.

| Dimension | Điểm 0 | Điểm 1 | Điểm 2 |
|---|---|---|---|
| Grounding | claim sai/không có nguồn | một phần có nguồn, còn thiếu | claim quan trọng có hỗ trợ đúng revision |
| Số liệu | sai giá trị/đơn vị/scope | đúng phần lớn, thiếu checks | value/unit/period/arithmetic đúng |
| Temporal fidelity | dùng future/wrong revision | không future nhưng proof thiếu | eligibility và version có bằng chứng |
| Completeness | bỏ driver/risk chính | có nhưng thiếu một nhóm | coverage các mục gold-required |
| Uncertainty | khẳng định khi thiếu/xung đột | có cảnh báo chung | giới hạn/ABSTAIN phù hợp bằng chứng |

Rubric không chấm hướng giá đúng chỉ vì narrative nghe thuyết phục. Gold human
không là khẳng định nhân quả chắc chắn. Nếu hai người chấm: Cohen kappa hoặc
weighted kappa cho labels phù hợp, report raw agreement và adjudication. Nếu
một người: công bố giới hạn, chấm lại một subset sau khoảng nghỉ và kiểm ngẫu
nhiên; không gọi là inter-rater agreement. Verifier errors so với gold, không
để chính backbone đánh giá mọi câu trả lời của nó như ground truth.

## Thống kê, failure và export

Primary paired contrasts đề xuất RQ1 exposure/version; RQ2 L2 vs HAF quality;
RQ3 HAF vs A5 unsupported claims; RQ4 HAF vs A2/A3 retrieval; RQ5 HAF vs A6
consistency. Preregister primary endpoints và Holm adjustment nếu nhiều primary
tests. Report effect sizes + 95% CI; block bootstrap theo thời gian/sự kiện,
cùng date block chứa mọi ticker và mọi arm. Block length chọn trên dev/correlation,
seed và replicate count cố định; chưa có số liệu để kết luận power/cỡ mẫu đủ.
P>0.05 không chứng minh tương đương; n nhỏ phải ghi inconclusive.

Lặp suy luận 3 lần trên subset được chọn trước để đo nondeterminism. Không
chọn run tốt nhất. Invalid JSON/OOM/timeout lưu attempt, raw response và failure;
không đổi model tự động. Alpha/relative-return decay và masking/counterfactual
chỉ là tín hiệu có confounding, không tự chứng minh đã nhớ/hết leakage.

Runner M6 phải xuất decisions.jsonl; claims/evidence/audit; metrics.csv kèm
denominators; equity_curve.csv; trades.csv; run_manifest.json; failure_report;
plots/tables từ runs thật. Mock/diagnostic/strict/conservative cohorts có run_kind
và directories riêng; aggregation từ chối trộn. Chưa có runner matrix ở mốc này.
