import React, { useEffect, useState } from "react";

const statuses = {
  completed_with_citations: "Có trích dẫn qua kiểm tra",
  abstained: "Từ chối trả lời",
  failed: "Lỗi mô hình",
  generation_failed: "Đầu ra mô hình chưa hợp lệ",
  not_run: "Chưa chạy",
  source_or_runner_failed: "Lỗi nguồn / bộ chạy",
  integrity_failed: "Không đạt kiểm tra toàn vẹn",
};
const reasons = {
  numbers_not_supported_by_quote: "Chuỗi số không khớp trích dẫn",
  quote_not_found: "Không tìm thấy trích dẫn nguyên văn",
  quote_ambiguous: "Trích dẫn trùng nhiều vị trí",
  unknown_evidence_id: "Mã bằng chứng không có trong nguồn",
  model_abstained: "Mô hình khai báo thiếu bằng chứng",
  named_entity_requires_review: "Cần kiểm tra doanh nghiệp được nhắc đến",
  model_digest_changed: "Phiên bản model thay đổi",
};
const reviewLabels = {
  pending: "Chưa có đáp án tham chiếu",
  answered: "Đã có đáp án tham chiếu",
  unanswerable: "Thiếu bằng chứng",
  needs_ocr: "Cần OCR",
  wrong_period: "Sai kỳ",
};
const batchLabels = {
  completed: "Đã kết thúc lịch chạy",
  stopped: "Đã dừng",
  interrupted: "Bị gián đoạn",
};

export default function DevelopmentEvaluation({ api, Panel, Notice }) {
  const [data, setData] = useState(null);
  const [ticker, setTicker] = useState("all");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function refresh() {
    setBusy(true);
    setError("");
    setData(null);
    try {
      setData(await api("research/evaluation"));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    refresh();
  }, []);
  function download() {
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
    );
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${data.batch.batch_id}-evaluation.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }
  const counts = data?.diagnostics || {};
  const comparison = data?.annotation_comparison;
  const tickers = [...new Set((data?.rows || []).map((row) => row.ticker))];
  const questions = (data?.rows || []).filter(
    (row) => ticker === "all" || row.ticker === ticker,
  );
  return (
    <Panel
      title="Câu hỏi và kết quả kiểm tra AI"
      subtitle="Xem nội dung từng câu hỏi, doanh nghiệp được hỏi và kết quả trả lời của AI."
    >
      <div className="evaluation-toolbar">
        <button className="text-button" disabled={busy} onClick={refresh}>
          {busy ? "Đang kiểm tra…" : "Cập nhật đánh giá"}
        </button>
        {data?.batch && (
          <button className="text-button" onClick={download}>
            Tải kết quả đánh giá
          </button>
        )}
      </div>
      {error && <Notice tone="error">{error}</Notice>}
      {data && (
        <>
          <p className="footnote">
            Đã lưu đối chiếu {data.declared_reviewed_cases}/{data.total_cases}{" "}
            câu hỏi.
            {data.declared_reviewed_cases === 0 &&
              " Chưa có đáp án tham chiếu để tính chỉ số đối chiếu."}
          </p>
          {!data.batch ? (
            <p>Chưa có bộ kết quả đã lưu cho các câu hỏi này.</p>
          ) : (
            <>
              <div className="evaluation-metrics">
                <div>
                  <strong>
                    {counts.verified_runs || 0}/{data.total_cases}
                  </strong>
                  <span>Bản chạy qua kiểm tra toàn vẹn</span>
                </div>
                <div>
                  <strong>{counts.completed_with_citations || 0}</strong>
                  <span>Câu có trích dẫn qua kiểm tra</span>
                </div>
                <div>
                  <strong>{counts.abstained || 0}</strong>
                  <span>Câu từ chối trả lời</span>
                </div>
                <div>
                  <strong>
                    {(counts.failed || 0) +
                      (counts.generation_failed || 0) +
                      (counts.source_or_runner_failed || 0) +
                      (counts.invalid_runs || 0)}
                  </strong>
                  <span>Lượt lỗi / chưa hoàn tất</span>
                </div>
              </div>
              <p className="footnote">
                Trích dẫn qua kiểm tra nguyên văn và số liệu vẫn cần người đọc
                xác nhận ý nghĩa. Những con số này không phải độ chính xác câu
                trả lời.
              </p>
              {Object.keys(data.rejected_claim_block_reasons || {}).length >
                0 && (
                <details className="audit-details">
                  <summary>Lý do chặn nhận định</summary>
                  <ul>
                    {Object.entries(data.rejected_claim_block_reasons).map(
                      ([key, count]) => (
                        <li key={key}>
                          {reasons[key] || key}: {count}
                        </li>
                      ),
                    )}
                  </ul>
                  <p className="footnote">
                    Một nhận định có thể có nhiều lý do chặn.
                  </p>
                </details>
              )}
              {comparison?.reference_span_hit_rate != null && (
                <p>
                  Vùng trích dẫn giao với đáp án đã khai báo:{" "}
                  {comparison.reference_spans_hit}/
                  {comparison.reference_answers} (
                  {(100 * comparison.reference_span_hit_rate).toFixed(1)}%).
                  Giao vị trí không xác nhận câu trả lời đúng nghĩa.
                </p>
              )}
              {comparison?.reference_numeric_quote_hit_rate != null && (
                <p>
                  Trích dẫn giao vị trí và chứa đủ chuỗi số tham chiếu:{" "}
                  {comparison.reference_numeric_quotes_hit}/
                  {comparison.numeric_reference_answers}. Đây là đối chiếu chuỗi
                  số trong nguồn, chưa kiểm tra đúng chỉ tiêu hoặc đơn vị theo
                  ngữ nghĩa.
                </p>
              )}
              <p className="footnote">
                {batchLabels[data.batch.status] || data.batch.status} · Chưa
                chạy: {counts.not_run || 0} câu hỏi. Bản chạy{" "}
                {data.batch.batch_id} · Kết quả phát triển, chưa xác nhận PiT
                lịch sử.
              </p>
            </>
          )}
          <section
            id="development-questions"
            className="evaluation-questions"
            aria-label="Danh sách câu hỏi đánh giá"
          >
            <div className="evaluation-question-heading">
              <h3>Danh sách {data.total_cases} câu hỏi</h3>
              <label className="review-field">
                Lọc doanh nghiệp
                <select
                  aria-label="Doanh nghiệp của câu hỏi"
                  value={ticker}
                  onChange={(e) => setTicker(e.target.value)}
                >
                  <option value="all">Tất cả doanh nghiệp</option>
                  {tickers.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <p className="footnote">
              Đang hiển thị {questions.length} câu hỏi. Mỗi câu được kiểm tra
              riêng cho từng doanh nghiệp.
            </p>
            <ol className="evaluation-question-list">
              {questions.map((row) => (
                <li key={row.case_id}>
                  <div className="evaluation-question-meta">
                    <strong>{row.ticker}</strong>
                    <span>{statuses[row.status] || row.status}</span>
                  </div>
                  <p className="evaluation-question-text">{row.question}</p>
                  <p className="footnote">
                    {row.accepted_claims != null && (
                      <>
                        {row.accepted_claims} nhận định qua kiểm tra ·{" "}
                        {row.rejected_claims} bị chặn ·{" "}
                      </>
                    )}
                    {reviewLabels[row.review_status] || row.review_status}
                  </p>
                </li>
              ))}
            </ol>
          </section>
        </>
      )}
    </Panel>
  );
}
