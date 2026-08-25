# Models

Trained model weights loaded by the backend at startup
(`backend/app/services/model_registry.py`) and by
`notebooks/Baseera_Main_Notebook_Final.ipynb`'s Appendix. Tracked in this
repository via **Git LFS** (see `.gitattributes`) — the fine-tuned BERT
checkpoint is 638MB, well past GitHub's 100MB soft limit for a normal blob.

| Path | Model | Purpose | Required? |
|---|---|---|---|
| `bert_review_sentiment/` | Fine-tuned `LiYuan/amazon-review-sentiment-analysis` (`bert-base-multilingual-uncased`), `AutoModelForSequenceClassification`, binary head | Review sentiment (Positive/Negative) | Optional — disable via `ENABLE_BERT=false` (e.g. on a low-RAM host; see `.env.example`) |
| `cnn2d_review_sentiment.pt` | `CNN2DReviewSentiment` — a from-scratch PyTorch multi-branch n-gram CNN (see `docs/architecture/MODEL_COMPARISON_AUDIT.md`) | Review sentiment (Positive/Negative), also backs the ABSA module | Optional — disable via `ENABLE_CNN2D=false` |

## Source and reproducibility

Both checkpoints were trained by this project's own pipeline
(`backend/scripts/train.py`, and equivalently
`notebooks/Baseera_Main_Notebook_Final.ipynb` Sections 6A/6B) against the
public [Olist Brazilian E-Commerce dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) —
not downloaded from an external model host. See
`docs/architecture/MODEL_CARD.md` for architecture, hyperparameters, and
verified metrics, and `docs/architecture/ARTIFACT_AUDIT.md` for how each
file here was independently confirmed genuine (not a stub or placeholder).

## If these files are missing

Retrain locally: `python backend/scripts/train.py --model bert ...` /
`--model cnn2d ...` (see the root `README.md` "Training" section for exact
commands), or restore them via `git lfs pull` if you have a full clone with
LFS configured. The backend and notebook both degrade gracefully (skip the
missing model, keep the rest working) rather than crashing if one file is
absent — see `ModelRegistry` in `backend/app/services/model_registry.py`.

## What does *not* belong here

- Preprocessing artefacts (tokenisers, scalers, label mappings) — see
  `artifacts/README.md`.
- The previously-evaluated-and-removed fake-review / authenticity-detection
  model — intentionally not part of this project (see
  `docs/architecture/PROJECT_STRUCTURE.md` and `CHANGELOG.md`); do not
  reintroduce it here.
