# Đề cương nghiên cứu PiT-HAF

## 1. Định vị đề tài

### Tên đề xuất

**Tiếng Việt**

> Nghiên cứu các kỹ thuật LLM và Agentic-RAG nhận biết thời điểm để phát triển hệ thống Agentic AI đáng tin cậy cho phân tích và hỗ trợ quyết định tài chính

**Tiếng Anh**

> PiT-HAF: A Point-in-Time Hierarchical Agentic-RAG Framework for Trustworthy Financial Analysis and Decision Support

PiT-HAF là tên làm việc. Cách viết đầy đủ cần được điều chỉnh nếu nhóm nghiên cứu đã quy định ý nghĩa khác cho chữ HAF.

## 2. Phân biệt hai mục tiêu

### Milestone kỹ thuật trong 1-2 ngày

Mục tiêu là chứng minh pipeline chạy xuyên suốt:

- tải hoặc đọc dữ liệu đã cache;
- chạy ít nhất ba baseline định lượng;
- sinh một quyết định mẫu theo schema cố định;
- lưu metric và nhật ký;
- frontend đọc được kết quả và hiển thị biểu đồ;
- có kiểm tra đơn giản rằng không dùng dữ liệu sau `as_of_time`.

Milestone này **không phải đóng góp khoa học cuối cùng** và không dùng để kết luận PiT-HAF tốt hơn các phương pháp khác.

### Mục tiêu khóa luận trong nhiều tháng

Thiết kế, hiện thực và đánh giá một framework Agentic-RAG cho tài chính có khả năng:

1. bảo đảm tính Point-in-Time trên toàn bộ vòng đời dữ liệu;
2. kết hợp dữ liệu có cấu trúc và phi cấu trúc;
3. phân rã tác vụ theo cấu trúc agent phân cấp;
4. kiểm tra bằng chứng, xung đột và rủi ro trước khi ra quyết định;
5. đánh giá đồng thời chất lượng dự đoán, giao dịch, retrieval, độ tin cậy và chi phí hệ thống.

## 3. Khoảng trống nghiên cứu

Từ các bài đã đọc, có thể hình thành khoảng trống sau:

- Các hệ thống multi-agent như ElliottAgents và TradingAgents tập trung vào phân vai và hiệu quả giao dịch, nhưng kiểm soát look-ahead bias chưa phải thành phần kiến trúc trung tâm.
- MASTER cung cấp đối chứng định lượng mạnh nhưng không giải quyết retrieval, bằng chứng hay sự nhiễm kiến thức tương lai của LLM.
- CARAG có causal-temporal knowledge graph, lọc tài liệu theo thời điểm và entity masking, nhưng chưa xây một giao thức kiểm toán Point-in-Time tổng quát xuyên qua retrieval, memory, tool calls, cache và agent communication.
- Look-Ahead-Bench đo alpha decay trong workflow giao dịch nhưng chưa cung cấp một kiến trúc Agentic-RAG hoàn chỉnh để ngăn leakage; benchmark hiện còn hẹp về số mã và số regime.
- Profit Mirage/FactFin đặt vấn đề leakage và counterfactual reasoning, mở ra nhu cầu kết hợp kiểm soát thời gian, truy xuất bằng chứng và kiểm định phản thực trong một framework thống nhất.

Khoảng trống có thể phát biểu:

> Chưa có đủ bằng chứng về việc một kiến trúc Agentic-RAG được kiểm soát Point-in-Time ở mức hệ thống có cải thiện khả năng tổng quát ngoài cutoff, chất lượng bằng chứng và hiệu quả điều chỉnh rủi ro so với RAG hoặc multi-agent thông thường hay không.

Đây là **giả thuyết về khoảng trống**, cần được xác nhận bằng systematic literature review trước khi tuyên bố là đóng góp mới.

## 4. Đóng góp dự kiến

### C1. Bi-temporal financial evidence model

Mỗi dữ kiện có ít nhất hai mốc thời gian:

- `event_time`: thời điểm sự kiện kinh tế diễn ra;
- `available_time`: thời điểm thông tin thực sự có thể quan sát bởi nhà đầu tư.

