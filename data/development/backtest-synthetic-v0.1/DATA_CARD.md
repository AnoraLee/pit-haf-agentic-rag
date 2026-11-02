# Synthetic execution v0.1

Ngày 02/11/2026. Kiểm tra kỹ thuật bằng dữ liệu tự tạo, không phải dataset
thị trường, kết quả backtest lịch sử hoặc benchmark dự báo tài chính.

- Sáu phiên tường minh, hai mã giả `SYN_A`/`SYN_B`, 12 bar tự tạo.
- Ba arm chọn trước: manual rotation, Q0 Buy & Hold, Q1 Equal Weight
  mỗi hai phiên. Cùng scenario gốc và config thực thi; không chọn run tốt.
- Engine có lệnh trễ phiên, phí/slippage, giới hạn tiền/lô/volume, FIFO,
  cổ phiếu/tiền bán chờ thanh toán, NAV và sổ lệnh/giao dịch/tiền/vị thế.
- 44 kiểm thử mới có ca tính tay, kiểm thời gian, settlement, tính tái
  lập và chống sai lệch artifact bằng tái tính. Ba run replay đạt.
- 83 hash artifact cũ giữ nguyên; không ghi nhãn/review DB thật, không
  gọi LLM hoặc tải dữ liệu giá trong bước này.
- Calendar/lot/cost/settlement là tham số giả lập, chưa xác nhận quy tắc
  sàn. Không có corporate actions, agent exit policy, Q2/Q3/Q4 hoặc kết
  quả VN30. Không phải nhãn độc lập hoặc cohort PiT strict.

Raw input, config, nguồn, JSON/CSV, manifest và seal nằm trong các thư
mục được ghim bởi `manifest.json`, ngoài Git. `validation.json` ghi các
kiểm tra phần mềm; `integrity.json` kiểm các metadata của mốc này.

Xem [quy tắc và lệnh chạy](../../../docs/research/33-synthetic-execution-engine.md).
