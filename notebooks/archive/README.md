# Archived notebooks

**This folder is not the recommended execution entry point.** For running the
project, use [`../Baseera_Main_Notebook_Final.ipynb`](../Baseera_Main_Notebook_Final.ipynb)
(see [`../../docs/notebook/NOTEBOOK_RUN_GUIDE.md`](../../docs/notebook/NOTEBOOK_RUN_GUIDE.md)).

## Which notebook is current

`notebooks/Baseera_Main_Notebook_Final.ipynb` is the current, maintained,
portability-tested notebook — Colab/local runtime detection, a dependency
compatibility bootstrap, Kaggle dataset acquisition, an optional smoke-test
mode, and the full EDA/preprocessing/modelling/evaluation/explainability
pipeline, all validated end-to-end (see
[`../../docs/notebook/NOTEBOOK_VALIDATION_REPORT.md`](../../docs/notebook/NOTEBOOK_VALIDATION_REPORT.md)).

## What's archived here, and why each one is preserved rather than deleted

| File | What it is | Why it's kept |
|---|---|---|
| `olist_full_eda_preprocessing_PYTORCH_FIXED.ipynb` | The **authoritative source notebook** that `Baseera_Main_Notebook_Final.ipynb` was built from — corrected in place from the original research notebook, with `# FIX:`-annotated bug fixes | Kept byte-for-byte unmodified as the audit trail / provenance record. Its SHA-256 is tracked in `NOTEBOOK_VALIDATION_REPORT.md` and must never change. |
| `olist_full_eda_preprocessing_PYTORCH.ipynb` | The **original, pre-fix** 151-cell research notebook | Historical baseline — shows the state before the leakage-bug and other fixes documented in `docs/notebook/`. |
| `Baseera_Project_Walkthrough.ipynb` | An earlier "current" notebook (a narrative walkthrough mixing real pipeline calls with illustrative source excerpts from `backend/`/`frontend/`) | Superseded by `Baseera_Main_Notebook_Final.ipynb`, which is a strict superset in validated, portable, runnable content. Kept for reference. |
| `01_Preprocessing.ipynb` … `08_Utility_Files.ipynb` | The pipeline split into 8 standalone, topic-scoped notebooks (preprocessing, models, training, evaluation, inference, backend, frontend, utility) | An earlier decomposition of the same pipeline, kept for anyone who prefers a per-topic notebook over one consolidated notebook. Not maintained in lockstep with the main notebook going forward. |

## Rule for this folder

Nothing here is edited going forward except to fix a genuinely broken path
if one is found — the analytical content of every file above is frozen.
New analysis, fixes, and portability work land in
`notebooks/Baseera_Main_Notebook_Final.ipynb` only.