Hệ thống chỉ được sử dụng bằng chứng có `available_time <= as_of_time`. Cách biểu diễn này xử lý trường hợp báo cáo quý mô tả sự kiện cũ nhưng được công bố muộn hơn.

### C2. Time-gated hybrid retrieval

Pipeline truy xuất theo thứ tự:

```text
Temporal filtering
    -> metadata/structured filtering
    -> semantic or graph retrieval
    -> reranking
    -> evidence packaging
```

Temporal gate chạy trước semantic search và trước khi đưa dữ liệu vào cache/memory của agent.

### C3. Hierarchical agent framework

Các agent tầng chuyên môn tạo memo độc lập; verifier kiểm tra bằng chứng và timestamp; risk agent kiểm tra độ chắc chắn; synthesizer chỉ được sử dụng các claim đã qua xác minh.

### C4. Point-in-Time audit ledger

Mỗi lần retrieval, tool call, memory read và agent handoff sinh một bản ghi có:

- query;
- thời điểm quyết định;
- danh sách document ID;
- `available_time` của từng tài liệu;
- agent sử dụng tài liệu;
- claim được tạo;
- trạng thái xác minh.

Ledger cho phép tính trực tiếp tỷ lệ vi phạm thời gian và tái lập từng quyết định.

### C5. Evaluation protocol

Đánh giá cùng lúc:

- dự đoán;
- hiệu quả giao dịch sau phí;
- look-ahead leakage;
- retrieval và faithfulness;
- robustness qua regime;
- chi phí và độ trễ.

## 5. Câu hỏi và giả thuyết nghiên cứu

### RQ1 - Point-in-Time control

Time-gated retrieval có làm giảm leakage và alpha decay so với static RAG không?

**H1:** PiT retrieval làm giảm đáng kể timestamp violation và giảm độ suy giảm ngoài cutoff.

### RQ2 - Agent decomposition

Phân rã tác vụ phân cấp có tốt hơn single-agent khi cùng dùng một tập bằng chứng không?

**H2:** PiT-HAF cải thiện Macro-F1/MCC và evidence coverage so với PiT-RAG single-agent.

### RQ3 - Verification

Verifier và risk agent có giảm hallucination, unsupported claims và quyết định quá tự tin không?

**H3:** Verifier giảm unsupported-claim rate và cải thiện calibration, đổi lại latency và token cost tăng.

### RQ4 - Causal-temporal retrieval

Kết hợp truy xuất theo lịch sử doanh nghiệp, đối thủ cùng ngành và quan hệ nguyên nhân có tốt hơn vector retrieval thuần túy không?

**H4:** Hybrid retrieval cải thiện evidence precision và hiệu quả ở các chân trời sau earnings announcement.

### RQ5 - Generalization

Kết quả có giữ được qua nhiều giai đoạn thị trường, nhóm vốn hóa và ngành hay không?

**H5:** Lợi ích của PiT-HAF vẫn tồn tại sau khi thay đổi regime và universe, nhưng mức cải thiện sẽ khác nhau theo chất lượng dữ liệu.

## 6. Kiến trúc đề xuất

```text
                         +----------------------+
User task + as_of_time ->| Planner/Task Router  |
                         +----------+-----------+
                                    |
                     +--------------v---------------+
                     | Point-in-Time Data Gateway   |
                     | event_time / available_time  |
                     +--------------+---------------+
                                    |
                 +------------------v------------------+
                 | Hybrid Retriever                   |
                 | structured + vector + graph/time   |
                 +-----+---------------+---------------+
                       |               |
          +------------v--+         +--v----------------+
          | Historical &  |         | Market/Technical  |
          | Fundamental   |         | Agent             |
          | Agent         |         +-------------------+
          +-------+-------+                   |
                  |                +----------v----------+
                  +--------------->| Evidence Verifier  |
                                   +----------+----------+
                                              |
                                   +----------v----------+
                                   | Risk/Uncertainty    |
                                   | Agent               |
                                   +----------+----------+
                                              |
                                   +----------v----------+
                                   | Synthesizer         |
                                   +----------+----------+
                                              |
                         Decision + evidence + audit log
```

