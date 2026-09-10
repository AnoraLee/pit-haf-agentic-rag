# GIẢI MÃ NHỊP ĐẬP CỦA THỊ TRƯỜNG

## CARAG: Agentic RAG tăng cường ngữ cảnh để dự báo cú sốc giá sau công bố kết quả kinh doanh

**Tác giả:** Chenhui Li (Millennium Management LLC), Weihai Lu (Đại học Bắc Kinh)

**Nguồn:** EACL 2026, Long Papers, trang 3055-3073

**Mã nguồn, dữ liệu và prompt:** https://github.com/luweihai/CARAG

> Bản dịch tiếng Việt phục vụ học tập và nghiên cứu. Các thuật ngữ chuẩn như earnings call, Agentic RAG, zero-shot, backtest, Macro-F1, MCC và Sharpe được giữ lại khi việc dịch hoàn toàn có thể làm mất sắc thái kỹ thuật. Nhãn bên trong các hình được giữ nguyên như bản gốc; chú thích hình và phần diễn giải đã được dịch.

# Tóm tắt

Dự báo chính xác các biến động giá cổ phiếu lớn sau khi doanh nghiệp công bố kết quả kinh doanh là một thách thức lâu năm. Các phương pháp hiện có - từ từ điển cảm xúc, encoder được fine-tune cho tới LLM độc lập - thường thiếu khả năng suy luận theo thời gian và quan hệ nhân quả, đồng thời dễ mắc thiên lệch tường thuật khi lặp lại giọng điệu quá lạc quan của ban lãnh đạo.

Chúng tôi giới thiệu **Context-Enriched Agentic RAG (CARAG)**, một khung truy xuất tăng cường sử dụng một nhóm các agent LLM hợp tác với nhau. Mỗi agent chuyên trách một nhiệm vụ phân tích riêng: đánh giá kết quả lịch sử, thẩm định độ đáng tin của guidance, hoặc so sánh với các doanh nghiệp cùng ngành. Các agent truy xuất bằng chứng có cấu trúc từ **Causal-Temporal Knowledge Graph (CTKG)** được xây dựng từ báo cáo tài chính và earnings call, nhờ đó có thể suy luận dựa trên bằng chứng và giàu ngữ cảnh.

Thiết kế này giảm hiện tượng ảo giác của LLM và tạo ra dự báo khách quan hơn. Không cần huấn luyện riêng cho tác vụ, hệ thống đạt kết quả zero-shot tốt nhất hiện tại trên các bộ dữ liệu NASDAQ, NYSE và MAEC; vượt cả LLM lớn hơn lẫn các mô hình fine-tune xét theo Macro-F1, MCC và Sharpe; đồng thời vượt các chuẩn thị trường S&P 500 và Nasdaq trong cùng kỳ dự báo. Toàn bộ mã nguồn, dữ liệu và prompt được công bố tại kho mã của dự án.

# 1. Giới thiệu

Các cuộc gọi công bố kết quả kinh doanh đưa ra một lượng thông tin khổng lồ có ảnh hưởng sâu sắc tới thị trường tài chính (Price et al., 2012). Những sự kiện này bao gồm kết quả kinh doanh và định hướng của ban lãnh đạo, thường kích hoạt biến động giá cổ phiếu đáng kể chỉ trong một ngày. Dữ liệu giàu có nhưng phi cấu trúc trong các cuộc gọi - gồm phần trình bày chuẩn bị trước, hỏi đáp và phát biểu hướng tới tương lai - tạo ra một bài toán mô hình hóa dự báo rất khó (Chen et al., 2022; Wu et al., 2023).

Sau thành công nổi bật của học sâu ở nhiều tác vụ khác (Lu et al., 2025; Xie et al., 2026, 2025a; Lu and Yin, 2025; Cui et al., 2025), ngày càng nhiều nghiên cứu đưa kiến trúc học sâu vào dự báo giá cổ phiếu từ earnings call. Cùng với các đột phá của Transformer (Zhu et al., 2026) và kỹ thuật pre-training (Tong et al., 2025; Zhang et al., 2025), các phương pháp dự báo cú sốc giá đã phát triển từ phân tích cảm xúc dựa trên từ điển (Loughran and McDonald, 2011), qua Transformer chuyên biệt cho tài chính như FinBERT (Araci, 2019), đến Transformer phân cấp (Koval et al., 2023).

Các nghiên cứu gần đây cho thấy encoder dựa trên đồ thị (Medya et al., 2022; Liu et al., 2024) có khả năng ánh xạ các quan hệ ẩn trong mạng lưới cổ phiếu. Tuy giúp hiểu ngữ cảnh tốt hơn, các mô hình này không thể thực hiện suy diễn logic theo chuỗi hoặc hợp nhất hiểu biết từ những nguồn dữ liệu không đồng nhất. Các cách tiếp cận dùng LLM gần đây cho thấy triển vọng trong việc tổng hợp thông tin từ nhiều loại tài liệu khác nhau (Chang et al., 2023; Ni et al., 2024). Tuy vậy, khi chỉ xử lý riêng lẻ một transcript của earnings call, cả các phương pháp hiện có lẫn LLM độc lập đều gặp hai vấn đề nền tảng:

- **Thiếu suy luận thời gian và nhân quả.** Mô hình độc lập không thể đặt thông tin mới vào đúng bối cảnh lịch sử. Chẳng hạn, chúng không đối chiếu mức tăng trưởng doanh số 16% vừa công bố với mức 55% trong các quý trước, như trường hợp Five Below ở quý IV/2021. Chúng cũng không thể tự kiểm chứng những nguyên nhân mà ban lãnh đạo nêu ra cho kết quả kinh doanh, nên thường chấp nhận các tường thuật đã được chủ ý điều chỉnh để tác động đến nhận thức (Li, 2010). Việc thiếu suy luận có cấu trúc (Cao et al., 2023) khiến mô hình không phân biệt được sức mạnh thực sự của doanh nghiệp với việc tăng trưởng chỉ đang giảm tốc.

- **Suy luận đơn khối và thiên lệch tường thuật.** Một mô hình duy nhất xử lý thông tin qua một lăng kính đơn khối, do đó rất dễ bị cuốn theo tường thuật được ban lãnh đạo trau chuốt và nảy sinh thiên lệch lạc quan (Cui and Zhai, 2023). Mô hình thiếu cách đánh giá linh hoạt và phản biện của chuyên gia con người, vốn tổng hợp nhiều góc nhìn như kết quả lịch sử và so sánh với doanh nghiệp cùng ngành để hình thành phán đoán cân bằng, vững chắc.

[[FIGURE:figure-1.png|Hình 1. Bên trái: so sánh theo chiều dọc đối chiếu phát biểu quý I/2022 của Meta với các quý trước. Bên phải: so sánh theo ngữ cảnh liên kết khoản lỗ mà Meta báo cáo với earnings call quý I/2022 của Apple, qua đó neo lời giải thích nhân quả vào công bố bên ngoài.]]

Để khắc phục các hạn chế trên, chúng tôi đề xuất **Context-Enriched Agentic RAG (CARAG)**. Khung này mô phỏng sự phân công lao động trong đầu tư cơ bản: các chuyên gia cộng tác về định giá nội tại và tỷ lệ chiết khấu, định giá tương đối so với doanh nghiệp cùng ngành, và tổng hợp ở cấp ngành. CARAG kết hợp điều phối đa agent với một cơ sở tri thức có cấu trúc (Kadan et al., 2012; Bradley et al., 2017; Groysberg et al., 2013).

Trước hết, chúng tôi xây dựng **Causal-Temporal Knowledge Graph (CTKG)** từ báo cáo tài chính lịch sử và earnings call trước đó để làm bộ nhớ dài hạn. Sau đó, một nhóm agent LLM chuyên trách hợp tác để phân tích earnings call mới. Mỗi agent nhận một chỉ thị riêng: đánh giá kết quả lịch sử, đối chiếu chuẩn cùng ngành, hoặc rà soát guidance trước đây; đồng thời truy vấn CTKG để neo phân tích vào bằng chứng. Cuối cùng, một agent tổng hợp tích hợp các bản ghi nhớ phân tích này thành một dự báo duy nhất có nhận biết ngữ cảnh.

Các đóng góp chính của nghiên cứu gồm:

1. Đề xuất khung **Context-Enriched Agentic RAG (CARAG)**. Theo hiểu biết của tác giả, đây là nghiên cứu đầu tiên trong lĩnh vực này kết hợp suy luận nhân quả và suy diễn theo thời gian nhằm nâng độ chính xác của dự báo giá cổ phiếu.

2. Đề xuất **Causal-Temporal Knowledge Graph (CTKG)** để mã hóa dữ liệu tài chính với cấu trúc thời gian và nhân quả; đồng thời giới thiệu **khung suy luận đa agent** phân tích earnings call từ nhiều góc nhìn để giảm thiên lệch suy luận của một mô hình duy nhất.

3. Công bố một bộ dữ liệu được tuyển chọn, liên kết hàng nghìn transcript earnings call với báo cáo tài chính tương ứng và biến động giá ở nhiều chân trời; từ đó tạo ra một benchmark có thể tái lập cho nghiên cứu NLP trong tài chính.

4. Trên các bộ NASDAQ, NYSE và MAEC, khung zero-shot đạt kết quả tốt nhất hiện tại, vượt LLM lớn, encoder fine-tune và mô hình căn chỉnh âm thanh - văn bản trong dự báo cú sốc giá. Backtest hai năm cho lợi suất thường niên hóa khoảng **36%** và **Sharpe 1,64** trên mẫu 3.158 cuộc gọi.

# 2. Công trình liên quan

## 2.1. Dự báo giá từ earnings call

Dự báo hiện tượng trôi dạt sau công bố lợi nhuận (**post-earnings announcement drift - PEAD**) - một bất thường thị trường trong đó giá tiếp tục dịch chuyển sau bất ngờ lợi nhuận (Ball and Brown, 1968) - đã phát triển từ từ điển cảm xúc (Stone et al., 1966; Loughran and McDonald, 2011) và đặc trưng transcript được thiết kế thủ công (Chin and Fan, 2023) sang các kiến trúc học máy tinh vi hơn (Peng, 2025; Wang et al., 2025).

Các encoder dựa trên Transformer như FinBERT giúp cải thiện phân tích nhưng bị giới hạn độ dài đầu vào, buộc phải cắt bớt transcript dài (Araci, 2019; Huang et al., 2024). Các mô hình phân cấp khắc phục vấn đề này bằng cách phân đoạn transcript (Koval et al., 2023; Zaheer et al., 2020). Những hướng hiện đại khác dùng học đa nhiệm để dự báo PEAD (Zhu et al., 2025), hoặc tích hợp dữ liệu đa phương thức để dự báo ngay trong cuộc gọi (Ghosh et al., 2025).

Gần đây, các mô hình đồ thị như StockGNN và ECHO-GL được phát triển để nắm bắt quan hệ giữa doanh nghiệp bằng cách xây dựng mạng khái niệm từ transcript (Medya et al., 2022; Liu et al., 2024). Dù vậy, các phương pháp hiện có vẫn khó thực hiện suy luận nhiều bước và tổng hợp chéo nguồn. CARAG hợp nhất tường thuật trong earnings call với dữ liệu tài chính có cấu trúc để cho phép suy diễn thời gian và nhân quả vượt quá khả năng của mô hình đơn khối.

