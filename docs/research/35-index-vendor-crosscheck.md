# 35 — Đối soát VNINDEX và so chuẩn chỉ dùng giá đóng cửa

Ngày 02/11/2026. Protocol `market_index_crosscheck_v0.1` so trường giá
VNINDEX giữa snapshot KBS đã ghim và nguồn biểu đồ Vietcap. Tách điều
kiện dùng close để so chuẩn khỏi điều kiện dùng OHLCV để thực thi.
Không sửa snapshot mốc 34 hoặc nâng nó thành dữ liệu giao dịch hợp lệ.

## Thu thập và kết quả

Một probe Vietcap được giữ riêng trước khi phát triển protocol. Sau
khi viết code/test, một query chính thức đọc cùng cửa sổ cố định
2021–2024, không retry. Đây là lựa chọn phát triển sau probe, chưa là
protocol test giữ kín hoặc thực nghiệm đăng ký trước. Không chọn ngày
theo lợi suất hoặc bỏ các ngày sai lệch.

KBS có 998 hàng. Vietcap trả 1.100 hàng, trong đó 102 hàng ngoài cửa sổ
được ghi lại; 998 hàng trong cửa sổ trùng toàn bộ tập ngày KBS.

| Trường | Phiên so sánh | Khớp số thập phân | Khác biệt |
|---|---:|---:|---:|
| Open | 998 | 424 | 574 |
| High | 998 | 960 | 38 |
| Low | 998 | 912 | 86 |
| Close | 998 | 998 | 0 |
| Volume thô | 998 | 0 | 998 |

Volume mới là đối chiếu giá trị trường gốc; chưa xác nhận hai feed có
cùng định nghĩa/phạm vi khối lượng, không coi chênh lệch là tỷ lệ lỗi.
Khác endpoint/vendor không chứng minh độc lập upstream: hai bên có
thể dùng cùng dữ liệu đầu nguồn. Đồng thuận không thay gold độc lập.

Giữ ba hàng KBS vi phạm quan hệ OHLC ngày 17/02/2021, 10/12/2021 và
15/05/2023. Vietcap có một hàng vi phạm ngày 23/08/2021. Chưa xác định
nguyên nhân/giá đúng; không lấy vendor nào làm chuẩn tuyệt đối, không
vá high/low/open hoặc trộn giá các feed thành bộ OHLC mới. Mỗi trường
khác biệt giữ ngày, giá trị hai bên và chênh lệch; mỗi lỗi OHLC giữ
vị trí hàng nguồn. Snapshot gốc vẫn bị chặn theo protocol mốc 34.

## Hợp đồng so chuẩn close-only

Chuỗi so chuẩn phát triển được tạo khi:

- Cả hai response đúng VNINDEX/index/đơn vị điểm, số hữu hạn dương,
  volume nguyên không âm, schema và thời gian nguồn hợp lệ.
- Tập ngày trong cửa sổ khớp hoàn toàn, không trùng ngày và có ít nhất
  hai phiên. Không chỉ lấy giao hai tập ngày để che mất coverage.
- Tất cả close khớp chính xác bằng Decimal, không có ngưỡng nới sai lệch.

Quan hệ OHLC vẫn được kiểm và báo đầy đủ nhưng không được dùng thay
điều kiện chỉ tiêu close. Đây là hợp đồng riêng có phạm vi hẹp, không
bỏ qua lỗi OHLC để đưa dữ liệu vào execution. `close_comparator_ready`
có thể true trong khi `eligible_for_execution` vẫn false.

So chuẩn Q2 phát triển gồm close theo phiên, chỉ số gốc 100 tại close
đầu quan sát, thay đổi close-to-close, drawdown và thay đổi toàn cửa sổ.
Giá trị đầu tiên của daily return là null; không bịa thêm phiên hoặc
gán return đầu bằng 0. Dùng Decimal context 50 chữ số cố định. Phí và
Macro-F1 là N/A, không phát sinh lệnh. Chưa có Sharpe/annualization hoặc
kết quả portfolio của các agent.

Mốc bắt đầu/kết thúc là close đầu/cuối **quan sát trong nguồn**, chưa
phải nhãn open-entry → close phiên thứ năm trong task protocol. Trước
khi so với chiến lược phải căn cùng lịch/cửa sổ/reference point và ghi
khác biệt price-return/total-return. Output hiện là mô tả chỉ số đã tải,
không chứng minh hiệu quả chiến lược, tính khả dụng tại thời điểm cũ,
độ phủ lịch sở hoặc tính đúng toàn bộ dữ liệu lịch sử.

