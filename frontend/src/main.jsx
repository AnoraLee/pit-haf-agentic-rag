import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  BookOpen,
  CheckCheck,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Database,
  Download,
  ExternalLink,
  FileCheck2,
  FileText,
  FlaskConical,
  FolderOpen,
  LayoutDashboard,
  Loader2,
  LockKeyhole,
  Menu,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  Terminal,
  X,
  Zap,
} from "lucide-react";
import "./styles.css";

const NAV = [
  ["overview", "Tổng quan", LayoutDashboard],
  ["documents", "Kho bằng chứng", FolderOpen],
  ["analysis", "Phân tích tài liệu", Sparkles],
  ["market", "Dữ liệu thị trường", BarChart3],
  ["experiments", "Thực nghiệm", FlaskConical],
];
const TYPES = {
  annual_report: "Báo cáo thường niên",
  financial_statement: "Báo cáo tài chính",
  business_overview: "Kết quả kinh doanh",
  earnings_overview: "Kết quả kinh doanh",
  financial_report: "Báo cáo tài chính",
};
const REASONS = {
  availability_unverified: "Chưa xác minh thời điểm khả dụng",
  timestamp_proof_missing: "Thiếu bằng chứng thời gian công bố",
  historical_revision_proof_missing: "Thiếu bằng chứng phiên bản lịch sử",
  time_and_version_proof_review_missing:
    "Chưa duyệt bằng chứng thời gian và phiên bản",
  date_only_excluded_from_strict:
    "Ngày công bố chưa đủ độ chính xác cho strict",
};
const fmt = (n) => (n == null ? "—" : new Intl.NumberFormat("vi-VN").format(n));
const when = (s) =>
  s ? new Date(s).toLocaleDateString("vi-VN") : "Chưa xác minh";
const navTo = (key) => {
  window.location.hash = key;
};
const shortTitle = (d) =>
  `${d.ticker} · ${TYPES[d.document_type] || "Công bố doanh nghiệp"} ${d.reporting_period || ""}${/Vietnamese/i.test(d.title) ? " · Tiếng Việt" : ""}`;

