# Truy xuất mục báo cáo tài chính v0.3 — development

Ngày: 23/10/2026. Đây là chẩn đoán phát triển sau khi đã xem lỗi của bộ 24 câu,
chưa phải đánh giá trên test độc lập. Profile mới vẫn là tùy chọn thử nghiệm;
`lexical_v0.2` là mặc định.

- `summary.json`: bản sao nguyên byte của chẩn đoán 24 câu, 72 đoạn nguồn.
- `smoke.json`: ba lượt Qwen3:4b thật, chọn trước một câu lợi nhuận mỗi mã.
- `validation.json`: đối chiếu ba lượt với batch gốc, lý do chặn và kiểm tra.
- `integrity.json`: SHA-256 các file metadata trên và artifact nguồn local.

Cùng ngân sách 3 đoạn × 700 ký tự, số chuỗi mốc của bản đối chiếu trợ lý có mặt
trong ngữ cảnh tăng từ 56 lên 103 trên 124 chuỗi: 20 câu tăng, 4 câu giữ nguyên.
Chuỗi có mặt không chứng minh đúng hàng/cột, năm, đơn vị hoặc ý nghĩa. Các chuỗi
do trợ lý soạn, chưa phải gold độc lập; runtime truy xuất không đọc đáp án này.

**Cả ba lượt Qwen mới đều từ chối sau kiểm tra**, không có nhận định được chấp
nhận, 9 nhận định bị chặn. Trong ba câu tương ứng của batch cũ, HPG có 3 nhận
định qua kiểm tra, FPT và VCB không có. Chưa chứng minh cải thiện đầu ra model;
không công bố semantic accuracy. Một lượt mỗi câu cũng chưa đủ đánh giá độ ổn
định sinh đầu ra.

Request/response, văn bản nguồn, trace và mã nguồn lúc chạy được giữ trong
`outputs/retrieval-development/20261023T133509Z-75d1ccc1/` và các thư mục
`outputs/company-reports/<run_id>/`; dữ liệu này tải riêng nếu được cung cấp
trên Drive. Metadata Git không thay thế artifact để replay.

Bộ case v0.2, batch gốc, nhãn thủ công và mặc định ứng dụng được giữ nguyên.
Chưa xác nhận PiT strict lịch sử, dự báo hay backtest. Chi tiết tại
[hồ sơ thử nghiệm](../../../docs/research/18-financial-section-retrieval.md).
