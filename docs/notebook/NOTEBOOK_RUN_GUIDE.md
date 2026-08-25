# Running `notebooks/Baseera_Main_Notebook_Final.ipynb`

This notebook is a portability-wrapped copy of
[`notebooks/archive/olist_full_eda_preprocessing_PYTORCH_FIXED.ipynb`](../../notebooks/archive/olist_full_eda_preprocessing_PYTORCH_FIXED.ipynb)
(the repository's authoritative EDA/preprocessing/modeling notebook — see
`NOTEBOOK_VALIDATION_REPORT.md` for why that notebook was selected). Its analysis,
cleaning rules, feature engineering, models, hyperparameters, splits, seeds, metrics, and
visualizations are **unchanged**. A new "Section 0 — Portability Setup" was inserted at
the top; everything from Section 1 onward is the original notebook, cell for cell.

## What Section 0 does

1. **0.1** Detects Google Colab vs. local Jupyter/script.
2. **0.2** Finds the repository root (or clones it, on a fresh Colab session with no
   local checkout), `chdir`s into it, and creates `data/raw/`, `data/processed/`,
   `models/`, `artifacts/`, `output/` if missing.
3. **0.3** **Critical dependency bootstrap.** Checks numpy/pandas/pyarrow versions via
   package *metadata only* (never imports them to check) — these three are pinned
   (`numpy<2.0`, `pandas<3`, `pyarrow<18`) because a newer combination was found during
   validation to risk a native crash. If already compatible: prints so and continues
   immediately, no install, no restart. If not: installs the pinned versions, then
   **requires exactly one kernel/runtime restart** before continuing (see "First-run
   restart" below) — it does not, and cannot safely, continue in the same process.
4. **0.4** Sets the random seed (42 — the same value the notebook's own `SEED` /
   `RANDOM_SEED` variables already use later on).
5. **0.5** Installs any other missing packages (transformers, sentencepiece, wordcloud,
   kaggle, seaborn, ...).
6. **0.5b** Pre-imports `sentencepiece` — a native-extension load-order fix (see
   `NOTEBOOK_VALIDATION_REPORT.md` §3 for the evidence); unrelated to package versions.
7. **0.6** Ensures the 9 raw Olist CSVs are present under `data/raw/` — reusing them if
   already there, otherwise downloading from Kaggle.
8. **0.7** Defines `BASEERA_SMOKE_TEST` (default `False`) — see "Smoke-test mode" below.

Section 1 onward (the original notebook) then finds those files itself, via its own
existing auto-detect cell (`data/raw` is one of its search locations) — Section 0 never
edits that cell. Section 0.7's flag reaches 8 further original cells (translation sample
size, the shared BERT/CNN2D split, both models' epoch counts, and every save path) through
small guards appended after the original lines, or a `_smoke_path()` wrapper around save
paths that is a no-op when the flag is off — see `NOTEBOOK_VALIDATION_REPORT.md` §6 for
the exact line-by-line diff.

## First-run restart (only if Section 0.3 needs to install something)

If your environment already has compatible numpy/pandas/pyarrow (true for anyone who
installed from `requirements-notebook.txt` — see below), **there is no restart**: Section
0.3 prints "already compatible" and the whole notebook runs top to bottom in one pass.

If it needs to install/upgrade one of the three:
1. Section 0.3 installs the pinned versions, prints exactly what it installed, writes a
   small marker file, and stops the run with a clear (expected, not an error) message.
2. **Colab**: the runtime restarts automatically (this looks like a crash notice — that's
   expected). Once it reconnects, **Runtime → Run all** again.
3. **Local Jupyter**: a kernel restart is requested automatically where possible; if not,
   restart it yourself (**Kernel → Restart Kernel**). Then **Run → Run All Cells** again.
4. The second run detects the now-compatible versions and proceeds normally — no second
   restart, no reinstall. If it's *still* incompatible after one restart (e.g. the install
   itself failed), Section 0.3 raises a clear error instead of restarting again (it will
   never loop).

## Smoke-test mode (`BASEERA_SMOKE_TEST`)

