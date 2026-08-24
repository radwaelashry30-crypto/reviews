"""Loads every optional model artifact exactly once, at application startup.

Owned by `app.main`'s lifespan context, stored on `app.state.model_registry`,
and injected into services via `dependencies.py`. No endpoint or service ever
touches disk to load a model — they only ever read from this registry.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

Status = Literal["available", "unavailable", "invalid", "loading_failed"]


@dataclass
class ArtifactStatus:
    name: str
    status: Status
    path: str | None = None
    error: str | None = None
    extra: dict = field(default_factory=dict)


class ModelRegistry:
    """In-memory holder for every loaded artifact + a status report per artifact."""

    def __init__(self) -> None:
        self.device = "cpu"
        self.bert_model = None
        self.bert_tokenizer = None
        self.cnn_model = None
        self.cnn_tokenizer = None
        self.rfm_scaler = None
        self.rfm_kmeans = None
        self.rfm_cluster_label_map: dict | None = None
        self.statuses: dict[str, ArtifactStatus] = {}
        # SHAP explainer: only needs the `shap` package (already installed
        # locally) and the BERT model that's already loaded -- no separate
        # external download or gating flag needed. ABSA (Task 3) defaults to
        # CNN2D, already loaded for Task 1, so that path has nothing separate
        # to lazy-load or cache -- see get_absa_pipeline(). The optional
        # DeBERTa-v3 ABSA path below is the one exception: it's a genuinely
        # separate, ~738MB download, lazy-loaded only when a caller
        # explicitly asks for it.
        self.shap_explainer = None
        self.absa_deberta_pipe = None
        # FastAPI runs sync `def` endpoints in a thread pool, so two
        # concurrent first requests could both see `self.shap_explainer is
        # None` (or `self.absa_deberta_pipe is None`) and both start loading
        # it at once. One lock per lazily loaded resource (not one shared
        # lock) so each load doesn't block a concurrent load unrelated to it.
        self._locks = {name: threading.Lock() for name in ("shap", "absa_deberta")}

    def _lazy_load(self, name: str, attr: str, loader):
        """Thread-safe lazy load: check, lock, check again. `loader` is
        called at most once even under concurrent first-time callers."""
        current = getattr(self, attr)
        if current is not None:
            return current  # fast path -- no lock once loaded
        with self._locks[name]:
            current = getattr(self, attr)  # re-check: another thread may have loaded it while we waited
            if current is not None:
                return current
            try:
                loaded = loader()
                setattr(self, attr, loaded)
                self.statuses[name] = ArtifactStatus(name, "available", None, extra={"device": self.device})
                return loaded
            except Exception as e:  # noqa: BLE001
                logger.exception("Lazy load of '%s' failed", name)
                self.statuses[name] = ArtifactStatus(name, "loading_failed", None, str(e))
                return None

    # -- loading -------------------------------------------------------
    def load_all(self) -> None:
        import torch

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        if settings.ENABLE_BERT:
            self._load_bert()
        else:
            self.statuses["bert"] = ArtifactStatus("bert", "unavailable", str(settings.BERT_MODEL_PATH), "Disabled via ENABLE_BERT=false (low-RAM deployment)")
        if settings.ENABLE_CNN2D:
            self._load_cnn()
        else:
            self.statuses["cnn2d"] = ArtifactStatus("cnn2d", "unavailable", str(settings.CNN_CHECKPOINT_PATH), "Disabled via ENABLE_CNN2D=false")
        self._load_rfm()

    def _load_bert(self) -> None:
        from app.ml.models import load_fine_tuned_bert

        path = settings.BERT_MODEL_PATH
        if not path.is_dir():
            self.statuses["bert"] = ArtifactStatus("bert", "unavailable", str(path), "Directory not found")
            return
        try:
            self.bert_model, self.bert_tokenizer = load_fine_tuned_bert(path, device=self.device)
            self.statuses["bert"] = ArtifactStatus(
                "bert", "available", str(path),
                extra={"num_labels": self.bert_model.config.num_labels, "device": self.device},
            )
        except Exception as e:  # noqa: BLE001
            logger.exception("Failed to load BERT model")
            self.statuses["bert"] = ArtifactStatus("bert", "loading_failed", str(path), str(e))

    def _load_cnn(self) -> None:
        import pickle
        import __main__ as main_module

        from app.ml.models import load_cnn2d_model
        from app.ml.preprocessing import SimpleVocabTokenizer

        # The original notebook pickled SimpleVocabTokenizer from ITS OWN
        # __main__ namespace. Python's pickle resolves classes by
        # (module, qualname) at load time, so unpickling this exact artifact
        # in any other process requires the class to also be reachable as
        # `__main__.SimpleVocabTokenizer` there. This is a one-time process-wide
        # registration, safe to repeat. See ARTIFACT_AUDIT.md.
        main_module.SimpleVocabTokenizer = SimpleVocabTokenizer

        ckpt_path = settings.CNN_CHECKPOINT_PATH
        tok_path = settings.CNN_TOKENIZER_PATH
        if not ckpt_path.is_file():
            self.statuses["cnn2d"] = ArtifactStatus("cnn2d", "unavailable", str(ckpt_path), "Checkpoint not found")
            return
        if not tok_path.is_file():
            self.statuses["cnn2d"] = ArtifactStatus("cnn2d", "unavailable", str(tok_path), "Tokenizer not found")
            return
        try:
            self.cnn_model = load_cnn2d_model(ckpt_path, device=self.device)
            with open(tok_path, "rb") as f:
                self.cnn_tokenizer = pickle.load(f)
            self.statuses["cnn2d"] = ArtifactStatus(
                "cnn2d", "available", str(ckpt_path),
                extra={"vocab_size": self.cnn_tokenizer.vocab_size, "device": self.device},
            )
        except Exception as e:  # noqa: BLE001
            logger.exception("Failed to load CNN2D model")
            self.statuses["cnn2d"] = ArtifactStatus("cnn2d", "loading_failed", str(ckpt_path), str(e))

    def _load_rfm(self) -> None:
        from app.ml.segmentation import load_segmentation_artifacts

        scaler_path, kmeans_path = settings.RFM_SCALER_PATH, settings.RFM_MODEL_PATH
        if not scaler_path.is_file() or not kmeans_path.is_file():
            self.statuses["rfm"] = ArtifactStatus("rfm", "unavailable", str(kmeans_path), "Segmentation artifacts not found")
            return
        try:
            self.rfm_scaler, self.rfm_kmeans, self.rfm_cluster_label_map = load_segmentation_artifacts(scaler_path, kmeans_path)
            self.statuses["rfm"] = ArtifactStatus("rfm", "available", str(kmeans_path), extra={"n_clusters": self.rfm_kmeans.n_clusters})
        except Exception as e:  # noqa: BLE001
            logger.exception("Failed to load RFM artifacts")
            self.statuses["rfm"] = ArtifactStatus("rfm", "loading_failed", str(kmeans_path), str(e))

    # -- reporting -------------------------------------------------------
    def status_report(self) -> dict:
        return {
            "device": self.device,
            "artifacts": {name: {"status": s.status, "error": s.error, **s.extra} for name, s in self.statuses.items()},
        }

    def require_bert(self):
        from app.core.exceptions import ModelUnavailableError

        if self.bert_model is None or self.bert_tokenizer is None:
            status_obj = self.statuses.get("bert")
            reason = status_obj.error if status_obj else "not loaded"
            raise ModelUnavailableError(f"BERT sentiment model is not available: {reason}")
        return self.bert_model, self.bert_tokenizer

    def require_cnn(self):
        from app.core.exceptions import ModelUnavailableError

        if self.cnn_model is None or self.cnn_tokenizer is None:
            status_obj = self.statuses.get("cnn2d")
            reason = status_obj.error if status_obj else "not loaded"
            raise ModelUnavailableError(f"CNN2D sentiment model is not available: {reason}")
        return self.cnn_model, self.cnn_tokenizer

    def require_rfm(self):
        from app.core.exceptions import ModelUnavailableError

        if self.rfm_scaler is None or self.rfm_kmeans is None:
            status_obj = self.statuses.get("rfm")
            reason = status_obj.error if status_obj else "not loaded"
            raise ModelUnavailableError(f"RFM segmentation model is not available: {reason}")
        return self.rfm_scaler, self.rfm_kmeans, self.rfm_cluster_label_map

    # -- lazy-loaded optional models (SHAP explainer) --------------------
    def get_shap_explainer(self):
        """Loads a SHAP explainer wrapping the fine-tuned BERT model on first
        call, then reuses it. Requires BERT itself to be available (ENABLE_BERT=true)
        and the `shap` package installed -- returns None (never raises) otherwise."""
        if self.bert_model is None or self.bert_tokenizer is None:
            self.statuses["shap"] = ArtifactStatus("shap", "unavailable", None, "BERT model not available")
            return None
        from app.ml.explainability import is_shap_available, load_shap_explainer

        if not is_shap_available():
            self.statuses["shap"] = ArtifactStatus("shap", "unavailable", None, "shap package not installed")
            return None
        device_idx = 0 if self.device == "cuda" else -1
        return self._lazy_load("shap", "shap_explainer", lambda: load_shap_explainer(self.bert_model, self.bert_tokenizer, device=device_idx))

    def get_absa_pipeline(self, absa_method: str = "cnn2d"):
        """Returns the ABSA pipeline for the requested method.

        Default (`"cnn2d"`): sentiment-given-aspect over CNN2D (see
        app/ml/absa.py module docstring for why this is the default -- the
        ~738MB external DeBERTa checkpoint below is a real memory risk on a
        free-tier deployment). No separate download or lazy-load needed --
        CNN2D is already loaded for Task 1, so this is only unavailable if
        CNN2D itself isn't.

        `"deberta"`: the optional, purpose-trained DeBERTa-v3 ABSA checkpoint
        (see app/ml/absa.py::load_deberta_absa_pipeline for its verified
        input contract and label mapping). Lazy-loaded on first request via
        the same thread-safe `_lazy_load` pattern as get_shap_explainer --
        never loaded at startup, never loaded unless explicitly requested. A
        loading failure (network, OOM, missing package) is caught by
        `_lazy_load`, reported as an `absa_deberta` status with a reason, and
        returns None here -- callers must never crash on this, and must never
        substitute a guessed prediction for the missing model."""
        if absa_method == "deberta":
            from app.ml.absa import load_deberta_absa_pipeline

            device_idx = 0 if self.device == "cuda" else -1
            return self._lazy_load("absa_deberta", "absa_deberta_pipe", lambda: load_deberta_absa_pipeline(device=device_idx))

        if self.cnn_model is None or self.cnn_tokenizer is None:
            self.statuses["absa"] = ArtifactStatus("absa", "unavailable", None, "CNN2D not available (required for aspect-sentiment scoring)")
            return None
        from app.ml.absa import load_absa_pipeline

        pipe = load_absa_pipeline(self.cnn_model, self.cnn_tokenizer, device=self.device)
        self.statuses["absa"] = ArtifactStatus("absa", "available", None, extra={"device": self.device})
        return pipe
