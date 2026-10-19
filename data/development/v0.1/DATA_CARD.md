# Case phát triển 0.1 — chờ người duyệt

24 câu hỏi từ 3 mã FPT/HPG/VCB × 8 chủ đề cấu hình trước. Mỗi case có tối đa
3 đoạn nguồn từ corpus v0.5, có SHA-256/raw version/page/offset để đối chiếu.
Đây là candidate để phát triển hỏi đáp; **0 human gold**, chưa là mẫu sự kiện
BCTC/nhãn lợi suất, không dùng làm held-out test hoặc để công bố accuracy.

Nguồn có cả publisher snapshot và dataset mirror. Quyền toàn văn theo data
card corpus v0.5: chỉ lưu local; Git giữ metadata và checksum. Phương pháp chọn
FTS5 hiện tại chưa bảo đảm đúng kỳ/entity/statement scope. 24 câu hỏi không
đồng nghĩa 24 bộ nguồn độc lập; các case có thể dùng lại trang/tài liệu.

Pack: `outputs/development-cases/20261019T024426Z-202a2c66/`. Mở `review.md`,
đọc nguồn gốc và `cases.jsonl` để xem kỳ/phạm vi; không chỉ đọc đoạn rời của bảng.
Giữ nguyên `cases.jsonl` và template; sao chép template sang một file annotation
mới trong cùng thư mục khi chấm, để giữ bản pending ban đầu.

Mỗi hàng annotation giữ `case_id`. Trạng thái:

- `pending`: chưa duyệt, không tính vào tập đã chấm.
- `answered`: có câu trả lời và bằng chứng đúng câu hỏi.
- `unanswerable`: không đủ thông tin trong các đoạn, ghi lý do.
- `needs_ocr`: parser/OCR không đủ để đọc đáng tin cậy.
- `wrong_period`: đoạn không trả lời đúng kỳ hỏi, ghi lý do.

Hàng đã duyệt cần `reviewer`, `reviewed_at` ISO có timezone. `answers` là list
các object `evidence_id` (S1–S3), `statement`, `quote` nguyên văn và
`extracted_numbers` (list chuỗi). Tối đa 3 đáp án, mỗi quote 12–400 ký tự.
Kiểm entity mẹ/con, kết quả/kế hoạch, năm/quý, hợp nhất/riêng lẻ, đơn vị và dấu
âm. Các trạng thái không trả lời giữ `answers=[]` và `notes` giải thích.

```powershell
.\run.ps1 development-cases `
  --pack outputs/development-cases/20261019T024426Z-202a2c66 `
  --check-reviews outputs/development-cases/20261019T024426Z-202a2c66/annotations.reviewed.jsonl
```

Checker kiểm checksum nguồn, đủ case, reviewer, timezone, quote và số; không
tự xác thực người chấm/ngữ nghĩa. `human_reviewed_cases_declared` là số khai
báo sau kiểm integrity. Review nội dung không tự chứng minh khả dụng lịch sử.
Chưa có timestamp/revision proof nên các case vẫn ngoài PiT strict.

Tham khảo [luồng và kết quả phát triển](../../../docs/research/14-single-agent-development.md).
