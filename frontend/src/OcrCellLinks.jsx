import React, { useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";
import OcrCellReview from "./OcrCellReview";

const fields = [
  ["label", "Chỉ tiêu"],
  ["value", "Giá trị"],
  ["period", "Cột năm"],
  ["statement_period", "Kỳ tài chính trên trang"],
  ["unit", "Đơn vị"],
  ["statement_scope", "Phạm vi"],
];
const reasonLabel = {
  missing_or_ambiguous_label: "Thiếu nhãn chỉ tiêu rõ ràng",
  missing_or_ambiguous_period: "Chưa đọc được hàng tiêu đề cột năm đầy đủ",
  missing_or_ambiguous_unit: "Thiếu hoặc có nhiều đơn vị",
  missing_or_ambiguous_statement_scope: "Chưa xác định hợp nhất hay riêng lẻ",
  absolute_year_unresolved: "Chưa xác định năm tuyệt đối",
  incomplete_numeric_row: "Dòng thiếu ô hoặc có chuỗi số bị tách",
  low_confidence_field: "Có chữ/số với điểm nhận dạng thấp",
  label_value_alignment_uncertain: "Vị trí nhãn và giá trị chưa rõ",
  dash_is_not_zero: "Dấu gạch không được hiểu là số 0",
  missing_or_ambiguous_statement_period:
    "Chưa có dòng ghi kỳ tài chính rõ ràng trên trang",
  wrapped_label_requires_review:
    "Nhãn ghép từ nhiều dòng OCR, cần đối chiếu toàn bộ",
};

export default function OcrCellLinks({
  api,
  runId,
  pageNumber,
  headerRuns = [],
  busy,
  setBusy,
  onHighlight,
}) {
  const [view, setView] = useState(null);
  const [cellId, setCellId] = useState("");
  const [error, setError] = useState("");
  const [policyId, setPolicyId] = useState("ocr_cell_links_v0.1");
  const [headerRunId, setHeaderRunId] = useState("");
  const active = useRef(true);
  useEffect(() => {
    active.current = true;
    return () => {
      active.current = false;
    };
  }, []);
  const page = view?.pages.find((p) => p.page === pageNumber);
  const cell = page?.cells.find((c) => c.candidate_id === cellId);
  async function load() {
    setBusy("ocr-cell-links");
    setError("");
    try {
      const data = await api(
        `research/ocr-previews/${runId}/cell-links?policy_id=${encodeURIComponent(policyId)}${headerRunId ? `&header_run_id=${encodeURIComponent(headerRunId)}` : ""}`,
      );
      if (!active.current) return;
      setView(data);
      const first = data.pages.find((p) => p.page === pageNumber)?.cells[0];
      setCellId(first?.candidate_id || "");
      onHighlight(first?.fields.value || null, "Giá trị");
    } catch (err) {
      if (active.current) setError(err.message);
    } finally {
      setBusy("");
    }
  }
  return (
    <details className="ocr-cell-links">
      <summary>Ô số OCR và thông tin đi kèm</summary>
      <p>
        Ghép thử số với nhãn và tiêu đề có vị trí nguồn. Chưa tự sửa chữ, suy
        năm hoặc xác nhận số liệu cho câu trả lời.
      </p>
      <label>
        Cách liên kết ô OCR
        <select
          aria-label="Cách liên kết ô OCR"
          value={policyId}
          disabled={!!busy}
          onChange={(e) => {
            setPolicyId(e.target.value);
            setHeaderRunId("");
            setView(null);
            setError("");
            onHighlight(null, "");
          }}
        >
          <option value="ocr_cell_links_v0.1">Theo dòng OCR · v0.1</option>
          <option value="ocr_cell_links_v0.2">
            Theo vị trí và nhãn xuống dòng · v0.2 thử nghiệm
          </option>
        </select>
      </label>
      {policyId === "ocr_cell_links_v0.2" && (
        <label>
          Lượt OCR bổ sung tiêu đề trên cùng trang
          <select
            aria-label="Lượt OCR bổ sung tiêu đề trên cùng trang"
            value={headerRunId}
            disabled={!!busy}
            onChange={(e) => {
              setHeaderRunId(e.target.value);
              setView(null);
              setError("");
              onHighlight(null, "");
            }}
          >
            <option value="">Dùng chữ trong lượt đang mở</option>
            {headerRuns.map((r) => (
              <option key={r.run_id} value={r.run_id}>
                {r.run_id} · trang {pageNumber}
              </option>
            ))}
          </select>
          <small>
            Chỉ nhận vùng hẹp phía trên các hàng số, cùng version PDF và ảnh
            trang.
          </small>
        </label>
      )}
      <button className="button" disabled={!!busy} onClick={load}>
        {busy === "ocr-cell-links" && <Loader2 className="spin" size={16} />}
        Liên kết ô số từ OCR đã lưu
      </button>
      {error && <p role="alert">{error}</p>}
      {page && (
        <>
          <p>
            {page.cells.length} ô ứng viên trên trang {pageNumber} · chưa duyệt.
          </p>
          {!page.cells.length && (
            <p>
              Chưa có đủ cột số để liên kết, hoặc dòng bị tách/mơ hồ. Vẫn có thể
              xem từng từ OCR bên dưới.
            </p>
          )}
          {!!page.cells.length && (
            <label>
              Ô số OCR cần đối chiếu
              <select
                aria-label="Ô số OCR cần đối chiếu"
                value={cellId}
                onChange={(e) => {
                  setCellId(e.target.value);
                  const next = page.cells.find(
                    (c) => c.candidate_id === e.target.value,
                  );
                  onHighlight(next?.fields.value || null, "Giá trị");
                }}
              >
                {page.cells.map((c) => (
                  <option key={c.candidate_id} value={c.candidate_id}>
                    {c.column_id} · {c.fields.label?.text || "Thiếu nhãn"} ·{" "}
                    {c.fields.value.text}
                  </option>
                ))}
              </select>
            </label>
          )}
          {cell && (
            <>
              <dl className="ocr-cell-fields">
                {fields
                  .filter(
                    ([key]) =>
                      key !== "statement_period" ||
                      view.policy_id === "ocr_cell_links_v0.2",
                  )
                  .map(([key, label]) => (
                    <div key={key}>
                      <dt>{label}</dt>
                      <dd>
                        {cell.fields[key] ? (
                          <>
                            <button
                              aria-label={`Xem vị trí ${label.toLocaleLowerCase()} OCR`}
                              onClick={() =>
                                onHighlight(cell.fields[key], label)
                              }
                            >
                              {cell.fields[key].text}
                            </button>
                            {cell.fields[key].word_refs?.some(
                              (r) => r.ocr_run_id !== runId,
                            ) && <small>Chữ từ lượt OCR bổ sung</small>}
                          </>
                        ) : (
                          "Chưa đủ bằng chứng"
                        )}
                      </dd>
                    </div>
                  ))}
              </dl>
              <p>
                Cột {cell.column_id} chỉ là thứ tự từ trái sang phải. Nhãn có
                thể nhận sai hoặc thiếu; chữ và ý nghĩa vẫn cần đối chiếu.
              </p>
              <ul className="ocr-cell-reasons">
                {cell.review_reasons
                  .filter((r) => reasonLabel[r])
                  .map((r) => (
                    <li key={r}>{reasonLabel[r]}</li>
                  ))}
              </ul>
              <OcrCellReview
                key={cell.candidate_id}
                api={api}
                view={view}
                cell={cell}
                busy={busy}
                setBusy={setBusy}
              />
            </>
          )}
        </>
      )}
    </details>
  );
}
