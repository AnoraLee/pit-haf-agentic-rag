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
import CaseReview from "./CaseReview";
import DevelopmentEvaluation from "./DevelopmentEvaluation";
import TableEvidence from "./TableEvidence";

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
  news_article: "Bài báo",
  issuer_news: "Tin doanh nghiệp tự công bố",
  official_policy_news: "Tin chính sách / vĩ mô",
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
const isArticleDoc = (d) =>
  d.media_type === "text/html" || d.origin === "dataset_mirror";
const shortTitle = (d) =>
  isArticleDoc(d)
    ? d.title
    : `${d.ticker} · ${TYPES[d.document_type] || "Công bố doanh nghiệp"} ${d.reporting_period || ""}${/Vietnamese/i.test(d.title) ? " · Tiếng Việt" : ""}`;
const entityLabel = (d) =>
  d.ticker === "MARKET"
    ? "Thị trường / vĩ mô"
    : d.related_tickers?.length
      ? d.related_tickers.join(", ")
      : d.ticker;

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
            {!compact && <th>NGÀY ĐĂNG / KỲ BÁO CÁO</th>}
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
                      {entityLabel(d)} <span>·</span>{" "}
                      {TYPES[d.document_type] || "Công bố doanh nghiệp"}
                      {d.publisher && <> · {d.publisher}</>}
                      {d.origin === "dataset_mirror" && (
                        <> · Bản nhập dataset</>
                      )}
                    </small>
                  </span>
                </button>
              </td>
              {!compact && (
                <td>
                  {isArticleDoc(d)
                    ? when(d.publication_date)
                    : d.reporting_period || "—"}
                </td>
              )}
              <td>
                <strong className="normal">
                  {d.text_pages}/{d.pages}
                </strong>
                <small>
                  {isArticleDoc(d)
                    ? "mục nội dung bài viết"
                    : "trang PDF có văn bản"}
                </small>
                {(d.potentially_partial_text_pages?.length > 0 ||
                  d.potentially_partial_document) && (
                  <small className="parser-warning">
                    Có trang trích xuất thiếu
                  </small>
                )}
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
function Coverage({ docs, summaryRows }) {
  const rows =
    summaryRows ||
    [...new Set(docs.map((d) => d.ticker))].map((ticker) => {
      const selected = docs.filter((d) => d.ticker === ticker);
      return {
        ticker,
        documents: selected.length,
        with_text: selected.filter((d) => d.text_pages > 0).length,
      };
    });
  const max = Math.max(1, ...rows.map((r) => r.documents));
  return (
    <div className="coverage">
      {rows.map(({ ticker, documents: pages, with_text: text }) => {
        return (
          <div className="coverage-row" key={ticker}>
            <div className="coverage-label">
              <DocLogo ticker={ticker} />
              <span>
                <strong>{ticker === "MARKET" ? "Thị trường" : ticker}</strong>
                <small>{fmt(pages)} tài liệu</small>
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
              {fmt(pages)} <small>tài liệu</small>
            </span>
          </div>
        );
      })}
      <div className="legend">
        <span>
          <i className="dot green" /> Có lớp văn bản
        </span>
        <span>
          <i className="dot light" /> Chưa có văn bản
        </span>
      </div>
      {summaryRows && (
        <p className="footnote">Một bài có thể liên quan nhiều mã cổ phiếu.</p>
      )}
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
  const pdfs = docs.filter((d) => !isArticleDoc(d));
  const stats = data.catalog?.scope_stats;
  const total = stats?.documents ?? docs.length;
  const articles = stats?.articles ?? docs.length - pdfs.length;
  const pages = stats?.pdf_pages ?? pdfs.reduce((n, d) => n + d.pages, 0),
    text = stats?.pdf_text_pages ?? pdfs.reduce((n, d) => n + d.text_pages, 0);
  const eligible = stats
    ? total - (stats.quarantined || 0)
    : docs.filter((d) => !d.quarantine_reasons.length).length;
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
          value={fmt(total)}
          note={`${fmt(stats?.pdf_documents ?? pdfs.length)} PDF · ${fmt(articles)} bài viết`}
          icon={FolderOpen}
        />
        <Stat
          label="Trang PDF đã thu thập"
          value={fmt(pages)}
          note="Snapshot gốc được kiểm tra SHA-256"
          icon={FileText}
          tone="blue"
        />
        <Stat
          label="Trang PDF có văn bản"
          value={fmt(text)}
          note={`${fmt(pages - text)} trang trống / chưa OCR`}
          icon={BookOpen}
          tone="violet"
        />
        <Stat
          label="Đủ điều kiện PiT strict"
          value={fmt(eligible)}
          note={`${fmt(total - eligible)} tài liệu cần xác minh lịch sử`}
          icon={ShieldCheck}
          tone="amber"
        />
      </div>
      <div className="grid-two">
        <Panel
          title="Độ bao phủ tài liệu"
          subtitle="Phân bố nội dung theo doanh nghiệp và thị trường"
          action={<Badge>LOCAL CORPUS</Badge>}
        >
          {docs.length ? (
            <Coverage
              docs={docs}
              summaryRows={
                data.catalog
                  ? data.catalog.scope_ticker === "all"
                    ? data.catalog.breakdown
                    : [{ ticker: data.catalog.scope_ticker, ...stats }]
                  : null
              }
            />
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
          subtitle="Báo cáo, báo chí và tin doanh nghiệp · đọc tại máy"
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
              [Database, "Kho bằng chứng", "PDF, bài báo và nguồn gốc"],
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
function AnnualCoverage({ coverage, ticker }) {
  if (!coverage) return null;
  const rows = coverage.issuers.filter(
    (row) =>
      row.entity_type !== "market_context" &&
      (ticker === "all" || row.ticker === ticker),
  );
  if (!rows.length) return null;
  const years = Object.keys(rows[0]?.annual_years || {});
  const covered = rows.reduce(
    (n, row) => n + Object.values(row.annual_years).filter(Boolean).length,
    0,
  );
  return (
    <Panel
      title="Độ bao phủ báo cáo thường niên"
      subtitle="Mỗi ô là một doanh nghiệp × năm. Bản dịch không được tính thêm một kỳ."
      action={
        <Badge tone="green">
          {covered}/{rows.length * years.length} kỳ
        </Badge>
      }
    >
      <div className="table-scroll">
        <table className="coverage-matrix">
          <thead>
            <tr>
              <th>DOANH NGHIỆP</th>
              <th>NHÓM NGÀNH</th>
              {years.map((y) => (
                <th key={y}>{y}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.ticker}>
                <td>
                  <strong>{row.ticker}</strong>
                </td>
                <td>{row.sector}</td>
                {years.map((y) => (
                  <td key={y}>
                    <span
                      className={
                        row.annual_years[y] ? "cell-present" : "cell-missing"
                      }
                    >
                      {row.annual_years[y] ? <CheckCheck size={14} /> : "—"}
                      <span>{row.annual_years[y] ? "Đã có" : "Còn thiếu"}</span>
                    </span>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="footnote">
        Độ phủ tài liệu chưa chứng minh đủ điều kiện Point-in-Time. Nhóm ngành
        được gán thủ công; universe lịch sử và survivorship bias chưa được xác
        minh.
      </p>
    </Panel>
  );
}

function Documents({ docs, onOpen, coverage, ticker, catalog }) {
  const [query, setQuery] = useState(""),
    [type, setType] = useState("all"),
    [year, setYear] = useState("all"),
    [scope, setScope] = useState("all"),
    [publisher, setPublisher] = useState("all"),
    [origin, setOrigin] = useState("all"),
    [page, setPage] = useState(1);
  const [remote, setRemote] = useState(null),
    [busy, setBusy] = useState(false),
    [failure, setFailure] = useState("");
  useEffect(() => setPage(1), [ticker, docs.length]);
  useEffect(() => {
    if (!catalog) return;
    let active = true;
    setBusy(true);
    setFailure("");
    const timer = setTimeout(() => {
      const params = new URLSearchParams({
        offset: String((page - 1) * 20),
        limit: "20",
        q: query,
        ticker,
        kind: type,
        year,
        scope,
        publisher,
        origin,
      });
      api(`catalog/documents?${params}`)
        .then((r) => {
          if (active) setRemote(r);
        })
        .catch((e) => {
          if (active) setFailure(e.message);
        })
        .finally(() => {
          if (active) setBusy(false);
        });
    }, 200);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [
    Boolean(catalog),
    ticker,
    query,
    type,
    year,
    scope,
    publisher,
    origin,
    page,
  ]);
  const localFiltered = docs
    .filter(
      (d) =>
        `${d.title} ${d.ticker} ${d.related_tickers?.join(" ") || ""} ${d.publisher || ""} ${d.reporting_period}`
          .toLowerCase()
          .includes(query.toLowerCase()) &&
        (type === "all" || d.document_type === type) &&
        (year === "all" || d.reporting_period?.startsWith(year)) &&
        (scope === "all" || d.statement_scope === scope) &&
        (publisher === "all" ||
          (d.publisher || "Báo cáo doanh nghiệp") === publisher),
    )
    .sort(
      (a, b) =>
        (
          b.publication_date ||
          b.reporting_period?.slice(0, 4) ||
          ""
        ).localeCompare(
          a.publication_date || a.reporting_period?.slice(0, 4) || "",
        ) ||
        (b.reporting_period || "").localeCompare(a.reporting_period || "") ||
        a.ticker.localeCompare(b.ticker) ||
        a.title.localeCompare(b.title),
    );
  const filtered = catalog ? remote?.documents || [] : localFiltered;
  const total = catalog ? remote?.total || 0 : filtered.length;
  const stats = remote?.stats || catalog?.scope_stats;
  const documentCount = stats?.documents ?? docs.length;
  const facets = catalog?.facets;
  const pageSize = 20;
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const currentPage = Math.min(page, pages);
  const start = (currentPage - 1) * pageSize;
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
          value={fmt(documentCount)}
          note={`${fmt(stats?.pdf_documents ?? docs.filter((d) => !isArticleDoc(d)).length)} PDF · ${fmt(stats?.articles ?? docs.filter(isArticleDoc).length)} bài viết`}
          icon={FileText}
        />
        <Stat
          label="Trang cần kiểm tra OCR"
          value={fmt(
            stats?.ocr_backlog ??
              docs
                .filter((d) => !isArticleDoc(d))
                .reduce((n, d) => n + d.pages - d.text_pages, 0),
          )}
          note="Chưa chạy OCR; không suy diễn nội dung"
          icon={BookOpen}
          tone="blue"
        />
        <Stat
          label="Cần xác minh PiT"
          value={fmt(
            stats?.quarantined ??
              docs.filter((d) => d.quarantine_reasons.length).length,
          )}
          note="Được giữ ngoài corpus lịch sử strict"
          icon={Clock3}
          tone="amber"
        />
      </div>
      <Panel
        title="Danh mục tài liệu"
        subtitle={`${fmt(total)} tài liệu phù hợp bộ lọc`}
        action={<Badge>{fmt(documentCount)} SNAPSHOTS</Badge>}
      >
        <div className="table-toolbar">
          <label className="input-with-icon">
            <Search size={17} />
            <input
              aria-label="Lọc tài liệu"
              placeholder="Tìm tên, mã cổ phiếu, kỳ báo cáo…"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setPage(1);
              }}
            />
          </label>
          <select
            aria-label="Loại tài liệu"
            value={type}
            onChange={(e) => {
              setType(e.target.value);
              setPage(1);
            }}
          >
            <option value="all">Tất cả loại tài liệu</option>
            {(
              facets?.types || [...new Set(docs.map((d) => d.document_type))]
            ).map((t) => (
              <option key={t} value={t}>
                {TYPES[t] || t}
              </option>
            ))}
          </select>
          <select
            aria-label="Năm tài liệu"
            value={year}
            onChange={(e) => {
              setYear(e.target.value);
              setPage(1);
            }}
          >
            <option value="all">Tất cả năm</option>
            {(
              facets?.years || [
                ...new Set(
                  docs
                    .map((d) => d.reporting_period?.slice(0, 4))
                    .filter(Boolean),
                ),
              ]
            )
              .sort()
              .reverse()
              .map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
          </select>
          <select
            aria-label="Phạm vi báo cáo"
            value={scope}
            onChange={(e) => {
              setScope(e.target.value);
              setPage(1);
            }}
          >
            <option value="all">Tất cả phạm vi</option>
            <option value="consolidated">Hợp nhất</option>
            <option value="parent">Công ty mẹ / riêng lẻ</option>
            <option value="unknown">Chưa xác định</option>
            <option value="not_applicable">Bài viết / không áp dụng</option>
          </select>
          <select
            aria-label="Nguồn đăng"
            value={publisher}
            onChange={(e) => {
              setPublisher(e.target.value);
              setPage(1);
            }}
          >
            <option value="all">Tất cả nguồn đăng</option>
            {(
              facets?.publishers || [
                ...new Set(
                  docs.map((d) => d.publisher || "Báo cáo doanh nghiệp"),
                ),
              ]
            )
              .sort()
              .map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
          </select>
          {catalog && (
            <select
              aria-label="Loại nguồn"
              value={origin}
              onChange={(e) => {
                setOrigin(e.target.value);
                setPage(1);
              }}
            >
              <option value="all">Tất cả cách thu thập</option>
              <option value="publisher_snapshot">Thu thập trực tiếp</option>
              <option value="dataset_mirror">Nhập từ dataset công khai</option>
            </select>
          )}
        </div>
        {failure && <Notice tone="error">{failure}</Notice>}
        {busy ? (
          <div className="loading">
            <Loader2 className="spin" /> Đang tìm tài liệu…
          </div>
        ) : filtered.length ? (
          <>
            <DocTable
              docs={
                catalog ? filtered : filtered.slice(start, start + pageSize)
              }
              onOpen={onOpen}
            />
            <nav
              className="document-pagination"
              aria-label="Phân trang tài liệu"
            >
              <span>
                {fmt(start + 1)}–{fmt(Math.min(start + pageSize, total))} /{" "}
                {fmt(total)} tài liệu
              </span>
              <div>
                <button
                  className="button secondary"
                  disabled={currentPage === 1}
                  onClick={() => setPage(currentPage - 1)}
                >
                  Trước
                </button>
                <span aria-live="polite">
                  Trang {currentPage}/{pages}
                </span>
                <button
                  className="button secondary"
                  disabled={currentPage === pages}
                  onClick={() => setPage(currentPage + 1)}
                >
                  Tiếp
                </button>
              </div>
            </nav>
          </>
        ) : (
          <Empty title="Không tìm thấy tài liệu">
            Thử từ khóa khác hoặc bỏ bộ lọc.
          </Empty>
        )}
      </Panel>
      <AnnualCoverage coverage={coverage} ticker={ticker} />
    </>
  );
}
function DocumentDrawer({ doc, onClose }) {
  const isArticle = isArticleDoc(doc);
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
              {entityLabel(doc)} ·{" "}
              {isArticle
                ? doc.publisher
                : doc.reporting_period || "Chưa ghi kỳ"}
            </p>
          </div>
        </div>
        <div className="source-meta">
          <span>
            Thu thập <strong>{when(doc.retrieved_at)}</strong>
          </span>
          <a href={doc.source_url} target="_blank" rel="noreferrer">
            {isArticle ? "Bài viết nguồn" : "PDF nguồn"}{" "}
            <ExternalLink size={13} />
          </a>
        </div>
        {isArticle && (
          <p className="footnote">
            Ngày đăng quan sát: {when(doc.publication_date)}
            {doc.author ? ` · Tác giả: ${doc.author}` : ""}. Thời gian trên
            trang chưa phải bằng chứng khả dụng lịch sử.
          </p>
        )}
        {doc.origin === "dataset_mirror" && (
          <p className="footnote">
            Nội dung nhập từ VietOnlineNews, có URL báo gốc; chưa đối chiếu lại
            với trang báo hiện tại. Dataset ghi nguồn {doc.dataset_split}, ID{" "}
            {doc.dataset_row_id}.
          </p>
        )}
        {doc.quarantine_reasons.length > 0 && (
          <Notice>
            <strong>Chưa đủ điều kiện lịch sử.</strong>
            <br />
            {doc.quarantine_reasons.map((r) => REASONS[r] || r).join("; ")}.
          </Notice>
        )}
        {(doc.potentially_partial_text_pages?.includes(page) ||
          doc.potentially_partial_document) && (
          <Notice>
            {doc.potentially_partial_document
              ? "Trình đọc PDF cảnh báo có thể bỏ sót nội dung của tài liệu."
              : "Trình đọc PDF đã bỏ qua một phần nội dung ở trang này."}{" "}
            Kiểm tra PDF gốc trước khi dùng cho đánh giá.
          </Notice>
        )}
        <div className="page-control">
          <span>
            {isArticle ? "Văn bản bài viết" : "Văn bản trích xuất · chưa OCR"}
          </span>
          {!isArticle && (
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
                    Math.min(
                      doc.pages,
                      Math.max(1, Number(e.target.value) || 1),
                    ),
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
          )}
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
function Analysis({ ticker, initialQuery, onTickerChange, tickers }) {
  const [query, setQuery] = useState(initialQuery || "");
  const [mode, setMode] = useState("exploratory_current");
  const [cutoff, setCutoff] = useState("2025-04-01T16:00");
  const [reportPeriod, setReportPeriod] = useState("auto"),
    [reportSources, setReportSources] = useState("issuer_reports"),
    [reportScope, setReportScope] = useState("all"),
    [reportRetrieval, setReportRetrieval] = useState("lexical_v0.2");
  const [search, setSearch] = useState(null),
    [payload, setPayload] = useState(null),
    [selected, setSelected] = useState(0);
  const [result, setResult] = useState(null),
    [busy, setBusy] = useState(""),
    [error, setError] = useState("");
  const [report, setReport] = useState(null),
    [development, setDevelopment] = useState(null),
    [history, setHistory] = useState([]);
  async function loadHistory() {
    try {
      setHistory((await api("research/reports")).reports);
    } catch {
      setHistory([]);
    }
  }
  useEffect(() => {
    let active = true;
    api("research/development")
      .then((r) => {
        if (active) setDevelopment(r);
      })
      .catch(() => {});
    loadHistory();
    return () => {
      active = false;
    };
  }, []);
  const reset = () => {
    setSearch(null);
    setPayload(null);
    setResult(null);
    setReport(null);
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
  async function createReport() {
    setBusy("report");
    setError("");
    setReport(null);
    try {
      setReport(
        await api("research/report", {
          query,
          ticker,
          mode,
          reporting_period: reportPeriod === "auto" ? null : reportPeriod,
          source_policy: reportSources,
          statement_scope: reportScope,
          retrieval_profile: reportRetrieval,
          decision_at:
            mode === "strict_point_in_time" ? `${cutoff}+07:00` : null,
        }),
      );
      await loadHistory();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  }
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
        title="Đặt câu hỏi của bạn"
        subtitle="Nhập nội dung bạn muốn tìm trong kho tài liệu tại máy."
      >
        <form onSubmit={find} className="analysis-form">
          <label className="query-input">
            <Search size={20} />
            <input
              aria-label="Câu hỏi của bạn"
              value={query}
              disabled={!!busy}
              maxLength={300}
              minLength={2}
              required
              placeholder="Nhập câu hỏi bạn muốn tìm hiểu…"
              onChange={(e) => {
                setQuery(e.target.value);
                reset();
              }}
            />
            <button
              className="button primary"
              disabled={!!busy || query.trim().length < 2}
            >
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
              Doanh nghiệp
              <select
                aria-label="Doanh nghiệp phân tích"
                value={ticker}
                disabled={!!busy}
                onChange={(e) => onTickerChange(e.target.value)}
              >
                <option value="all">Tất cả doanh nghiệp</option>
                {(tickers || ["FPT", "HPG", "VCB"])
                  .filter((t) => t !== "MARKET")
                  .map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
              </select>
            </label>
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
        <div className="evaluation-toolbar question-shortcut">
          <span className="footnote">
            Bạn muốn xem bộ câu hỏi đã dùng để kiểm tra AI?
          </span>
          <button
            className="text-button"
            type="button"
            onClick={() =>
              document
                .getElementById("development-questions")
                ?.scrollIntoView({ behavior: "smooth", block: "start" })
            }
          >
            Xem {development?.case_pack?.cases || ""} câu hỏi kiểm tra
          </button>
        </div>
      </Panel>
      <Notice tone={mode === "strict_point_in_time" ? "green" : "amber"}>
        {mode === "strict_point_in_time"
          ? "Chỉ tài liệu được gateway cho phép tại mốc quyết định mới đi vào truy xuất và thống kê corpus. Thiếu bằng chứng lịch sử sẽ không gọi mô hình."
          : "Chế độ khám phá nội dung hiện tại. Kết quả không phải phân tích tại thời điểm lịch sử; chưa sinh dự báo hoặc khuyến nghị giao dịch."}
      </Notice>
      {error && <Notice tone="error">{error}</Notice>}
      <Panel
        title="Báo cáo doanh nghiệp"
        subtitle="Một agent tổng hợp tối đa ba đoạn nguồn, kiểm tra trích dẫn và giữ dấu vết lần chạy."
      >
        <div className="analysis-options report-options">
          <label>
            Kỳ báo cáo
            <select
              aria-label="Kỳ báo cáo của báo cáo doanh nghiệp"
              value={reportPeriod}
              disabled={!!busy}
              onChange={(e) => {
                setReportPeriod(e.target.value);
                setReport(null);
              }}
            >
              <option value="auto">Tự nhận diện từ câu hỏi</option>
              <option value="all">Không lọc kỳ</option>
              {Array.from({ length: 11 }, (_, i) => 2026 - i).map((y) => (
                <option key={y} value={String(y)}>
                  {y}
                </option>
              ))}
            </select>
          </label>
          <label>
            Nguồn cho báo cáo
            <select
              aria-label="Nguồn cho báo cáo"
              value={reportSources}
              disabled={!!busy}
              onChange={(e) => {
                setReportSources(e.target.value);
                setReport(null);
              }}
            >
              <option value="issuer_reports">
                Báo cáo PDF của doanh nghiệp
              </option>
              <option value="all_linked">
                Tất cả nguồn được gắn mã liên quan
              </option>
            </select>
          </label>
          <label>
            Phạm vi số liệu
            <select
              aria-label="Phạm vi số liệu báo cáo"
              value={reportScope}
              disabled={!!busy}
              onChange={(e) => {
                setReportScope(e.target.value);
                setReport(null);
              }}
            >
              <option value="all">Tất cả phạm vi</option>
              <option value="consolidated">Hợp nhất</option>
              <option value="parent">Công ty mẹ / riêng lẻ</option>
            </select>
          </label>
          <label>
            Cách tìm bằng chứng
            <select
              aria-label="Cách tìm bằng chứng cho báo cáo"
              value={reportRetrieval}
              disabled={!!busy}
              onChange={(e) => {
                setReportRetrieval(e.target.value);
                setReport(null);
              }}
            >
              <option value="lexical_v0.2">Theo từ khóa</option>
              <option value="financial_sections_v0.3">
                Ưu tiên mục báo cáo và bảng số liệu · thử nghiệm
              </option>
            </select>
          </label>
        </div>
        <p className="footnote">
          Kỳ kế toán lọc theo metadata PDF; năm đăng bài báo không thay thế kỳ
          báo cáo. Không có nguồn đúng kỳ thì dừng, không tự chuyển sang kỳ
          khác.
          {reportRetrieval === "financial_sections_v0.3" &&
            " Cách thử nghiệm ưu tiên mục báo cáo tài chính và các đoạn bổ sung chỉ tiêu, năm, đơn vị; vẫn cần kiểm tra ý nghĩa và phạm vi số liệu."}
        </p>
        <div className="extract-action">
          <span>
            {ticker === "all"
              ? "Chọn một doanh nghiệp ở bộ lọc bên trên để lập báo cáo."
              : `${ticker} · báo cáo bằng chứng cho câu hỏi đang nhập`}
          </span>
          <button
            className="button primary"
            onClick={createReport}
            disabled={!!busy || ticker === "all" || query.trim().length < 2}
          >
            {busy === "report" ? (
              <Loader2 className="spin" size={16} />
            ) : (
              <FileCheck2 size={16} />
            )}
            {busy === "report"
              ? "Đang lập báo cáo…"
              : "Lập báo cáo doanh nghiệp"}
          </button>
        </div>
        <p className="footnote">
          Trích dẫn được đối chiếu nguyên văn; diễn giải cần người duyệt. Dự báo
          lợi suất và chỉ tiêu từ số liệu đã duyệt chưa được chạy.
          {development?.case_pack &&
            ` Bộ phát triển có ${development.case_pack.cases} case, ${development.case_pack.human_reviewed_cases} case được người duyệt tại thời điểm tạo bộ.`}
        </p>
        {report && <CompanyReportResult result={report} />}
        {!!history.length && (
          <details className="audit-details">
            <summary>Lịch sử báo cáo · gồm cả lượt bị chặn</summary>
            <p className="footnote">
              Mở kết quả đã lưu, không gọi lại mô hình. Nội dung thuộc câu hỏi,
              doanh nghiệp và chế độ của chính lần chạy đó.
            </p>
            {history.map((r) => (
              <div key={r.run_id} className="trace-row">
                <span>
                  {r.ticker || "—"} ·{" "}
                  {r.status === "completed_with_citations"
                    ? `${r.claims} trích dẫn`
                    : r.status === "integrity_failed"
                      ? "Lỗi toàn vẹn"
                      : "Bị chặn / từ chối"}{" "}
                  · {r.run_id}
                </span>
                <button
                  className="text-button"
                  disabled={!!busy || r.status === "integrity_failed"}
                  onClick={async () => {
                    setBusy("history");
                    setError("");
                    try {
                      setReport(await api(`research/reports/${r.run_id}`));
                    } catch (err) {
                      setError(err.message);
                    } finally {
                      setBusy("");
                    }
                  }}
                >
                  Mở báo cáo {r.run_id}
                </button>
              </div>
            ))}
          </details>
        )}
      </Panel>
      <TableEvidence
        api={api}
        Panel={Panel}
        Notice={Notice}
        ticker={ticker}
        query={query}
        mode={mode}
        cutoff={cutoff}
        reportingPeriod={reportPeriod}
        busy={busy}
        setBusy={setBusy}
      />
      <DevelopmentEvaluation api={api} Panel={Panel} Notice={Notice} />
      <CaseReview api={api} Panel={Panel} Notice={Notice} />
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
function CompanyReportResult({ result }) {
  const ready = result.status === "completed_with_citations";
  function download(kind) {
    const content =
      kind === "md" ? result.markdown : JSON.stringify(result, null, 2);
    const url = URL.createObjectURL(
      new Blob([content], {
        type:
          kind === "md" ? "text/markdown;charset=utf-8" : "application/json",
      }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = `${result.ticker}-${result.run_id}.${kind}`;
    a.click();
    URL.revokeObjectURL(url);
  }
  return (
    <div className="extraction-result">
      <div className="result-heading">
        <h3>Báo cáo bằng chứng {result.ticker}</h3>
        <Badge tone={ready ? "green" : "amber"}>
          {ready
            ? `${result.claims.length} trích dẫn đã đối chiếu`
            : result.status === "failed"
              ? "Không chạy được"
              : "Từ chối vì thiếu bằng chứng"}
        </Badge>
      </div>
      <p className="footnote">
        Câu hỏi của lần chạy: {result.question} ·{" "}
        {result.mode === "strict_point_in_time" ? "PiT strict" : "Đọc hiện tại"}
      </p>
      {result.retrieval_profile_id === "financial_sections_v0.3" && (
        <p className="footnote">
          Cách tìm bằng chứng: ưu tiên mục báo cáo và bảng số liệu · thử nghiệm.
        </p>
      )}
      {result.retrieval_scope && (
        <p className="footnote">
          Kỳ được lọc:{" "}
          {result.retrieval_scope.reporting_period || "Không giới hạn"} ·{" "}
          {result.retrieval_scope.source_policy === "issuer_reports"
            ? "Báo cáo của chính doanh nghiệp"
            : "Nguồn gắn mã liên quan"}{" "}
          ·{" "}
          {{
            all: "Tất cả phạm vi",
            consolidated: "Hợp nhất",
            parent: "Công ty mẹ / riêng lẻ",
          }[result.retrieval_scope.statement_scope] ||
            result.retrieval_scope.statement_scope}
        </p>
      )}
      {!!result.sources?.length && (
        <details className="audit-details">
          <summary>Xem các đoạn nguồn đã giao cho model</summary>
          {result.sources.map((s) => (
            <div key={s.evidence_id}>
              <p>
                <strong>
                  {s.evidence_id} · {s.source.ticker} ·{" "}
                  {s.source.reporting_period || "Chưa rõ kỳ"}
                </strong>{" "}
                · {s.source.title}
              </p>
              <a
                className="source-link"
                href={s.source.source_url}
                target="_blank"
                rel="noreferrer"
              >
                Nguồn gốc · trang/mục {s.passage.page}
              </a>
              <pre className="passage-text">{s.passage.text}</pre>
            </div>
          ))}
        </details>
      )}
      {result.error && <Notice tone="error">{result.error}</Notice>}
      {result.claims.map((claim, i) => (
        <div key={i} className="report-claim">
          <p className="summary-label">
            Diễn giải của mô hình · chưa duyệt ngữ nghĩa
          </p>
          <p>{claim.statement}</p>
          <blockquote>
            {claim.verification.literal_quote.source_quote}
          </blockquote>
          <a
            className="source-link"
            href={claim.citation.source_url}
            target="_blank"
            rel="noreferrer"
          >
            {claim.evidence_id} · Trang/mục {claim.citation.page} · ký tự{" "}
            {claim.citation.start}–{claim.citation.end}{" "}
            <ExternalLink size={13} />
          </a>
        </div>
      ))}
      {!!result.missing_information.length && (
        <Notice>
          <strong>Mô hình báo còn thiếu · chưa duyệt ngữ nghĩa</strong>
          <ul>
            {result.missing_information.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </Notice>
      )}
      <p className="footnote">
        {result.llm_calls} lần gọi mô hình ·{" "}
        {result.historical_availability_validated
          ? "Nguồn vượt gateway lịch sử"
          : "Chưa xác minh khả dụng lịch sử"}{" "}
        · Chưa sinh dự báo lợi suất.
      </p>
      <div className="trace-row">
        <span>
          <Clock3 size={13} />{" "}
          {result.generation
            ? `${result.generation.wall_seconds.toFixed(1)} giây`
            : "Chưa có inference"}{" "}
          · {result.run_id}
        </span>
        <button className="text-button" onClick={() => download("md")}>
          <Download size={14} /> Tải báo cáo
        </button>
        <button className="text-button" onClick={() => download("json")}>
          <Download size={14} /> Tải dấu vết JSON
        </button>
      </div>
    </div>
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
      {(result.source_parser_diagnostics?.potentially_partial_document ||
        result.source_parser_diagnostics?.potentially_partial_text_pages?.includes(
          result.passage?.page,
        )) && (
        <Notice>
          Nguồn có cảnh báo nội dung có thể bị lược bỏ khi đọc PDF. Trích dẫn
          khớp chuỗi không chứng minh văn bản trang đã đầy đủ.
        </Notice>
      )}
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
      setData(
        await api(
          `workspace?ticker=${encodeURIComponent(ticker === "all" ? "" : ticker)}`,
        ),
      );
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
    if (!data?.catalog) return;
    let active = true;
    api(
      `workspace?ticker=${encodeURIComponent(ticker === "all" ? "" : ticker)}`,
    )
      .then((next) => {
        if (active) setData(next);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [ticker, Boolean(data?.catalog)]);
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
    (d) =>
      ticker === "all" ||
      d.ticker === ticker ||
      d.related_tickers?.includes(ticker),
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
                <small>
                  {fmt(data.document_count ?? data.documents.length)}
                </small>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-filter">
          <div className="nav-label">PHẠM VI NGHIÊN CỨU</div>
          <label className="sr-only" htmlFor="ticker-filter">
            Phạm vi bằng chứng
          </label>
          <select
            id="ticker-filter"
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
          >
            <option value="all">Tất cả doanh nghiệp và thị trường</option>
            {[
              ...new Set(
                data?.catalog?.facets?.tickers ||
                  (data?.documents || []).flatMap((d) => [
                    d.ticker,
                    ...(d.related_tickers || []),
                  ]),
              ),
            ]
              .sort()
              .map((t) => (
                <option key={t} value={t}>
                  {t === "MARKET" ? "Thị trường / vĩ mô" : t}
                </option>
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
                <Documents
                  docs={docs}
                  onOpen={setDrawer}
                  coverage={data.coverage}
                  ticker={ticker}
                  catalog={data.catalog}
                />
              )}
              {current[0] === "analysis" && (
                <Analysis
                  key={analysisQuery}
                  ticker={ticker}
                  onTickerChange={setTicker}
                  tickers={
                    data.catalog?.facets?.tickers || [
                      ...new Set(data.documents.map((d) => d.ticker)),
                    ]
                  }
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
