import React, { useEffect, useState } from "react";
import { ExternalLink, Loader2, Table2 } from "lucide-react";
import TableReview from "./TableReview";

const reasons = {
  missing_or_ambiguous_statement_scope: "Chưa rõ phạm vi hợp nhất / riêng lẻ",
  missing_or_ambiguous_unit: "Chưa rõ đơn vị",
  wrapped_label_requires_review: "Tên chỉ tiêu gồm nhiều dòng",
  dash_is_not_zero: "Dấu gạch ngang chưa được diễn giải là số 0",
  row_specific_unit_or_ratio_requires_review:
    "Cần kiểm tra đơn vị riêng của dòng",
  conflicting_values_same_label_requires_review:
    "Cùng nhãn chỉ tiêu nhưng có số khác nhau; AI không được chốt nhóm này",
  net_profit_label_alias_requires_review:
    "Cần kiểm tra ý nghĩa chỉ tiêu lợi nhuận thuần trong báo cáo này",
};
const fields = [
  ["label", "Chỉ tiêu", "#247c55"],
  ["value", "Giá trị", "#d78222"],
  ["period", "Cột năm", "#4269b0"],
  ["unit", "Đơn vị", "#9a59a3"],
  ["statement_scope", "Phạm vi", "#ad5161"],
];
const status = (s) =>
  ({
    extracted_unreviewed: "Đã đọc bảng · chưa duyệt",
    selected_candidates_unreviewed: "AI đã chọn ô · chưa duyệt",
    abstained_no_table_context: "Chưa có ô phù hợp",
    abstained: "AI chưa chọn được ô hợp lệ",
    invalid_generation: "Đầu ra AI chưa hợp lệ",
    failed: "Lượt chạy lỗi",
    integrity_failed: "Không qua kiểm tra toàn vẹn",
  })[s] || s;

