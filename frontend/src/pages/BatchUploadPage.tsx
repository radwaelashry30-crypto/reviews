import { ChangeEvent, DragEvent, useRef, useState } from "react";
import { ErrorState } from "../components/ErrorState";
import { LoadingState } from "../components/LoadingState";
import { AspectBreakdownChart } from "../components/charts/AspectBreakdownChart";
import { ConfidenceHistogramChart } from "../components/charts/ConfidenceHistogramChart";
import { SentimentSplitChart } from "../components/charts/SentimentSplitChart";
import { SentimentTrendChart } from "../components/charts/SentimentTrendChart";
import { useFileUpload } from "../hooks/useSentiment";
import { APP_NAME, MODEL_OPTIONS } from "../utils/constants";
import { formatNumber, formatPercent } from "../utils/formatters";
import type { FileRowResult, FileUploadResponse, ModelName } from "../types/sentiment";

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
 * pulling in a charting library. */
function svgDonut(nPositive: number, nNegative: number): string {
  const total = nPositive + nNegative || 1;
  const cx = 90, cy = 90, r = 65, stroke = 26;
  const circumference = 2 * Math.PI * r;
  const posLen = (nPositive / total) * circumference;
  const negLen = (nNegative / total) * circumference;
  return `<svg viewBox="0 0 180 180" width="180" height="180">
    <circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="#241d16" stroke-width="${stroke}" />
    <circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="#5cb37a" stroke-width="${stroke}"
      stroke-dasharray="${posLen} ${circumference - posLen}" stroke-dashoffset="0" transform="rotate(-90 ${cx} ${cy})" />
    <circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="#d9705f" stroke-width="${stroke}"
      stroke-dasharray="${negLen} ${circumference - negLen}" stroke-dashoffset="${-posLen}" transform="rotate(-90 ${cx} ${cy})" />
    <text x="${cx}" y="${cy - 4}" text-anchor="middle" font-size="22" font-weight="700" fill="#f3ede4">${Math.round((nPositive / total) * 100)}%</text>
    <text x="${cx}" y="${cy + 16}" text-anchor="middle" font-size="10" fill="#766b5c">positive</text>
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
      return `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${barW.toFixed(1)}" height="${barH.toFixed(1)}" rx="4" fill="#c9992e" />
        <text x="${(x + barW / 2).toFixed(1)}" y="${(y - 6).toFixed(1)}" text-anchor="middle" font-size="10" fill="#f3ede4">${b.count}</text>
        <text x="${(x + barW / 2).toFixed(1)}" y="${h - 6}" text-anchor="middle" font-size="9" fill="#766b5c">${b.label}</text>`;
    })
    .join("");
  return `<svg viewBox="0 0 ${w} ${h}" width="${w}" height="${h}">
    <line x1="${padLeft}" y1="${h - padBottom}" x2="${w}" y2="${h - padBottom}" stroke="#322a20" />
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
      <div><div class="label" style="color:#5cb37a;">Positive-leaning</div><div class="word-chips">${chips(words.top_positive_words, "positive")}</div></div>
      <div><div class="label" style="color:#d9705f;">Negative-leaning</div><div class="word-chips">${chips(words.top_negative_words, "negative")}</div></div>
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
        <h3>Fake Review Screening</h3>
        ${
          fake.available
            ? `<div class="value" style="color:#d9705f;">${fake.flagged_pct.toFixed(1)}%</div>
               <div class="note" style="margin-top:0.2rem;">${fake.n_flagged_fake.toLocaleString()} of ${fake.n_screened_negative.toLocaleString()} negative reviews flagged</div>`
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
  body { font-family: -apple-system, "Segoe UI", Inter, sans-serif; background: #100e0c; color: #f3ede4; margin: 0; padding: 2.5rem 2rem; }
  h1 { font-size: 1.5rem; margin: 0 0 0.25rem; }
  .sub { color: #a89c8a; font-size: 0.85rem; margin-bottom: 2rem; }
  .kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 0.9rem; margin-bottom: 2rem; max-width: 900px; }
  .kpi { background: #1c1712; border: 1px solid #322a20; border-radius: 14px; padding: 1rem 1.2rem; }
  .kpi .label { color: #766b5c; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.03em; }
  .kpi .value { font-size: 1.6rem; font-weight: 700; margin-top: 0.25rem; }
  .charts-row { display: flex; gap: 1.5rem; flex-wrap: wrap; margin-bottom: 2rem; }
  .chart-box { background: #1c1712; border: 1px solid #322a20; border-radius: 14px; padding: 1.2rem 1.4rem; }
  .chart-box h3 { margin: 0 0 0.8rem; font-size: 0.8rem; color: #a89c8a; text-transform: uppercase; letter-spacing: 0.03em; font-weight: 600; }
  .legend-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 0.4rem; }
  table { border-collapse: collapse; width: 100%; max-width: 1000px; font-size: 0.85rem; }
  th, td { text-align: left; padding: 0.5rem 0.7rem; border-bottom: 1px solid #241d16; }
  th { color: #766b5c; text-transform: uppercase; font-size: 0.68rem; letter-spacing: 0.03em; }
  td.text { max-width: 420px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .label.positive { color: #5cb37a; font-weight: 700; }
  .label.negative { color: #d9705f; font-weight: 700; }
  .note { color: #766b5c; font-size: 0.78rem; margin-top: 1rem; }
  .word-chips { display: flex; flex-wrap: wrap; gap: 0.35rem; margin-top: 0.6rem; }
  .word-chip { padding: 0.2rem 0.55rem; border-radius: 6px; border: 1px solid; font-size: 0.82rem; }
  .word-chip.positive { border-color: #3c6b4c; background: rgba(92,179,122,0.14); color: #f3ede4; }
  .word-chip.negative { border-color: #7a3b30; background: rgba(217,112,95,0.14); color: #f3ede4; }
</style></head>
<body>
  <h1>${escapeHtml(result.filename)}</h1>
  <div class="sub">Classified by ${APP_NAME} · model: ${result.model_name} · column used: ${escapeHtml(result.text_column_used)} · generated ${new Date().toLocaleString()}</div>
  <div class="kpis">
    <div class="kpi"><div class="label">Rows Processed</div><div class="value">${result.rows_processed.toLocaleString()}</div></div>
    <div class="kpi"><div class="label">Positive</div><div class="value" style="color:#5cb37a">${posPct.toFixed(1)}%</div></div>
    <div class="kpi"><div class="label">Negative</div><div class="value" style="color:#d9705f">${negPct.toFixed(1)}%</div></div>
    <div class="kpi"><div class="label">Skipped</div><div class="value">${result.n_skipped_empty_or_error.toLocaleString()}</div></div>
  </div>
  <div class="charts-row">
    <div class="chart-box">
      <h3>Sentiment Split</h3>
      ${donut}
      <div style="margin-top:0.6rem;font-size:0.78rem;color:#a89c8a;">
        <div><span class="legend-dot" style="background:#5cb37a"></span>Positive — ${result.n_positive.toLocaleString()}</div>
        <div><span class="legend-dot" style="background:#d9705f"></span>Negative — ${result.n_negative.toLocaleString()}</div>
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
  <p class="note">Sentiment predictions are probabilistic and dataset-dependent, not objective judgments.</p>
</body></html>`;
}

export function BatchUploadPage() {
  const { result, loading, error, upload, clearSaved } = useFileUpload();
  const [modelName, setModelName] = useState<ModelName>("bert");
  const [advanced, setAdvanced] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  function handleFile(file: File | undefined) {
    if (!file) return;
    setSelectedFile(file);
    upload(file, modelName, advanced);
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragActive(false);
    handleFile(e.dataTransfer.files?.[0]);
  }

  function handleInputChange(e: ChangeEvent<HTMLInputElement>) {
    handleFile(e.target.files?.[0]);
  }

  return (
    <div className="page">
      <span className="eyebrow">Batch Analyzer</span>
      <h1>Classify a whole file of reviews at once</h1>
      <p className="page-subtitle">
        Upload a CSV or Excel file with a review-text column (any common name — the file's own
        review text column, e.g. <code>review_comment_message_en</code>, <code>text</code>,{" "}
        <code>review</code>, is auto-detected). Every row is classified Positive or Negative, up
        to 2,000 rows per upload. Results are saved for 7 days, so reloading this page won't lose them.
      </p>

      <div className="upload-row" style={{ display: "flex", gap: "1.5rem", flexWrap: "wrap", alignItems: "flex-end" }}>
        <label>
          Model
          <select value={modelName} onChange={(e) => setModelName(e.target.value as ModelName)}>
            {MODEL_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </label>
        <label className="checkbox-label" style={{ marginBottom: "0.55rem" }}>
          <input type="checkbox" checked={advanced} onChange={(e) => setAdvanced(e.target.checked)} />
          Advanced analysis (fake-review + aspects — slower, sampled)
        </label>
      </div>

      <div
        className={`dropzone ${dragActive ? "active" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
        onDragLeave={() => setDragActive(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
      >
        <input ref={inputRef} type="file" accept=".csv,.xlsx,.xls" onChange={handleInputChange} style={{ display: "none" }} />
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M12 15V4M12 4l-4 4M12 4l4 4M5 15v3a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <span>{selectedFile ? selectedFile.name : "Drop a .csv or .xlsx file here, or click to browse"}</span>
      </div>

      {loading && <LoadingState label="Classifying rows..." />}
      <ErrorState error={error} />

      {result && (
        <div className="upload-results">
          {result.expires_at && (
            <p className="limitations-note">
              Restored from a saved upload ({result.filename}) — available until{" "}
              {new Date(result.expires_at).toLocaleString()}.{" "}
              <button type="button" className="explain-trigger" style={{ padding: "0.15rem 0.6rem", marginLeft: "0.4rem" }} onClick={clearSaved}>
                Clear & upload a new file
              </button>
            </p>
          )}
          <div className="kpi-grid">
            <div className="kpi-card">
              <div className="kpi-label">Rows Processed</div>
              <div className="kpi-value">{formatNumber(result.rows_processed)}</div>
              {result.truncated && <div className="kpi-sub">Truncated from {formatNumber(result.total_rows_in_file)} (max {formatNumber(result.max_rows_supported)})</div>}
            </div>
            <div className="kpi-card">
              <div className="kpi-label">Positive</div>
              <div className="kpi-value" style={{ color: "var(--positive)" }}>{formatPercent(result.positive_pct)}</div>
              <div className="kpi-sub">{formatNumber(result.n_positive)} reviews</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">Negative</div>
              <div className="kpi-value" style={{ color: "var(--negative)" }}>{formatPercent(result.negative_pct)}</div>
              <div className="kpi-sub">{formatNumber(result.n_negative)} reviews</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">Skipped</div>
              <div className="kpi-value">{formatNumber(result.n_skipped_empty_or_error)}</div>
              <div className="kpi-sub">empty or errored rows</div>
            </div>
          </div>

          <div className="chart-grid" style={{ marginBottom: "1.75rem" }}>
            <section className="chart-card">
              <h2>Sentiment Split</h2>
              <SentimentSplitChart nPositive={result.n_positive} nNegative={result.n_negative} />
            </section>
            <section className="chart-card">
              <h2>Confidence Distribution</h2>
              <ConfidenceHistogramChart results={result.results} />
            </section>
          </div>

          {result.top_words && (result.top_words.top_positive_words.length > 0 || result.top_words.top_negative_words.length > 0) && (
            <div className="chart-card" style={{ marginBottom: "1.75rem" }}>
              <h2>Most Influential Words</h2>
              <p className="limitations-note" style={{ marginTop: "-0.4rem", marginBottom: "0.9rem" }}>
                Words that show up disproportionately in Positive vs. Negative reviews in this file (frequency-based, not per-row SHAP).
              </p>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "1.25rem" }}>
                <div>
                  <div className="kpi-label" style={{ color: "var(--positive)" }}>Positive-leaning</div>
                  <div className="token-chip-list">
                    {result.top_words.top_positive_words.map((w) => (
                      <span key={w.word} className="token-chip" style={{ background: "var(--positive-soft)", borderColor: "var(--positive-border)" }} title={`${w.count} occurrences`}>
                        {w.word}
                      </span>
                    ))}
                  </div>
                </div>
                <div>
                  <div className="kpi-label" style={{ color: "var(--negative)" }}>Negative-leaning</div>
                  <div className="token-chip-list">
                    {result.top_words.top_negative_words.map((w) => (
                      <span key={w.word} className="token-chip" style={{ background: "var(--negative-soft)", borderColor: "var(--negative-border)" }} title={`${w.count} occurrences`}>
                        {w.word}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {result.time_trend?.available && (
            <div className="chart-card" style={{ marginBottom: "1.75rem" }}>
              <h2>Sentiment Trend ({result.time_trend.date_column_used})</h2>
              <SentimentTrendChart data={result.time_trend.points} />
            </div>
          )}

          {(result.fake_review_summary || result.aspect_summary) && (
            <div className="chart-grid" style={{ marginBottom: "1.75rem" }}>
              {result.fake_review_summary && (
                <section className="chart-card">
                  <h2>Fake Review Screening</h2>
                  {result.fake_review_summary.available ? (
                    <>
                      <div className="kpi-value" style={{ color: "var(--negative)" }}>{formatPercent(result.fake_review_summary.flagged_pct)}</div>
                      <div className="kpi-sub">
                        {formatNumber(result.fake_review_summary.n_flagged_fake)} of {formatNumber(result.fake_review_summary.n_screened_negative)} negative reviews flagged
                      </div>
                      <p className="limitations-note" style={{ marginTop: "0.9rem" }}>{result.fake_review_summary.methodology_note}</p>
                    </>
                  ) : (
                    <p className="limitations-note">Not available ({result.fake_review_summary.reason}).</p>
                  )}
                </section>
              )}
              {result.aspect_summary && (
                <section className="chart-card">
                  <h2>Aspect Breakdown</h2>
                  {result.aspect_summary.available ? (
                    <>
                      <AspectBreakdownChart data={result.aspect_summary.per_aspect} />
                      <p className="limitations-note" style={{ marginTop: "0.9rem" }}>{result.aspect_summary.methodology_note}</p>
                    </>
                  ) : (
                    <p className="limitations-note">Not available ({result.aspect_summary.reason}).</p>
                  )}
                </section>
              )}
            </div>
          )}

          <div className="chart-card">
            <div className="upload-results-header">
              <h2>Results — column used: {result.text_column_used}</h2>
              <div style={{ display: "flex", gap: "0.6rem", flexWrap: "wrap" }}>
                <button
                  type="button"
                  className="explain-trigger"
                  onClick={() => downloadBlob(`${result.filename}-dashboard.html`, buildDashboardHtml(result), "text/html")}
                >
                  Download dashboard (HTML)
                </button>
                <button
                  type="button"
                  className="explain-trigger"
                  onClick={() => downloadBlob(`${result.filename}-classified.csv`, resultsToCsv(result.results), "text/csv")}
                >
                  Download results (CSV)
                </button>
              </div>
            </div>
            <div style={{ overflowX: "auto" }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Row</th>
                    <th>Text</th>
                    <th>Label</th>
                    <th>Confidence</th>
                  </tr>
                </thead>
                <tbody>
                  {result.results.slice(0, 200).map((r) => (
                    <tr key={r.row}>
                      <td>{r.row}</td>
                      <td style={{ maxWidth: 420, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.text}</td>
                      <td style={{ color: r.label === "Positive" ? "var(--positive)" : r.label === "Negative" ? "var(--negative)" : "var(--text-faint)", fontWeight: 600 }}>
                        {r.label}
                      </td>
                      <td>{r.confidence !== undefined ? formatPercent(r.confidence * 100, 0) : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {result.results.length > 200 && (
                <p className="limitations-note">Showing first 200 of {formatNumber(result.results.length)} rows — download the CSV for the full list.</p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
