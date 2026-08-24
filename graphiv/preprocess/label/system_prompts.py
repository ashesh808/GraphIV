"""
The three instruction blocks the refine loop is built from, and the shared LM factory

One block per component, so a component's wording changes in exactly one place
"""

from __future__ import annotations

import dspy

from graphiv.core.config import Config

LABELER: str = (
    "You are labeling the intent of inline citations in scientific papers.\n"
    "Apply the labeling policy in `prompt` exactly as written, and do not substitute your own.\n"
    "Each sample is numbered and shows the section heading and the sentence, with the citation\n"
    "marker replaced by [CITE].\n"
    "Return one entry per sample, in the order given, with a short reason naming the phrase in\n"
    "the sentence that decided the label."
)

JUDGE: str = (
    "You are diagnosing a citation-labeling policy that produced wrong labels.\n"
    "You are shown each mistake: the sentence, the predicted label, the correct label, and the\n"
    "labeler's own stated reason.\n"
    "Read the reasons, not just the labels, and find what the policy made the labeler believe.\n"
    "Name the confusions that recur across mistakes, and say which rule or example in the policy\n"
    "caused each one.\n"
    "Write a critique of the policy, not a list of corrections for these samples."
)

DRAFTER: str = (
    "You are rewriting a citation-labeling policy so it survives the failures in the critique.\n"
    "Keep everything the critique does not fault, since the policy already works on most cases.\n"
    "Change the decision rules, the boundary wording and the worked examples that the critique\n"
    "names, and add an example only for a confusion the critique actually reports.\n"
    "Preserve the output contract and the label vocabulary exactly.\n"
    "Return the complete replacement policy, with no commentary around it."
)


def lm(model: str | None = None, temperature: float = 0.0, max_tokens: int = 8192) -> dspy.LM:
    """
    An LM bound to the project router, defaulting to the batch model
    """
    cfg = Config.load()
    return dspy.LM(
        f"openai/{model or cfg.map_model}",
        api_base=cfg.llm_base_url,
        api_key="none",
        temperature=temperature,
        max_tokens=max_tokens,
    )
