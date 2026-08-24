export const APP_NAME = "Baseera";
export const APP_TAGLINE = "Customer review intelligence for the Olist marketplace";

export const MODEL_OPTIONS = [
  { value: "bert", label: "BERT (fine-tuned, primary)" },
  { value: "cnn2d", label: "CNN2D (from scratch)" },
] as const;

export const LANGUAGE_OPTIONS = [
  { value: "en", label: "English" },
  { value: "pt", label: "Portuguese" },
] as const;

// CNN2D first and selected by default: it's the always-loaded, no-extra-memory
// path. DeBERTa is an optional, purpose-trained ABSA checkpoint -- slower to
// first-respond (lazy-loaded, ~738MB) but not claimed to be more accurate here;
// this project hasn't benchmarked either against Olist-specific ground truth.
export const ABSA_MODEL_OPTIONS = [
  { value: "cnn2d", label: "RAKE + CNN2D — Fast/Light" },
  { value: "deberta", label: "DeBERTa-v3 ABSA — Specialized/Slower" },
] as const;
