# Development batch evaluation v0.1

Ngày 22/10/2026. Đây là hồ sơ chạy local và kiểm thử phần mềm, không là dataset
mới, human gold, held-out test hoặc kết quả dự báo/backtest.

- Nguồn: đúng bộ case v0.2 đã công bố, 24 câu hỏi của FPT/HPG/VCB; mỗi case có
  tối đa ba đoạn đã pin. Không thêm hoặc chọn lại case theo kết quả model.
- Câu hỏi model: `case.question`. `case.query` dùng cho bước chuẩn bị nguồn.
- Model: qwen3:4b local, một call/case, không retry, context 4096/output 1024.
  Digest và raw traces ở hồ sơ validation; không suy training cutoff từ tag.
- Chế độ: đọc tài liệu hiện tại, không có chứng minh availability lịch sử.
- Annotation: vẫn 24 pending tại thời điểm kiểm tra. Không tạo người chấm hoặc
  đáp án giả. Các tỷ lệ đối chiếu không có mẫu số đều là `null`.
- Thống kê quote/số/schema và thời gian chỉ là kiểm tra cơ học/phát triển.
  Trích dẫn qua kiểm tra không chứng minh diễn giải đúng ngữ nghĩa.
- Public: metadata run/hash, trạng thái và tổng hợp kỹ thuật. PDF, đoạn nguồn,
  request/response, báo cáo đầy đủ và annotation ở thư mục local được Git ignore.
- Các checksum/source profile cũ của corpus v0.5 và case v0.1/v0.2 được giữ nguyên;
  không sửa hồ sơ cũ để khớp runtime mới. Profile evaluator hiện tại được ghi riêng.

Xem [hướng dẫn và định nghĩa mẫu số](../../../docs/research/16-development-batch-evaluation.md)
và [validation](validation.json). Bộ này không đánh giá full hierarchy/graph,
peer analysis, semantic verifier, memory isolation hoặc hiệu quả giao dịch.
