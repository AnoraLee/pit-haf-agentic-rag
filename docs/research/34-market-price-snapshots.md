# 34 — Snapshot giá 2021–2024 và kiểm tra đầu vào

Ngày 02/11/2026. Protocol `market_price_snapshot_v0.1` thu phản hồi giá
công khai, lưu byte gốc và tái tính báo cáo chất lượng. Mốc này chuẩn bị
input cho định lượng; chưa chuyển giá vào engine hoặc tính lợi suất.

## Kết quả thu thập

Chọn trước FPT/HPG/VCB theo bộ phát triển hiện có, cùng VNINDEX làm đối
chứng chỉ số; cửa sổ 01/01/2021–31/12/2024. Không chọn mã/ngày theo lợi
suất. Bốn GET tuần tự tới KBS, không retry, đều nhận được phản hồi JSON.

| Nguồn | Số hàng phản hồi | Hàng chuẩn hóa | 2021 / 2022 / 2023 / 2024 | Trạng thái |
|---|---:|---:|---|---|
| FPT | 998 | 998 | 250 / 249 / 249 / 250 | Đã lưu, chưa xác minh điều chỉnh/PiT |
| HPG | 998 | 998 | 250 / 249 / 249 / 250 | Đã lưu, chưa xác minh điều chỉnh/PiT |
| VCB | 998 | 998 | 250 / 249 / 249 / 250 | Đã lưu, chưa xác minh điều chỉnh/PiT |
| VNINDEX | 998 | 0 | Chặn toàn bộ đầu vào chỉ số | Có hàng không thỏa quan hệ OHLC |

Ba cổ phiếu có tổng **2.994 bar**, từ 04/01/2021 đến 31/12/2024, không
có bar cuối tuần hoặc volume bằng 0 trong phản hồi này. Đây là thống kê
nguồn tải hiện tại; số hàng không chứng minh đầy đủ lịch giao dịch.

Kiểm tra độc lập quan hệ `low <= min(open, close) <= max(open, close)
<= high` trên byte VNINDEX đã lưu phát hiện ba hàng ngày 17/02/2021,
10/12/2021 và 15/05/2023 không thỏa. Chưa xác định nguyên nhân hoặc giá
đúng. Không nới điều kiện, sửa close/high/low, loại riêng ba ngày hoặc
tự đổi nguồn để chạy được. Raw 998 hàng vẫn giữ; luồng chuẩn hóa chỉ số
bị chặn ngay hàng lỗi đầu tiên. Chưa dùng VNINDEX này làm lịch chuẩn
hay comparator lợi suất; báo cáo không có chỉ số đầu tư.

## Nguồn, đơn vị và thời gian

Provider cũ trả DataFrame cho UI, chưa lưu snapshot giá ở luồng đó.
Adapter mới dùng endpoint GET công khai tương ứng trong mã KBS của
`vnstock 4.0.7`, giữ phản hồi HTTP gốc, URL, thời điểm tải và header hữu
ích. Không import Vnstock, không đăng nhập/API key, không thay package
hoặc gọi các bước khởi tạo toàn cục của thư viện. Giữ timeout/giới hạn
8 MiB, tối đa bốn instrument và 2.000 hàng mỗi phản hồi.

KBS raw equity được giữ theo VND, chỉ số theo điểm. Căn cứ mapping là
mã adapter đã cài: đường xử lý cổ phiếu chia raw cho 1.000 trước khi
trả nghìn VND; không nhân 1.000 lần nữa trên raw HTTP. Bản chép `quote.py`
và `const.py` được ghim hash riêng để truy nguyên nhận định này; chưa
phải kiểm chứng đơn vị độc lập với sở giao dịch.

Đọc JSON số bằng Decimal, xuất giá thành chuỗi, không qua float hoặc
làm tròn hai chữ số như đường provider cũ. Chấp nhận tối đa sáu chữ số
thập phân, không sửa giá ngoài phạm vi/precision được hỗ trợ. Chặn sai
symbol, khóa JSON trùng, số không hữu hạn/bool, volume phân số/âm,
ngày trùng/sai định dạng, thiếu OHLCV hoặc quan hệ giá không hợp lệ.
Hàng ngoài khoảng được ghi thống kê và giữ trong raw; không bù ngày.

