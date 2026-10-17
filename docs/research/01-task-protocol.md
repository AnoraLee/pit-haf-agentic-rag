# Task, timeline và hợp đồng dữ liệu — bản phát triển 0.1

## Tác vụ và đơn vị mẫu

Tác vụ chính: phân tích một doanh nghiệp Việt Nam tại `decision_at` từ bằng
chứng đã khả dụng, sinh báo cáo có trích dẫn và dự đoán hướng lợi suất 5 phiên.
Mẫu chính đề xuất là **sự kiện công bố báo cáo tài chính hợp nhất** (quý,
soát xét bán niên, kiểm toán năm). Giải trình/công bố/tin và báo cáo thường niên
là bằng chứng bổ sung. Phân tích định kỳ là robustness riêng; không trộn thành
mẫu chính để tăng số mẫu tùy ý.

`sample_id = ticker + disclosure_record_id + protocol_version`. Mỗi sự kiện
ban đầu có một mẫu; revisions dùng để kiểm tra đúng version tại cutoff. Nếu
đánh giá revision như một sự kiện mới, đăng ký thành cohort riêng trước test.
Nhiều mã cùng ngày phải được giữ thành block khi ước lượng bất định.

Mục tiêu universe 10–20 mã, ít nhất 3 ngành, nhiều năm. Mã pilot dự kiến
FPT/HPG/VCB để kiểm tra ba loại báo cáo; không phải universe cuối cùng và không
được chọn theo lợi suất tương lai. Phải có danh sách lịch sử thành phần/niêm
yết/ngừng giao dịch/hủy niêm yết nếu khả thi. Nếu chỉ lấy mã còn tồn tại, ghi
survivorship bias và giới hạn phạm vi, không tuyên bố đại diện toàn thị trường.

## Timeline và nhãn chính

Đề xuất quyết định lúc **16:00 Asia/Ho_Chi_Minh** tại phiên đầu tiên có
`available_at <= decision_at`. Giờ này là lịch phân tích dự kiến của hệ thống,
không là giả định giờ công bố/giờ khớp. Lịch phiên phải đến từ nguồn xác minh.
Thông tin đến sau mốc đó đợi phiên phân tích sau. Feature giá cũng phải vượt
gateway; dữ liệu cuối ngày chưa chứng minh khả dụng không được tự đưa vào.

```text
available_at của đúng revision
  -> phiên phân tích d, decision_at = d 16:00 (+07:00)
  -> phiên giao dịch kế tiếp s0, điểm khớp sớm nhất khả thi theo engine
  -> s0, s1, s2, s3, s4: horizon chính 5 phiên
  -> evaluator đọc giá/nhãn sau horizon; agent không được truy cập
```

Nhãn price-return phát triển đề xuất:
`r_5 = close(s4) / open(s0) - 1`. UP nếu `r_5 > 0`; DOWN nghĩa là lợi suất
không dương, gồm đúng 0. Báo riêng tỷ lệ zero return; không tự bỏ các mẫu đó.
Đây là nhãn từ entry-reference tới close phiên thứ năm, không phải công thức
close(T−1) của CARAG. Horizon 1/10/20 phiên chỉ là robustness được khóa trước.

Giá open tham chiếu không bảo đảm lệnh thật khớp được. Nếu thiếu open/close,
ngừng giao dịch hoặc corporate action không xử lý được: label unavailable và
failure reason; giữ trong flow chart số mẫu, không chuyển sang ngày sinh lợi
hơn. Chốt cách tính total/price return và sự kiện cổ tức trước khi freeze.
Raw giá có `adjustment_status=unknown` hiện chỉ dùng khảo sát, chưa đủ để tuyên
bố nhãn/backtest PiT nghiêm ngặt. Exit close s4 chỉ khả thi nếu lệnh thoát đã
đặt theo lịch từ trước và engine hỗ trợ; nếu không, dùng next feasible execution
và báo độ lệch so với nhãn, không đồng nhất nhãn với PnL.

Output phân tích có UP/DOWN/ABSTAIN. ABSTAIN là hành vi từ chối dự đoán, không
là lớp thật thứ ba để tính F1. Các lý do: thiếu evidence, conflict chưa giải
quyết, quote/numeric verification fail, model timeout/JSON/OOM, bất định cao.
Ngưỡng abstention chọn trên development/validation và khóa trước test.
Confidence tự báo là điểm chắc chắn chủ quan; chỉ gọi probability/calibrated
confidence khi có quy trình calibration và kiểm tra trên tập riêng.

## Policy giao dịch tách khỏi dự đoán

