"""
Vision faithfulness: does a generated caption actually match the crop it describes

It answers whether the vision model can be leveraged, not merely whether it emitted text
"""

from __future__ import annotations

import asyncio
import base64
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI

from .._boot import LLM_BASE_URL

VISION_MODEL = "Gemma-4-26B-Vision"
_SYS = (
    "You are shown a research-paper figure and a CAPTION written about it. Decide whether the "
    "caption faithfully describes what is actually in the image. Answer ONE word: yes / partial / no."
)


async def _check_one(client: AsyncOpenAI, sem: asyncio.Semaphore, png: bytes, caption: str) -> str:
    async with sem:
        b64 = base64.b64encode(png).decode("ascii")
        try:
            resp = await client.chat.completions.create(
                model=VISION_MODEL,
                messages=[
                    {"role": "system", "content": _SYS},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"CAPTION: {caption}"},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{b64}"},
                            },
                        ],
                    },
                ],
                temperature=0.0,
                max_tokens=8,
                timeout=300,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )
        except Exception:  # noqa: BLE001
            return "skip"
        ans = (resp.choices[0].message.content or "").strip().lower()
        return "yes" if "yes" in ans else "partial" if "partial" in ans else "no"


async def _run(out_dir: Path, figures: dict[str, dict[str, Any]]) -> dict[str, Any]:
    items: list[tuple[bytes, str]] = []
    for info in figures.values():
        fp = out_dir / str(info.get("file", ""))
        cap = str(info.get("caption", ""))
        if fp.exists() and cap:
            items.append((fp.read_bytes(), cap))
    if not items:
        return {"checked": 0, "caption_faithfulness": 0.0}
    sem = asyncio.Semaphore(2)
    async with AsyncOpenAI(base_url=LLM_BASE_URL, api_key="none") as client:
        verdicts = await asyncio.gather(*[_check_one(client, sem, png, cap) for png, cap in items])
    scored = [v for v in verdicts if v != "skip"]
    yes = sum(v == "yes" for v in scored)
    partial = sum(v == "partial" for v in scored)
    score = (yes + 0.5 * partial) / len(scored) if scored else 0.0
    return {"checked": len(scored), "caption_faithfulness": round(score, 3)}


def caption_faithfulness(out_dir: Path, figures: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """
    Fraction of captions the vision model re-confirms against their saved crop
    """
    return asyncio.run(_run(out_dir, figures))
