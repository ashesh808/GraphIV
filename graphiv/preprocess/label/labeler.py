"""
The labeler component: apply a policy to a batch of citations and explain each call

The reason field is what the judge reads, so a prediction is useless without it
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import dspy
from pydantic import BaseModel, Field

from ._common import INTENTS
from .sample import Sample
from .system_prompts import LABELER

DEFAULT_BATCH: int = 25
# the batched model serves four slots, each at a quarter of the router context
DEFAULT_PARALLELISM: int = 4


class LabeledCitation(BaseModel):
    """
    One label the model returns, keyed by its position in the batch
    """

    id: int = Field(description="the sample number this entry labels")
    intent: str = Field(
        description="one of uses, extends, compares, motivates, background, critiques"
    )
    reason: str = Field(description="the phrase in the sentence that decided the label")


class ApplyPolicy(dspy.Signature):
    """
    Label each citation by the given policy
    """

    prompt: str = dspy.InputField(desc="the labeling policy to apply verbatim")
    samples: str = dspy.InputField(desc="the numbered citations to label")
    predictions: list[LabeledCitation] = dspy.OutputField(desc="one entry per sample, in order")


@dataclass(frozen=True)
class Labeling:
    """
    One label as the refine loop stores it, with the gold it is scored against
    """

    sample: Sample
    intent: str
    reason: str
    ok: bool

    @property
    def correct(self) -> bool:
        """
        Whether the intent matches the gold label
        """
        return self.ok and self.intent == self.sample.intent


def render(batch: list[Sample]) -> str:
    """
    Render one batch as the numbered block the labeler answers
    """
    lines: list[str] = []
    for i, s in enumerate(batch):
        section = re.sub(r"^[\d\.]+\s*", "", s.section or "(unknown)")[:60]
        lines.append(f'[{i}] section="{section}" | "{s.sentence}"')
    return "\n".join(lines)


class Labeler(dspy.Module):
    """
    Apply one policy to a sample set, batching the calls
    """

    def __init__(
        self, batch_size: int = DEFAULT_BATCH, parallelism: int = DEFAULT_PARALLELISM
    ) -> None:
        super().__init__()
        self.batch_size: int = batch_size
        self.parallelism: int = max(1, parallelism)
        self.predict: dspy.Predict = dspy.Predict(ApplyPolicy.with_instructions(LABELER))

    def _one_batch(self, prompt: str, batch: list[Sample]) -> list[Labeling]:
        """
        Label one batch, filling any entry the model failed to return
        """
        try:
            out = self.predict(prompt=prompt, samples=render(batch))
            returned: list[LabeledCitation] = list(out.predictions)
        # a policy under evolution can produce any malformed output, and the sweep must continue
        except Exception as e:  # noqa: BLE001
            print(f"  labeler batch failed: {type(e).__name__}: {str(e)[:120]}", flush=True)
            returned = []
        by_id = {int(r.id): r for r in returned}
        preds: list[Labeling] = []
        for i, s in enumerate(batch):
            r = by_id.get(i)
            intent = (r.intent or "").strip().lower() if r else ""
            ok = intent in INTENTS
            preds.append(
                Labeling(
                    sample=s,
                    intent=intent if ok else "",
                    reason=(r.reason if r else "").strip(),
                    ok=ok,
                )
            )
        return preds

    def forward(self, prompt: str, samples: list[Sample]) -> list[Labeling]:
        """
        Label every sample under one policy, running the batches against the model's slots
        """
        batches = [
            samples[start : start + self.batch_size]
            for start in range(0, len(samples), self.batch_size)
        ]
        if not batches:
            return []
        if self.parallelism == 1 or len(batches) == 1:
            return [p for b in batches for p in self._one_batch(prompt, b)]
        with ThreadPoolExecutor(max_workers=self.parallelism) as pool:
            done = list(pool.map(lambda b: self._one_batch(prompt, b), batches))
        return [p for chunk in done for p in chunk]