async function api(path, body) {
  const response = await fetch(
    `/api/${path}`,
    body
      ? {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      : undefined,
  );
  const data = await response.json().catch(() => ({}));
  if (!response.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : "Yêu cầu chưa hợp lệ. Kiểm tra lại thông tin đã nhập.",
    );
  return data;
}
function Icon({ icon: Component, size = 18, ...props }) {
  return (
    <Component size={size} strokeWidth={1.7} aria-hidden="true" {...props} />
  );
}
function Badge({ children, tone = "muted" }) {
  return <span className={`badge ${tone}`}>{children}</span>;
}
function Notice({ children, tone = "amber" }) {
  return (
    <div className={`notice ${tone}`} role="status">
      <Icon icon={tone === "error" ? X : ShieldCheck} />
      <div>{children}</div>
    </div>
  );
}
function Empty({ title, children, icon = Search }) {
  return (
    <div className="empty">
      <span className="empty-icon">
        <Icon icon={icon} size={27} />
      </span>
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
function Stat({ label, value, note, icon, tone = "green" }) {
  return (
    <div className="stat">
      <div className="stat-top">
        <span>{label}</span>
        <span className={`stat-icon ${tone}`}>
          <Icon icon={icon} />
        </span>
      </div>
      <div className="stat-number">{value}</div>
      <div className="stat-note">{note}</div>
    </div>
  );
}
function Panel({ title, subtitle, action, children, className = "" }) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-head">
        <div>
          <h2>{title}</h2>
          {subtitle && <p>{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}
function DocLogo({ ticker }) {
  return (
    <span className={`company-logo ${ticker?.toLowerCase()}`}>
      {ticker?.slice(0, 1)}
    </span>
  );
}
function DocTable({ docs, onOpen, compact = false }) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>TÀI LIỆU / DOANH NGHIỆP</th>
            {!compact && <th>KỲ BÁO CÁO</th>}
            <th>ĐỘ BAO PHỦ</th>
            <th>POINT-IN-TIME</th>
            <th>
              <span className="sr-only">Mở</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {docs.map((d) => (
            <tr key={d.version_id}>
              <td>
                <button className="doc-cell" onClick={() => onOpen(d)}>
                  <DocLogo ticker={d.ticker} />
                  <span>
                    <strong>{shortTitle(d)}</strong>
                    <small>
                      {d.ticker} <span>·</span>{" "}
                      {TYPES[d.document_type] || "Công bố doanh nghiệp"}
                    </small>
                  </span>
                </button>
              </td>
              {!compact && <td>{d.reporting_period || "—"}</td>}
              <td>
                <strong className="normal">
                  {d.text_pages}/{d.pages}
                </strong>
                <small>trang có văn bản</small>
              </td>
              <td>
                <Badge tone={d.quarantine_reasons.length ? "amber" : "green"}>
                  {d.quarantine_reasons.length
                    ? "Chờ xác minh"
                    : "Đủ điều kiện"}
                </Badge>
              </td>
              <td>
                <button
                  className="icon-button"
                  aria-label={`Đọc ${d.title}`}
                  onClick={() => onOpen(d)}
                >
                  <Icon icon={ChevronRight} size={17} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
function Coverage({ docs }) {
  const tickers = [...new Set(docs.map((d) => d.ticker))];
  const max = Math.max(
    1,
    ...tickers.map((t) =>
      docs.filter((d) => d.ticker === t).reduce((n, d) => n + d.pages, 0),
    ),
  );
  return (
    <div className="coverage">
      {tickers.map((ticker) => {
        const selected = docs.filter((d) => d.ticker === ticker);
        const pages = selected.reduce((n, d) => n + d.pages, 0);
        const text = selected.reduce((n, d) => n + d.text_pages, 0);
        return (
          <div className="coverage-row" key={ticker}>
            <div className="coverage-label">
              <DocLogo ticker={ticker} />
              <span>
                <strong>{ticker}</strong>
                <small>{selected.length} tài liệu</small>
              </span>
            </div>
            <div className="bar-track">
              <div
                className="bar-full"
                style={{ width: `${(pages / max) * 100}%` }}
              >
                <div
                  className="bar-text"
                  style={{ width: `${pages ? (text / pages) * 100 : 0}%` }}
                />
              </div>
            </div>
            <span className="coverage-count">
              {fmt(pages)} <small>trang</small>
            </span>
          </div>
        );
      })}
      <div className="legend">
        <span>
          <i className="dot green" /> Có lớp văn bản
        </span>
        <span>
          <i className="dot light" /> Cần kiểm tra OCR
        </span>
      </div>
    </div>
  );
}
function Quality({ pilot }) {
  const m = pilot?.metrics,
    r = pilot?.replay;
  if (!m)
    return (
      <Empty title="Chưa có thực nghiệm" icon={FlaskConical}>
        Kết quả sẽ xuất hiện khi có pilot tài liệu thật.
      </Empty>
    );
  const total = m.sample_denominator,
    exact = r?.strict_accepted ?? m.accepted_extractions;
  const mapped = r ? r.mapped_accepted - exact : 0,
    rejected = total - exact - mapped;
  const colors = ["#20765e", "#a1c6b7", "#e7ecea"];
  let offset = 0;
  return (
    <>
      <div className="quality">
        <svg
          className="donut"
          viewBox="0 0 120 120"
          role="img"
          aria-label={`${exact + mapped} trên ${total} trích dẫn qua kiểm tra nguồn`}
        >
          {[exact, mapped, rejected].map((n, i) => {
            const old = offset;
            offset += (n / total) * 100;
            return (
              <circle
                key={i}
                cx="60"
                cy="60"
                r="46"
                fill="none"
                stroke={colors[i]}
                strokeWidth="11"
                pathLength="100"
                strokeDasharray={`${(n / total) * 100} ${100 - (n / total) * 100}`}
                strokeDashoffset={-old}
                transform="rotate(-90 60 60)"
              />
            );
          })}
          <text x="60" y="59" textAnchor="middle" className="donut-value">
            {exact + mapped}
            <tspan className="donut-total">/{total}</tspan>
          </text>
          <text x="60" y="77" textAnchor="middle" className="donut-label">
            KHỚP NGUỒN
          </text>
        </svg>
        <div className="quality-legend">
          {[
            [exact, "Nguyên văn", colors[0]],
            [mapped, "Chỉ khác khoảng trắng", colors[1]],
            [rejected, "Bị chặn", colors[2]],
          ].map(([n, label, color]) => (
            <div key={label}>
              <span>
                <i className="dot" style={{ background: color }} />
                {label}
              </span>
              <strong>{n}</strong>
            </div>
          ))}
        </div>
      </div>
      <p className="footnote">
        Pilot trích xuất {total} đoạn. Chưa đánh giá tính đúng đắn của tóm tắt
        hoặc chất lượng dự báo.
      </p>
    </>
  );
}
function Overview({ data, docs, onOpen }) {
  const pages = docs.reduce((n, d) => n + d.pages, 0),
    text = docs.reduce((n, d) => n + d.text_pages, 0);
  const eligible = docs.filter((d) => !d.quarantine_reasons.length).length;
  return (
    <>
      <div className="hero">
        <div>
          <div className="eyebrow">
            <span className="live-dot" /> EVIDENCE FIRST. TIME AWARE.
          </div>
          <h1>
            Hiểu doanh nghiệp.
            <br />
            <span>Bắt đầu từ bằng chứng.</span>
          </h1>
          <p>
            Không gian phân tích cổ phiếu Việt Nam với nguồn tài liệu,
            <br className="desktop" /> thời điểm và trích dẫn có thể kiểm tra.
          </p>
          <button className="button lime" onClick={() => navTo("analysis")}>
            Khám phá tài liệu <Icon icon={ArrowRight} size={17} />
          </button>
        </div>
        <div className="hero-graphic" aria-hidden="true">
          <div className="orbit orbit-one" />
          <div className="orbit orbit-two" />
          <div className="graphic-file f1">
            <FileText size={24} />
            <span>PDF / NGUỒN GỐC</span>
            <i />
            <i />
          </div>
          <div className="graphic-core">
            <ShieldCheck size={36} strokeWidth={1.2} />
            <span>PiT-HAF</span>
          </div>
          <div className="graphic-file f2">
            <CheckCheck size={24} />
            <span>TRÍCH DẪN / ĐỐI CHIẾU</span>
            <i />
          </div>
          <span className="graphic-caption">SOURCE → RETRIEVE → VERIFY</span>
        </div>
      </div>
      <div className="stats-grid">
        <Stat
          label="Tài liệu trong kho"
          value={fmt(docs.length)}
          note={`${new Set(docs.map((d) => d.ticker)).size} doanh nghiệp Việt Nam`}
          icon={FolderOpen}
        />
        <Stat
          label="Trang đã thu thập"
          value={fmt(pages)}
          note="Snapshot gốc được kiểm tra SHA-256"
          icon={FileText}
          tone="blue"
        />
        <Stat
          label="Trang có văn bản"
          value={fmt(text)}
          note={`${fmt(pages - text)} trang trống / chưa OCR`}
          icon={BookOpen}
          tone="violet"
        />
        <Stat
          label="Đủ điều kiện PiT strict"
          value={fmt(eligible)}
          note={`${docs.length - eligible} tài liệu cần xác minh lịch sử`}
          icon={ShieldCheck}
          tone="amber"
        />
      </div>
      <div className="grid-two">
        <Panel
          title="Độ bao phủ tài liệu"
          subtitle="Phân bố snapshot thực tế theo doanh nghiệp"
          action={<Badge>LOCAL CORPUS</Badge>}
        >
          {docs.length ? (
            <Coverage docs={docs} />
          ) : (
            <Empty title="Không có tài liệu">
              Đổi bộ lọc hoặc kiểm tra kho dữ liệu.
            </Empty>
          )}
        </Panel>
        <Panel
          title="Chất lượng trích dẫn"
          subtitle="Kết quả pilot đã lưu trên máy"
          action={
            <button
              className="text-button"
              onClick={() => navTo("experiments")}
            >
              Chi tiết <Icon icon={ArrowUpRight} size={16} />
            </button>
          }
        >
          <Quality pilot={data.pilot} />
        </Panel>
      </div>
      <div className="grid-wide">
        <Panel
          title="Tài liệu trong không gian nghiên cứu"
          subtitle="Nguồn chính thức · phiên bản bất biến · đọc tại máy"
          action={
            <button className="text-button" onClick={() => navTo("documents")}>
              Xem tất cả <Icon icon={ArrowRight} size={16} />
            </button>
          }
        >
          <DocTable docs={docs.slice(0, 4)} onOpen={onOpen} compact />
        </Panel>
        <Panel title="Luồng phân tích" subtitle="Các bước đã nối với backend">
          <div className="flow-list">
            {[
              [Database, "Kho bằng chứng", "PDF và provenance"],
              [Search, "Truy xuất", "BM25 trên đoạn nguyên văn"],
              [Zap, "Mô hình local", "qwen3:4b qua Ollama"],
              [ShieldCheck, "Đối chiếu nguồn", "Trích dẫn và chuỗi số"],
            ].map(([I, label, desc], i) => (
              <div className="flow-step" key={label}>
                <span className="flow-icon">
                  <Icon icon={I} size={17} />
                </span>
                <div>
                  <strong>{label}</strong>
                  <small>{desc}</small>
                </div>
                <span className="step-number">0{i + 1}</span>
              </div>
            ))}
          </div>
          <button
            className="button secondary full"
            onClick={() => navTo("analysis")}
          >
            Mở bàn phân tích <Icon icon={ArrowRight} size={16} />
          </button>
        </Panel>
      </div>
      <Notice>
        <strong>Trạng thái nghiên cứu:</strong> Kho tài liệu hiện chưa đủ bằng
        chứng thời gian và phiên bản lịch sử để chạy PiT strict. Đọc tài liệu
        hiện tại vẫn khả dụng; dự báo và backtest chưa triển khai.
      </Notice>
    </>
  );
}
function Documents({ docs, onOpen }) {
  const [query, setQuery] = useState(""),
    [type, setType] = useState("all");
  const filtered = docs.filter(
    (d) =>
      `${d.title} ${d.ticker} ${d.reporting_period}`
        .toLowerCase()
        .includes(query.toLowerCase()) &&
      (type === "all" || d.document_type === type),
  );
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Kho bằng chứng</h1>
          <p>Mỗi tài liệu gắn với nguồn, phiên bản và dấu vết thu thập.</p>
        </div>
        <Badge tone="green">
          <LockKeyhole size={12} /> Snapshot bất biến
        </Badge>
      </div>
      <div className="stats-grid three">
        <Stat
          label="Tài liệu"
          value={docs.length}
          note="Tài liệu thật từ nguồn chính thức"
          icon={FileText}
        />
        <Stat
          label="Trang cần kiểm tra OCR"
          value={docs.reduce((n, d) => n + d.pages - d.text_pages, 0)}
          note="Chưa chạy OCR; không suy diễn nội dung"
          icon={BookOpen}
          tone="blue"
        />
        <Stat
          label="Cần xác minh PiT"
          value={docs.filter((d) => d.quarantine_reasons.length).length}
          note="Được giữ ngoài corpus lịch sử strict"
          icon={Clock3}
          tone="amber"
        />
      </div>
      <Panel
        title="Danh mục tài liệu"
        subtitle={`${filtered.length} tài liệu phù hợp bộ lọc`}
        action={<Badge>{docs.length} SNAPSHOTS</Badge>}
      >
        <div className="table-toolbar">
          <label className="input-with-icon">
            <Search size={17} />
            <input
              aria-label="Lọc tài liệu"
              placeholder="Tìm tên, mã cổ phiếu, kỳ báo cáo…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
          <select
            aria-label="Loại tài liệu"
            value={type}
            onChange={(e) => setType(e.target.value)}
          >
            <option value="all">Tất cả loại tài liệu</option>
            {[...new Set(docs.map((d) => d.document_type))].map((t) => (
              <option key={t} value={t}>
                {TYPES[t] || t}
              </option>
            ))}
          </select>
        </div>
        {filtered.length ? (
          <DocTable docs={filtered} onOpen={onOpen} />
        ) : (
          <Empty title="Không tìm thấy tài liệu">
            Thử từ khóa khác hoặc bỏ bộ lọc.
          </Empty>
        )}
      </Panel>
    </>
  );
}
function DocumentDrawer({ doc, onClose }) {
  const [page, setPage] = useState(1),
    [content, setContent] = useState(null),
    [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    setContent(null);
    setError("");
    api(`documents/${doc.version_id}/pages/${page}`)
      .then((d) => {
        if (active) setContent(d);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [doc.version_id, page]);
  useEffect(() => {
    const handler = (e) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);
  return (
    <div className="drawer-overlay" onClick={onClose}>
      <aside
        className="drawer"
        role="dialog"
        aria-modal="true"
        aria-label="Đọc tài liệu"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="drawer-heading">
          <Badge tone="green">NGUỒN BẰNG CHỨNG</Badge>
          <button
            autoFocus
            className="icon-button"
            aria-label="Đóng tài liệu"
            onClick={onClose}
          >
            <X size={20} />
          </button>
        </div>
        <div className="drawer-title">
          <DocLogo ticker={doc.ticker} />
          <div>
            <h2>{shortTitle(doc)}</h2>
            <p>
              {doc.ticker} · {doc.reporting_period || "Chưa ghi kỳ"}
            </p>
          </div>
        </div>
        <div className="source-meta">
          <span>
            Thu thập <strong>{when(doc.retrieved_at)}</strong>
          </span>
          <a href={doc.source_url} target="_blank" rel="noreferrer">
            PDF nguồn <ExternalLink size={13} />
          </a>
        </div>
        {doc.quarantine_reasons.length > 0 && (
          <Notice>
            <strong>Chưa đủ điều kiện lịch sử.</strong>
            <br />
            {doc.quarantine_reasons.map((r) => REASONS[r] || r).join("; ")}.
          </Notice>
        )}
        <div className="page-control">
          <span>Văn bản trích xuất · chưa OCR</span>
          <div>
            <button
              className="icon-button"
              disabled={page === 1}
              aria-label="Trang trước"
              onClick={() => setPage(page - 1)}
            >
              <ChevronLeft size={16} />
            </button>
            <input
              aria-label="Số trang"
              type="number"
              min="1"
              max={doc.pages}
              value={page}
              onChange={(e) =>
                setPage(
                  Math.min(doc.pages, Math.max(1, Number(e.target.value) || 1)),
                )
              }
            />
            <span>/ {doc.pages}</span>
            <button
              className="icon-button"
              disabled={page === doc.pages}
              aria-label="Trang sau"
              onClick={() => setPage(page + 1)}
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
        {error ? (
          <Notice tone="error">{error}</Notice>
        ) : !content ? (
          <div className="loading">
            <Loader2 className="spin" /> Đang mở trang…
          </div>
        ) : content.text.trim() ? (
          <pre className="page-text">{content.text}</pre>
        ) : (
          <Empty title="Trang chưa có lớp văn bản" icon={FileText}>
            Trang này cần OCR hoặc kiểm tra trực tiếp trong PDF nguồn.
          </Empty>
        )}
        <details className="audit-details">
          <summary>Định danh và toàn vẹn dữ liệu</summary>
          <dl>
            <dt>SHA-256 tài liệu</dt>
            <dd>{doc.content_hash}</dd>
            <dt>Version ID</dt>
            <dd>{doc.version_id}</dd>
            <dt>SHA-256 văn bản trang</dt>
            <dd>{content?.text_hash || "—"}</dd>
          </dl>
        </details>
      </aside>
    </div>
  );
}
function Analysis({ ticker, initialQuery }) {
  const [query, setQuery] = useState(
    initialQuery || "doanh thu lợi nhuận năm 2024",
  );
  const [mode, setMode] = useState("exploratory_current");
  const [cutoff, setCutoff] = useState("2025-04-01T16:00");
  const [search, setSearch] = useState(null),
    [payload, setPayload] = useState(null),
    [selected, setSelected] = useState(0);
  const [result, setResult] = useState(null),
    [busy, setBusy] = useState(""),
    [error, setError] = useState("");
  const reset = () => {
    setSearch(null);
    setPayload(null);
    setResult(null);
    setError("");
  };
  useEffect(reset, [ticker]);
  async function find(e) {
    e.preventDefault();
    setBusy("search");
    setError("");
    setResult(null);
    setSearch(null);
    const body = {
      query,
      ticker: ticker === "all" ? null : ticker,
      mode,
      decision_at: mode === "strict_point_in_time" ? `${cutoff}+07:00` : null,
    };
    try {
      const data = await api("search", body);
      setSearch(data);
      setPayload(body);
      setSelected(0);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  }
  async function extract() {
    const hit = search.passages[selected];
    setBusy("model");
    setError("");
    setResult(null);
    try {
      setResult(
        await api("analysis", {
          ...payload,
          version_id: hit.version_id,
          page: hit.page,
          start: hit.start,
        }),
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  }
  const hit = search?.passages[selected];
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Bàn phân tích tài liệu</h1>
          <p>
            Từ câu hỏi nghiên cứu đến đoạn nguồn và trích dẫn được đối chiếu.
          </p>
        </div>
        <Badge tone="green">
          <Zap size={12} /> LOCAL INFERENCE
        </Badge>
      </div>
      <div className="analysis-steps">
        <span className="active">
          01 <b>Tìm bằng chứng</b>
        </span>
        <ChevronRight size={15} />
        <span className={hit ? "active" : ""}>
          02 <b>Đọc đoạn nguồn</b>
        </span>
        <ChevronRight size={15} />
        <span className={result ? "active" : ""}>
          03 <b>Trích xuất & kiểm chứng</b>
        </span>
      </div>
      <Panel
        title="Bạn muốn tìm hiểu điều gì?"
        subtitle="Truy xuất từ kho tài liệu tại máy, không tìm kiếm trên Internet."
      >
        <form onSubmit={find} className="analysis-form">
          <label className="query-input">
            <Search size={20} />
            <input
              aria-label="Câu hỏi nghiên cứu"
              value={query}
              disabled={!!busy}
              maxLength={300}
              minLength={2}
              required
              placeholder="Ví dụ: doanh thu và lợi nhuận năm 2024"
              onChange={(e) => {
                setQuery(e.target.value);
                reset();
              }}
            />
            <button className="button primary" disabled={!!busy}>
              {busy === "search" ? (
                <Loader2 className="spin" size={16} />
              ) : (
                <Search size={16} />
              )}
              Tìm bằng chứng
            </button>
          </label>
          <div className="analysis-options">
            <label>
              Phạm vi thời gian
              <select
                aria-label="Chế độ thời gian"
                value={mode}
                disabled={!!busy}
                onChange={(e) => {
                  setMode(e.target.value);
                  reset();
                }}
              >
                <option value="exploratory_current">
                  Đọc tài liệu hiện tại
                </option>
                <option value="strict_point_in_time">
                  Point-in-Time · strict
                </option>
              </select>
            </label>
            {mode === "strict_point_in_time" && (
              <label>
                Mốc quyết định · giờ Việt Nam
                <input
                  type="datetime-local"
                  aria-label="Mốc quyết định"
                  value={cutoff}
                  disabled={!!busy}
                  required
                  onChange={(e) => {
                    setCutoff(e.target.value);
                    reset();
                  }}
                />
              </label>
            )}
            <span className="analysis-scope">
              <Database size={14} />{" "}
              {ticker === "all" ? "Toàn bộ doanh nghiệp" : ticker} · BM25
            </span>
          </div>
        </form>
      </Panel>
      <Notice tone={mode === "strict_point_in_time" ? "green" : "amber"}>
        {mode === "strict_point_in_time"
          ? "Chỉ tài liệu được gateway cho phép tại mốc quyết định mới đi vào truy xuất và thống kê corpus. Thiếu bằng chứng lịch sử sẽ không gọi mô hình."
          : "Chế độ khám phá nội dung hiện tại. Kết quả không phải phân tích tại thời điểm lịch sử; chưa sinh dự báo hoặc khuyến nghị giao dịch."}
      </Notice>
      {error && <Notice tone="error">{error}</Notice>}
      {!search && !busy && (
        <Empty title="Mỗi nhận định bắt đầu từ một nguồn" icon={FileCheck2}>
          Nhập nội dung cần tìm để xem các đoạn phù hợp, đọc nguồn và chạy trích
          xuất bằng mô hình local.
        </Empty>
      )}
      {search && !hit && (
        <Panel
          title={
            mode === "strict_point_in_time"
              ? "Không có bằng chứng đủ điều kiện tại mốc này"
              : "Không tìm thấy đoạn phù hợp"
          }
        >
          <Empty
            title={
              mode === "strict_point_in_time"
                ? "Dừng trước khi gọi mô hình"
                : "Thử một câu hỏi khác"
            }
            icon={ShieldCheck}
          >
            {mode === "strict_point_in_time"
              ? "Gateway đã giữ tài liệu chưa đủ bằng chứng lịch sử ngoài corpus. Không dùng tài liệu hiện tại để thay thế."
              : "Tìm theo chỉ tiêu, kỳ báo cáo hoặc đổi mã cổ phiếu."}
          </Empty>
          {!!search.gateway_audit.length && (
            <details className="audit-details">
              <summary>Xem lý do từ gateway</summary>
              <pre>{JSON.stringify(search.gateway_audit, null, 2)}</pre>
            </details>
          )}
        </Panel>
      )}
      {hit && (
        <div className="analysis-grid">
          <Panel
            title={`${search.passages.length} đoạn liên quan`}
            subtitle="Điểm BM25 phản ánh độ liên quan, không phải độ tin cậy."
          >
            <div className="passage-list">
              {search.passages.map((p, i) => (
                <button
                  key={`${p.version_id}-${p.page}-${p.start}`}
                  disabled={!!busy}
                  className={`passage-item ${selected === i ? "selected" : ""}`}
                  onClick={() => {
                    setSelected(i);
                    setResult(null);
                  }}
                >
                  <div>
                    <Badge tone="green">{p.ticker}</Badge>
                    <span>Trang {p.page}</span>
                    <small>#{i + 1}</small>
                  </div>
                  <strong>{p.record_id}</strong>
                  <p>{p.text.slice(0, 160)}…</p>
                </button>
              ))}
            </div>
          </Panel>
          <Panel
            title={`${hit.ticker} · Trang ${hit.page}`}
            subtitle={`${hit.record_id} · ký tự ${hit.start}–${hit.end}`}
            action={<Badge>ĐOẠN NGUYÊN VĂN</Badge>}
          >
            <pre className="passage-text">{hit.text}</pre>
            <div className="extract-action">
              <span>
                <LockKeyhole size={14} /> Chỉ đoạn này được gửi tới Ollama
                local.
              </span>
              <button
                className="button primary"
                onClick={extract}
                disabled={!!busy}
              >
                {busy === "model" ? (
                  <Loader2 className="spin" size={16} />
                ) : (
                  <Sparkles size={16} />
                )}
                {busy === "model"
                  ? "Đang trích xuất…"
                  : "Trích xuất & kiểm chứng"}
              </button>
            </div>
            {busy === "model" && (
              <p className="footnote">
                Lần đầu có thể lâu hơn do nạp mô hình. Chờ yêu cầu hoàn tất
                trước khi chạy tiếp.
              </p>
            )}
            {result && <ExtractionResult result={result} />}
          </Panel>
        </div>
      )}
    </>
  );
}
function ExtractionResult({ result }) {
  const accepted = result.status === "verified_quote",
    output = result.generation?.output;
  const reasons = {
    generation_failed: "Mô hình không trả được đầu ra hợp lệ.",
    model_abstained: "Mô hình từ chối trích xuất vì thiếu bằng chứng.",
    model_changed: "Định danh mô hình thay đổi trong lần chạy.",
    quote_not_found: "Không tìm thấy trích dẫn nguyên văn trong đoạn nguồn.",
    quote_ambiguous:
      "Trích dẫn xuất hiện nhiều lần, chưa xác định được vị trí duy nhất.",
    quote_empty: "Đầu ra không có trích dẫn để đối chiếu.",
    numbers_not_supported: "Có chuỗi số không khớp với trích dẫn nguồn.",
  };
  function download() {
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(result, null, 2)], { type: "application/json" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = `${result.run_id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }
  return (
    <div className="extraction-result">
      <div className="result-heading">
        <h3>
          <ShieldCheck size={18} />
          Kết quả đối chiếu nguồn
        </h3>
        <Badge tone={accepted ? "green" : "amber"}>
          {accepted
            ? "Trích dẫn khớp nguồn"
            : result.status === "failed"
              ? "Không chạy được"
              : "Bị chặn"}
        </Badge>
      </div>
      {accepted ? (
        <>
          <blockquote>{result.verification.quote.source_quote}</blockquote>
          <div className="numbers">
            {output.extracted_numbers.map((n, i) => (
              <Badge key={i}>{n}</Badge>
            ))}
          </div>
          <p className="summary-label">
            Tóm tắt của mô hình · chưa duyệt ngữ nghĩa
          </p>
          <p className="model-summary">{output.summary}</p>
          <Notice tone="green">
            Đã đối chiếu trích dẫn và chuỗi số với đoạn nguồn. Việc khớp chuỗi
            chưa chứng minh toàn bộ diễn giải của mô hình là đúng.
          </Notice>
        </>
      ) : (
        <Notice>
          {result.error ||
            result.block_reasons?.map((r) => reasons[r] || r).join(" ") ||
            "Đầu ra chưa vượt qua kiểm tra trích dẫn, số liệu hoặc định danh mô hình."}
          <br />
          Không dùng tóm tắt này làm bằng chứng đã xác minh.
        </Notice>
      )}
      <div className="trace-row">
        <span>
          <Clock3 size={13} />{" "}
          {result.generation
            ? `${result.generation.wall_seconds.toFixed(1)} giây`
            : "Chưa có inference"}{" "}
          · {result.run_id}
        </span>
        <button className="text-button" onClick={download}>
          <Download size={14} />
          Tải dấu vết
        </button>
      </div>
      <details className="audit-details">
        <summary>Đầu ra thô, nguồn và kiểm tra chi tiết</summary>
        <pre>{JSON.stringify(result, null, 2)}</pre>
      </details>
    </div>
  );
}
function PriceChart({ rows, unit = "VND", id = "price", title }) {
  const [hover, setHover] = useState(null);
  const values = rows.map((r) => r.close),
    min = Math.min(...values),
    max = Math.max(...values);
  const low = min - (max - min || max * 0.01) * 0.12,
    high = max + (max - min || max * 0.01) * 0.12;
  const x = (i) => 65 + (i / Math.max(1, rows.length - 1)) * 805,
    y = (v) => 240 - ((v - low) / (high - low)) * 210;
  const path = rows
    .map((r, i) => `${i ? "L" : "M"}${x(i)},${y(r.close)}`)
    .join(" ");
  const selected = hover == null ? rows.length - 1 : hover;
  return (
    <div className="price-chart">
      <div className="chart-top">
        <span>{title}</span>
        <strong>
          {fmt(rows[selected].close)} <small>{unit}</small>
          <em>{when(rows[selected].session_date)}</em>
        </strong>
      </div>
      <svg
        viewBox="0 0 900 285"
        role="img"
        aria-label={`Biểu đồ giá ${title}`}
        onMouseLeave={() => setHover(null)}
        onMouseMove={(e) => {
          const r = e.currentTarget.getBoundingClientRect();
          setHover(
            Math.min(
              rows.length - 1,
              Math.max(
                0,
                Math.round(
                  ((((e.clientX - r.left) / r.width) * 900 - 65) / 805) *
                    (rows.length - 1),
                ),
              ),
            ),
          );
        }}
      >
        <defs>
          <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#238568" stopOpacity=".16" />
            <stop offset="1" stopColor="#238568" stopOpacity="0" />
          </linearGradient>
        </defs>
        {[0, 1, 2, 3, 4].map((i) => {
          const v = low + ((high - low) * i) / 4;
          return (
            <g key={i}>
              <line
                x1="65"
                x2="870"
                y1={y(v)}
                y2={y(v)}
                stroke="#e9eeec"
                strokeDasharray="4 4"
              />
              <text x="53" y={y(v) + 4} textAnchor="end">
                {fmt(Math.round(v))}
              </text>
            </g>
          );
        })}
        <path d={`${path} L870,240 L65,240 Z`} fill={`url(#${id})`} />
        <path d={path} fill="none" stroke="#228265" strokeWidth="2.5" />
        {[0, Math.floor((rows.length - 1) / 2), rows.length - 1]
          .filter((v, i, a) => a.indexOf(v) === i)
          .map((i) => (
            <text key={i} x={x(i)} y="270" textAnchor="middle">
              {when(rows[i].session_date)}
            </text>
          ))}
        {hover != null && (
          <g>
            <line
              x1={x(hover)}
              x2={x(hover)}
              y1="25"
              y2="240"
              stroke="#75988c"
              strokeDasharray="4 4"
            />
            <circle
              cx={x(hover)}
              cy={y(rows[hover].close)}
              r="5"
              fill="#228265"
              stroke="white"
              strokeWidth="2"
            />
          </g>
        )}
      </svg>
    </div>
  );
}
function Market({ ticker }) {
  const [symbol, setSymbol] = useState(ticker === "all" ? "FPT" : ticker),
    [start, setStart] = useState("2024-01-01"),
    [end, setEnd] = useState("2024-06-30");
  const [index, setIndex] = useState(false),
    [result, setResult] = useState(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    if (ticker !== "all") setSymbol(ticker);
    setResult(null);
  }, [ticker]);
  async function load(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setResult(null);
    try {
      setResult(
        await api(
          `market?${new URLSearchParams({ ticker: symbol, start, end, include_index: index })}`,
        ),
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  const rows = result?.prices || [],
    change = rows.length ? (rows.at(-1).close / rows[0].close - 1) * 100 : null;
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Dữ liệu thị trường</h1>
          <p>Quan sát chuỗi giá Việt Nam từ Vnstock / KBS.</p>
        </div>
        <Badge>OHLCV · VND</Badge>
      </div>
      <Panel title="Khoảng thời gian quan sát">
        <form className="market-form" onSubmit={load}>
          <label>
            Mã cổ phiếu
            <input
              aria-label="Mã cổ phiếu"
              required
              pattern="[A-Z0-9]{2,12}"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            />
          </label>
          <label>
            Từ ngày
            <input
              aria-label="Ngày bắt đầu"
              type="date"
              required
              value={start}
              onChange={(e) => setStart(e.target.value)}
            />
          </label>
          <label>
            Đến ngày
            <input
              aria-label="Ngày kết thúc"
              type="date"
              required
              value={end}
              max={new Date(Date.now() - 86400000).toISOString().slice(0, 10)}
              onChange={(e) => setEnd(e.target.value)}
            />
          </label>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={index}
              onChange={(e) => setIndex(e.target.checked)}
            />{" "}
            Xem VNINDEX
          </label>
          <button className="button primary" disabled={busy}>
            {busy ? (
              <Loader2 className="spin" size={16} />
            ) : (
              <Download size={16} />
            )}
            Tải dữ liệu
          </button>
        </form>
      </Panel>
      <Notice>
        Giá chưa được xác minh lịch sử điều chỉnh và thời điểm khả dụng. Đây là
        biểu đồ quan sát, chưa phải dữ liệu PiT strict hoặc kết quả backtest.
      </Notice>
      {error && <Notice tone="error">{error}</Notice>}
      {!rows.length && !busy && !error && (
        <Empty title="Khám phá diễn biến thị trường" icon={BarChart3}>
          Chọn cổ phiếu và khoảng ngày rồi tải dữ liệu. Không tự tải khi mở
          trang.
        </Empty>
      )}
      {rows.length > 0 && (
        <>
          <div className="stats-grid">
            <Stat
              label="Mã quan sát"
              value={result.ticker}
              note="Cổ phiếu Việt Nam"
              icon={Activity}
            />
            <Stat
              label="Số phiên"
              value={rows.length}
              note={`${when(rows[0].session_date)} — ${when(rows.at(-1).session_date)}`}
              icon={Clock3}
              tone="blue"
            />
            <Stat
              label="Giá đóng cửa cuối"
              value={fmt(rows.at(-1).close)}
              note="VND / cổ phiếu"
              icon={BarChart3}
            />
            <Stat
              label="Thay đổi giá đầu/cuối"
              value={`${change >= 0 ? "+" : ""}${change.toFixed(2)}%`}
              note="Chưa tính phí, cổ tức hoặc slippage"
              icon={change >= 0 ? ArrowUpRight : ArrowDownRight}
              tone="amber"
            />
          </div>
          <Panel
            title={`Giá đóng cửa ${result.ticker}`}
            subtitle="Di chuột lên biểu đồ để xem từng phiên"
          >
            <PriceChart rows={rows} title={result.ticker} />
          </Panel>
          {result.index && (
            <Panel
              title="VNINDEX"
              subtitle="Điểm chỉ số; hai chuỗi chưa căn chỉnh để tính relative return"
            >
              <PriceChart
                rows={result.index}
                title="VNINDEX"
                unit="điểm"
                id="index-price"
              />
            </Panel>
          )}
          {result.index_error && (
            <Notice tone="error">
              Không tải được VNINDEX: {result.index_error}
            </Notice>
          )}
          <details className="audit-details">
            <summary>Dữ liệu và metadata nguồn</summary>
            <pre>{JSON.stringify(result, null, 2)}</pre>
          </details>
        </>
      )}
    </>
  );
}
function Experiments({ pilot }) {
  const m = pilot?.metrics,
    r = pilot?.replay;
  if (!m)
    return (
      <Empty title="Chưa có pilot hoàn tất" icon={FlaskConical}>
        Chạy pilot trên tài liệu thật để xem các chỉ số tại đây.
      </Empty>
    );
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Thực nghiệm & kiểm chứng</h1>
          <p>
            Kết quả từ artifact đã lưu. Mẫu thất bại vẫn được giữ trong mẫu số.
          </p>
        </div>
        <Badge tone="green">PILOT TRÍCH XUẤT</Badge>
      </div>
      <Notice>
        Đây là pilot phát triển trên {m.sample_denominator} đoạn từ{" "}
        {pilot.document_count} tài liệu. Chưa có nhãn độc lập cho số liệu/ngữ
        nghĩa, chưa đánh giá dự báo hoặc backtest.
      </Notice>
      <div className="stats-grid">
        <Stat
          label="JSON hợp lệ"
          value={`${m.schema_valid_samples}/${m.sample_denominator}`}
          note="Đầu ra đúng schema"
          icon={CheckCheck}
        />
        <Stat
          label="Trích xuất qua kiểm tra strict"
          value={`${m.accepted_extractions}/${m.sample_denominator}`}
          note="Trích dẫn và chuỗi số nguyên văn"
          icon={FileCheck2}
          tone="blue"
        />
        <Stat
          label="Sau ánh xạ khoảng trắng"
          value={r ? `${r.mapped_accepted}/${r.sample_denominator}` : "—"}
          note="Replay offline; không gọi lại mô hình"
          icon={ShieldCheck}
        />
        <Stat
          label="Độ trễ trung vị"
          value={`${m.median_sample_wall_seconds.toFixed(1)}s`}
          note={`p95: ${m.p95_sample_wall_seconds_nearest_rank.toFixed(1)} giây`}
          icon={Clock3}
          tone="amber"
        />
      </div>
      <div className="grid-two">
        <Panel
          title="Đối chiếu trích dẫn"
          subtitle="Chỉ ánh xạ khoảng trắng; không sửa số hoặc nội dung"
        >
          <Quality pilot={pilot} />
        </Panel>
        <Panel
          title="Cấu hình lần chạy"
          subtitle="Định danh mô hình được kiểm tra trước và sau inference"
        >
          <dl className="config-list">
            {[
              ["Model", pilot.manifest.config.model],
              ["Context", `${pilot.manifest.config.num_ctx} tokens`],
              [
                "Temperature / seed",
                `${pilot.manifest.config.temperature} / ${pilot.manifest.config.seed}`,
              ],
              ["Thời gian", when(pilot.manifest.created_at)],
              [
                "Model digest",
                pilot.manifest.model_before.digest.slice(0, 20) + "…",
              ],
              [
                "Định danh sau chạy",
                pilot.manifest.model_digest_stable
                  ? "Không thay đổi"
                  : "Cần kiểm tra",
              ],
            ].map(([k, v]) => (
              <div key={k}>
                <dt>{k}</dt>
                <dd>{v}</dd>
              </div>
            ))}
          </dl>
        </Panel>
      </div>
      <Panel
        title="Những gì kết quả này chưa chứng minh"
        subtitle="Giới hạn cần giữ khi viết và bảo vệ khóa luận"
      >
        <div className="limitations-grid">
          {[
            [
              BookOpen,
              "Tính đúng của diễn giải",
              "Trích dẫn khớp nguồn chưa đủ chứng minh tóm tắt đúng ngữ nghĩa.",
            ],
            [
              Clock3,
              "Tính khả dụng lịch sử",
              "Thời điểm tải không thay thế thời điểm công bố và bằng chứng phiên bản.",
            ],
            [
              Activity,
              "Hiệu quả đầu tư",
              "Chưa có kết quả dự báo hướng giá, lợi suất danh mục hoặc đối chứng backtest.",
            ],
          ].map(([I, t, d]) => (
            <div key={t}>
              <Icon icon={I} size={22} />
              <h3>{t}</h3>
              <p>{d}</p>
            </div>
          ))}
        </div>
      </Panel>
      <details className="audit-details">
        <summary>Xem artifact và chỉ số đầy đủ</summary>
        <p>{pilot.path}</p>
        <pre>{JSON.stringify(pilot, null, 2)}</pre>
      </details>
    </>
  );
}
function App() {
  const [tab, setTab] = useState(window.location.hash.slice(1) || "overview");
  const [data, setData] = useState(null),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(false);
  const [ticker, setTicker] = useState("all"),
    [model, setModel] = useState(null),
    [drawer, setDrawer] = useState(null);
  const [topQuery, setTopQuery] = useState(""),
    [analysisQuery, setAnalysisQuery] = useState(""),
    [mobile, setMobile] = useState(false);
  async function refresh() {
    setLoading(true);
    setError("");
    try {
      setData(await api("workspace"));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }
  async function checkModel() {
    setModel(null);
    try {
      setModel(await api("model"));
    } catch (e) {
      setModel({ connected: false, error: e.message });
    }
  }
  useEffect(() => {
    refresh();
    checkModel();
  }, []);
  useEffect(() => {
    const handler = () => {
      setTab(window.location.hash.slice(1) || "overview");
      setMobile(false);
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", handler);
    return () => window.removeEventListener("hashchange", handler);
  }, []);
  const current = NAV.find((n) => n[0] === tab) || NAV[0];
  const docs = (data?.documents || []).filter(
    (d) => ticker === "all" || d.ticker === ticker,
  );
  return (
    <div className="app-shell">
      <a
        className="skip-link"
        href="#workspace-content"
        onClick={(e) => {
          e.preventDefault();
          document.getElementById("workspace-content").focus();
        }}
      >
        Đến nội dung chính
      </a>
      {mobile && (
        <div className="mobile-overlay" onClick={() => setMobile(false)} />
      )}
      <aside id="sidebar-nav" className={`sidebar ${mobile ? "open" : ""}`}>
        <a href="#overview" className="brand">
          <span className="brand-mark">
            <i />
            <i />
            <i />
          </span>
          <span>
            PiT-HAF<small>RESEARCH WORKSPACE</small>
          </span>
        </a>
        <div className="workspace-tag">
          <span className="live-dot" /> Vietnam equities <Badge>LOCAL</Badge>
        </div>
        <div className="nav-label">KHÔNG GIAN LÀM VIỆC</div>
        <nav aria-label="Điều hướng chính">
          {NAV.map(([key, label, I]) => (
            <button
              key={key}
              className={`nav-item ${current[0] === key ? "active" : ""}`}
              onClick={() => {
                navTo(key);
                setMobile(false);
              }}
              aria-current={current[0] === key ? "page" : undefined}
            >
              <Icon icon={I} size={19} />
              <span>{label}</span>
              {key === "documents" && data && (
                <small>{data.documents.length}</small>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-filter">
          <div className="nav-label">PHẠM VI NGHIÊN CỨU</div>
          <label className="sr-only" htmlFor="ticker-filter">
            Phạm vi doanh nghiệp
          </label>
          <select
            id="ticker-filter"
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
          >
            <option value="all">Tất cả doanh nghiệp</option>
            {[...new Set((data?.documents || []).map((d) => d.ticker))]
              .sort()
              .map((t) => (
                <option key={t}>{t}</option>
              ))}
          </select>
          <p>Nguồn bằng chứng tại máy của bạn.</p>
        </div>
        <div className="sidebar-bottom">
          <div className="local-card">
            <div>
              <span className="chip-icon">
                <Terminal size={17} />
              </span>
              <strong>Mô hình cục bộ</strong>
              <button
                className="icon-button"
                aria-label="Kiểm tra Ollama"
                onClick={checkModel}
              >
                <RefreshCw size={13} />
              </button>
            </div>
            <p>
              qwen3:4b <span>Q4_K_M</span>
            </p>
            <small>
              <i
                className={`dot ${model?.connected && model?.installed ? "green" : model ? "amber" : "light"}`}
              />
              {model
                ? model.connected && model.installed
                  ? "Ollama đã kết nối"
                  : model.connected
                    ? "Chưa có model"
                    : "Ollama chưa kết nối"
                : "Đang kiểm tra…"}
            </small>
          </div>
          <div className="sidebar-note">
            <ShieldCheck size={15} />
            <span>
              Nghiên cứu có thể kiểm tra.
              <br />
              Mỗi nhận định, một nguồn.
            </span>
          </div>
          <div className="sidebar-footer">
            PiT-HAF <span>v0.1 · Development</span>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="icon-button mobile-menu"
              aria-label="Mở menu"
              aria-expanded={mobile}
              aria-controls="sidebar-nav"
              onClick={() => setMobile(!mobile)}
            >
              <Menu size={20} />
            </button>
            <span>Không gian nghiên cứu</span>
            <ChevronRight size={14} />
            <strong>{current[1]}</strong>
          </div>
          <form
            className="top-search"
            onSubmit={(e) => {
              e.preventDefault();
              if (topQuery.trim()) {
                setAnalysisQuery(topQuery);
                navTo("analysis");
              }
            }}
          >
            <Search size={16} />
            <input
              aria-label="Tìm trong bằng chứng"
              placeholder="Tìm trong bằng chứng…"
              value={topQuery}
              onChange={(e) => setTopQuery(e.target.value)}
            />
            <kbd>↵</kbd>
          </form>
          <div className="topbar-end">
            <span className="local-indicator">
              <span className="live-dot" /> Local workspace
            </span>
            <button
              className={`icon-button ${loading ? "spin" : ""}`}
              aria-label="Làm mới dữ liệu"
              disabled={loading}
              onClick={refresh}
            >
              <RefreshCw size={17} />
            </button>
            <span className="avatar">P</span>
          </div>
        </header>
        <main id="workspace-content" tabIndex={-1}>
          <div className="section-eyebrow">
            {current[0] === "overview"
              ? "TỔNG QUAN NGHIÊN CỨU"
              : "PIT-HAF / VIETNAM EQUITIES"}
            <span>
              <Clock3 size={12} />{" "}
              {new Date().toLocaleDateString("vi-VN", {
                day: "2-digit",
                month: "long",
                year: "numeric",
              })}
            </span>
          </div>
          {error && (
            <Notice tone="error">
              Không tải được workspace: {error}{" "}
              <button className="text-button" onClick={refresh}>
                Thử lại
              </button>
            </Notice>
          )}
          {!data && !error && (
            <div className="loading initial">
              <Loader2 className="spin" size={25} />
              Đang mở không gian nghiên cứu…
            </div>
          )}
          {data?.errors.map((e, i) => (
            <Notice tone="error" key={i}>
              {e}
            </Notice>
          ))}
          {data && (
            <>
              {current[0] === "overview" && (
                <Overview data={data} docs={docs} onOpen={setDrawer} />
              )}
              {current[0] === "documents" && (
                <Documents docs={docs} onOpen={setDrawer} />
              )}
              {current[0] === "analysis" && (
                <Analysis
                  key={analysisQuery}
                  ticker={ticker}
                  initialQuery={analysisQuery}
                />
              )}
              {current[0] === "market" && <Market ticker={ticker} />}
              {current[0] === "experiments" && (
                <Experiments pilot={data.pilot} />
              )}
            </>
          )}
          <footer className="content-footer">
            <span>PiT-HAF · Point-in-Time Hierarchical Agentic Framework</span>
            <span>
              <LockKeyhole size={12} /> Dữ liệu & xử lý tại máy
            </span>
          </footer>
        </main>
      </div>
      {drawer && (
        <DocumentDrawer
          key={drawer.version_id}
          doc={drawer}
          onClose={() => setDrawer(null)}
        />
      )}
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
