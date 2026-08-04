import pickle

import pytest
import torch

from app.core.config import settings
from app.ml.models import CNN2DReviewSentiment, load_cnn2d_model, load_fine_tuned_bert


def test_cnn2d_architecture_shapes():
    model = CNN2DReviewSentiment(vocab_size=1000, max_len=50, embed_dim=16, num_filters=4)
    assert model.embedding.weight.shape == (1000, 16)
    assert len(model.branches) == 4  # filter sizes (2,3,4,5)
    x = torch.randint(0, 1000, (3, 50))
    out = model(x)
    assert out.shape == (3,)  # raw logits, one per example, no sigmoid applied


def test_cnn2d_checkpoint_loads_strict(project_root):
    ckpt = project_root / "models" / "cnn2d_review_sentiment.pt"
    if not ckpt.is_file():
        pytest.skip(f"CNN2D checkpoint not found at {ckpt}")
    model = load_cnn2d_model(ckpt, device="cpu")
    assert sum(p.numel() for p in model.parameters()) == 3_049_345
    assert not model.training  # eval mode


def test_cnn2d_tokenizer_loads_and_has_reserved_indices(project_root):
    import __main__ as main_module
    from app.ml.preprocessing import SimpleVocabTokenizer

    main_module.SimpleVocabTokenizer = SimpleVocabTokenizer
    tok_path = project_root / "artifacts" / "cnn2d_tokenizer.pkl"
    if not tok_path.is_file():
        pytest.skip(f"CNN2D tokenizer not found at {tok_path}")
    with open(tok_path, "rb") as f:
        tok = pickle.load(f)
    assert tok.word_index[tok.oov_token] == 1
    assert tok.vocab_size > 0


def test_bert_loads_with_two_labels(project_root):
    model_dir = project_root / "models" / "bert_review_sentiment"
    if not model_dir.is_dir():
        pytest.skip(f"Fine-tuned BERT directory not found at {model_dir}")
    model, tokenizer = load_fine_tuned_bert(model_dir, device="cpu")
    assert model.config.num_labels == 2
    assert not model.training


def test_bert_missing_directory_raises_not_falls_back(tmp_path):
    fake_dir = tmp_path / "does_not_exist"
    with pytest.raises(FileNotFoundError):
        load_fine_tuned_bert(fake_dir, device="cpu")


def test_cnn2d_strict_load_rejects_shape_mismatch():
    """A checkpoint from a differently-shaped model must NOT silently load."""
    wrong_model = CNN2DReviewSentiment(vocab_size=500, embed_dim=8)  # different from default (30000, 100)
    state_dict = wrong_model.state_dict()
    target_model = CNN2DReviewSentiment()  # default (30000, 100)
    with pytest.raises(RuntimeError):
        target_model.load_state_dict(state_dict, strict=True)
