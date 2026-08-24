"""
The drafter component: rewrite the policy so the critique's failures stop happening

It returns a whole replacement policy, because a patch against a moving prompt does not apply
"""

from __future__ import annotations

import dspy

from .system_prompts import DRAFTER


class Redraft(dspy.Signature):
    """
    Rewrite a labeling policy against a critique of it
    """

    seed_prompt: str = dspy.InputField(desc="the policy that produced the mistakes")
    critique: str = dspy.InputField(desc="what that policy taught wrong")
    new_prompt: str = dspy.OutputField(desc="the complete replacement policy")


class Drafter(dspy.Module):
    """
    Produce the next generation's policy
    """

    def __init__(self) -> None:
        super().__init__()
        self.predict: dspy.Predict = dspy.Predict(Redraft.with_instructions(DRAFTER))

    def forward(self, seed_prompt: str, critique: str) -> str:
        """
        Rewrite the policy, returning the seed unchanged when the rewrite fails
        """
        if not critique.strip():
            return seed_prompt
        try:
            out = self.predict(seed_prompt=seed_prompt, critique=critique)
            drafted = str(out.new_prompt).strip()
        # a failed redraft costs one generation, not the sweep
        except Exception as e:  # noqa: BLE001
            print(f"  drafter failed: {type(e).__name__}: {str(e)[:120]}", flush=True)
            return seed_prompt
        return drafted or seed_prompt
