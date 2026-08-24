"""
The judge component: read the mistakes and say what the policy taught wrong

It is shown the labeler's own reasons, since a wrong label with a sound reason is a policy fault
"""

from __future__ import annotations

from collections import defaultdict

import dspy

from .labeler import Labeling
from .system_prompts import JUDGE

# a critique written from more than this many mistakes stops naming specifics
MAX_MISTAKES: int = 40


class Critique(dspy.Signature):
    """
    Diagnose a labeling policy from the mistakes it produced
    """

    incorrect_samples: str = dspy.InputField(desc="each mistake, with predicted, gold and reason")
    critique: str = dspy.OutputField(desc="what the policy taught wrong, and where")


def spread(mistakes: list[Labeling], limit: int) -> list[Labeling]:
    """
    Take the mistakes round-robin over confusion pairs, so a rare confusion is not crowded out
    """
    buckets: dict[tuple[str, str], list[Labeling]] = defaultdict(list)
    for p in mistakes:
        buckets[(p.sample.intent, p.intent if p.ok else "(unparsed)")].append(p)
    order = sorted(buckets, key=lambda k: (-len(buckets[k]), k))
    out: list[Labeling] = []
    depth = 0
    while len(out) < limit and any(len(buckets[k]) > depth for k in order):
        for k in order:
            if len(buckets[k]) > depth:
                out.append(buckets[k][depth])
                if len(out) == limit:
                    break
        depth += 1
    return out


def render(mistakes: list[Labeling], limit: int = MAX_MISTAKES) -> str:
    """
    Render the mistakes as the block the judge diagnoses
    """
    blocks: list[str] = []
    for i, p in enumerate(spread(mistakes, limit)):
        predicted = p.intent if p.ok else "(unparsed)"
        blocks.append(
            f"[{i}] sentence: {p.sample.sentence}\n"
            f"    section:   {p.sample.section or '(unknown)'}\n"
            f"    predicted: {predicted}\n"
            f"    gold:      {p.sample.intent}\n"
            f"    reason:    {p.reason or '(none given)'}"
        )
    return "\n\n".join(blocks)


class Judge(dspy.Module):
    """
    Turn a set of mistakes into one critique of the policy that caused them
    """

    def __init__(self, limit: int = MAX_MISTAKES) -> None:
        super().__init__()
        self.limit: int = limit
        self.predict: dspy.Predict = dspy.Predict(Critique.with_instructions(JUDGE))

    def forward(self, mistakes: list[Labeling]) -> str:
        """
        Diagnose one generation's mistakes
        """
        if not mistakes:
            return ""
        try:
            out = self.predict(incorrect_samples=render(mistakes, self.limit))
            return str(out.critique).strip()
        # a failed critique costs one generation, not the sweep
        except Exception as e:  # noqa: BLE001
            print(f"  judge failed: {type(e).__name__}: {str(e)[:120]}", flush=True)
            return ""
