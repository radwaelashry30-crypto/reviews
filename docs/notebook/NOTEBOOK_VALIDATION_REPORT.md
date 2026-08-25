# Notebook Validation Report — `notebooks/Baseera_Main_Notebook_Final.ipynb`

**Revision 4** — dependency-compatibility and stability pass. This revision
achieves the acceptance criterion revisions 2–3 could not: **5 of 5
independent fresh-process runs, in a clean isolated environment, completed
every executable cell with zero failures and zero crashes.** It also found
and fixed the *actual* remaining blocker, which turned out to be different
from what revision 3 assumed — see §3. Revisions 1–3's notebook-selection
evidence (§1, unaffected) is carried forward; everything about dependency
versions, the crash, and test results in revisions 2–3 is superseded by this
one.

## 1. Authoritative source notebook

Unchanged — `notebooks/archive/olist_full_eda_preprocessing_PYTORCH_FIXED.ipynb`,
SHA-256 `397c939103dfaf01f11f72d7ba0c6fc49f8f7837b7b1dec75349ce05ba908724`,
157 cells. **Confirmed still unmodified** this pass too.

## 2. Task 1 — Compatible dependency set

**Method**: not guessed. Pip was given this project's own authoritative
range constraints (`backend/requirements.txt`) and asked to resolve them
against live PyPI metadata in a clean, isolated venv
(`python -m venv`, Python 3.11.0, torch from
`--extra-index-url https://download.pytorch.org/whl/cpu`), then the
resolved versions were captured with `pip freeze` and locked into
`requirements-notebook.txt`.

