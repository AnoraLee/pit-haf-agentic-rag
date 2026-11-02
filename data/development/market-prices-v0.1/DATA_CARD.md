# Market price snapshots v0.1

Ngày 02/11/2026. Thu giá thị trường để kiểm chất lượng đầu vào, không
phải kết quả đầu tư, nhãn độc lập hoặc dataset PiT strict.

- Phạm vi chọn trước: FPT/HPG/VCB và comparator VNINDEX, 2021–2024;
  chưa là universe lịch sử VN30 và chưa loại survivorship bias.
- Bốn phản hồi KBS, 998 hàng mỗi phản hồi. Ba cổ phiếu chuẩn hóa được
  2.994 bar VND. VNINDEX raw có ba hàng vi phạm quan hệ OHLC, chặn toàn
  bộ luồng chuẩn hóa chỉ số, giữ nguyên raw, chưa sửa/loại riêng ngày lỗi.
- JSON số dùng Decimal, raw equity VND tách index points; nguồn mapping
  từ adapter đã cài, chưa được xác nhận độc lập với sở.
- Mỗi cổ phiếu có số bar theo năm 250/249/249/250; không weekend/zero
  volume trong phản hồi này. Không coi số hàng là bằng chứng lịch đầy đủ.
- Adjustment recipe, lịch sở, corporate actions, availability/revision,
  execution rules/settlement còn thiếu. `available_at=null`, adjustment
  unknown và eligible_for_execution false; không tính lợi suất.
- 37 test mới, 104 test liên quan đạt; replay snapshot đạt đối chiếu.
  87 hash artifact cũ không đổi, không ghi review DB hoặc gọi LLM.
- Một probe giá FPT và robots riêng trước capture; robots HTTP 400.
  Capture dùng bốn GET giá, không retry. Bốn lượt archive tài liệu:
  Vnstock thành công, ba VSD/HNX lỗi kiểm SSL, được giữ lại.
- Quyền phân phối raw chưa được xác minh. Raw JSON/CSV/HTML và artifact
  local ngoài Git; repository chỉ có cấu hình, metadata và thẻ dữ liệu.

`manifest.json` pin snapshot/study/source-inspection và hash; `validation.json`
ghi phạm vi phần mềm/chất lượng; `integrity.json` bảo vệ metadata mốc này.
Xem [cách chạy và giới hạn](../../../docs/research/34-market-price-snapshots.md).
