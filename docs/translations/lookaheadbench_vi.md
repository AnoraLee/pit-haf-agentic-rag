# LOOK-AHEAD-BENCH

## Một chuẩn đánh giá tiêu chuẩn hóa về thiên lệch nhìn trước trong các LLM Point-in-Time dành cho tài chính

**Tác giả:** Mostapha Benhenda

**Bản gốc:** arXiv:2601.13770v1 [cs.AI], ngày 20 tháng 01 năm 2026

**Thông tin liên hệ:** Mostapha Benhenda, mostaphabenhenda@gmail.com

> **Ghi chú bản dịch:** Trong tài liệu này, "look-ahead bias" được dịch là "thiên lệch nhìn trước"; "Point-in-Time (PiT)" được giữ nguyên để chỉ mô hình hoặc quy trình chỉ sử dụng thông tin có thể biết tại đúng thời điểm ra quyết định. Tên mô hình, tên hệ thống, công thức và số liệu được giữ theo bản gốc. Đây là bản dịch phục vụ học tập, không phải bản dịch chính thức của tác giả.

# Tóm tắt

Chúng tôi giới thiệu Look-Ahead-Bench, một chuẩn đánh giá được tiêu chuẩn hóa nhằm đo lường thiên lệch nhìn trước trong các Mô hình Ngôn ngữ Lớn (LLM) Point-in-Time (PiT) bên trong các quy trình tài chính thực tế và mang tính ứng dụng. Khác với phần lớn phương pháp hiện có vốn chủ yếu kiểm tra tri thức nhìn trước nội tại thông qua hỏi đáp, benchmark của chúng tôi đánh giá hành vi của mô hình trong các tình huống thực tiễn. Để phân biệt năng lực dự báo thực sự với hiệu năng dựa trên ghi nhớ, chúng tôi phân tích sự suy giảm hiệu năng giữa các chế độ thị trường khác biệt về thời gian, đồng thời đưa vào một số baseline định lượng để thiết lập các ngưỡng hiệu năng.

Chúng tôi đánh giá các LLM nguồn mở nổi bật - Llama 3.1 (8B và 70B) và DeepSeek 3.2 - so với họ mô hình LLM Point-in-Time của PiT-Inference, gồm Pitinf-Small, Pitinf-Medium và mô hình cấp độ tiên phong Pitinf-Large. Kết quả cho thấy các LLM tiêu chuẩn có thiên lệch nhìn trước đáng kể, được đo bằng sự suy giảm alpha. Ngược lại, các mô hình Pitinf thể hiện khả năng tổng quát hóa và suy luận được cải thiện khi kích thước mô hình tăng lên. Công trình này đặt nền móng cho việc đánh giá có chuẩn hóa đối với thiên lệch thời gian trong LLM tài chính, đồng thời cung cấp một khuôn khổ thực tiễn để nhận diện các mô hình phù hợp cho triển khai trong thế giới thực. Mã nguồn được công bố tại https://github.com/benstaf/lookaheadbench.

# 1. Giới thiệu

Các Mô hình Ngôn ngữ Lớn đang tạo ra thay đổi lớn trong tài chính định lượng. FinGPT (Yang và cộng sự, 2023), BloombergGPT (Wu và cộng sự, 2023), FinMem (Yu và cộng sự, 2023), FinRL-DeepSeek (Benhenda, 2025), TradingAgents (Xiao và cộng sự, 2025), cùng với các kiến trúc đa tác tử như Hedge-Agents (Li và cộng sự, 2025a) và AI Hedge Fund (Singh, 2025), đã thể hiện năng lực đáng chú ý trong xử lý dữ liệu tài chính, tạo tín hiệu giao dịch và thực thi các chiến lược đầu tư phức tạp.

Tuy nhiên, phía sau những kết quả đầy hứa hẹn này là một thách thức phương pháp luận nền tảng, đe dọa tính hợp lệ của các ứng dụng tài chính dựa trên LLM: **thiên lệch nhìn trước**.

Thiên lệch nhìn trước xảy ra khi mô hình truy cập thông tin vốn chưa thể có tại thời điểm dự báo. Điều này tạo ra các chỉ số hiệu năng bị thổi phồng giả tạo và những kết quả ấy biến mất khi triển khai trong thực tế. Vì vậy, lợi nhuận backtest thường sụp giảm sau khi vượt qua cửa sổ tri thức của mô hình và hoạt động giao dịch bước vào vùng dữ liệu thực sự chưa từng biết (Li và cộng sự, 2025b).

## 1.1. Thách thức của thiên lệch thời gian trong LLM tài chính

LLM được tiền huấn luyện trên các kho dữ liệu quy mô web chứa lượng lớn thông tin tài chính, bao gồm các giải thích hậu nghiệm về sự kiện thị trường, biến động giá lịch sử và các phân tích hồi cứu. Khi LLM gặp một prompt về "hiệu quả của NVIDIA trong năm 2023", mô hình có thể đã được huấn luyện trên văn bản nêu rõ "NVIDIA tăng 190% trong năm 2023 nhờ làn sóng AI" (Li và cộng sự, 2025b). Trong trường hợp này, mô hình không học quan hệ dự báo; nó ghi nhớ kết quả rồi thuật lại kết quả đó trong quá trình đánh giá.

