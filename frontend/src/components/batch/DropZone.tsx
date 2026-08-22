import { ChangeEvent, DragEvent, KeyboardEvent, useId, useRef, useState } from "react";
import { Button } from "../ui/Button";
import { formatBytes } from "../../utils/formatters";
import { FileIcon, UploadCloudIcon, XIcon } from "./icons";

interface DropZoneProps {
  selectedFile: File | null;
  onFileSelected: (file: File) => void;
  onRemove: () => void;
  disabled?: boolean;
  accept: string;
  acceptLabel: string;
  maxSizeLabel: string;
  maxRowsLabel: string;
  statusLabel?: string;
}

export function DropZone({
  selectedFile, onFileSelected, onRemove, disabled = false, accept, acceptLabel, maxSizeLabel, maxRowsLabel, statusLabel,
}: DropZoneProps) {
  const [dragActive, setDragActive] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const labelId = useId();
  const descId = useId();

  function openPicker() {
    if (!disabled) inputRef.current?.click();
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragActive(false);
    if (disabled) return;
    const file = e.dataTransfer.files?.[0];
    if (file) onFileSelected(file);
  }

  function handleInputChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) onFileSelected(file);
    e.target.value = "";
  }

  function handleKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      openPicker();
    }
  }

  if (selectedFile) {
    return (
      <div className="bsr-batch-file-summary">
        <span className="bsr-batch-file-summary__icon" aria-hidden="true">
          <FileIcon />
        </span>
        <div className="bsr-batch-file-summary__info">
          <span className="bsr-batch-file-summary__name">{selectedFile.name}</span>
          <span className="bsr-sm" style={{ color: "var(--bsr-text-faint)" }}>
            {formatBytes(selectedFile.size)}
            {statusLabel ? ` · ${statusLabel}` : ""}
          </span>
        </div>
        <div className="bsr-batch-file-summary__actions">
          <Button type="button" variant="ghost" onClick={openPicker} disabled={disabled}>
            Replace
          </Button>
          <Button type="button" variant="ghost" leftIcon={<XIcon />} onClick={onRemove} disabled={disabled} aria-label="Remove selected file">
            Remove
          </Button>
        </div>
        <input ref={inputRef} type="file" accept={accept} onChange={handleInputChange} className="bsr-visually-hidden" tabIndex={-1} aria-hidden="true" />
      </div>
    );
  }

  return (
    <div
      className={`bsr-batch-dropzone${dragActive ? " bsr-batch-dropzone--active" : ""}${disabled ? " bsr-batch-dropzone--disabled" : ""}`}
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-labelledby={labelId}
      aria-describedby={descId}
      aria-disabled={disabled || undefined}
      onClick={openPicker}
      onKeyDown={handleKeyDown}
      onDragOver={(e) => { e.preventDefault(); if (!disabled) setDragActive(true); }}
      onDragLeave={() => setDragActive(false)}
      onDrop={handleDrop}
    >
      <input ref={inputRef} type="file" accept={accept} onChange={handleInputChange} className="bsr-visually-hidden" tabIndex={-1} aria-hidden="true" />
      <span className="bsr-batch-dropzone__icon" aria-hidden="true">
        <UploadCloudIcon />
      </span>
      <span id={labelId} className="bsr-body" style={{ fontWeight: 600 }}>
        Drop a file here, or click to browse
      </span>
      <span id={descId} className="bsr-sm" style={{ color: "var(--bsr-text-faint)" }}>
        {acceptLabel} · up to {maxSizeLabel} · {maxRowsLabel}
      </span>
    </div>
  );
}
