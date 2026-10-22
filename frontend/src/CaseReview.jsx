import React, { useEffect, useState } from "react";

const labels = {
  pending: "Chưa có đáp án",
  answered: "Có đáp án",
  unanswerable: "Thiếu bằng chứng",
  needs_ocr: "Cần OCR / đọc lại bảng",
  wrong_period: "Sai kỳ báo cáo",
};
const blank = () => ({
  evidence_id: "S1",
  statement: "",
  quote: "",
  extracted_numbers: [],
});
const scopeNames = {
  consolidated: "Hợp nhất",
  parent: "Công ty mẹ / riêng lẻ",
  unknown: "Chưa rõ phạm vi",
  not_applicable: "Không áp dụng",
};

export default function CaseReview({ api, Panel, Notice }) {
  const [list, setList] = useState(null),
    [caseId, setCaseId] = useState(""),
    [detail, setDetail] = useState(null);
  const [status, setStatus] = useState("pending"),
    [reviewer, setReviewer] = useState(""),
    [notes, setNotes] = useState("");
  const [answers, setAnswers] = useState([blank()]),
    [declaration, setDeclaration] = useState(false);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [message, setMessage] = useState("");
  async function refresh() {
    const next = await api("research/cases");
    setList(next);
    setCaseId((id) => id || next.cases[0]?.case_id || "");
  }
  useEffect(() => {
    refresh().catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    if (!caseId) return;
    let active = true;
    setDetail(null);
    setError("");
    setMessage("");
    setDeclaration(false);
    api(`research/cases/${caseId}`)
      .then((r) => {
        if (!active) return;
        setDetail(r);
        setStatus(r.review?.status || "pending");
        setReviewer((previous) => r.review?.reviewer || previous);
        setNotes(r.review?.notes || "");
        setAnswers(r.review?.answers?.length ? r.review.answers : [blank()]);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [caseId]);
  function edit(i, key, value) {
    setAnswers((rows) =>
      rows.map((a, n) => (n === i ? { ...a, [key]: value } : a)),
    );
  }
  async function save(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const review = await api("research/reviews", {
        pack_id: detail.pack_id,
        case_id: caseId,
        previous_revision: detail.review?.revision || null,
        status,
        reviewer,
        declaration,
        answers:
          status === "answered"
            ? answers.map((a) => ({
                ...a,
                extracted_numbers: a.extracted_numbers
                  .map((n) => n.trim())
                  .filter(Boolean),
              }))
            : [],
        notes,
      });
      setDetail((r) => ({ ...r, review }));
      setDeclaration(false);
      setMessage(
        "Đã lưu phiên bản chấm mới; các phiên bản trước được giữ lại.",
      );
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  async function download() {
    setError("");
    try {
      const r = await api("research/reviews/export");
      const url = URL.createObjectURL(
        new Blob(
          [r.annotations.map((a) => JSON.stringify(a)).join("\n") + "\n"],
          { type: "application/x-ndjson" },
        ),
      );
      const a = document.createElement("a");
      a.href = url;
      a.download = `${r.pack_id}-reviews.jsonl`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message);
    }
  }
  const invalid =
    !detail ||
    !reviewer.trim() ||
    (status !== "pending" && !declaration) ||
    (status === "answered" &&
      (!detail.case.evidence.length ||
        answers.some((a) => !a.statement.trim() || !a.quote.trim()))) ||
    (!["pending", "answered"].includes(status) && !notes.trim());
  return (
    <Panel
      title="Tạo đáp án tham chiếu"
      subtitle="Bạn đọc tài liệu và ghi câu trả lời đã kiểm tra để làm mốc đối chiếu với AI."
    >
      <details className="audit-details">
        <summary>Chọn câu hỏi và nhập đáp án tham chiếu</summary>
        <ol className="review-guide">
          <li>Chọn một câu hỏi trong danh sách bên dưới.</li>
          <li>Mở PDF đã lưu, tìm và kiểm tra thông tin trả lời câu hỏi.</li>
          <li>
            Nhập đáp án cùng trích dẫn nguyên văn; nếu nguồn không đủ, chọn
            “Thiếu bằng chứng”.
          </li>
        </ol>
        {error && <Notice tone="error">{error}</Notice>}
        {message && <Notice tone="green">{message}</Notice>}
        {list && (
          <>
            <p className="footnote">
              Đã lưu đối chiếu {list.declared_reviewed_cases}/
              {list.cases.length} câu hỏi. Đây là bản nhập thủ công, cần người
              đọc kiểm tra nội dung.
            </p>
            <label className="review-field">
              Câu hỏi cần đối chiếu
              <select
                aria-label="Câu hỏi cần đối chiếu"
                value={caseId}
                disabled={busy}
                onChange={(e) => setCaseId(e.target.value)}
              >
                {list.cases.map((c) => (
                  <option key={c.case_id} value={c.case_id}>
                    {c.ticker} · {c.question} · {labels[c.status]}
                  </option>
                ))}
              </select>
            </label>
            {detail && (
              <>
                <h3>{detail.case.question}</h3>
                <p className="footnote">
                  Các đoạn dưới đây đã được pin. Mở tài liệu gốc để kiểm tra
                  bảng, kỳ, đơn vị và doanh nghiệp mẹ/con.
                </p>
                {detail.case.evidence.map((s) => (
                  <details key={s.evidence_id} className="audit-details">
                    <summary>
                      {s.evidence_id} · {s.source.ticker} ·{" "}
                      {s.source.reporting_period || "Chưa rõ kỳ"} ·{" "}
                      {s.source.title}
                    </summary>
                    <p className="footnote">
                      Trang/mục {s.passage.page} · ký tự {s.passage.start}–
                      {s.passage.end} ·{" "}
                      {scopeNames[s.source.statement_scope] ||
                        s.source.statement_scope}{" "}
                      ·{" "}
                      {s.source.origin === "dataset_mirror"
                        ? "Bản nhập dataset"
                        : "Nguồn thu thập trực tiếp"}
                    </p>
                    <div className="review-source-links">
                      <a
                        className="source-link"
                        href={s.source.source_url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Mở tài liệu gốc
                      </a>
                      {s.source.media_type === "application/pdf" && (
                        <a
                          className="source-link"
                          href={`/api/documents/${s.source.version_id}/raw#page=${s.passage.page}`}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Mở PDF đã lưu đúng phiên bản
                        </a>
                      )}
                    </div>
                    <pre className="page-text">{s.passage.text}</pre>
                  </details>
                ))}
                <form className="review-form" onSubmit={save}>
                  <div className="review-grid">
                    <label className="review-field">
                      Trạng thái
                      <select
                        aria-label="Trạng thái chấm"
                        value={status}
                        disabled={busy}
                        onChange={(e) => setStatus(e.target.value)}
                      >
                        {Object.entries(labels).map(([v, label]) => (
                          <option key={v} value={v}>
                            {label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="review-field">
                      Tên hoặc ký hiệu người chấm
                      <input
                        aria-label="Người chấm"
                        maxLength={100}
                        required
                        value={reviewer}
                        disabled={busy}
                        onChange={(e) => setReviewer(e.target.value)}
                      />
                    </label>
                  </div>
                  {status === "answered" && (
                    <>
                      {answers.map((a, i) => (
                        <fieldset className="review-answer" key={i}>
                          <legend>Đáp án {i + 1}</legend>
                          <label className="review-field">
                            Đoạn bằng chứng
                            <select
                              aria-label={`Nguồn đáp án ${i + 1}`}
                              value={a.evidence_id}
                              onChange={(e) =>
                                edit(i, "evidence_id", e.target.value)
                              }
                              disabled={busy}
                            >
                              {detail.case.evidence.map((s) => (
                                <option key={s.evidence_id}>
                                  {s.evidence_id}
                                </option>
                              ))}
                            </select>
                          </label>
                          <label className="review-field">
                            Đáp án tham chiếu bạn đã kiểm tra
                            <textarea
                              aria-label={`Câu trả lời ${i + 1}`}
                              maxLength={400}
                              required
                              value={a.statement}
                              disabled={busy}
                              onChange={(e) =>
                                edit(i, "statement", e.target.value)
                              }
                            />
                          </label>
                          <label className="review-field">
                            Trích dẫn nguyên văn từ đoạn nguồn
                            <textarea
                              aria-label={`Trích dẫn đáp án ${i + 1}`}
                              minLength={12}
                              maxLength={400}
                              required
                              value={a.quote}
                              disabled={busy}
                              onChange={(e) => edit(i, "quote", e.target.value)}
                            />
                          </label>
                          <label className="review-field">
                            Chuỗi số cần đối chiếu, mỗi dòng một mục
                            <textarea
                              aria-label={`Chuỗi số đáp án ${i + 1}`}
                              value={a.extracted_numbers.join("\n")}
                              disabled={busy}
                              onChange={(e) =>
                                edit(
                                  i,
                                  "extracted_numbers",
                                  e.target.value.split("\n"),
                                )
                              }
                            />
                          </label>
                          {answers.length > 1 && (
                            <button
                              type="button"
                              className="text-button"
                              disabled={busy}
                              onClick={() =>
                                setAnswers((rows) =>
                                  rows.filter((_, n) => n !== i),
                                )
                              }
                            >
                              Bỏ đáp án {i + 1}
                            </button>
                          )}
                        </fieldset>
                      ))}
                      <button
                        type="button"
                        className="text-button"
                        disabled={busy || answers.length === 3}
                        onClick={() => setAnswers((rows) => [...rows, blank()])}
                      >
                        Thêm đáp án
                      </button>
                    </>
                  )}
                  <label className="review-field">
                    Ghi chú / lý do không trả lời được
                    <textarea
                      aria-label="Ghi chú chấm"
                      value={notes}
                      maxLength={3000}
                      disabled={busy}
                      onChange={(e) => setNotes(e.target.value)}
                    />
                  </label>
                  <label className="review-declaration">
                    <input
                      type="checkbox"
                      checked={declaration}
                      disabled={busy}
                      onChange={(e) => setDeclaration(e.target.checked)}
                    />
                    Tôi đã đọc nguồn và kiểm tra nội dung chấm.
                  </label>
                  <div className="extract-action">
                    <button
                      className="button primary"
                      disabled={busy || invalid}
                    >
                      {busy ? "Đang lưu…" : "Lưu đáp án tham chiếu"}
                    </button>
                    <button
                      type="button"
                      className="text-button"
                      disabled={busy}
                      onClick={download}
                    >
                      Tải annotation JSONL
                    </button>
                  </div>
                  <p className="footnote">
                    Bản ghi lưu local, kèm người khai báo, thời điểm lưu và
                    revision. Kiểm tra trích dẫn không tự xác nhận ngữ nghĩa
                    hoặc danh tính người chấm.
                  </p>
                </form>
              </>
            )}
          </>
        )}
      </details>
    </Panel>
  );
}
