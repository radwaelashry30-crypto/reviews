import { FormEvent, useId, useState } from "react";
import { Button } from "../ui/Button";
import { useRfmPrediction } from "../../hooks/useSegmentation";
import { colorForSegment } from "./segmentColors";

/**
 * A genuine "what-if" tool over the real POST /segmentation/predict
 * endpoint -- not a fabricated customer. The user enters a hypothetical
 * Recency/Frequency/Monetary profile and sees which of the real trained
 * K-Means clusters it would fall into, using the exact same model that
 * classified every real customer. Validation mirrors the backend's own
 * constraints (recency>=0, frequency>=1, monetary>=0) exactly.
 */
export function RfmExplorer() {
  const { result, loading, error, predict } = useRfmPrediction();
  const [recency, setRecency] = useState("30");
  const [frequency, setFrequency] = useState("2");
  const [monetary, setMonetary] = useState("250");
  const [touched, setTouched] = useState(false);

  const recencyId = useId();
  const frequencyId = useId();
  const monetaryId = useId();
  const errorId = useId();

  const recencyNum = Number(recency);
  const frequencyNum = Number(frequency);
  const monetaryNum = Number(monetary);
  const isValid =
    recency !== "" && Number.isFinite(recencyNum) && recencyNum >= 0 &&
    frequency !== "" && Number.isFinite(frequencyNum) && frequencyNum >= 1 &&
    monetary !== "" && Number.isFinite(monetaryNum) && monetaryNum >= 0;

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setTouched(true);
    if (!isValid || loading) return;
    predict({ recency: recencyNum, frequency: frequencyNum, monetary: monetaryNum });
  }

  return (
    <form className="bsr-customers-explorer" onSubmit={handleSubmit} noValidate>
      <div className="bsr-customers-explorer__fields">
        <label className="bsr-customers-field-label" htmlFor={recencyId}>
          Recency (days since last order)
          <input
            id={recencyId}
            type="number"
            min={0}
            step="1"
            className="bsr-customers-input"
            value={recency}
            onChange={(e) => setRecency(e.target.value)}
            onBlur={() => setTouched(true)}
            aria-invalid={touched && !isValid || undefined}
            aria-describedby={touched && !isValid ? errorId : undefined}
          />
        </label>
        <label className="bsr-customers-field-label" htmlFor={frequencyId}>
          Frequency (distinct orders)
          <input
            id={frequencyId}
            type="number"
            min={1}
            step="1"
            className="bsr-customers-input"
            value={frequency}
            onChange={(e) => setFrequency(e.target.value)}
            onBlur={() => setTouched(true)}
            aria-invalid={touched && !isValid || undefined}
            aria-describedby={touched && !isValid ? errorId : undefined}
          />
        </label>
        <label className="bsr-customers-field-label" htmlFor={monetaryId}>
          Monetary (total spend, R$)
          <input
            id={monetaryId}
            type="number"
            min={0}
            step="0.01"
            className="bsr-customers-input"
            value={monetary}
            onChange={(e) => setMonetary(e.target.value)}
            onBlur={() => setTouched(true)}
            aria-invalid={touched && !isValid || undefined}
            aria-describedby={touched && !isValid ? errorId : undefined}
          />
        </label>
      </div>

      {touched && !isValid && (
        <p id={errorId} className="bsr-sm bsr-customers-explorer__error" role="alert">
          Recency must be 0 or more, frequency at least 1, and monetary 0 or more.
        </p>
      )}

      <div className="bsr-customers-explorer__submit">
        <Button type="submit" variant="primary" disabled={!isValid} loading={loading} loadingLabel="Classifying…">
          {loading ? "Classifying…" : "Classify this profile"}
        </Button>
        {result && (
          <div className="bsr-customers-explorer__result">
            <span
              className="bsr-customers-explorer__pill"
              style={{ borderColor: colorForSegment(result.segment_name), color: colorForSegment(result.segment_name) }}
            >
              <span className="bsr-customers-explorer__pill-dot" aria-hidden="true" style={{ background: colorForSegment(result.segment_name) }} />
              {result.segment_name}
            </span>
            <span className="bsr-sm" style={{ color: "var(--bsr-text-faint)" }}>
              Real prediction from the trained K-Means model (cluster {result.cluster_id})
            </span>
          </div>
        )}
      </div>

      {!loading && error && (
        <p className="bsr-sm bsr-customers-explorer__error" role="alert">
          Couldn't classify this profile: {error.message}
        </p>
      )}
    </form>
  );
}
