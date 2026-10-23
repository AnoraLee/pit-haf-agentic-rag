# Đối chiếu nguồn 24 câu hỏi phát triển

Trợ lý đọc toàn trang PDF, kiểm tra trực quan tiêu đề, cột năm, đơn vị và phạm vi doanh nghiệp; đối chiếu với ngữ cảnh đã ghim và đầu ra đã lưu. Không chạy lại mô hình, không sửa kết quả gốc, không dùng làm nhãn kiểm thử độc lập.

**Nguồn gốc: trợ lý soạn; chưa được người dùng xác nhận độc lập.** Không thay đổi sổ đáp án tham chiếu thủ công hoặc tính độ chính xác ngữ nghĩa từ bản này.

Bộ câu hỏi: `20261019T030531Z-8ef1bf33`. Bản chạy gốc: `20261022T030940Z-22f948f0`.

Số trang dưới đây là trang PDF (bắt đầu từ 1), có thể khác số in trên tài liệu. Các mục tiêu 2025 là kế hoạch nêu trong báo cáo 2024. Kiểm tra nguồn này không xác nhận tính sẵn có tại thời điểm lịch sử (PiT).

## Nhận xét về hệ thống

- Bỏ sót bằng chứng có thể dùng: 4 câu.
- Thiếu ngữ cảnh; từ chối phù hợp: 4 câu.
- Bản nháp có sai sót đã bị chặn: 2 câu.
- Không có đáp án; ngữ cảnh mới hỗ trợ một phần: 5 câu.
- Có trích dẫn nhưng trả lời chưa đầy đủ/đúng trọng tâm: 4 câu.
- Có nhận định hữu ích, có cơ sở: 3 câu.
- Lỗi sinh đầu ra: 1 câu.
- Có trích dẫn nhưng dễ hiểu sai kỳ hoặc điều kiện: 1 câu.

Đây là phân loại định tính của trợ lý, không phải tỷ lệ đúng trên bộ kiểm thử độc lập. Bộ kiểm tra nguyên văn/số liệu có thể chặn số đúng khi năm/đơn vị ở ngoài câu trích; đồng thời trích dẫn hợp lệ vẫn có thể sai trọng tâm hoặc nhầm kế hoạch với thực hiện.

## 1. FPT — Kết quả lợi nhuận năm 2024 được nguồn mô tả như thế nào?

Năm 2024, FPT có lợi nhuận thuần từ hoạt động kinh doanh 11.025 tỷ VNĐ, lợi nhuận trước thuế 11.070 tỷ VNĐ và lợi nhuận sau thuế 9.427 tỷ VNĐ. Lợi nhuận sau thuế thuộc cổ đông công ty mẹ là 7.857 tỷ VNĐ. Đây là số làm tròn trong bảng tổng hợp hợp nhất.

**Ngữ cảnh model:** Hỗ trợ một phần. S1 trang 11 có dòng lợi nhuận hoạt động 11.025 và tăng 21,0%, nhưng đoạn cắt không chứa đơn vị và các dòng lợi nhuận trước/sau thuế. S2 có biên lợi nhuận hoạt động 17,5%.

**Đối chiếu kết quả:** Bỏ sót bằng chứng có thể dùng. Không có nhận định được chấp nhận. Hai nhận định về lợi nhuận hoạt động và biên lợi nhuận phù hợp với toàn trang, nhưng bộ kiểm tra chặn vì năm 2024 không nằm ngay trong câu trích dẫn. Phần khai báo thiếu thông tin cũng mâu thuẫn với dữ liệu hoạt động đã có.

