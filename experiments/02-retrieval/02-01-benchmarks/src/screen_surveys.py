"""
Screen the keyword-selected candidates and derive each survey's question from its abstract

The title keyword admits observational sky surveys and benchmark papers, which are not reviews
The question comes from the abstract because a title-derived one under-scopes the survey
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from graphiv.core.llm import chat, parse_json
from graphiv.core.settings import MAP_MODEL

HERE = Path(__file__).parent

SYSTEM = """
You classify arXiv papers and write search questions.
A LITERATURE REVIEW surveys and organizes prior published work on a topic.
It is not a review paper if it reports new observations, new measurements, a new dataset,
a new benchmark, a new instrument or a new method, even when its title says survey.
An astronomical sky survey and a spectroscopic retrieval survey are observations, not reviews.
Answer with JSON only.
""".strip()

USER = """
Title: {title}

Abstract: {abstract}

Return JSON with exactly these keys:
  "is_review": true or false
  "reason": at most 12 words
  "question": one research question, 15 to 30 words, that a reader would ask to find the
    body of work this paper reviews. Cover the full scope of the abstract, not one subtopic.
    Do not name the paper, and do not use the words survey or review.
""".strip()


async def screen(s: dict[str, Any]) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
    """
    One classify-and-question call, degrading to a rejected entry when the model fails
    """
    txt, _, _ = await chat(
        MAP_MODEL,
        SYSTEM,
        USER.format(title=s["title"], abstract=str(s["abstract"])[:4000]),
        0.0,
        400,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )
    try:
        d: dict[str, Any] = parse_json(txt)  # pyright: ignore[reportExplicitAny]
    except (ValueError, TypeError, KeyError) as e:
        return {
            **s,
            "is_review": False,
            "reason": f"parse failed: {type(e).__name__}",
            "question": "",
        }
    return {
        **s,
        "is_review": bool(d.get("is_review")),
        "reason": str(d.get("reason", "")),
        "question": " ".join(str(d.get("question", "")).split()),
    }


async def main(src: str, dst: str, limit: int) -> None:
    """
    Screen every candidate in src concurrently and write the survivors to dst
    """
    pool: list[dict[str, Any]] = json.loads((HERE / "data" / src).read_text())[
        :limit
    ]  # pyright: ignore[reportExplicitAny]
    out = await asyncio.gather(*(screen(s) for s in pool))
    keep = [s for s in out if s["is_review"] and s["question"]]
    for s in out:
        mark = "keep" if s in keep else "DROP"
        print(
            f"  {mark}  {s['arxiv_id']}  {str(s['category']):<9} {str(s['title'])[:52]:<52} {s['reason'][:38]}"
        )
    print(f"\n{len(keep)}/{len(out)} kept")
    _ = (HERE / "data" / dst).write_text(json.dumps(keep, indent=1))


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "surveys.json"
    dst = sys.argv[2] if len(sys.argv) > 2 else "surveys_screened.json"
    lim = int(sys.argv[3]) if len(sys.argv) > 3 else 10**6
    asyncio.run(main(src, dst, lim))