## 2.2. Agent LLM

Cùng với sự phát triển của LLM, khung đa agent ngày càng nổi bật và cho thấy hiệu quả trên nhiều ứng dụng (Zhang et al., 2025; Chen et al., 2024; Wei et al., 2025a; Zhao et al., 2025; Wei et al., 2025b; Xie et al., 2025b). Dự báo earnings call bằng LLM vẫn đang ở giai đoạn đầu. Nghiên cứu ban đầu (Chang et al., 2023) cho thấy điểm cảm xúc thô của ChatGPT trong khoảng [-10, 10] có sức mạnh dự báo đối với hiện tượng trôi dạt giá. Các nghiên cứu sau ghi nhận độ chính xác tăng khi LLM có cửa sổ ngữ cảnh rộng cùng đọc transcript, tỷ số tài chính và giá (Ni et al., 2024), nhưng vẫn chỉ dùng prompt một lượt, không có truy xuất, lặp hoặc hợp tác giữa agent.

Nhiều nghiên cứu đã khảo sát lợi ích của các agent hợp tác có bộ nhớ chung và cơ chế phản hồi giữa cũng như bên trong agent (Talebirad and Nadiri, 2023; Park et al., 2023; Han et al., 2024; Guo et al., 2024; Zhang et al., 2024; Gao et al., 2024; Xu et al., 2025; Ji et al., 2025). Trong các miền khác như thông tin sai lệch, khung đa agent chuyên biệt theo vai trò, được tăng cường bằng truy xuất, thường vượt LLM độc lập (Li et al., 2024). OpenAGI chia tuyên bố thành các tác vụ con, chia sẻ ngữ cảnh truy xuất và đạt kết quả kiểm chứng sự thật tốt nhất mà không cần giám sát (Zhang and Gao, 2023; Ge et al., 2024). Bộ truy xuất nhiều bước MUSER và GET nhận biết đồ thị tiếp tục cải thiện việc neo bằng chứng (Liao et al., 2023; Xu et al., 2022). Trong tài chính, GraphRAG (Barry et al., 2025) cho thấy lợi ích của việc kết hợp đồ thị tri thức với truy xuất văn bản cổ điển để giảm ảo giác và tăng hiệu quả ở tác vụ hỏi đáp tài chính.

# 3. Phương pháp

## 3.1. Chuẩn bị đầu vào và nhãn mục tiêu

### Thu nạp dữ liệu

Pipeline thu nhận hai luồng dữ liệu cho từng cặp doanh nghiệp - quý. Thứ nhất là **toàn bộ transcript** gồm phần phát biểu chuẩn bị trước và hỏi đáp của các công ty NYSE/NASDAQ, được thu thập từ Seeking Alpha. Thứ hai là **dữ liệu có cấu trúc từ báo cáo tài chính**: báo cáo kết quả kinh doanh, bảng cân đối kế toán và báo cáo lưu chuyển tiền tệ của nhiều quý gần nhất, được phân tích từ hồ sơ 10-K và 10-Q công khai trong EDGAR của SEC.

Transcript và báo cáo được sắp xếp nghiêm ngặt theo ngày công bố. Khi agent phân tích quý t, nó chỉ được truy cập transcript và dữ liệu cơ bản có ngày không muộn hơn t. Nhờ đó mỗi dự báo sử dụng tập thông tin thực tế tại thời điểm ra quyết định, loại bỏ thiên lệch nhìn trước. Thống kê và chi tiết dữ liệu tài chính cơ bản được trình bày ở Phụ lục I.

### Mục tiêu dự báo

Với một earnings call vào ngày giao dịch T, lợi suất kỳ hạn k ngày, trong đó k thuộc {1, 3, 7, 15, 30}, được định nghĩa:

[[EQUATION:r_(T-1:T+k) = (P_close_(T+k) / P_close_(T-1)) - 1]]

Nhãn mục tiêu là dấu của lợi suất:

[[EQUATION:y = sgn(r_(T-1:T+k)) thuộc {-1, 1}]]

Agent tổng hợp phải đưa ra dự báo zero-shot trực tiếp để tăng khả năng giải thích. Nó sinh điểm tin cậy s thuộc [0, 10], sau đó được chuyển thành dự báo nhị phân: 1 nếu điểm lớn hơn 5 và -1 nếu điểm không quá 5. Độ chính xác được đánh giá bằng cách so sánh dự báo y-hat với nhãn thật y.

## 3.2. Giảm thiên lệch nhìn trước của LLM

LLM có nguy cơ mắc **thiên lệch hồi tưởng**, tức tri thức có sau làm sai lệch cách diễn giải dữ liệu trước đó. Ví dụ, mô hình có thể gắn nhãn tích cực cho earnings call năm 2019 của NVIDIA chỉ vì biết Ampere sau này thành công, trong khi tại thời điểm cuộc gọi kết quả đó chưa thể biết được.

CARAG giảm rò rỉ bằng **che thực thể có tên**: thay token chỉ doanh nghiệp và sản phẩm, chẳng hạn NVIDIA và Ampere, bằng placeholder để mô hình dựa vào dữ liệu cơ bản thay vì thương hiệu hoặc tín hiệu chịu ảnh hưởng bởi tương lai. Để xử lý rò rỉ thời gian, nhóm tác giả còn thử nghiệm trên 2.259 transcript sau thời điểm cắt tri thức của mô hình, từ tháng 8/2023 đến tháng 12/2024. Kết quả vì thế không bị thiên lệch bởi tri thức nằm ngoài cửa sổ huấn luyện của LLM (Phụ lục A).

## 3.3. Trích xuất và phân công Fact

### 3.3.1. Trích xuất Fact

Pipeline đồ thị tri thức truyền thống tạo ra các bộ ba tĩnh, ví dụ (CompanyA, has_CEO, John Doe), không phù hợp với tài chính vì bỏ qua hai loại thông tin quan trọng nhất trong earnings call: động lực biến đổi theo thời gian và các tuyên bố nhân quả. Những câu như “biên lợi nhuận quý này giảm so với quý trước” hoặc “doanh thu tăng nhờ ra mắt sản phẩm mới” chính là bằng chứng nhà phân tích dùng để định giá doanh nghiệp. Để nắm bắt loại thông tin này, nhóm tác giả xây dựng **Causal-Temporal Knowledge Graph (CTKG)** và dùng một LLM chuyên trách để điền dữ liệu vào đồ thị.

So với chỉ mục sự kiện hoặc cơ sở dữ liệu chuỗi thời gian đơn giản, CTKG không chỉ lưu sự kiện và chỉ tiêu mà còn biểu diễn tường minh **quan hệ nhân quả** và **phụ thuộc thời gian** giữa các sự kiện. Ngữ nghĩa có cấu trúc này cho phép agent suy luận nhiều bước sâu hơn; cơ sở dữ liệu chuỗi thời gian truyền thống chỉ lưu sự kiện và thiếu cấu trúc quan hệ cần thiết cho suy luận.

Một **Agent Trích xuất và Phân công Fact** chuyên biệt điều phối quá trình tạo fact bằng cách chuyển văn bản phi cấu trúc thành đầu ra có cấu trúc. Mỗi Fact là bộ năm:

[[EQUATION:f = (s, q, tau, mu, nu)]]

trong đó s là mã cổ phiếu, q là quý, tau là loại fact, mu là chỉ tiêu tài chính và nu là giá trị. Fact được phân loại thành **Result**, **Forward-Looking**, **Risk Disclosure**, **Sentiment** hoặc **Macro**, đồng thời chứa chỉ tiêu cụ thể như Revenue và giá trị tương ứng. Fact loại Result nắm bắt chỉ tiêu cụ thể được nêu trong transcript hoặc báo cáo tài chính. Báo cáo tài chính được dùng để bổ sung mức thay đổi theo quý (QoQ) hoặc theo năm (YoY).

Mỗi nút Fact liên kết với nút Ticker và Quarter tương ứng. Historic Performance Agent và Historic Earnings Agent neo tại Ticker A rồi duyệt đồ thị **theo chiều dọc**, lùi trên chuỗi thời gian các quý kế tiếp nhau từ 2024-Q4 về 2024-Q3 để tạo lịch sử kết quả đầy đủ. Ngược lại, Competitor Agent bắt đầu từ Quarter 2024-Q4 và mở rộng **theo chiều ngang** qua các liên kết đồng cấp tới mọi mã cổ phiếu ở cùng quý, chẳng hạn Firm B.

[[FIGURE:figure-2.png|Hình 2. Kiến trúc CARAG gồm bốn mô-đun: chuẩn bị dữ liệu và nhãn; trích xuất và phân công Fact; suy luận đa agent trên CTKG; tổng hợp phân cấp và dự báo.]]

Để mô hình hóa nhân quả, một Fact được nối với nút Reason riêng qua quan hệ HAS_REASON. Nút Reason có hai chức năng. Thứ nhất, nó có thể lưu nguyên văn lý do mà ban lãnh đạo đưa ra trong earnings call. Nếu ban lãnh đạo nói “triển vọng tích cực cho tăng trưởng tiếp tục”, chính phát biểu này được lưu làm Reason. Thứ hai, nút có thể lưu diễn giải phân tích của LLM. Chẳng hạn, “một tuần tuyệt vời để học hỏi từ khách hàng” có thể được chuẩn hóa thành Reason: “cho thấy cảm xúc tích cực đối với quan hệ và phản hồi của khách hàng”.

Mỗi nút Fact được lưu trong Neo4j; embedding 1.536 chiều của nó được lập chỉ mục để tìm kiếm tương đồng ngữ nghĩa. Việc tách **cái gì** (Fact) khỏi **vì sao** (Reason) khuyến khích sự đa dạng trong phân tích. Agent có thể truy vấn mọi doanh nghiệp cùng báo cáo một chỉ tiêu, từ đó thực hiện meta-analysis về cách các đội ngũ quản lý khác nhau diễn giải cùng loại kết quả.

### 3.3.2. Phân công Fact

Biểu diễn mỗi fact đã trích xuất là f_i = (tau_i, c_i). Hàm định tuyến phi ánh xạ mỗi fact tới một hoặc nhiều agent ở tầng sau:

[[EQUATION:phi: F -> P(A), với A = {A_HP, A_HE, A_COMP}]]

Mỗi agent chỉ nhận một luồng thông tin đã được lọc và có độ liên quan cao. Fact loại Result, ví dụ doanh thu vừa công bố, được chuyển cho **Historic Performance Agent** để so với kết quả trước đây của chính doanh nghiệp. Fact loại Forward-Looking, chẳng hạn dự phóng của ban lãnh đạo, được chuyển cho **Historic Earnings Agent** để đánh giá độ đáng tin và mức độ có căn cứ của tuyên bố. Fact loại Risk Disclosure được gửi cho **Competitor Agent** để xác định rủi ro mang tính riêng doanh nghiệp hay toàn ngành, đồng thời gửi cho Historic Earnings Agent để đánh giá mức độ cụ thể và minh bạch.

## 3.4. Suy luận đa agent

Ba agent LLM chuyên biệt hoạt động song song, truy vấn CTKG và tạo các bản ghi nhớ phân tích (memo). Các memo này trở thành đầu vào cho giai đoạn tổng hợp cuối.