| Package | Pinned | Why this exact version |
|---|---|---|
| Python | 3.11.0 | Matches the source notebook's own `kernelspec` (`"version": "3.11.15"`, same minor) and this repo's existing tooling |
| numpy | **1.26.4** | Highest patch on the last pre-2.0 minor; satisfies the enforced `<2.0` bound |
| pandas | **2.3.3** | Latest release satisfying the enforced `<3` bound (pip's own resolution, not the older 2.2.x guessed in a prior pass) |
| pyarrow | **17.0.0** | Latest release satisfying the enforced `<18` bound |
| scikit-learn | 1.5.2 | Within `backend/requirements.txt`'s `>=1.4,<1.6` |
| torch | 2.5.1 (`+cpu` build tested) | Within `>=2.2,<2.6` (the upper bound is a documented CVE-2025-32434 guard — see `backend/requirements.txt`); CPU build matches `backend/Dockerfile`'s own production choice; a CUDA build (`+cu124`) was also independently verified working with this project's models |
| transformers | 4.46.3 | Within `>=4.40,<4.50` |
| tokenizers | 0.20.3 | Resolved alongside transformers |
| sentencepiece | 0.2.2 | Within `>=0.2,<0.3` — required by MarianMT/T5 tokenizers this notebook imports |
| sacremoses | 0.1.1 | Within `>=0.1,<0.2` — required by MarianTokenizer |
| protobuf | 5.29.6 | Within `>=4.25,<6` |
| shap | 0.46.0 | Within `>=0.45,<0.47` — used by the Appendix's explainability cells |
| scipy | 1.13.1 | Within `>=1.12,<1.14` — used by the Mann-Whitney/Welch's-t significance test |
| matplotlib | 3.9.4 | Within `>=3.8,<3.10` — word cloud + BERT/CNN2D learning-curve plots |
| seaborn | 0.13.2 | Within `>=0.13,<0.14` — BERT/CNN2D confusion-matrix heatmaps |
| kaggle | 1.8.4 | Within `>=1.6,<2` — dataset acquisition (Section 0.6) |
| jupyter / ipywidgets | 1.1.1 / 8.1.9 | Local execution + the Appendix's interactive-demo widgets |
| plotly, wordcloud, joblib, fastapi, pydantic(-settings), sqlalchemy, alembic, psycopg, slowapi, openpyxl, python-multipart, uvicorn | see `requirements-notebook.txt` | The Appendix directly imports `backend.app.*` modules, which transitively need the full backend stack |

**NLTK**: intentionally **not included**. Grepped the entire authoritative
notebook for `nltk` — zero matches. Its tokenization
(`SimpleVocabTokenizer`) and stopword handling (a hand-written Portuguese
set for the word cloud) are self-contained; adding NLTK would be an unused
dependency, which the task explicitly says to avoid.

**Enforcement, not just documentation**: the three constraints
(`pandas<3`, `numpy<2.0`, `pyarrow<18`) are enforced at notebook run-time by
the new Section 0.3 bootstrap (§4), not merely written in a comment.

**`requirements-notebook.txt`** was rewritten to be one self-contained,
internally consistent, exact-pinned set (previously: range-based, delegated
via `-r backend/requirements.txt`).

## 3. Task 3 — Reassessment of the `pd.set_option("future.infer_string", False)` workaround

**Removed.** Evidence: under the correctly pinned stack (pandas 2.3.3, numpy
1.26.4, pyarrow 17.0.0, resolved and `pip check`-verified in the clean venv),

```python
>>> import pandas as pd
>>> pd.get_option("future.infer_string")
False
>>> pd.Series(["a"]).dtype
dtype('O')          # plain object dtype -- NOT pyarrow-backed
```

`future.infer_string` already defaults to `False` under pandas <3 — the
condition the option was suppressing never occurs once the environment
itself is correct. Retaining it would have been "keeping it merely because
it was added previously," which the task explicitly says not to do. It was
deleted (2 cells removed — see §7).

**However — removing it did NOT make the notebook stable.** A second,
different, unrelated crash remained (this is the actual finding of this
pass, and the reason revision 3's fix was necessary-but-insufficient):

### The real remaining blocker: a `sentencepiece` native-extension load-order fault

With the pinned, clean, `pip check`-passing environment, the sequential run
still crashed (`faulthandler`-captured, `Windows fatal exception: access
violation`) — but **at a completely different, new location**:

```
File ".../sentencepiece/__init__.py", line 6 in <module>
  (create_module -> module_from_spec -> _find_and_load, i.e. loading the
   compiled _sentencepiece extension itself)
File ".../transformers/models/t5/tokenization_t5.py", line 23 in <module>
File ".../transformers/models/mt5/__init__.py", line 29 in <module>
...
File "cell_40" (the translation cell's `from transformers import MarianMTModel, MarianTokenizer`)
```

Reproduced **3 of 3 times**, always at this exact spot, in the clean
pandas/numpy/pyarrow-pinned venv — proving the pandas/pyarrow pin (§2) was
not the actual fix for a full clean run; it fixed a real, separately-proven
risk (revision 3), but a different fault was still blocking full execution.

**Diagnosis**: isolated tests —
```python
import sentencepiece                          # alone: OK
import torch; import sentencepiece            # OK
import sentencepiece                          # FIRST, before anything else: OK
# vs. the real sequence: numpy, pandas, matplotlib, plotly, scipy,
# scikit-learn, torch, transformers all already loaded, THEN sentencepiece
# (a SWIG-generated native extension) for the first time -> crash, 3/3
```
— importing `sentencepiece` **before** the rest of the native-heavy stack
avoids the fault entirely; importing it **after** does not, reliably. This
is consistent with a Windows DLL base-address/relocation conflict (a known
class of issue with SWIG-generated Windows extensions when many other
native modules have already claimed process address space) — **not a
version incompatibility problem**, and not fixed by any pandas/numpy/pyarrow
pin.

**Fix**: pre-import `sentencepiece` early in Section 0 (new 0.5b, right
after general dependency installation), before any of the notebook's own
cells reach it naturally. Verified: **0 crashes in 5/5 full fresh-process
runs after this fix** (§4) vs. **3/3 crashes without it**, same environment.

**Correct summary, per the task's explicit instruction not to mis-attribute
the primary fix**: the actual, sufficient fix for full-run stability in this
pass is the `sentencepiece` pre-import (§3/§7), not the dependency pins.
The dependency pins (§2) are independently correct and necessary
(enforcing this project's own stated constraints, and fixing the earlier,
separately-reproduced pandas/pyarrow string-array fault from revision 3),
but were not, by themselves, sufficient for a fully clean run.

## 4. Task 2 — Bootstrap dependency check (Section 0.3)

Implemented exactly as specified:
1. Runs before numpy/pandas/pyarrow/scikit-learn/torch/transformers/SHAP are
   imported anywhere in this notebook (verified: it is the first substantive
   cell after environment detection and project-root resolution, both of
   which only use `os`/`sys`/`pathlib`/`subprocess`).
2. Checks installed versions via `importlib.metadata.version()` only — never
   imports the package being checked.
3. Compares against this project's own ranges (`numpy<2.0` etc.).
4. Installs only what's incompatible (`pip install pkg==<pinned>` for just
   the failing package(s)).
5. Prints installed / required / action for every one of the 3 packages,
   every run (verified in every trial's stdout, §5).
6. Detects `sys.modules` membership for all 3 before touching anything —
   if any is already imported, raises immediately instead of attempting an
   unsafe in-process replacement.
7. After an install, **always** stops the run and requires a restart
   (Colab: `os.kill(os.getpid(), 9)`, auto-reconnects; local:
   `get_ipython().kernel.do_shutdown(restart=True)`, falls back to a printed
   manual-restart instruction) — never continues in a mixed old/new process.
8. A `.baseera_bootstrap_restart_marker` file (in `PROJECT_ROOT`, not a
   machine-specific path) prevents an infinite loop: if still incompatible
   after one restart+install cycle, raises a clear manual-intervention error
   instead of restarting again.
9. No secrets are involved in this cell at all (nothing credential-related).
10. No machine-specific paths (`PROJECT_ROOT` is resolved portably, per
    Section 0.2, on both Colab and local).

**Verified in this session**: the clean venv already had the pinned
versions (installed as part of building it — §5), so Section 0.3 printed
"already compatible" and continued without a restart in every one of the 5
stability runs (§5) — the *normal* expected path for anyone who installs
from `requirements-notebook.txt` first. The install→restart→marker branch
was code-reviewed and unit-verified for its control-flow logic (version
comparison, `sys.modules` detection, marker read/write) but not re-triggered
against a genuinely incompatible venv in this pass (that would require
building a second, deliberately-wrong venv — out of scope for this
targeted pass; the branch's logic is unchanged from a version reviewed in
revision 3 for equivalent code).

## 5. Task 4/5 — Clean isolated environment + 5/5 stability acceptance

**Environment**: `python -m venv` at a path outside the repository (not
reusing the "contaminated" global Python that revisions 2–3 ran in — that
one has pandas 3.0.3/numpy 2.4.6/pyarrow 24.0.0, confirmed in revision 3).
Installed **only** from the final `requirements-notebook.txt`
(`pip install -r requirements-notebook.txt --extra-index-url
https://download.pytorch.org/whl/cpu`).

```
Python 3.11.0
numpy==1.26.4  pandas==2.3.3  pyarrow==17.0.0  (all 3 constraints satisfied)
pip check: No broken requirements found.
```

**Pre-flight tests** (clean venv, before the full notebook run):
- Import test for all direct dependencies: passed (all resolve; `pip check`
  found zero broken requirements, i.e. every declared dependency's own
  requirements are satisfied by what's installed).
- `pd.read_csv` / `pd.to_csv` on a real-shaped string+numeric DataFrame: OK.
- `pd.to_parquet` round-trip via pyarrow: OK.
- Notebook syntax validation: `ast.parse()` on all 77 code cells — 0 errors.

**Five independent fresh-process full smoke-test runs**
(`BASEERA_SMOKE_TEST=True`, forced after its own cell exactly as a user
manually setting it would, no preloaded state, cell 117-equivalent *not*
skipped this time — every cell actually executes):

| Run | Python | pandas | numpy | pyarrow | Executable cells | Passed | Failed | Exit code | Runtime | Peak RSS |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 3.11.0 | 2.3.3 | 1.26.4 | 17.0.0 | 77 | **77** | 0 | 0 | 74.8s | 4726.1 MB |
| 2 | 3.11.0 | 2.3.3 | 1.26.4 | 17.0.0 | 77 | **77** | 0 | 0 | 76.2s | 4723.3 MB |
| 3 | 3.11.0 | 2.3.3 | 1.26.4 | 17.0.0 | 77 | **77** | 0 | 0 | 74.6s | 4724.1 MB |
| 4 | 3.11.0 | 2.3.3 | 1.26.4 | 17.0.0 | 77 | **77** | 0 | 0 | 74.1s | 4728.6 MB |
| 5 | 3.11.0 | 2.3.3 | 1.26.4 | 17.0.0 | 77 | **77** | 0 | 0 | 73.8s | 4720.1 MB |

**Result: 5/5 runs, 77/77 executable cells each, 0 failures, 0 crashes, 0
segfaults, 0 skipped cells.** (One earlier attempt in this same clean venv
was discarded and re-run, not counted above: a harness bug — Windows
console `cp1252` encoding choking on a `✔` character the notebook itself
prints — caused a `UnicodeEncodeError` in the test harness before any
notebook logic ran; fixed by setting `PYTHONIOENCODING=utf-8` for the
harness process, not a notebook change, and excluded from the 5 counted
runs since it never validated notebook behavior at all.)

Acceptance-criterion checklist, all confirmed across the 5 runs:
- Model construction: real `AutoModelForSequenceClassification` (BERT) +
  real `CNN2DReviewSentiment` (from-scratch PyTorch) — both built successfully.
- At least one training step per model: real forward/backward passes, 1
  smoke-scale epoch each, real loss values printed every run.
- Evaluation: real (small-sample, honestly noisy — 16–64 rows) classification
  reports for both models, every run.
- Artifact save/load: real files under `*/smoke_test/`; the Appendix
  separately loads the **real production** models (untouched by the smoke
  run) and performs real inference (§6).
- Inference: real, on a real Olist review (§6).
- SHAP: real, on 4 real test-split reviews, via the real production BERT
  model, every run that reached the Appendix (all 5).

## 6. Task 7 — Export integrity (every run)

Verified against the artifacts from the final counted run:
- `output/smoke_test/olist_cleaned_dataset.csv` — exists, reopens, shape `(112650, 41)`.
- `output/smoke_test/olist_cleaned_dataset.parquet` — exists, reopens, shape `(112650, 41)`.
- Row count matches `df` at export time (112,650 — independently
  cross-confirmed by the Data-Grain Audit appendix cell in the same run).
- Column count (41) and exact column name/order identical between CSV and Parquet.
- Smoke outputs confirmed isolated under `*/smoke_test/` subfolders (`models/`,
  `artifacts/`, `weights/`, `output/`, `data/raw/`) — all deleted after
  verification, never left in the repository, all `.gitignore`d
  (`**/smoke_test/`, unchanged from a prior pass).
- **Production artifacts confirmed unchanged — by cryptographic hash, not
  just timestamp**:

  | File | SHA-256 (after 5 smoke runs) | Matches known Git-LFS object hash |
  |---|---|---|
  | `artifacts/rfm_scaler.pkl` | `c6dcdbd6fc1fae14e352a76ec758e41b18cb04d59da0eb6ca99120127a7918c7` | ✅ (`git lfs ls-files` prefix `c6dcdbd6fc`) |
  | `artifacts/cnn2d_tokenizer.pkl` | `ea7e225fc8d72f174944e2759f1409d36191b68fa2ec9acd632c1eafeb6557af` | ✅ (`git lfs ls-files` prefix `ea7e225fc8`) |
  | `models/bert_review_sentiment/model.safetensors` | (669,455,360 bytes, timestamp `Aug 23 10:50`, unchanged) | — |
  | `models/cnn2d_review_sentiment.pt` | (12,210,185 bytes, timestamp `Aug 23 11:14`, unchanged) | — |

## 7. Task 6 — Real, meaningful Olist review for smoke-test inference

Previous pass's review (`'use 9.5'`, 7 chars) was dataset-real but too short
to be meaningful. Fixed by adding a minimum-length filter (append-only
change to the existing selection block, same deterministic
`random_state=GLOBAL_SEED` sampling):

```python
_real_reviews = reviews[
    reviews["review_comment_message"].notna()
    & (reviews["review_comment_message"] != "No Message")
    & (reviews["review_comment_message"].str.strip().str.len() >= 30)
]
```

**Real result, this pass's reference run:**

```
[smoke test] Real Olist review selected programmatically for smoke testing.
[smoke test]   review_id = 'a2c5f2d89bf35609d11057d61e326f68'
[smoke test]   pandas index = 6251
[smoke test]   length = 40 chars
[smoke test]   review_comment_message = 'Great product, lived up to expectations.'
[smoke test] Prediction on this real review (smoke-test output only, NOT
an official project metric): {'label': 'Positive', 'class_id': 1,
'probability_positive': 0.9234, 'probability_negative': 0.0766,
'confidence': 0.9234, 'model_name': 'cnn2d', 'source_language': 'en',
'translated': False, 'cleaned_text': 'Great product, lived up to expectations.'}
```

- Source column: `review_comment_message` (exactly as specified) — the
  in-memory `reviews` DataFrame already loaded/cleaned by the notebook's
  own Section 2/3, not re-read or fabricated.
- Non-null, non-empty, ≥30 chars: enforced by the filter above.
- Deterministic: `random_state=GLOBAL_SEED` (42, the project's existing
  seed) — same row every run (confirmed: identical `review_id` across all 5
  stability runs).
- `review_id`, pandas index, exact text, and length all printed before
  prediction.
- Labeled exactly `"Real Olist review selected programmatically for smoke
  testing."`, and the prediction line is explicitly marked "smoke-test
  output only, NOT an official project metric."
- Translation: this project's models (both BERT — a multilingual
  checkpoint — and CNN2D, trained directly on raw `review_comment_message`
  per this notebook's own Section 6A data-prep cell) are trained on
  **untranslated** text; no separate translation step exists in the
  project's own pipeline for this call, so none was introduced here — the
  call matches `predict_sentiment(registry, text, model_name="cnn2d")`
  exactly as the original notebook's own illustrative example above it
  already does.

## 8. Task 8 — Preservation and drift audit

**Comparison 1 — vs. the authoritative 157-cell source notebook:**

```
147 unchanged original cells  +  10 modified original cells  =  157   ✓
```

Unchanged from revision 3 — this pass touched **zero additional original
cells**. All of this pass's changes are inside Section 0 (new, not part of
the 157) plus one cosmetic renumbering pass over Section 0's own markdown
headers (also not part of the 157).

| Original index | Modified? | Reason (pass introduced) |
|---|---|---|
| 23, 98, 102, 104, 107, 108, 115, 117 | yes (rev. 2) | smoke-test guards — untouched this pass |
| 126 | yes (rev. 2) | converted to markdown (verified `NameError`) — untouched this pass |
| 143 | yes (rev. 3, refined this pass) | smoke-test review-selection block — this pass only added a length filter to the existing appended block (still append-only; original 8 lines still untouched) |
| all other 147 | no | byte-identical to source, every pass |

**Comparison 2 — vs. the notebook immediately before this pass** (revision
3's file, SHA-256
`91fffc6e374fdd99c43066ff65ac1c974a7b4e4e44fc81b68941ec680baad68b`):

| Metric | Before this pass | After this pass | Change |
|---|---|---|---|
| Total cells | 174 | **176** | +2 |
| Code cells | 76 | **77** | +1 |
| Markdown cells | 98 | **99** | +1 |
| Original cells modified (of 157) | 10 | 10 | unchanged (cell 143 refined, not newly touched) |

**Exact changes this pass** (all inside the new Section 0, or a same-cell
refinement of an already-modified cell):
1. **Removed** the revision-3 "0.7 Pandas/PyArrow stability fix" cells (2:
   markdown + code) — shown unnecessary under the correct pins (§3).
2. **Added** "0.3 Critical dependency bootstrap" (2 cells: markdown + code)
   — Task 2's bootstrap.
3. **Added** "0.5b Native-extension load-order fix" (2 cells: markdown +
   code) — the actual fix for the remaining crash (§3).
4. **Renumbered** 4 existing Section-0 markdown headers (0.3→0.4 seeds,
   0.4→0.5 deps, 0.5→0.6 Kaggle, 0.6→0.7 smoke-test) — text-only, no code
   changed, for consistency with the 2 new subsections.
5. **Refined** the existing smoke-test review-selection block inside cell
   143 (already-modified since revision 3) — added a `>=30`-char filter and
   updated print labels/text (§7). No new cell; the original 8 lines of
   cell 143 remain untouched.

**No unrelated cell drift**: every cell not listed above is byte-identical
to revision 3's file, verified programmatically (full diff, source[2:] vs.
new[21:] after accounting for the net +2 structural change, 145/155 tail
cells match, plus the one deliberately-refined cell 143).

**Authoritative source notebook**: confirmed unmodified — SHA-256 unchanged
(`397c939103dfaf01f11f72d7ba0c6fc49f8f7837b7b1dec75349ce05ba908724`),
`git status --short` clean for that path, throughout this pass.

**New notebook SHA-256 (this revision):**
`032220d2ae61721fb78b0a1d9016130818815330c9120aab90792b73521e715f`

## 9. Task 9 — Test-type disclosure (explicit)

| Item | Status |
|---|---|
| **Clean-environment local smoke test** | **Live, real, 5/5** — see §5. |
| **Full-scale (non-smoke) local run** | **Not tested.** `BASEERA_SMOKE_TEST=False` end-to-end (full 3/10-epoch training) was not run to completion in the clean venv in this pass. |
| **Live Google Colab run** | **Not tested.** No live Colab runtime was used. |
| **Static Colab validation** | Performed (unchanged from revision 2/3): no machine-specific paths, `google.colab` imports properly guarded, root-resolution/clone logic reviewed. |
| **Mocked Kaggle acquisition** | Performed (revision 2, unchanged this pass) — real credentials unavailable in this sandbox, explicitly disclosed, not implied to be a live download test. |
| **Real (live) Kaggle acquisition** | **Not tested.** No real Kaggle API download was performed in any pass. |

## 10. Remaining untested items

- Full-scale (non-smoke, `BASEERA_SMOKE_TEST=False`) training to completion.
- A real Google Colab runtime (live).
- A real, non-mocked Kaggle API download.
- The bootstrap's install→restart→marker branch was not re-triggered
  against a second, deliberately-incompatible venv in this pass (reviewed,
  not re-executed — see §4).
- GPU execution of the full pipeline (the clean venv used CPU-only torch;
  this project's models were separately confirmed compatible with a CUDA
  build in an earlier pass, but not re-tested end-to-end in this pass's
  clean venv).

## 11. `git diff --stat`

```
 .gitignore                               |  11 ++
 backend/app/api/v1/endpoints/health.py   |  20 ++-
 backend/app/api/v1/router.py             |   3 +-
 backend/app/core/config.py               |  42 +++++
 backend/app/core/security.py             |  28 ++++
 backend/app/db/models.py                 | 274 ++++++++++++++++++++++++++++++-
 backend/app/main.py                      |  11 ++
 backend/app/tests/test_db_persistence.py |  10 +-
 8 files changed, 395 insertions(+), 4 deletions(-)
```

Unchanged from revision 3 — `.gitignore` was **not** touched this pass (out
of this pass's permitted scope). Only `notebooks/Baseera_Main_Notebook_Final.ipynb`,
`requirements-notebook.txt`, `NOTEBOOK_RUN_GUIDE.md`, and this report
(all untracked) changed. No tracked file's diff changed.

## 12. `git status --short`

```
 M .gitignore
 M backend/app/api/v1/endpoints/health.py
 M backend/app/api/v1/router.py
 M backend/app/core/config.py
 M backend/app/core/security.py
 M backend/app/db/models.py
 M backend/app/main.py
 M backend/app/tests/test_db_persistence.py
?? notebooks/Baseera_Main_Notebook_Final.ipynb
?? NOTEBOOK_RUN_GUIDE.md
?? NOTEBOOK_VALIDATION_REPORT.md
?? backend/app/api/v1/endpoints/marketplace_data.py
?? backend/app/db/marketplace_base.py
?? backend/app/repositories/marketplace_repository.py
?? backend/app/schemas/marketplace.py
?? backend/app/schemas/model_info.py
?? backend/app/services/marketplace_analytics_cache.py
?? backend/app/services/marketplace_analytics_service.py
?? backend/app/services/marketplace_import_service.py
?? backend/app/services/marketplace_version_service.py
?? backend/app/tests/test_marketplace_data.py
?? backend/migrations/versions/b590246793c8_create_marketplace_tables.py
?? data/marketplace_staging/
?? requirements-notebook.txt
```

No unrelated repository files modified — the 8 `M` rows and `marketplace_*`
`??` rows are pre-existing, unrelated, in-progress work on this branch
(confirmed in every prior pass; still untouched). `smoke_test/` subfolders
and the `.baseera_bootstrap_restart_marker` file from this pass's live runs
were deleted after verification and do not appear above. The temporary
validation venv (`venv_baseera_clean/`) was created outside this
repository's working tree (a scratch/temp directory) and is not part of
this repo at all.

## 13. Confirmation: no commit or push performed

No `git add`, `git commit`, or `git push` was run at any point in this pass
(or any prior pass). All changes remain in the working tree, exactly as
shown in §12.
