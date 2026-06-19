"""Shared paths and constants for the phase_3.bert student.

The student is a DistilBERT-base fine-tune of the 100k Gemma teacher labels
in `data/citation_labels/labels.db`. Trained weights and training artifacts
live under `MODELS_DIR / student-v1/` so nothing leaks into the global
HuggingFace cache (we already pinned that via `pin_hf_cache`).
"""

from __future__ import annotations

from pathlib import Path

from label._common import (
    ARXIVKG_PG_DSN as ARXIVKG_PG_DSN,
    ARXIV_SQLITE as ARXIV_SQLITE,
    BASE_PATH,
    HF_CACHE_DIR as HF_CACHE_DIR,
    INTENTS as INTENTS,
    LABELS_DB as LABELS_DB,
    LABELS_DIR as LABELS_DIR,
    MODELS_DIR,
    POLARITIES as POLARITIES,
    pin_hf_cache as pin_hf_cache,
)

MODEL_NAME: str = "distilbert/distilbert-base-uncased"

# Training artifacts. Bump the suffix when retraining.
STUDENT_DIR: Path = MODELS_DIR / "student-v1"
STUDENT_CKPT: Path = STUDENT_DIR / "best.pt"
STUDENT_TOKENIZER_DIR: Path = STUDENT_DIR / "tokenizer"
STUDENT_LOSS_PNG: Path = STUDENT_DIR / "loss.png"
STUDENT_TEST_REPORT: Path = STUDENT_DIR / "test_report.json"
STUDENT_TRAIN_LOG: Path = STUDENT_DIR / "train_log.json"

# Cached tokenized dataset (avoid re-tokenizing on every run).
DATASET_CACHE: Path = BASE_PATH / "citation_labels" / "student_dataset.pt"

# Tokenization budget. Citation sentences are short (~60 tokens median);
# allowing 256 covers section heading + sentence comfortably for the tail.
MAX_SEQ_LEN: int = 256

# Stratification budget (intent-stratified split).
TRAIN_FRAC: float = 0.80
VAL_FRAC: float = 0.10
TEST_FRAC: float = 0.10
SPLIT_SEED: int = 42
