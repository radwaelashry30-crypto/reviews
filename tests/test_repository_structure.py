"""Structural checks for the reorganised repository layout. These verify the
repository's own shape and portability guarantees, not model/business logic
(that's backend/app/tests/, run separately)."""
import json
import re

import pytest

MACHINE_SPECIFIC_PATTERNS = [
    re.compile(r"C:\\Users\\[A-Za-z0-9_]+", re.IGNORECASE),
    re.compile(r"/Users/[A-Za-z0-9_]+/Downloads", re.IGNORECASE),
    re.compile(r"Fake[ _]news", re.IGNORECASE),
    re.compile(r"AppData\\Local\\Temp\\claude", re.IGNORECASE),
]

# Files that legitimately discuss "machine-specific paths" as a concept
# (e.g. this test file, or docs explaining the pattern) without containing
# a real one -- excluded so the check isn't self-defeating.
_SELF_REFERENTIAL = {
    "tests/test_repository_structure.py",
    # Documents, as historical evidence, the exact redacted-elsewhere paths this
    # test looks for -- see docs/architecture/ARTIFACT_AUDIT.md §7 for the
    # canonical redacted version.
    "docs/REPOSITORY_RESTRUCTURE_REPORT.md",
}


def test_main_notebook_exists(repo_root):
    nb = repo_root / "notebooks" / "Baseera_Main_Notebook_Final.ipynb"
    assert nb.is_file(), f"Expected the current notebook at {nb}"


def test_main_notebook_is_valid_json(repo_root):
    nb_path = repo_root / "notebooks" / "Baseera_Main_Notebook_Final.ipynb"
    data = json.loads(nb_path.read_text(encoding="utf-8"))
    assert "cells" in data and len(data["cells"]) > 0


def test_archived_source_notebook_preserved(repo_root):
    archived = repo_root / "notebooks" / "archive" / "olist_full_eda_preprocessing_PYTORCH_FIXED.ipynb"
    assert archived.is_file(), "The authoritative source notebook must remain in notebooks/archive/"


def test_no_machine_specific_paths_in_tracked_docs(repo_root):
    """Scans root-level and docs/ Markdown files for hard-coded personal
    paths (this machine's Downloads/Fake news folder, Claude scratch dirs)
    -- these must never leak into committed documentation."""
    offenders = []
    candidates = (
        list(repo_root.glob("*.md"))
        + list(repo_root.glob("docs/**/*.md"))
        + list(repo_root.glob("data/**/*.md"))
        + list(repo_root.glob("models/**/*.md"))
        + list(repo_root.glob("artifacts/**/*.md"))
        + list(repo_root.glob("notebooks/**/*.md"))
    )
    for path in candidates:
        rel = path.relative_to(repo_root).as_posix()
        if rel in _SELF_REFERENTIAL:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in MACHINE_SPECIFIC_PATTERNS:
            if pattern.search(text):
                offenders.append((rel, pattern.pattern))
    assert not offenders, f"Machine-specific paths found: {offenders}"


def test_data_readme_documents_required_files(repo_root):
    readme = (repo_root / "data" / "README.md").read_text(encoding="utf-8")
    required = [
        "olist_customers_dataset.csv",
        "olist_geolocation_dataset.csv",
        "olist_order_items_dataset.csv",
        "olist_order_payments_dataset.csv",
        "olist_order_reviews_dataset.csv",
        "olist_orders_dataset.csv",
        "olist_products_dataset.csv",
        "olist_sellers_dataset.csv",
        "product_category_name_translation.csv",
    ]
    missing = [f for f in required if f not in readme]
    assert not missing, f"data/README.md is missing required filenames: {missing}"


def test_models_and_artifacts_have_readmes(repo_root):
    assert (repo_root / "models" / "README.md").is_file()
    assert (repo_root / "artifacts" / "README.md").is_file()


@pytest.mark.parametrize("path", [
    "notebooks/archive/README.md",
    "docs/notebook/NOTEBOOK_RUN_GUIDE.md",
    "docs/notebook/NOTEBOOK_VALIDATION_REPORT.md",
    "requirements-notebook.txt",
    "run_project.sh",
])
def test_expected_files_exist(repo_root, path):
    assert (repo_root / path).is_file(), f"Expected {path} to exist after restructuring"
