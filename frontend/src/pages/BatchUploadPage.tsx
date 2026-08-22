import { useEffect, useMemo, useState } from "react";
import { AspectBreakdownChart } from "../components/charts/AspectBreakdownChart";
import { ConfidenceHistogramChart } from "../components/charts/ConfidenceHistogramChart";
import { SentimentSplitChart } from "../components/charts/SentimentSplitChart";
import { SentimentTrendChart } from "../components/charts/SentimentTrendChart";
import { DropZone } from "../components/batch/DropZone";
import { ResultsFilter, type LabelFilter } from "../components/batch/ResultsFilter";
import { RowResultsCards, RowResultsTable } from "../components/batch/RowResults";
import { DownloadIcon } from "../components/batch/icons";
import { Button } from "../components/ui/Button";
import { DemoDataBadge } from "../components/ui/DemoDataBadge";
import { ErrorState } from "../components/ui/ErrorState";
import { GlassCard } from "../components/ui/GlassCard";
import { StatusPill } from "../components/ui/Badge";
import { SurfaceCard } from "../components/ui/SurfaceCard";
import { useModelStatus } from "../hooks/useAnalytics";
import { useFileUpload } from "../hooks/useSentiment";
import { APP_NAME, MODEL_OPTIONS } from "../utils/constants";
import { formatBytes, formatNumber, formatPercent } from "../utils/formatters";
import type { FileRowResult, FileUploadResponse, ModelName } from "../types/sentiment";
import "../styles/batch.css";

const ACCEPTED_EXTENSIONS = [".csv", ".xlsx", ".xls"];
const MAX_UPLOAD_BYTES = 5 * 1024 * 1024; // mirrors backend/app/api/v1/endpoints/sentiment.py MAX_UPLOAD_BYTES
const MAX_ROWS = 2000; // mirrors backend/app/services/file_batch_service.py MAX_FILE_ROWS

const CONFIDENCE_BUCKETS = [
  { label: "50-60%", min: 0.5, max: 0.6 },
  { label: "60-70%", min: 0.6, max: 0.7 },
  { label: "70-80%", min: 0.7, max: 0.8 },
  { label: "80-90%", min: 0.8, max: 0.9 },
  { label: "90-100%", min: 0.9, max: 1.01 },
];

function bucketConfidence(results: FileRowResult[]) {
  return CONFIDENCE_BUCKETS.map((b) => ({
    label: b.label,
    count: results.filter((r) => r.confidence !== undefined && r.confidence >= b.min && r.confidence < b.max).length,
  }));
}

/** Hand-built inline SVG donut -- the exported HTML has to render fully
 * offline with no bundler/CDN, so this draws arcs directly rather than
 * pulling in a charting library. Colors are a static snapshot of the
 * Baseera palette (this file is a standalone document, not styled by the
 * app's CSS once downloaded). */
function svgDonut(nPositive: number, nNegative: number): string {
  const total = nPositive + nNegative || 1;
  const cx = 90, cy = 90, r = 65, stroke = 26;
  const circumference = 2 * Math.PI * r;
  const posLen = (nPositive / total) * circumference;
  const negLen = (nNegative / total) * circumference;
  return `<svg viewBox="0 0 180 180" width="180" height="180">
    <circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="#1a2740" stroke-width="${stroke}" />
    <circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="#3ddc97" stroke-width="${stroke}"
      stroke-dasharray="${posLen} ${circumference - posLen}" stroke-dashoffset="0" transform="rotate(-90 ${cx} ${cy})" />
    <circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="#ff667a" stroke-width="${stroke}"
      stroke-dasharray="${negLen} ${circumference - negLen}" stroke-dashoffset="${-posLen}" transform="rotate(-90 ${cx} ${cy})" />
    <text x="${cx}" y="${cy - 4}" text-anchor="middle" font-size="22" font-weight="700" fill="#e8eef7">${Math.round((nPositive / total) * 100)}%</text>
    <text x="${cx}" y="${cy + 16}" text-anchor="middle" font-size="10" fill="#8fa3bd">positive</text>
  </svg>`;
}

