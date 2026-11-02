import React, { useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";

const statusLabels = {
  pending: "Đang đối chiếu",
  needs_context: "Cần thêm bằng chứng",
  rejected: "Không chấp nhận",
  confirmed: "Đã đối chiếu đủ",
};
const checkLabels = {
  label: "Đã kiểm tra chỉ tiêu",
  value: "Đã kiểm tra chuỗi số và dấu",
  year: "Đã kiểm tra năm của ô số",
  unit: "Đã kiểm tra đơn vị",
  statement_scope: "Đã kiểm tra phạm vi hợp nhất/riêng lẻ",
};
const methodLabels = {
  explicit_column: "Theo năm ghi ở cột",
  annual_current: "Năm nay theo kỳ tài chính trên trang",
  annual_previous: "Năm trước theo kỳ tài chính trên trang",
};
const missingLabels = {
  label: "nhãn chỉ tiêu",
  value: "giá trị",
  period: "tiêu đề cột kỳ",
  unit: "đơn vị",
  statement_scope: "phạm vi",
  supported_year_basis: "cơ sở xác định năm được hỗ trợ",
  numeric_value_not_dash: "giá trị số thay cho dấu gạch",
};

export default function OcrCellReview({ api, view, cell, busy, setBusy }) {
  const [record, setRecord] = useState(null);
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const active = useRef(true);
  useEffect(() => {
    active.current = true;
    return () => {
      active.current = false;
    };
  }, []);
  const runId = view.ocr_run_id;
  const query = `policy_id=${encodeURIComponent(view.policy_id)}${view.header_ocr_run_id ? `&header_run_id=${encodeURIComponent(view.header_ocr_run_id)}` : ""}`;
  const endpoint = `research/ocr-previews/${runId}/cell-links/reviews`;
  function display(data) {
    const selected = data.cells.find(
      (c) => c.candidate_id === cell.candidate_id,
    );
    if (!selected)
      throw new Error(
        "Ô số hoặc nguồn đã thay đổi. Hãy liên kết lại trước khi đối chiếu.",
      );
    const latest = selected.latest;
    setRecord(selected);
    setForm({
      status: latest?.status || "pending",
      reviewer: latest?.reviewer || "",
      declaration: false,
      checks:
        latest?.checks ||
        Object.fromEntries(Object.keys(checkLabels).map((k) => [k, false])),
      metric: latest?.interpretation?.metric || cell.fields.label?.text || "",
      value_literal:
        latest?.interpretation?.value_literal || cell.fields.value.text,
      year: latest?.interpretation?.year || "",
      year_method: latest?.year_method || "",
      calendar_mapping_checked: false,
      year_basis_note: latest?.year_basis_note || "",
      correction_notes: latest?.correction_notes || "",
      notes: latest?.notes || "",
    });
  }
  async function load() {
    setBusy("ocr-review-load");
    setError("");
    setNotice("");
    try {
      const data = await api(`${endpoint}?${query}`);
      if (active.current) display(data);
    } catch (err) {
      if (active.current) setError(err.message);
    } finally {
      setBusy("");
    }
  }
  function update(key, value) {
    setNotice("");
    setForm((previous) => {
      const next = {
        ...previous,
        [key]: value,
        declaration: key === "declaration" ? value : false,
      };
      const check = {
        metric: "label",
        value_literal: "value",
        year: "year",
        year_method: "year",
      }[key];
      if (check) next.checks = { ...previous.checks, [check]: false };
      if (key === "year_method" || key === "year")
        next.calendar_mapping_checked = false;
      return next;
    });
  }
  const confirmed = form?.status === "confirmed";
  const mappedYear =
    form?.year_method === "annual_current" ||
    form?.year_method === "annual_previous";
  const corrected =
    form &&
    (form.metric !== cell.fields.label?.text ||
      form.value_literal !== cell.fields.value.text);
  const ready =
    form &&
    form.reviewer.trim() &&
    (form.status === "pending" || form.declaration) &&
    ((form.status !== "rejected" && form.status !== "needs_context") ||
      form.notes.trim()) &&
    (!confirmed ||
      (record.requirements.can_confirm &&
        Object.values(form.checks).every(Boolean) &&
        form.metric.trim() &&
        form.value_literal.trim() &&
        /^(19|20)\d{2}$/.test(form.year) &&
        form.year_method &&
        (!mappedYear ||
          (form.calendar_mapping_checked && form.year_basis_note.trim())) &&
        (!corrected || form.correction_notes.trim())));
  async function save() {
    if (!ready) return;
    setBusy("ocr-review-save");
    setError("");
    setNotice("");
    try {
      const data = await api(endpoint, {
        run_id: runId,
        policy_id: view.policy_id,
        header_run_id: view.header_ocr_run_id || null,
        candidate_id: cell.candidate_id,
        binding_sha256: record.binding_sha256,
        previous_revision: record.latest?.revision || null,
        status: form.status,
        reviewer: form.reviewer,
        declaration: form.declaration,
        checks: form.checks,
        interpretation: confirmed
          ? {
              metric: form.metric,
              value_literal: form.value_literal,
              year: form.year,
              unit: cell.fields.unit?.observed_value,
              statement_scope: cell.fields.statement_scope?.observed_value,
            }
          : null,
        year_method: confirmed ? form.year_method : null,
        calendar_mapping_checked:
          confirmed && mappedYear ? form.calendar_mapping_checked : false,
        year_basis_note: form.year_basis_note,
        correction_notes: form.correction_notes,
        notes: form.notes,
      });
      if (active.current) {
        display(data);
        setNotice("Đã lưu phiếu và lịch sử. Kết quả OCR gốc được giữ nguyên.");
      }
    } catch (err) {
      if (active.current) setError(err.message);
    } finally {
      setBusy("");
    }
  }
  return (
    <details className="ocr-review">
      <summary>Ghi kết quả đối chiếu ô số</summary>
      <p>
        Phiếu lưu riêng bản chép và nhận xét của người đối chiếu. Chưa tự đưa số
        vào câu trả lời hoặc coi đây là nhãn độc lập.
      </p>
      <button className="button" disabled={!!busy} onClick={load}>
        {busy === "ocr-review-load" && <Loader2 className="spin" size={16} />}
        {record ? "Tải lại phiếu đối chiếu" : "Mở phiếu đối chiếu"}
      </button>
      {error && (
        <p role="alert" className="ocr-error">
          {error}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      {form && (
        <>
          <p>
            {record.history.length} lần lưu cho ô này.{" "}
            {record.latest
              ? `Trạng thái đã lưu: ${statusLabels[record.latest.status]}.`
              : "Chưa có nhận xét đã lưu."}
          </p>
          {!record.requirements.can_confirm && (
            <p className="ocr-review-missing">
              Chưa thể xác nhận: thiếu{" "}
              {record.requirements.missing
                .map((k) => missingLabels[k] || k)
                .join(", ")}
              . Có thể lưu đang đối chiếu, cần bằng chứng hoặc không chấp nhận.
            </p>
          )}
          <fieldset disabled={!!busy}>
            <legend>Phiếu cho ô đang chọn</legend>
            <label>
              Người đối chiếu
              <input
                aria-label="Người đối chiếu ô OCR"
                value={form.reviewer}
                maxLength={100}
                onChange={(e) => update("reviewer", e.target.value)}
              />
            </label>
            <label>
              Kết quả đối chiếu
              <select
                aria-label="Kết quả đối chiếu ô OCR"
                value={form.status}
                onChange={(e) => update("status", e.target.value)}
              >
                {Object.entries(statusLabels).map(([key, label]) => (
                  <option
                    key={key}
                    value={key}
                    disabled={
                      key === "confirmed" && !record.requirements.can_confirm
                    }
                  >
                    {label}
                  </option>
                ))}
              </select>
            </label>
            {confirmed && (
              <>
                <label>
                  Chỉ tiêu đã đối chiếu
                  <input
                    aria-label="Chỉ tiêu đã đối chiếu OCR"
                    value={form.metric}
                    maxLength={250}
                    onChange={(e) => update("metric", e.target.value)}
                  />
                </label>
                <label>
                  Chuỗi số đã đối chiếu
                  <input
                    aria-label="Chuỗi số đã đối chiếu OCR"
                    value={form.value_literal}
                    maxLength={120}
                    onChange={(e) => update("value_literal", e.target.value)}
                  />
                </label>
                <label>
                  Cơ sở xác định năm
                  <select
                    aria-label="Cơ sở xác định năm OCR"
                    value={form.year_method}
                    onChange={(e) => update("year_method", e.target.value)}
                  >
                    <option value="">Chọn cơ sở đã kiểm tra</option>
                    {record.requirements.year_methods.map((m) => (
                      <option key={m} value={m}>
                        {methodLabels[m]}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Năm đã đối chiếu
                  <input
                    aria-label="Năm đã đối chiếu OCR"
                    inputMode="numeric"
                    maxLength={4}
                    placeholder="Tự nhập năm đã kiểm tra"
                    value={form.year}
                    onChange={(e) => update("year", e.target.value)}
                  />
                </label>
                {mappedYear && (
                  <>
                    <label className="ocr-review-check">
                      <input
                        type="checkbox"
                        checked={form.calendar_mapping_checked}
                        onChange={(e) =>
                          update("calendar_mapping_checked", e.target.checked)
                        }
                      />
                      Tôi đã kiểm tra cách quy Năm nay/Năm trước theo kỳ tài
                      chính kết thúc 31/12.
                    </label>
                    <label>
                      Giải thích cách xác định năm
                      <textarea
                        aria-label="Giải thích cách xác định năm OCR"
                        value={form.year_basis_note}
                        maxLength={1000}
                        rows={3}
                        onChange={(e) =>
                          update("year_basis_note", e.target.value)
                        }
                      />
                    </label>
                  </>
                )}
                <p>
                  Đơn vị nguồn: {cell.fields.unit?.text}. Phạm vi nguồn:{" "}
                  {cell.fields.statement_scope?.text}. Nếu không khớp ảnh, hãy
                  chọn cần thêm bằng chứng.
                </p>
                <label>
                  Lý do sửa bản chép OCR{corrected ? " (bắt buộc)" : ""}
                  <textarea
                    aria-label="Lý do sửa bản chép OCR"
                    value={form.correction_notes}
                    maxLength={2000}
                    rows={3}
                    onChange={(e) => update("correction_notes", e.target.value)}
                  />
                </label>
                <div className="ocr-review-checks">
                  {Object.entries(checkLabels).map(([key, label]) => (
                    <label className="ocr-review-check" key={key}>
                      <input
                        type="checkbox"
                        checked={form.checks[key]}
                        onChange={(e) =>
                          update("checks", {
                            ...form.checks,
                            [key]: e.target.checked,
                          })
                        }
                      />
                      {label}
                    </label>
                  ))}
                </div>
              </>
            )}
            <label>
              Nhận xét / bằng chứng còn thiếu
              <textarea
                aria-label="Nhận xét đối chiếu OCR"
                value={form.notes}
                maxLength={3000}
                rows={3}
                onChange={(e) => update("notes", e.target.value)}
              />
            </label>
            <label className="ocr-review-check">
              <input
                type="checkbox"
                checked={form.declaration}
                onChange={(e) => update("declaration", e.target.checked)}
              />
              Tôi đã đối chiếu ảnh PDF và xác nhận đây là nhận xét của tôi.
            </label>
            <button
              className="button"
              disabled={!!busy || !ready}
              onClick={save}
            >
              {busy === "ocr-review-save" && (
                <Loader2 className="spin" size={16} />
              )}
              Lưu phiếu đối chiếu OCR
            </button>
          </fieldset>
          <a href={`/api/${endpoint}/export?${query}`} download>
            Tải phiếu và lịch sử OCR (JSON)
          </a>
          {!!record.history.length && (
            <details>
              <summary>Lịch sử của ô đang chọn</summary>
              <ol>
                {record.history.map((e) => (
                  <li key={e.revision}>
                    <strong>{statusLabels[e.status]}</strong> · {e.reviewer} ·{" "}
                    {new Date(e.recorded_at).toLocaleString("vi-VN")}
                    <p>
                      {e.notes ||
                        e.correction_notes ||
                        "Không có ghi chú bổ sung."}
                    </p>
                    {e.interpretation && (
                      <p>
                        {e.interpretation.metric}:{" "}
                        {e.interpretation.value_literal} ·{" "}
                        {e.interpretation.year}
                      </p>
                    )}
                  </li>
                ))}
              </ol>
            </details>
          )}
        </>
      )}
    </details>
  );
}
