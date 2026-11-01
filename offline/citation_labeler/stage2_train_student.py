"""
Distill the teacher's labels into a DistilBERT classifier and keep the best epoch

Section and sentence go in as a pair, which is what separates `uses` from `background`
256 tokens covers every citation sentence measured, where the longest was 205
"""

from __future__ import annotations

import argparse
import csv
import random
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import torch
from numpy.typing import NDArray
from torch import nn
from torch.utils.data import DataLoader, TensorDataset, WeightedRandomSampler
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from src.core.config import load_config
from src.core.paths import OFFLINE_CONFIG

INTENTS = ("uses", "extends", "compares", "motivates", "background", "critiques")
INTENT_ID = {name: i for i, name in enumerate(INTENTS)}
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def attention_kind() -> str:
    """
    The fastest attention backend that actually imports on this machine

    Returns:
        Either `flash_attention_2` or `sdpa`.
    """
    try:
        import flash_attn  # noqa: F401, PLC0415

        return "flash_attention_2"
    except ImportError:
        return "sdpa"


def macro_f1(truth: NDArray[np.int64], pred: NDArray[np.int64]) -> float:
    """
    Unweighted mean F1 over the six classes

    Args:
        truth: true class ids.
        pred: predicted class ids.

    Returns:
        The macro F1.
    """
    scores: list[float] = []
    for c in range(len(INTENTS)):
        tp = int(((pred == c) & (truth == c)).sum())
        fp = int(((pred == c) & (truth != c)).sum())
        fn = int(((pred != c) & (truth == c)).sum())
        denom = 2 * tp + fp + fn
        scores.append(2 * tp / denom if denom else 0.0)
    return float(np.mean(scores))


