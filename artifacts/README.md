# Artefacts

Fitted preprocessing objects and small inference-time metadata — everything
the backend and notebook need for inference *besides* the model weights
themselves (see `models/README.md` for those). Tracked via Git LFS where
binary (`.pkl`); plain JSON files are tracked normally.

| File | Contents | Produced by |
|---|---|---|
| `cnn2d_tokenizer.pkl` | Fitted `SimpleVocabTokenizer` (vocabulary, frequency caps) for the CNN2D model | `backend/app/ml/models.py` training / notebook Section 6B |
| `rfm_scaler.pkl` | Fitted `Pipeline` (`log1p` + `StandardScaler`) for RFM features | `backend/app/ml/segmentation.py` / notebook Section 5.6 |
| `rfm_kmeans.pkl` | Fitted `KMeans` (k=4, seed 42) for customer segmentation | same as above |
| `label_mapping.json` | Class-id ↔ label name mapping (`0`↔Negative, `1`↔Positive) | `backend/scripts/export_artifacts.py` |
| `model_manifest.json` | Which model files exist, their checksums, and freshness metadata — checked at startup by `_check_metrics_freshness()` | `backend/scripts/export_artifacts.py` |
| `split_manifest.json` | Stable `review_id`/text-hash record of the train/val/test split, so evaluation and the SHAP demo never depend on re-running the split | `backend/app/ml/preprocessing.py` |
| `translation_manifest.json` | Record of which reviews were machine-translated and by which model (MarianMT `opus-mt-ROMANCE-en`) | `backend/scripts/translate_reviews.py` |

## Regenerating

All of the above are reproducible from the raw dataset via the project's own
pipeline — none are hand-edited. See `backend/scripts/run_pipeline.py`,
`export_artifacts.py`, and `docs/architecture/ARTIFACT_AUDIT.md` for exactly
how each file is produced and independently verified.

## If these files are missing

The backend and notebook both report which optional artefacts are
unavailable rather than crashing (see `ModelRegistry.statuses` in
`backend/app/services/model_registry.py`) — but RFM segmentation and the
CNN2D pipeline specifically require their corresponding `.pkl` file to be
present.