Kiến trúc có thể mở rộng thêm News/Sentiment Agent và Peer Agent sau khi bản tối thiểu ổn định.

## 7. Dữ liệu đề xuất

### Tập chính: thị trường Mỹ

Lý do chọn làm thí nghiệm chính:

- có earnings-call transcript, SEC filings và OHLCV;
- dễ đối chiếu CARAG, TradingAgents và Look-Ahead-Bench;
- thuận lợi cho tái lập và so sánh quốc tế.

Các lớp dữ liệu:

1. giá và khối lượng theo ngày;
2. earnings-call transcript;
3. 10-Q/10-K và financial statements;
4. ngày/giờ công bố thực tế;
5. sector/peer mapping;
6. tùy chọn: tin tức có timestamp đáng tin cậy.

### Tập kiểm chứng mở rộng: Việt Nam

Có thể dùng như case study cuối khóa luận nếu thu thập được dữ liệu công bố đáng tin cậy. Không nên dùng làm tập chính ngay từ đầu vì transcript, timestamp và dữ liệu doanh nghiệp có thể thiếu hoặc khó chuẩn hóa. Giá trị của tập này là chứng minh khả năng chuyển miền, không nhất thiết phải tái tạo toàn bộ benchmark Mỹ.

## 8. Baseline đầy đủ

### Nhóm định lượng

- Buy & Hold.
- Equal Weight.
- Momentum 3M.
- Mean Reversion 3M.
- MA Crossover 50/100.
- XGBoost hoặc LightGBM với feature kỹ thuật.
- MASTER nếu tái hiện được ổn định ở giai đoạn sau.

### Nhóm LLM/RAG

- LLM không retrieval.
- LLM + wide context.
- Static vector RAG.
- Single-agent Agentic-RAG.
- TradingAgents hoặc framework multi-agent tương đương.
- Multi-agent không PiT gate.
- PiT single-agent RAG.
- PiT-HAF đầy đủ.

## 9. Ablation bắt buộc

| Biến thể | Thành phần bị loại | Câu hỏi kiểm tra |
|---|---|---|
| A1 | Temporal gate | leakage tăng bao nhiêu? |
| A2 | Causal/graph retrieval | vector-only có đủ không? |
| A3 | Peer context | thông tin ngành đóng góp bao nhiêu? |
| A4 | Agent hierarchy | single-agent có tương đương không? |
| A5 | Verifier | hallucination và calibration thay đổi thế nào? |
| A6 | Memory | historical consistency thay đổi thế nào? |
| A7 | Entity masking | mô hình có dựa vào ký ức về ticker không? |
| A8 | Counterfactual test | quyết định có phản ứng đúng với biến đổi nguyên nhân không? |

## 10. Metric

### Prediction

- Macro-F1;
- MCC;
- balanced accuracy;
- Brier score hoặc expected calibration error;
- kết quả theo horizon 1/3/7/15/30 ngày.

### Trading

- cumulative và annualized return;
- Sharpe/Sortino;
- maximum drawdown;
- volatility;
- turnover;
- return sau transaction cost;
- alpha so với Buy & Hold/Equal Weight.

### Point-in-Time và leakage

- timestamp violation rate;
- future-document exposure rate;
- alpha decay qua các period;
- độ nhạy khi che ticker/entity;
- chênh lệch trước/sau knowledge cutoff;
- hiệu năng trên counterfactual inputs.

### RAG và giải thích

- retrieval precision/recall trên tập gán nhãn;
- citation correctness;
- evidence coverage;
- unsupported claim rate;
- faithfulness được chấm thủ công và bằng rubric cố định.

### Hệ thống

- latency theo agent và toàn pipeline;
- input/output tokens;
- chi phí mỗi quyết định;
- failure/retry rate.

## 11. Thiết kế thực nghiệm chống leakage