Sự nhiễm bẩn từ dữ liệu tiền huấn luyện tạo ra các thiên lệch có hệ thống, đặc biệt nguy hiểm trong tài chính - nơi quan hệ nhân quả theo thời gian có vai trò tối quan trọng. Nhiều nghiên cứu đã ghi nhận các biểu hiện khác nhau của vấn đề này:

- **Rò rỉ dữ liệu huấn luyện:** Mô hình nhớ lại trực tiếp giá cổ phiếu, số liệu lợi nhuận và sự kiện thị trường cụ thể từ kho dữ liệu huấn luyện (Lopez-Lira và cộng sự, 2025b).
- **Ghi nhớ thực thể:** Ngay cả khi định danh đã được che, mô hình vẫn có thể nhận ra doanh nghiệp từ các manh mối ngữ cảnh và truy xuất hiệu quả lịch sử liên quan (Sarkar và Vafa, 2024).
- **Thất bại trong suy luận thời gian:** Mô hình gặp khó khăn khi phân biệt thông tin có thể biết tại các thời điểm khác nhau, dẫn đến những dự báo bất khả thi về mặt logic (Yan và Tang, 2026; Gao và cộng sự, 2025).

## 1.2. Hạn chế của các phương pháp đánh giá hiện tại

Các phương pháp phát hiện thiên lệch nhìn trước hiện có chủ yếu tập trung vào kiểm tra tri thức nội tại thông qua tác vụ hỏi đáp hoặc đánh giá khả năng ghi nhớ những dữ kiện cụ thể. Dù có giá trị, các phương pháp này có thể không phản ánh được hậu quả thực tế của thiên lệch trong những bối cảnh tài chính ngoài đời thực.

Phép thử mang tính thực dụng đối với năng lực của một mô hình tài chính không nằm ở việc nó có thể hay không thể nhớ lại các mẫu hình lịch sử từ dữ liệu huấn luyện, mà nằm ở khả năng tổng quát hóa trong thực tế trước những điều kiện thị trường thực sự mới.

## 1.3. Các đóng góp của nghiên cứu

Chúng tôi giới thiệu Look-Ahead-Bench, một benchmark được tiêu chuẩn hóa nhằm giải quyết các hạn chế nói trên thông qua ba đóng góp chính:

1. **Tích hợp quy trình giao dịch thực tiễn:** Khác với các benchmark dựa trên tri thức, đánh giá của chúng tôi sử dụng các hệ thống giao dịch tác tử có tính thực tế, đưa ra quyết định danh mục thực sự. Chúng tôi sử dụng framework AI Hedge Fund (Singh, 2025), một dự án nguồn mở được sử dụng rộng rãi với hơn 45 nghìn sao trên GitHub, qua đó đưa hoạt động đánh giá vượt ra ngoài các bài toán đồ chơi để xem xét khả năng triển khai trong thế giới thực.
2. **Đánh giá LLM Point-in-Time:** Chúng tôi đánh giá trực tiếp các mô hình Pitinf - các LLM thương mại được thiết kế chuyên biệt để loại bỏ thiên lệch nhìn trước một cách hiệu quả - cùng với các mô hình nền tảng tiêu chuẩn.
3. **Chỉ số Alpha Decay:** Chúng tôi giới thiệu một chỉ số nghiêm ngặt để đo thiên lệch bằng cách định lượng mức sụt giảm hiệu năng giữa giai đoạn trong mẫu, tức cửa sổ huấn luyện, và giai đoạn ngoài mẫu trong tương lai.

Kết quả cho thấy các LLM tiêu chuẩn có thiên lệch nhìn trước đáng kể, với alpha decay thấp hơn -15 điểm phần trăm giữa hai giai đoạn, trong khi các mô hình Pitinf duy trì hiệu năng ổn định. Nghiên cứu này cung cấp một công cụ chẩn đoán để nhận diện thiên lệch trong LLM tài chính.

# 2. Công trình liên quan

## 2.1. Thiên lệch nhìn trước trong LLM tài chính

Thiên lệch nhìn trước ngày càng được nhìn nhận rộng rãi như một vấn đề nghiêm trọng trong các ứng dụng LLM tài chính. Glasserman và Lin (2023) thực hiện một trong những đánh giá có hệ thống sớm nhất, khảo sát cả thiên lệch nhìn trước và hiệu ứng gây xao nhãng trong phân tích cảm xúc dựa trên GPT để dự đoán lợi suất cổ phiếu. Công trình cho thấy việc ẩn danh định danh doanh nghiệp có thể cải thiện hiệu năng nhờ giảm hiệu ứng gây xao nhãng, đồng thời nhấn mạnh khó khăn trong việc tách biệt phân tích cảm xúc thực sự khỏi các liên hệ đã được ghi nhớ.

Levy (2025) nhấn mạnh hệ quả đối với các ứng dụng tài chính và đề xuất những chiến lược giảm thiểu, bao gồm quản lý cẩn thận mốc cắt dữ liệu và trung hòa embedding của thực thể. Gao và cộng sự (2025) phát triển một kiểm định thống kê để phát hiện thiên lệch nhìn trước bằng Lookahead Propensity (LAP), một đại lượng dựa trên kỹ thuật tấn công suy luận thành viên. Phương pháp này liên hệ mức độ quen thuộc của mô hình với dữ liệu huấn luyện - được ước lượng bằng phân tích xác suất token - với độ chính xác dự báo. Dù sáng tạo, phương pháp tập trung vào các tác vụ dự báo riêng lẻ thay vì đánh giá hệ thống giao dịch đầu-cuối.