class Student:
    """
    The teacher's CSV turned into a trained classifier
    """

    def __init__(self, labeler_path: str, seed: int, splits: tuple[float, float, float]) -> None:
        """
        Args:
            labeler_path: the citation_labeler data directory.
            seed: shuffle seed, so a split is reproducible.
            splits: train, validation and test fractions.
        """
        self.root = Path(labeler_path)
        self.seed = seed
        self.splits = splits
        self.model_name = "distilbert/distilbert-base-uncased"
        self.max_seq = 256
        self.oversample_power = 0.6
        self.parts: dict[str, list[dict[str, str]]] = {}

    def load(self) -> dict[str, int]:
        """
        Read the teacher's labels and cut them into three reproducible splits

        Returns:
            Row counts per split.
        """
        path = self.root / "teacher_labeled.csv"
        with path.open(encoding="utf-8") as fh:
            rows = [r for r in csv.DictReader(fh) if r.get("intent") in INTENT_ID]
        random.Random(self.seed).shuffle(rows)

        n = len(rows)
        a = int(n * self.splits[0])
        b = a + int(n * self.splits[1])
        self.parts = {"train": rows[:a], "val": rows[a:b], "test": rows[b:]}
        sizes = {k: len(v) for k, v in self.parts.items()}
        print(f"[student] {n:,} rows from {path.name}: {sizes}", flush=True)
        return sizes

    def _encode(
        self, rows: list[dict[str, str]], tok: Any
    ) -> TensorDataset:  # pyright: ignore[reportExplicitAny]
        """
        Tokenize a split as (section, sentence) pairs

        Args:
            rows: the split.
            tok: the tokenizer.

        Returns:
            A dataset of input ids, mask and label.
        """
        enc = tok(
            [r["section"] or "(unknown)" for r in rows],
            [r["sentence"] for r in rows],
            max_length=self.max_seq,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        y = torch.tensor([INTENT_ID[r["intent"]] for r in rows], dtype=torch.long)
        return TensorDataset(enc["input_ids"], enc["attention_mask"], y)

    def _sampler(self) -> WeightedRandomSampler:
        """
        Draw rare intents more often, since real citations are about three quarters background

        Uses the settled inverse-frequency power from the previous pipeline, where the sampler
        does the balancing alone and cross-entropy stays unweighted to avoid counting it twice.

        Returns:
            A sampler over the training split.
        """
        labels = [INTENT_ID[r["intent"]] for r in self.parts["train"]]
        counts = Counter(labels)
        weight = {c: (1.0 / n) ** self.oversample_power for c, n in counts.items()}
        per_row = [weight[c] for c in labels]
        return WeightedRandomSampler(per_row, num_samples=len(labels), replacement=True)

    def train(self, epochs: int, batch: int, lr: float) -> Path:
        """
        Finetune the backbone, checkpoint every epoch and keep the best validation macro F1

        Args:
            epochs: passes over the training split.
            batch: rows per step.
            lr: peak learning rate.

        Returns:
            The path of the best checkpoint.
        """
        if not self.parts:
            _ = self.load()
        attn = attention_kind()
        print(f"[student] {self.model_name} on {DEVICE} with {attn}", flush=True)

        tok = AutoTokenizer.from_pretrained(self.model_name)
        model = AutoModelForSequenceClassification.from_pretrained(
            self.model_name, num_labels=len(INTENTS), attn_implementation=attn
        ).to(DEVICE)

        train_rows = self._encode(self.parts["train"], tok)
        train_dl = DataLoader(train_rows, batch_size=batch, sampler=self._sampler())
        val_dl = DataLoader(self._encode(self.parts["val"], tok), batch_size=batch)
        opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
        sched = torch.optim.lr_scheduler.OneCycleLR(
            opt, max_lr=lr, total_steps=max(1, epochs * len(train_dl)), pct_start=0.1
        )
        loss_fn = nn.CrossEntropyLoss()

        ckpts = self.root / "ckpts"
        ckpts.mkdir(parents=True, exist_ok=True)
        best_f1, best_path = -1.0, ckpts / "iteration_00.pt"
        log: list[str] = []

        for epoch in range(epochs):
            model.train()
            running = 0.0
            for ids, mask, y in train_dl:
                ids, mask, y = ids.to(DEVICE), mask.to(DEVICE), y.to(DEVICE)
                with torch.autocast("cuda", dtype=torch.bfloat16, enabled=DEVICE.type == "cuda"):
                    logits = model(input_ids=ids, attention_mask=mask).logits
                    loss = loss_fn(logits.float(), y)
                loss.backward()
                _ = nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                opt.step()
                sched.step()
                opt.zero_grad(set_to_none=True)
                running += float(loss)

            truth, pred = self._infer(model, val_dl)
            f1 = macro_f1(truth, pred)
            acc = float((truth == pred).mean())
            line = (
                f"epoch {epoch} loss {running / max(1, len(train_dl)):.4f} "
                f"val_acc {acc:.4f} val_macro_f1 {f1:.4f}"
            )
            print(f"[student] {line}", flush=True)
            log.append(line)

            path = ckpts / f"iteration_{epoch:02d}.pt"
            torch.save(model.state_dict(), path)
            if f1 > best_f1:
                best_f1, best_path = f1, path

        _ = shutil.copy(best_path, self.root / "best.pt")
        tok.save_pretrained(self.root / "tokenizer")
        logs = self.root / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        _ = (logs / "student.log").write_text("\n".join(log) + "\n", encoding="utf-8")
        print(f"[student] best was {best_path.name} at macro F1 {best_f1:.4f}", flush=True)
        return self.root / "best.pt"

    def _infer(
        self, model: Any, dl: DataLoader
    ) -> tuple[NDArray[np.int64], NDArray[np.int64]]:  # pyright: ignore[reportExplicitAny]
        """
        Run a loader and collect truth and predicted class ids

        Args:
            model: the classifier.
            dl: a loader over an encoded split.

        Returns:
            True and predicted ids.
        """
        model.eval()
        truth: list[int] = []
        pred: list[int] = []
        with torch.no_grad():
            for ids, mask, y in dl:
                with torch.autocast("cuda", dtype=torch.bfloat16, enabled=DEVICE.type == "cuda"):
                    logits = model(input_ids=ids.to(DEVICE), attention_mask=mask.to(DEVICE)).logits
                pred.extend(logits.argmax(-1).cpu().tolist())
                truth.extend(y.tolist())
        return np.asarray(truth), np.asarray(pred)

    def benchmark(self, rows: int, batch: int) -> float:
        """
        Time the forward pass so a multi-day labeling run is not launched on a guess

        Args:
            rows: how many synthetic rows to push through.
            batch: rows per step.

        Returns:
            Rows per second.
        """
        attn = attention_kind()
        tok = AutoTokenizer.from_pretrained(self.model_name)
        model = AutoModelForSequenceClassification.from_pretrained(
            self.model_name, num_labels=len(INTENTS), attn_implementation=attn
        ).to(DEVICE)
        sample = [
            {
                "section": "Related Work",
                "sentence": "We follow the approach of [CITE] here." * 3,
                "intent": "uses",
            }
            for _ in range(rows)
        ]
        dl = DataLoader(self._encode(sample, tok), batch_size=batch)
        _ = self._infer(model, dl)  # warm the kernels before timing
        t0 = time.time()
        _ = self._infer(model, dl)
        rate = rows / (time.time() - t0)
        print(f"[student] {attn}: {rate:,.0f} rows/s, so 73.0M rows is {73e6 / rate / 3600:.1f} h")
        return rate


def report(student: Student) -> None:
    """
    Score the best checkpoint and write the three figures

    Args:
        student: a Student whose splits are loaded.
    """
    import matplotlib.pyplot as plt  # noqa: PLC0415
    from plot import apply_theme, series  # noqa: PLC0415

    apply_theme()

    tok = AutoTokenizer.from_pretrained(student.root / "tokenizer")
    model = AutoModelForSequenceClassification.from_pretrained(
        student.model_name, num_labels=len(INTENTS), attn_implementation=attention_kind()
    )
    _ = model.load_state_dict(torch.load(student.root / "best.pt", weights_only=True))
    model = model.to(DEVICE)

    dl = DataLoader(student._encode(student.parts["test"], tok), batch_size=256)
    truth, pred = student._infer(model, dl)
    print(
        f"[student] test acc {float((truth == pred).mean()):.4f} "
        f"macro F1 {macro_f1(truth, pred):.4f}",
        flush=True,
    )

    logs = student.root / "logs"
    logs.mkdir(parents=True, exist_ok=True)

    cm = np.zeros((len(INTENTS), len(INTENTS)), dtype=int)
    for g, p in zip(truth, pred, strict=True):
        cm[g, p] += 1
    fig, ax = plt.subplots(figsize=(6, 5))
    _ = ax.imshow(cm, cmap="viridis")
    _ = ax.set_title("student against the teacher, held-out split")
    _ = ax.set_xticks(range(len(INTENTS)), INTENTS, rotation=45, ha="right")
    _ = ax.set_yticks(range(len(INTENTS)), INTENTS)
    _ = ax.set_xlabel("predicted")
    _ = ax.set_ylabel("teacher label")
    for i in range(len(INTENTS)):
        for j in range(len(INTENTS)):
            """
            Viridis runs light at the top of its range, so a fixed white number vanishes there.
            """
            shade = "#000000" if cm[i, j] > cm.max() * 0.6 else "#ffffff"
            _ = ax.text(j, i, str(int(cm[i, j])), ha="center", va="center", color=shade, fontsize=8)
    fig.tight_layout()
    fig.savefig(logs / "student_matrix.png", dpi=150)
    plt.close(fig)

    counts = Counter(r["intent"] for part in student.parts.values() for r in part)
    fig, ax = plt.subplots(figsize=(6, 4))
    names = list(INTENTS)
    _ = ax.bar(names, [counts.get(n, 0) for n in names], color=series()[: len(names)])
    _ = ax.set_title("intents in teacher_labeled.csv")
    _ = ax.set_ylabel("citations")
    _ = ax.set_title("teacher_labeled.csv class distribution")
    _ = plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    fig.tight_layout()
    fig.savefig(logs / "class_distribution.png", dpi=150)
    plt.close(fig)
    print(f"[student] wrote {logs}/student_matrix.png and class_distribution.png", flush=True)


def main() -> None:
    """
    Read the config, then load, train and report
    """
    ap = argparse.ArgumentParser()
    _ = ap.add_argument("--config_path", default=str(OFFLINE_CONFIG))
    _ = ap.add_argument("--benchmark", type=int, default=0, help="time N rows and exit")
    args = ap.parse_args()

    cfg = load_config(str(args.config_path))
    cl = cfg["citation_labeler"]
    splits: list[float] = [float(x) for x in cl["LABELER_SPLITS"]]
    student = Student(
        labeler_path=str(cl["LABELER_PATH"]),
        seed=int(cl["LABELER_SEED"]),
        splits=(splits[0], splits[1], splits[2]),
    )
    student.model_name = str(cl["LABELER_MODEL"])
    student.max_seq = int(cl["LABELER_MAX_SEQ"])

    if int(args.benchmark):  # pyright: ignore[reportAny]
        _ = student.benchmark(
            int(args.benchmark), int(cl["LABELER_BATCH"])
        )  # pyright: ignore[reportAny]
        return

    _ = student.load()
    _ = student.train(
        epochs=int(cl["LABELER_EPOCHS"]),
        batch=int(cl["LABELER_TRAIN_BATCH"]),
        lr=float(cl["LABELER_LR"]),
    )
    report(student)


if __name__ == "__main__":
    main()
