"""
Shared paths and constants for the intent student

Weights and training artifacts stay under the project models directory
Nothing is allowed to leak into the global HuggingFace cache
"""

from __future__ import annotations

from pathlib import Path

from graphiv.preprocess.label._common import (
    ARXIV_SQLITE as ARXIV_SQLITE,
)
from graphiv.preprocess.label._common import (
    ARXIVKG_PG_DSN as ARXIVKG_PG_DSN,
)
from graphiv.preprocess.label._common import (
    BASE_PATH,
    MODELS_DIR,
)
from graphiv.preprocess.label._common import (
    HF_CACHE_DIR as HF_CACHE_DIR,
)
from graphiv.preprocess.label._common import (
    INTENTS as INTENTS,
)
from graphiv.preprocess.label._common import (
    LABELS_DB as LABELS_DB,
)
from graphiv.preprocess.label._common import (
    LABELS_DIR as LABELS_DIR,
)
from graphiv.preprocess.label._common import (
    pin_hf_cache as pin_hf_cache,
)

MODEL_NAME: str = "distilbert/distilbert-base-uncased"

# Training artifacts
# Bump the suffix when retraining
STUDENT_DIR: Path = MODELS_DIR / "student-v1"
STUDENT_CKPT: Path = STUDENT_DIR / "best.pt"
STUDENT_TOKENIZER_DIR: Path = STUDENT_DIR / "tokenizer"
STUDENT_LOSS_PNG: Path = STUDENT_DIR / "loss.png"
STUDENT_TEST_REPORT: Path = STUDENT_DIR / "test_report.json"
STUDENT_TRAIN_LOG: Path = STUDENT_DIR / "train_log.json"

# Cached tokenized dataset (avoid re-tokenizing on every run)
DATASET_CACHE: Path = BASE_PATH / "citation_labels" / "student_dataset.pt"

# 256 covers a section heading plus a citation sentence well into the tail
MAX_SEQ_LEN: int = 256

# Stratification budget (intent-stratified split)
TRAIN_FRAC: float = 0.80
VAL_FRAC: float = 0.10
TEST_FRAC: float = 0.10
SPLIT_SEED: int = 42