Những nghiên cứu khác đã mở rộng cả khía cạnh thực nghiệm và phương pháp luận trong việc khảo sát thiên lệch nhìn trước của mô hình ngôn ngữ tài chính. Chúng đề xuất các phép chẩn đoán chuẩn hóa, đánh giá theo dạng benchmark và kiểm thử sức chịu đựng có kiểm soát theo thời gian, qua đó chỉ ra sự phóng đại hiệu năng do nhiễm dữ liệu tương lai trong bối cảnh dự báo và giao dịch (Noguer i Alonso, 2024; Lopez-Lira và cộng sự, 2025a).

## 2.2. Rò rỉ thông tin và ghi nhớ

Vấn đề rộng hơn về rò rỉ thông tin trong LLM đã nhận được nhiều sự quan tâm. Li và cộng sự (2025b) giới thiệu FinLeak-Bench và framework FactFin để định lượng có hệ thống vấn đề rò rỉ theo bốn chiều, đồng thời cho thấy phần lớn các agent dựa trên LLM đã công bố không thể vượt baseline sau khi đi qua knowledge cutoff của chúng.

Lopez-Lira và cộng sự (2025b) ghi nhận "vấn đề ghi nhớ" thông qua việc kiểm thử rộng khả năng nhớ lại của GPT-4o. Kết quả cho thấy mô hình có thể nhớ chính xác giá đóng cửa của S&P 500 với sai số dưới 1% đối với các ngày nằm trong cửa sổ huấn luyện, trong khi sai số "bùng nổ" đối với các ngày sau cutoff. Carlini và cộng sự (2021; 2022) thiết lập nền tảng lý thuyết và thực nghiệm để hiểu hiện tượng ghi nhớ trong mô hình ngôn ngữ lớn, chứng minh rằng dữ liệu huấn luyện có thể được trích xuất khỏi mô hình bằng các truy vấn được thiết kế cẩn thận.

Các nghiên cứu bổ sung còn cho thấy sự nhiễm bẩn tiền huấn luyện và rò rỉ thời gian ngầm vẫn có thể tồn tại ngay cả khi không có dấu hiệu ngày tháng tường minh, đồng thời ảnh hưởng của rò rỉ tăng theo quy mô mô hình nếu không được giảm thiểu một cách chủ động (Kong và cộng sự, 2025; Drinkall và cộng sự, 2024).

## 2.3. Mô hình Point-in-Time và mô hình nhận biết thời gian

Sự phát triển của các mô hình Point-in-Time (PiT) là một phản ứng trực tiếp trước lo ngại về thiên lệch nhìn trước. Những mô hình như Time Machine GPT (Drinkall và cộng sự, 2024), ChronoGPT (He và cộng sự, 2025) và DatedGPT (Yan và Tang, 2026) đưa ra các framework nhận biết thời gian, trong đó mô hình được huấn luyện nghiêm ngặt chỉ trên dữ liệu trước cutoff để bảo đảm tính toàn vẹn thời gian. Các phương pháp này cho thấy ràng buộc thời gian tường minh có thể ngăn rò rỉ thông tin tương lai. Merchant và Levy (2025) đề xuất điều chỉnh logit bằng các mô hình phụ trợ chuyên biệt, cho phép loại bỏ cả tri thức nguyên văn và tri thức ngữ nghĩa mà không cần huấn luyện lại mô hình nền lớn.

Ngoài ra còn có các LLM Point-in-Time độc quyền được thiết kế cho backtesting, chẳng hạn các mô hình từ PiT-Inference (PiT-Inference, 2026). Chúng có ba kích thước: Small dưới 10 tỷ tham số dành cho tác vụ độ trễ thấp; Medium dưới 100 tỷ tham số; và Large trên 500 tỷ tham số dành cho các tác vụ suy luận cấp độ tiên phong.

## 2.4. Các hệ thống giao dịch tác tử

Việc ứng dụng LLM vào giao dịch tác tử đã tạo ra nhiều hệ thống mới. Yu và cộng sự (2023; 2024) phát triển FinMem và FinCon, thể hiện các khả năng memory và multi-agent tinh vi. Zhang và cộng sự (2024b) xây dựng một foundation agent đa phương thức được tăng cường bằng công cụ, trong khi Yang và cộng sự (2024) giới thiệu FinRobot cho nghiên cứu cổ phiếu và định giá.

Dự án nguồn mở AI Hedge Fund (Singh, 2025) cung cấp các agent giao dịch dựa trên LLM và được chọn làm nền tảng cho việc triển khai benchmark của chúng tôi nhờ ảnh hưởng đáng kể trong cộng đồng, với hơn 45 nghìn sao trên GitHub.

# 3. Phương pháp

## 3.1. Thiết kế hai giai đoạn

Đánh giá của chúng tôi so sánh hiệu năng mô hình trên hai giai đoạn được lựa chọn cẩn thận để kiểm thử các mô hình có knowledge cutoff đến năm 2023-2024, đồng thời duy trì đặc điểm thị trường tương tự nhằm bảo đảm so sánh công bằng, tương tự FinLeak-Bench (Li và cộng sự, 2025b).

**Giai đoạn P1 - trong mẫu:** từ ngày 01/04/2021 đến ngày 30/09/2021.

- Thời lượng: 6 tháng.
- Lợi suất Buy-and-Hold: +25,32%.
- Mục đích: thiết lập hiệu năng cơ sở bên trong cửa sổ có khả năng thuộc dữ liệu huấn luyện của Llama 3.1 (8B, 70B) và DeepSeek 3.2.

