"""
DistilBERT student fine-tune on the Gemma teacher labels

The teacher store and the token cache are both arguments, so a retrain never clobbers a run
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from ._common import (
    ARXIVKG_PG_DSN,
    DATASET_CACHE,
    INTENTS,
    LABELS_DB,
    MAX_SEQ_LEN,
    MODEL_NAME,
    MODELS_DIR,
    SPLIT_SEED,
    TRAIN_FRAC,
    VAL_FRAC,
    pin_hf_cache,
)

pin_hf_cache()

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import psycopg  # noqa: E402
import torch  # noqa: E402
import torch.nn.functional as functional  # noqa: E402
from torch.utils.data import (  # noqa: E402
    DataLoader,
    TensorDataset,
    WeightedRandomSampler,
)
from transformers import (  # noqa: E402
    AutoTokenizer,
    PreTrainedTokenizerBase,
    get_linear_schedule_with_warmup,
)

from .model import IntentStudent  # noqa: E402

DEVICE: torch.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


# ---------------------------------------------------------------------------
# Dataset construction


@dataclass
class Example:
    """
    One labeled citation occurrence as the trainer sees it
    """

    citing_id: int
    ordinal: int
    section: str
    sentence: str
    intent_id: int


def load_examples(labels_db: Path = LABELS_DB) -> list[Example]:
    """
    Join a teacher store (ok=1) with PG (section, sentence)
    """
    print(f"loading labels from {labels_db}", flush=True)
    lconn = sqlite3.connect(labels_db)
    rows: list[tuple[int, int, str]] = cast(
        list[tuple[int, int, str]],
        lconn.execute("SELECT citing_id, ordinal, intent FROM label WHERE ok = 1").fetchall(),
    )
    lconn.close()
    print(f"  labels: {len(rows):,}", flush=True)

    intent_idx: dict[str, int] = {name: i for i, name in enumerate(INTENTS)}

    print("fetching (section, sentence) payloads from Postgres ...", flush=True)
    pg = psycopg.connect(ARXIVKG_PG_DSN)
    cur = pg.cursor()
    examples: list[Example] = []
    label_map: dict[tuple[int, int], str] = {(r[0], r[1]): r[2] for r in rows}

    pair_list: list[tuple[int, int]] = list(label_map.keys())
    chunk = 5000
    t0 = time.time()
    for start in range(0, len(pair_list), chunk):
        sub = pair_list[start : start + chunk]
        values_sql = ",".join("(%s,%s)" for _ in sub)
        params: list[int] = []
        for cid, ord_ in sub:
            params.extend([cid, ord_])
        _ = cur.execute(
            "SELECT c.citing_id, c.ordinal, COALESCE(c.section,''), c.sentence "
            "FROM citation c "
            f"JOIN (VALUES {values_sql}) AS v(cid, ord) "
            "ON c.citing_id = v.cid AND c.ordinal = v.ord "
            "WHERE c.sentence IS NOT NULL",
            params,
        )
        fetched: list[tuple[int, int, str, str]] = cast(
            list[tuple[int, int, str, str]], cur.fetchall()
        )
        for cid, ord_, section, sentence in fetched:
            examples.append(
                Example(
                    citing_id=cid,
                    ordinal=ord_,
                    section=section,
                    sentence=sentence,
                    intent_id=intent_idx[label_map[(cid, ord_)]],
                )
            )
        if (start // chunk) % 5 == 0:
            print(
                f"  fetched {len(examples):,}/{len(pair_list):,} " f"({time.time() - t0:.0f}s)",
                flush=True,
            )
    pg.close()
    print(f"  total: {len(examples):,} examples in {time.time() - t0:.0f}s", flush=True)
    return examples


def stratified_split(
    examples: list[Example], seed: int = SPLIT_SEED
) -> tuple[list[int], list[int], list[int]]:
    """
    Return (train_idx, val_idx, test_idx) stratified by intent
    """
    by_intent: dict[int, list[int]] = {i: [] for i in range(len(INTENTS))}
    for idx, ex in enumerate(examples):
        by_intent[ex.intent_id].append(idx)
    rng = random.Random(seed)
    train_idx: list[int] = []
    val_idx: list[int] = []
    test_idx: list[int] = []
    for intent_id in range(len(INTENTS)):
        ids = by_intent[intent_id][:]
        rng.shuffle(ids)
        n = len(ids)
        n_train = int(round(n * TRAIN_FRAC))
        n_val = int(round(n * VAL_FRAC))
        train_idx.extend(ids[:n_train])
        val_idx.extend(ids[n_train : n_train + n_val])
        test_idx.extend(ids[n_train + n_val :])
    rng.shuffle(train_idx)
    rng.shuffle(val_idx)
    rng.shuffle(test_idx)
    print(
        f"split: train={len(train_idx):,}  val={len(val_idx):,}  test={len(test_idx):,}",
        flush=True,
    )
    return train_idx, val_idx, test_idx


def tokenize_and_cache(
    examples: list[Example],
    tokenizer: PreTrainedTokenizerBase,
    cache: Path = DATASET_CACHE,
) -> dict[str, torch.Tensor]:
    """
    Tokenize all examples, cache to disk
    """
    if cache.exists():
        print(f"loading cached tokens from {cache}", flush=True)
        cached: dict[str, torch.Tensor] = torch.load(cache, weights_only=True)
        if cached["input_ids"].shape[0] == len(examples):
            return cached
        print("  cache size mismatch, re-tokenizing", flush=True)

    print(f"tokenizing {len(examples):,} examples ...", flush=True)
    sections = [ex.section or "(unknown)" for ex in examples]
    sentences = [ex.sentence for ex in examples]
    t0 = time.time()
    # Pair-encode: [CLS] section [SEP] sentence [SEP]
    enc = tokenizer(
        sections,
        sentences,
        max_length=MAX_SEQ_LEN,
        padding="max_length",
        truncation=True,
        return_tensors="pt",
    )
    print(f"  tokenized in {time.time() - t0:.1f}s", flush=True)

    intent_ids = torch.tensor([ex.intent_id for ex in examples], dtype=torch.long)
    out: dict[str, torch.Tensor] = {
        "input_ids": enc["input_ids"],
        "attention_mask": enc["attention_mask"],
        "intent_id": intent_ids,
    }
    cache.parent.mkdir(parents=True, exist_ok=True)
    torch.save(out, cache)
    print(f"  saved cache -> {cache}", flush=True)
    return out


# ---------------------------------------------------------------------------
# Training


@dataclass
class TrainConfig:
    """
    Every training hyperparameter, with the shipped defaults
    """

    epochs: int = 4
    train_batch_size: int = 64
    eval_batch_size: int = 256
    lr: float = 2e-5
    weight_decay: float = 0.01
    warmup_frac: float = 0.1
    log_every: int = 50
    eval_every_epoch: bool = True
    # rare-class handling
    oversample_power: float = 0.0  # 0=off, 0.5=sqrt(inv-freq), 1=full inv-freq
    focal_gamma: float = 0.0  # 0=plain CE, 2=standard focal
    use_class_weights: bool = True  # CE class weights; switch off when sampler balances


@dataclass
class TrainLog:
    """
    Per-step training and validation curves, kept for the loss plot
    """

    step: list[int] = field(default_factory=list)
    train_loss: list[float] = field(default_factory=list)
    val_step: list[int] = field(default_factory=list)
    val_loss: list[float] = field(default_factory=list)
    val_intent_acc: list[float] = field(default_factory=list)
    val_intent_macro_f1: list[float] = field(default_factory=list)


def class_weights(ids: torch.Tensor, n_classes: int) -> torch.Tensor:
    """
    Inverse-square-root class weights, normalized to mean one
    """
    counts = torch.bincount(ids, minlength=n_classes).float()
    counts = counts.clamp_min(1.0)
    inv = 1.0 / counts.sqrt()
    inv = inv / inv.mean()
    return inv


def sample_weights_from_classes(ids: torch.Tensor, n_classes: int, power: float) -> torch.Tensor:
    """
    Per-sample weight for WeightedRandomSampler

        weight_i = (1 / count[class(i)]) ** power, normalised so mean=1.
        power=0 -> uniform; power=0.5 -> sqrt(inv-freq); power=1 -> full inv-freq.
    """
    counts = torch.bincount(ids, minlength=n_classes).float().clamp_min(1.0)
    class_w = (1.0 / counts).pow(power)
    sample_w = class_w[ids]
    sample_w = sample_w / sample_w.mean()
    return sample_w


def focal_ce_loss(
    logits: torch.Tensor,
    targets: torch.Tensor,
    gamma: float,
    weight: torch.Tensor | None = None,
) -> torch.Tensor:
    """
    Focal cross-entropy. gamma=0 reduces to plain CE
    """
    if gamma <= 0:
        return functional.cross_entropy(logits, targets, weight=weight)
    logp = functional.log_softmax(logits, dim=-1)
    p_t = logp.gather(1, targets.unsqueeze(1)).squeeze(1).exp()
    focal = (1.0 - p_t).pow(gamma) * (-logp.gather(1, targets.unsqueeze(1)).squeeze(1))
    if weight is not None:
        w_t = weight[targets]
        focal = focal * w_t
    return focal.mean()


def macro_f1(y_true: np.ndarray, y_pred: np.ndarray, n_classes: int) -> tuple[float, list[float]]:
    """
    Macro F1 and the per-class F1 scores behind it
    """
    f1s: list[float] = []
    for c in range(n_classes):
        tp = int(((y_pred == c) & (y_true == c)).sum())
        fp = int(((y_pred == c) & (y_true != c)).sum())
        fn = int(((y_pred != c) & (y_true == c)).sum())
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        f1s.append(f1)
    return float(np.mean(f1s)), f1s


def evaluate(
    model: IntentStudent,
    loader: DataLoader,
    intent_w: torch.Tensor | None,
    cfg: TrainConfig,
) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]: mixed scalars + np arrays
    """
    Score the model over a loader and return the metric bundle
    """
    model.eval()
    losses: list[float] = []
    y_intent_t: list[np.ndarray] = []
    y_intent_p: list[np.ndarray] = []
    with torch.no_grad():
        for input_ids, attention_mask, intent_id in loader:
            input_ids = input_ids.to(DEVICE)
            attention_mask = attention_mask.to(DEVICE)
            intent_id = intent_id.to(DEVICE)
            with torch.autocast("cuda", dtype=torch.bfloat16):
                intent_logits = model(input_ids, attention_mask)
                loss = focal_ce_loss(intent_logits.float(), intent_id, cfg.focal_gamma, intent_w)
            losses.append(float(loss.item()))
            y_intent_t.append(intent_id.cpu().numpy())
            y_intent_p.append(intent_logits.argmax(-1).cpu().numpy())
    yi_t = np.concatenate(y_intent_t)
    yi_p = np.concatenate(y_intent_p)
    intent_acc = float((yi_p == yi_t).mean())
    intent_f1, intent_per_class_f1 = macro_f1(yi_t, yi_p, len(INTENTS))
    return {
        "loss": float(np.mean(losses)),
        "intent_acc": intent_acc,
        "intent_macro_f1": intent_f1,
        "intent_per_class_f1": dict(zip(INTENTS, intent_per_class_f1, strict=False)),
        "y_intent_true": yi_t,
        "y_intent_pred": yi_p,
    }


def confusion(y_true: np.ndarray, y_pred: np.ndarray, n_classes: int) -> list[list[int]]:
    """
    Confusion matrix as nested lists, ready for JSON
    """
    cm = np.zeros((n_classes, n_classes), dtype=np.int64)
    for t, p in zip(y_true.tolist(), y_pred.tolist(), strict=False):
        cm[t, p] += 1
    return cm.tolist()


def train(
    cfg: TrainConfig,
    out_suffix: str,
    labels_db: Path = LABELS_DB,
    dataset_cache: Path = DATASET_CACHE,
) -> None:
    """
    Train the student and write the checkpoint, curves and test report
    """
    student_dir = MODELS_DIR / f"student-{out_suffix}"
    student_ckpt = student_dir / "best.pt"
    student_tokenizer_dir = student_dir / "tokenizer"
    student_loss_png = student_dir / "loss.png"
    student_test_report = student_dir / "test_report.json"
    student_train_log = student_dir / "train_log.json"
    student_dir.mkdir(parents=True, exist_ok=True)
    print(f"training run -> {student_dir}", flush=True)

    print(f"loading tokenizer ({MODEL_NAME})", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    examples = load_examples(labels_db)
    tokens = tokenize_and_cache(examples, tokenizer, dataset_cache)

    train_idx, val_idx, test_idx = stratified_split(examples)
    train_t = torch.tensor(train_idx, dtype=torch.long)
    val_t = torch.tensor(val_idx, dtype=torch.long)
    test_t = torch.tensor(test_idx, dtype=torch.long)

    def make_dataset(ix: torch.Tensor) -> TensorDataset:
        return TensorDataset(
            tokens["input_ids"][ix],
            tokens["attention_mask"][ix],
            tokens["intent_id"][ix],
        )

    train_ds = make_dataset(train_t)
    val_ds = make_dataset(val_t)
    test_ds = make_dataset(test_t)

    train_intent_ids = tokens["intent_id"][train_t]
    if cfg.oversample_power > 0:
        sample_w = sample_weights_from_classes(train_intent_ids, len(INTENTS), cfg.oversample_power)
        sampler = WeightedRandomSampler(
            weights=sample_w.tolist(), num_samples=len(train_t), replacement=True
        )
        print(
            f"WeightedRandomSampler enabled (power={cfg.oversample_power}); "
            f"effective per-class share per batch (approx):",
            flush=True,
        )
        # expected counts under the sampler
        counts = torch.bincount(train_intent_ids, minlength=len(INTENTS)).float()
        share = counts * (1.0 / counts).pow(cfg.oversample_power)
        share = share / share.sum()
        for n, s in zip(INTENTS, share.tolist(), strict=False):
            print(f"    {n:>10s}: {s:.3f}", flush=True)
        train_loader = DataLoader(
            train_ds,
            batch_size=cfg.train_batch_size,
            sampler=sampler,
            num_workers=2,
            pin_memory=True,
            persistent_workers=True,
        )
    else:
        train_loader = DataLoader(
            train_ds,
            batch_size=cfg.train_batch_size,
            shuffle=True,
            num_workers=2,
            pin_memory=True,
            persistent_workers=True,
        )

    val_loader = DataLoader(
        val_ds,
        batch_size=cfg.eval_batch_size,
        shuffle=False,
        num_workers=2,
        pin_memory=True,
        persistent_workers=True,
    )
    test_loader = DataLoader(
        test_ds,
        batch_size=cfg.eval_batch_size,
        shuffle=False,
        num_workers=2,
        pin_memory=True,
        persistent_workers=True,
    )

    # CE class weights (None if sampler is already balancing)
    intent_w: torch.Tensor | None = None
    if cfg.use_class_weights:
        intent_w = class_weights(train_intent_ids, len(INTENTS)).to(DEVICE)
        print(
            "intent class weights : "
            + ", ".join(f"{n}={w:.2f}" for n, w in zip(INTENTS, intent_w.tolist(), strict=False)),
            flush=True,
        )
    else:
        print("CE class weights disabled (sampler balances).", flush=True)

    print(f"building model ({MODEL_NAME})", flush=True)
    model = IntentStudent(n_intent=len(INTENTS)).to(DEVICE)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"  params: {n_params / 1e6:.1f}M", flush=True)

    optimizer = torch.optim.AdamW(model.parameters(), lr=cfg.lr, weight_decay=cfg.weight_decay)
    total_steps = cfg.epochs * len(train_loader)
    warmup_steps = int(total_steps * cfg.warmup_frac)
    scheduler = get_linear_schedule_with_warmup(
        optimizer, num_warmup_steps=warmup_steps, num_training_steps=total_steps
    )
    print(
        f"training: {cfg.epochs} epochs, {len(train_loader)} batches/epoch, "
        f"warmup {warmup_steps} steps",
        flush=True,
    )

    log = TrainLog()
    best_val_f1: float = -1.0
    global_step = 0
    t_start = time.time()
    smoothed_loss: float | None = None

    for epoch in range(cfg.epochs):
        model.train()
        for _batch_idx, (input_ids, attention_mask, intent_id) in enumerate(train_loader):
            input_ids = input_ids.to(DEVICE, non_blocking=True)
            attention_mask = attention_mask.to(DEVICE, non_blocking=True)
            intent_id = intent_id.to(DEVICE, non_blocking=True)

            optimizer.zero_grad(set_to_none=True)
            with torch.autocast("cuda", dtype=torch.bfloat16):
                intent_logits = model(input_ids, attention_mask)
                loss = focal_ce_loss(intent_logits.float(), intent_id, cfg.focal_gamma, intent_w)
            loss.backward()
            _ = torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            scheduler.step()

            global_step += 1
            loss_v = float(loss.item())
            smoothed_loss = (
                loss_v if smoothed_loss is None else 0.97 * smoothed_loss + 0.03 * loss_v
            )
            log.step.append(global_step)
            log.train_loss.append(loss_v)

            if global_step % cfg.log_every == 0:
                lr_now = optimizer.param_groups[0]["lr"]
                elapsed = time.time() - t_start
                print(
                    f"  ep {epoch} step {global_step:>5d}/{total_steps}  "
                    f"loss {smoothed_loss:.4f}  lr {lr_now:.2e}  "
                    f"({elapsed:.0f}s elapsed)",
                    flush=True,
                )

        # end-of-epoch validation
        val = evaluate(model, val_loader, intent_w, cfg)
        log.val_step.append(global_step)
        log.val_loss.append(float(val["loss"]))
        log.val_intent_acc.append(float(val["intent_acc"]))
        log.val_intent_macro_f1.append(float(val["intent_macro_f1"]))
        print(
            f"  [val ep{epoch}] loss={val['loss']:.4f}  "
            f"intent acc={val['intent_acc']:.4f} macroF1={val['intent_macro_f1']:.4f}",
            flush=True,
        )

        val_f1 = float(val["intent_macro_f1"])
        if val_f1 > best_val_f1:
            best_val_f1 = val_f1
            torch.save(model.state_dict(), student_ckpt)
            print(
                f"  ↑ new best val intent macroF1={val_f1:.4f}  saved {student_ckpt}",
                flush=True,
            )

    # ---- final plot + test ----
    print("\nfinal test eval ...", flush=True)
    state = torch.load(student_ckpt, map_location=DEVICE, weights_only=True)
    _ = model.load_state_dict(state)
    test = evaluate(model, test_loader, intent_w, cfg)

    # tokenizer save
    student_tokenizer_dir.mkdir(parents=True, exist_ok=True)
    tokenizer.save_pretrained(str(student_tokenizer_dir))

    # plot
    plot_loss(log, student_loss_png)

    # save training log
    train_log_obj: dict[str, object] = {
        "labels_db": str(labels_db),
        "config": {
            "epochs": cfg.epochs,
            "train_batch_size": cfg.train_batch_size,
            "eval_batch_size": cfg.eval_batch_size,
            "lr": cfg.lr,
            "weight_decay": cfg.weight_decay,
            "warmup_frac": cfg.warmup_frac,
            "max_seq_len": MAX_SEQ_LEN,
            "oversample_power": cfg.oversample_power,
            "focal_gamma": cfg.focal_gamma,
            "use_class_weights": cfg.use_class_weights,
        },
        "n_train": len(train_idx),
        "n_val": len(val_idx),
        "n_test": len(test_idx),
        "best_val_intent_macro_f1": best_val_f1,
        "step": log.step,
        "train_loss": log.train_loss,
        "val_step": log.val_step,
        "val_loss": log.val_loss,
        "val_intent_acc": log.val_intent_acc,
        "val_intent_macro_f1": log.val_intent_macro_f1,
    }
    student_train_log.write_text(json.dumps(train_log_obj, indent=2))

    # test report
    report: dict[str, object] = {
        "n_test": len(test_idx),
        "intent_acc": float(test["intent_acc"]),
        "intent_macro_f1": float(test["intent_macro_f1"]),
        "intent_per_class_f1": test["intent_per_class_f1"],
        "intent_distribution_pred": dict(Counter(test["y_intent_pred"].tolist())),
        "intent_distribution_true": dict(Counter(test["y_intent_true"].tolist())),
        "intent_confusion": confusion(
            test["y_intent_true"],
            test["y_intent_pred"],
            len(INTENTS),
        ),
    }
    student_test_report.write_text(json.dumps(report, indent=2, default=int))
    print(
        f"\nTEST  intent acc={test['intent_acc']:.4f} macroF1={test['intent_macro_f1']:.4f}",
        flush=True,
    )
    print(f"per-class intent F1: {test['intent_per_class_f1']}", flush=True)
    print(f"\nartifacts in {student_dir}", flush=True)


def plot_loss(log: TrainLog, out_path: Path) -> None:
    """
    Plot the training and validation curves
    """
    fig, ax1 = plt.subplots(figsize=(8, 4.5))
    if log.train_loss:
        # smooth the train loss with a moving avg for readability
        window = max(1, len(log.train_loss) // 200)
        smoothed = np.convolve(log.train_loss, np.ones(window) / window, mode="valid")
        smooth_steps = log.step[window - 1 :]
        _ = ax1.plot(
            log.step,
            log.train_loss,
            lw=0.4,
            alpha=0.3,
            color="steelblue",
            label="train (raw)",
        )
        _ = ax1.plot(smooth_steps, smoothed, lw=1.5, color="steelblue", label="train (smoothed)")
    if log.val_step:
        _ = ax1.plot(
            log.val_step,
            log.val_loss,
            "o-",
            color="darkorange",
            label="val",
            lw=2,
            ms=6,
        )
    ax1.set_xlabel("step")
    ax1.set_ylabel("weighted intent loss")
    ax1.set_title("DistilBERT student fine-tune, loss")
    ax1.grid(alpha=0.3)
    ax1.legend(loc="upper right")

    if log.val_step:
        ax2 = ax1.twinx()
        _ = ax2.plot(
            log.val_step,
            log.val_intent_macro_f1,
            "s--",
            color="green",
            label="val intent macroF1",
        )
        ax2.set_ylabel("val intent macro F1", color="green")
        ax2.tick_params(axis="y", labelcolor="green")
        ax2.legend(loc="lower right")

    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)
    print(f"  loss plot -> {out_path}", flush=True)


def main() -> None:
    """
    Parse the training arguments and train
    """
    parser = argparse.ArgumentParser()
    _ = parser.add_argument(
        "--epochs", type=int, default=4
    )  # pyright: ignore[reportUnusedCallResult]
    _ = parser.add_argument(
        "--batch-size", type=int, default=64
    )  # pyright: ignore[reportUnusedCallResult]
    _ = parser.add_argument(
        "--lr", type=float, default=2e-5
    )  # pyright: ignore[reportUnusedCallResult]
    _ = parser.add_argument(  # pyright: ignore[reportUnusedCallResult]
        "--oversample-power",
        type=float,
        default=0.0,
        help="WeightedRandomSampler power. 0=off, 0.5=sqrt(inv-freq), 1=full inv-freq.",
    )
    _ = parser.add_argument(  # pyright: ignore[reportUnusedCallResult]
        "--focal-gamma",
        type=float,
        default=0.0,
        help="Focal loss gamma; 0 = plain CE.",
    )
    _ = parser.add_argument(  # pyright: ignore[reportUnusedCallResult]
        "--no-class-weights",
        action="store_true",
        help="Disable CE class weights (use this when --oversample-power > 0).",
    )
    _ = parser.add_argument(  # pyright: ignore[reportUnusedCallResult]
        "--out-suffix",
        type=str,
        default="v1",
        help="Saves to data/models/student-<suffix>/.",
    )
    _ = parser.add_argument(  # pyright: ignore[reportUnusedCallResult]
        "--labels-db",
        type=str,
        default=str(LABELS_DB),
        help="Teacher store to train on.",
    )
    _ = parser.add_argument(  # pyright: ignore[reportUnusedCallResult]
        "--dataset-cache",
        type=str,
        default=str(DATASET_CACHE),
        help="Tokenized dataset cache; give a fresh path for a fresh teacher store.",
    )
    args = parser.parse_args()
    cfg = TrainConfig(
        epochs=int(args.epochs),  # pyright: ignore[reportAny]
        train_batch_size=int(args.batch_size),  # pyright: ignore[reportAny]
        lr=float(args.lr),  # pyright: ignore[reportAny]
        oversample_power=float(args.oversample_power),  # pyright: ignore[reportAny]
        focal_gamma=float(args.focal_gamma),  # pyright: ignore[reportAny]
        use_class_weights=not bool(args.no_class_weights),  # pyright: ignore[reportAny]
    )
    train(
        cfg,
        out_suffix=str(args.out_suffix),  # pyright: ignore[reportAny]
        labels_db=Path(str(args.labels_db)),  # pyright: ignore[reportAny]
        dataset_cache=Path(str(args.dataset_cache)),  # pyright: ignore[reportAny]
    )


if __name__ == "__main__":
    main()
