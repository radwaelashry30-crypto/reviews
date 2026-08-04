export const APP_NAME = "Olist Marketplace Platform";

export const MODEL_OPTIONS = [
  { value: "bert", label: "BERT (fine-tuned, primary)" },
  { value: "cnn2d", label: "CNN2D (from scratch)" },
] as const;

export const LANGUAGE_OPTIONS = [
  { value: "en", label: "English" },
  { value: "pt", label: "Portuguese" },
] as const;