**Giai đoạn P2 - ngoài mẫu:** từ ngày 01/07/2024 đến ngày 31/12/2024.

- Thời lượng: 6 tháng.
- Chế độ thị trường: đợt tăng giá được thúc đẩy bởi AI, đi kèm cảm xúc trái chiều.
- Lợi suất Buy-and-Hold: +24,75%, tương tự P1.
- Mục đích: kiểm tra khả năng tổng quát hóa trong giai đoạn sau cutoff của Llama 3.1 (8B, 70B) và DeepSeek 3.2.

## 3.2. Danh mục và không gian giao dịch

Benchmark sử dụng một không gian giao dịch tập trung gồm năm cổ phiếu công nghệ vốn hóa lớn: AAPL (Apple Inc.), MSFT (Microsoft Corporation), GOOGL (Alphabet Inc.), NVDA (NVIDIA Corporation) và TSLA (Tesla Inc.).

## 3.3. Chỉ số đánh giá

### 3.3.1. Tính alpha

Đối với mỗi mô hình và mỗi giai đoạn, alpha được tính như sau:

> **α = R(LLM) - R(Buy & Hold)**  (1)

Đại lượng này đo lợi suất vượt trội do chiến lược LLM tạo ra so với baseline Buy-and-Hold thụ động.

### 3.3.2. Phân tích Alpha Decay

Chỉ báo thiên lệch cốt lõi là alpha decay giữa hai giai đoạn:

> **α(Decay) = α(P2) - α(P1)**  (2)

Alpha decay âm cho thấy hiệu năng tương đối của mô hình suy giảm trong giai đoạn ngoài mẫu, gợi ý khả năng có thiên lệch nhìn trước trong kết quả ở giai đoạn trong mẫu.

## 3.4. Các baseline định lượng

Chúng tôi so sánh các agent AI với một tập hợp chiến lược định lượng truyền thống. Các chiến lược bao quát cách tiếp cận thụ động, hệ thống, bám xu hướng và nghịch xu hướng, qua đó tạo thành mốc tham chiếu toàn diện để đánh giá hiệu năng tương đối và độ vững qua nhiều chế độ thị trường. Tất cả chiến lược sử dụng cùng vốn ban đầu, cho phép cổ phiếu phân số và tái cân bằng hàng tháng, trừ trường hợp có ghi chú khác.

### 3.4.1. Buy & Hold - thụ động

Baseline đơn giản nhất phân bổ vốn đều cho tất cả ticker tại đầu giai đoạn và giữ nguyên vị thế mà không tái cân bằng. Chiến lược này biểu diễn mức tiếp xúc thụ động, chỉ mua, đối với không gian cổ phiếu đã chọn và là tham chiếu để tính alpha.

### 3.4.2. Tái cân bằng hàng tháng theo trọng số bằng nhau - hệ thống

Chiến lược duy trì phân bổ giá trị bằng nhau cho từng ticker bằng cách tái cân bằng vào đầu mỗi tháng. Nó tạo mức tiếp xúc rộng với thị trường trong khi kiểm soát rủi ro tập trung, và thường vượt Buy-and-Hold đơn giản trong các không gian đa dạng hóa nhờ phần bù tái cân bằng.

### 3.4.3. Momentum 3 tháng, chọn nửa trên

Đây là chiến lược bám xu hướng cổ điển. Tại mỗi lần tái cân bằng hàng tháng, chiến lược xếp hạng ticker theo tổng lợi suất ba tháng trước đó và phân bổ đều cho nửa trên; nếu lịch sử không đủ, nó phân bổ đều cho tất cả ticker. Chiến lược khai thác tính tiếp diễn của xu hướng trung hạn và trong lịch sử là một trong những nhân tố định lượng vững nhất.

### 3.4.4. Mean Reversion 3 tháng, chọn nửa dưới

Đây là đối trọng nghịch xu hướng của Momentum. Tại mỗi lần tái cân bằng hàng tháng, chiến lược xếp hạng ticker theo lợi suất ba tháng trước đó và phân bổ đều cho nửa có hiệu năng thấp nhất; nếu lịch sử không đủ, nó phân bổ đều cho tất cả. Chiến lược đặt cược vào sự đảo chiều giá và thường hoạt động tốt trong chế độ đi ngang hoặc có độ phân tán cao, nhưng có thể chịu thiệt hại khi xu hướng mạnh.

### 3.4.5. Giao cắt đường trung bình động 50/100 ngày, tái cân bằng hàng ngày

Quy tắc bám xu hướng này chỉ nắm giữ một ticker khi đường trung bình động đơn giản 50 ngày của nó cao hơn đường trung bình động đơn giản 100 ngày. Vị thế được tái cân bằng hàng ngày: vốn được phân bổ đều cho tất cả ticker thỏa điều kiện; nếu không có ticker nào thỏa điều kiện thì giữ tiền mặt. Hệ thống hai đường trung bình động cổ điển này nhằm đi theo xu hướng trong khi tránh các đợt sụt giảm lớn.

### 3.4.6. Nhiễu ngẫu nhiên - nhóm đối chứng