/** Hand-built inline SVG bar chart for the confidence-bucket histogram, same offline constraint as the donut above. */
function svgHistogram(buckets: { label: string; count: number }[]): string {
  const w = 460, h = 160, padLeft = 34, padBottom = 24, barGap = 14;
  const max = Math.max(1, ...buckets.map((b) => b.count));
  const barW = (w - padLeft - barGap * (buckets.length - 1)) / buckets.length;
  const bars = buckets
    .map((b, i) => {
      const barH = (b.count / max) * (h - padBottom - 16);
      const x = padLeft + i * (barW + barGap);
      const y = h - padBottom - barH;
      return `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${barW.toFixed(1)}" height="${barH.toFixed(1)}" rx="4" fill="#f4b942" />
        <text x="${(x + barW / 2).toFixed(1)}" y="${(y - 6).toFixed(1)}" text-anchor="middle" font-size="10" fill="#e8eef7">${b.count}</text>
        <text x="${(x + barW / 2).toFixed(1)}" y="${h - 6}" text-anchor="middle" font-size="9" fill="#8fa3bd">${b.label}</text>`;
    })
    .join("");
  return `<svg viewBox="0 0 ${w} ${h}" width="${w}" height="${h}">
    <line x1="${padLeft}" y1="${h - padBottom}" x2="${w}" y2="${h - padBottom}" stroke="#24354d" />
    ${bars}
  </svg>`;
}

function resultsToCsv(results: FileRowResult[]): string {
  const header = "row,label,confidence,probability_positive,probability_negative,text\n";
  const escape = (v: string) => `"${v.replace(/"/g, '""')}"`;
  const rows = results
    .map((r) =>
      [r.row, r.label, r.confidence ?? "", r.probability_positive ?? "", r.probability_negative ?? "", escape(r.text)].join(","),
    )
    .join("\n");
  return header + rows;
}

function downloadBlob(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: `${mime};charset=utf-8;` });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

const escapeHtml = (s: string) => s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c] as string));

/** Word-chip lists for the offline export -- mirrors the "Most Influential Words" page section. */
function buildTopWordsHtml(result: FileUploadResponse): string {
  const words = result.top_words;
  if (!words || (words.top_positive_words.length === 0 && words.top_negative_words.length === 0)) return "";
  const chips = (items: { word: string; count: number }[], cls: string) =>
    items.map((w) => `<span class="word-chip ${cls}" title="${w.count} occurrences">${escapeHtml(w.word)}</span>`).join("");
  return `<div class="chart-box" style="margin-bottom:2rem;max-width:1000px;">
    <h3>Most Influential Words</h3>
    <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(220px, 1fr));gap:1.2rem;">
      <div><div class="label" style="color:#3ddc97;">Positive-leaning</div><div class="word-chips">${chips(words.top_positive_words, "positive")}</div></div>
      <div><div class="label" style="color:#ff667a;">Negative-leaning</div><div class="word-chips">${chips(words.top_negative_words, "negative")}</div></div>
    </div>
  </div>`;
}

/** Weekly positive-rate table for the offline export -- a table rather than a
 * full inline SVG line chart, to keep this hand-rolled export simple. */
function buildTimeTrendHtml(result: FileUploadResponse): string {
  const trend = result.time_trend;
  if (!trend?.available) return "";
  const rows = trend.points
    .map((p) => `<tr><td>${escapeHtml(p.period)}</td><td>${p.n.toLocaleString()}</td><td>${p.positive_pct.toFixed(1)}%</td></tr>`)
    .join("");
  return `<div class="chart-box" style="margin-bottom:2rem;max-width:1000px;">
    <h3>Sentiment Trend (${escapeHtml(trend.date_column_used)})</h3>
    <table><thead><tr><th>Week</th><th>Reviews</th><th>% Positive</th></tr></thead><tbody>${rows}</tbody></table>
  </div>`;
}

/** Fake-review + aspect summary for the offline export, only present when the
 * upload ran with advanced=true. */
