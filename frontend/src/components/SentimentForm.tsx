import { FormEvent, useId, useState } from "react";
import { Button } from "./ui/Button";
import { SparkleIcon, TrashIcon } from "./sentiment/icons";
import { ABSA_MODEL_OPTIONS, LANGUAGE_OPTIONS, MODEL_OPTIONS } from "../utils/constants";
import type { AbsaModel, FullPipelineRequest, ModelName } from "../types/sentiment";

const MAX_LENGTH = 2000;
const SAMPLE_REVIEW =
  "The product arrived two days late and the box was damaged, but the item itself works fine. " +
  "Customer service was slow to respond to my first message. Not what I expected for the price.";

interface Props {
  onSubmit: (request: FullPipelineRequest) => void;
  loading: boolean;
}

export function SentimentForm({ onSubmit, loading }: Props) {
  const [text, setText] = useState("");
  const [modelName, setModelName] = useState<ModelName>("bert");
  const [absaModel, setAbsaModel] = useState<AbsaModel>("cnn2d");
  const [sourceLanguage, setSourceLanguage] = useState<"en" | "pt">("en");
  const [translate, setTranslate] = useState(false);
  const [touched, setTouched] = useState(false);

  const textareaId = useId();
  const hintId = useId();
  const counterId = useId();
  const validationId = useId();

  const trimmedLength = text.trim().length;
  const isBlank = trimmedLength === 0;
  const showValidation = touched && isBlank;
  const nearLimit = text.length >= MAX_LENGTH * 0.9;
  const atLimit = text.length >= MAX_LENGTH;

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setTouched(true);
    if (isBlank || loading) return;
    onSubmit({ text, model_name: modelName, source_language: sourceLanguage, translate, absa_model: absaModel });
  }

  function fillSample() {
    setText(SAMPLE_REVIEW);
    setTouched(false);
  }

  function clearText() {
    setText("");
    setTouched(false);
  }

  const describedBy = [hintId, counterId, showValidation ? validationId : null].filter(Boolean).join(" ");

  return (
    <form className="bsr-sentiment-form" onSubmit={handleSubmit} noValidate>
      <div className="bsr-sentiment-form__field">
        <label className="bsr-sentiment-form__label" htmlFor={textareaId}>
          Customer review
        </label>
        <p className="bsr-sm bsr-sentiment-form__hint" id={hintId}>
          Paste one customer review in English or Portuguese. It's analyzed on its own -- no account, order, or product data is used.
        </p>
        <textarea
          id={textareaId}
          className="bsr-sentiment-textarea"
          placeholder="e.g. “Delivery was fast and the product matched the description perfectly.”"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onBlur={() => setTouched(true)}
          rows={7}
          maxLength={MAX_LENGTH}
          aria-invalid={showValidation || undefined}
          aria-describedby={describedBy}
        />
        <div className="bsr-sentiment-textarea-foot">
          <span
            id={counterId}
            className={`bsr-caption bsr-sentiment-counter${atLimit ? " bsr-sentiment-counter--at-limit" : nearLimit ? " bsr-sentiment-counter--near-limit" : ""}`}
          >
            {text.length.toLocaleString()} / {MAX_LENGTH.toLocaleString()}
          </span>
          {showValidation && (
            <span id={validationId} role="alert" className="bsr-sm bsr-sentiment-validation">
              Enter a review before analyzing -- blank or whitespace-only text can't be submitted.
            </span>
          )}
        </div>
        <div className="bsr-sentiment-form__tools">
          <Button type="button" variant="ghost" leftIcon={<SparkleIcon />} onClick={fillSample}>
            Try a demonstration review
          </Button>
          <Button type="button" variant="ghost" leftIcon={<TrashIcon />} onClick={clearText} disabled={text.length === 0}>
            Clear
          </Button>
        </div>
      </div>

      <div className="bsr-sentiment-form__row">
        <label className="bsr-sentiment-field-label">
          Model
          <select className="bsr-sentiment-select" value={modelName} onChange={(e) => setModelName(e.target.value as ModelName)}>
            {MODEL_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </label>
        <label className="bsr-sentiment-field-label">
          ABSA model
          <select className="bsr-sentiment-select" value={absaModel} onChange={(e) => setAbsaModel(e.target.value as AbsaModel)}>
            {ABSA_MODEL_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </label>
        <label className="bsr-sentiment-field-label">
          Review language
          <select className="bsr-sentiment-select" value={sourceLanguage} onChange={(e) => setSourceLanguage(e.target.value as "en" | "pt")}>
            {LANGUAGE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </label>
        <label className="bsr-sentiment-checkbox-row">
          <input
            type="checkbox"
            checked={translate}
            disabled={sourceLanguage !== "pt"}
            onChange={(e) => setTranslate(e.target.checked)}
          />
          Translate before analyzing
        </label>
      </div>

      <div className="bsr-sentiment-submit-row">
        <Button
          type="submit"
          variant="primary"
          disabled={isBlank}
          loading={loading}
          loadingLabel="Analyzing review…"
        >
          {loading ? "Analyzing review…" : "Analyze review"}
        </Button>
      </div>
    </form>
  );
}