Đây là một chiến lược cố ý ngây thơ. Mỗi ngày, nó áp dụng các trọng số ngẫu nhiên cho lợi suất ngày của từng ticker, gồm 40% xác suất vị thế mua, 40% xác suất vị thế bán và 20% xác suất trọng số bằng không, sau đó chuẩn hóa. Baseline "con khỉ ném phi tiêu" này giúp đánh giá liệu hiệu năng quan sát được có vượt qua những gì thuần ngẫu nhiên có thể đạt được trong cùng không gian hay không.

## 3.5. Các agent giao dịch dựa trên LLM

Chúng tôi triển khai agent giao dịch dựa trên LLM bằng framework nguồn mở AI Hedge Fund (Singh, 2025), một hệ thống proof-of-concept phổ biến để khám phá quyết định đầu tư dựa trên AI, có 45,3 nghìn sao trên GitHub tính đến tháng 01/2026. Repository có tại https://github.com/virattt/ai-hedge-fund.

Framework sử dụng kiến trúc đa tác tử, trong đó các agent chuyên biệt được hỗ trợ bởi LLM - gồm Valuation Agent, Sentiment Agent, Fundamentals Agent, Technicals Agent và các agent khác mô phỏng những nhà đầu tư nổi tiếng như Warren Buffett - phân tích dữ liệu thị trường và tạo tín hiệu giao dịch. Risk Manager Agent tính giới hạn vị thế dựa trên chỉ số rủi ro, còn Portfolio Manager Agent tổng hợp tín hiệu thành quyết định phân bổ cuối cùng. Các giao dịch chỉ được mô phỏng, không thực thi thật, nên framework phù hợp cho nghiên cứu và benchmark.

Các đặc điểm chính liên quan đến đánh giá gồm:

- Hỗ trợ nhiều nhà cung cấp LLM qua API: OpenAI, Groq, Anthropic và DeepSeek.
- Có sẵn khả năng truy cập dữ liệu giá lịch sử cho AAPL, GOOGL, MSFT, NVDA và TSLA mà không cần khóa API ngoài, phù hợp chính xác với không gian giao dịch của benchmark.

Trong thực nghiệm, framework được điều chỉnh theo giao thức tái cân bằng hàng tháng nhất quán với các baseline định lượng. Vào đầu mỗi tháng, agent nhận dữ liệu lịch sử đến thời điểm đó, tạo trọng số mục tiêu cho năm cổ phiếu; các trọng số sau đó được chuẩn hóa và thực thi trong mô phỏng. Hệ thống cho phép cổ phiếu phân số và sử dụng cùng mức vốn ban đầu.

Các mô hình được đánh giá trong quy trình tác tử gồm:

**Mô hình nền tảng tiêu chuẩn.** Đây là các LLM nguồn mở được sử dụng rộng rãi, có khả năng nhiễm dữ liệu huấn luyện kéo dài đến năm 2023-2024:

- Meta Llama 3.1 8B và 70B, có cutoff tháng 12/2023.
- DeepSeek 3.2, có cutoff tháng 07/2024.

**Mô hình Point-in-Time.** Họ Pitinf độc quyền của PiT-Inference được thiết kế với cutoff thời gian hiệu dụng vào tháng 01/2020 nhằm loại bỏ thiên lệch nhìn trước:

- Pitinf-Small, dưới 10B tham số, phù hợp cho tác vụ độ trễ thấp.
- Pitinf-Medium, dưới 100B tham số.
- Pitinf-Large, trên 500B tham số, dành cho hiệu năng suy luận cấp độ tiên phong.

# 4. Kết quả thực nghiệm

Bảng 1 tóm tắt hiệu năng của các baseline định lượng và mô hình AI trong cả hai giai đoạn.

**Bảng 1. So sánh hiệu năng giữa baseline định lượng và mô hình AI.** Lưu ý "Nghịch lý mở rộng quy mô" trong P2: mô hình tiêu chuẩn suy giảm khi quy mô tăng do các tiên nghiệm sai mạnh hơn, còn mô hình PiT cải thiện khi quy mô tăng nhờ suy luận sạch hơn.

| Mô hình / Chiến lược | Biến thể | Lợi suất P1 (%) | Alpha P1 (đpt) | Lợi suất P2 (%) | Alpha P2 (đpt) | Alpha Decay (đpt) |
|---|---|---:|---:|---:|---:|---:|
| **CHIẾN LƯỢC ĐỊNH LƯỢNG** | | | | | | |
| Buy & Hold | Thụ động | +25,32 | +0,00 | +24,75 | +0,00 | +0,00 |
| Equal Weight | Hệ thống | +25,68 | +0,36 | +22,33 | -2,42 | -2,78 |
| Momentum 3M | Hệ thống | +33,28 | +7,96 | +30,50 | +5,75 | -2,21 |
| Mean Reversion | Hệ thống | +20,70 | -4,62 | +9,35 | -15,40 | -10,78 |
| MA Crossover | Bám xu hướng | -2,46 | -27,78 | +6,91 | -17,84 | +9,94 |
| Random Noise | Đối chứng | +11,43 | -13,89 | +0,56 | -24,19 | -10,30 |
| **MÔ HÌNH AI - AGENT** | | | | | | |
| Llama 3.1 8B | Tiêu chuẩn | +39,13 | +13,81 | +21,33 | -3,42 | -17,23 |
| Llama 3.1 70B | Tiêu chuẩn | +44,59 | +19,27 | +28,77 | +4,02 | -15,25 |
| DeepSeek 3.2 | Tiêu chuẩn | +46,05 | +20,73 | +23,71 | -1,04 | -21,77 |
| Pitinf-Small | PiT | +25,07 | -0,25 | +24,81 | +0,06 | +0,31 |
| Pitinf-Medium | PiT | +27,76 | +2,44 | +28,04 | +3,29 | +0,85 |
| Pitinf-Large | PiT | +31,34 | +6,02 | +32,07 | +7,32 | +1,30 |