Nguồn: [trang PDF 11](../../data/cache/evidence/blobs/04/041c5a2ac49f0e8f4a29f2b1fdb82aea00608579ad33c0606adf9ad06dd8da40#page=11).

Case `dev01-FPT-income` · Run `20261022T030942Z-a339ea46` · 0 nhận định qua kiểm tra, 2 bị chặn.

## 2. FPT — Nguồn công bố chỉ tiêu doanh thu hoặc thu nhập nào cho năm 2024?

Bảng tổng hợp hợp nhất ghi tổng doanh thu năm 2024 là 62.849 tỷ VNĐ, so với 52.618 tỷ VNĐ năm 2023; mức tăng được báo cáo là 19,4%. Các giá trị trong bảng đã làm tròn đến tỷ VNĐ.

**Ngữ cảnh model:** Thiếu/sai chủ đề. Ba đoạn ghim nằm ở chính sách kế toán và bảng tài sản của doanh nghiệp được mua lại, không có chỉ tiêu tổng doanh thu FPT năm 2024.

**Đối chiếu kết quả:** Thiếu ngữ cảnh; từ chối phù hợp. Từ chối trả lời là phù hợp với ba đoạn được cung cấp. Toàn PDF có đáp án, nên lỗi chính ở bước truy xuất/chọn ngữ cảnh.

Nguồn: [trang PDF 11](../../data/cache/evidence/blobs/04/041c5a2ac49f0e8f4a29f2b1fdb82aea00608579ad33c0606adf9ad06dd8da40#page=11).

Case `dev01-FPT-revenue` · Run `20261022T031020Z-2ab30456` · 0 nhận định qua kiểm tra, 3 bị chặn.

## 3. FPT — Nguồn nêu mức tăng trưởng và kỳ so sánh nào?

So với năm 2023, năm 2024 FPT tăng tổng doanh thu 19,4%, lợi nhuận trước thuế 20,3%, lợi nhuận sau thuế 21,0% và lợi nhuận sau thuế thuộc cổ đông công ty mẹ 21,5%. Cần phân biệt mức tăng doanh thu với mức tăng lợi nhuận.

**Ngữ cảnh model:** Hỗ trợ một phần. S1 trang 9 trộn thứ tự chữ trong đồ họa; S3 trang 14 có tăng trưởng doanh thu CNTT nước ngoài 27,4%, nhưng đây là một lĩnh vực, không phải tổng doanh thu tập đoàn.

**Đối chiếu kết quả:** Bản nháp có sai sót đã bị chặn. Mô hình gán 21% cho tăng trưởng doanh thu, trong khi bảng đầy đủ ghi doanh thu tăng 19,4% và lợi nhuận sau thuế tăng 21,0%. Nhận định sai không đi qua bộ kiểm tra.

Nguồn: [trang PDF 11](../../data/cache/evidence/blobs/04/041c5a2ac49f0e8f4a29f2b1fdb82aea00608579ad33c0606adf9ad06dd8da40#page=11).

Case `dev01-FPT-growth` · Run `20261022T031100Z-4920a4f9` · 0 nhận định qua kiểm tra, 3 bị chặn.

## 4. FPT — Nguồn nêu thông tin nào về tài sản và nghĩa vụ nợ?

Tại 31/12/2024, bảng cân đối kế toán hợp nhất FPT ghi tổng tài sản 71.999.995.678.620 VND và nợ phải trả 36.272.455.573.820 VND. Nợ phải trả gồm nợ ngắn hạn 34.836.184.067.740 VND và nợ dài hạn 1.436.271.506.080 VND.

**Ngữ cảnh model:** Hỗ trợ một phần. S2 trang 149 có nợ phải trả và tiêu đề năm/đơn vị. S3 trang 171 là tài sản của doanh nghiệp mua lại, không phải tổng tài sản hợp nhất FPT.

**Đối chiếu kết quả:** Không có đáp án; ngữ cảnh mới hỗ trợ một phần. Có thể trả lời phần nợ từ S2, nhưng không có nhận định được chấp nhận do câu trích dẫn ngắn bỏ tiêu đề năm. Không được dùng bảng mua lại ở S3 làm tổng tài sản tập đoàn.

Nguồn: [trang PDF 148](../../data/cache/evidence/blobs/04/041c5a2ac49f0e8f4a29f2b1fdb82aea00608579ad33c0606adf9ad06dd8da40#page=148), [trang PDF 149](../../data/cache/evidence/blobs/04/041c5a2ac49f0e8f4a29f2b1fdb82aea00608579ad33c0606adf9ad06dd8da40#page=149).

Case `dev01-FPT-assets` · Run `20261022T031124Z-bc8b89b7` · 0 nhận định qua kiểm tra, 3 bị chặn.

## 5. FPT — Nguồn có thông tin gì về tiền và dòng tiền hoạt động?

Lưu chuyển tiền thuần từ hoạt động kinh doanh hợp nhất năm 2024 là 11.703.777.188.868 VND, so với 9.517.095.698.405 VND năm 2023. Đây là dòng tiền kinh doanh sau điều chỉnh vốn lưu động và các khoản chi, khác với lợi nhuận trước thay đổi vốn lưu động 13.626.844.968.489 VND.

**Ngữ cảnh model:** Hỗ trợ một phần. Các đoạn có đầu bảng dòng tiền kinh doanh và một số dòng đầu tư; dòng tổng tiền thuần hoạt động kinh doanh ở cuối trang 153 nằm ngoài đoạn ghim.

**Đối chiếu kết quả:** Có trích dẫn nhưng trả lời chưa đầy đủ/đúng trọng tâm. Nhận định được chấp nhận nói về tiền thu hồi đầu tư góp vốn, phù hợp với đoạn đầu tư nhưng không trả lời dòng tiền hoạt động kinh doanh. Chưa thể coi câu này đã được trả lời đầy đủ.

Nguồn: [trang PDF 153](../../data/cache/evidence/blobs/04/041c5a2ac49f0e8f4a29f2b1fdb82aea00608579ad33c0606adf9ad06dd8da40#page=153).

Case `dev01-FPT-cash` · Run `20261022T031226Z-3215ceee` · 1 nhận định qua kiểm tra, 2 bị chặn.

## 6. FPT — Hoạt động kinh doanh chính và diễn biến phân khúc được mô tả thế nào?

FPT phân hoạt động thành ba khối: Công nghệ (CNTT trong nước và nước ngoài), Viễn thông (viễn thông và nội dung số), cùng Giáo dục, Đầu tư và Khác. Năm 2024, doanh thu ba khối tăng lần lượt 24,4%, 11,4% và 14,3% so với năm trước.

**Ngữ cảnh model:** Hỗ trợ một phần. S3 trang 51 bắt đầu mô tả ba khối nhưng bị cắt trước danh sách đầy đủ; hai đoạn khác chủ yếu là định nghĩa kế toán về bộ phận kinh doanh.

**Đối chiếu kết quả:** Có trích dẫn nhưng trả lời chưa đầy đủ/đúng trọng tâm. Nhận định qua kiểm tra chỉ lặp định nghĩa bộ phận theo kế toán, không nêu ba khối hoạt động hoặc diễn biến năm 2024. Trích dẫn có thật nhưng tính hữu ích cho câu hỏi thấp.

Nguồn: [trang PDF 51](../../data/cache/evidence/blobs/04/041c5a2ac49f0e8f4a29f2b1fdb82aea00608579ad33c0606adf9ad06dd8da40#page=51).

Case `dev01-FPT-operations` · Run `20261022T031316Z-7cb76f1b` · 1 nhận định qua kiểm tra, 2 bị chặn.

## 7. FPT — Nguồn nêu rủi ro hoặc khó khăn cụ thể nào?

Báo cáo nêu rủi ro tỷ giá đối với dịch vụ CNTT ở thị trường nước ngoài; rủi ro nợ xấu và hàng tồn kho tăng cao; cùng yêu cầu tuân thủ pháp luật, lao động nhập cư và khác biệt văn hóa khi mở rộng quốc tế. Các biện pháp gồm phòng ngừa tỷ giá, kiểm soát công nợ/tồn kho và cập nhật quy định tại nước sở tại.

**Ngữ cảnh model:** Đủ để trả lời. S2 và S3 trang 119 nêu trực tiếp rủi ro tỷ giá, tuân thủ và nội dung quản trị. Có đủ bằng chứng để trả lời ít nhất một rủi ro cụ thể.

**Đối chiếu kết quả:** Bỏ sót bằng chứng có thể dùng. Không có nhận định được chấp nhận dù nguồn có nội dung rủi ro rõ. Các trường số trích xuất không được câu trích dẫn hỗ trợ làm bộ kiểm tra chặn nhận định về tỷ giá.

Nguồn: [trang PDF 119](../../data/cache/evidence/blobs/04/041c5a2ac49f0e8f4a29f2b1fdb82aea00608579ad33c0606adf9ad06dd8da40#page=119).

Case `dev01-FPT-risk` · Run `20261022T031353Z-d6755189` · 0 nhận định qua kiểm tra, 2 bị chặn.

## 8. FPT — Nguồn nêu kế hoạch hay mục tiêu gì, và đó thuộc kỳ nào?

Trong kế hoạch năm 2025, FPT đặt doanh thu 75.400 tỷ VNĐ và lợi nhuận trước thuế 13.395 tỷ VNĐ. Ngân sách đầu tư dự kiến 11.000 tỷ VNĐ, gồm Công nghệ 6.000, Viễn thông 2.500, Giáo dục/Đầu tư/Khác 2.500 tỷ VNĐ. Đây là mục tiêu và dự kiến, không phải kết quả thực hiện năm 2024 hay 2025.

**Ngữ cảnh model:** Hỗ trợ một phần. S1 trang 47 có tiêu đề kế hoạch 2025 và ngân sách Công nghệ/Viễn thông; tổng đầu tư, đơn vị và chỉ tiêu doanh thu/lợi nhuận nằm ngoài đoạn cắt.

**Đối chiếu kết quả:** Có trích dẫn nhưng trả lời chưa đầy đủ/đúng trọng tâm. Nhận định được chấp nhận nêu 6.000 và 2.500 nhưng bỏ đơn vị và kỳ ngay trong phát biểu. Nội dung có cơ sở, song cần bổ sung năm 2025 và tỷ VNĐ để sử dụng được.

Nguồn: [trang PDF 47](../../data/cache/evidence/blobs/04/041c5a2ac49f0e8f4a29f2b1fdb82aea00608579ad33c0606adf9ad06dd8da40#page=47).

Case `dev01-FPT-outlook` · Run `20261022T031415Z-00125581` · 1 nhận định qua kiểm tra, 0 bị chặn.

## 9. HPG — Kết quả lợi nhuận năm 2024 được nguồn mô tả như thế nào?

Bảng tổng hợp hợp nhất ghi năm 2024 Hòa Phát có lợi nhuận trước thuế 13.694 tỷ đồng và lợi nhuận sau thuế 12.020 tỷ đồng. Lợi nhuận sau thuế tăng 77% so với năm 2023; biên lợi nhuận sau thuế/doanh thu thuần là 8,7%. Các giá trị tiền đã làm tròn đến tỷ đồng.

**Ngữ cảnh model:** Đủ để trả lời. S1 trang 31 có lợi nhuận sau thuế 12.020 tỷ đồng, tăng 77% và biên lợi nhuận 8,7%. Có thể trả lời câu hỏi lợi nhuận từ chính ngữ cảnh ghim.

**Đối chiếu kết quả:** Có nhận định hữu ích, có cơ sở. Ba nhận định được chấp nhận phù hợp với nguồn: lợi nhuận sau thuế, biên lợi nhuận và EBITDA. Đây là trường hợp trả lời hữu ích; kiểm tra này vẫn do trợ lý thực hiện.

Nguồn: [trang PDF 12](../../data/cache/evidence/blobs/4f/4f203765a2c39a14aa8c78838d3b21db5b03f663b2c4490b801d17427830446d#page=12), [trang PDF 29](../../data/cache/evidence/blobs/4f/4f203765a2c39a14aa8c78838d3b21db5b03f663b2c4490b801d17427830446d#page=29).

Case `dev01-HPG-income` · Run `20261022T031436Z-550b5fa9` · 3 nhận định qua kiểm tra, 0 bị chặn.

## 10. HPG — Nguồn công bố chỉ tiêu doanh thu hoặc thu nhập nào cho năm 2024?

Năm 2024, Hòa Phát ghi doanh thu bán hàng và cung cấp dịch vụ 140.561 tỷ đồng, còn doanh thu thuần là 138.855 tỷ đồng trong bảng tổng hợp hợp nhất. Đây là hai chỉ tiêu khác nhau; không lấy doanh thu của riêng phân khúc thép làm doanh thu toàn tập đoàn.

**Ngữ cảnh model:** Hỗ trợ một phần. S3 trang 30 có doanh thu thuần xuất khẩu 43.340 tỷ đồng và tỷ trọng 31%. Các bảng phân khúc ở S1/S2 bị cắt và tách cột, khó dùng cho tổng doanh thu tập đoàn.

**Đối chiếu kết quả:** Không có đáp án; ngữ cảnh mới hỗ trợ một phần. Không có nhận định qua kiểm tra. Một phần dữ liệu xuất khẩu có thể dùng, nhưng đầu ra còn ghép số bị cắt và gán số phân khúc cho toàn tập đoàn; việc khai báo thiếu bằng chứng khiến mọi nhận định bị chặn.

Nguồn: [trang PDF 12](../../data/cache/evidence/blobs/4f/4f203765a2c39a14aa8c78838d3b21db5b03f663b2c4490b801d17427830446d#page=12).

Case `dev01-HPG-revenue` · Run `20261022T031516Z-a41f8057` · 0 nhận định qua kiểm tra, 3 bị chặn.

## 11. HPG — Nguồn nêu mức tăng trưởng và kỳ so sánh nào?

Báo cáo ghi doanh thu năm 2024 tăng 17% và lợi nhuận tăng 77% so với năm 2023. Riêng doanh thu lĩnh vực thép tăng 16%, lợi nhuận lĩnh vực thép tăng 64% so với cùng kỳ. Cần giữ rõ phạm vi toàn tập đoàn và riêng ngành thép.

**Ngữ cảnh model:** Đủ để trả lời. S1 trang 29 và đoạn lợi nhuận trang 31 nêu rõ tỷ lệ tăng và mốc so sánh 2023.

**Đối chiếu kết quả:** Có nhận định hữu ích, có cơ sở. Hai nhận định được chấp nhận nêu đúng mức tăng doanh thu 17% và lợi nhuận 77% so với 2023. Tuy nhiên, phần thiếu thông tin lại nói chưa có thông tin tăng trưởng, mâu thuẫn với chính các nhận định.

Nguồn: [trang PDF 29](../../data/cache/evidence/blobs/4f/4f203765a2c39a14aa8c78838d3b21db5b03f663b2c4490b801d17427830446d#page=29).

Case `dev01-HPG-growth` · Run `20261022T031612Z-5815bccc` · 2 nhận định qua kiểm tra, 1 bị chặn.

## 12. HPG — Nguồn nêu thông tin nào về tài sản và nghĩa vụ nợ?

Bảng tổng hợp hợp nhất cuối năm 2024 ghi tổng tài sản 224.490 tỷ đồng, nợ phải trả 109.842 tỷ đồng và vốn chủ sở hữu 114.647 tỷ đồng. Các số đã làm tròn theo từng dòng nên phép cộng có thể lệch 1 tỷ đồng.

**Ngữ cảnh model:** Hỗ trợ một phần. S1 trang 101 có tổng tài sản nhưng nhãn và số bị tách trong quá trình trích văn bản. Các đoạn còn lại nêu tỷ số tài chính/vốn chủ, chưa cung cấp đủ bảng tài sản và nợ có tiêu đề.

**Đối chiếu kết quả:** Không có đáp án; ngữ cảnh mới hỗ trợ một phần. Mô hình tìm được giá trị tài sản nhưng ghép câu trích dẫn không có nguyên văn liền nhau và khai báo thiếu bằng chứng, nên không nhận định nào được chấp nhận. Cần truy xuất bảng cùng tiêu đề thay vì ghép hàng theo suy đoán.

Nguồn: [trang PDF 12](../../data/cache/evidence/blobs/4f/4f203765a2c39a14aa8c78838d3b21db5b03f663b2c4490b801d17427830446d#page=12).

Case `dev01-HPG-assets` · Run `20261022T031653Z-b1a824d5` · 0 nhận định qua kiểm tra, 3 bị chặn.

## 13. HPG — Nguồn có thông tin gì về tiền và dòng tiền hoạt động?

Năm 2024, tiền thuần từ hoạt động kinh doanh hợp nhất là 6.608 tỷ đồng. Tiền thuần đầu tư âm 29.788 tỷ đồng, tiền thuần tài chính dương 17.815 tỷ đồng; lưu chuyển tiền thuần trong kỳ âm 5.365 tỷ đồng. Tiền và tương đương tiền cuối kỳ là 6.888 tỷ đồng. Đây là các số làm tròn trong bảng tổng hợp.

**Ngữ cảnh model:** Thiếu/sai chủ đề. Ba đoạn ghim chủ yếu có tiêu đề, nhãn chỉ tiêu và thông tin bộ máy; không chứa giá trị tiền thuần kinh doanh dùng được.

**Đối chiếu kết quả:** Thiếu ngữ cảnh; từ chối phù hợp. Từ chối trả lời phù hợp với ngữ cảnh. Toàn PDF có bảng trả lời được; cần sửa truy xuất vùng bảng, không kết luận rằng tài liệu không có số liệu.

Nguồn: [trang PDF 12](../../data/cache/evidence/blobs/4f/4f203765a2c39a14aa8c78838d3b21db5b03f663b2c4490b801d17427830446d#page=12).

Case `dev01-HPG-cash` · Run `20261022T031738Z-2a50ac10` · 0 nhận định qua kiểm tra, 3 bị chặn.

## 14. HPG — Hoạt động kinh doanh chính và diễn biến phân khúc được mô tả thế nào?

Thép là hoạt động cốt lõi, đóng góp 93% doanh thu và 86% lợi nhuận sau thuế toàn tập đoàn năm 2024. Sản lượng bán HRC, thép xây dựng, thép chất lượng cao và phôi đạt 8,11 triệu tấn, tăng 21%. Nông nghiệp đóng góp 5% doanh thu và 8% lợi nhuận; lợi nhuận nhóm này gấp 4,6 lần năm 2023.

**Ngữ cảnh model:** Hỗ trợ một phần. Ngữ cảnh có hoạt động thức ăn chăn nuôi của công ty thành viên, không bao quát mảng thép và cơ cấu kinh doanh toàn Hòa Phát.

**Đối chiếu kết quả:** Có trích dẫn nhưng trả lời chưa đầy đủ/đúng trọng tâm. Hai nhận định được chấp nhận đúng cho hoạt động thức ăn chăn nuôi, nhưng thiếu chỉ rõ phạm vi công ty thành viên và bỏ mảng thép cốt lõi. Câu trả lời chưa đại diện toàn tập đoàn.

Nguồn: [trang PDF 29](../../data/cache/evidence/blobs/4f/4f203765a2c39a14aa8c78838d3b21db5b03f663b2c4490b801d17427830446d#page=29).

Case `dev01-HPG-operations` · Run `20261022T031834Z-56237c04` · 2 nhận định qua kiểm tra, 1 bị chặn.

## 15. HPG — Nguồn nêu rủi ro hoặc khó khăn cụ thể nào?

Hòa Phát chịu rủi ro tỷ giá và lãi suất. Nhập khẩu chiếm hơn 70% tổng giá vốn năm 2024; than, quặng phụ thuộc nguồn nước ngoài, nên tỷ giá tăng làm tăng chi phí nguyên liệu và tài chính. Các khoản vay/công cụ có lãi suất tạo thêm rủi ro chi phí trong bối cảnh tiền tệ thắt chặt.

**Ngữ cảnh model:** Đủ để trả lời. S1 trang 24 nêu trực tiếp nhập khẩu, biến động tỷ giá, lãi suất và cách quản trị.

**Đối chiếu kết quả:** Có nhận định hữu ích, có cơ sở. Nhận định được chấp nhận nêu đúng việc quản trị rủi ro tỷ giá và lãi suất, nhưng chưa giải thích cơ chế tác động. Phần thiếu thông tin lại cho rằng chưa rõ rủi ro cụ thể, mâu thuẫn với nguồn và nhận định.

Nguồn: [trang PDF 24](../../data/cache/evidence/blobs/4f/4f203765a2c39a14aa8c78838d3b21db5b03f663b2c4490b801d17427830446d#page=24).

Case `dev01-HPG-risk` · Run `20261022T031918Z-0f86deb9` · 1 nhận định qua kiểm tra, 2 bị chặn.

## 16. HPG — Nguồn nêu kế hoạch hay mục tiêu gì, và đó thuộc kỳ nào?

Ban Tổng Giám đốc trình Đại hội đồng cổ đông kế hoạch hợp nhất năm 2025: doanh thu 170.000 tỷ đồng và lợi nhuận sau thuế 15.000 tỷ đồng. Định hướng gồm vận hành ổn định phân kỳ 1 Dung Quất 2, hoàn thành phân kỳ 2 vào quý 4/2025 và phát triển thép chất lượng cao. Đây là kế hoạch được trình, không phải kết quả đã đạt.

**Ngữ cảnh model:** Đủ để trả lời. S1 trang 41 có tiêu đề kế hoạch năm 2025 và hai mục tiêu doanh thu/lợi nhuận. S3 nêu định hướng tăng trưởng giai đoạn 2025–2030.

**Đối chiếu kết quả:** Bỏ sót bằng chứng có thể dùng. Mô hình khai báo không xác định được kỳ dù tiêu đề kế hoạch năm 2025 nằm trong ngữ cảnh. Không có nhận định được chấp nhận; đây là bỏ sót bằng chứng có sẵn.

Nguồn: [trang PDF 41](../../data/cache/evidence/blobs/4f/4f203765a2c39a14aa8c78838d3b21db5b03f663b2c4490b801d17427830446d#page=41).

Case `dev01-HPG-outlook` · Run `20261022T031948Z-2fdda64c` · 0 nhận định qua kiểm tra, 3 bị chặn.

## 17. VCB — Kết quả lợi nhuận năm 2024 được nguồn mô tả như thế nào?

Báo cáo kết quả hoạt động hợp nhất năm 2024 ghi lợi nhuận trước thuế 42.236.135 triệu VND và lợi nhuận sau thuế 33.853.117 triệu VND. Không dùng lợi nhuận của VCBL, VCBS hay công ty con khác thay cho kết quả hợp nhất Vietcombank.

**Ngữ cảnh model:** Thiếu/sai chủ đề. Cả ba đoạn trang 18 đều nói về công ty thành viên như VCBL, VCBS, VCBR và VCB Lào; không có lợi nhuận hợp nhất VCB.

**Đối chiếu kết quả:** Thiếu ngữ cảnh; từ chối phù hợp. Không xuất bản nhận định lợi nhuận hợp nhất từ các số công ty con là phù hợp. Truy xuất đã chọn sai cấp doanh nghiệp dù đúng mã VCB trong metadata.

Nguồn: [trang PDF 67](../../data/cache/evidence/blobs/9d/9deccc3518e23302d00353b4d371a9dd251b67b12f9fe58a4da4ad3c727e99f8#page=67).

Case `dev01-VCB-income` · Run `20261022T032014Z-4f9403cf` · 0 nhận định qua kiểm tra, 3 bị chặn.

## 18. VCB — Nguồn công bố chỉ tiêu doanh thu hoặc thu nhập nào cho năm 2024?

Với ngân hàng cần gọi đúng từng chỉ tiêu: năm 2024 thu nhập lãi và các khoản tương tự là 93.654.841 triệu VND; chi phí lãi 38.249.106 triệu VND; thu nhập lãi thuần 55.405.735 triệu VND. Tổng thu nhập hoạt động hợp nhất là 68.578.496 triệu VND. Thu nhập lãi gộp và thu nhập lãi thuần không thể dùng thay nhau.

**Ngữ cảnh model:** Đủ để trả lời. S1 trang 67 chứa cột năm 2024, đơn vị triệu VND và các dòng thu nhập lãi/chi phí lãi/thu nhập lãi thuần.

**Đối chiếu kết quả:** Bản nháp có sai sót đã bị chặn. Mô hình gọi 55.405.735 là thu nhập lãi và khoản tương tự, trong khi đó là thu nhập lãi thuần. Một phát biểu khác gắn 55.406 với triệu VND từ bảng tóm tắt làm sai đơn vị. Các nhận định này đã bị chặn.

Nguồn: [trang PDF 67](../../data/cache/evidence/blobs/9d/9deccc3518e23302d00353b4d371a9dd251b67b12f9fe58a4da4ad3c727e99f8#page=67).

Case `dev01-VCB-revenue` · Run `20261022T032044Z-10ecaef1` · 0 nhận định qua kiểm tra, 3 bị chặn.

## 19. VCB — Nguồn nêu mức tăng trưởng và kỳ so sánh nào?

Phần đánh giá hoạt động 2024 nêu tổng tài sản khoảng 2,1 triệu tỷ đồng, tăng xấp xỉ 13,4% so với 2023; huy động vốn khoảng 1,5 triệu tỷ đồng, tăng xấp xỉ 8%; tín dụng khoảng 1,5 triệu tỷ đồng, tăng xấp xỉ 14%. Lợi nhuận trước thuế 42.236 tỷ đồng tăng khoảng 2,2% so với năm trước. Đây là số làm tròn trong phần thuyết minh hoạt động.

**Ngữ cảnh model:** Thiếu/sai chủ đề. Các đoạn ghim nói về bổ nhiệm nhân sự và giao dịch/quan hệ với công ty liên quan, không có tăng trưởng tài chính năm 2024.

**Đối chiếu kết quả:** Thiếu ngữ cảnh; từ chối phù hợp. Từ chối trả lời phù hợp với ngữ cảnh bị truy xuất sai chủ đề. Cần chọn đoạn đánh giá kết quả 2024, không bổ sung tỷ lệ bằng suy đoán.

Nguồn: [trang PDF 23](../../data/cache/evidence/blobs/9d/9deccc3518e23302d00353b4d371a9dd251b67b12f9fe58a4da4ad3c727e99f8#page=23).

Case `dev01-VCB-growth` · Run `20261022T032115Z-230d525e` · 0 nhận định qua kiểm tra, 3 bị chặn.

## 20. VCB — Nguồn nêu thông tin nào về tài sản và nghĩa vụ nợ?

Tại 31/12/2024, báo cáo tình hình tài chính hợp nhất ghi tổng tài sản có 2.085.873.522 triệu VND; tổng nợ phải trả 1.889.664.354 triệu VND; vốn chủ sở hữu 196.209.168 triệu VND. Bảng phân tích rủi ro ở trang 100/102 trình bày nhiều khoản tài sản gộp trước dự phòng, nên không dùng tổng 2.118.424.116 trong bảng đó thay cho tổng tài sản có trên báo cáo tình hình tài chính.

**Ngữ cảnh model:** Hỗ trợ một phần. S1 trang 102 và S3 trang 100 có tổng nợ phải trả 1.889.664.354 cùng mốc 31/12/2024; tiêu đề đơn vị ở đầu bảng ngoài đoạn cắt. Các bảng này phục vụ phân tích thanh khoản/lãi suất, không phải bảng cân đối theo giá trị ghi sổ.

**Đối chiếu kết quả:** Không có đáp án; ngữ cảnh mới hỗ trợ một phần. Không có nhận định được chấp nhận. Ngữ cảnh có thể hỗ trợ phần nợ khi bổ sung tiêu đề đơn vị, nhưng cần phân biệt bảng rủi ro với báo cáo tình hình tài chính để tránh nhầm tổng tài sản.

Nguồn: [trang PDF 66](../../data/cache/evidence/blobs/9d/9deccc3518e23302d00353b4d371a9dd251b67b12f9fe58a4da4ad3c727e99f8#page=66), [trang PDF 100](../../data/cache/evidence/blobs/9d/9deccc3518e23302d00353b4d371a9dd251b67b12f9fe58a4da4ad3c727e99f8#page=100).

Case `dev01-VCB-assets` · Run `20261022T032151Z-9a8e05dc` · 0 nhận định qua kiểm tra, 3 bị chặn.

## 21. VCB — Nguồn có thông tin gì về tiền và dòng tiền hoạt động?

Năm 2024, lưu chuyển tiền thuần từ hoạt động kinh doanh hợp nhất là 59.122.831 triệu VND, so với âm 38.541.530 triệu VND năm 2023. Tiền và các khoản tương đương tiền cuối năm 2024 là 430.614.185 triệu VND. Không nhầm dòng tiền lãi thực nhận với thu nhập lãi dồn tích trong báo cáo kết quả kinh doanh.

**Ngữ cảnh model:** Đủ để trả lời. S3 trang 68 có dòng tiền thuần kinh doanh 59.122.831 và năm/đơn vị. Giá trị tiền cuối năm nằm ngoài đoạn ghim, nhưng đủ để trả lời phần dòng tiền kinh doanh.

**Đối chiếu kết quả:** Lỗi sinh đầu ra. Lượt sinh không hoàn tất (incomplete_generation), không tạo được đầu ra hợp lệ. Đây là lỗi kỹ thuật, không phải quyết định từ chối vì thiếu bằng chứng.

Nguồn: [trang PDF 68](../../data/cache/evidence/blobs/9d/9deccc3518e23302d00353b4d371a9dd251b67b12f9fe58a4da4ad3c727e99f8#page=68).

Case `dev01-VCB-cash` · Run `20261022T032240Z-4bc17eac` · 0 nhận định qua kiểm tra, 0 bị chặn.

## 22. VCB — Hoạt động kinh doanh chính và diễn biến phân khúc được mô tả thế nào?

Hoạt động 2024 tập trung tăng trưởng tín dụng an toàn, điều chỉnh giảm lãi suất cho vay để hỗ trợ doanh nghiệp, cung cấp giải pháp ngân hàng bán buôn/bán lẻ và mở rộng dịch vụ số. Vietcombank triển khai xác thực sinh trắc học và ra mắt New Digibank với phiên bản cho các nhóm khách hàng. Nội dung này mô tả hoạt động đã triển khai năm 2024.

**Ngữ cảnh model:** Hỗ trợ một phần. S1 trang 26 mô tả chiến lược; S2/S3 trang 22 là kế hoạch 2025, không phải đánh giá kết quả hoạt động 2024.

**Đối chiếu kết quả:** Có trích dẫn nhưng dễ hiểu sai kỳ hoặc điều kiện. Hai nhận định qua kiểm tra chủ yếu là kế hoạch tín dụng và số hóa 2025. Phát biểu tín dụng 16,28% bỏ điều kiện tối đa và không nêu kỳ 2025, dễ khiến người đọc hiểu là kết quả 2024. Kiểm tra nguyên văn chưa ngăn được nhầm kỳ/trạng thái kế hoạch.

Nguồn: [trang PDF 21](../../data/cache/evidence/blobs/9d/9deccc3518e23302d00353b4d371a9dd251b67b12f9fe58a4da4ad3c727e99f8#page=21), [trang PDF 22](../../data/cache/evidence/blobs/9d/9deccc3518e23302d00353b4d371a9dd251b67b12f9fe58a4da4ad3c727e99f8#page=22).

Case `dev01-VCB-operations` · Run `20261022T032411Z-ac5ab8c9` · 2 nhận định qua kiểm tra, 1 bị chặn.

## 23. VCB — Nguồn nêu rủi ro hoặc khó khăn cụ thể nào?

Báo cáo đánh giá bối cảnh 2024 có khó khăn từ lạm phát, xung đột địa chính trị và sự phục hồi chậm của các nền kinh tế lớn. Các yếu tố này tạo bất định cho môi trường hoạt động; đây là mô tả khó khăn vĩ mô trong nguồn, không phải dự báo xác suất tổn thất của ngân hàng.

**Ngữ cảnh model:** Đủ để trả lời. S2 trang 23 nói trực tiếp về lạm phát, địa chính trị và kinh tế thế giới; đủ trả lời khó khăn cụ thể.

**Đối chiếu kết quả:** Bỏ sót bằng chứng có thể dùng. Không có nhận định được chấp nhận vì mô hình khai báo thiếu bằng chứng và có số không được hỗ trợ. Phần khó khăn vĩ mô thực tế đã có trong ngữ cảnh.

Nguồn: [trang PDF 23](../../data/cache/evidence/blobs/9d/9deccc3518e23302d00353b4d371a9dd251b67b12f9fe58a4da4ad3c727e99f8#page=23).

Case `dev01-VCB-risk` · Run `20261022T032454Z-636036b0` · 0 nhận định qua kiểm tra, 1 bị chặn.

## 24. VCB — Nguồn nêu kế hoạch hay mục tiêu gì, và đó thuộc kỳ nào?

Kế hoạch 2025 nêu tổng tài sản tăng 10%, huy động vốn thị trường 1 tăng 8%, tín dụng tăng tối đa 16,28% theo giao của NHNN, nợ xấu dưới 1,5% và lợi nhuận trước thuế tăng 3,5%. Các chỉ tiêu còn phụ thuộc phê duyệt/điều chỉnh kế hoạch theo chú thích của báo cáo. Đây là mục tiêu 2025, không phải số thực hiện 2024.

**Ngữ cảnh model:** Hỗ trợ một phần. S1 trang 22 có tiêu đề kế hoạch 2025 và mục tiêu tài sản tăng 10%; các chỉ tiêu khác nằm ngoài đoạn cắt. S2 nói mục tiêu GDP của nền kinh tế, không phải doanh thu hay lợi nhuận VCB.

**Đối chiếu kết quả:** Không có đáp án; ngữ cảnh mới hỗ trợ một phần. Mô hình bỏ qua tiêu đề kỳ 2025, khai báo thiếu thông tin và đưa mục tiêu GDP vĩ mô vào bản nháp. Không có nhận định được chấp nhận; có thể trả lời ít nhất phần mục tiêu tài sản từ S1.

Nguồn: [trang PDF 22](../../data/cache/evidence/blobs/9d/9deccc3518e23302d00353b4d371a9dd251b67b12f9fe58a4da4ad3c727e99f8#page=22).

Case `dev01-VCB-outlook` · Run `20261022T032517Z-930f9547` · 0 nhận định qua kiểm tra, 3 bị chặn.
