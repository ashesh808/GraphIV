"""
The refine loop: label, judge the mistakes, redraft the policy, and keep the best generation

The critique only ever sees the dev half, so the held-out half scores a policy it never shaped
Every generation's policy is written to prompts/, so a winner is a file and not a log line
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import cast

import dspy

from ._common import INTENTS, LABELS_DIR
from .drafter import Drafter
from .judge import Judge
from .labeler import Labeler, Labeling
from .sample import Sample, label_rare, label_stratified
from .system_prompts import lm

PROMPTS_DIR: Path = Path(__file__).resolve().parent / "prompts"
RESULTS_DIR: Path = LABELS_DIR / "refine"
SEED_PROMPT: Path = PROMPTS_DIR / "citation_label_prompt_00.txt"

# the share of the evaluation set the critique never sees
DEFAULT_HOLDOUT: float = 0.4


@dataclass(frozen=True)
class Metrics:
    """
    One policy's score on one split
    """

    accuracy: float
    macro_f1: float
    parse_rate: float
    n: int


@dataclass(frozen=True)
class Score:
    """
    One generation: how big its policy grew and how it scored on both splits
    """

    generation: int
    prompt_chars: int
    prompt_lines: int
    prompt_words: int
    dev: Metrics
    test: Metrics


def macro_f1(preds: list[Labeling]) -> float:
    """
    Unweighted mean F1 over the six intents, counting an unparsed label as wrong
    """
    total = 0.0
    for intent in INTENTS:
        tp = sum(1 for p in preds if p.ok and p.intent == intent and p.sample.intent == intent)
        fp = sum(1 for p in preds if p.ok and p.intent == intent and p.sample.intent != intent)
        fn = sum(
            1 for p in preds if p.sample.intent == intent and not (p.ok and p.intent == intent)
        )
        denom = 2 * tp + fp + fn
        total += (2 * tp / denom) if denom else 0.0
    return total / len(INTENTS)


def measure(preds: list[Labeling]) -> Metrics:
    """
    Reduce one split's predictions to the metric row
    """
    n = len(preds)
    if not n:
        return Metrics(0.0, 0.0, 0.0, 0)
    return Metrics(
        accuracy=sum(p.correct for p in preds) / n,
        macro_f1=macro_f1(preds),
        parse_rate=sum(p.ok for p in preds) / n,
        n=n,
    )


def shape(prompt: str) -> tuple[int, int, int]:
    """
    The size of a policy as chars, lines and whitespace-separated words
    """
    return len(prompt), len(prompt.splitlines()), len(prompt.split())


def evaluation_set(source: str, n_stratified: int, n_rare: int, seed: int) -> list[Sample]:
    """
    The stratified draw, plus a rare-class draw when one is asked for
    """
    samples = label_stratified(n_stratified, source=source, seed=seed)
    if n_rare <= 0:
        return samples
    seen = {(s.citing_id, s.ordinal) for s in samples}
    extra = [
        s
        for s in label_rare(n_rare, source=source, seed=seed + 1)
        if (s.citing_id, s.ordinal) not in seen
    ]
    return samples + extra


def split(samples: list[Sample], holdout: float, seed: int) -> tuple[list[Sample], list[Sample]]:
    """
    Cut each class by the same fraction, so dev and held-out stay equally stratified
    """
    if holdout <= 0.0:
        return samples, []
    groups: dict[str, list[Sample]] = defaultdict(list)
    for s in samples:
        groups[s.intent].append(s)
    rng = random.Random(seed)
    dev: list[Sample] = []
    test: list[Sample] = []
    for intent in sorted(groups):
        rows = sorted(groups[intent], key=lambda s: (s.citing_id, s.ordinal))
        rng.shuffle(rows)
        cut = int(round(len(rows) * holdout))
        test.extend(rows[:cut])
        dev.extend(rows[cut:])
    rng.shuffle(dev)
    rng.shuffle(test)
    return dev, test


def dump(preds: list[Labeling], path: Path) -> None:
    """
    Write one split's predictions, so an experiment can rebuild the confusion matrix
    """
    rows = [
        {
            "citing_id": p.sample.citing_id,
            "ordinal": p.sample.ordinal,
            "gold": p.sample.intent,
            "pred": p.intent,
            "ok": p.ok,
            "reason": p.reason,
        }
        for p in preds
    ]
    _ = path.write_text(json.dumps(rows, indent=1), encoding="utf-8")


def plot(scores: list[Score], path: Path) -> None:
    """
    Draw accuracy against generation on both splits, with policy length behind it
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    gens = [s.generation for s in scores]
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    _ = ax.plot(gens, [s.dev.accuracy for s in scores], marker="o", label="dev accuracy")
    _ = ax.plot(gens, [s.dev.macro_f1 for s in scores], marker="s", label="dev macro-F1")
    if scores[0].test.n:
        _ = ax.plot(
            gens,
            [s.test.accuracy for s in scores],
            marker="o",
            linestyle="--",
            label="held-out accuracy",
        )
        _ = ax.plot(
            gens,
            [s.test.macro_f1 for s in scores],
            marker="s",
            linestyle="--",
            label="held-out macro-F1",
        )
    best = max(scores, key=lambda s: s.dev.accuracy)
    _ = ax.axvline(best.generation, color="0.6", linestyle=":", linewidth=1)
    _ = ax.set_xlabel("generation")
    _ = ax.set_ylabel("score")
    _ = ax.set_title(
        f"prompt refinement, dev n={scores[0].dev.n} held-out n={scores[0].test.n}, "
        f"best gen {best.generation}"
    )
    _ = ax.set_xticks(gens)
    _ = ax.set_ylim(0.0, 1.0)
    _ = ax.legend(fontsize=8)
    size = ax.twinx()
    _ = size.plot(gens, [s.prompt_chars for s in scores], color="0.7", linewidth=1)
    _ = size.set_ylabel("policy length (chars)", color="0.5")
    size.tick_params(axis="y", labelcolor="0.5")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def run(
    source_prompt: Path = SEED_PROMPT,
    generations: int = 6,
    source: str = "gold",
    n_stratified: int = 300,
    n_rare: int = 0,
    seed: int = 0,
    model: str | None = None,
    batch_size: int = 25,
    parallelism: int = 4,
    holdout: float = DEFAULT_HOLDOUT,
) -> Path:
    """
    Evolve the policy for `generations` rounds and return the winning prompt file
    """
    dspy.configure(lm=lm(model))
    samples = evaluation_set(source, n_stratified, n_rare, seed)
    if not samples:
        raise SystemExit(f"no labeled samples in source '{source}'")
    dev, test = split(samples, holdout, seed)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    print(
        f"[refine] {len(samples)} samples from '{source}': "
        f"dev {len(dev)}, held-out {len(test)}, {generations} generations",
        flush=True,
    )

    labeler, judge, drafter = Labeler(batch_size, parallelism), Judge(), Drafter()
    prompt = source_prompt.read_text(encoding="utf-8")
    scores: list[Score] = []
    paths: dict[int, Path] = {}

    for generation in range(generations):
        path = PROMPTS_DIR / f"citation_label_prompt_{generation:02d}.txt"
        if generation or not path.exists():
            _ = path.write_text(prompt, encoding="utf-8")
        paths[generation] = path
        dev_preds = cast(list[Labeling], labeler(prompt=prompt, samples=dev))
        test_preds = cast(list[Labeling], labeler(prompt=prompt, samples=test)) if test else []
        chars, lines, words = shape(prompt)
        s = Score(generation, chars, lines, words, measure(dev_preds), measure(test_preds))
        scores.append(s)
        dump(dev_preds + test_preds, RESULTS_DIR / f"preds_{generation:02d}.json")
        print(
            f"[refine] gen {generation}  dev acc {s.dev.accuracy:.3f} F1 {s.dev.macro_f1:.3f}  "
            f"held-out acc {s.test.accuracy:.3f} F1 {s.test.macro_f1:.3f}  "
            f"parsed {s.dev.parse_rate:.3f}  {chars} chars",
            flush=True,
        )
        if generation == generations - 1:
            break
        mistakes = [p for p in dev_preds if not p.correct]
        critique = cast(str, judge(mistakes=mistakes))
        if not critique:
            print("[refine] no critique, stopping early", flush=True)
            break
        _ = (RESULTS_DIR / f"critique_{generation:02d}.txt").write_text(critique, encoding="utf-8")
        prompt = cast(str, drafter(seed_prompt=prompt, critique=critique))

    best = max(scores, key=lambda s: s.dev.accuracy)
    winner = RESULTS_DIR / "citation_label_prompt_best.txt"
    _ = winner.write_text(paths[best.generation].read_text(encoding="utf-8"), encoding="utf-8")
    _ = (RESULTS_DIR / "metrics.json").write_text(
        json.dumps(
            {
                "source": source,
                "seed": seed,
                "model": model,
                "holdout": holdout,
                "best_generation": best.generation,
                "scores": [asdict(s) for s in scores],
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    plot(scores, RESULTS_DIR / "accuracy.png")
    print(
        f"[refine] best gen {best.generation} at dev accuracy {best.dev.accuracy:.3f}, "
        f"held-out {best.test.accuracy:.3f} -> {winner}",
        flush=True,
    )
    return winner


def main() -> None:
    """
    Run the refine loop from the command line
    """
    ap = argparse.ArgumentParser(description="evolve the citation labeling policy")
    _ = ap.add_argument("--source-prompt", type=Path, default=SEED_PROMPT)
    _ = ap.add_argument("--generations", type=int, default=6)
    _ = ap.add_argument("--source", default="gold", choices=("gold", "teacher"))
    _ = ap.add_argument("--stratified", type=int, default=300)
    _ = ap.add_argument("--rare", type=int, default=0)
    _ = ap.add_argument("--seed", type=int, default=0)
    _ = ap.add_argument("--model", default=None)
    _ = ap.add_argument("--batch-size", type=int, default=25)
    _ = ap.add_argument("--parallelism", type=int, default=4)
    _ = ap.add_argument("--holdout", type=float, default=DEFAULT_HOLDOUT)
    ns = ap.parse_args()
    _ = run(
        source_prompt=Path(str(ns.source_prompt)),  # pyright: ignore[reportAny]
        generations=int(ns.generations),  # pyright: ignore[reportAny]
        source=str(ns.source),  # pyright: ignore[reportAny]
        n_stratified=int(ns.stratified),  # pyright: ignore[reportAny]
        n_rare=int(ns.rare),  # pyright: ignore[reportAny]
        seed=int(ns.seed),  # pyright: ignore[reportAny]
        model=None if ns.model is None else str(ns.model),  # pyright: ignore[reportAny]
        batch_size=int(ns.batch_size),  # pyright: ignore[reportAny]
        parallelism=int(ns.parallelism),  # pyright: ignore[reportAny]
        holdout=float(ns.holdout),  # pyright: ignore[reportAny]
    )


if __name__ == "__main__":
    main()