function buildAdvancedSummaryHtml(result: FileUploadResponse): string {
  const fake = result.fake_review_summary;
  const aspects = result.aspect_summary;
  if (!fake && !aspects) return "";

  const fakeHtml = fake
    ? `<div class="chart-box">
        <h3>Experimental Authenticity Signal</h3>
        ${
          fake.available
            ? `<div class="value" style="color:#f4b942;">${fake.flagged_pct.toFixed(1)}%</div>
               <div class="note" style="margin-top:0.2rem;">${fake.n_flagged_fake.toLocaleString()} of ${fake.n_screened_negative.toLocaleString()} negative reviews show an elevated experimental signal -- not proof of fraud.</div>`
            : `<p class="note">Not available (${escapeHtml(fake.reason)}).</p>`
        }
      </div>`
    : "";

  const aspectsHtml = aspects
    ? `<div class="chart-box">
        <h3>Aspect Breakdown</h3>
        ${
          aspects.available
            ? `<table><thead><tr><th>Aspect</th><th>Mentioned</th><th>Positive</th><th>Neutral</th><th>Negative</th></tr></thead><tbody>${aspects.per_aspect
                .map((a) => `<tr><td>${escapeHtml(a.aspect)}</td><td>${a.mentioned_pct.toFixed(0)}%</td><td>${a.positive_pct.toFixed(0)}%</td><td>${a.neutral_pct.toFixed(0)}%</td><td>${a.negative_pct.toFixed(0)}%</td></tr>`)
                .join("")}</tbody></table>
              <p class="note">Positive/Neutral/Negative are computed among reviews that mentioned that aspect only (see the Mentioned column).</p>`
            : `<p class="note">Not available (${escapeHtml(aspects.reason)}).</p>`
        }
      </div>`
    : "";

  return `<div class="charts-row">${fakeHtml}${aspectsHtml}</div>`;
}

/** Self-contained HTML dashboard snapshot for one classified file -- opens
 * and reads fine completely offline, no external assets. Built client-side
 * from data already in memory (no extra backend round-trip). */