1. Mọi bản ghi dùng `available_time`, không dùng riêng kỳ tài chính hoặc ngày sự kiện.
2. Tách train/validation/test theo thời gian; không random split.
3. Feature normalization chỉ fit trên train.
4. Retrieval index cho thời điểm `t` chỉ chứa dữ liệu quan sát được tại `t` hoặc dùng pre-filter cứng trước truy vấn.
5. Backtest khớp lệnh ở thời điểm thực tế có thể hành động, ví dụ T+1 sau earnings call.
6. Tính phí giao dịch và slippage theo nhiều kịch bản.
7. Cố định model snapshot, prompt, temperature và seed; lưu raw response.
8. Đánh giá ít nhất ba regime và nhiều ngành; không chỉ năm mã công nghệ.
9. Dùng block bootstrap hoặc kiểm định phù hợp với chuỗi thời gian thay vì coi mọi quyết định độc lập.
10. Báo cáo cả kết quả âm và lỗi pipeline, không chỉ chọn những giao dịch tốt.

## 12. Lộ trình nhiều tháng

### Giai đoạn 1 - Khảo sát và đặc tả

- systematic literature review;
- chốt task, dataset và định nghĩa Point-in-Time;
- viết data card, threat model và evaluation protocol;
- tái hiện baseline định lượng.

### Giai đoạn 2 - Data engineering

- xây bi-temporal schema;
- ingestion cho transcript, filings và market data;
- chuẩn hóa `available_time`;
- test chống future leakage;
- tạo các time-sliced index.

### Giai đoạn 3 - Baseline LLM/RAG

- LLM-only, wide-context và static RAG;
- single-agent PiT-RAG;
- đo prediction, retrieval, latency và cost;
- hoàn thiện frontend quan sát evidence và audit.

### Giai đoạn 4 - PiT-HAF

- specialist agents;
- verifier và risk agent;
- hierarchical synthesis;
- memory có timestamp;
- audit ledger và structured output.

### Giai đoạn 5 - Thực nghiệm lớn

- full comparison;
- ablation;
- multi-regime và multi-sector;
- entity masking và counterfactual stress tests;
- kiểm định thống kê.

### Giai đoạn 6 - Hoàn thiện khóa luận

- phân tích lỗi định tính;
- viết chương phương pháp và thực nghiệm;
- hoàn thiện demo;
- reproducibility package;
- chuẩn bị slide và kịch bản bảo vệ.

## 13. Milestone 48 giờ đầu tiên

### Backend/baseline

- Một lệnh chạy Buy & Hold, Equal Weight, Momentum 3M và MA 50/100.
- Hai period mẫu theo Look-Ahead-Bench.
- File kết quả chuẩn: `metrics.csv`, `equity_curve.csv`, `trades.csv`.
- Một adapter single-agent có thể chạy bằng API hoặc mock mode.
- Schema quyết định thống nhất cho các phiên bản sau.
- Test `available_time <= as_of_time`.

### Frontend

- chọn ticker/universe, ngày quyết định và horizon;
- nút chạy baseline;
- bảng return, alpha, Sharpe, drawdown và alpha decay;
- equity curve;
- vùng quyết định mẫu cùng evidence;
- PiT audit badge;
- trang hoặc panel theo dõi agent, ban đầu có thể chỉ đọc log mẫu.

Frontend 48 giờ là **bề mặt quan sát thí nghiệm**, không phải sản phẩm đầu tư hoàn chỉnh. Thiết kế từ đầu để sau này thay mock output bằng PiT-HAF thật mà không phải viết lại giao diện.

## 14. Tiêu chí để khóa luận được xem là đủ mạnh

Khóa luận không nên chỉ dừng ở “xây được nhiều agent”. Tối thiểu cần có:

1. định nghĩa Point-in-Time rõ và threat model cho leakage;
2. một thành phần kỹ thuật mới hoặc cách kết hợp có căn cứ;
3. ít nhất sáu baseline/biến thể có ý nghĩa;
4. ablation cho từng thành phần chính;
5. đánh giá nhiều regime/ngành và sau transaction cost;
6. metric cho dự đoán, RAG, leakage và hệ thống;
7. kiểm định thống kê và phân tích lỗi;
8. mã nguồn, cấu hình, dữ liệu hoặc hướng dẫn tái lập;
9. demo hiển thị bằng chứng và audit trail;
10. giới hạn nghiên cứu được trình bày trung thực.
