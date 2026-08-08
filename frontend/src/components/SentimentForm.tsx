import { FormEvent, useState } from "react";
import { LANGUAGE_OPTIONS, MODEL_OPTIONS } from "../utils/constants";
import type { FullPipelineRequest, ModelName } from "../types/sentiment";

interface Props {
  onSubmit: (request: FullPipelineRequest) => void;
  loading: boolean;
}

export function SentimentForm({ onSubmit, loading }: Props) {
  const [text, setText] = useState("");
  const [modelName, setModelName] = useState<ModelName>("bert");
  const [sourceLanguage, setSourceLanguage] = useState<"en" | "pt">("en");
  const [translate, setTranslate] = useState(false);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    onSubmit({ text, model_name: modelName, source_language: sourceLanguage, translate });
  }

  return (
    <form className="sentiment-form" onSubmit={handleSubmit}>
      <textarea
        placeholder="Paste a customer review here..."
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={5}
        maxLength={2000}
      />
      <div className="sentiment-form-row">
        <label>
          Model
          <select value={modelName} onChange={(e) => setModelName(e.target.value as ModelName)}>
            {MODEL_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </label>
        <label>
          Language
          <select value={sourceLanguage} onChange={(e) => setSourceLanguage(e.target.value as "en" | "pt")}>
            {LANGUAGE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </label>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={translate}
            disabled={sourceLanguage !== "pt"}
            onChange={(e) => setTranslate(e.target.checked)}
          />
          Translate before analyzing
        </label>
      </div>
      <button type="submit" disabled={loading || !text.trim()}>
        {loading ? "Analyzing..." : "Analyze"}
      </button>
    </form>
  );
}
