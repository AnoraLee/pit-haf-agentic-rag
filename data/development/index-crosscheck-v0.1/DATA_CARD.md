# VNINDEX vendor crosscheck v0.1

Ngày 02/11/2026. Đối soát hai vendor và so chuẩn price-close phục vụ phát
triển, không phải gold độc lập hoặc kết quả backtest đầu tư.

- KBS: snapshot mốc 34, 998 hàng 2021–2024. Vietcap: 1.100 hàng raw,
  998 hàng trong cửa sổ, 102 hàng ngoài cửa sổ được giữ thống kê.
- Tập 998 ngày trùng; close khớp Decimal ở cả 998 phiên. Open khác 574,
  high khác 38, low khác 86, volume thô khác 998. Chưa align định nghĩa
  volume; không coi đây là tỷ lệ sai số ngữ nghĩa.
- Giữ ba hàng KBS và một hàng Vietcap vi phạm quan hệ OHLC; không sửa,
  vá, trộn feed hoặc loại riêng ngày. Chuẩn hóa mốc 34 không thay đổi.
- Hợp đồng close-only yêu cầu đủ tập ngày và toàn bộ close khớp; không
  âm thầm dùng giao ngày, nới tolerance hoặc chọn vendor theo lợi suất.
- Tạo curve gốc 100, biến động close-to-close và drawdown của chỉ số
  quan sát. Đây chưa là PnL giao dịch, nhãn horizon hay cohort PiT.
  Phí/Macro-F1 N/A; 0 lệnh. Eligible_for_execution/historical validation
  và independent_gold vẫn false; nguồn upstream có thể liên quan.
- Một query probe trước phát triển và một query chart chính thức,
  không retry/authentication/account/order API. Request/code/source
  hash được pin; replay offline kiểm KBS dependency và tái tính JSON/CSV.
- 42 test mới, 79 test nhóm liên quan đạt; 95 hash bảo vệ không đổi,
  không ghi review DB thật hoặc gọi LLM. Chưa xác minh quyền phân phối
  raw; response/CSV/figure ngoài Git, metadata nhỏ ở repository.

`manifest.json` pin run/study/figure và thống kê; `validation.json` ghi
kiểm chứng; `integrity.json` kiểm metadata. Bảng/ảnh từ cùng các snapshot
phát triển, chưa là đánh giá ngoài mẫu hoặc nhãn người duyệt độc lập.
Xem [quy tắc và lệnh chạy](../../../docs/research/35-index-vendor-crosscheck.md).
