import React, { useState } from "react";

const labels = {
  pending: "Chưa duyệt / đã rút xác nhận",
  confirmed: "Đã xác nhận vị trí này",
  rejected: "Không phù hợp",
  needs_context: "Cần thêm ngữ cảnh",
};
const checkLabels = {
  label: "Tên chỉ tiêu đúng ý nghĩa tôi ghi bên dưới",
  value: "Chuỗi số và dấu âm khớp nguồn",
  year: "Cột năm đúng kỳ cần đối chiếu",
  unit: "Đơn vị đúng cho dòng này",
  statement_scope: "Phạm vi hợp nhất / riêng lẻ đúng nguồn",
};
const scopeLabel = (scope) =>
  ({ consolidated: "Hợp nhất", parent: "Công ty mẹ / riêng lẻ" })[scope] ||
  "Chưa có locator phạm vi";

export default function TableReview({
  api,
  runId,
  cell,
  location,
  record,
  busy,
  setBusy,
  onSaved,
  onReload,
}) {
  const latest = record?.latest;
  const [status, setStatus] = useState(latest?.status || "");
  const [reviewer, setReviewer] = useState(latest?.reviewer || "");
  const [metric, setMetric] = useState(latest?.interpretation?.metric || "");
  const [notes, setNotes] = useState(latest?.notes || "");
  const [checks, setChecks] = useState({});
  const [declaration, setDeclaration] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const f = location.fields;
  const confirmable = !!(
    f.unit &&
    f.statement_scope &&
    !cell.conflict_group_id
  );
  const valid =
    record &&
    reviewer.trim() &&
    status &&
    (status === "pending" || declaration) &&
    (status === "confirmed"
      ? confirmable &&
        metric.trim() &&
        Object.keys(checkLabels).every((key) => checks[key])
      : status === "pending" || notes.trim());

  async function save() {
    setBusy("table-review");
    setError("");
    setSaved(false);
    try {
      const result = await api(`research/table-evidence/${runId}/reviews`, {
        run_id: runId,
        candidate_id: cell.candidate_id,
        source_cell_id: location.cell_id,
        binding_sha256: record.binding_sha256,
        previous_revision: latest?.revision || null,
        status,
        reviewer,
        declaration,
        checks: Object.fromEntries(
          Object.keys(checkLabels).map((key) => [key, !!checks[key]]),
        ),
        interpretation:
          status === "confirmed"
            ? {
                metric,
                year: f.period.text,
                unit: f.unit.value,
                statement_scope: f.statement_scope.value,
              }
            : null,
        notes,
      });
      onSaved(result);
      setSaved(true);
      setChecks({});
      setDeclaration(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  }

  return (
    <section className="table-review" aria-label="Duyệt vị trí nguồn đang chọn">
      <h3>Duyệt vị trí nguồn đang chọn</h3>
      <p>
        Bạn đọc PDF và ghi kết luận cho đúng vị trí này. Đánh giá được lưu
        riêng, không tự áp dụng cho vị trí trùng hoặc sửa kết quả AI đã chạy.
      </p>
      <p className="table-review-status" role="status">
        {latest ? labels[latest.status] : "Vị trí này chưa có đánh giá"}
        {latest && ` · ${latest.reviewer}`}
      </p>
      <p className="footnote">
        Người duyệt tự khai báo; chưa xác nhận độc lập. Không tự chuyển thành
        nhãn chuẩn hoặc số liệu dùng cho backtest.
      </p>
      <dl className="table-review-source">
        <div>
          <dt>Số nguồn</dt>
          <dd>{f.value.text}</dd>
        </div>
        <div>
          <dt>Năm</dt>
          <dd>{f.period.text}</dd>
        </div>
        <div>
          <dt>Đơn vị</dt>
          <dd>{f.unit?.value || "Chưa có locator đơn vị"}</dd>
        </div>
        <div>
          <dt>Phạm vi</dt>
          <dd>{scopeLabel(f.statement_scope?.value)}</dd>
        </div>
      </dl>
      <fieldset disabled={!!busy || !record}>
        <label>
          Người duyệt
          <input
            aria-label="Người duyệt ô bảng"
            value={reviewer}
            maxLength={100}
            onChange={(e) => setReviewer(e.target.value)}
            placeholder="Tên hoặc ký hiệu của bạn"
          />
        </label>
        <label>
          Kết luận
          <select
            aria-label="Kết luận duyệt ô bảng"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setSaved(false);
            }}
          >
            <option value="">Chọn kết luận sau khi đọc nguồn</option>
            {Object.entries(labels).map(([key, label]) => (
              <option
                key={key}
                value={key}
                disabled={key === "confirmed" && !confirmable}
              >
                {label}
              </option>
            ))}
          </select>
        </label>
        {!confirmable && (
          <p className="table-review-reason">
            Thiếu locator đơn vị/phạm vi hoặc có nhóm khác số. Chọn “Cần thêm
            ngữ cảnh” hay “Không phù hợp”.
          </p>
        )}
        {status === "confirmed" && (
          <>
            <label>
              Chỉ tiêu bạn xác nhận
              <input
                aria-label="Chỉ tiêu xác nhận"
                value={metric}
                maxLength={200}
                onChange={(e) => setMetric(e.target.value)}
                placeholder="Ghi rõ chỉ tiêu theo ý nghĩa trong nguồn"
              />
            </label>
            <div className="table-review-checks">
              {Object.entries(checkLabels).map(([key, label]) => (
                <label key={key}>
                  <input
                    type="checkbox"
                    checked={!!checks[key]}
                    onChange={(e) =>
                      setChecks({ ...checks, [key]: e.target.checked })
                    }
                  />
                  {label}
                </label>
              ))}
            </div>
          </>
        )}
        <label>
          Ghi chú / lý do
          <textarea
            aria-label="Ghi chú duyệt ô bảng"
            value={notes}
            maxLength={3000}
            rows={3}
            onChange={(e) => setNotes(e.target.value)}
          />
        </label>
        {status && status !== "pending" && (
          <label className="table-review-declaration">
            <input
              type="checkbox"
              checked={declaration}
              onChange={(e) => setDeclaration(e.target.checked)}
            />
            Tôi đã trực tiếp đối chiếu vị trí PDF này và chịu trách nhiệm về kết
            luận đã ghi.
          </label>
        )}
        <button className="button primary" disabled={!valid} onClick={save}>
          {busy === "table-review"
            ? "Đang lưu đánh giá…"
            : "Lưu đánh giá vị trí này"}
        </button>
      </fieldset>
      {error && (
        <p className="table-review-error" role="alert">
          {error}
        </p>
      )}
      {saved && <p role="status">Đã lưu một phiên bản đánh giá mới.</p>}
      <div className="table-review-tools">
        <button className="text-button" onClick={onReload} disabled={!!busy}>
          Tải lại đánh giá
        </button>
        <a
          href={`/api/research/table-evidence/${runId}/reviews/export`}
          download
        >
          Tải lịch sử duyệt JSON
        </a>
      </div>
      <details className="table-provenance">
        <summary>
          Lịch sử vị trí này ({record?.history.length || 0} phiên bản)
        </summary>
        {(record?.history || [])
          .slice()
          .reverse()
          .map((event) => (
            <article key={event.revision}>
              <strong>
                {labels[event.status]} · {event.reviewer}
              </strong>
              <p>{new Date(event.recorded_at).toLocaleString("vi-VN")}</p>
              {event.interpretation && (
                <p>Chỉ tiêu: {event.interpretation.metric}</p>
              )}
              {event.notes && <p>{event.notes}</p>}
              <p>Revision: {event.revision}</p>
            </article>
          ))}
      </details>
    </section>
  );
}