## 4.1. Các phát hiện chính

**So với các chiến lược định lượng:**

- **Độ vững của Momentum:** Chiến lược định lượng tốt nhất là Momentum tạo alpha +7,96 điểm phần trăm trong P1 và duy trì +5,75 điểm phần trăm trong P2, chỉ suy giảm nhẹ -2,21 điểm phần trăm.
- **Thất bại của Mean Reversion:** Chiến lược kém nhất là Mean Reversion suy giảm đáng kể -10,78 điểm phần trăm, cho thấy rủi ro của việc khớp quá mức chiến lược với một số chế độ hồi quy về trung bình cụ thể trong khi thị trường đang có xu hướng.

**Nghịch lý mở rộng quy mô và inverse scaling.** Kết quả chỉ ra sự khác biệt quan trọng trong tác động của việc tăng quy mô mô hình khi tồn tại thiên lệch nhìn trước. Chúng tôi gọi hiện tượng này là "Nghịch lý mở rộng quy mô":

- **Mô hình tiêu chuẩn - "Bẫy ký ức":** Đối với mô hình tiêu chuẩn, tăng quy mô thực tế làm tổn hại hiệu năng P2 so với đỉnh. DeepSeek 3.2 đạt Alpha P1 cao nhất, +20,73 điểm phần trăm, nhờ khả năng ghi nhớ dữ liệu năm 2021 tốt hơn, nhưng lại chịu mức sụp giảm nghiêm trọng nhất trong P2, với alpha decay -21,77 điểm phần trăm.
- **Diễn giải:** Điều này phù hợp với hiện tượng "inverse scaling" của McKenzie và cộng sự (2023), trong đó hiệu năng trên một số tác vụ giảm khi quy mô mô hình tăng. Trong dự báo tài chính, mô hình lớn hơn hình thành các tiên nghiệm mạnh hơn nhưng dễ gãy hơn dựa trên dữ liệu huấn luyện. Lopez-Lira và cộng sự (2025c) nhận xét rằng mô hình lớn nhớ chính xác các giá trị lịch sử tốt hơn, nhưng trí nhớ "như ảnh chụp" này trở thành bất lợi khi chế độ thị trường thay đổi. Khi được triển khai trong P2 năm 2024, các tiên nghiệm nội tại mạnh xung đột với thực tế, dẫn đến hallucination đầy tự tin và lấn át các tín hiệu ngữ cảnh tức thời.
- **Mô hình Point-in-Time - "Lợi tức của suy luận":** Ngược lại, họ Pitinf cho thấy quy luật mở rộng tích cực khi không còn thiên lệch. Sau khi loại bỏ tác nhân gây nhiễu là "ký ức tương lai", tăng quy mô mô hình cải thiện suy luận tài chính thực sự - như diễn giải cảm xúc và phân tích vĩ mô - thay vì chỉ mở rộng khả năng ghi nhớ đường giá lịch sử.

# 5. Kết luận và hướng nghiên cứu tương lai

Bài báo là một proof-of-concept cho thấy Look-Ahead-Bench có thể đóng vai trò công cụ chẩn đoán thiên lệch nhìn trước trong LLM tài chính. Các mô hình nền tảng tiêu chuẩn, dù mạnh, chịu alpha decay nghiêm trọng khi chuyển từ cửa sổ huấn luyện có thể đã ghi nhớ sang dữ liệu mới. Ngược lại, các mô hình Pitinf cho thấy khả năng tổng quát hóa tốt hơn.

Tuy nhiên, cần thực hiện thêm nhiều thí nghiệm.

## 5.1. Mở rộng phạm vi thực nghiệm

Đánh giá hiện tại chỉ giới hạn ở năm cổ phiếu công nghệ vốn hóa lớn của Hoa Kỳ. Để bảo đảm độ vững, cần các thiết lập backtest đa dạng hơn với ít nhất 20-30 cổ phiếu thuộc nhiều ngành, bao gồm:

- **Cổ phiếu vốn hóa nhỏ:** Nhóm này ít có khả năng bị ghi nhớ trong kho dữ liệu huấn luyện.
- **Các ngành ngoài công nghệ:** Ví dụ y tế và công nghiệp.
- **Tài sản đa dạng:** Hàng hóa hoặc ngoại hối, dù khả năng áp dụng LLM trong các lĩnh vực này có khác biệt.
- **Nhiều giai đoạn:** Kiểm thử ít nhất bốn giai đoạn có độ dài khác nhau.

## 5.2. Mở rộng mô hình và agent

Look-Ahead-Bench cần được bổ sung nhiều agent giao dịch hơn, chẳng hạn FinMem (Yu và cộng sự, 2023), FinGPT (Yang và cộng sự, 2023), FinRL-DeepSeek (Benhenda, 2025), TradingAgents (Xiao và cộng sự, 2025) và Hedge-Agents (Li và cộng sự, 2025a).

