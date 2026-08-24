import { useState } from "react";
import { AspectsBreakdown } from "../components/AspectsBreakdown";
import { ExplanationCard } from "../components/ExplanationCard";
import { SentimentForm } from "../components/SentimentForm";
import { SentimentResult } from "../components/SentimentResult";
import { Button } from "../components/ui/Button";
import { DemoDataBadge } from "../components/ui/DemoDataBadge";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorState } from "../components/ui/ErrorState";
import { GlassCard } from "../components/ui/GlassCard";
import { SurfaceCard } from "../components/ui/SurfaceCard";
import { CheckIcon, CopyIcon, RefreshIcon } from "../components/sentiment/icons";
import { useExplanation, useFullPipeline } from "../hooks/useSentiment";
import type { FullPipelineRequest, FullPipelineResponse } from "../types/sentiment";
import "../styles/sentiment.css";

function buildResultSummary(result: FullPipelineResponse): string {
  const s = result.sentiment;
  const lines = [
    "Baseera review analysis",
    `Sentiment: ${s.label} (${(s.confidence * 100).toFixed(0)}% confidence)`,
    `Positive: ${(s.probability_positive * 100).toFixed(0)}% · Negative: ${(s.probability_negative * 100).toFixed(0)}%`,
    `Model: ${s.model_name}${s.translated ? " (translated before analysis)" : ""}`,
  ];

  if (result.aspects.available && result.aspects.aspects && result.aspects.aspects.length > 0) {
    lines.push("", "Aspects:");
    for (const a of result.aspects.aspects) lines.push(`  ${a.aspect}: ${a.sentiment}`);
  }

  return lines.join("\n");
}

export function SentimentPage() {
  const { result, loading, error, analyze, reset } = useFullPipeline();
  const explanation = useExplanation();
  const [lastRequest, setLastRequest] = useState<FullPipelineRequest | null>(null);
  const [formKey, setFormKey] = useState(0);
  const [copied, setCopied] = useState(false);

  function handleSubmit(request: FullPipelineRequest) {
    explanation.reset();
    setLastRequest(request);
    analyze(request);
  }

  function handleRetry() {
    if (lastRequest) analyze(lastRequest);
  }

  function handleAnalyzeAnother() {
    reset();
    explanation.reset();
    setLastRequest(null);
    setFormKey((k) => k + 1);
  }

  async function handleCopySummary() {
    if (!result) return;
    try {
      await navigator.clipboard.writeText(buildResultSummary(result));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard access can be denied by the browser -- fail silently rather
      // than surface an ErrorState for a non-critical convenience action.
    }
  }

  const canRetry = !!lastRequest && !!error && error.code !== "VALIDATION_ERROR";

  const liveMessage = loading
    ? "Analyzing review…"
    : error
      ? `Analysis failed: ${error.message}`
      : result
        ? `Analysis complete. ${result.sentiment.label} sentiment, ${(result.sentiment.confidence * 100).toFixed(0)} percent confidence.`
        : "";

  return (
    <div className="bsr-sentiment">
      <header className="bsr-sentiment-intro">
        <span className="bsr-label bsr-sentiment-intro__eyebrow">Review Analyzer</span>
        <h1 className="bsr-h1">Understand what one review is really saying</h1>
        <p className="bsr-body-lg">
          Paste one customer review and analyze its sentiment and the signals the models actually return -- confidence
          and per-aspect reaction. This is a demonstration project built on academic models; every result below is a
          probabilistic estimate, not a certainty.
        </p>
        <div className="bsr-sentiment-intro__notes">
          <DemoDataBadge kind="demo" label="Demonstration / academic project" />
          <DemoDataBadge kind="demo" label="Estimates, not certainties" />
        </div>
      </header>

      <div className="bsr-sentiment-workspace">
        <GlassCard className="bsr-sentiment-panel">
          <SentimentForm key={formKey} onSubmit={handleSubmit} loading={loading} />
        </GlassCard>

        <div className="bsr-sentiment-results">
          <div className="bsr-visually-hidden" role="status" aria-live="polite">
            {liveMessage}
          </div>

          {result && (
            <div className="bsr-sentiment-results__actions">
              <Button type="button" variant="secondary" leftIcon={<RefreshIcon />} onClick={handleAnalyzeAnother}>
                Analyze another review
              </Button>
              <Button type="button" variant="ghost" leftIcon={copied ? <CheckIcon /> : <CopyIcon />} onClick={handleCopySummary}>
                {copied ? "Copied" : "Copy result summary"}
              </Button>
            </div>
          )}

          {loading && (
            <SurfaceCard className="bsr-sentiment-panel">
              <div className="bsr-loading-state bsr-loading-state--full" aria-hidden="true">
                <span className="bsr-btn__spinner bsr-loading-state__spinner" aria-hidden="true" style={{ width: 24, height: 24 }} />
                <span className="bsr-body">Analyzing review…</span>
                <span className="bsr-sm" style={{ color: "var(--bsr-text-faint)" }}>Running sentiment and aspect analysis.</span>
              </div>
            </SurfaceCard>
          )}

          {!loading && error && (
            <SurfaceCard className="bsr-sentiment-panel">
              <ErrorState
                title={error.code === "VALIDATION_ERROR" ? "Review couldn't be submitted" : "Analysis failed"}
                message={error.message}
                code={error.code}
                onRetry={canRetry ? handleRetry : undefined}
              />
            </SurfaceCard>
          )}

          {!loading && !error && !result && (
            <SurfaceCard className="bsr-sentiment-panel bsr-sentiment-empty">
              <EmptyState
                title="Your analysis will appear here"
                description="Paste a review on the left and press Analyze -- sentiment, confidence, and aspect signals will show up in this panel."
              />
            </SurfaceCard>
          )}

          {!loading && result && (
            <div className="bsr-sentiment-fade-in" style={{ display: "flex", flexDirection: "column", gap: "var(--bsr-space-5)" }}>
              <SurfaceCard className="bsr-sentiment-panel" aria-label="Primary sentiment and confidence">
                <SentimentResult result={result.sentiment} analysisId={result.analysis_id} />
              </SurfaceCard>

              <SurfaceCard className="bsr-sentiment-panel" aria-label="Aspect-level breakdown">
                <AspectsBreakdown result={result.aspects} />
              </SurfaceCard>

              {result.sentiment.model_name === "bert" && (
                <SurfaceCard className="bsr-sentiment-panel" aria-label="Model explanation">
                  {!explanation.result && !explanation.loading ? (
                    <>
                      <div className="bsr-sentiment-card-head">
                        <span className="bsr-label">Explainable AI</span>
                        <Button type="button" variant="secondary" onClick={() => explanation.explain(result.sentiment.cleaned_text)}>
                          Explain this prediction
                        </Button>
                      </div>
                      <p className="bsr-sm" style={{ color: "var(--bsr-text-faint)" }}>
                        See which words pushed this specific prediction toward Positive or Negative (SHAP values, BERT only).
                      </p>
                    </>
                  ) : (
                    <ExplanationCard result={explanation.result} loading={explanation.loading} />
                  )}
                </SurfaceCard>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
