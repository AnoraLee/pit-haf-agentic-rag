import React, { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import OcrCellLinks from "./OcrCellLinks";

const statusLabel = (value) =>
  ({
    ocr_unreviewed: "chưa duyệt",
    failed: "lượt lỗi",
    partial_failure: "có trang lỗi",
    integrity_failed: "lỗi toàn vẹn",
  })[value] || value;

export default function OcrPreview({
  api,
  ticker,
  query,
  mode,
  cutoff,
  reportingPeriod,
  versionId,
  busy,
  setBusy,
}) {
  const [pageInput, setPageInput] = useState("1");
  const [useRegion, setUseRegion] = useState(false);
  const [regionProfile, setRegionProfile] = useState("pdf_ocr_region_v0.2");
  const [regionInput, setRegionInput] = useState(["0", "0", "100", "100"]);
  const [runs, setRuns] = useState([]);
  const [runId, setRunId] = useState("");
  const [view, setView] = useState(null);
  const [pageIndex, setPageIndex] = useState(0);
  const [wordId, setWordId] = useState("");
  const [filter, setFilter] = useState("");
  const [error, setError] = useState("");
  const [imageError, setImageError] = useState(false);
  const [fieldOverlay, setFieldOverlay] = useState(null);
  useEffect(() => {
    let active = true;
    setRuns([]);
    setRunId("");
    setView(null);
    setError("");
    if (versionId) {
      api(`research/ocr-previews?version_id=${encodeURIComponent(versionId)}`)
        .then((data) => {
          if (active) setRuns(data.runs);
        })
        .catch((err) => {
          if (active) setError(err.message);
        });
    }
    return () => {
      active = false;
    };
  }, [versionId]);
  useEffect(() => {
    setView(null);
    setError("");
  }, [ticker, query, mode, cutoff, reportingPeriod]);
  const page = view?.pages[pageIndex];
  const words = page?.words || [];
  const visibleWords = words.filter((w) =>
    w.text.toLocaleLowerCase().includes(filter.trim().toLocaleLowerCase()),
  );
  const selected =
    visibleWords.find((w) => w.id === wordId) ||
    (fieldOverlay ? undefined : visibleWords[0]);
  useEffect(() => {
    setImageError(false);
  }, [view?.run.run_id, page?.page]);
  function display(data) {
    setView(data);
    setRunId(data.run.run_id);
    setPageIndex(0);
    setWordId("");
    setFilter("");
    setFieldOverlay(null);
  }
  async function create() {
    const tokens = pageInput.split(",").map((s) => s.trim());
    const pages = tokens.map(Number);
    if (
      tokens.some((s) => !/^\d{1,5}$/.test(s)) ||
      pages.length > (useRegion ? 1 : 4) ||
      new Set(pages).size !== pages.length ||
      pages.some((n) => n < 1 || n > 10000)
    ) {
      setError(
        useRegion
          ? "OCR khoanh vùng nhận đúng một số trang PDF."
          : "Nhập từ 1 đến 4 số trang PDF khác nhau, cách nhau bằng dấu phẩy.",
      );
      return;
    }
    const region = regionInput.map((s) => Number(s) / 100);
    if (
      useRegion &&
      (regionInput.some((s) => s.trim() === "") ||
        region.some((n) => !Number.isFinite(n) || n < 0 || n > 1) ||
        region[2] - region[0] < 0.01 ||
        region[3] - region[1] < 0.01)
    ) {
      setError("Vùng OCR cần nằm trong 0–100%, rộng và cao ít nhất 1% trang.");
      return;
    }
    setBusy("ocr-preview");
    setError("");
    setView(null);
    try {
      const data = await api("research/ocr-previews", {
        ticker,
        query,
        mode,
        document_version_id: versionId,
        pages,
        profile_id: useRegion ? regionProfile : "pdf_ocr_preview_v0.1",
        region: useRegion ? region : null,
        reporting_period: /^\d{4}$/.test(reportingPeriod)
          ? reportingPeriod
          : null,
        decision_at: mode === "strict_point_in_time" ? `${cutoff}+07:00` : null,
      });
      display(data);
      setRuns(
        (
          await api(
            `research/ocr-previews?version_id=${encodeURIComponent(versionId)}`,
          )
        ).runs,
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  }
  async function open() {
    setBusy("ocr-open");
    setError("");
    try {
      display(await api(`research/ocr-previews/${runId}`));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  }
  return (
    <details className="ocr-preview">
      <summary>OCR trang PDF · thử nghiệm</summary>
      <p>
        Đọc chữ từ ảnh trang khi PDF chưa có lớp chữ. Chọn một tài liệu ở phía
        trên, rồi nhập tối đa 4 số trang PDF.
      </p>
      <label className="ocr-region-toggle">
        <input
          type="checkbox"
          checked={useRegion}
          disabled={!!busy}
          onChange={(e) => setUseRegion(e.target.checked)}
        />
        Khoanh vùng OCR một trang · thử nghiệm
      </label>
      {useRegion && (
        <fieldset className="ocr-region-fields" disabled={!!busy}>
          <legend>Vùng đọc theo phần trăm trang gốc</legend>
          <label>
            Cách đọc chữ trong vùng
            <select
              aria-label="Cách đọc chữ trong vùng"
              value={regionProfile}
              onChange={(e) => setRegionProfile(e.target.value)}
            >
              <option value="pdf_ocr_region_v0.2">Một khối chữ · v0.2</option>
              <option value="pdf_ocr_sparse_v0.3">
                Các cụm chữ rời · v0.3 thử nghiệm
              </option>
            </select>
          </label>
          <p>
            Tính từ góc trên bên trái. 0, 0, 100, 100 là cả trang. Cấu hình này
            dùng 240 dpi; chỉ chạy một trang mỗi lượt. Cách đọc cụm chữ rời có
            thể làm tách chuỗi số, cần so với lượt đọc trước.
          </p>
          <div>
            {["Trái (%)", "Trên (%)", "Phải (%)", "Dưới (%)"].map(
              (label, i) => (
                <label key={label}>
                  {label}
                  <input
                    type="number"
                    min="0"
                    max="100"
                    step="0.1"
                    value={regionInput[i]}
                    onChange={(e) =>
                      setRegionInput((values) =>
                        values.map((v, j) => (i === j ? e.target.value : v)),
                      )
                    }
                  />
                </label>
              ),
            )}
          </div>
        </fieldset>
      )}
      <div className="ocr-controls">
        <label>
          Trang PDF cần đọc OCR
          <input
            aria-label="Trang PDF cần đọc OCR"
            value={pageInput}
            maxLength={30}
            disabled={!!busy}
            onChange={(e) => setPageInput(e.target.value)}
            placeholder="Ví dụ: 3, 48, 94"
          />
        </label>
        <button
          className="button"
          disabled={!!busy || !versionId || query.trim().length < 2}
          onClick={create}
        >
          {busy === "ocr-preview" && <Loader2 className="spin" size={16} />}Chạy
          OCR các trang đã chọn
        </button>
      </div>
      {!versionId && (
        <p>Hãy bấm “Xem tài liệu phù hợp” rồi chọn riêng một PDF.</p>
      )}
      {versionId && (
        <div className="ocr-controls">
          <label>
            Lượt OCR đã lưu
            <select
              aria-label="Lượt OCR đã lưu"
              value={runId}
              disabled={!!busy}
              onChange={(e) => setRunId(e.target.value)}
            >
              <option value="">Chọn lượt OCR</option>
              {runs.map((r) => (
                <option
                  key={r.run_id}
                  value={r.run_id}
                  disabled={r.status === "integrity_failed"}
                >
                  {r.run_id} ·{" "}
                  {r.profile_id === "pdf_ocr_sparse_v0.3"
                    ? "chữ rời v0.3"
                    : r.profile_id === "pdf_ocr_region_v0.2"
                      ? "vùng v0.2"
                      : "trang v0.1"}
                  {r.requested_region &&
                    r.requested_region[3] - r.requested_region[1] <= 0.1 &&
                    " · vùng hẹp"}{" "}
                  · trang {r.requested_pages?.join(", ")} ·{" "}
                  {statusLabel(r.status)}
                </option>
              ))}
            </select>
          </label>
          <button className="button" disabled={!!busy || !runId} onClick={open}>
            Mở bản OCR
          </button>
        </div>
      )}
      {error && (
        <p className="ocr-error" role="alert">
          {error}
        </p>
      )}
      {view && (
        <div className="ocr-result">
          <strong>
            {view.source.ticker} · {view.source.title}
          </strong>
          <p>
            Chữ và số OCR chưa được đối chiếu. Điểm nhận dạng không phải xác
            suất đúng; chưa dùng kết quả này làm facts hoặc ngữ cảnh trả lời.
          </p>
          {view.run.requested_region && (
            <p>
              Vùng đã chạy (trái, trên, phải, dưới):{" "}
              {view.run.requested_region
                .map((v) => `${Number((v * 100).toFixed(2))}%`)
                .join(" · ")}
              . Khung nét đứt trên ảnh ghi lại vùng này.
            </p>
          )}
          <label>
            Trang OCR đang xem
            <select
              aria-label="Trang OCR đang xem"
              disabled={!!busy}
              value={pageIndex}
              onChange={(e) => {
                setPageIndex(Number(e.target.value));
                setWordId("");
                setFilter("");
                setFieldOverlay(null);
              }}
            >
              {view.pages.map((p, i) => (
                <option key={p.page} value={i}>
                  Trang {p.page} ·{" "}
                  {p.status === "failed"
                    ? "lỗi"
                    : `${p.word_count} từ · ${p.low_confidence_words} điểm thấp`}
                </option>
              ))}
            </select>
          </label>
          {page?.status === "failed" ? (
            <p role="alert">
              Trang {page.page}: {page.error}
            </p>
          ) : (
            page && (
              <>
                <div className="ocr-grid">
                  <div>
                    <OcrCellLinks
                      key={`${view.run.run_id}:${page.page}`}
                      api={api}
                      runId={view.run.run_id}
                      pageNumber={page.page}
                      headerRuns={runs.filter(
                        (r) =>
                          r.run_id !== view.run.run_id &&
                          r.status === "ocr_unreviewed" &&
                          r.requested_pages?.length === 1 &&
                          r.requested_pages[0] === page.page &&
                          r.requested_region &&
                          r.requested_region[3] - r.requested_region[1] <= 0.1,
                      )}
                      busy={busy}
                      setBusy={setBusy}
                      onHighlight={(ref, name) => {
                        setFieldOverlay(ref ? { ref, name } : null);
                        setFilter("");
                        setWordId(ref?.word_ids[0] || "");
                      }}
                    />
                    <label>
                      Tìm trong chữ OCR
                      <input
                        aria-label="Tìm trong chữ OCR"
                        value={filter}
                        onChange={(e) => {
                          setFilter(e.target.value);
                          setFieldOverlay(null);
                        }}
                      />
                    </label>
                    <p>
                      {visibleWords.length} / {words.length} từ phù hợp · hiển
                      thị tối đa 250 từ.
                    </p>
                    <div
                      className="ocr-word-list"
                      role="region"
                      aria-label="Danh sách từ OCR"
                      tabIndex={0}
                    >
                      <table>
                        <thead>
                          <tr>
                            <th>Chữ OCR</th>
                            <th>Điểm / 100</th>
                          </tr>
                        </thead>
                        <tbody>
                          {visibleWords.slice(0, 250).map((w) => (
                            <tr
                              key={w.id}
                              className={
                                w.id === selected?.id ? "selected" : ""
                              }
                            >
                              <td>
                                <button
                                  aria-pressed={w.id === selected?.id}
                                  onClick={() => {
                                    setWordId(w.id);
                                    setFieldOverlay(null);
                                  }}
                                >
                                  {w.id} · {w.text}
                                </button>
                              </td>
                              <td>
                                {w.confidence.toFixed(1)}
                                {w.low_confidence && <small>Thấp</small>}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                  <div className="ocr-source-panel">
                    <p>
                      Ảnh từ PDF gốc · trang {page.page}
                      {fieldOverlay
                        ? ` · ${fieldOverlay.name}: ${fieldOverlay.ref.text}`
                        : selected && ` · ${selected.id}: ${selected.text}`}
                    </p>
                    <div className="ocr-page-image">
                      <img
                        src={page.image_url}
                        alt={`Trang OCR gốc ${page.page} của ${view.source.ticker}`}
                        onError={() => setImageError(true)}
                      />
                      {(selected ||
                        fieldOverlay ||
                        page.geometry.ocr_crop_pixels) && (
                        <svg
                          viewBox={`0 0 ${page.geometry.image_width} ${page.geometry.image_height}`}
                          role="img"
                          aria-label="Vùng OCR đã chạy và từ đang chọn"
                        >
                          {page.geometry.ocr_crop_pixels && (
                            <rect
                              x={page.geometry.ocr_crop_pixels[0]}
                              y={page.geometry.ocr_crop_pixels[1]}
                              width={
                                page.geometry.ocr_crop_pixels[2] -
                                page.geometry.ocr_crop_pixels[0]
                              }
                              height={
                                page.geometry.ocr_crop_pixels[3] -
                                page.geometry.ocr_crop_pixels[1]
                              }
                              fill="none"
                              stroke="#287b71"
                              strokeWidth={Math.max(
                                2,
                                page.geometry.image_width / 600,
                              )}
                              strokeDasharray="14 8"
                            />
                          )}
                          {fieldOverlay &&
                            fieldOverlay.ref.word_boxes.map((box, i) => (
                              <rect
                                key={i}
                                x={box[0]}
                                y={box[1]}
                                width={box[2] - box[0]}
                                height={box[3] - box[1]}
                                fill="rgba(154,89,163,0.15)"
                                stroke="#9a59a3"
                                strokeWidth={Math.max(
                                  2,
                                  page.geometry.image_width / 700,
                                )}
                              />
                            ))}
                          {selected && !fieldOverlay && (
                            <rect
                              x={selected.bbox_pixels[0]}
                              y={selected.bbox_pixels[1]}
                              width={
                                selected.bbox_pixels[2] -
                                selected.bbox_pixels[0]
                              }
                              height={
                                selected.bbox_pixels[3] -
                                selected.bbox_pixels[1]
                              }
                              fill="rgba(154,89,163,0.15)"
                              stroke="#9a59a3"
                              strokeWidth={Math.max(
                                2,
                                page.geometry.image_width / 700,
                              )}
                            />
                          )}
                        </svg>
                      )}
                    </div>
                    {imageError && (
                      <p role="alert">
                        Không tải được ảnh trang qua kiểm tra nguồn.
                      </p>
                    )}
                    <p>
                      Vùng tô là vị trí OCR trên ảnh đã kiểm tra từ PDF; chưa
                      xác nhận chữ hoặc số được nhận đúng.
                    </p>
                  </div>
                </div>
                <details>
                  <summary>Toàn bộ chữ OCR của trang</summary>
                  <pre>{page.text}</pre>
                </details>
              </>
            )
          )}
        </div>
      )}
    </details>
  );
}
