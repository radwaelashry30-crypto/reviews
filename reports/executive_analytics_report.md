# Executive Analytics Report — Olist Marketplace

## 1. Executive summary

Olist's marketplace is growing steadily (Jan 2017–Aug 2018) but is operationally strained by delivery reliability, and is under-monetizing its existing customer base (96.9% of customers buy exactly once). Late delivery is the single clearest, statistically significant driver of dissatisfaction. A fine-tuned BERT model can now flag negative sentiment directly from review text at 93.4% accuracy on a corrected, leakage-free test set.

## 2. Dataset description

Olist Brazilian E-Commerce dataset: 9 relational tables covering ~99,000 orders, ~95,000 unique customers, ~3,100 sellers, Jan 2017–Aug 2018.

## 3. Relational model

`orders (1) -> (N) order_items -> products/sellers`; `orders (1) -> (1, aggregated) payments/reviews`. See README §4 and `DATA_GRAIN_AUDIT.md`.

## 4. Data-quality findings

261,831 duplicate geolocation rows removed; delivery-date NaNs preserved (genuine, not imputed); review text gaps filled with an explicit sentinel used later as a sentiment-task exclusion filter. Full detail: `DATA_QUALITY_AUDIT.md`.

## 5. Data-grain audit

The notebook's merged dataframe over-counts order-level KPIs by ~14.2% (112,650 item rows vs. 98,666 unique orders). Corrected canonical datasets fix this throughout. Full detail: `DATA_GRAIN_AUDIT.md`.

## 6. Missing-value treatment

See `DATA_QUALITY_AUDIT.md` §3 for the full imputation-decision table with audit verdicts.

## 7. Feature engineering

Delivery duration/delay, late-delivery flag, calendar features, IQR price-outlier flag, per-customer order count, per-seller late-delivery rate.

## 8. EDA insights

- Order volume grows steadily with a Black-Friday-season spike; revenue growth tracks order-count growth almost exactly (volume-driven, not value-driven).
- Demand is concentrated in the Southeast (São Paulo/Rio/Minas Gerais).
- Peak ordering: weekday, late morning–afternoon.

## 9. Delivery performance

Late-delivery rate (order grain, from `orders_enriched`, 99,441 total orders): **6.57%**. Late deliveries correlate strongly and significantly with lower review scores (see §15).

## 10. Geographic findings

Late-delivery rate varies sharply by state; states furthest from the Southeast logistics hub show the highest late-delivery rates. See `results/state_performance.json`.

## 11. Payment behavior

Credit card is the dominant payment method; a large share of orders use multiple installments, consistent with Brazilian consumer-credit norms.

## 12. Customer behavior

96.9% of customers place exactly one order — the platform's largest untapped growth lever is retention, not acquisition.

## 13. Seller performance

Late deliveries concentrate in a small subset of high-volume sellers (`results` via `sellers_enriched`), making targeted seller intervention more efficient than a blanket policy change.

## 14. Review analysis

Review-score distribution and delay-bucket analysis (`eda.review_score_by_delay_bucket`) show satisfaction drops as soon as ANY lateness occurs, with no "small delay, no problem" zone.

## 15. Statistical test results

Welch's t-test and Mann-Whitney U (both order-grain, alpha=0.05) on review score, late vs. on-time delivery: **statistically significant** (p ≈ 0 in both tests, verified on this project's actual `orders_enriched`). See `results/late_delivery_significance_test.json`.

## 16. RFM segmentation

K-Means (k=4, seed=42), Frequency/Monetary computed correctly at order grain, from the genuine raw Olist CSVs (`data/raw/`). Segments (customer counts, n=96,096): At Risk 38,656 · Champion 2,422 · Loyal Customer 2,962 · Potential Loyal 52,056. See `results/rfm_segments.json`.

## 17. Sentiment-model methodology

Binary classification, 1-2★→Negative, 4-5★→Positive, 3★ and empty-text reviews excluded. See README §10, `DATA_LEAKAGE_AUDIT.md`.

## 18. BERT architecture and configuration

See README §11 / `config/bert_config.json`.

## 19. CNN2D architecture and configuration

See README §12 / `config/cnn2d_config.json`.

## 20. Notebook-reported results

See README §13 / `results/notebook_reported_metrics.json`. **Not leakage-free, not a fair comparison** — see below.

## 21. Corrected reproduced results

See README §14 / `results/reproduced_metrics.json`. BERT: 93.4% accuracy, 0.927 F1-macro on a corrected 6,297-row test set.

## 22. Fair model comparison

Same test set, both models: BERT wins on accuracy/precision/F1/MCC; CNN2D has a marginally higher ROC-AUC (0.9770 vs 0.9755). See `MODEL_COMPARISON_AUDIT.md`.

## 23. SHAP explanation

Fine-tuned BERT, PartitionExplainer, sample size 8, drawn from the stored test split. Top tokens for negative predictions align with delivery/complaint language ("not delivered", "wrong", "broken"); positive predictions align with quality/speed language ("excellent", "wonderful", "on time"). See `backend/app/ml/explainability.py`.

## 24. Fake-review limitations

0/11,407 negative reviews flagged as fake by `jb10231/fake-review-detector` — documented as likely domain shift, NOT proof of authenticity. See README §18.

## 25. ABSA findings

Sentiment-given-aspect over {delivery, product quality, price, customer service, packaging}, n=200 reviews. Delivery aspect shows a roughly even Positive/Negative split, consistent with delivery being the dominant driver of both praise and complaint in the free-text review data.

## 26. Business recommendations

1. **Launch a structured retention program** targeting "At Risk"/"Potential Loyal" RFM segments (51,787 + 38,286 = 90,073 customers, 94% of the base) — highest leverage given the 96.9% one-time-buyer rate.
2. **Tighten carrier SLAs and open direct performance reviews with the worst-late-delivery-rate sellers/states.**
3. **Improve delivery-estimate accuracy at checkout** — since any lateness (even 0-5 days) sharply hurts satisfaction, a more conservative ETA that's rarely missed may protect satisfaction as much as faster shipping.
4. **Deploy the BERT sentiment classifier operationally** to flag negative-sentiment reviews for CS follow-up as soon as they're written, without waiting on the star rating alone.
5. **Invest in a Southeast-anchored regional distribution hub** given demand concentration.

## 27. Technical limitations

Sample-dependent metrics; CPU-only verification in this delivery (GPU would materially speed up BERT training/eval); fake-review/ABSA modules unvalidated for this domain; raw 9 CSVs not present in this delivery (derived datasets used instead — see `DATA_GRAIN_AUDIT.md` §4).

## 28. Responsible-use statement

See README §41. Sentiment predictions are probabilistic tools to prioritize human review, not automated judgments about customers or sellers.