Policy ban đầu: long-only/cash, không leverage/short. Với dự đoán UP được xác
minh, mở vị thế trong giới hạn slot `1/N_universe`; DOWN không mở vị thế mới;
ABSTAIN không mở lệnh mới. Vị thế đang có tuân thủ lịch thoát 5 phiên và tồn kho
bán được của engine; ABSTAIN không tự chuyển thành SELL. Risk có thể giảm target
hoặc chặn lệnh nhưng không đổi label. Nhiều sự kiện cùng mã, vốn thiếu và giới
hạn slot phải có quy tắc deterministic được chốt trong M2. Mọi classifier/LLM
so sánh dùng cùng policy, phí, slippage và timeline.

Buy & Hold/Equal Weight là strategy danh mục riêng; không gán dự đoán giả cho
chúng. VNINDEX là đối chứng chỉ số price return, không là tài sản mua trực tiếp.
Phân tích đúng mà trade không khớp, hoặc PnL âm, vẫn phải được báo cáo.

## Schema evidence/version

| Trường | Semantics/kiểm tra |
|---|---|
| record_id / version_id | bản ghi logic / revision bất biến; chunk và fact tham chiếu cả hai |
| source_id / source_url | tổ chức/endpoint gốc, URL listing và document khi khác nhau |
| ticker / document_type | mã Việt Nam, loại tài liệu, hợp nhất/riêng lẻ là thuộc tính riêng |
| event_at | thời điểm sự kiện/kỳ báo cáo; có thể là ngày, không dùng làm eligibility |
| published_at | giờ công bố có timezone nếu nguồn xác minh; unknown thì null |
| available_at | thời điểm/bound khả dụng của **đúng bytes revision**, timezone bắt buộc khi vào Guard |
| retrieved_at | lúc lấy bytes; không chứng minh khả dụng lịch sử |
| availability_basis | verified_publication / conservative_date_bound / unverified + bằng chứng đi kèm |
| timestamp_precision | second / minute / day / unknown; không bịa second precision |
| content_hash | SHA-256 raw bytes; text/chunks có hash riêng và extractor version |
| raw_snapshot_path | snapshot bất biến; đường dẫn + quyền sử dụng/chia sẻ |
| page_or_section | page, section, offset quote để truy ngược |
| adjustment_status | verified_unadjusted / verified_adjusted / unknown; document không áp dụng ghi N/A |

Thêm `publication_date`, `timestamp_evidence_path`, `version_basis`,
`statement_scope`, `currency`, `unit`, `reporting_period`, `system_recorded_at`,
`supersedes_version_id` khi phù hợp. ID phải duy nhất, version hash khớp bytes.
Không tự lấy ngày ký báo cáo, tên file hoặc HTTP Last-Modified làm bằng chứng
giờ công bố lịch sử. Snapshot tải hôm nay không tự là snapshot tại ngày trước.

Date-only: giữ `published_at=null`, `publication_date` gốc; policy phát triển
đề xuất lấy upper bound đầu ngày kế tiếp tại +07:00, và phân tích ở phiên sau
theo lịch. Bound được ghi là conservative, không gọi là giờ công bố thật.
Đây chỉ là sensitivity cohort cho tới khi chứng minh đúng ngày/phiên bản;
strict cohort đòi bằng chứng availability và revision integrity đủ tin cậy.
Metadata thiếu/unverified -> quarantine có lý do, không silently drop khỏi audit.

Chỉ mô tả schema là **version-aware evidence/provenance**, chưa gọi là hệ
bi-temporal hoàn chỉnh. Muốn dùng thuật ngữ đó phải có valid/system intervals,
append-only lịch sử transaction và query theo cả cutoff khả dụng lẫn thời điểm
hệ thống ghi nhận; chỉ hai cột thời gian không đủ.

## Quyết định và điều kiện còn mở

| Quyết định | Đề xuất để phát triển | Khi phải chốt |
|---|---|---|
| Mẫu/horizon | sự kiện BCTC hợp nhất, 5 phiên | M1→M2; sau feasibility với giảng viên |
| Label | UP/>0, DOWN/<=0, price return entry→s4 | trước freeze nhãn; corporate actions phải giải quyết |
| Universe/years | 10–20 mã ≥3 ngành; chưa chốt năm vì chưa biết coverage | sau pilot, trước nhãn/test |
| Calendar/settlement/lot | nguồn chính thức theo sàn và từng giai đoạn | trước nghiệm thu engine M2 |
| Date-only strictness | quarantine khỏi strict; cohort bound riêng | trước thu thập rộng |
| Splits/threshold | chronological và purge/embargo theo label interval | trước thử prompt/model trên test |
| Model/context/thinking | qwen3:4b là ứng viên, sequential calls | sau 20–30 mẫu thật và benchmark |
| Deadline/budget/mẫu trường | chưa xác định | khi yêu cầu của trường/tài nguyên ảnh hưởng mốc |

Không cần dừng viết code chẩn đoán/UI để chờ những quyết định này. Chúng là
điều kiện phải khóa trước thực nghiệm cuối, chưa phải quyết định đã được phê duyệt.
