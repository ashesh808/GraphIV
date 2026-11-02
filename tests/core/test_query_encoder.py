"""Nomic model identity and real CPU pooling, isolated from research OpenMP libraries."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from src.core.query_encoder import CODE_REVISION, DIMENSION, MODEL_REVISION, NomicQueryEncoder


def test_local_encoder_requires_the_existing_model_and_pinned_architecture(tmp_path: Path) -> None:
    encoder = NomicQueryEncoder("nomic-embed-text-v2-moe", cache=tmp_path)
    assert encoder.dimension == DIMENSION == 768
    assert encoder.revision == MODEL_REVISION
    assert encoder.code_revision == CODE_REVISION
    assert encoder._model is None
    assert not list(tmp_path.iterdir())
    with pytest.raises(ValueError, match="existing nomic"):
        NomicQueryEncoder("different-embedding-space", cache=tmp_path)
    with pytest.raises(ValueError, match="immutable"):
        NomicQueryEncoder(cache=tmp_path, code_revision="main")
    with pytest.raises(ValueError, match="positive integer"):
        NomicQueryEncoder(cache=tmp_path, threads=0)


def test_real_torch_pooling_uses_prefix_padding_mask_full_dimension_and_l2_normalization() -> None:
    # A separate interpreter avoids loading macOS research Torch and FAISS's
    # different bundled libomp copies into one test process. No model is downloaded.
    code = r"""
import math
from types import SimpleNamespace
import torch
from src.core.query_encoder import NomicQueryEncoder

calls = []
class Tokenizer:
    def __call__(self, text, **kwargs):
        calls.append((text, kwargs))
        return {"input_ids": torch.tensor([[1, 2, 0]]), "attention_mask": torch.tensor([[1, 1, 0]])}
class Model:
    def __call__(self, **kwargs):
        hidden = torch.zeros(1, 3, 768)
        hidden[0, 0, 0] = 3
        hidden[0, 1, 1] = 4
        hidden[0, 2] = 1e9
        return SimpleNamespace(last_hidden_state=hidden)
encoder = NomicQueryEncoder()
encoder._model = Model()
encoder._tokenizer = Tokenizer()
result = encoder.embed("citation graph retrieval")
assert len(result) == 768
assert abs(result[0] - .6) < 1e-6 and abs(result[1] - .8) < 1e-6
assert all(value == 0 for value in result[2:])
assert abs(math.sqrt(sum(value * value for value in result)) - 1) < 1e-6
assert calls[0][0] == "search_query: citation graph retrieval"
assert calls[0][1] == {
    "padding": True, "truncation": True, "max_length": 512, "return_tensors": "pt"
}
encoder.encode_document("Paper title", "The original abstract")
assert calls[1][0] == "search_document: Title: Paper title\nAbstract: The original abstract"
class InvalidModel:
    def __call__(self, **kwargs):
        return SimpleNamespace(last_hidden_state=torch.zeros(1, 3, 384))
encoder._model = InvalidModel()
try:
    encoder.embed("must not change embedding space")
except ValueError as error:
    assert "incompatible embedding shape" in str(error)
else:
    raise AssertionError("Invalid dimension must fail; no alternate embedding provider is allowed")
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
