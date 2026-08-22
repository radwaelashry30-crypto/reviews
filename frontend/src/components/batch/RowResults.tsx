import { useState } from "react";
import { StatusPill } from "../ui/Badge";
import { ChevronDownIcon } from "./icons";
import type { FileRowResult } from "../../types/sentiment";
import { formatPercent } from "../../utils/formatters";

const PREVIEW_LENGTH = 140;

function labelTone(label: FileRowResult["label"]) {
  if (label === "Positive") return "positive" as const;
  if (label === "Negative") return "negative" as const;
  return "warning" as const;
}

/**
 * `text` here is already a backend-side preview (truncated to 300 characters
 * server-side, see file_batch_service.py), not the full original review --
 * "show more" reveals that full stored preview, not a longer original text
 * the frontend doesn't have.
 */
function RowText({ text }: { text: string }) {
  const [expanded, setExpanded] = useState(false);
  if (text.length <= PREVIEW_LENGTH) return <span>{text}</span>;
  return (
    <span>
      {expanded ? text : `${text.slice(0, PREVIEW_LENGTH)}…`}{" "}
      <button type="button" className="bsr-batch-row-expand" onClick={() => setExpanded((v) => !v)}>
        {expanded ? "Show less" : "Show more"}
      </button>
    </span>
  );
}

export function RowResultsTable({ rows }: { rows: FileRowResult[] }) {
  return (
    <table className="bsr-batch-table">
      <thead>
        <tr>
          <th scope="col">Row</th>
          <th scope="col">Review preview</th>
          <th scope="col">Sentiment</th>
          <th scope="col">Confidence</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.row}>
            <td className="bsr-mono">{r.row}</td>
            <td className="bsr-batch-table__text">
              <RowText text={r.text} />
            </td>
            <td>
              {r.label === "ERROR" ? (
                <StatusPill tone="warning">Error</StatusPill>
              ) : (
                <StatusPill tone={labelTone(r.label)}>{r.label}</StatusPill>
              )}
            </td>
            <td className="bsr-mono">
              {r.label === "ERROR" ? (
                <span className="bsr-sm" style={{ color: "var(--bsr-text-faint)" }}>{r.error ?? "processing error"}</span>
              ) : r.confidence !== undefined ? (
                formatPercent(r.confidence * 100, 0)
              ) : (
                "—"
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function RowCard({ row }: { row: FileRowResult }) {
  const [expanded, setExpanded] = useState(false);
  const detailsId = `batch-row-${row.row}-details`;
  return (
    <li className="bsr-batch-card">
      <button
        type="button"
        className="bsr-batch-card__head"
        aria-expanded={expanded}
        aria-controls={detailsId}
        onClick={() => setExpanded((v) => !v)}
      >
        <span className="bsr-mono bsr-sm" style={{ color: "var(--bsr-text-faint)" }}>Row {row.row}</span>
        {row.label === "ERROR" ? <StatusPill tone="warning">Error</StatusPill> : <StatusPill tone={labelTone(row.label)}>{row.label}</StatusPill>}
        <ChevronDownIcon className={expanded ? "bsr-batch-card__chevron bsr-batch-card__chevron--open" : "bsr-batch-card__chevron"} aria-hidden="true" />
      </button>
      {expanded && (
        <div id={detailsId} className="bsr-batch-card__body">
          <p className="bsr-sm">{row.text}</p>
          {row.label === "ERROR" ? (
            <p className="bsr-sm" style={{ color: "var(--bsr-text-faint)" }}>{row.error ?? "processing error"}</p>
          ) : (
            row.confidence !== undefined && (
              <p className="bsr-sm" style={{ color: "var(--bsr-text-muted)" }}>{formatPercent(row.confidence * 100, 0)} confidence</p>
            )
          )}
        </div>
      )}
    </li>
  );
}

export function RowResultsCards({ rows }: { rows: FileRowResult[] }) {
  return (
    <ul className="bsr-batch-card-list">
      {rows.map((r) => (
        <RowCard key={r.row} row={r} />
      ))}
    </ul>
  );
}
