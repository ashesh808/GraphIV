"""
Prompt refinement: what the APE loop did to the policy, and what it bought

Reads the frozen refine artifacts, so no model runs here
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from _harness.theme import (  # noqa: E402  # fmt: skip
    BARS,
    ON_SURFACE,
    PRIMARY,
    SECONDARY,
    TERTIARY,
    apply_theme,
)

_HERE = Path(__file__).resolve()
_EXP = _HERE.parents[1]
_REPO = _HERE.parents[4]

CACHE = _EXP / "cache"
RESULTS = _EXP / "results"
REFINE = _REPO / "data" / "citation_labels" / "refine"
PROMPTS = _REPO / "graphiv" / "preprocess" / "label" / "prompts"
INTENTS = ["uses", "extends", "compares", "motivates", "background", "critiques"]

# a worked example line, which is the policy's only per-case teaching device
EX_RE = re.compile(r"^\s*EX\d+\.", re.MULTILINE)
# a numbered decision rule, which is the policy's tie-breaking ladder
RULE_RE = re.compile(r"^\s{0,4}\d+\.\s", re.MULTILINE)


def _metrics() -> dict[str, Any]:
    path = REFINE / "metrics.json"
    if not path.exists():
        raise SystemExit(f"no refine metrics at {path}; run the refine loop first")
    return json.loads(path.read_text(encoding="utf-8"))  # pyright: ignore[reportAny]


def _preds(generation: int) -> list[dict[str, Any]]:
    path = REFINE / f"preds_{generation:02d}.json"
    return (
        json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    )  # pyright: ignore[reportAny]


def _structure(generation: int) -> dict[str, int]:
    """
    Count the teaching devices in one generation's policy
    """
    path = PROMPTS / f"citation_label_prompt_{generation:02d}.txt"
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    return {
        "digest": int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:8], 16),
        "chars": len(text),
        "lines": len(text.splitlines()),
        "words": len(text.split()),
        "examples": len(EX_RE.findall(text)),
        "rules": len(RULE_RE.findall(text)),
        "class_mentions": sum(text.count(k) for k in INTENTS),
    }


def _curve(scores: list[dict[str, Any]], best: int, out: Path) -> None:
    """
    Accuracy and macro-F1 per generation on both splits, with policy length behind them
    """
    apply_theme()
    gens = [int(s["generation"]) for s in scores]
    fig, ax = plt.subplots(figsize=(7.6, 4.4))
    series = (
        ("dev", "accuracy", PRIMARY, "-", "o"),
        ("dev", "macro_f1", SECONDARY, "-", "s"),
        ("test", "accuracy", PRIMARY, "--", "o"),
        ("test", "macro_f1", SECONDARY, "--", "s"),
    )
    for split, key, color, style, marker in series:
        label = ("dev " if split == "dev" else "held-out ") + key.replace("_", "-")
        _ = ax.plot(
            gens,
            [float(s[split][key]) for s in scores],
            color=color,
            linestyle=style,
            marker=marker,
            linewidth=2,
            label=label,
        )
    _ = ax.axvline(best, color=ON_SURFACE, linestyle=":", linewidth=1)
    ax.set_xlabel("generation")
    ax.set_ylabel("score")
    ax.set_xticks(gens)
    ax.set_ylim(0, 1)
    ax.set_title(f"APE loop: the critique only ever saw dev (best generation {best})")
    ax.legend(fontsize=8, ncol=2)
    ax.grid(True, alpha=0.3)
    size = ax.twinx()
    _ = size.plot(
        gens, [int(s["prompt_chars"]) for s in scores], color=TERTIARY, linewidth=1, alpha=0.6
    )
    size.set_ylabel("policy length (chars)", color=TERTIARY)
    size.tick_params(axis="y", labelcolor=TERTIARY)
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)


def _growth(struct: list[dict[str, int]], out: Path) -> None:
    """
    How the policy grew, split into the devices that grew
    """
    apply_theme()
    gens = list(range(len(struct)))
    fig, axes = plt.subplots(1, 2, figsize=(10.0, 3.8))
    _ = axes[0].plot(
        gens, [s.get("chars", 0) for s in struct], marker="o", color=PRIMARY, linewidth=2
    )
    axes[0].set_xlabel("generation")
    axes[0].set_ylabel("chars")
    axes[0].set_xticks(gens)
    axes[0].set_title("policy length")
    axes[0].grid(True, alpha=0.3)
    for i, key in enumerate(("examples", "rules", "lines")):
        _ = axes[1].plot(
            gens,
            [s.get(key, 0) for s in struct],
            marker="o",
            color=BARS[i % len(BARS)],
            linewidth=2,
            label=key,
        )
    axes[1].set_xlabel("generation")
    axes[1].set_ylabel("count")
    axes[1].set_xticks(gens)
    axes[1].set_title("teaching devices")
    axes[1].legend(fontsize=8)
    axes[1].grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)


def _confusion(rows: list[dict[str, Any]], title: str, out: Path) -> list[list[int]]:
    """
    The winning policy's confusion on the labeled set, row-normalized for reading
    """
    apply_theme()
    idx = {k: i for i, k in enumerate(INTENTS)}
    m = np.zeros((len(INTENTS), len(INTENTS)), dtype=float)
    for r in rows:
        gold, pred = str(r["gold"]), str(r["pred"])
        if gold in idx and pred in idx:
            m[idx[gold], idx[pred]] += 1
    total = m.sum(axis=1, keepdims=True)
    norm = np.divide(m, total, out=np.zeros_like(m), where=total > 0)
    fig, ax = plt.subplots(figsize=(6.2, 5.4))
    im = ax.imshow(norm, cmap="magma", vmin=0, vmax=1)
    ax.set_xticks(range(len(INTENTS)))
    ax.set_yticks(range(len(INTENTS)))
    ax.set_xticklabels(INTENTS, rotation=35, ha="right", fontsize=9)
    ax.set_yticklabels(INTENTS, fontsize=9)
    ax.set_xlabel("teacher label")
    ax.set_ylabel("gold")
    ax.set_title(title)
    for i in range(len(INTENTS)):
        for j in range(len(INTENTS)):
            ax.text(
                j,
                i,
                f"{norm[i, j]:.2f}",
                ha="center",
                va="center",
                color="white" if norm[i, j] < 0.6 else "black",
                fontsize=8,
            )
    _ = fig.colorbar(im, ax=ax, fraction=0.046, label="row-normalized")
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)
    return m.astype(int).tolist()


def _per_class_f1(rows: list[dict[str, Any]]) -> dict[str, float]:
    """
    F1 per intent, counting an unparsed label as wrong
    """
    out: dict[str, float] = {}
    for k in INTENTS:
        tp = sum(1 for r in rows if r["gold"] == k and r["pred"] == k)
        fp = sum(1 for r in rows if r["gold"] != k and r["pred"] == k)
        fn = sum(1 for r in rows if r["gold"] == k and r["pred"] != k)
        denom = 2 * tp + fp + fn
        out[k] = (2 * tp / denom) if denom else 0.0
    return out


def _class_drift(first: dict[str, float], best: dict[str, float], out: Path) -> None:
    """
    Which classes the loop actually repaired, seed policy against winner
    """
    apply_theme()
    x = np.arange(len(INTENTS))
    fig, ax = plt.subplots(figsize=(7.4, 4.0))
    _ = ax.bar(x - 0.2, [first[k] for k in INTENTS], 0.4, label="seed policy", color=BARS[0])
    _ = ax.bar(x + 0.2, [best[k] for k in INTENTS], 0.4, label="winning policy", color=BARS[2])
    ax.set_xticks(x)
    ax.set_xticklabels(INTENTS, rotation=25, ha="right", fontsize=9)
    ax.set_ylabel("F1")
    ax.set_ylim(0, 1)
    ax.set_title("per-class F1, seed policy against the winner")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3, axis="y")
    for xi, k in enumerate(INTENTS):
        ax.text(
            xi + 0.2,
            best[k],
            f"{best[k]:.2f}",
            ha="center",
            va="bottom",
            fontsize=7,
            color=ON_SURFACE,
        )
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)


def tables(meta: dict[str, Any], struct: list[dict[str, int]], best_f1: dict[str, float]) -> None:
    """
    Write the metric vector as markdown and as LaTeX macros
    """
    scores: list[dict[str, Any]] = meta["scores"]
    best = int(meta["best_generation"])
    seed_s, best_s = scores[0], scores[best]
    md = [
        f"Seed policy: dev acc **{seed_s['dev']['accuracy']:.3f}**, "
        f"held-out acc **{seed_s['test']['accuracy']:.3f}**.",
        f"Winner (generation {best}): dev acc **{best_s['dev']['accuracy']:.3f}**, "
        f"held-out acc **{best_s['test']['accuracy']:.3f}**, "
        f"held-out macro-F1 **{best_s['test']['macro_f1']:.3f}**.",
        "",
        "| gen | chars | lines | examples | rules | dev acc | dev F1 | held-out acc | held-out F1 |"
        " parsed |",
        "|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|",
    ]
    for s in scores:
        g = int(s["generation"])
        st = struct[g] if g < len(struct) else {}
        # a failed redraft returns the seed, so the generation repeats its predecessor verbatim
        repeat = " (repeat)" if g and st.get("digest") == struct[g - 1].get("digest") else ""
        md.append(
            f"| {g}{repeat} | {s['prompt_chars']} | {s['prompt_lines']} | "
            f"{st.get('examples', 0)} | "
            f"{st.get('rules', 0)} | {s['dev']['accuracy']:.3f} | {s['dev']['macro_f1']:.3f} | "
            f"{s['test']['accuracy']:.3f} | {s['test']['macro_f1']:.3f} | "
            f"{s['dev']['parse_rate']:.3f} |"
        )
    md += ["", "| intent | winner held-out F1 |", "|---|--:|"]
    for k in INTENTS:
        md.append(f"| {k} | {best_f1.get(k, 0.0):.3f} |")
    _ = (RESULTS / "metrics.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    macros = [
        f"\\newcommand{{\\ApeSeedAcc}}{{{seed_s['test']['accuracy']:.3f}}}",
        f"\\newcommand{{\\ApeBestAcc}}{{{best_s['test']['accuracy']:.3f}}}",
        f"\\newcommand{{\\ApeBestF}}{{{best_s['test']['macro_f1']:.3f}}}",
        f"\\newcommand{{\\ApeBestGen}}{{{best}}}",
        f"\\newcommand{{\\ApeSeedChars}}{{{seed_s['prompt_chars']}}}",
        f"\\newcommand{{\\ApeBestChars}}{{{best_s['prompt_chars']}}}",
        f"\\newcommand{{\\ApeDevN}}{{{seed_s['dev']['n']}}}",
        f"\\newcommand{{\\ApeTestN}}{{{seed_s['test']['n']}}}",
    ]
    _ = (RESULTS / "macros.tex").write_text("\n".join(macros) + "\n", encoding="utf-8")


def run(use_cache: bool) -> None:
    """
    Rebuild every figure and table from the frozen refine artifacts
    """
    _ = use_cache  # file reads are instant, the flag is kept for uniformity
    RESULTS.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    meta = _metrics()
    scores: list[dict[str, Any]] = meta["scores"]
    best = int(meta["best_generation"])
    struct = [_structure(int(s["generation"])) for s in scores]

    _curve(scores, best, RESULTS / "accuracy.png")
    _growth(struct, RESULTS / "prompt_growth.png")
    best_rows = _preds(best)
    matrix = _confusion(
        best_rows,
        f"Teacher confusion, winning policy (generation {best})",
        RESULTS / "teacher_confusion.png",
    )
    best_f1 = _per_class_f1(best_rows)
    _class_drift(_per_class_f1(_preds(0)), best_f1, RESULTS / "class_drift.png")
    tables(meta, struct, best_f1)

    summary = {
        "best_generation": best,
        "generations": len(scores),
        "dev_n": scores[0]["dev"]["n"],
        "test_n": scores[0]["test"]["n"],
        "seed_test_acc": scores[0]["test"]["accuracy"],
        "best_test_acc": scores[best]["test"]["accuracy"],
        "best_test_macro_f1": scores[best]["test"]["macro_f1"],
        "structure": struct,
        "repeats": [
            g
            for g in range(1, len(struct))
            if struct[g].get("digest") == struct[g - 1].get("digest")
        ],
        "best_per_class_f1": best_f1,
        "confusion": matrix,
    }
    _ = (CACHE / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(
        f"[01-06] best generation {best}: held-out acc "
        f"{scores[best]['test']['accuracy']:.3f} from {scores[0]['test']['accuracy']:.3f}; "
        f"wrote 4 figures + tables",
        flush=True,
    )