Leave `BASEERA_SMOKE_TEST = False` (the default, in Section 0.7) for the real pipeline —
full dataset, full 70/10/20 split, full epoch counts (`EPOCHS=3` BERT, `CNN_EPOCHS=10`
CNN2D), real save paths. This is what "Run all" does unless you change it.

Set it to `True` only to quickly verify the whole pipeline still connects — tiny data
subset (64/16/16 rows), 1 epoch per model, everything written under `smoke_test/`
subfolders (`models/smoke_test/`, `artifacts/smoke_test/`, `weights/smoke_test/`,
`output/smoke_test/`, `data/raw/smoke_test/`) so it can never overwrite the real trained
models or reported metrics, and a real Olist review is selected programmatically for a
one-off inference check (see `NOTEBOOK_VALIDATION_REPORT.md` §5). **5 of 5 independent
fresh-process runs in a clean, pinned virtual environment completed all 77 executable
cells with no error** (see `NOTEBOOK_VALIDATION_REPORT.md` §4). Do not report smoke-test
numbers (accuracy, loss, etc.) as this project's real results — they come from 1 epoch on
64 rows and are only a connectivity check.

## Google Colab

1. Open the notebook in Colab (File → Upload notebook, or open directly from GitHub:
   `radwaelashry30-crypto/baseera-marketplace-analytics` → `notebooks/Baseera_Main_Notebook_Final.ipynb`).
2. **Runtime → Run all.**
3. Section 0.3 checks dependencies; Colab ships numpy/pandas/pyarrow that are usually
   *newer* than this project's pins, so an install + one automatic restart on the very
   first run is the expected common case on Colab specifically (see "First-run restart"
   above) — just **Runtime → Run all** again once it reconnects.
4. When Section 0.6 asks for Kaggle credentials (only if you haven't set them up — see
   below), upload your `kaggle.json` when prompted.
5. Recommended for the BERT/CNN2D training cells: **Runtime → Change runtime type → GPU**
   (T4 is enough). CPU works too, just much slower (BERT fine-tuning: minutes on GPU,
   potentially hours on CPU).

**Kaggle credentials on Colab** — get `kaggle.json` from
[kaggle.com/settings](https://www.kaggle.com/settings) → *API* → *Create New Token*.
Never paste the token's contents into a plain code cell (it would be saved in the
notebook's output and could leak if shared). Either:
- Let Section 0.6's upload prompt handle it when it appears (uploads directly into
  `~/.kaggle/kaggle.json`, not into any notebook cell/output), or
- Use a Colab **Secret** (key icon in the left sidebar) for `KAGGLE_USERNAME` /
  `KAGGLE_KEY`, and read them into `os.environ` from the secret store before Section 0
  runs — this keeps the values out of the notebook file entirely.

**Normal (full) mode**: just leave `BASEERA_SMOKE_TEST = False` (Section 0.7, the
default) and Run All — no extra steps.

## Local (Windows / macOS / Linux)

**Supported Python: 3.11** (the version this notebook, and the pinned dependency set in
`requirements-notebook.txt`, was tested against).

```bash
git clone https://github.com/radwaelashry30-crypto/baseera-marketplace-analytics.git
cd baseera-marketplace-analytics

# 1. Create a dedicated virtual environment (recommended method — do not install
#    into your global/base Python; this keeps every pin below isolated from
#    anything else on your machine).
python3.11 -m venv .venv
# Windows: .venv\Scripts\activate       macOS/Linux: source .venv/bin/activate

# 2. Install this project's exact, pip-checked, compatible dependency set.
#    --extra-index-url pulls a CPU-only torch build (smaller/faster; matches
#    backend/Dockerfile's own choice) -- a CUDA build also works if you already
#    have one, see "GPU" below.
pip install -r requirements-notebook.txt --extra-index-url https://download.pytorch.org/whl/cpu

# 3. Register this environment as a Jupyter kernel (so Jupyter/JupyterLab can
#    find it -- otherwise it may default to a different, incompatible Python).
python -m ipykernel install --user --name baseera --display-name "Python 3.11 (baseera)"

# 4. Launch and select the kernel.
jupyter notebook notebooks/Baseera_Main_Notebook_Final.ipynb
# In the notebook: Kernel -> Change Kernel -> "Python 3.11 (baseera)"
```