export default function TableEvidence({
  api,
  Panel,
  Notice,
  ticker,
  query,
  mode,
  cutoff,
  reportingPeriod,
  busy,
  setBusy,
}) {
  const [runs, setRuns] = useState([]);
  const [runId, setRunId] = useState("");
  const [view, setView] = useState(null);
  const [chosen, setChosen] = useState(0);
  const [location, setLocation] = useState(0);
  const [field, setField] = useState("value");
  const [withModel, setWithModel] = useState(false);
  const [withTextLayer, setWithTextLayer] = useState(false);
  const [error, setError] = useState("");
  const [zoom, setZoom] = useState(false);
  const [imageError, setImageError] = useState(false);
  async function history() {
    const suffix =
      ticker === "all" ? "" : `?ticker=${encodeURIComponent(ticker)}`;
    const result = await api(`research/table-evidence${suffix}`);
    setRuns(result.runs);
  }
  useEffect(() => {
    let active = true;
    const suffix =
      ticker === "all" ? "" : `?ticker=${encodeURIComponent(ticker)}`;
    api(`research/table-evidence${suffix}`)
      .then((data) => {
        if (active) setRuns(data.runs);
      })
      .catch((err) => {
        if (active) setError(err.message);
      });
    return () => {
      active = false;
    };
  }, [ticker]);
  useEffect(() => {
    setView(null);
    setRunId("");
    setError("");
  }, [ticker, query, mode]);
  const cell = view?.cells[chosen];
  const alternatives = cell?.source_alternatives || [];
  const activeLocation = alternatives[location] || cell;
  const review = view?.reviews?.locations.find(
    (r) =>
      r.candidate_id === cell?.candidate_id &&
      r.source_cell_id === activeLocation?.cell_id,
  );
  const source = view?.sources.find(
    (s) => s.index === activeLocation?.source_index,
  );
  useEffect(() => {
    setLocation(0);
  }, [chosen, view?.run.run_id]);
  useEffect(() => {
    setImageError(false);
  }, [view?.run.run_id, source?.index]);
  async function open() {
    setBusy("table-history");
    setError("");
    try {
      setView(await api(`research/table-evidence/${runId}`));
      setChosen(0);
      setField("value");
      setZoom(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  }
  async function create() {
    setBusy("table");
    setError("");
    setView(null);
    try {
      const period = /^\d{4}$/.test(reportingPeriod) ? reportingPeriod : null;
      const data = await api("research/table-evidence", {
        ticker,
        query,
        mode,
        reporting_period: period,
        decision_at: mode === "strict_point_in_time" ? `${cutoff}+07:00` : null,
        use_model: withModel,
        profile_id: withTextLayer ? "table_cells_v0.7" : "table_cells_v0.6",
      });
      setView(data);
      setChosen(0);
      setRunId(data.run.run_id);
      setField("value");
      setZoom(false);
      await history();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  }
  async function reloadReviews() {
    setBusy("table-review-load");
    setError("");
    try {
      setView(await api(`research/table-evidence/${view.run.run_id}`));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  }
  const locators = (key) => {
    const f = activeLocation?.fields[key];
    if (!f) return [];
    if (key === "label") return activeLocation.fields.label_parts || [f];
    return [f.source || f];
  };
  return (
    <Panel
      className="table-evidence-panel"
      title="Đối chiếu ô bảng với PDF"
      subtitle="Chọn một chỉ tiêu để xem ô số, cột năm và phần đơn vị trên trang gốc."
    >
      <div className="table-evidence-body">
        <div className="table-evidence-actions">
          <label className="table-model-option">
            <input
              type="checkbox"
              checked={withModel}
              disabled={!!busy}
              onChange={(e) => setWithModel(e.target.checked)}
            />
            Nhờ AI chọn tối đa 3 ô liên quan
          </label>
          <label className="table-model-option">
            <input
              type="checkbox"
              checked={withTextLayer}
              disabled={!!busy}
              onChange={(e) => setWithTextLayer(e.target.checked)}
            />
            Đọc lại lớp chữ PDF · thử nghiệm
          </label>
          <button
            className="button primary"
            disabled={!!busy || ticker === "all" || query.trim().length < 2}
            onClick={create}
          >
            {busy === "table" ? (
              <Loader2 className="spin" size={16} />
            ) : (
              <Table2 size={16} />
            )}
            {busy === "table"
              ? "Đang đọc bảng…"
              : "Đọc bảng cho câu hỏi đang nhập"}
          </button>
        </div>
        <p className="footnote">
          Chọn doanh nghiệp và năm ở phần câu hỏi phía trên. Ô có nguồn và ID
          hợp lệ vẫn cần kiểm tra ý nghĩa; chưa có số liệu được xác nhận để đưa
          vào backtest.
          {withTextLayer &&
            " Đọc lại lớp chữ có thể chậm và đổi trang được chọn. Chưa hỗ trợ PDF cần OCR."}
        </p>
        <div className="table-saved-controls">
          <label>
            Lượt đọc bảng đã lưu
            <select
              aria-label="Lượt đọc bảng đã lưu"
              value={runId}
              disabled={!!busy}
              onChange={(e) => setRunId(e.target.value)}
            >
              <option value="">Chọn kết quả để xem</option>
              {runs.map((r) => (
                <option
                  key={r.run_id}
                  value={r.run_id}
                  disabled={r.status === "integrity_failed"}
                >
                  {r.ticker || "—"} · {status(r.status)} · {r.run_id}
                </option>
              ))}
            </select>
          </label>
          <button className="button" onClick={open} disabled={!!busy || !runId}>
            Mở kết quả đọc bảng
          </button>
        </div>
        {error && <Notice tone="error">{error}</Notice>}
        {view && (
          <div className="table-evidence-result">
            <div className="table-result-heading">
              <strong>
                {view.run.ticker} · {status(view.run.status)}
              </strong>
              <span>
                {view.cells.length} ô gợi ý · {view.run.llm_calls} lượt gọi AI ·
                PDF đã kiểm tra lại
              </span>
            </div>
            <p className="table-saved-question">
              Câu hỏi của lượt này: {view.run.question}
            </p>
            {view.context_audit && (
              <p className="table-saved-question">
                Đã lọc {view.context_audit.filtered_cells} ô ngoài phạm vi câu
                hỏi; gộp {view.context_audit.duplicate_groups} nhóm cùng nhãn và
                số.
                {view.context_audit.conflict_groups > 0 &&
                  " Có nhóm khác số liệu cần người kiểm tra."}
              </p>
            )}
            <Notice tone="amber">
              Kết quả phát triển chưa duyệt ngữ nghĩa. Không xác nhận phân tích
              tại thời điểm lịch sử hoặc độ chính xác tài chính.
            </Notice>
            {!cell && (
              <p className="table-empty">
                {view.context_audit?.query_supported === false
                  ? "Phần bảng hiện hỗ trợ số liệu lợi nhuận, doanh thu/thu nhập, tài sản/nợ và tiền theo năm. Câu hỏi này cần luồng báo cáo hoặc bằng chứng khác."
                  : "Chưa tìm được ô bảng phù hợp. Lượt chạy và lý do dừng vẫn được giữ trong lịch sử."}
              </p>
            )}
            {cell && (
              <div className="table-evidence-layout">
                <div className="table-cell-list">
                  <div
                    className="table-candidates-scroll"
                    role="region"
                    aria-label="Danh sách ô gợi ý"
                    tabIndex={0}
                  >
                    <table>
                      <thead>
                        <tr>
                          <th>Chỉ tiêu</th>
                          <th>Năm</th>
                          <th>Giá trị nguồn</th>
                        </tr>
                      </thead>
                      <tbody>
                        {view.cells.map((c, i) => (
                          <tr
                            key={c.candidate_id}
                            className={i === chosen ? "selected" : ""}
                          >
                            <td>
                              <button
                                aria-pressed={i === chosen}
                                onClick={() => {
                                  setChosen(i);
                                  setField("value");
                                }}
                              >
                                <span>
                                  {c.context_ref} · {c.label}
                                </span>
                                {c.model_selected && (
                                  <small>AI chọn · chưa duyệt</small>
                                )}
                                {c.equivalent_count > 1 && (
                                  <small>
                                    {c.equivalent_count} vị trí cùng nhãn/số
                                  </small>
                                )}
                              </button>
                            </td>
                            <td>{c.year}</td>
                            <td>{c.value}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <p className="table-cell-unit">
                    Đơn vị nguồn:{" "}
                    <strong>
                      {activeLocation?.fields.unit?.source.text ||
                        cell.unit ||
                        "Chưa xác định"}
                    </strong>
                  </p>
                  {alternatives.length > 1 && (
                    <label className="table-location-control">
                      Vị trí nguồn của nhóm ô
                      <select
                        aria-label="Vị trí nguồn của nhóm ô"
                        value={location}
                        onChange={(e) => setLocation(Number(e.target.value))}
                      >
                        {alternatives.map((a, i) => (
                          <option key={a.cell_id} value={i}>
                            Vị trí {i + 1} · trang {a.page} · vùng bảng{" "}
                            {a.header_index + 1}
                          </option>
                        ))}
                      </select>
                    </label>
                  )}
                  {cell.review_reasons.map((r) => (
                    <p className="table-review-reason" key={r}>
                      {reasons[r] || r}
                    </p>
                  ))}
                  <div
                    className="table-field-list"
                    aria-label="Các phần bằng chứng của ô"
                  >
                    {fields.map(([key, label, color]) => {
                      const refs = locators(key);
                      return (
                        <button
                          key={key}
                          disabled={!refs.length}
                          aria-pressed={field === key}
                          onClick={() => setField(key)}
                          style={{ "--field-color": color }}
                        >
                          <b>{label}</b>
                          <span>
                            {refs.length
                              ? refs.map((r) => r.text).join(" / ")
                              : "Chưa có bằng chứng"}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                  <TableReview
                    key={`${view.run.run_id}:${cell.candidate_id}:${activeLocation.cell_id}:${review?.latest?.revision || "pending"}`}
                    api={api}
                    runId={view.run.run_id}
                    cell={cell}
                    location={activeLocation}
                    record={review}
                    busy={busy}
                    setBusy={setBusy}
                    onSaved={(reviews) =>
                      setView((current) => ({ ...current, reviews }))
                    }
                    onReload={reloadReviews}
                  />
                </div>
                <div className="table-source-view">
                  <div className="table-source-toolbar">
                    <strong>PDF · trang {source.page}</strong>
                    <button
                      className="text-button"
                      onClick={() => setZoom(!zoom)}
                    >
                      {zoom ? "Vừa khung" : "Phóng to trang"}
                    </button>
                    <a href={source.raw_url} target="_blank" rel="noreferrer">
                      Mở PDF <ExternalLink size={12} />
                    </a>
                  </div>
                  <div className="table-page-scroll">
                    {!imageError ? (
                      <div
                        className={`table-page-canvas ${zoom ? "zoomed" : ""}`}
                        style={{
                          aspectRatio: `${source.width} / ${source.height}`,
                        }}
                      >
                        <img
                          src={source.image_url}
                          alt={`Trang PDF gốc ${source.page} của ${view.run.ticker}`}
                          onError={() => setImageError(true)}
                        />
                        <svg
                          viewBox={`0 0 ${source.width} ${source.height}`}
                          aria-label="Vùng bằng chứng đang chọn"
                          role="img"
                        >
                          {locators(field).map((r, i) => (
                            <rect
                              key={i}
                              x={r.bbox[0]}
                              y={r.bbox[1]}
                              width={r.bbox[2] - r.bbox[0]}
                              height={r.bbox[3] - r.bbox[1]}
                              stroke={fields.find(([key]) => key === field)[2]}
                              strokeWidth={source.width / 650}
                              fill="rgba(255,184,60,.23)"
                            />
                          ))}
                        </svg>
                      </div>
                    ) : (
                      <p className="table-empty">
                        Không tải được ảnh trang. Bạn có thể mở PDF gốc ở liên
                        kết trên.
                      </p>
                    )}
                  </div>
                  <p className="footnote">
                    Vùng tô là vị trí từ trên PDF, không phải xác nhận số liệu
                    đúng ngữ nghĩa. Bấm “Chỉ tiêu”, “Cột năm”, “Đơn vị” để đối
                    chiếu từng phần.
                  </p>
                  <details className="table-provenance">
                    <summary>Dấu vết nguồn và lượt chạy</summary>
                    <p>
                      Phiên bản: {view.run.profile_id} · {view.run.run_id}
                    </p>
                    <p>SHA-256 PDF: {source.content_hash}</p>
                  </details>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </Panel>
  );
}
