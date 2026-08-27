"""
The distilled student: what it gets right, and what it changed in the graph

The teacher-held-out report is read from disk, the gold score and the corpus census hit the store
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import matplotlib.pyplot as plt
import numpy as np
from _harness.report.theme import BARS, ON_SURFACE, PRIMARY, SECONDARY, apply_theme

_HERE = Path(__file__).resolve()
_EXP = _HERE.parents[1]
_REPO = _HERE.parents[4]

CACHE = _EXP / "cache"
RESULTS = _EXP / "results"
MODELS = _REPO / "data" / "models"
INTENTS = ["uses", "extends", "compares", "motivates", "background", "critiques"]

# the student that labeled every edge, and the one it replaces
SHIPPED = "v4"
PRIOR = "v1"
LIVE_TABLE = "citation_intent_v2"


def _report(version: str) -> dict[str, Any]:
    path = MODELS / f"student-{version}" / "test_report.json"
    return (
        json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    )  # pyright: ignore[reportAny]


def _confusion(matrix: list[list[int]], title: str, out: Path) -> None:
    """
    Row-normalized confusion over the six intents
    """
    apply_theme()
    m = np.array(matrix, dtype=float)
    row = m.sum(axis=1, keepdims=True)
    norm = np.divide(m, row, out=np.zeros_like(m), where=row > 0)
    fig, ax = plt.subplots(figsize=(6.2, 5.4))
    im = ax.imshow(norm, cmap="magma", vmin=0, vmax=1)
    ax.set_xticks(range(len(INTENTS)))
    ax.set_yticks(range(len(INTENTS)))
    ax.set_xticklabels(INTENTS, rotation=35, ha="right", fontsize=9)
    ax.set_yticklabels(INTENTS, fontsize=9)
    ax.set_xlabel("predicted")
    ax.set_ylabel("true")
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


def _f1_versions(reports: dict[str, dict[str, Any]], out: Path) -> None:
    """
    Per-class F1 for every student version that has a report
    """
    apply_theme()
    versions = sorted(reports)
    x = np.arange(len(INTENTS))
    width = 0.8 / max(1, len(versions))
    fig, ax = plt.subplots(figsize=(8.0, 4.2))
    for i, v in enumerate(versions):
        f1 = cast(dict[str, float], reports[v].get("intent_per_class_f1", {}))
        _ = ax.bar(
            x + (i - (len(versions) - 1) / 2) * width,
            [f1.get(k, 0.0) for k in INTENTS],
            width,
            label=f"student-{v}",
            color=BARS[i % len(BARS)],
        )
    ax.set_xticks(x)
    ax.set_xticklabels(INTENTS, rotation=25, ha="right", fontsize=9)
    ax.set_ylabel("F1")
    ax.set_ylim(0, 1)
    ax.set_title("per-class F1 on the teacher-held-out split")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)


def _census() -> dict[str, Any]:
    """
    The corpus distribution under both students, and how far they disagree
    """
    import psycopg

    from graphiv.core.config import Config

    out: dict[str, Any] = {}
    with psycopg.connect(Config.load().pg_dsn) as conn:
        rows = cast(
            list[tuple[str, int]],
            conn.execute(
                "SELECT intent, count(*) FROM citation WHERE intent IS NOT NULL GROUP BY 1"
            ).fetchall(),
        )
        out["prior"] = dict(rows)
        rows = cast(
            list[tuple[str, int]],
            conn.execute(f"SELECT intent, count(*) FROM {LIVE_TABLE} GROUP BY 1").fetchall(),
        )
        out["shipped"] = dict(rows)
        pair = cast(
            list[tuple[str, str, int]],
            conn.execute(
                f"SELECT c.intent, v.intent, count(*) FROM {LIVE_TABLE} v "
                "JOIN citation c ON c.citing_id = v.citing_id AND c.ordinal = v.ordinal "
                "WHERE c.intent IS NOT NULL GROUP BY 1, 2"
            ).fetchall(),
        )
        out["drift"] = [[a, b, n] for a, b, n in pair]
        score = cast(
            list[tuple[float, int]],
            conn.execute(
                f"SELECT width_bucket(intent_score, 0, 1, 10) / 10.0, count(*) "
                f"FROM {LIVE_TABLE} GROUP BY 1 ORDER BY 1"
            ).fetchall(),
        )
        out["confidence"] = [[float(b), int(n)] for b, n in score]
    return out


def _provenance() -> dict[str, Any]:
    """
    How the gold set was built, which decides what it can and cannot arbitrate

    Rows carrying `accepted` were pre-filled by student-PRIOR and waved through, so any score the
    prior student gets on them is circular.
    """
    import psycopg

    from graphiv.core.config import Config

    with psycopg.connect(Config.load().pg_dsn) as conn:
        rows = cast(
            list[tuple[str, int, int]],
            conn.execute(
                "SELECT g.labeler, count(*), count(*) FILTER (WHERE c.intent = g.intent) "
                "FROM gold_label g JOIN citation c "
                "ON c.citing_id = g.citing_id AND c.ordinal = g.ordinal "
                "WHERE c.intent IS NOT NULL GROUP BY 1"
            ).fetchall(),
        )
    return {a: {"n": n, "echoes_prior": e} for a, n, e in rows}


def _gold_score(version: str = SHIPPED) -> dict[str, Any]:
    """
    Score a student on the human gold set, which no teacher label ever touched
    """
    import psycopg
    import torch
    from transformers import AutoTokenizer

    from graphiv.core.config import Config
    from graphiv.preprocess.intent._common import MODEL_NAME, pin_hf_cache

    pin_hf_cache()
    from graphiv.preprocess.intent.model import load_student

    with psycopg.connect(Config.load().pg_dsn) as conn:
        rows = cast(
            list[tuple[str, str, str, str]],
            conn.execute(
                "SELECT COALESCE(c.section,''), c.sentence, g.intent, g.labeler "
                "FROM gold_label g JOIN citation c "
                "ON c.citing_id = g.citing_id AND c.ordinal = g.ordinal "
                "WHERE c.sentence IS NOT NULL AND g.intent IS NOT NULL"
            ).fetchall(),
        )
    if not rows:
        return {}
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = load_student(MODELS / f"student-{version}" / "best.pt", device)
    preds: list[str] = []
    for start in range(0, len(rows), 256):
        part = rows[start : start + 256]
        enc = tokenizer(
            [r[0] or "(unknown)" for r in part],
            [r[1] for r in part],
            max_length=128,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        with torch.no_grad():
            logits = model(enc["input_ids"].to(device), enc["attention_mask"].to(device))
        preds.extend(INTENTS[int(i)] for i in logits.argmax(-1).cpu().tolist())
    gold = [r[2] for r in rows]
    human = [i for i, r in enumerate(rows) if r[3] == "human"]
    accepted = [i for i, r in enumerate(rows) if r[3] != "human"]
    return {
        "n": len(rows),
        "accuracy": sum(p == g for p, g in zip(preds, gold, strict=True)) / len(rows),
        "n_human": len(human),
        "human_accuracy": (sum(preds[i] == gold[i] for i in human) / len(human) if human else 0.0),
        "n_accepted": len(accepted),
        "accepted_accuracy": (
            sum(preds[i] == gold[i] for i in accepted) / len(accepted) if accepted else 0.0
        ),
        "human_hits": sum(preds[i] == gold[i] for i in human),
        "confusion": [
            [sum(1 for p, g in zip(preds, gold, strict=True) if g == a and p == b) for b in INTENTS]
            for a in INTENTS
        ],
    }


def _base_rate(confusion: list[list[int]], observed: dict[str, int]) -> dict[str, Any]:
    """
    Undo the classifier's own bias, then score precision at the rate the corpus actually has

    Precision measured on a class-balanced gold set does not transfer to a corpus where one class
    is two thirds of the edges, so the observed marginal is inverted through P(pred | gold) first.
    """
    m = np.array(confusion, dtype=float)
    rows = m.sum(axis=1, keepdims=True)
    cond = np.divide(m, rows, out=np.zeros_like(m), where=rows > 0)
    total = max(1, sum(observed.values()))
    marginal = np.array([observed.get(k, 0) / total for k in INTENTS])
    try:
        prior = np.linalg.solve(cond.T, marginal)
    except np.linalg.LinAlgError:
        return {}
    negative = float(prior.min())
    prior = np.clip(prior, 0.0, None)
    prior = prior / max(prior.sum(), 1e-12)
    precision: dict[str, float] = {}
    for j, name in enumerate(INTENTS):
        predicted = float((prior * cond[:, j]).sum())
        precision[name] = float(prior[j] * cond[j, j] / predicted) if predicted > 0 else 0.0
    return {
        "observed": {k: float(v) for k, v in zip(INTENTS, marginal, strict=True)},
        "corrected": {k: float(v) for k, v in zip(INTENTS, prior, strict=True)},
        "corpus_precision": precision,
        "ci": _bootstrap(m, marginal),
        "condition": float(np.linalg.cond(cond.T)),
        # a negative unconstrained solution means the inversion needed clipping to stay a prior
        "clipped": negative < 0.0,
    }


def _bootstrap(
    m: np.ndarray[Any, Any], marginal: np.ndarray[Any, Any], draws: int = 4000
) -> dict[str, list[float]]:
    """
    A 95% interval on each corrected precision, from resampling the gold set

    The gold set is stratified by true class, so each row is redrawn multinomially at its own n,
    which is what carries the uncertainty of a leak estimated from a handful of counts.
    """
    rng = np.random.default_rng(0)
    counts = m.sum(axis=1)
    keep: list[list[float]] = []
    for _ in range(draws):
        boot = np.stack(
            [
                (
                    rng.multinomial(int(counts[i]), m[i] / counts[i])
                    if counts[i] > 0
                    else np.zeros(len(INTENTS))
                )
                for i in range(len(INTENTS))
            ]
        ).astype(float)
        rows = boot.sum(axis=1, keepdims=True)
        cond = np.divide(boot, rows, out=np.zeros_like(boot), where=rows > 0)
        try:
            prior = np.linalg.solve(cond.T, marginal)
        except np.linalg.LinAlgError:
            continue
        prior = np.clip(prior, 0.0, None)
        prior = prior / max(prior.sum(), 1e-12)
        got = [
            (
                float(prior[j] * cond[j, j] / d)
                if (d := float((prior * cond[:, j]).sum())) > 0
                else 0.0
            )
            for j in range(len(INTENTS))
        ]
        keep.append(got)
    if not keep:
        return {}
    arr = np.array(keep)
    lo, hi = np.percentile(arr, 2.5, axis=0), np.percentile(arr, 97.5, axis=0)
    return {k: [float(lo[j]), float(hi[j])] for j, k in enumerate(INTENTS)}


def _base_rate_fig(base: dict[str, Any], out: Path) -> None:
    """
    What the student reports against what the corpus holds, with precision at the true rate
    """
    apply_theme()
    observed = cast(dict[str, float], base["observed"])
    corrected = cast(dict[str, float], base["corrected"])
    precision = cast(dict[str, float], base["corpus_precision"])
    x = np.arange(len(INTENTS))
    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.2))
    _ = axes[0].bar(
        x - 0.2, [100 * observed[k] for k in INTENTS], 0.4, label="student says", color=PRIMARY
    )
    _ = axes[0].bar(
        x + 0.2,
        [100 * corrected[k] for k in INTENTS],
        0.4,
        label="bias-corrected",
        color=SECONDARY,
    )
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(INTENTS, rotation=25, ha="right", fontsize=9)
    axes[0].set_ylabel("share of edges (%)")
    axes[0].set_title("corpus distribution, reported against corrected")
    axes[0].legend(fontsize=8)
    axes[0].grid(True, alpha=0.3, axis="y")
    bars = axes[1].bar(
        x, [precision[k] for k in INTENTS], 0.6, color=[BARS[i % len(BARS)] for i in x]
    )
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(INTENTS, rotation=25, ha="right", fontsize=9)
    axes[1].set_ylabel("precision at the corpus rate")
    axes[1].set_ylim(0, 1)
    axes[1].set_title("what fraction of each label in the graph is right")
    axes[1].grid(True, alpha=0.3, axis="y")
    for b, k in zip(bars, INTENTS, strict=True):
        axes[1].text(
            b.get_x() + b.get_width() / 2,
            precision[k],
            f"{precision[k]:.2f}",
            ha="center",
            va="bottom",
            fontsize=8,
            color=ON_SURFACE,
        )
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)


def _shift(census: dict[str, Any], out: Path) -> None:
    """
    The corpus share of each intent before and after the relabel
    """
    apply_theme()
    prior = cast(dict[str, int], census["prior"])
    shipped = cast(dict[str, int], census["shipped"])
    tp, ts = max(1, sum(prior.values())), max(1, sum(shipped.values()))
    x = np.arange(len(INTENTS))
    fig, ax = plt.subplots(figsize=(7.6, 4.2))
    _ = ax.bar(
        x - 0.2,
        [100 * prior.get(k, 0) / tp for k in INTENTS],
        0.4,
        label=f"student-{PRIOR} (citation.intent)",
        color=PRIMARY,
    )
    _ = ax.bar(
        x + 0.2,
        [100 * shipped.get(k, 0) / ts for k in INTENTS],
        0.4,
        label=f"student-{SHIPPED} ({LIVE_TABLE})",
        color=SECONDARY,
    )
    ax.set_xticks(x)
    ax.set_xticklabels(INTENTS, rotation=25, ha="right", fontsize=9)
    ax.set_ylabel("share of edges (%)")
    ax.set_yscale("log")
    ax.set_title("corpus intent distribution, before and after the relabel")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3, axis="y")
    for xi, k in enumerate(INTENTS):
        ax.text(
            xi + 0.2,
            100 * shipped.get(k, 0) / ts,
            f"{100 * shipped.get(k, 0) / ts:.1f}",
            ha="center",
            va="bottom",
            fontsize=7,
            color=ON_SURFACE,
        )
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)


def tables(
    reports: dict[str, dict[str, Any]],
    gold: dict[str, Any],
    census: dict[str, Any],
    base: dict[str, Any],
    prior: dict[str, Any],
    base_prior: dict[str, Any],
    prov: dict[str, Any],
) -> None:
    """
    Write the metric vector as markdown and as LaTeX macros
    """
    rep = reports.get(SHIPPED, {})
    md = [
        f"student-{SHIPPED} on the teacher-held-out split (n={rep.get('n_test', 0):,}): "
        f"acc **{rep.get('intent_acc', 0):.3f}**, macro-F1 **{rep.get('intent_macro_f1', 0):.3f}**.",
    ]
    if gold:
        md.append(
            f"On the {gold['n']} gold occurrences: acc **{gold['accuracy']:.3f}** "
            f"({gold['n_human']} hand-labeled: **{gold['human_accuracy']:.3f}**)."
        )
    if prior and prov:
        acc = cast(dict[str, int], prov.get("accepted", {}))
        echo = acc.get("echoes_prior", 0) / max(acc.get("n", 1), 1)
        md += [
            "",
            f"**The gold set cannot rank these two students.** {acc.get('n', 0)} of its"
            f" {gold.get('n', 0)} rows were pre-filled by student-{PRIOR} and waved through, and"
            f" {echo:.1%} of those still carry exactly what student-{PRIOR} wrote. So"
            f" student-{PRIOR} scores **{prior['accuracy']:.3f}** here by construction, and"
            f" student-{SHIPPED}'s **{gold['accuracy']:.3f}** measures agreement with"
            f" student-{PRIOR}, not accuracy. Only the hand-typed rows are independent:",
            "",
            "| rows | student-" + SHIPPED + " | student-" + PRIOR + " |",
            "|---|--:|--:|",
            f"| hand-typed (n={gold.get('n_human', 0)}) | "
            f"{gold.get('human_accuracy', 0):.3f} | {prior.get('human_accuracy', 0):.3f} |",
            f"| pre-filled (n={gold.get('n_accepted', 0)}) | "
            f"{gold.get('accepted_accuracy', 0):.3f} | {prior.get('accepted_accuracy', 0):.3f} |",
            "",
            f"At n={gold.get('n_human', 0)} the hand-typed gap is"
            f" {abs(gold.get('human_hits', 0) - prior.get('human_hits', 0))} items, which settles"
            " nothing. An independent sample is what would.",
        ]
    md += ["", "| student | teacher-held-out acc | macro-F1 |", "|---|--:|--:|"]
    for v in sorted(reports):
        r = reports[v]
        md.append(
            f"| student-{v} | {r.get('intent_acc', 0):.3f} | {r.get('intent_macro_f1', 0):.3f} |"
        )
    md += ["", "| intent | F1 |", "|---|--:|"]
    f1 = cast(dict[str, float], rep.get("intent_per_class_f1", {}))
    for k in INTENTS:
        md.append(f"| {k} | {f1.get(k, 0.0):.3f} |")
    if base:
        md += [
            "",
            "Precision on the balanced gold set does not transfer to a corpus two thirds"
            " `background`, so the observed marginal is inverted through P(pred | gold)"
            f" (condition {base['condition']:.1f}).",
            "",
            f"Read the last two columns as departures from student-{PRIOR}, not as errors: the"
            " confusion behind them is the anchored gold set above.",
            "",
            f"| intent | student-{SHIPPED} says | bias-corrected | precision at the corpus rate"
            f" | student-{PRIOR} |",
            "|---|--:|--:|--:|--:|",
        ]
        ci = cast(dict[str, list[float]], base.get("ci", {}))
        was = cast(dict[str, float], base_prior.get("corpus_precision", {}))
        for k in INTENTS:
            lo, hi = ci.get(k, [0.0, 0.0])
            span = (
                f"{base['corpus_precision'][k]:.2f} ({lo:.2f}-{hi:.2f})"
                if ci
                else f"{base['corpus_precision'][k]:.2f}"
            )
            md.append(
                f"| {k} | {100 * base['observed'][k]:.2f}% | {100 * base['corrected'][k]:.2f}% "
                f"| {span} | {was[k]:.2f} |"
                if was
                else f"| {k} | {100 * base['observed'][k]:.2f}% | {100 * base['corrected'][k]:.2f}%"
                f" | {span} | |"
            )
    if census.get("drift"):
        drift = cast(list[list[Any]], census["drift"])
        same = sum(int(n) for a, b, n in drift if a == b)
        total = sum(int(n) for _, _, n in drift)
        md += [
            "",
            f"Against student-{PRIOR} over {total:,} shared edges, the two agree on "
            f"**{same / max(total, 1):.1%}**.",
        ]
    _ = (RESULTS / "metrics.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    macros = [
        f"\\newcommand{{\\StudentAcc}}{{{rep.get('intent_acc', 0):.3f}}}",
        f"\\newcommand{{\\StudentMacroF}}{{{rep.get('intent_macro_f1', 0):.3f}}}",
        f"\\newcommand{{\\StudentNTest}}{{{rep.get('n_test', 0):,}}}",
    ]
    if gold:
        macros.append(f"\\newcommand{{\\StudentGoldAcc}}{{{gold['accuracy']:.3f}}}")
    if census.get("shipped"):
        macros.append(
            f"\\newcommand{{\\EdgesLabeled}}{{{sum(cast(dict[str, int], census['shipped']).values()):,}}}"
        )
    _ = (RESULTS / "macros.tex").write_text("\n".join(macros) + "\n", encoding="utf-8")


def run(use_cache: bool) -> None:
    """
    Rebuild every figure and table, hitting the store only when the cache is cold
    """
    RESULTS.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    reports = {v: r for v in ("v1", "v2", "v3", "v4") if (r := _report(v))}
    if SHIPPED not in reports:
        raise SystemExit(f"no test_report for student-{SHIPPED}; train it first")

    live = CACHE / "live.json"
    if use_cache and live.exists():
        blob = cast(dict[str, Any], json.loads(live.read_text(encoding="utf-8")))
    else:
        blob = {
            "census": _census(),
            "gold": _gold_score(),
            "gold_prior": _gold_score(PRIOR),
            "provenance": _provenance(),
        }
        _ = live.write_text(json.dumps(blob, indent=1), encoding="utf-8")
    census = cast(dict[str, Any], blob.get("census", {}))
    gold = cast(dict[str, Any], blob.get("gold", {}))
    prior = cast(dict[str, Any], blob.get("gold_prior", {}))
    prov = cast(dict[str, Any], blob.get("provenance", {}))

    _confusion(
        cast(list[list[int]], reports[SHIPPED]["intent_confusion"]),
        f"Intent confusion (student-{SHIPPED}, teacher-held-out)",
        RESULTS / "intent_confusion.png",
    )
    if gold.get("confusion"):
        _confusion(
            cast(list[list[int]], gold["confusion"]),
            f"Intent confusion (student-{SHIPPED}, gold set n={gold['n']})",
            RESULTS / "gold_confusion.png",
        )
    _f1_versions(reports, RESULTS / "intent_f1.png")
    base: dict[str, Any] = {}
    if census.get("shipped"):
        _shift(census, RESULTS / "corpus_shift.png")
        if gold.get("confusion"):
            base = _base_rate(
                cast(list[list[int]], gold["confusion"]),
                cast(dict[str, int], census["shipped"]),
            )
            if base:
                _base_rate_fig(base, RESULTS / "base_rate.png")
    base_prior: dict[str, Any] = {}
    if census.get("prior") and prior.get("confusion"):
        base_prior = _base_rate(
            cast(list[list[int]], prior["confusion"]),
            cast(dict[str, int], census["prior"]),
        )
    tables(reports, gold, census, base, prior, base_prior, prov)

    _ = (CACHE / "summary.json").write_text(
        json.dumps(
            {
                "shipped": SHIPPED,
                "reports": {
                    v: {k: r[k] for k in ("n_test", "intent_acc", "intent_macro_f1")}
                    for v, r in reports.items()
                },
                "gold": {k: v for k, v in gold.items() if k != "confusion"},
                "gold_prior": {k: v for k, v in prior.items() if k != "confusion"},
                "corpus": census.get("shipped", {}),
                "base_rate": base,
                "base_rate_prior": base_prior,
                "provenance": prov,
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    print(
        f"[01-07] student-{SHIPPED} macro-F1 "
        f"{reports[SHIPPED].get('intent_macro_f1', 0):.3f}; wrote figures + tables",
        flush=True,
    )