function buildDashboardHtml(result: FileUploadResponse): string {
  const posPct = result.positive_pct;
  const negPct = result.negative_pct;
  const rows = result.results
    .slice(0, 500)
    .map(
      (r) =>
        `<tr><td>${r.row}</td><td class="text">${escapeHtml(r.text)}</td><td class="label ${r.label.toLowerCase()}">${r.label}</td><td>${r.confidence !== undefined ? (r.confidence * 100).toFixed(0) + "%" : "—"}</td></tr>`,
    )
    .join("");
  const donut = svgDonut(result.n_positive, result.n_negative);
  const histogram = svgHistogram(bucketConfidence(result.results));

  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>${escapeHtml(result.filename)} — ${APP_NAME} report</title>
<style>
  body { font-family: -apple-system, "Segoe UI", Inter, sans-serif; background: #0a1220; color: #e8eef7; margin: 0; padding: 2.5rem 2rem; }
  h1 { font-size: 1.5rem; margin: 0 0 0.25rem; }
  .sub { color: #8fa3bd; font-size: 0.85rem; margin-bottom: 2rem; }
  .kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 0.9rem; margin-bottom: 2rem; max-width: 900px; }
  .kpi { background: #101d33; border: 1px solid #24354d; border-radius: 14px; padding: 1rem 1.2rem; }
  .kpi .label { color: #8fa3bd; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.03em; }
  .kpi .value { font-size: 1.6rem; font-weight: 700; margin-top: 0.25rem; }
  .charts-row { display: flex; gap: 1.5rem; flex-wrap: wrap; margin-bottom: 2rem; }
  .chart-box { background: #101d33; border: 1px solid #24354d; border-radius: 14px; padding: 1.2rem 1.4rem; }
  .chart-box h3 { margin: 0 0 0.8rem; font-size: 0.8rem; color: #8fa3bd; text-transform: uppercase; letter-spacing: 0.03em; font-weight: 600; }
  .legend-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 0.4rem; }
  table { border-collapse: collapse; width: 100%; max-width: 1000px; font-size: 0.85rem; }
  th, td { text-align: left; padding: 0.5rem 0.7rem; border-bottom: 1px solid #1a2740; }
  th { color: #8fa3bd; text-transform: uppercase; font-size: 0.68rem; letter-spacing: 0.03em; }
  td.text { max-width: 420px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .label.positive { color: #3ddc97; font-weight: 700; }
  .label.negative { color: #ff667a; font-weight: 700; }
  .label.error { color: #f4b942; font-weight: 700; }
  .note { color: #8fa3bd; font-size: 0.78rem; margin-top: 1rem; }
  .word-chips { display: flex; flex-wrap: wrap; gap: 0.35rem; margin-top: 0.6rem; }
  .word-chip { padding: 0.2rem 0.55rem; border-radius: 6px; border: 1px solid; font-size: 0.82rem; }
  .word-chip.positive { border-color: #1f6b47; background: rgba(61,220,151,0.14); color: #e8eef7; }
  .word-chip.negative { border-color: #7a2f3b; background: rgba(255,102,122,0.14); color: #e8eef7; }
</style></head>
<body>
  <h1>${escapeHtml(result.filename)}</h1>
  <div class="sub">Classified by ${APP_NAME} · model: ${result.model_name} · column used: ${escapeHtml(result.text_column_used)} · generated ${new Date().toLocaleString()}</div>
  <div class="kpis">
    <div class="kpi"><div class="label">Rows Processed</div><div class="value">${result.rows_processed.toLocaleString()}</div></div>
    <div class="kpi"><div class="label">Positive</div><div class="value" style="color:#3ddc97">${posPct.toFixed(1)}%</div></div>
    <div class="kpi"><div class="label">Negative</div><div class="value" style="color:#ff667a">${negPct.toFixed(1)}%</div></div>
    <div class="kpi"><div class="label">Skipped</div><div class="value">${result.n_skipped_empty_or_error.toLocaleString()}</div></div>
  </div>
  <div class="charts-row">
    <div class="chart-box">
      <h3>Sentiment Split</h3>
      ${donut}
      <div style="margin-top:0.6rem;font-size:0.78rem;color:#8fa3bd;">
        <div><span class="legend-dot" style="background:#3ddc97"></span>Positive — ${result.n_positive.toLocaleString()}</div>
        <div><span class="legend-dot" style="background:#ff667a"></span>Negative — ${result.n_negative.toLocaleString()}</div>
      </div>
    </div>
    <div class="chart-box">
      <h3>Confidence Distribution</h3>
      ${histogram}
    </div>
  </div>
  ${buildTopWordsHtml(result)}
  ${buildTimeTrendHtml(result)}
  ${buildAdvancedSummaryHtml(result)}
  <table>
    <thead><tr><th>Row</th><th>Text</th><th>Label</th><th>Confidence</th></tr></thead>
    <tbody>${rows}</tbody>
  </table>
  ${result.results.length > 500 ? `<p class="note">Showing first 500 of ${result.results.length} rows. Download the CSV from the app for the full list.</p>` : ""}
  <p class="note">Sentiment predictions are probabilistic and dataset-dependent, not objective judgments. The experimental authenticity signal, where shown, is not proof of fraud.</p>
</body></html>`;
}

function validateFileClientSide(file: File): string | null {
  const lower = file.name.toLowerCase();
  if (!ACCEPTED_EXTENSIONS.some((ext) => lower.endsWith(ext))) {
    return `"${file.name}" isn't a supported file type. Upload a .csv, .xlsx, or .xls file.`;
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    return `"${file.name}" is ${formatBytes(file.size)}, over the ${formatBytes(MAX_UPLOAD_BYTES)} limit.`;
  }
  if (file.size === 0) {
    return `"${file.name}" is empty.`;
  }
  return null;
}

export function BatchUploadPage() {
  const { result, loading, error, upload, clearSaved, durationMs, retry, reset } = useFileUpload();
  const modelStatus = useModelStatus();
  const [modelName, setModelName] = useState<ModelName>("bert");
  const [advanced, setAdvanced] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [clientError, setClientError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [labelFilter, setLabelFilter] = useState<LabelFilter>("all");

  const bertUnavailable = modelStatus.data?.artifacts?.bert?.status && modelStatus.data.artifacts.bert.status !== "available";

  // A disabled <option> only stops the user from picking it in the dropdown --
  // it doesn't change an already-selected value, so without this the form
  // would silently keep submitting "bert" (the default) even after the
  // status check confirms it's unavailable, failing every row. Only steers
  // away from bert specifically; never overrides an explicit cnn2d choice.
  useEffect(() => {
    if (bertUnavailable && modelName === "bert") setModelName("cnn2d");
  }, [bertUnavailable, modelName]);

  function handleFile(file: File) {
    const clientIssue = validateFileClientSide(file);
    setClientError(clientIssue);
    setSelectedFile(file);
    if (clientIssue) return; // genuinely blocking -- never send an invalid file
    upload(file, modelName, advanced);
  }

  function handleRemove() {
    setSelectedFile(null);
    setClientError(null);
    reset();
  }

  function handleStartOver() {
    clearSaved();
    setSelectedFile(null);
    setClientError(null);
    reset();
    setSearch("");
    setLabelFilter("all");
  }

  const filteredResults = useMemo(() => {
    if (!result) return [];
    const q = search.trim().toLowerCase();
    return result.results.filter((r) => {
      if (labelFilter !== "all" && r.label !== labelFilter) return false;
      if (q && !r.text.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [result, search, labelFilter]);

  const displayedResults = filteredResults.slice(0, 200);

  const liveMessage = loading
    ? "Validating and analyzing file…"
    : error
      ? `Upload failed: ${error.message}`
      : result
        ? `Processing complete. ${formatNumber(result.rows_processed)} rows processed, ${formatPercent(result.positive_pct)} positive.`
        : "";

  const canRetry = !!error && error.code !== "VALIDATION_ERROR";

  return (
    <div className="bsr-batch">
      <header className="bsr-batch-intro">
        <span className="bsr-label bsr-batch-intro__eyebrow">Batch Analyzer</span>
        <h1 className="bsr-h1">Analyze customer reviews in bulk</h1>
        <p className="bsr-body-lg">
          Upload a CSV or Excel file with a review-text column -- every row is classified Positive or Negative, up to{" "}
          {formatNumber(MAX_ROWS)} rows per file. Results are probabilistic estimates, the same models used on the single-review
          analyzer, just run over a whole file at once.
        </p>
        <div className="bsr-batch-intro__notes">
          <DemoDataBadge kind="demo" label="Demonstration / academic project" />
          <DemoDataBadge kind="demo" label="Results saved for 7 days on this server" />
        </div>
      </header>

      <div className="bsr-batch-step">
        <div className="bsr-batch-step-head">
          <span className="bsr-batch-step-head__number">1</span>
          <h2 className="bsr-h4">Prepare your file</h2>
        </div>

        <div className="bsr-batch-workspace">
          <GlassCard className="bsr-batch-panel">
            <h3 className="bsr-h5" style={{ marginTop: 0 }}>Expected columns</h3>
            <p className="bsr-sm" style={{ color: "var(--bsr-text-faint)" }}>
              The review-text column is auto-detected by name. Any of these work -- or any text column with reasonably long values.
            </p>
            <table className="bsr-batch-schema-table">
              <thead>
                <tr><th>Column</th><th>Required</th><th>Notes</th></tr>
              </thead>
              <tbody>
                <tr><td className="bsr-mono">text / review / comment / message</td><td>Required (one of)</td><td>The review text itself</td></tr>
                <tr><td className="bsr-mono">date / created_at / review_date</td><td>Optional</td><td>Enables the sentiment-trend chart</td></tr>
              </tbody>
            </table>
            <p className="bsr-sm" style={{ color: "var(--bsr-text-faint)", marginTop: "var(--bsr-space-3)" }}>
              Example row (demonstration content):
            </p>
            <table className="bsr-batch-schema-table">
              <thead><tr><th>text</th><th>date</th></tr></thead>
              <tbody><tr><td>"Delivery was fast and the product matched the listing."</td><td>2018-05-14</td></tr></tbody>
            </table>

            <div className="bsr-batch-settings" style={{ marginTop: "var(--bsr-space-5)" }}>
              <div className="bsr-batch-settings__row">
                <label className="bsr-batch-field-label">
                  Model
                  <select className="bsr-batch-select" value={modelName} onChange={(e) => setModelName(e.target.value as ModelName)}>
                    {MODEL_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value} disabled={opt.value === "bert" && !!bertUnavailable}>
                        {opt.label}{opt.value === "bert" && bertUnavailable ? " -- unavailable on this deployment" : ""}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <label className="bsr-batch-checkbox-row">
                <input type="checkbox" checked={advanced} onChange={(e) => setAdvanced(e.target.checked)} />
                <span>
                  Advanced analysis -- adds an experimental authenticity signal and aspect breakdown over a sample of up to 100 rows.
                  Slower; output may report "not available" if those optional models aren't loaded on this deployment.
                </span>
              </label>
            </div>
          </GlassCard>

          <GlassCard className="bsr-batch-panel">
            <h3 className="bsr-h5" style={{ marginTop: 0 }}>Upload</h3>
            <DropZone
              selectedFile={selectedFile}
              onFileSelected={handleFile}
              onRemove={handleRemove}
              disabled={loading}
              accept=".csv,.xlsx,.xls"
              acceptLabel=".csv, .xlsx, .xls"
              maxSizeLabel={formatBytes(MAX_UPLOAD_BYTES)}
              maxRowsLabel={`up to ${formatNumber(MAX_ROWS)} rows`}
              statusLabel={loading ? "Validating & analyzing…" : result ? "Processed" : clientError ? "Rejected" : undefined}
            />
            {clientError && (
              <p className="bsr-sm bsr-batch-inline-error" role="alert">{clientError}</p>
            )}

            <div className="bsr-visually-hidden" role="status" aria-live="polite">{liveMessage}</div>

            {loading && (
              <div className="bsr-loading-state bsr-loading-state--full" aria-hidden="true" style={{ marginTop: "var(--bsr-space-4)" }}>
                <span className="bsr-btn__spinner bsr-loading-state__spinner" aria-hidden="true" style={{ width: 24, height: 24 }} />
                <span className="bsr-body">Validating &amp; analyzing…</span>
                <span className="bsr-sm" style={{ color: "var(--bsr-text-faint)" }}>
                  This runs synchronously on the server; larger files take longer. No progress percentage is reported by the API, so this is an indeterminate wait, not a stalled page.
                </span>
              </div>
            )}

            {!loading && error && (
              <div style={{ marginTop: "var(--bsr-space-4)" }}>
                <ErrorState
                  title={error.code === "VALIDATION_ERROR" ? "File couldn't be processed" : "Upload failed"}
                  message={error.message}
                  code={error.code}
                  onRetry={canRetry ? retry : undefined}
                />
              </div>
            )}
          </GlassCard>
        </div>
      </div>

      {result && (
        <div className="bsr-batch-step">
          <div className="bsr-batch-step-head">
            <span className="bsr-batch-step-head__number">2</span>
            <h2 className="bsr-h4">Review results</h2>
          </div>

          <div className="bsr-batch-results">
            {result.expires_at && (
              <div className="bsr-batch-restored-banner">
                <span className="bsr-sm">
                  Restored from a saved upload ({result.filename}) -- available until {new Date(result.expires_at).toLocaleString()}.
                </span>
                <Button type="button" variant="ghost" onClick={handleStartOver}>Start over with a new file</Button>
              </div>
            )}

            <SurfaceCard className="bsr-batch-panel" aria-label="Processing summary">
              <div className="bsr-batch-card-head">
                <h3 className="bsr-h5" style={{ margin: 0 }}>
                  {result.truncated ? (
                    <StatusPill tone="warning">Truncated</StatusPill>
                  ) : result.n_classified > 0 ? (
                    <StatusPill tone="positive">Complete</StatusPill>
                  ) : (
                    <StatusPill tone="negative">No rows classified</StatusPill>
                  )}
                </h3>
                {durationMs !== null && (
                  <span className="bsr-sm" style={{ color: "var(--bsr-text-faint)" }}>
                    Processed in {(durationMs / 1000).toFixed(1)}s (measured in this browser)
                  </span>
                )}
              </div>
              <div className="bsr-batch-kpis">
                <div className="bsr-batch-kpi">
                  <span className="bsr-batch-kpi__value bsr-mono">{formatNumber(result.rows_processed)}</span>
                  <span className="bsr-batch-kpi__label bsr-label">Rows processed</span>
                  {result.truncated && (
                    <span className="bsr-batch-kpi__sub">Truncated from {formatNumber(result.total_rows_in_file)} (max {formatNumber(result.max_rows_supported)})</span>
                  )}
                </div>
                <div className="bsr-batch-kpi">
                  <span className="bsr-batch-kpi__value bsr-mono" style={{ color: "var(--bsr-positive)" }}>{formatPercent(result.positive_pct)}</span>
                  <span className="bsr-batch-kpi__label bsr-label">Positive</span>
                  <span className="bsr-batch-kpi__sub">{formatNumber(result.n_positive)} reviews</span>
                </div>
                <div className="bsr-batch-kpi">
                  <span className="bsr-batch-kpi__value bsr-mono" style={{ color: "var(--bsr-negative)" }}>{formatPercent(result.negative_pct)}</span>
                  <span className="bsr-batch-kpi__label bsr-label">Negative</span>
                  <span className="bsr-batch-kpi__sub">{formatNumber(result.n_negative)} reviews</span>
                </div>
                <div className="bsr-batch-kpi">
                  <span className="bsr-batch-kpi__value bsr-mono">{formatNumber(result.n_skipped_empty_or_error)}</span>
                  <span className="bsr-batch-kpi__label bsr-label">Skipped</span>
                  <span className="bsr-batch-kpi__sub">empty or errored rows</span>
                </div>
              </div>
              <p className="bsr-sm" style={{ color: "var(--bsr-text-faint)", marginTop: "var(--bsr-space-4)" }}>
                Text column used: <code>{result.text_column_used}</code> · Model: {result.model_name}
              </p>
            </SurfaceCard>

            <div className="bsr-batch-chart-grid">
              <SurfaceCard className="bsr-batch-panel" aria-label="Sentiment split, donut chart">
                <h3 className="bsr-h5" style={{ marginTop: 0 }}>Sentiment split</h3>
                <SentimentSplitChart nPositive={result.n_positive} nNegative={result.n_negative} />
              </SurfaceCard>
              <SurfaceCard className="bsr-batch-panel" aria-label="Confidence distribution, bar chart">
                <h3 className="bsr-h5" style={{ marginTop: 0 }}>Confidence distribution</h3>
                <ConfidenceHistogramChart results={result.results} />
              </SurfaceCard>
            </div>

            {result.top_words && (result.top_words.top_positive_words.length > 0 || result.top_words.top_negative_words.length > 0) && (
              <SurfaceCard className="bsr-batch-panel" aria-label="Most influential words">
                <h3 className="bsr-h5" style={{ marginTop: 0 }}>Most influential words</h3>
                <p className="bsr-sm" style={{ color: "var(--bsr-text-faint)", marginTop: "-0.3rem" }}>
                  Words that show up disproportionately in Positive vs. Negative reviews in this file (frequency-based, not per-row SHAP).
                </p>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "var(--bsr-space-5)", marginTop: "var(--bsr-space-3)" }}>
                  <div>
                    <span className="bsr-label" style={{ color: "var(--bsr-positive)" }}>Positive-leaning</span>
                    <div className="bsr-batch-tokens">
                      {result.top_words.top_positive_words.map((w) => (
                        <span key={w.word} className="bsr-batch-token-chip" style={{ background: "var(--bsr-positive-soft)", borderColor: "var(--bsr-positive-border)" }} title={`${w.count} occurrences`}>
                          {w.word}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div>
                    <span className="bsr-label" style={{ color: "var(--bsr-negative)" }}>Negative-leaning</span>
                    <div className="bsr-batch-tokens">
                      {result.top_words.top_negative_words.map((w) => (
                        <span key={w.word} className="bsr-batch-token-chip" style={{ background: "var(--bsr-negative-soft)", borderColor: "var(--bsr-negative-border)" }} title={`${w.count} occurrences`}>
                          {w.word}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </SurfaceCard>
            )}

            {result.time_trend?.available && (
              <SurfaceCard className="bsr-batch-panel" aria-label="Sentiment trend over time">
                <h3 className="bsr-h5" style={{ marginTop: 0 }}>Sentiment trend ({result.time_trend.date_column_used})</h3>
                <SentimentTrendChart data={result.time_trend.points} />
              </SurfaceCard>
            )}

            {(result.fake_review_summary || result.aspect_summary) && (
              <div className="bsr-batch-chart-grid">
                {result.fake_review_summary && (
                  <SurfaceCard className="bsr-batch-panel" aria-label="Experimental authenticity signal">
                    <h3 className="bsr-h5" style={{ marginTop: 0 }}>Experimental authenticity signal</h3>
                    {result.fake_review_summary.available ? (
                      <>
                        <p className="bsr-sm" style={{ color: "var(--bsr-text-muted)" }}>
                          Elevated signal in <strong style={{ color: "var(--bsr-text)" }}>{formatPercent(result.fake_review_summary.flagged_pct)}</strong> of screened negative reviews
                        </p>
                        <p className="bsr-sm" style={{ color: "var(--bsr-text-faint)" }}>
                          {formatNumber(result.fake_review_summary.n_flagged_fake)} of {formatNumber(result.fake_review_summary.n_screened_negative)} negative reviews -- this is not proof any of them are fake.
                        </p>
                        <p className="bsr-sm" style={{ color: "var(--bsr-text-faint)", marginTop: "var(--bsr-space-2)" }}>{result.fake_review_summary.methodology_note}</p>
                      </>
                    ) : (
                      <p className="bsr-sm" style={{ color: "var(--bsr-text-faint)" }}>Not available ({result.fake_review_summary.reason}).</p>
                    )}
                  </SurfaceCard>
                )}
                {result.aspect_summary && (
                  <SurfaceCard className="bsr-batch-panel" aria-label="Aspect breakdown">
                    <h3 className="bsr-h5" style={{ marginTop: 0 }}>Aspect breakdown</h3>
                    {result.aspect_summary.available ? (
                      <>
                        <AspectBreakdownChart data={result.aspect_summary.per_aspect} />
                        <p className="bsr-sm" style={{ color: "var(--bsr-text-faint)", marginTop: "var(--bsr-space-3)" }}>{result.aspect_summary.methodology_note}</p>
                      </>
                    ) : (
                      <p className="bsr-sm" style={{ color: "var(--bsr-text-faint)" }}>Not available ({result.aspect_summary.reason}).</p>
                    )}
                  </SurfaceCard>
                )}
              </div>
            )}

            <SurfaceCard className="bsr-batch-panel" aria-label="Row-level results">
              <div className="bsr-batch-card-head">
                <h3 className="bsr-h5" style={{ margin: 0 }}>Row-level results</h3>
                <div className="bsr-batch-results-actions">
                  <Button type="button" variant="secondary" leftIcon={<DownloadIcon />} onClick={() => downloadBlob(`${result.filename}-dashboard.html`, buildDashboardHtml(result), "text/html")}>
                    Download dashboard (HTML)
                  </Button>
                  <Button type="button" variant="secondary" leftIcon={<DownloadIcon />} onClick={() => downloadBlob(`${result.filename}-classified.csv`, resultsToCsv(result.results), "text/csv")}>
                    Download results (CSV)
                  </Button>
                </div>
              </div>

              <ResultsFilter
                search={search}
                onSearchChange={setSearch}
                labelFilter={labelFilter}
                onLabelFilterChange={setLabelFilter}
                visibleCount={displayedResults.length}
                totalCount={result.results.length}
              />

              <div className="bsr-batch-table-wrap">
                <RowResultsTable rows={displayedResults} />
              </div>
              <RowResultsCards rows={displayedResults} />

              {filteredResults.length > 200 && (
                <p className="bsr-sm" style={{ color: "var(--bsr-text-faint)", marginTop: "var(--bsr-space-3)" }}>
                  Showing first 200 of {formatNumber(filteredResults.length)} matching rows -- download the CSV for the full list.
                </p>
              )}
              {filteredResults.length === 0 && (
                <p className="bsr-sm" style={{ color: "var(--bsr-text-faint)", marginTop: "var(--bsr-space-3)" }}>
                  No loaded rows match this filter.
                </p>
              )}
            </SurfaceCard>
          </div>
        </div>
      )}
    </div>
  );
}
