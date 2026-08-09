import { ChangeEvent, DragEvent, useRef, useState } from "react";
import { ErrorState } from "../components/ErrorState";
import { LoadingState } from "../components/LoadingState";
import { useFileUpload } from "../hooks/useSentiment";
import { MODEL_OPTIONS } from "../utils/constants";
import { formatNumber, formatPercent } from "../utils/formatters";
import type { FileRowResult, ModelName } from "../types/sentiment";

function resultsToCsv(filename: string, results: FileRowResult[]): string {
  const header = "row,label,confidence,probability_positive,probability_negative,text\n";
  const escape = (v: string) => `"${v.replace(/"/g, '""')}"`;
  const rows = results
    .map((r) =>
      [
        r.row,
        r.label,
        r.confidence ?? "",
        r.probability_positive ?? "",
        r.probability_negative ?? "",
        escape(r.text),
      ].join(","),
    )
    .join("\n");
  return header + rows;
}

function downloadCsv(filename: string, content: string) {
  const blob = new Blob([content], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export function BatchUploadPage() {
  const { result, loading, error, upload } = useFileUpload();
  const [modelName, setModelName] = useState<ModelName>("bert");
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  function handleFile(file: File | undefined) {
    if (!file) return;
    setSelectedFile(file);
    upload(file, modelName);
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
        to 2,000 rows per upload.
      </p>

      <div className="upload-row">
        <label>
          Model
          <select value={modelName} onChange={(e) => setModelName(e.target.value as ModelName)}>
            {MODEL_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
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

          <div className="chart-card">
            <div className="upload-results-header">
              <h2>Results — column used: {result.text_column_used}</h2>
              <button
                type="button"
                className="explain-trigger"
                onClick={() => downloadCsv(`${result.filename}-classified.csv`, resultsToCsv(result.filename, result.results))}
              >
                Download results (CSV)
              </button>
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