Phạm vi kiến trúc giao dịch tự trị cũng cần được mở rộng bằng cách tích hợp các agent chuyên biệt, gồm FinAgent (Zhang và cộng sự, 2024b), FinRobot (Yang và cộng sự, 2024) và StockAgent (Zhang và cộng sự, 2024a). Bên cạnh đó, cần đưa QuantAgent (Xiong và cộng sự, 2025) vào để bao quát chiến lược đầu tư định lượng, còn CryptoTrade (Li và cộng sự, 2024) sẽ mở rộng phạm vi sang thị trường tiền mã hóa.

Để đánh giá khả năng phân tích cơ bản và dự báo, cần xem xét các mô hình tập trung vào khám phá nhân tố và dự báo thị trường. Nhóm này gồm LLMFactor (Cao, 2025) cho khai phá nhân tố định lượng, cùng các agent dự báo như TradingGPT (Li và cộng sự, 2023), AlphaGPT (Wang và cộng sự, 2025), MarketGPT (Wheeler và Varner, 2024) và StockGPT (Mai, 2024). Các framework đánh giá như PIXIU (Xie và cộng sự, 2023) và FinPos (Bijia Liu và Ronghao Dang, 2025) cũng nên được sử dụng nhờ các tập dữ liệu toàn diện và hiểu biết về xác định quy mô vị thế.

Cuối cùng, để xử lý động lực thị trường phức tạp liên quan đến tương tác và giao dịch tần suất cao, benchmark cần được mở rộng để hỗ trợ môi trường học tăng cường đa tác tử. Điều này nên bao gồm các framework như Language Model Guided RL (Darmanin và Vella, 2025). Các công cụ gần đây như AutoTrader (RexiaAI, 2025) cũng cần được xem xét để bao quát phổ từ nguyên mẫu nghiên cứu đến hệ thống giao dịch có thể triển khai.

## 5.3. Mở rộng phương pháp backtesting

Benchmark nên vượt ra ngoài các đường giá lịch sử bằng cách sử dụng những kỹ thuật thẩm định nâng cao, bao gồm:

- **Dữ liệu tổng hợp và phản thực:** Kiểm tra cách mô hình phản ứng với những sự kiện thị trường có thể đã xảy ra nhưng thực tế không xảy ra.
- **Rademacher Anti-Serum (RAS):** Sử dụng các phương pháp như Paleologo (2025) đề xuất để kiểm tra nghiêm ngặt hiện tượng khớp quá mức trong backtesting.

# Tài liệu tham khảo

Tên công trình được giữ nguyên theo bản gốc để thuận tiện tra cứu.

Benhenda, M. (2025). FinRL-DeepSeek: LLM-infused risk-sensitive reinforcement learning for trading agents. https://arxiv.org/abs/2502.07393

Bijia Liu and Ronghao Dang. (2025). FinPos: A position-aware trading agent system for real financial markets. https://arxiv.org/abs/2510.27251

Cao, L. (2025). Chain-of-alpha: Unleashing the power of large language models for alpha mining in quantitative trading. https://arxiv.org/abs/2508.06312

Carlini, N., Tramer, F., Wallace, E., Jagielski, M., Herbert-Voss, A., Lee, K., Roberts, A., Brown, T., Song, D., Erlingsson, U., Oprea, A., and Raffel, C. (2021). Extracting training data from large language models. USENIX Security Symposium.

Carlini, N., Ippolito, D., Jagielski, M., Lee, K., Tramer, F., and Zhang, C. (2022). Quantifying memorization across neural language models. International Conference on Machine Learning (ICML).

Darmanin, A. and Vella, V. (2025). Language model guided reinforcement learning in quantitative trading. https://arxiv.org/abs/2508.02366

Drinkall, F., Rahimikia, E., Pierrehumbert, J. B., and Zohren, S. (2024). Time Machine GPT. https://arxiv.org/abs/2404.18543

Gao, Z., Jiang, W., and Yan, Y. (2025). A test of lookahead bias in LLM forecasts. https://arxiv.org/abs/2512.23847

Glasserman, P. and Lin, C. (2023). Assessing Look-Ahead Bias in Stock Return Predictions Generated By GPT Sentiment Analysis. https://arxiv.org/abs/2309.17322

He, S., Lv, L., Manela, A., and Wu, J. (2025). Chronologically consistent large language models. https://arxiv.org/abs/2502.21206

Kong, Y., Hwang, Y., Kaiser, M., Vryonides, C., Oomen, R., and Zohren, S. (2025). Fusing narrative semantics for financial volatility forecasting. https://arxiv.org/abs/2510.20699

Levy, B. (2025). Caution Ahead: Numerical Reasoning and Look-ahead Bias in AI Models. SSRN Electronic Journal. https://ssrn.com/abstract=5082861

Li, X., Zeng, Y., Xing, X., Xu, J., and Xu, X. (2025a). HedgeAgents: A Balanced-aware Multi-agent Financial Trading System. https://arxiv.org/abs/2502.13165

Li, X., Zeng, Y., Xing, X., Xu, J., and Xu, X. (2025b). Profit Mirage: Revisiting Information Leakage in LLM-based Financial Agents. https://arxiv.org/abs/2510.07920

Li, Y., Yu, Y., Li, H., Chen, Z., and Khashanah, K. (2023). TradingGPT: Multi-Agent System with Layered Memory and Distinct Characters for Enhanced Financial Trading Performance. https://arxiv.org/abs/2309.03736

Li, Y., Luo, B., Wang, Q., Chen, N., Liu, X., and He, B. (2024). A Reflective LLM-based Agent to Guide Zero-shot Cryptocurrency Trading. https://arxiv.org/abs/2407.09546

