# Bằng chứng theo ô PDF v0.5 — development

Ngày: 25/10/2026. Profile thử nghiệm mới hỗ trợ tiêu đề cột năm không có
STT/Chỉ tiêu, năm căn giữa với số căn phải, bảng song song và một tập con nhãn
xuống dòng. Không thay extractor v0.4 hoặc nhãn/case gốc.

- `initial.json`: study trên bảy mã đã định trước, dừng tại BID sau lỗi quyền
  kết nối loopback của sandbox; chưa có lần generation nào trong study này.
- `continuation.json`: giữ lỗi trước đó, chạy tiếp BID/MWG/VNM với quyền truy
  cập loopback; có đúng hai generation mới cho BID và VNM.
- `validation.json`: chi tiết tám run study, nguồn/trang và bảng mô tả run mới
  nhất từng mã; không phải accuracy. Ghi riêng run đọc bảng qua frontend.
- `integrity.json`: hash metadata và cấu hình v0.5.

FPT/HPG/VCB lần lượt trích 55/78/70 ô, ACB 18 ô, BID 78 ô, MWG 0 ô, VNM 50 ô.
Đây là ô từ nhiều năm trên trang được chọn, chưa phải từng chỉ tiêu duy nhất
đã chuẩn hóa hoặc được xác nhận. ACB chỉ có một ứng viên sai chủ đề lợi nhuận;
MWG chưa có context. VNM bỏ bảng tỷ số không có đơn vị tiền tệ, nhưng lựa chọn
của model còn lặp nhãn ở hai vùng bảng. Giữ các kết quả này để phát triển tiếp.

363 kiểm thử đạt; 18 run của study v0.4/v0.5 replay đạt, gồm cả lượt lỗi trước
generation. Kiểm tra byte/hash thành công không có nghĩa tác vụ sinh thành công
hoặc đúng ngữ nghĩa. `human_reviewed_facts=0`, chưa có semantic accuracy.

Raw PDF và các run ở `outputs/table-evidence/` vẫn tải riêng. Các metadata này
không đủ để replay nếu thiếu raw PDF, bảng, context và request/response. Chưa
upload artifact mới lên Drive/GitHub trong mốc này.

Xem [hướng dẫn giao diện và giới hạn](../../../docs/research/20-table-source-viewer.md).
