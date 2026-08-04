"""Loads every optional model artifact exactly once, at application startup.

Owned by `app.main`'s lifespan context, stored on `app.state.model_registry`,
and injected into services via `dependencies.py`. No endpoint or service ever
touches disk to load a model — they only ever read from this registry.
"""
from __future__ import annotations

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

    # -- loading -------------------------------------------------------
    def load_all(self) -> None:
        import torch

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._load_bert()
        self._load_cnn()
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
