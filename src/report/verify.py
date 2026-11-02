"""Repair generated prose against original sources, retaining only evidenced replacements.

The model checks meaning; the local guard checks that every replacement carries a real,
verbatim excerpt from the source it cites. Excerpts are audit inputs, never citation quotations
rendered in the report. This complements, rather than replaces, the corpus identity check.
"""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict

from src.core import llm
from src.report.ground import read_ids

LOG = logging.getLogger(__name__)

REPAIR_TOKENS = 3200
MIN_QUOTE_CHARS = 30
MAX_QUOTE_CHARS = 800

REPAIR = """Check and repair a literature-review {kind} using ONLY the original sources below.
The draft is untrusted generated text, not evidence. Use no outside knowledge.

ORIGINAL SOURCES (JSON maps each arXiv id to its own supplied abstract or source section):
{sources}

UNTRUSTED DRAFT:
{draft}

Return replacement factual sentences, not a verdict on the draft. Delete unsupported claims.
You may shorten or rewrite claims to match the sources. A shorter answer is better than filling
gaps. Every replacement must be entailed by the cited source excerpt in its full source context.

Rules:
- Preserve the distinction between a paper's background motivation and its own method/results.
  A general historical limitation is not a demonstrated failure of the method being proposed.
- Attribute a method, formal connection, number, or result only to the paper that states it.
  Do not transfer a later paper's contribution to an earlier related paper.
- Comparisons must state their reported evaluation scope. Different papers' evaluations do not
  establish a global best method, consensus, necessity, or universal limitation. Remove such
  conclusions unless the supplied evidence actually establishes that scope.
- Do not invent costs, limitations, caveats, trade-offs, improvements, or open questions. When a
  source gives no limitation, omit the limitation rather than infer one from the model's design.
- A citation path or predicted intent label establishes connectivity, not methodological ancestry,
  influence, agreement, causation, or a scientific comparison. Do not infer any of those from it.
- For an open question, retain it only if a source section explicitly identifies that issue as
  unresolved or future work. Abstracts or titles alone do not establish an open limitation.
- Each claim is one factual sentence (or one open question), with inline arXiv:<id> citations.
  Its sources must contain every cited id and no others. Use only ids in ORIGINAL SOURCES.
- For each source give an exact supporting excerpt of 30 to 800 characters copied from THAT
  source, including the words that support the claim. Do not paraphrase excerpts. An excerpt
  that merely names the subject does not support a claim about its results or limitations.
- Excerpts are internal abstract/source evidence, not citation sentences. Never put invented or
  reconstructed quotations into the replacement text. Preserve prose, without headings/lists.
- Use paragraph numbers starting at 0, in order. Empty claims is correct if nothing is supported.

JSON only:
{{"claims":[{{"text":"Supported sentence arXiv:2401.00001.","paragraph":0,
"sources":[{{"id":"2401.00001","quote":"Exact supporting words from this source."}}]}}]}}
"""


def _space(value: str) -> str:
    return " ".join(value.split())


def repair_text(
    model: llm.Gemma,
    draft: str,
    sources: dict[str, str],
    *,
    kind: str = "prose",
) -> str:
    """Replace a draft with source-checked claims, dropping invalid or absent evidence.

    The original draft is never a fallback. Matching excerpts do not mechanically prove
    entailment; the model is instructed to check that against the complete original source.
    """
    originals = {key.lower(): value for key, value in sources.items() if value.strip()}
    if not draft.strip() or not originals:
        return ""
    parsed = llm.parse_json(
        model.ask(
            REPAIR.format(
                kind=kind,
                sources=json.dumps(originals, ensure_ascii=False),
                draft=draft,
            ),
            max_tokens=REPAIR_TOKENS,
        )
    )
    raw = parsed.get("claims") if isinstance(parsed, dict) else None
    if not isinstance(raw, list):
        LOG.warning("source repair returned no valid claims")
        return ""
    paragraphs: dict[int, list[str]] = defaultdict(list)
    previous = 0
    rejected = 0
    for claim in raw:
        if not isinstance(claim, dict):
            rejected += 1
            continue
        text, paragraph, supports = (
            claim.get("text"),
            claim.get("paragraph"),
            claim.get("sources"),
        )
        if (
            not isinstance(text, str)
            or not text.strip()
            # A single supported sentence must not carry an unreviewed second sentence.
            or re.search(r"[.!?]\s+[A-Z\"“]", text) is not None
            or text.lstrip().startswith(("#", "- ", ">"))
            or type(paragraph) is not int
            or not previous <= paragraph <= 20
            or not isinstance(supports, list)
            or not supports
        ):
            rejected += 1
            continue
        cited = read_ids(text)
        evidence: set[str] = set()
        valid = bool(cited)
        for support in supports:
            if not isinstance(support, dict):
                valid = False
                break
            ident, quote = support.get("id"), support.get("quote")
            if not isinstance(ident, str) or not isinstance(quote, str):
                valid = False
                break
            ident, quote = ident.lower(), _space(quote)
            if (
                ident not in originals
                or not MIN_QUOTE_CHARS <= len(quote) <= MAX_QUOTE_CHARS
                or quote not in _space(originals[ident])
            ):
                valid = False
                break
            evidence.add(ident)
        if not valid or cited != evidence:
            rejected += 1
            continue
        paragraphs[paragraph].append(_space(text))
        previous = paragraph
    LOG.info(
        "source repair retained %d claims, dropped %d", sum(map(len, paragraphs.values())), rejected
    )
    return "\n\n".join(" ".join(sentences) for sentences in paragraphs.values())