## Nguồn và tái lập

Endpoint chỉ đọc chart công khai của Vietcap dùng POST với `ONE_DAY`,
VNINDEX, `countBack=1100` và `to` tính tường minh từ ngày kết thúc +1
tại UTC+7. Không dùng timezone máy, không import Vnstock, không gọi
account/order API, không đăng nhập, API key, đổi định danh hoặc retry.
Request shape được đối chiếu với mã `vnstock 4.0.7` đã cài; nguồn này
cũng có trong [danh sách provider hiện tại](https://www.vnstocks.com/docs/vnstock/tham-khao/data-sources).
Danh sách hiện tại không xác nhận riêng tính đúng của feed đã tải.

Vietcap trả các mảng OHLCV và epoch-seconds dạng chuỗi; chặn mảng lệch
độ dài, symbol khác/nhiều series, ngày trùng, NaN/bool, precision không
hỗ trợ hoặc đoán timestamp milliseconds. Quy đổi epoch sang nhãn ngày
UTC+7 và giữ epoch gốc; KBS giữ nhãn thời gian nguồn. Cả hai
`available_at` đều null, không suy từ 07:00 hoặc thời điểm tải.

```powershell
.\run.ps1 index-crosscheck --capture --kbs-run 20261102T145138Z-21243d88
.\run.ps1 index-crosscheck --replay outputs/index-crosschecks/20261102T152723Z-d6143601
```

Capture nhận `--config` tùy chọn, cần snapshot KBS đúng cửa sổ và qua
kiểm toàn vẹn trước khi query. Mỗi run pin seal/hash response KBS,
giữ nguyên request/config/raw Vietcap, HTTP metadata, observations hai
bên, comparison JSON, `field_mismatches.csv`, `close_comparator.csv`,
bản chép code và seal. Không thực thi bản chép nguồn khi replay.

Replay hoàn toàn offline, kiểm lại snapshot KBS, source binding,
request, toàn bộ hash rồi tái tính JSON/CSV. Source bị thay, kể cả
reseal, không âm thầm giữ kết quả cũ. Không nhận override source/config.
Thất bại tải hoặc parse được lưu; comparator null, CSV còn header.
Exit 0 nghĩa là đạt đồng thuận close-only; không đồng nghĩa OHLCV,
calendar hoặc dữ liệu thực thi đạt. Exit 2 khi không tạo được comparator.

Run thật: `outputs/index-crosschecks/20261102T152723Z-d6143601/`.
Study: `outputs/index-crosscheck-development/20261102T152720Z-5a213df8/`.
Biểu đồ PNG/SVG từ artifact này ở
`outputs/index-crosscheck-figures/20261102T152723Z-d6143601/`.
Raw/CSV/figure ở ngoài Git; clone có code/config/metadata để tạo run
mới hoặc replay khi đã khôi phục các dependency tương ứng.

42 test mới kiểm phép tính tay, đồng thuận theo trường, giữ lỗi OHLC,
khác ngày/close dù rất nhỏ, context Decimal, schema/epoch/mảng, POST
giới hạn/redirect/partial response, dependency, reseal, CSV và CLI.
Nhóm đối soát chỉ số + snapshot có 79 test đạt. Lượt chính thức replay
khớp và 95 hash bảo vệ trước đó giữ nguyên; 0 lượt LLM/review DB thật.
Toàn bộ 724 test và Ruff đạt, giữ hai cảnh báo phụ thuộc test cũ.
Frontend không đổi nên không chạy lại build/QA giao diện. PNG/SVG đã
được tạo từ snapshot và xem kiểm tra bố cục/chú thích.
Xem [manifest](../../data/development/index-crosscheck-v0.1/manifest.json)
và [validation](../../data/development/index-crosscheck-v0.1/validation.json).

Tiếp theo vẫn cần lịch HOSE và thanh toán theo thời điểm trong phiên,
corporate actions/giá cổ phiếu, lịch sử universe và lineage cutoff.
Q0/Q1 còn ở kịch bản giả lập, Q2 mới là comparator phát triển; Q3/Q4 và
ma trận nghiên cứu đầy đủ chưa chạy.
