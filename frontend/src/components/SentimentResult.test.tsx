import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SentimentResult } from "./SentimentResult";
import type { SentimentPrediction } from "../types/sentiment";

const basePrediction: SentimentPrediction = {
  label: "Positive",
  class_id: 1,
  probability_positive: 0.87,
  probability_negative: 0.13,
  confidence: 0.87,
  model_name: "cnn2d",
  source_language: "en",
  translated: false,
  cleaned_text: "great product",
  analysis_id: null,
};

describe("SentimentResult", () => {
  it("renders a Positive verdict with its confidence", () => {
    const { container } = render(<SentimentResult result={basePrediction} />);
    expect(container.querySelector(".sentiment-result-label")).toHaveTextContent("Positive");
    expect(screen.getByText(/87.*confidence/)).toBeInTheDocument();
  });

  it("renders a Negative verdict distinctly from Positive", () => {
    const negative: SentimentPrediction = { ...basePrediction, label: "Negative", probability_positive: 0.1, probability_negative: 0.9, confidence: 0.9 };
    const { container } = render(<SentimentResult result={negative} />);
    expect(container.querySelector(".sentiment-result-label")).toHaveTextContent("Negative");
    expect(container.querySelector(".sentiment-result.negative")).not.toBeNull();
  });

  it("shows the model name used", () => {
    render(<SentimentResult result={basePrediction} />);
    expect(screen.getByText(/cnn2d/)).toBeInTheDocument();
  });

  it("shows a feedback prompt only when an analysisId is available", () => {
    const { rerender } = render(<SentimentResult result={basePrediction} analysisId={null} />);
    expect(screen.queryByText(/Was this right/)).not.toBeInTheDocument();

    rerender(<SentimentResult result={basePrediction} analysisId="abc123" />);
    expect(screen.getByText(/Was this right/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Prediction was correct/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Prediction was wrong/ })).toBeInTheDocument();
  });
});
