/**
 * Illustrative content for the landing page only. Every number here is a
 * hand-picked round figure chosen to *look* like a plausible dashboard --
 * none of it is queried from the API or copied from the real, audited
 * metrics in README.md/results/*.json. Every component that renders this
 * data must pair it with a <DemoDataBadge> (or equivalent inline label) so
 * nothing on the landing page can be mistaken for a live production figure
 * (product decision 9). This file has no backend dependency and never will
 * -- if the landing page needs real numbers, that's a Phase 3+ decision.
 */

export interface DemoReview {
  id: string;
  text: string;
  sentiment: "positive" | "negative" | "mixed";
  aspect: string;
}

export const DEMO_REVIEWS: DemoReview[] = [
  { id: "r1", text: "The product quality is excellent, but delivery took longer than expected.", sentiment: "mixed", aspect: "Delivery" },
  { id: "r2", text: "Customer support solved my issue quickly and professionally.", sentiment: "positive", aspect: "Customer support" },
  { id: "r3", text: "The latest update made the checkout process confusing.", sentiment: "negative", aspect: "Checkout experience" },
];

export const RECENT_REVIEWS: DemoReview[] = [
  ...DEMO_REVIEWS,
  { id: "r4", text: "Packaging was solid and the item arrived without a scratch.", sentiment: "positive", aspect: "Product quality" },
  { id: "r5", text: "Price felt fair for what shipped, would order again.", sentiment: "positive", aspect: "Value for money" },
];

export const SENTIMENT_SPLIT = { positive: 64, neutral: 18, negative: 18 };

export interface TrendPoint {
  label: string;
  positivePct: number;
}

/** Six illustrative points -- shaped like the real `/analytics/*monthly` and
 * sentiment time-trend endpoints, but the values are invented for display. */
export const SENTIMENT_TREND: TrendPoint[] = [
  { label: "Mar", positivePct: 54 },
  { label: "Apr", positivePct: 58 },
  { label: "May", positivePct: 55 },
  { label: "Jun", positivePct: 61 },
  { label: "Jul", positivePct: 60 },
  { label: "Aug", positivePct: 64 },
];

export interface PainPoint {
  category: string;
  negativeMentionPct: number;
}

/** Demonstration categories -- close to, but not identical with, the real
 * backend's fixed 5-aspect ABSA set (delivery, product quality, price,
 * customer service, packaging). Never claim these are pulled from the
 * dataset; label every use as demonstration. */
export const PAIN_POINTS: PainPoint[] = [
  { category: "Delivery", negativeMentionPct: 34 },
  { category: "Checkout experience", negativeMentionPct: 22 },
  { category: "Customer support", negativeMentionPct: 17 },
  { category: "Value for money", negativeMentionPct: 15 },
  { category: "Product quality", negativeMentionPct: 12 },
];

export interface SourceBreakdownRow {
  label: string;
  pct: number;
}

export const SOURCE_BREAKDOWN: SourceBreakdownRow[] = [
  { label: "Historical Olist dataset", pct: 71 },
  { label: "CSV batch upload", pct: 24 },
  { label: "Manual single review", pct: 5 },
];

export const DEMO_KPIS = {
  totalReviews: 1240,
  overallPositivePct: 64,
  topPainPoint: "Delivery",
  categoriesTracked: 5,
};

export const RULE_BASED_RECOMMENDATION = {
  text: "Delivery-related negative sentiment increased in the selected period. Review carrier performance and communicate clearer delivery estimates.",
  basis: "Triggered by: negative-mention rate for the “Delivery” category rising above its trailing average.",
};

/** First 3 are presented as the primary, prominent capabilities (the core
 * collect -> score -> explain loop); the rest render in the compact
 * secondary grid. Order is deliberate -- wording is unchanged from Phase 2. */
export const CAPABILITIES: Array<{ title: string; description: string }> = [
  { title: "Sentiment Analysis", description: "BERT and CNN2D models classify each review as positive or negative from its text alone." },
  { title: "Aspect-Based Insights", description: "Sentiment broken down per aspect -- delivery, product quality, price, service, packaging." },
  { title: "Batch Review Processing", description: "Upload a CSV of reviews and get predictions, aspects, and a confidence distribution back in one pass." },
  { title: "Customer Segmentation", description: "RFM + K-Means groups customers into Champion, Loyal, Potential Loyal, and At Risk segments." },
  { title: "Product & Seller Analytics", description: "Category performance and seller-level delivery/revenue metrics from the enriched order data." },
  { title: "Geographic Analytics", description: "State-level delivery performance across the dataset's coverage area." },
  { title: "Model Transparency", description: "SHAP explanations and documented, corrected accuracy metrics for every shipped model." },
];

export const PRIMARY_CAPABILITY_COUNT = 3;

export const JOURNEY_STAGES: Array<{ stage: string; title: string; description: string }> = [
  { stage: "Collect", title: "Bring reviews in", description: "Analyze a single review by hand, or upload a CSV batch for bulk processing." },
  { stage: "Analyze", title: "Score sentiment", description: "BERT/CNN2D classify each review as positive or negative from its text alone." },
  { stage: "Understand", title: "Surface the aspects", description: "Aspect-level scoring shows which part of the experience -- delivery, price, service -- is driving the sentiment." },
  { stage: "Decide", title: "Act with confidence", description: "Pain points and trends turn into rule-based, honestly-labeled recommendations a team can act on." },
];
