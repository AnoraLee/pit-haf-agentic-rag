# Ghi chú đọc bài và milestone baseline cho hướng PiT-HAF

Ngày cập nhật: 03/09/2026

> **Ghi chú lịch sử, đối chiếu lại 06/10/2026:** giữ nội dung đọc paper và kế hoạch cũ để truy nguyên. Đề xuất rút gọn/1–2 ngày và protocol Mỹ dưới đây không còn là kế hoạch hiện hành. Phạm vi đầy đủ với Việt Nam làm thị trường chính nằm trong [đề cương](de-cuong-nghien-cuu-pit-haf.md) và [hồ sơ nghiên cứu](research/README.md). Các claim về paper cần đọc cùng [ma trận kiểm chứng](research/02-literature-contributions.md); chưa tái hiện thí nghiệm của tác giả.

## 1. Kết luận nhanh cho milestone 1-2 ngày

Với mục tiêu có kết quả chạy và giao diện cơ bản trong 1-2 ngày, hướng khả thi nhất là:

1. Dùng các chiến lược định lượng trong **Look-Ahead-Bench** làm baseline không LLM: Buy & Hold, Equal Weight, Momentum 3 tháng, Mean Reversion 3 tháng và MA 50/100.
2. Dùng một **single-agent** hoặc **TradingAgents rút gọn** làm baseline LLM.
3. Xây bản đầu của **PiT-HAF** bằng retrieval có khóa thời gian, ba agent chuyên môn và một agent tổng hợp.
4. Chưa triển khai Neo4j, DRL hoặc MASTER trong vòng đầu. Có thể bổ sung sau khi pipeline tối thiểu đã chạy và được kiểm tra chống rò rỉ dữ liệu.

Tên làm việc phù hợp cho đề tài:

> **PiT-HAF: A Point-in-Time Hierarchical Agentic-RAG Framework for Financial Analysis and Decision Support**

Nếu “PiT-HAF” của nhóm có cách viết đầy đủ khác, chỉ cần đổi tên; kiến trúc và kế hoạch đánh giá bên dưới vẫn dùng được.

## 2. Bốn bài cốt lõi

### 2.1 MASTER: Market-Guided Stock Transformer for Stock Price Forecasting

**Bài toán.** Dự đoán lợi suất chuẩn hóa của nhiều cổ phiếu, có xét tương quan động giữa cổ phiếu và trạng thái thị trường.

**Kiến trúc.** Năm bước: market-guided gating, intra-stock aggregation, inter-stock aggregation, temporal aggregation và prediction. Dữ liệu gồm Alpha158, thông tin chỉ số thị trường, cửa sổ nhìn lại 8 ngày và nhãn lợi suất sau 5 ngày.

**Baseline và metric.** XGBoost, LSTM, GRU, TCN, Transformer, GAT, DTML; đánh giá bằng IC, ICIR, RankIC, RankICIR, annualized return và information ratio. Trên CSI300/CSI800, bài báo báo cáo MASTER đứng đầu phần lớn chỉ số.

**Giá trị cho khóa luận.** Đây là baseline định lượng mạnh để chứng minh rằng Agentic AI phải được so sánh với mô hình không LLM, không chỉ so với một LLM khác.