Lopez-Lira, A., Choi, C., Kim, Y., Kwon, J., Kim, J., and Yun, S. (2025a). Thematic Scoring: Quantifying Contextual Narratives using Language Models. SSRN Electronic Journal. https://ssrn.com/abstract=5233994

Lopez-Lira, A., Tang, Y., and Zhu, M. (2025b). The Memorization Problem: Can We Trust LLMs' Economic Forecasts? SSRN Electronic Journal. https://ssrn.com/abstract=5217505

Lopez-Lira, A., Tang, Y., and Zhu, M. (2025c). The Memorization Problem: Can We Trust LLMs' Economic Forecasts? arXiv:2504.14765. https://arxiv.org/abs/2504.14765

Mai, D. (2024). StockGPT: A GenAI Model for Stock Prediction and Trading. https://arxiv.org/abs/2404.05101

McKenzie, I. R., Lyzhov, A., Pieler, M., Parrish, A., Mueller, A., Prabhu, A., McLean, E., Kirtland, A., Ross, A., Liu, A., et al. (2023). Inverse Scaling: When Bigger Isn't Better. Transactions on Machine Learning Research. https://openreview.net/forum?id=DwgRm72GQF

Merchant, H. and Levy, B. (2025). A fast and effective solution to the problem of look-ahead bias in LLMs. https://arxiv.org/abs/2512.06607

Noguer i Alonso, M. (2024). Look-Ahead Bias in Large Language Models (LLMs): Implications and Applications in Finance. SSRN Electronic Journal. https://ssrn.com/abstract=5022165

Paleologo, G. A. (2025). The Elements of Quantitative Investing. John Wiley & Sons.

PiT-Inference. (2026). Introducing Pitinf models.

RexiaAI. (2025). AutoTrader: An automated trading framework using LLMs. https://github.com/RexiaAI/AutoTrader

Sarkar, A. and Vafa, K. (2024). Lookahead Bias in Pretrained Language Models. SSRN Electronic Journal. https://ssrn.com/abstract=4754678

Singh, V. (2025). AI hedge fund: Open-source framework for LLM-based trading agents. https://github.com/virattt/ai-hedge-fund

Wang, S., Yuan, H., Zhou, L., Ni, L. M., Shum, H.-Y., and Guo, J. (2025). Alpha-GPT: Human-AI Interactive Alpha Mining for Quantitative Investment. https://arxiv.org/abs/2308.00016

Wheeler, A. and Varner, J. (2024). MarketGPT: Developing a Pre-trained transformer (GPT) for Modeling Financial Time Series. https://arxiv.org/abs/2411.16585

Wu, S., Irsoy, O., Lu, S., Dabravolski, V., Dredze, M., Gehrmann, S., Kambadur, P., Rosenberg, D., and Mann, G. (2023). BloombergGPT: A large language model for finance. https://arxiv.org/abs/2303.17564

Xiao, Y., Sun, E., Luo, D., and Wang, W. (2025). TradingAgents: Multi-agents LLM financial trading framework. https://arxiv.org/abs/2412.20138

Xie, Q., Han, W., Zhang, X., Lai, Y., Peng, M., Lopez-Lira, A., and Huang, J. (2023). PIXIU: A Large Language Model, Instruction Data and Evaluation Benchmark for Finance. https://arxiv.org/abs/2306.05443

Xiong, F., Zhang, X., Feng, A., Sun, S., and You, C. (2025). QuantAgent: Price-Driven Multi-Agent LLMs for High-Frequency Trading. https://arxiv.org/abs/2509.09995

Yan, Y. and Tang, R. (2026). DatedGPT: Preventing Lookahead Bias in Large Language Models with Time-Aware Pre-training. AFA Poster Session 2026.

Yang, H., Liu, X.-Y., and Wang, C. D. (2023). FinGPT: Open-source financial large language models. https://arxiv.org/abs/2306.06031

Yang, H., Zhang, B., Wang, N., Guo, C., Zhang, X., Lin, L., Wang, J., Zhou, T., Guan, M., Zhang, R., and Wang, C. D. (2024). FinRobot: An open-source AI agent platform for financial applications using large language models. https://arxiv.org/abs/2405.14767

Yu, Y., Li, H., Chen, Z., Jiang, Y., Li, Y., Zhang, D., and Khashanah, K. (2023). FinMem: A performance-enhanced LLM trading agent with layered memory and character design. https://arxiv.org/abs/2311.13743

Yu, Y., Yao, Z., Li, H., Deng, Z., Cao, Y., Chen, Z., and Xie, Q. (2024). FinCon: A synthesized LLM multi-agent system with conceptual verbal reinforcement for enhanced financial decision making. https://arxiv.org/abs/2407.06567

Zhang, C., Liu, X., Zhang, Z., Jin, M., Li, L., Wang, Z., Hua, W., Shu, D., Zhu, S., Jin, X., Li, S., Du, M., and Zhang, Y. (2024a). When AI meets finance (StockAgent): Large language model-based stock trading in simulated real-world environments. https://arxiv.org/abs/2407.18957

Zhang, W., Zhao, L., Xia, H., Sun, S., Sun, J., Qin, M., Li, X., Zhao, Y., Zhao, Y., Cai, X., Zheng, L., Wang, X., and An, B. (2024b). A multimodal foundation agent for financial trading: Tool-augmented, diversified, and generalist. https://arxiv.org/abs/2402.18485