### 3.4.1. Historic Performance Agent

Thiết kế agent dựa trên nguyên lý: giá trị nội tại thể hiện trong báo cáo tài chính là điểm neo dài hạn của giá cổ phiếu (Ou and Penman, 1989). Với fact f = (s, q, tau, mu, nu), có embedding ngữ nghĩa v thuộc R^d, định nghĩa lịch sử của cùng cặp mã cổ phiếu - chỉ tiêu:

[[EQUATION:H(s, mu) = {f' = (s, q', tau', mu, nu') : q' < q}]]

Agent dùng độ tương đồng cosine sigma(v, v_h) = <v, v_h> / (||v|| ||v_h||), rồi truy xuất k bản ghi lịch sử tương đồng nhất:

[[EQUATION:N_k(f) = arg top-k_(h thuộc H(s, mu)) sigma(v, v_h)]]

Với fact Result mới f = (s, q, RESULT, mu, nu), đặt f^(-1) = (s, q-1, RESULT, mu, nu^(-1)) là fact gần nhất trước đó của cùng mã và chỉ tiêu. Dựa trên các fact lịch sử, agent tạo so sánh có cấu trúc để phát hiện dịch chuyển xu hướng và đặt kết quả hiện tại vào lịch sử của chính doanh nghiệp. Mức thay đổi giữa hai kỳ được tính:

[[EQUATION:Delta nu = nu - nu^(-1); delta = Delta nu / nu^(-1)]]

Định nghĩa ánh xạ rho: F -> R gán cho mỗi fact f nút Reason r = rho(f). Agent đánh giá cặp (delta_t, r), xem xét lý do phía sau kết quả và đánh dấu trường hợp lời giải thích của ban lãnh đạo không hòa giải được con số hiện tại với chuẩn lịch sử. Trong dữ liệu nghiên cứu, khi Codexis (CDXS) báo cáo biên lợi nhuận gộp quý IV năm tài chính 2019 là 47%, agent truy ra mức 51% của năm trước và xác định đúng sự xói mòn lợi nhuận dù doanh thu vẫn tăng hai chữ số.

### 3.4.2. Historic Earnings Agent

Dựa trên lý thuyết quy kết cổ điển (Heider, 1958; Kelley, 1967), agent này giả định các tuyên bố của ban lãnh đạo được hỗ trợ bởi bằng chứng định lượng có thể kiểm chứng sẽ đáng tin hơn; phát biểu có căn cứ cũng tạo phản ứng thị trường và điều chỉnh của nhà phân tích mạnh hơn so với diễn ngôn không có bằng chứng (Mayew et al., 2015).

Tương tự Historic Performance Agent, agent này truy xuất k fact tương đồng nhất, nhưng lấy **mọi loại fact**, không chỉ Result. Nhiệm vụ chính là đánh giá guidance hướng tới tương lai từ các cuộc gọi trước đã được vượt, đạt hay bỏ lỡ. Ví dụ, ở quý I/2021 của Newmark (NMRK), ban lãnh đạo hướng dẫn tăng trưởng doanh thu cả năm 20%-25% nhưng quý I chỉ đạt 4,1%; agent đã đánh dấu rủi ro cao không hoàn thành kế hoạch.

### 3.4.3. Competitor Analyst Agent

Nhiều nghiên cứu tài chính thực nghiệm cho thấy ngành và lĩnh vực là động lực chính của đồng biến lợi suất. Nhân tố ngành toàn cầu có thể giải thích nhiều phương sai chéo hơn yếu tố địa lý (Cavaglia et al., 2000; Baca et al., 2000; Heston and Rouwenhorst, 1994; Moskowitz and Grinblatt, 1999).

Do đó, agent đánh giá doanh nghiệp bằng cách so trực tiếp với các công ty cùng ngành thay vì nhìn riêng lẻ. Gọi U là tập doanh nghiệp có thể giao dịch và S = {s_1, ..., s_11} là các ngành GICS; mỗi doanh nghiệp i thuộc U có nhãn ngành sigma(i) thuộc S. Với doanh nghiệp trọng tâm i*, tập doanh nghiệp cùng ngành là:

[[EQUATION:P(i*) = {j thuộc U trừ {i*} : sigma(j) = sigma(i*)}]]

Xét fact trọng tâm f* = (i*, q*, mu, v*) với chỉ tiêu mu, lớp vị từ thu thập mọi fact cùng chỉ tiêu và cùng quý của các doanh nghiệp đồng cấp:

[[EQUATION:p(f*) = {f' = (j, q*, mu, v_j) thuộc F : j thuộc P(i*)}]]

Agent truy xuất k fact tương đồng cosine nhất, tạo chuẩn ngành và tính độ lệch của doanh nghiệp so với chuẩn. Nó cũng rút thông tin tương tự từ mô tả bằng lời và fact cảm xúc.

## 3.5. Tổng hợp phân cấp và dự báo

Một **Synthesizer Agent** cấp cao thực hiện suy luận meta để tích hợp đầu ra từ các agent chuyên biệt. Agent nhận ba memo phân tích và duy trì bộ nhớ cuốn chiếu:

[[EQUATION:H_t = {(y-hat_(t-k), r_(t-k), u_(t-k))} từ k=1 đến K]]

Trong đó y-hat_(t-k) là dự báo được phát ra k quý trước, r_(t-k) là lợi suất vượt trội thực tế và u_(t-k) là phán quyết bằng văn bản đi kèm. Từ đó, agent tạo hai câu: (i) bản tóm tắt ngắn gọn bằng chứng hỗ trợ; và (ii) hướng dự báo kèm điểm tin cậy s_t thuộc [0, 10], trong đó 0 là niềm tin mạnh nhất rằng giá giảm và 10 là niềm tin mạnh nhất rằng giá tăng.

# 4. Thực nghiệm

## 4.1. Thiết kế thực nghiệm

### Tuyển chọn bộ dữ liệu

Để hỗ trợ tái lập đầy đủ, nhóm tác giả xây dựng và công bố hai corpus earnings call mới cho các công ty niêm yết trên **NASDAQ** và **NYSE**, mỗi transcript được ghép với báo cáo tài chính tương ứng. Hai bộ này dùng để benchmark CARAG với các baseline chỉ dùng văn bản và được cung cấp trong tài liệu bổ sung.

Để so sánh sức mạnh dự báo của dữ liệu tài chính cơ bản với tín hiệu âm thanh, CARAG được benchmark với các mô hình căn chỉnh âm thanh - văn bản tiên tiến trên MAEC (Li et al., 2020). Nhóm tác giả thay track âm thanh bằng báo cáo tài chính khớp theo quý, giữ nguyên mọi thiết lập khác. Thiết kế này cô lập phần đóng góp của **neo vào báo cáo tài chính** so với **căn chỉnh âm thanh**.

**Bảng 1. Thống kê mô tả các corpus NASDAQ, NYSE và MAEC.** T_min, T_med và T_max là độ dài transcript tối thiểu, trung vị và tối đa.

| Sàn/Bộ dữ liệu | Khoảng thời gian | Số transcript | Số mã | T_min | T_med | T_max |
|---|---|---:|---:|---:|---:|---:|
| NASDAQ | 23/05/2019 - 09/02/2023 | 1.772 | 507 | 1.416 | 7.059 | 8.061 |
| NYSE | 21/05/2019 - 22/02/2023 | 1.386 | 470 | 771 | 7.006 | 7.924 |
| MAEC | 25/02/2015 - 21/06/2018 | 2.725 | 963 | 420 | 1.994 | 9.081 |

### Các họ mô hình baseline

Trên NASDAQ và NYSE, nghiên cứu so sánh với hai họ baseline chỉ dùng văn bản:

1. **Baseline LLM zero-shot chỉ nhận transcript:** từ điển Loughran-McDonald; GPT-4o-mini; GPT-3.5-turbo; pipeline LangGraph hai agent mô phỏng tương tác nhà phân tích - người phản biện (Wang and Duan, 2024); và biến thể Graph-of-Thoughts (GoT) sinh nhiều giả thuyết rồi chọn đầu ra xếp hạng cao nhất (Zhou et al., 2023). Các baseline này không có ngữ cảnh tài chính có cấu trúc. Ngoài ra còn có **WideCtx**, cung cấp cho GPT-4o-mini cả transcript lẫn báo cáo tài chính trong một cửa sổ ngữ cảnh lớn.

2. **Baseline encoder văn bản có giám sát:** FinBERT (Huang et al., 2024), biến thể BERT 110 triệu tham số được huấn luyện trên hồ sơ và transcript tài chính; và Hierarchical FinBERT (Koval et al., 2023), chia transcript dài thành các đoạn căn theo câu với L thuộc {32, 64, 128}, mã hóa bằng FinBERT rồi tổng hợp bằng một Transformer nhẹ.

Họ baseline thứ ba gồm các mô hình căn chỉnh âm thanh - văn bản trên MAEC: **MDRM** (Qin and Yang, 2019), mô hình hồi quy sâu hợp nhất âm thanh với transcript; **StockGNN** (Medya et al., 2022), dùng mạng nơ-ron đồ thị có cổng để mô hình hóa cấu trúc trong transcript qua đồ thị đồng xuất hiện; và **ECHO-GL** (Liu et al., 2024), khung học đồ thị dị thể động liên kết cổ phiếu, câu và chủ đề bằng cơ chế tổng hợp dựa trên attention.

### Cấu hình mô hình và đánh giá

Mỗi agent chuyên biệt dùng GPT-4o-mini. Hệ thống phối hợp nhiều mô hình nhẹ đạt độ chính xác dự báo tốt hơn baseline đơn khối lớn hơn. Mọi tương tác dùng giải mã xác định với **temperature = 0** và **top_p = 1**. Trong bước truy xuất, mỗi agent lấy năm fact tương đồng nhất từ đồ thị, tức **k = 5**. Hai chỉ số chính là **Macro-F1** và **Matthews Correlation Coefficient (MCC)**, được đánh giá trên nhiều chân trời dự báo. Ký hiệu **bd** trong bảng nghĩa là ngày giao dịch.

**Bảng 2A. Macro-F1 (%) trên NASDAQ, trung bình qua 10 lần chạy.**

| Phương pháp | +1bd | +3bd | +7bd | +15bd | +30bd |
|---|---:|---:|---:|---:|---:|
| LM | 40,9 | 41,7 | 40,5 | 39,5 | 37,0 |
| GPT-4o-mini | 47,3 | 47,4 | 46,5 | 45,8 | 43,8 |
| GPT-3.5-turbo | 43,9 | 44,1 | 43,0 | 42,0 | 40,8 |
| LangGraph | 35,6 | 35,7 | 35,3 | 34,9 | 33,0 |
| GoT | 41,3 | 41,7 | 42,5 | 43,2 | 41,7 |
| WideCtx | 48,1 | 48,2 | 47,2 | 46,4 | 44,5 |
| FinBERT | 53,4 | 53,3 | 53,2 | 53,1 | 53,0 |
| HierFinBERT | 53,5 | 52,1 | 52,2 | 52,3 | 52,0 |
| **CARAG** | **55,7** | **55,1** | **54,2** | **53,5** | **53,2** |
| Cải thiện (%) | +4,1 | +3,4 | +1,9 | +0,8 | +0,4 |
| p-value (%) | 3,0 | 3,5 | 3,8 | 4,2 | 4,2 |

**Bảng 2B. MCC (%) trên NASDAQ, trung bình qua 10 lần chạy.**

| Phương pháp | +1bd | +3bd | +7bd | +15bd | +30bd |
|---|---:|---:|---:|---:|---:|
| LM | 2,9 | 5,0 | 3,8 | 2,6 | -0,4 |
| GPT-4o-mini | 11,9 | 11,7 | 10,8 | 9,8 | 8,8 |
| GPT-3.5-turbo | 8,0 | 8,3 | 7,2 | 6,0 | 7,4 |
| LangGraph | 3,6 | 3,4 | 5,0 | 6,6 | 6,4 |
| GoT | 4,3 | 4,2 | 7,0 | 10,0 | 6,0 |
| WideCtx | 12,4 | 12,0 | 11,1 | 10,2 | 9,1 |
| FinBERT | 11,8 | 11,3 | 10,7 | 10,0 | 9,6 |
| HierFinBERT | 11,4 | 10,9 | 10,3 | 9,7 | 9,2 |
| **CARAG** | **13,7** | **12,6** | **11,5** | **10,6** | **10,1** |
| Cải thiện (%) | +10,5 | +5,0 | +3,6 | +3,9 | +5,2 |
| p-value (%) | 3,5 | 3,9 | 3,9 | 3,9 | 3,9 |

**Bảng 2C. Macro-F1 (%) trên NYSE, trung bình qua 10 lần chạy.**

| Phương pháp | +1bd | +3bd | +7bd | +15bd | +30bd |
|---|---:|---:|---:|---:|---:|
| LM | 44,4 | 44,4 | 44,5 | 44,7 | 42,4 |
| GPT-4o-mini | 49,0 | 49,1 | 50,0 | 51,0 | 49,3 |
| GPT-3.5-turbo | 48,0 | 47,7 | 48,0 | 48,2 | 45,6 |
| LangGraph | 36,1 | 36,2 | 35,8 | 35,4 | 33,5 |
| GoT | 44,0 | 42,8 | 43,5 | 44,0 | 44,8 |
| WideCtx | 49,6 | 49,7 | 50,5 | 51,6 | 49,9 |
| FinBERT | 53,6 | 53,4 | 53,0 | 52,7 | 52,6 |
| HierFinBERT | 53,7 | 53,5 | 52,8 | 51,9 | 51,8 |
| **CARAG** | **57,4** | **57,0** | **57,2** | **57,5** | **56,3** |
| Cải thiện (%) | +6,9 | +6,5 | +7,9 | +9,1 | +7,0 |
| p-value (%) | 2,3 | 2,3 | 2,2 | 2,2 | 2,3 |

**Bảng 2D. MCC (%) trên NYSE, trung bình qua 10 lần chạy.**

| Phương pháp | +1bd | +3bd | +7bd | +15bd | +30bd |
|---|---:|---:|---:|---:|---:|
| LM | 8,3 | 7,7 | 6,5 | 5,5 | 3,4 |
| GPT-4o-mini | 15,4 | 14,0 | 14,4 | 14,8 | 13,4 |
| GPT-3.5-turbo | 15,2 | 14,0 | 12,8 | 11,7 | 9,2 |
| LangGraph | 4,1 | 3,9 | 5,5 | 7,1 | 6,9 |
| GoT | 9,9 | 6,0 | 6,0 | 6,0 | 9,2 |
| WideCtx | 15,7 | 14,4 | 14,8 | 15,1 | 13,7 |
| FinBERT | 13,5 | 12,8 | 12,7 | 12,6 | 12,1 |
| HierFinBERT | 13,0 | 12,5 | 12,3 | 12,0 | 11,5 |
| **CARAG** | **16,2** | **15,2** | **15,4** | **15,6** | **13,9** |
| Cải thiện (%) | +3,2 | +5,6 | +4,1 | +3,3 | +1,5 |
| p-value (%) | 3,9 | 3,5 | 3,7 | 3,9 | 3,9 |

**Bảng 2E. Macro-F1 (%) trên MAEC - so sánh với mô hình dùng âm thanh.**

| Phương pháp | +1bd | +3bd | +7bd | +15bd | +30bd |
|---|---:|---:|---:|---:|---:|
| MDRM | 48,7 | 52,0 | 51,0 | 53,7 | 55,9 |
| StockGNN | 53,0 | 51,1 | 52,0 | 52,6 | 55,2 |
| ECHO-GL | 54,4 | 54,3 | 54,4 | 54,9 | 57,3 |
| **CARAG** | **58,7** | **57,9** | **57,0** | **55,2** | **57,6** |
| Cải thiện tuyệt đối | +4,3 | +3,6 | +2,6 | +0,3 | +0,3 |
| p-value (%) | 2,2 | 2,3 | 3,0 | 4,2 | 4,2 |

**Bảng 2F. MCC (%) trên MAEC - so sánh với mô hình dùng âm thanh.**

| Phương pháp | +1bd | +3bd | +7bd | +15bd | +30bd |
|---|---:|---:|---:|---:|---:|
| MDRM | 1,9 | 2,8 | 2,7 | 2,8 | 6,3 |
| StockGNN | 4,0 | 4,3 | 5,0 | 6,4 | 6,0 |
| ECHO-GL | 6,7 | 6,3 | 6,0 | 6,7 | 6,9 |
| **CARAG** | **17,6** | **16,0** | **14,0** | **8,8** | **10,0** |
| Cải thiện tuyệt đối | +10,9 | +9,7 | +8,0 | +2,1 | +3,1 |
| p-value (%) | 3,7 | 3,7 | 3,7 | 3,0 | 2,3 |

### Kết quả tổng thể so với baseline

**(O1) CARAG vượt đáng kể các LLM zero-shot khác.** Macro-F1 cao hơn hơn 17% so với GPT-4o-mini chỉ đọc transcript trên cả NASDAQ và NYSE. CARAG cũng vượt WideCtx dù baseline này nhận cùng transcript và báo cáo tài chính thô. Điều đó cho thấy lợi ích không chỉ đến từ nhiều dữ liệu hơn mà từ suy luận có cấu trúc: trích xuất thời gian - nhân quả rõ ràng và tổng hợp đa agent qua CTKG tạo sức mạnh dự báo bổ sung so với mô hình đơn khối có cửa sổ ngữ cảnh lớn.

**(O2) CARAG vượt encoder văn bản.** Ở chân trời +1 ngày, agent zero-shot vượt Hierarchical FinBERT đã fine-tune lần lượt 2,2 điểm F1 tuyệt đối (+4,1%) và 2,3 điểm MCC (+20,2%) trên NASDAQ; 3,7 điểm F1 (+6,9%) và 3,2 điểm MCC (+24,6%) trên NYSE, dù không huấn luyện riêng cho tác vụ.

**(O3) Dữ liệu tài chính cơ bản có sức dự báo mạnh hơn tín hiệu âm thanh.** Trên MAEC ở chân trời +1 ngày, CARAG vượt ECHO-GL 4,3 điểm F1 tuyệt đối (+7,9%) và 10,9 điểm MCC (+162,7%). ECHO-GL cùng mọi baseline khác đều được huấn luyện có giám sát cho từng cửa sổ dự báo, trong khi CARAG vẫn zero-shot ở mọi chân trời. Kết quả cho thấy neo LLM vào bằng chứng tài chính cơ bản đem lại tín hiệu dự báo giàu hơn nhiều so với chỉ bổ sung đặc trưng âm thanh.

### Chi phí token và độ trễ

Nhóm bốn agent có chi phí suy luận trung vị chỉ **0,0040 USD cho mỗi hồ sơ**. Xử lý một hồ sơ hoàn chỉnh mất trung bình **157 giây**, đủ hỗ trợ sử dụng gần thời gian thực. Phân rã token và độ trễ nằm ở Phụ lục F.

### Xử lý mất cân bằng lớp trong dự báo zero-shot

GPT-4o-mini chỉ nhận transcript đạt balanced accuracy 54% trên NASDAQ và 56% trên NYSE, nhưng Macro-F1 chỉ còn 47% và 49%. Hình 3 cho thấy mô hình này dự đoán quá nhiều lớp dương vì ban lãnh đạo thường nhấn mạnh mặt tích cực và giảm nhẹ mặt tiêu cực. CARAG tạo phân phối cân xứng hơn.

[[FIGURE:figure-3.png|Hình 3. Phân phối dự báo thô của baseline chỉ dùng transcript so với CARAG trên NASDAQ và NYSE. Màu xanh biểu thị điểm không quá 5; màu đỏ biểu thị điểm lớn hơn 5.]]

### Nghiên cứu ablation

**Bảng 3. Macro-F1 khi lần lượt loại từng mô-đun ngữ cảnh.** Giá trị trong ngoặc là mức giảm tương đối.

| Biến thể | NASDAQ | NYSE | MAEC |
|---|---:|---:|---:|
| **Mô hình đầy đủ (CARAG, zero-shot)** | **55,7** | **57,4** | **58,7** |
| Không Historic Performance | 54,2 (-2,7%) | 55,6 (-3,1%) | 57,1 (-2,7%) |
| Không Competitor Analyst | 55,3 (-0,7%) | 56,7 (-1,2%) | 58,1 (-1,0%) |
| Không Historic Earnings | 54,8 (-1,6%) | 56,3 (-1,9%) | 57,7 (-1,7%) |
| Không Knowledge Graph | 54,3 (-2,5%) | 55,3 (-3,7%) | 56,8 (-3,2%) |
| Không Memory | 55,2 (-0,9%) | 57,3 (-0,2%) | 58,4 (-0,5%) |

Mức giảm mạnh nhất xuất hiện khi bỏ Knowledge Graph. Historic Performance và Historic Earnings cũng mang lại mức tăng đáng kể. Ngược lại, bỏ bộ nhớ ngắn hạn hoặc Competitor Analyst chỉ gây suy giảm nhỏ. Như vậy, ngữ cảnh được căn chỉnh theo đồ thị là thiết yếu, và agent neo theo thời gian hữu ích hơn tín hiệu so sánh chéo với đối thủ.

Để kiểm chứng vai trò của kiến trúc đa agent, nhóm tác giả so sánh mô hình đầy đủ với: (1) **Single-Agent CTKG**, gộp prompt của Synthesizer và ba agent chuyên biệt thành một chỉ thị duy nhất cho một mô hình có quyền truy cập đồ thị; và (2) **Weighted Synthesis**, lấy trung bình có trọng số của ba điểm hướng dự báo 0-10 thay vì thực hiện bước tổng hợp suy luận.

**Bảng 4. Ablation mở rộng giữa CARAG đầy đủ, biến thể đơn agent, agent riêng lẻ và chiến lược tổng hợp heuristic.**

| Biến thể | NASDAQ | NYSE | MAEC |
|---|---:|---:|---:|
| **Mô hình đầy đủ (CARAG)** | **55,7** | **57,4** | **58,7** |
| CTKG-only, một agent | 54,5 (-2,1%) | 56,2 (-2,1%) | 57,3 (-2,4%) |
| Tổng hợp có trọng số | 55,3 (-0,7%) | 57,1 (-0,5%) | 57,6 (-1,9%) |
| Chỉ Historic Performance | 54,4 (-2,3%) | 55,1 (-4,0%) | 57,2 (-2,6%) |
| Chỉ Competitor Analyst | 53,2 (-4,5%) | 54,2 (-5,6%) | 56,7 (-3,4%) |
| Chỉ Historic Earnings | 54,1 (-2,9%) | 54,9 (-4,4%) | 57,1 (-2,7%) |

Mô hình CTKG đơn agent luôn kém CARAG đầy đủ, Macro-F1 giảm 2,1% trên NASDAQ và 2,4% trên MAEC. Việc buộc một cửa sổ ngữ cảnh xử lý đồng thời chuẩn lịch sử, so sánh đồng cấp và quy kết nguyên nhân làm loãng chất lượng suy luận. Từng agent riêng lẻ cũng kém hệ thống phối hợp, xác nhận không một góc nhìn nào là đủ. Tổng hợp có trọng số kém tổng hợp văn bản phân cấp, cho thấy Synthesizer Agent tạo thêm giá trị bằng cách giải quyết xung đột theo logic thay vì chỉ lấy trung bình điểm số.

### Kết quả backtest

Backtest giả định tín hiệu tính bằng dữ liệu ngày T được thực thi tại T+1. Chiến lược CARAG đạt **lợi suất thường niên hóa 35,83%** và **Sharpe 1,64**, vượt GPT-3.5-turbo chỉ dùng transcript (13,64%; Sharpe 0,64) và từ điển LM (-16,69%; Sharpe -0,47). Cùng kỳ, S&P 500 đạt 1,80% với Sharpe 0,19; Nasdaq đạt -8,94% với Sharpe -0,24.

[[FIGURE:figure-4.png|Hình 4. Backtest hai năm trên 1.772 transcript NASDAQ và 1.386 transcript NYSE: PnL tích lũy trễ một ngày và Sharpe cuốn chiếu 126 ngày đã thường niên hóa.]]

# 5. Kết luận

CARAG kết hợp các LLM chuyên trách với CTKG để dự báo cú sốc giá sau công bố kết quả kinh doanh. Thực nghiệm trên NASDAQ, NYSE và MAEC cho thấy cải thiện nhất quán về Macro-F1 và MCC ở nhiều chân trời mà không cần fine-tune theo tác vụ, đồng thời đạt Sharpe cao hơn trong backtest hai năm.

Nghiên cứu tương lai sẽ mở rộng nhóm agent bằng các mô hình ngôn ngữ tiền huấn luyện mã nguồn mở lớn hơn, khảo sát pre-training có nhận biết CTKG để đào sâu suy luận thời gian - nhân quả, và có thể nối thêm một bộ hồi quy số nhẹ vào đầu ra của Synthesizer nhằm tạo điểm ensemble kết hợp tín hiệu ký hiệu với tín hiệu thống kê.

# 6. Hạn chế

Thứ nhất, do giới hạn ngân sách, hệ thống chỉ dùng GPT-4o-mini làm backbone. Lựa chọn này cho thấy hiệu quả chi phí nhưng không cho phép so sánh trực tiếp với LLM mã nguồn mở, vốn thuận lợi hơn cho tái lập và minh bạch. Nghiên cứu tương lai cần đánh giá với backbone mở để tách riêng lợi ích của kiến trúc agentic.

Thứ hai, pipeline trích xuất fact giả định phát biểu của ban lãnh đạo có thể được đối chiếu với dữ liệu cơ bản có cấu trúc. Trong thực tế, kiểm chứng fact bằng ground truth ngay tại thời điểm cuộc gọi đòi hỏi dữ liệu nhà cung cấp độc quyền như Compustat hoặc IBES. Các dữ liệu benchmark này không có ngay khi cuộc gọi được phát hành, hạn chế tính hữu ích cho dự báo thời gian thực. CTKG giải quyết một phần khoảng trống, nhưng pipeline fact-checking nghiêm ngặt hơn vẫn là câu hỏi mở.

# Tài liệu tham khảo

> Tiêu đề công trình và thông tin xuất bản được giữ nguyên ngôn ngữ gốc để thuận tiện tra cứu.

Doğu Araci. 2019. FinBERT: Financial sentiment analysis with pre-trained language models. arXiv:1908.10063.

Susan P. Baca, Brian L. Garbe, and Richard A. Weiss. 2000. The rise of sector effects in global equity markets. Financial Analysts Journal, 56(5):34-40.

Ray Ball and Philip Brown. 1968. An empirical evaluation of accounting income numbers. Journal of Accounting Research, 6(2):159-178.

M. Barry, S. Sanyal, A. K. Maji, and S. K. Adduru. 2025. GraphRAG: Leveraging graph-based efficiency to minimize hallucinations in LLM-driven RAG for finance data. Proceedings of the 1st Workshop on Generative AI for Knowledge-Intensive Tasks, pages 55-70.

Daniel Bradley, Süleyin Gokkaya, Xi Liu, and Fei Xie. 2017. Are all analysts created equal? Industry expertise and monitoring effectiveness of financial analysts. Journal of Accounting and Economics, 63(2-3):179-206.

Jingyuan Cao et al. 2023. A survey on financial large language models. arXiv:2311.13788.

Stefano Cavaglia, Chris Brightman, and Michael Aked. 2000. The increasing importance of industry factors in global equity returns. Financial Analysts Journal, 56(5):41-54.

Anne Chang, Xi Dong, Xiumin Martin, and Changyun Zhou. 2023. AI (ChatGPT) democratization and trading inequality. Olin Business School Center for Finance & Accounting Research, Working Paper 2023-019.

Chaochao Chen et al. 2024. Integration of large language models and federated learning. Patterns, 5(12).

Yancheng Chen, Zirui Liu, and Feng Lu. 2022. A text-based machine learning approach to forecasting stock returns with conference call transcripts. The North American Journal of Economics and Finance, 61:101673.

Andrew Chin and Yuyu Fan. 2023. Leveraging text mining to extract insights from earnings call transcripts. Journal of Investment Management, 21(1):81-102.

Ruidi Cui and Jingjing Zhai. 2023. Can ChatGPT reduce human financial analysts' optimistic biases? China Finance Review International.

Xiaoxi Cui et al. 2025. Diffusion-based multi-modal synergy interest network for click-through rate prediction. Proceedings of ACM SIGIR, pages 581-591.

J. Gao, W. Xu, T. Li, and Z. Liu. 2024. Memory sharing for multi-agent large language models. arXiv:2404.09982.

Yingqiang Ge et al. 2024. OpenAGI: When LLM meets domain experts. Advances in Neural Information Processing Systems 36.

S. Ghosh, A. Maji, and S. K. Naskar. 2025. MIMIC: Multi-modal Indian earnings calls dataset to predict stock prices. arXiv:2504.09257.

Boris Groysberg, Paul M. Healy, George Serafeim, and Devin M. Shanthikumar. 2013. The stock selection and performance of buy-side analysts. Management Science, 59(5):1062-1075.

Taicheng Guo et al. 2024. Large language model based multi-agents: A survey of progress and challenges. Proceedings of IJCAI-24, pages 8048-8057.

Shanshan Han et al. 2024. LLM multi-agent systems: Challenges and open problems. arXiv:2402.03578.

Fritz Heider. 1958. The Psychology of Interpersonal Relations. Wiley, New York.

Steven L. Heston and K. Geert Rouwenhorst. 1994. Does industrial structure explain the benefits of international diversification? Journal of Financial Economics, 36(1):3-27.

Allen H. Huang, Hui Wang, and Yi Yang. 2024. FinBERT: A large language model for extracting information from financial text. Contemporary Accounting Research.

H. Ji, S. Wang, Y. Zhao, and B. Xu. 2025. LLM-based multi-agent systems as graph generative models. Findings of ACL 2025, pages 1045-1058.

Ohad Kadan, Leonardo Madureira, Rong Wang, and Tzachi Zach. 2012. Analysts' industry expertise. Working paper.

Harold H. Kelley. 1967. Attribution theory in social psychology. Nebraska Symposium on Motivation, 15:192-238.

Ross Koval, Nicholas Andrews, and Xifeng Yan. 2023. Forecasting earnings surprises from conference call transcripts. Findings of ACL 2023, pages 8197-8209.

Feng Li. 2010. The information content of forward-looking statements in corporate filings - a naïve Bayesian machine learning approach. Journal of Accounting Research, 48(5):1049-1102.

Jiazheng Li, Linyi Yang, Barry Smyth, and Ruihai Dong. 2020. MAEC: A multimodal aligned earnings conference call dataset for financial risk prediction. Proceedings of CIKM 2020, pages 3063-3070.

Xinyi Li, Yongfeng Zhang, and Edward C. Malthouse. 2024. Large language model agent for fake news detection. arXiv:2405.01593.

Hao Liao et al. 2023. MUSER: A multi-step evidence retrieval enhancement framework for fake news detection. Proceedings of KDD 2023, pages 4461-4472.

Mengpu Liu et al. 2024. ECHO-GL: Earnings calls-driven heterogeneous graph learning for stock movement prediction. Proceedings of AAAI-24, pages 13972-13980.

Tim Loughran and Bill McDonald. 2011. When is a liability not a liability? Textual analysis, dictionaries, and 10-Ks. The Journal of Finance, 66(1):35-65.

Weihai Lu, Yu Tong, and Zhiqiu Ye. 2025. DAMMFND: Domain-aware multimodal multi-view fake news detection. Proceedings of AAAI, volume 39, pages 559-567.

Weihai Lu and Li Yin. 2025. DMMD4SR: Diffusion model-based multi-level multimodal denoising for sequential recommendation. Proceedings of ACM Multimedia, pages 6363-6372.

William J. Mayew, Mani Sethuraman, and Mohan Venkatachalam. 2015. MD&A disclosure and the firm's ability to continue as a going concern. Journal of Accounting Research, 53(5):1385-1419.

Sourav Medya, Mohammad Rasoolinejad, Yang Yang, and Brian Uzzi. 2022. An exploratory study of stock price movements from earnings calls. Companion Proceedings of WWW 2022, pages 1-11.

Tobias J. Moskowitz and Mark Grinblatt. 1999. Do industries explain momentum? The Journal of Finance, 54(4):1249-1290.

Haowei Ni et al. 2024. Harnessing earnings reports for stock predictions: A QLoRA-enhanced LLM approach. arXiv preprint.

Jane A. Ou and Stephen H. Penman. 1989. Financial statement analysis and the prediction of stock returns. Journal of Accounting and Economics, 11(4):295-329.

Joon Sung Park et al. 2023. Generative agents: Interactive simulacra of human behavior. Proceedings of UIST 2023.

Y. Peng. 2025. Earnings prediction using machine learning: A survey. Osaka Economic Papers.

S. McKay Price, James S. Doran, David R. Peterson, and Barbara A. Bliss. 2012. Earnings conference calls and stock returns: The incremental informativeness of textual tone. Journal of Banking & Finance, 36(4):992-1011.

Yu Qin and Yi Yang. 2019. What you say and how you say it matters: Predicting stock volatility using verbal and vocal cues. Proceedings of ACL 2019, pages 390-401.

Philip J. Stone, Dexter C. Dunphy, Marshall S. Smith, and Daniel M. Ogilvie. 1966. The General Inquirer: A Computer Approach to Content Analysis. MIT Press.

Yashar Talebirad and Amirhossein Nadiri. 2023. Multi-agent collaboration: Harnessing the power of intelligent LLM agents. arXiv:2306.03314.

Yu Tong et al. 2025. DAPT: Domain-aware prompt-tuning for multimodal fake news detection. Proceedings of ACM Multimedia, pages 7902-7911.

Jialin Wang and Zhihua Duan. 2024. Agent AI with LangGraph: A modular framework for enhancing machine translation using large language models. arXiv:2412.03801.

Z. Wang, T. K. Trinh, W. Liu, and C. Zhu. 2025. Temporal evolution of sentiment in earnings calls and its relationship with financial performance. Applied and Computational Engineering, 141:195-206.

Xiaolong Wei et al. 2025a. Beyond ReAct: A planner-centric framework for complex tool-augmented LLM reasoning. arXiv:2511.10037.

Xiaolong Wei et al. 2025b. Igniting creative writing in small language models: LLM-as-a-judge versus multi-agent refined rewards. Proceedings of EMNLP 2025, pages 17171-17197.

Shijie Wu et al. 2023. BloombergGPT: A large language model for finance. arXiv:2303.17564.

Zequn Xie et al. 2025a. Dynamic uncertainty learning with noisy correspondence for text-based person search. arXiv:2505.06566.

Zequn Xie et al. 2025b. Chat-driven text generation and interaction for person retrieval. Proceedings of EMNLP 2025, pages 5259-5270.

Zequn Xie, Boyun Zhang, Yuxiao Lin, and Tao Jin. 2026. Delving deeper: Hierarchical visual perception for robust video-text retrieval. arXiv:2601.12768.

K. Xu, R. Zhang, Y. Wang, and J. Chen. 2025. A-Mem: Agentic memory for large language model agents. arXiv:2502.12110.

Weizhi Xu, Junfei Wu, Qiang Liu, Shu Wu, and Liang Wang. 2022. Evidence-aware fake news detection with graph neural networks. Proceedings of The Web Conference 2022, pages 2501-2510.

Manzil Zaheer et al. 2020. BigBird: Transformers for longer sequences. Advances in Neural Information Processing Systems 33.

Guixian Zhang et al. 2025. Mitigating propensity bias of large language models for recommender systems. ACM Transactions on Information Systems, 43(6):1-26.

Jintian Zhang et al. 2024. Exploring collaboration mechanisms for LLM agents: A social psychology view. Proceedings of ACL 2024, pages 14544-14607.

Xuan Zhang and Wei Gao. 2023. Towards LLM-based fact verification on news claims with a hierarchical step-by-step prompting method. arXiv:2310.00305.

Zhejun Zhao et al. 2025. TURA: Tool-augmented unified retrieval agent for AI search. arXiv:2508.04604.

Shinn Zhou et al. 2023. Graph-of-Thought: Solving elaborate problems with large language models. arXiv:2305.10601.

Jingyuan Zhu et al. 2026. Comparing neural architectures for English-Spanish machine translation: From LSTM to Transformer.

Y. Zhu, X. Liu, and O. R. L. Sheng. 2025. Post-earnings-announcement drift prediction: Leveraging post-event investor responses with multitask learning. Information Systems Research.

# Phụ lục A. Kết quả sau thời điểm cắt tri thức của mô hình

Để đánh giá vững chắc hơn và loại bỏ hoàn toàn thiên lệch nhìn trước của LLM, nhóm tác giả lặp lại thực nghiệm trên dữ liệu sau thời điểm cắt tri thức của GPT-4o-mini: từ tháng 8/2023 đến tháng 12/2024, gồm 2.259 transcript. Kết quả Macro-F1 và MCC được trình bày riêng trong Bảng 5 và Bảng 6.

**Bảng 5. Macro-F1 (%) sau thời điểm cắt tri thức của GPT-4o-mini.**

| Phương pháp | +1bd | +3bd | +7bd | +15bd | +30bd |
|---|---:|---:|---:|---:|---:|
| LM | 40,5 | 39,8 | 39,5 | 40,5 | 39,7 |
| GPT-3.5-turbo | 34,2 | 31,8 | 30,8 | 32,7 | 31,7 |
| WideCtx | 60,4 | 59,7 | 58,7 | 59,1 | 57,5 |
| FinBERT | 58,9 | 58,5 | 58,2 | 58,3 | 58,1 |
| HierFinBERT | 59,7 | 59,3 | 58,9 | 59,0 | 58,7 |
| **CARAG** | **63,6** | **63,1** | **62,4** | **61,6** | **60,9** |
| Cải thiện (%) | +5,3 | +5,7 | +5,9 | +4,2 | +3,7 |

**Bảng 6. MCC (%) sau thời điểm cắt tri thức của GPT-4o-mini.**

| Phương pháp | +1bd | +3bd | +7bd | +15bd | +30bd |
|---|---:|---:|---:|---:|---:|
| LM | 9,7 | 8,5 | 7,8 | 8,7 | 5,4 |
| GPT-3.5-turbo | 8,5 | 7,0 | 6,4 | 6,4 | 5,2 |
| WideCtx | 27,5 | 25,9 | 20,0 | 20,3 | 17,5 |
| FinBERT | 22,5 | 22,0 | 21,5 | 21,7 | 20,9 |
| HierFinBERT | 23,6 | 23,0 | 22,6 | 22,8 | 21,9 |
| **CARAG** | **28,6** | **27,7** | **26,4** | **24,0** | **22,6** |
| Cải thiện (%) | +4,0 | +6,9 | +16,8 | +5,3 | +3,2 |

Kết quả xác nhận mức cải thiện không phải sản phẩm của tri thức hồi tưởng tiềm ẩn. Trong chế độ nghiêm ngặt, không rò rỉ, CARAG vẫn vượt mọi baseline với biên đáng kể. Lợi thế đến từ suy luận thời gian - nhân quả và việc neo vào fact có cấu trúc, không phải từ tri thức đã được chứa sẵn trong corpus pre-training.

# Phụ lục B. Khả năng giải thích

Nghiên cứu đối chiếu phán quyết của baseline chỉ dùng transcript với CARAG ở earnings call quý I/2021 của MicroVision, sau đó cổ phiếu giảm 29% trong ngày giao dịch kế tiếp. Baseline lặp lại ngôn ngữ lạc quan của lãnh đạo nên dự báo quá tích cực. CARAG phát hiện lỗ ròng mở rộng và chi phí vận hành tăng, nhờ đó đưa ra dự báo phù hợp với lợi suất âm thực tế: điểm hướng 4 so với 8 của baseline.

[[FIGURE:figure-5.png|Hình 5. Ca nghiên cứu MicroVision quý I/2021: baseline chỉ dùng transcript nhấn mạnh câu chuyện tích cực; CARAG đối chiếu doanh thu, lợi nhuận gộp, lỗ ròng và chi phí vận hành để đưa ra phán quyết thận trọng hơn.]]

# Phụ lục C. Độ nhạy siêu tham số

Macro-F1 cao nhất khi mỗi agent truy xuất **năm fact lịch sử** và **năm fact đồng cấp**. Tăng k_hist từ 5 lên 10 mang lại cải thiện nhỏ trên các bộ dữ liệu Mỹ dày đặc; ngược lại, tăng k_comp quá 5 làm kết quả trên MAEC giảm nhẹ.

[[FIGURE:figure-6.png|Hình 6. Độ nhạy siêu tham số k_hist và k_comp trên NASDAQ, NYSE và MAEC.]]

# Phụ lục D. Chi tiết backtest

Tín hiệu dự báo được đánh giá bằng một chiến lược giao dịch mô phỏng trung lập thị trường nghiêm ngặt. Tín hiệu tính từ thông tin có ở ngày T được thực thi tại T+1. Bộ tối ưu dùng MOSEK để giải bài toán nón bậc hai (SOCP), cân bằng lợi suất kỳ vọng và rủi ro dưới các ràng buộc trung lập và mức phơi nhiễm rõ ràng.

Ma trận hiệp phương sai đường chéo của rủi ro từng cổ phiếu được ước lượng trên cửa sổ nhìn lại nửa năm, ký hiệu Sigma_h. Với phân rã Cholesky Sigma_h = L_h^T L_h, danh mục ngày h, x_h thuộc R^N, được xác định bởi:

[[EQUATION:tối đa hóa theo x_h: mu_h^T x_h]]

[[EQUATION:với 1^T x_h = 0 (trung lập thị trường)]]

[[EQUATION:||L_h x_h||_2 <= sigma* (giới hạn biến động ex-ante)]]

[[EQUATION:||x_h||_1 <= G* (giới hạn tổng phơi nhiễm)]]

Ràng buộc 1^T x_h = 0 bảo đảm danh mục không có phơi nhiễm thị trường ròng vào mỗi ngày giao dịch. Điều này loại beta hệ thống để hiệu quả danh mục phản ánh alpha trong tín hiệu thay vì hướng thị trường ngẫu nhiên. Giới hạn tổng phơi nhiễm kiểm soát đòn bẩy; giới hạn biến động ex-ante khống chế rủi ro danh mục trước giao dịch.

Nghiên cứu đặt **sigma* = 10%** và **G* = 200%**, tạo chiến lược long-short, trung lập USD và có quản trị rủi ro. Vì vậy, lợi suất vượt trội hoặc Sharpe không thể quy cho độ trôi thụ động của thị trường mà phải đến từ khả năng dự báo khác biệt lợi suất theo chiều chéo.

# Phụ lục E. Lược đồ Fact và Knowledge Graph

**Hình 7. Ví dụ một Fact loại Result của Axon, mã AXON, quý IV/2023.**

| Khóa | Giá trị |
|---|---|
| embedding | [-0.0115..., 0.0115...] |
| metric | Annual Recurring Revenue (ARR) |
| quarter | 2023-Q4 |
| ticker | AXON |
| type | Result |
| value | 697 triệu USD |

[[FIGURE:figure-8.png|Hình 8. Duyệt theo chiều dọc: agent neo tại doanh nghiệp và đi qua các nút Fact giữa các quý 2023-Q1 và 2023-Q2.]]

[[FIGURE:figure-9.png|Hình 9. Duyệt theo chiều ngang: agent neo tại một quý rồi đi qua các doanh nghiệp DataDog và New Relic.]]

Mỗi nút Fact gắn với cả Ticker và Quarter, bảo đảm căn chỉnh ở cấp doanh nghiệp và thời gian. Lược đồ có sáu loại quan hệ. **REPORTS_IN** nối ticker với quý; **HAS_FACT** nối quý với các fact được báo cáo; **FOR_FIRM** nối fact trở lại doanh nghiệp; **HAS_VALUE** nối fact với giá trị; **EXPLAINED_BY** nối fact với Reason để giữ ngữ cảnh giải thích; và **QoQ_COMPARES** nối fact của cùng chỉ tiêu giữa các quý liên tiếp, kèm thuộc tính phần trăm thay đổi delta_pct.

## E.1. Topology và quá trình xây dựng CTKG

CTKG chuyển transcript phi cấu trúc thành mạng logic tài chính dày đặc. Đặc trưng cấp nút biểu diễn các thực thể rời rạc như Fact, Reason và Metric; đặc trưng cấp liên kết ánh xạ cấu trúc quan hệ như quy kết nhân quả EXPLAINED_BY và neo thời gian REPORTS_IN. Số cạnh HAS_REASON bằng số Fact, bảo đảm mỗi tuyên bố định lượng được neo về mặt ngữ nghĩa vào bình luận định tính của ban lãnh đạo.

**Bảng 7A. Thống kê nút của CTKG.**

| Dữ liệu | Transcript | Ticker | Fact | Reason | Value | Metric | Quarter | Tổng nút |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| NASDAQ | 1.772 | 507 | 79.775 | 44.300 | 79.775 | 79.775 | 18 | 285.922 |
| NYSE | 1.386 | 470 | 55.738 | 34.650 | 55.738 | 55.738 | 18 | 203.738 |
| MAEC | 2.725 | 963 | 109.417 | 68.125 | 109.417 | 109.417 | 20 | 400.084 |

**Bảng 7B. Thống kê cạnh của CTKG.**

| Dữ liệu | FOR_FIRM | HAS_VALUE | EXPLAINED_BY | HAS_FACT | REPORTS_IN | Tổng cạnh |
|---|---:|---:|---:|---:|---:|---:|
| NASDAQ | 79.775 | 79.775 | 79.775 | 79.775 | 1.772 | 320.872 |
| NYSE | 55.738 | 55.738 | 55.738 | 55.738 | 1.386 | 224.338 |
| MAEC | 109.417 | 109.417 | 109.417 | 109.417 | 2.725 | 440.393 |

MAEC là đồ thị lớn nhất, với hơn 400.000 nút và 440.000 cạnh.

# Phụ lục F. Benchmark độ trễ

**Bảng 8. Token và độ trễ trung vị cho mỗi earnings call.**

| Agent | Token đầu vào | Token đầu ra | Truy vấn đồ thị (giây) | LLM (giây) |
|---|---:|---:|---:|---:|
| Competitor Analyst | 719 | 653 | 38,6 | 3,8 |
| Historic Performance | 1.160 | 715 | 49,1 | 11,8 |
| Historic Earnings | 1.012 | 444 | 16,3 | 6,4 |
| Main Agent | 15.580 | 242 | 26,6 | 4,7 |
| **Tổng** | **18.471** | **2.054** | **130,6** | **26,7** |

# Phụ lục G. Các bộ dữ liệu được đóng góp

Nghiên cứu đóng góp nhiều bộ dữ liệu mới cho phân tích earnings call. Bộ đầy đủ sẽ được mã nguồn mở sau khi bài được chấp nhận; hiện tài liệu bổ sung đã có một phần dữ liệu. **Enhanced Earnings Call Datasets** gồm 1.386 earnings call của công ty NYSE và 1.772 earnings call của công ty NASDAQ. Mỗi bản ghi chứa transcript đầy đủ, dữ liệu tài chính theo quý liên quan và nhãn biến động giá sau công bố.

## G.1. Báo cáo tài chính

Financial Statements Directory chứa dữ liệu tài chính theo quý của hơn 1.500 mã, có trường hợp dài tới 20 năm. Mỗi doanh nghiệp có ba báo cáo nền tảng: báo cáo kết quả kinh doanh `_income_statement.csv` về doanh thu, chi phí và khả năng sinh lời; bảng cân đối `_balance_sheet.csv` về tài sản, nợ và vốn chủ; báo cáo lưu chuyển tiền tệ `_cash_flow_statement.csv` về hoạt động kinh doanh, đầu tư và tài trợ.

# Phụ lục H. Mẫu prompt của các agent

Các mục dưới đây dịch lại chính xác prompt cung cấp cho từng agent chuyên biệt. Placeholder trong ngoặc nhọn, ví dụ `{self_ticker}`, được điền khi chạy hệ thống. Tên khóa JSON và biến được giữ nguyên để có thể dùng trực tiếp khi dựng baseline.

## H.1. Fact Extraction Agent

[[PROMPT:Fact Extraction Agent]]
Bạn là một nhà phân tích tài chính có nhiệm vụ trích xuất các fact có cấu trúc từ transcript earnings call của một công ty.

Mã cổ phiếu công ty: {ticker}
Quý: {quarter}
Văn bản transcript: {raw_text}

NHIỆM VỤ:
1. Đọc văn bản và xác định mọi phát biểu có thể định lượng, chỉ số hiệu quả chính (KPI), guidance hướng tới tương lai và đánh giá định tính về kết quả.
2. Với mỗi phát biểu đã xác định, tạo một đối tượng JSON có các khóa: `statement`, `metric`, `value` và `type`.

Đầu ra phải là một danh sách JSON chứa các đối tượng fact có cấu trúc này.
[[ENDPROMPT]]

## H.2. Comparative Peers Agent

[[PROMPT:Comparative Peers Agent]]
Bạn đang phân tích transcript earnings call của một công ty cùng với các phát biểu của những công ty tương đồng.

Mã cổ phiếu của công ty: {self_ticker}
Các Fact của công ty: {json.dumps(facts, indent=2)}
Peer_Facts: {json.dumps(related_facts, indent=2)}

NHIỆM VỤ:
- Với từng fact nếu có thể, mô tả cách giải thích của công ty về kết quả của chính mình khác với các công ty khác như thế nào.
- Trích dẫn bằng chứng thực tế từ các cuộc gọi lịch sử.

Giữ phân tích súc tích. Không bàn về những lĩnh vực không được đề cập.
[[ENDPROMPT]]

## H.3. Historical Earnings Agent

[[PROMPT:Historical Earnings Agent]]
Bạn đang phân tích transcript earnings call của một công ty so với các earnings call trước đây của chính công ty đó.

Các Fact hiện tại: {json.dumps(fact, indent=2)}
Quý hiện tại: {current_quarter}
Các Fact lịch sử: {json.dumps(related_facts, indent=2)}

NHIỆM VỤ:
1. Kiểm chứng guidance trước đây: với mỗi phát biểu hướng tới tương lai từ các quý trước, cho biết công ty đã đạt, vượt hay bỏ lỡ guidance đó trong {current_quarter}. Dẫn số liệu cụ thể, ví dụ: “Tăng trưởng doanh thu đạt 12% so với guidance 10% trong 2024-Q3”.
2. So sánh kết quả: đối chiếu kết quả hiện tại đang được thảo luận với kết quả lịch sử và nêu số liệu cụ thể.
3. Cung cấp bằng chứng: định dạng mỗi dòng bằng chứng là `metric: phát biểu lịch sử -> kết quả hiện tại`.
4. Nêu kết quả bất ngờ: xác định trường hợp ban lãnh đạo không đề cập một so sánh lịch sử quan trọng hoặc kết quả lệch mạnh khỏi xu hướng; giải thích vì sao điều đó quan trọng.
[[ENDPROMPT]]

## H.4. Financials-Statement Agent

[[PROMPT:Financials-Statement Agent]]
Bạn đang rà soát transcript earnings call của một công ty và so sánh một fact quan trọng với báo cáo tài chính lịch sử.

Fact hiện tại của quý: {json.dumps(fact, indent=2)}
Các Fact quá khứ tương đồng: {json.dumps(similar_facts, indent=2)}

NHIỆM VỤ:
- So sánh trực tiếp: đối chiếu fact hiện tại với từng fact quá khứ; nêu quý, chỉ tiêu và giá trị; làm nổi bật xu hướng.
- Kết quả được hỗ trợ: xác định nơi bình luận của ban lãnh đạo được dữ liệu tài chính xác nhận.
- Kết quả bất ngờ: làm nổi bật kết quả ban lãnh đạo không đề cập hoặc lệch khỏi xu hướng lịch sử; giải thích ý nghĩa đối với nhà đầu tư.

Tập trung vào cải thiện kết quả cuối cùng như lợi nhuận ròng. Lưu ý số liệu có thể được ghi theo đơn vị vạn (wan) hoặc trăm triệu (yi); cần quy đổi đúng khác biệt về thang đo.
[[ENDPROMPT]]

## H.5. Synthesis & Prediction Agent

[[PROMPT:Synthesis & Prediction Agent]]
Bạn là người đưa ra phán quyết cuối cùng trong một hệ thống phân tích tài chính đa agent. Hãy tổng hợp phát hiện của ba agent chuyên biệt để dự báo phản ứng giá cổ phiếu.

Các phân tích nhận được:
- Phân tích đồng cấp: {peer_analysis_summary}
- Phân tích lịch sử: {historical_analysis_summary}
- Phân tích báo cáo tài chính: {financials_analysis_summary}

NHIỆM VỤ:
1. Tổng hợp phát hiện: viết một đoạn tóm tắt điều hành tích hợp hiểu biết từ cả ba phân tích.
2. Xác định động lực chính: liệt kê 3-5 yếu tố quan trọng nhất, tích cực hoặc tiêu cực, có khả năng ảnh hưởng tới tâm lý nhà đầu tư.
3. Dự báo cú sốc giá: dựa trên bằng chứng, phân loại kết quả thành `Positive Shock`, `Negative Shock` hoặc `Neutral`.
4. Biện minh dự báo: đưa ra lý do súc tích dựa trên bằng chứng, tham chiếu cụ thể tới phân tích của các agent.
[[ENDPROMPT]]

# Phụ lục I. Các chỉ tiêu chính trích xuất từ báo cáo tài chính

Để giữ đầu vào có cấu trúc ở quy mô xử lý được nhưng vẫn bao quát kinh tế, nhóm tác giả rút khoảng 15 dòng chỉ tiêu trong mỗi bảng cân đối, báo cáo kết quả kinh doanh và lưu chuyển tiền tệ xuống còn 15 chỉ tiêu lõi. Các chỉ tiêu cho agent góc nhìn giàu thông tin về nền tảng doanh nghiệp, có thể so sánh theo chiều dọc và chiều ngang trong CTKG. Chúng được nhúng thành nút Fact và nối với Quarter/Ticker để agent suy luận xu hướng thời gian và chuẩn cùng ngành.

**Bảng 9. Mười lăm chỉ tiêu báo cáo tài chính truyền cho các agent suy luận.**

| Chủ đề kinh tế | Các dòng dữ liệu được thu nhận |
|---|---|
| Sức mạnh bảng cân đối | Tiền và tương đương tiền; khoản phải thu; hàng tồn kho; bất động sản, nhà xưởng và thiết bị; nợ ngắn hạn; tổng nợ ngắn hạn; tổng nợ phải trả; tổng vốn chủ sở hữu |
| Khả năng sinh lời và biên lợi nhuận | Lợi nhuận ròng; lợi nhuận gộp; khấu hao hữu hình và vô hình |
| Động lực dòng tiền | Dòng tiền thuần từ hoạt động kinh doanh; dòng tiền thuần từ hoạt động đầu tư; dòng tiền thuần từ hoạt động tài trợ |
| Hiệu quả trên mỗi cổ phiếu | Lợi nhuận pha loãng trên cổ phiếu phổ thông |

# Phụ lục J. Ví dụ các Fact trích xuất từ earnings call

Dưới đây là các fact được Fact Extraction Agent trích xuất từ một earnings call duy nhất của ALTO, quý III/2023. Mỗi mục nêu loại fact, agent nhận fact và Reason. Tài liệu bổ sung cung cấp khoảng 1.000 cuộc gọi có fact liên kết.

- **Adjusted EBITDA:** 4,7 triệu USD. Loại: Result. Agent: Historic Performance. Reason: EBITDA điều chỉnh dương so với mức âm 20,6 triệu USD năm 2022.

- **Lợi nhuận gộp:** Cải thiện so với cùng kỳ 2022. Loại: Result. Agent: Historic Performance. Reason: Biên lợi nhuận crush tốt.

- **Sản lượng:** Thấp hơn dự kiến. Loại: Result. Agent: Historic Performance. Reason: Thời gian dừng máy ngoài kế hoạch cao bất thường.

- **Doanh số cồn chuyên dụng:** 85 triệu gallon. Loại: Result. Agent: Historic Performance. Reason: Tiến gần con số này dù nhu cầu người tiêu dùng thấp hơn.

- **Mức basis của ngô:** Tăng 0,31 USD so với kỳ trước. Loại: Result. Agent: Historic Performance. Reason: Cho thấy mức tăng mạnh theo quý.

- **Lỗ phái sinh:** 3,7 triệu USD. Loại: Result. Agent: Historic Performance. Reason: Tác động bất lợi của chiến lược phòng hộ.

- **Mục tiêu EBITDA điều chỉnh thường niên, giữa năm 2026:** Trên 65 triệu USD. Loại: Forward-Looking. Agent: Historic Earnings. Reason: Hoàn thành các dự án ngắn hạn.

- **Mục tiêu EBITDA điều chỉnh thường niên năm 2027:** Khoảng 125 triệu USD. Loại: Forward-Looking. Agent: Historic Earnings. Reason: Men, CCS và các sáng kiến dài hạn khác.

- **Mùa ký hợp đồng 2024:** Tiến độ cho thấy có thể vượt lượng gallon giao năm 2023. Loại: Forward-Looking. Agent: Historic Earnings. Reason: Giá premium so với ethanol cấp nhiên liệu.

- **Doanh số cồn chuyên dụng năm 2024:** Mục tiêu 90 triệu gallon. Loại: Forward-Looking. Agent: Historic Earnings. Reason: Dựa trên tiến độ ký hợp đồng hiện tại.

- **Chi phí sửa chữa và bảo trì:** Tăng đáng kể. Loại: Risk Disclosure. Agent: Competitor Analyst, Historic Earnings. Reason: Gây tác động bất lợi tới sản lượng.

- **Hạn chế chuỗi cung ứng:** Ảnh hưởng đáng kể tới chi phí lắp đặt. Loại: Risk Disclosure. Agent: Competitor Analyst, Historic Earnings. Reason: Tăng trên 70% so với ước tính ban đầu.

- **Môi trường thị trường vốn:** Khó khăn. Loại: Risk Disclosure. Agent: Competitor Analyst, Historic Earnings. Reason: Ảnh hưởng tới tài trợ và ưu tiên dự án.

- **Nhu cầu khách hàng:** Thấp hơn kỳ vọng. Loại: Risk Disclosure. Agent: Competitor Analyst, Historic Earnings. Reason: Ảnh hưởng doanh số và lợi nhuận.

- **Giọng điệu tổng thể:** Tích cực. Loại: Sentiment. Agent: Không, giữ cho bước tổng hợp. Reason: “Chúng tôi vẫn hào hứng về triển vọng và tin tưởng vào chiến lược tăng trưởng dài hạn”.

- **Mức tự tin của ban lãnh đạo:** Lạc quan. Loại: Sentiment. Agent: Không, giữ cho bước tổng hợp. Reason: “Chúng tôi tiếp tục giải quyết từng phần và đạt tiến bộ tốt”.

- **Môi trường kinh tế:** Điều kiện hiện tại ảnh hưởng tiến độ. Loại: Macro. Agent: Không, chỉ làm ngữ cảnh. Reason: “Dựa trên môi trường kinh tế hiện tại”.

- **Nhu cầu thị trường:** Phản ánh việc người mua quản lý tồn kho. Loại: Macro. Agent: Không, chỉ làm ngữ cảnh. Reason: “Cam kết của khách hàng không chỉ dựa trên nhu cầu thị trường”.

- **Mô hình mua hàng mùa đông:** Giảm sâu theo mùa từ quý III. Loại: Macro. Agent: Không, chỉ làm ngữ cảnh. Reason: Xu hướng mùa vụ ảnh hưởng doanh số.

- **Dòng tiền từ hoạt động kinh doanh:** 23 triệu USD. Loại: Result. Agent: Historic Performance. Reason: Báo cáo cho quý III.

- **Chi đầu tư theo quý:** 7 triệu USD. Loại: Result. Agent: Historic Performance. Reason: Đầu tư nhà máy từ đầu năm đạt 25 triệu USD.

- **Số dư tiền mặt:** 26 triệu USD. Loại: Result. Agent: Historic Performance. Reason: Tại ngày 30/09/2023.

- **Tổng hạn mức vay:** 118 triệu USD. Loại: Result. Agent: Historic Performance. Reason: Hỗ trợ vận hành và tăng trưởng.

- **Hạn mức tín dụng vận hành:** 53 triệu USD. Loại: Result. Agent: Historic Performance. Reason: Một phần tổng hạn mức vay.

- **Khoản vay có kỳ hạn:** 40 triệu USD. Loại: Result. Agent: Historic Performance. Reason: Một phần tổng hạn mức vay.

- **Quyền chọn yêu cầu vay bổ sung:** Tối đa 25 triệu USD. Loại: Result. Agent: Historic Performance. Reason: Có thể dùng cho vận hành.

- **Thời gian hoạt động và độ tin cậy tương lai:** Kỳ vọng hưởng lợi từ sửa chữa. Loại: Forward-Looking. Agent: Historic Earnings. Reason: Hoàn thành trong quý.

- **Thách thức vận hành:** Gián đoạn không liên tục. Loại: Risk Disclosure. Agent: Competitor Analyst, Historic Earnings. Reason: Chịu nhiều thách thức thị trường.

- **Cải thiện hiệu suất dầu ngô:** Đạt được tại nhà máy xay khô Pekin. Loại: Result. Agent: Historic Performance. Reason: Tối ưu quy trình riêng của thiết kế ICM.

- **Dự án thu giữ và lưu trữ carbon:** Đang tiến triển với đối tác. Loại: Forward-Looking. Agent: Historic Earnings. Reason: Thiết kế đường ống và hệ thống lưu trữ.

# Phụ lục K. Ví dụ phân tích của Synthesis & Prediction Agent

Dưới đây là ví dụ đầu vào từ một earnings call duy nhất của ALTO, quý II/2023, được chuyển vào agent tổng hợp và dự báo cuối.

## So sánh trực tiếp

Các fact hiện tại cho thấy adjusted EBITDA 16 triệu USD, dòng tiền kinh doanh dương, mức sử dụng công suất 81%, số dư tiền mặt 23 triệu USD và tổng hạn mức vay tới 114 triệu USD. Các con số phản ánh sức mạnh vận hành và thanh khoản được cải thiện.

## Các fact quá khứ tương đồng nhất

Kết quả quá khứ tạo ngữ cảnh hữu ích. Dòng tiền thuần từ hoạt động tài trợ từng âm 221,50 nghìn USD, nên hiện tại cho thấy chuyển dịch sang quản trị dòng tiền tốt hơn. Lợi nhuận ròng là 22,11 triệu USD, cao hơn adjusted EBITDA hiện tại 16 triệu USD, cho thấy khả năng sinh lời vẫn là thách thức. EPS pha loãng 0,30 tiếp tục nhấn mạnh trọng tâm lợi nhuận. Chi phí vận hành 353 triệu USD cho thấy quy mô chi phí lớn so với EBITDA.

Tiền và tương đương tiền 21,20 triệu USD trước đây thấp hơn 23 triệu USD hiện tại, cho thấy thanh khoản mạnh hơn. Lợi nhuận gộp 8,85 triệu USD thấp đáng kể so với EBITDA hiện tại, phản ánh hiệu quả đã cải thiện. Dòng tiền thuần từ hoạt động kinh doanh 9,64 triệu USD, trong khi số dương hiện tại cho thấy khả năng tạo tiền tốt hơn. Tổng nợ ngắn hạn 14,94 triệu USD giúp đặt nghĩa vụ vào bối cảnh thanh khoản.

## Xu hướng đáng chú ý

Số dư tiền tăng từ 21,20 lên 23 triệu USD cho thấy quản trị thanh khoản tốt hơn. Chuyển sang dòng tiền kinh doanh dương phản ánh hiệu quả cao hơn; adjusted EBITDA tăng cho thấy vận hành mạnh hơn, dù vẫn thấp hơn mức lợi nhuận ròng lịch sử.

## Kết quả được hỗ trợ

Việc ban lãnh đạo nhấn mạnh đạt dòng tiền kinh doanh dương được số liệu xác nhận. Sự tự tin về cải thiện EBITDA cũng có cơ sở, dù vẫn còn dư địa nâng khả năng sinh lời.

## Kiểm chứng guidance trước đây

Các phát biểu hướng tới tương lai dự kiến các dự án vốn tạo thêm trên 65 triệu USD EBITDA thường niên vào năm 2025 và khoảng 125 triệu USD từ CCS cùng các sáng kiến khác vào năm 2026. Dù chưa thể so trực tiếp với số hiện tại, tiến độ dự án cho thấy doanh nghiệp đang hướng tới mục tiêu.

## So sánh các kết quả được thảo luận

Dòng tiền kinh doanh năm 2023 là dương so với 9,64 triệu USD năm 2022. Lợi nhuận ròng cũng dương, cải thiện so với mức 22,11 triệu USD được ghi nhận năm 2022 theo phần phân tích của mô hình. Chi tiêu vốn đạt 8 triệu USD, một khoản đầu tư đáng kể cho quá trình chuyển đổi.

## Bằng chứng hỗ trợ

Dòng tiền kinh doanh cải thiện từ 9,64 triệu USD lên mức dương trong năm 2023. Lợi nhuận ròng chuyển sang dương. CapEx 8 triệu USD thể hiện cam kết chuyển đổi dài hạn.

## Phân tích so với doanh nghiệp tương đồng

ALTO nhấn mạnh sự lạc quan và chuyển giao lãnh đạo, khác với các doanh nghiệp đồng cấp chủ yếu báo cáo số liệu tài chính. Sự phù hợp với Low Carbon Fuel Standard được trình bày như lợi thế dài hạn, trong khi đối thủ nhấn mạnh tác động tài chính tức thời. ALTO công khai áp lực lạm phát và giá ngô tăng, còn các công ty đồng cấp ít đề cập. Kỷ luật thị trường được xem là yếu tố hỗ trợ biên lợi nhuận; CapEx được mô tả như khoản đầu tư chuyển đổi với trọng tâm là chi tiêu từ đầu năm. ALTO còn nêu mua lại cổ phiếu trong chiến lược vốn, chủ đề không xuất hiện ở báo cáo của đối thủ.

## Kết luận của ví dụ

ALTO làm nổi bật tâm lý ban lãnh đạo, đầu tư chiến lược và điều kiện thị trường, qua đó khác biệt với doanh nghiệp đồng cấp chỉ tập trung vào kết quả tài chính. Công ty đạt adjusted EBITDA 16 triệu USD, sử dụng công suất 81% và dòng tiền kinh doanh dương trong năm 2023. Sự lạc quan của lãnh đạo, các dự án vốn và thay đổi pháp lý thuận lợi cho thấy quỹ đạo tích cực của tăng trưởng lợi nhuận.