**Không phù hợp làm baseline đầu tiên.** [Kho mã nguồn MASTER](https://github.com/SJTU-DMTai/MASTER) dùng `pandas==1.5.3`, `torch==1.11.0`, phụ thuộc Qlib và dữ liệu tải riêng. Nhóm tác giả cũng ghi nhận vấn đề ở tập validation/test đã công bố và hướng dẫn vá lại. Việc tái hiện đúng có rủi ro vượt quá mốc 1-2 ngày.

### 2.2 CARAG: Context-Enriched Agentic RAG

**Bài toán.** Dự đoán hướng biến động giá sau earnings call ở các chân trời 1, 3, 7, 15 và 30 ngày giao dịch.

**Kiến trúc.** CARAG xây Causal-Temporal Knowledge Graph (CTKG) từ transcript và báo cáo tài chính. Fact có ticker, quý, loại, metric và value; reason được lưu riêng để biểu diễn quan hệ nhân quả. Ba agent chạy song song:

- Historic Performance: so sánh kết quả hiện tại với quá khứ của chính doanh nghiệp.
- Historic Earnings: kiểm tra doanh nghiệp đã đạt hay bỏ lỡ guidance trước đó.
- Competitor Analyst: so sánh với doanh nghiệp cùng ngành.

Synthesizer hợp nhất các memo và trả về hướng cùng độ tin cậy.

**Kiểm soát thời gian.** Tài liệu được sắp theo ngày công bố và truy vấn tại quý `t` chỉ dùng dữ liệu có ngày không vượt quá `t`. Tên doanh nghiệp/sản phẩm còn được che để giảm khả năng LLM nhớ kết quả lịch sử.

**Kết quả đáng chú ý.** Bài báo báo cáo Macro-F1 +1 ngày lần lượt 55,7% trên NASDAQ, 57,4% trên NYSE và 58,7% trên MAEC. Ablation cho thấy bỏ knowledge graph làm giảm kết quả nhiều hơn bỏ memory hoặc competitor agent. Full multi-agent tốt hơn biến thể single-agent CTKG khoảng 2,1-2,4% tương đối tùy tập dữ liệu. Backtest báo cáo annualized return 35,83% và Sharpe 1,64 trên mẫu 3.158 earnings calls.

**Giá trị cho khóa luận.** Đây là bài gần nhất với Agentic-RAG tài chính mà đề tài cần. Có thể kế thừa ba ý: fact có dấu thời gian, retrieval theo chiều dọc/lịch sử và chiều ngang/đối thủ, và phân tách agent trước khi tổng hợp.

**Chi phí tái hiện.** [Kho mã nguồn CARAG](https://github.com/luweihai/CARAG) có code, CSV, financial statements, prompt và kết quả mẫu; tuy nhiên bản đầy đủ cần OpenAI API và Neo4j. Bài báo ghi nhận khoảng 18.471 input tokens, 2.054 output tokens và thời gian trung vị khoảng 157 giây cho mỗi earnings call. Vì vậy nên chạy trên một tập nhỏ trước.

### 2.3 Look-Ahead-Bench

**Bài toán.** Đo look-ahead bias của LLM trong workflow giao dịch đầu-cuối thay vì chỉ hỏi đáp về dữ kiện lịch sử.

**Thiết kế.** So sánh hai giai đoạn sáu tháng có mức Buy & Hold gần nhau:

- P1: 01/04/2021-30/09/2021, nằm trong vùng có khả năng xuất hiện trong dữ liệu huấn luyện.
- P2: 01/07/2024-31/12/2024, dùng như giai đoạn hậu cutoff.

Universe gồm AAPL, MSFT, GOOGL, NVDA và TSLA. Hai đại lượng chính:

```text
alpha(period) = return(model, period) - return(buy_and_hold, period)
alpha_decay   = alpha(P2) - alpha(P1)
```

**Baseline.** Buy & Hold, Equal Weight, Momentum 3M, Mean Reversion 3M, MA 50/100 và Random Noise. Đây là phần dễ tái hiện nhất trong bốn bài.

**Điểm cần thận trọng.** Chỉ có năm cổ phiếu công nghệ vốn hóa lớn và hai giai đoạn, nên alpha decay âm là dấu hiệu cảnh báo chứ chưa tự nó chứng minh mô hình đã ghi nhớ dữ liệu. Ngoài ra, [repository Look-Ahead-Bench](https://github.com/benstaf/lookaheadbench) hiện có cấu trúc React/Vite cho leaderboard nhưng không thấy mã Python tái hiện benchmark trong cây mã nguồn công khai. Vì vậy nên tự cài lại các baseline định lượng ngắn gọn.

### 2.4 ElliottAgents

**Bài toán.** Kết hợp Elliott Wave Principle với LLM multi-agent để phát hiện mẫu sóng và sinh khuyến nghị đầu tư.

**Kiến trúc.** Bảy agent: Coordinator, Data Engineer, Elliott Waves Analyst, Backtester, Technical Analysis Expert, Investment Advisor và Report Writer. Hệ thống dùng yfinance, LangGraph, RAG/knowledge graph, chart tools và thành phần DRL/backtesting.

**Kết quả.** Bài báo đánh giá các mẫu 1-2-3-4 và 1-2-3-4-5 trên dữ liệu ngày/giờ. Trên sáu mã được báo cáo, việc thêm backtesting làm tăng tỷ lệ dự đoán đúng; mức tăng tối đa được tác giả mô tả là khoảng 16 điểm phần trăm.

**Giá trị cho khóa luận.** Phù hợp để tham khảo cách chia vai trò, luồng điều phối và cách trình bày output có chart, mức hỗ trợ/kháng cự, mục tiêu và rủi ro.

**Không phù hợp làm baseline đầu tiên.** Quy tắc gán sóng Elliott mang tính chủ quan; số mẫu phát hiện theo từng mã nhỏ; mô tả train/test của DRL và cross-validation chưa đủ chi tiết để loại trừ leakage; bài báo không đưa ra baseline thống kê mạnh hay chi phí giao dịch. Nên coi đây là nguồn thiết kế giao diện và agent flow, không phải chuẩn thực nghiệm chính. Xem [bài ElliottAgents](https://arxiv.org/abs/2506.16813).

## 3. Các bài nên đọc thêm

### Ưu tiên 1: đọc ngay

1. **TradingAgents: Multi-Agents LLM Financial Trading Framework** - kiến trúc đầy đủ, mã nguồn đang được duy trì, hỗ trợ nhiều LLM và local Ollama. Đây là baseline multi-agent dễ chạy hơn việc tự tái hiện ElliottAgents. [Paper](https://arxiv.org/abs/2412.20138) · [Code](https://github.com/TauricResearch/TradingAgents)
2. **Profit Mirage: Revisiting Information Leakage in LLM-based Financial Agents** - trực tiếp nối Look-Ahead-Bench với RAG, counterfactual simulation và đánh giá ngoài cutoff. Đây là nguồn quan trọng nhất để biện minh tính mới của PiT-HAF. [Paper](https://arxiv.org/abs/2510.07920)
3. **FinMem** - hữu ích cho thiết kế memory theo độ mới và mức quan trọng; có mã nguồn. [Paper](https://arxiv.org/abs/2311.13743) · [Code](https://github.com/pipiku915/FinMem-LLM-StockTrading)

### Ưu tiên 2: đọc sau khi baseline chạy

4. **Toward Expert Investment Teams: A Multi-Agent LLM System with Fine-Grained Trading Tasks** - nhấn mạnh task decomposition chi tiết và backtest có kiểm soát leakage trên cổ phiếu Nhật. [Paper](https://arxiv.org/abs/2602.23330)
5. **HedgeAgents** - hữu ích cho risk/hedging agents và cách tổ chức hội nghị agent, nhưng không phải lựa chọn tái hiện nhanh vì mã nguồn công khai chưa rõ ràng. [Paper](https://arxiv.org/abs/2502.13165)

## 4. Đề xuất phạm vi PiT-HAF

### Câu hỏi nghiên cứu

> Việc kết hợp retrieval có ràng buộc Point-in-Time với phân rã tác vụ đa tác tử có làm tăng độ chính xác, độ tin cậy bằng chứng và khả năng tổng quát ngoài knowledge cutoff so với LLM, RAG và multi-agent thông thường hay không?

### Kiến trúc tối thiểu

```text
User query + as_of_time
          |
          v
  Temporal Gate ------> loại mọi tài liệu có published_at > as_of_time
          |
          v
    Planner/Router
      /     |      \
     v      v       v
Historical Fundamental Technical/Market
Agent      Agent       Agent
      \     |      /
       v    v     v
     Evidence Verifier
            |
            v
   Risk + Synthesizer
            |
            v
 Decision + confidence + citations + audit log
```

Mỗi evidence bắt buộc có `source_id`, `published_at`, `available_at`, `as_of_time`, nội dung trích, và điểm relevance. Temporal Gate phải chạy **trước** embedding search; lọc sau retrieval vẫn có thể làm lộ tài liệu tương lai vào quá trình xếp hạng hoặc cache.

### Output chuẩn hóa

```json
{
  "ticker": "AAPL",
  "as_of_time": "2024-07-01T16:00:00-04:00",
  "horizon_days": 5,
  "decision": "BUY|HOLD|SELL",
  "direction_score": 0.0,
  "confidence": 0.0,
  "key_drivers": [],
  "risks": [],
  "evidence": [
    {
      "source_id": "...",
      "published_at": "...",
      "claim": "...",
      "quote": "..."
    }
  ],
  "agent_memos": {},
  "pit_audit": {
    "future_documents_seen": 0,
    "latest_allowed_timestamp": "..."
  }
}
```

## 5. Ma trận thực nghiệm

| ID | Hệ thống | Mục đích |
|---|---|---|
| B0 | Buy & Hold / Equal Weight | mốc thụ động |
| B1 | Momentum 3M / MA 50-100 | baseline định lượng mạnh, rẻ |
| B2 | Single LLM, không retrieval | đo kiến thức nội tại và narrative bias |
| B3 | Static RAG, không khóa thời gian | đo lợi ích và nguy cơ của retrieval |
| B4 | Multi-agent, không PiT gate | đo lợi ích của phân vai |
| Ours | PiT-HAF | hệ thống đầy đủ |

Metric tối thiểu:

- Dự đoán: Macro-F1, MCC, balanced accuracy.
- Giao dịch: cumulative return, annualized return, Sharpe, maximum drawdown, turnover và chi phí giao dịch.
- Point-in-Time: future-document rate, timestamp violation count và alpha decay.
- RAG: citation precision, evidence coverage và faithfulness trên một tập được gán nhãn thủ công.
- Hệ thống: latency, token usage và chi phí mỗi quyết định.

## 6. Kế hoạch 1-2 ngày

### Ngày 1: tạo baseline chạy được

1. Chọn universe năm mã giống Look-Ahead-Bench để giảm biến số.
2. Chuẩn hóa OHLCV theo ngày và cache thành CSV/Parquet.
3. Cài năm baseline định lượng; xuất `metrics.csv`, `equity_curve.csv` và `trades.csv`.
4. Chạy P1 và P2; tính alpha và alpha decay.
5. Chạy một single-agent trên 10-20 thời điểm đầu tiên, temperature 0, output JSON cố định.
6. Viết unit test khẳng định mọi tài liệu đầu vào có `available_at <= as_of_time`.

**Definition of done ngày 1:** một lệnh chạy toàn bộ baseline, tạo bảng metric và không có timestamp violation.

### Ngày 2: Agentic-RAG nhỏ và frontend

1. Dùng SQLite/Parquet + vector index nhỏ thay Neo4j trong prototype.
2. Triển khai ba agent: Historical/Fundamental, Technical/Market và Risk/Verifier; thêm Synthesizer.
3. Chạy trên 20-50 mẫu, lưu toàn bộ memo và evidence.
4. Frontend có năm khu vực:
   - form chọn ticker, `as_of_time` và horizon;
   - quyết định BUY/HOLD/SELL cùng confidence;
   - timeline hoạt động của agent;
   - evidence có ngày công bố và nguồn;
   - biểu đồ equity/alpha decay cùng PiT audit badge.
5. So sánh B1, B2, B3 và PiT-HAF trên cùng lát dữ liệu.

**Definition of done ngày 2:** người dùng chọn ticker/ngày, nhận quyết định có bằng chứng; giao diện hiển thị rõ không tài liệu tương lai nào được sử dụng.

## 7. Quyết định kỹ thuật nên chốt ngay

- **Baseline đầu tiên:** tự cài Look-Ahead-Bench quant strategies; không phụ thuộc repo hiện tại.
- **Baseline multi-agent:** TradingAgents bản cấu hình tối thiểu.
- **RAG prototype:** SQLite/Parquet trước, Neo4j sau.
- **Dữ liệu văn bản:** lấy một tập nhỏ earnings-call/financial-statement từ CARAG để demo; sau đó mới mở rộng.
- **MASTER:** để ở thí nghiệm mở rộng hoặc chỉ dùng làm đối chứng từ literature nếu không đủ tài nguyên tái hiện.
- **ElliottAgents:** dùng làm cảm hứng cho agent flow và giao diện; không dùng làm chuẩn chính về độ chính xác.

## 8. Rủi ro phải ghi trong khóa luận

1. Knowledge cutoff công bố của LLM không bảo đảm dữ liệu huấn luyện thực tế sạch tuyệt đối.
2. Alpha decay chịu ảnh hưởng của thay đổi regime, universe nhỏ và chiến lược phân bổ, không chỉ leakage.
3. Kết quả backtest phải bao gồm phí giao dịch, độ trễ công bố và thời điểm khớp lệnh T+1.
4. Không được dùng ngày kỳ báo cáo thay cho ngày tài liệu thực sự có sẵn trên thị trường.
5. LLM evaluation cần cố định prompt, temperature, model version và lưu raw response để tái lập.
6. Đây là hệ thống hỗ trợ nghiên cứu, không phải tư vấn đầu tư hay hệ thống giao dịch thật.