`source_time` như `07:00` được giữ nguyên là nhãn nguồn không timezone;
`available_at=null`. Thời điểm tải hôm nay không được đổi thành mốc
khả dụng năm 2021–2024. [Tài liệu Vnstock hiện tại](https://www.vnstocks.com/docs/vnstock/thi-truong-market)
mô tả nến và giá đã điều chỉnh theo sự kiện quyền, nhưng đó là tài liệu
thế hệ 5; chưa xác minh riêng công thức/factor/lịch sửa của feed đã lấy.
Vì vậy `adjustment_status` vẫn unknown, không gọi raw này là giá khớp
nguyên trạng lịch sử hoặc giá total return đã được chứng nhận.

## Điều kiện còn thiếu

Báo cáo liệt kê các blocker: công thức điều chỉnh/corporate actions,
lịch sở độc lập, thời điểm khả dụng/phiên bản lịch sử, quy tắc thực thi
theo giai đoạn và mô hình thanh toán trong phiên. `eligible_for_execution`
luôn false ở protocol này; chưa có đường bật qua config hoặc chuyển
snapshot thành scenario giao dịch. Engine giả lập mốc 33 giữ nguyên.

Khi một chỉ số chuẩn hóa được, công cụ chỉ so các nhãn ngày cổ phiếu với
nhãn chỉ số **cùng nguồn** để tìm khác biệt; không xem đó là xác minh
lịch sở. Trong run này VNINDEX bị chặn nên các phép so ngày giữ null.
Universe vẫn là ba mã phát triển còn tồn tại, chưa xử lý survivorship
hoặc xác lập cohort VN30 theo thời gian.

Đã tìm/đọc các nguồn nền tảng:

- [VSD công bố lịch nghỉ thanh toán 2024](https://vsdc.vn/vi/ad/159293)
  và [HNX điều chỉnh lịch nghỉ cuối tháng 4/2024](https://www.hnx.vn/vi-vn/chi-tiet-lich-nghi-gd-60018631.html?_page=1)
  cho thấy phải xét phiên bản, loại lịch và đúng sở. Không áp thông báo
  HNX làm lịch HOSE cho ba cổ phiếu này.
- [VSD tổng kết thay đổi thời điểm thanh toán từ 29/08/2022](https://vsdc.vn/vi/ad/155750)
  và [thông báo vận hành của VNDIRECT](https://www.vndirect.com.vn/tin_vndirect/vndirect-chinh-thuc-giao-dich-chung-khoan-t2-tu-ngay-29-08-2022/)
  là căn cứ nghiên cứu tiếp phần thanh toán trong ngày. Không lấy độ trễ
  hai phiên ở open trong demo làm triển khai chính xác quy tắc này.

Lưu HTML tài liệu Vnstock thành công. Ba lượt tải archive VSD/HNX bằng
Python thất bại kiểm chứng certificate, giữ lỗi và không bỏ kiểm SSL.
Các URL/tra cứu web ở trên chưa thành snapshot lịch/luật được xác nhận
trong registry. Probe robots KBS trả HTTP 400, trạng thái chưa xác định;
chưa xác minh quyền phân phối lại raw. Vì vậy dữ liệu nằm local, ngoài Git.

## Chạy và tái lập

```powershell
.\run.ps1 market-snapshot --capture
.\run.ps1 market-snapshot --replay outputs/market-snapshots/20261102T145138Z-21243d88
```

Capture cần Internet, dùng config `configs/market_snapshot_v0_1.json`.
Replay hoàn toàn offline, kiểm hash/file set, đọc lại raw và tái tính
normalized JSON, quality report và CSV. Không chạy bản chép nguồn. Có
thể truyền `--config <file>` khi capture; replay từ chối override.

Run này replay khớp, nhưng CLI vẫn trả exit 2 vì có một instrument lỗi
chuẩn hóa. Exit 2 không được diễn giải thành snapshot đã sửa hoặc pass
chất lượng; đọc `quality.json` để xem lỗi. Lỗi toàn vẹn/tái tính được
báo riêng. Không retry tự động hoặc sửa lịch để tăng coverage.

Run giữ `config.json`, raw/HTTP/outcome của mỗi mã, `normalized.json`,
`quality.json`, `prices.csv`, bản chép decoder/runner, manifest và seal.
Cookie/authorization header không được lưu. Raw/CSV nằm ngoài Git;
clone chỉ có code/config/data card/metadata. Có thể tự capture một run
mới hoặc khôi phục đúng ID từ bản sao local để replay.

37 test mới và 104 test nhóm snapshot/provider/engine đạt; kiểm JSON
Decimal, identity/unit/date, thiếu hàng, transport/parse failure, dữ liệu
ngoài kỳ, source/index alignment, private headers, CLI và reseal/tái tính.
87 hash artifact cũ giữ nguyên; không tạo review DB hoặc gọi LLM.
Toàn bộ 682 test và Ruff đạt, giữ hai cảnh báo phụ thuộc test cũ.
Frontend không đổi nên không chạy lại build/QA giao diện.
Study và kiểm tra ba hàng VNINDEX được ghim trong
[manifest](../../data/development/market-prices-v0.1/manifest.json).
Xem [validation](../../data/development/market-prices-v0.1/validation.json).

Tiếp theo là đối soát chỉ số bằng nguồn độc lập có provenance; xử lý
lịch sở/thanh toán đúng thời kỳ và corporate actions, rồi mới nối giá
với các baseline. Chưa có kết quả backtest thị trường ở mốc này.