Conda, if you prefer it over venv:

```bash
conda create -n baseera python=3.11 -y
conda activate baseera
pip install -r requirements-notebook.txt --extra-index-url https://download.pytorch.org/whl/cpu
python -m ipykernel install --user --name baseera --display-name "Python 3.11 (baseera)"
jupyter notebook notebooks/Baseera_Main_Notebook_Final.ipynb
```

Then, with the `baseera` kernel selected, **Run → Run All Cells** (Jupyter) or
**Kernel → Restart Kernel and Run All Cells** (JupyterLab).

**If you installed from `requirements-notebook.txt` as above, Section 0.3 will find
everything already compatible and there is no restart** — this is the expected path for
a fresh dedicated venv. A restart is only needed if you're running inside some other,
pre-existing environment whose numpy/pandas/pyarrow don't match the pins (see "First-run
restart" above) — this does not touch any Python environment other than the one currently
active (no global/other-venv changes).

### Kaggle credentials, locally

Place `kaggle.json` at:
- Windows: `C:\Users\<you>\.kaggle\kaggle.json`
- macOS/Linux: `~/.kaggle/kaggle.json`

or export `KAGGLE_USERNAME` / `KAGGLE_KEY` as environment variables before launching
Jupyter. If the 9 CSVs are already under `data/raw/` (e.g. you cloned this repository and
they're already there, or you downloaded the
[Olist dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) manually and
placed them there yourself), Section 0.6 skips the download entirely — no credentials
needed in that case.

### Smoke-test execution (local)

