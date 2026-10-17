# Bài 2 — Point-in-Time Guard

## Vì sao cần module này?

Giả sử phân tích một doanh nghiệp lúc 16:00 ngày 01/07/2024 giờ Việt Nam.
Báo cáo mô tả quý I vẫn có thể được công bố sau ngày đó. Một báo cáo đã có
cũng có thể được sửa vào ngày 03/07. Dùng bản sửa mới để mô phỏng quyết định
ngày 01/07 sẽ đưa thông tin tương lai vào phân tích.

Module `src/pit_haf/data/point_in_time.py` chọn những phiên bản đã có tại thời
điểm quyết định. Nó là bước trước retrieval, tạo prompt và đọc memory của agent.
Các bước đó chưa được triển khai, nên hiện Guard mới được kiểm thử độc lập.

## Input và output

Hàm `select_as_of(records, decision_at=...)` nhận DataFrame với các trường:

| Trường | Ý nghĩa |
|---|---|
| `record_id` | ID của một bản ghi logic; các lần sửa của cùng bản ghi dùng cùng ID |
| `source_id` | Nguồn của bản ghi; giữ nguyên giữa các phiên bản |
| `available_at` | Thời điểm phiên bản này thực sự có thể quan sát; bắt buộc có múi giờ |
| `published_at` | Tùy chọn: thời điểm công bố, phải có múi giờ và không sau `available_at` |
| `content`, các trường khác | Nội dung bằng chứng; được giữ lại cho bản ghi được chọn |

`decision_at` cũng phải có múi giờ. Ví dụ `2024-07-01T16:00:00+07:00` tương
đương `2024-07-01T09:00:00Z`. Module chuyển thời gian sang UTC để so sánh.

Output là `PointInTimeResult` gồm:

- `records`: phiên bản mới nhất của từng `record_id` có
  `available_at <= decision_at`; có thể rỗng nếu chưa có dữ liệu.
- `audit`: ID, nguồn, thời điểm khả dụng, thời điểm quyết định và trạng thái
  `allowed` / `future` / `superseded`. Audit không chứa nội dung văn bản.
- `decision_at`: mốc quyết định theo UTC.

Trong lớp này, `allowed` nghĩa là vượt qua kiểm tra timestamp được cung cấp;
chưa có kiểm chứng độc lập độ chính xác của timestamp hoặc nội dung.
Audit dành cho kiểm tra thực nghiệm; chỉ đưa `records` vào bước truy xuất/LLM.
Không đưa audit chứa metadata tương lai vào ngữ cảnh của agent.

## Luồng xử lý

1. Kiểm tra schema, ID và timestamp. Thiếu timestamp, thiếu múi giờ hoặc có
   hai phiên bản trùng ID/thời điểm đều gây `PointInTimeError` cho cả đầu vào.
2. Loại phiên bản có thời điểm khả dụng sau mốc quyết định.
3. Trong các phiên bản còn lại, chọn bản mới nhất cho mỗi ID.
4. Trả bản ghi được chọn và audit; không sửa DataFrame đầu vào.

Phải lọc thời gian trước khi chọn phiên bản. Nếu chọn bản mới nhất của toàn
bộ lịch sử rồi mới lọc, bản sửa tương lai sẽ làm mất cả bản gốc hợp lệ.

## Chạy ví dụ nhỏ

```powershell
.\run.ps1 pit-demo
```

Ví dụ dùng dữ liệu giả định, không phải báo cáo FPT thật:

| Bản ghi | Khả dụng (giờ Việt Nam) | Với quyết định 01/07 lúc 16:00 |
|---|---|---|
| Báo cáo gốc, giá trị mẫu 100 | 01/07 lúc 09:00 | Được chọn |
| Bản sửa, giá trị mẫu 120 | 03/07 lúc 09:00 | Bị loại vì ở tương lai |
| Tin mới | 02/07 lúc 08:00 | Bị loại vì ở tương lai |

Trong Python:

```python
import pandas as pd
from pit_haf.data.point_in_time import select_as_of

evidence = pd.DataFrame([
    {
        "record_id": "example-report",
        "source_id": "synthetic-example",
        "available_at": "2024-07-01T09:00:00+07:00",
        "content": "Nội dung báo cáo giả định.",
    },
])
result = select_as_of(evidence, decision_at="2024-07-01T16:00:00+07:00")
print(result.records)
print(result.audit)
```

## Giới hạn và bước nối với dữ liệu thật

Provider hiện trả `session_date` và `retrieved_at`, chưa có `available_at`
đã xác minh. Truyền thẳng DataFrame đó vào Guard sẽ báo thiếu trường; không
được tự đổi tên `session_date` hoặc `retrieved_at` thành `available_at`.

Với mỗi tài liệu thật cần lưu nguồn, bằng chứng về thời điểm công bố/khả dụng,
nội dung từng phiên bản và snapshot. Nếu nguồn chỉ cung cấp ngày công bố mà
không có giờ, cần quy tắc bảo thủ được ghi rõ và kiểm chứng trước khi sử dụng.
Không giả định dữ liệu cuối ngày đã sẵn sàng ngay tại giờ đóng cửa.

Guard không khôi phục được phiên bản cũ đã mất, không xác minh giá đã điều chỉnh
và không loại bỏ kiến thức tương lai trong trọng số LLM. `available_at` phải
thuộc đúng phiên bản đang lưu, không chỉ là ngày công bố bản gốc.
Audit hiện được trả trong bộ nhớ; lưu audit và snapshot bền vững là bước tiếp theo.

## Câu hỏi tự giải thích

1. Tại sao báo cáo quý I có thể bị loại khi quyết định vào tháng VII?
2. Khi bản sửa công bố ngày 03/07, bản nào được phép dùng ngày 01/07?
3. Khác nhau giữa `session_date`, `retrieved_at` và `available_at` là gì?
4. Vì sao không dùng `pd.to_datetime(..., utc=True)` để tự hiểu timestamp
   thiếu múi giờ là UTC?
5. Guard chạy đúng có chứng minh LLM không biết kết quả tương lai không?