With the `baseera` kernel selected, open Section 0.7's cell, change
`BASEERA_SMOKE_TEST = False` to `True`, then **Run All Cells**. Takes well under two
minutes end to end (real numbers from this delivery's own validation: ~75 seconds).

### Full-mode execution (local)

Leave `BASEERA_SMOKE_TEST = False` (Section 0.7) and **Run All Cells** — this is the
real pipeline: full dataset, full split, full BERT/CNN2D training (`EPOCHS=3`/
`CNN_EPOCHS=10`), several minutes to a few hours depending on CPU vs. GPU.

### GPU

Local GPU (CUDA) is used automatically if `torch.cuda.is_available()`. The
`requirements-notebook.txt` install command above installs the CPU-only torch build by
default; for GPU, install a CUDA-matching torch build instead (see
[pytorch.org/get-started](https://pytorch.org/get-started/locally/) for the exact command
for your CUDA version) before or after the rest of `requirements-notebook.txt` — this
project's models were verified working under both `torch==2.5.1+cpu` and
`torch==2.5.1+cu124`. CPU-only works, just slower for the BERT/CNN2D training cells
(Sections 6A/6B).

## Expected folder structure after a full run

```
baseera-marketplace-analytics/
├── data/
│   ├── raw/            9 Olist CSVs (downloaded or reused)
│   └── processed/
├── models/
│   ├── bert_review_sentiment/
│   └── cnn2d_review_sentiment.pt
├── artifacts/
│   ├── rfm_scaler.pkl, rfm_kmeans.pkl
│   └── cnn2d_tokenizer.pkl
├── weights/             per-epoch BERT checkpoints
└── output/
    ├── olist_cleaned_dataset.csv
    └── olist_cleaned_dataset.parquet
```

## Expected outputs

- **EDA**: ~20 Plotly charts + 2 statistical tests, inline in the notebook (Sections 3–5).
- **RFM segmentation**: 4 customer segments + `artifacts/rfm_scaler.pkl` /
  `artifacts/rfm_kmeans.pkl` (Section 5.6).
- **BERT model**: fine-tuned checkpoint at `models/bert_review_sentiment/`, per-epoch
  checkpoints under `weights/`, metrics/confusion matrix printed inline (Section 6A).
- **CNN2D model**: `models/cnn2d_review_sentiment.pt` +
  `artifacts/cnn2d_tokenizer.pkl`, metrics/confusion matrix inline (Section 6B).
- **Cleaned dataset export**: `output/olist_cleaned_dataset.{csv,parquet}` (Section 6).
- **Appendix** (Section 7 onward): a mix of directly-runnable cells (load real
  `results/*.json`, call the ML pipeline in-process) and illustrative source excerpts
  (backend/frontend/CI/Docker code, shown as fenced code blocks in markdown). One cell
  that used to be a non-executable `code` cell (a FastAPI startup excerpt, originally
  section "9. Backend API") has been converted to a markdown fenced block, since it
  reliably raised `NameError` if executed — everything else in the Appendix, including
  the SHAP explanation and interactive-demo cells, was live-tested end-to-end against the
  real production models in this delivery. See `NOTEBOOK_VALIDATION_REPORT.md` §4 for the
  full cell-by-cell readiness table.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `RuntimeError: Kaggle credentials not found` | No `kaggle.json` / env vars, and not on Colab (no upload prompt) | Place `kaggle.json` as described above, or manually download the dataset and put the 9 CSVs in `data/raw/` |
| `FileNotFoundError: Could not find the Olist raw CSVs` (from the *original* notebook's own Section 2 cell, not Section 0) | Section 0.6 didn't run, or downloaded to the wrong place | Make sure Section 0 ran before Section 2; check `data/raw/` has all 9 files |
| `git: command not found` during Section 0.2 (fresh Colab clone path) | Shouldn't happen on Colab (git preinstalled); on a minimal local install, git is missing | Install git, or run the notebook from inside an already-cloned checkout instead |
| Appendix cells (Section 9+) raise `ModuleNotFoundError: app...` | Repo was cloned but `git lfs pull` failed, or you're not in a full checkout | `git lfs pull` manually inside the cloned repo; or ignore — the EDA/training sections above the Appendix don't need this |
| Section 0.3 stops with "restart required" | Expected on the first run in an environment with a numpy/pandas/pyarrow version this project doesn't support | See "First-run restart" above — restart once, Run All again |
| Section 0.3 raises "still incompatible after a prior install-and-restart attempt" | The install itself likely failed (e.g. no internet, or a conflicting pin elsewhere in the environment) | Check the install output above this error; consider using a fresh venv from `requirements-notebook.txt` instead of debugging the current one |
| `pip install` step is slow / reinstalls things you already have | First run in a bare venv/Colab session | Expected once; subsequent runs skip already-installed packages (Section 0.5 checks before installing) |
| CUDA out-of-memory during BERT/CNN2D training | Limited GPU VRAM | Switch to CPU (slower) or a larger-VRAM Colab GPU runtime; batch sizes are fixed at their original values (not changed by this delivery) |
| A Windows access-violation crash (no Python traceback, process just exits) during the translation cell or BERT tokenizer setup | Root-caused (see `NOTEBOOK_VALIDATION_REPORT.md` §3): on at least one validation machine, `sentencepiece`'s native extension failed to load if imported only *after* several other native-heavy libraries (numpy, pandas, matplotlib, scipy, scikit-learn, torch) had already loaded — a DLL-load-order issue, not a version problem. Section 0.5b pre-imports `sentencepiece` early specifically to prevent this; verified 5/5 clean runs with the fix in place, in a clean pinned environment. | If it still happens: restart the kernel/runtime, run again (this is a load-order issue, not corrupted data — nothing computed so far is lost by data, but the process itself must restart). If persistent, try running in Google Colab or a Linux/macOS environment instead of Windows, where this class of issue is rare. |

## Do not commit

- `kaggle.json` (Kaggle API credentials) — now excluded via `.gitignore`.
- Raw Kaggle CSVs under `data/raw/` — already excluded via `.gitignore`; the dataset is
  CC BY-NC-SA 4.0 licensed by Olist/Kaggle and should not be redistributed through this repo.
- Any `data/uploads/`, `.venv/`, or `__pycache__/` generated while running.
- Any `smoke_test/` subfolders from `BASEERA_SMOKE_TEST=True` runs — already excluded via `.gitignore` (`**/smoke_test/`).
- The `.baseera_bootstrap_restart_marker` file (Section 0.3) — a transient local marker, not meant to be tracked.
