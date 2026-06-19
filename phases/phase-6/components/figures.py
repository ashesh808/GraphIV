"""P3 — locate, crop, and vision-caption a paper's key figure for the report.

Finds the first 'Figure 1' caption in the early pages, crops the column region above it
(the figure, vector or raster), and asks Gemma-4-26B-Vision to describe it. The crop is saved
and embedded in the report with an arXiv:id + p.N reference, so figures are grounded too.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF  # pyright: ignore[reportMissingTypeStubs]


from llm import chat, ensure_loaded  # noqa: E402
from pdf_figures import pdf_path  # noqa: E402

VISION_MODEL = "Gemma-4-26B-Vision"
CONCURRENCY = 2  # vision crops are large; keep the single 3090 calm
_NO_THINK: dict[str, object] = {"chat_template_kwargs": {"enable_thinking": False}}
_FIG_CAP: re.Pattern[str] = re.compile(r"^\s*(figure|fig\.?)\s*1\b", re.IGNORECASE)
_CAP_SYS = (
    "Describe this research-paper figure in 2-3 sentences: what is drawn (boxes/arrows/axes/"
    "labels) and what it conveys. Be concrete and factual; do not invent. No preamble, no "
    "reasoning."
)


def first_figure(
    arxiv_id: str, max_pages: int = 6, dpi: int = 150
) -> tuple[int, bytes, str] | None:
    """Crop the first figure (region above its 'Figure 1' caption). (page, png, caption_text)."""
    p = pdf_path(arxiv_id)
    if p is None:
        return None
    try:
        with fitz.open(p) as doc:  # pyright: ignore[reportUnknownMemberType]
            for pno in range(min(max_pages, doc.page_count)):
                page = doc.load_page(pno)  # pyright: ignore[reportUnknownMemberType]
                blocks: Any = page.get_text("blocks")  # pyright: ignore[reportUnknownMemberType]  # fmt: skip
                cap = next(
                    (b for b in blocks if _FIG_CAP.match(str(b[4]))),
                    None,  # pyright: ignore[reportAny]
                )
                if cap is None:
                    continue
                cx0, cy0, cx1, cy1 = (
                    float(cap[0]),
                    float(cap[1]),
                    float(cap[2]),
                    float(cap[3]),
                )
                # figure = column region above the caption, down to the nearest block above.
                above = [
                    float(b[3])
                    for b in blocks
                    if float(b[3]) <= cy0 + 1 and _overlap_x(b, cx0, cx1)
                ]
                top = (
                    max(above) if above else page.rect.y0
                )  # pyright: ignore[reportUnknownMemberType]
                top = max(
                    page.rect.y0, min(top, cy0 - 250)
                )  # pyright: ignore[reportUnknownMemberType]
                rect = fitz.Rect(cx0 - 8, top, cx1 + 8, cy1)
                if rect.height < 60 or rect.width < 60:
                    rect = fitz.Rect(
                        page.rect.x0, page.rect.y0, page.rect.x1, cy1
                    )  # pyright: ignore[reportUnknownMemberType]
                pix = page.get_pixmap(
                    clip=rect, dpi=dpi
                )  # pyright: ignore[reportUnknownMemberType]
                png: bytes = pix.tobytes(
                    "png"
                )  # pyright: ignore[reportUnknownMemberType]
                return pno + 1, png, " ".join(str(cap[4]).split())[:300]
    except Exception:  # noqa: BLE001
        return None
    return None


def _overlap_x(b: tuple[float, ...], x0: float, x1: float) -> bool:
    return not (float(b[2]) < x0 or float(b[0]) > x1)


async def _caption_one(sem: asyncio.Semaphore, title: str, png: bytes) -> str | None:
    # llm.chat carries retry+restart, so a cold vision-model swap doesn't drop the caption.
    async with sem:
        try:
            txt, _, _ = await chat(
                VISION_MODEL,
                _CAP_SYS,
                f"Figure from: {title}",
                0.2,
                300,
                extra_body=_NO_THINK,
                images=[png],
            )
        except Exception:  # noqa: BLE001
            return None
        return " ".join(txt.split()).strip() or None


async def figures_for(
    items: list[tuple[str, str]], out_dir: Path, top_n: int = 10
) -> dict[str, dict[str, object]]:
    """Crop+caption the first figure of up to top_n papers. id -> {page, file, caption}."""
    fig_dir = out_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    crops: list[tuple[str, str, int, bytes]] = []
    for aid, title in items[:top_n]:
        got = first_figure(aid)
        if got is None:
            continue
        page, png = got[0], got[1]
        crops.append((aid, title, page, png))
    if not crops:
        return {}
    await ensure_loaded(
        VISION_MODEL
    )  # warm once so concurrent callers skip the cold swap
    sem = asyncio.Semaphore(CONCURRENCY)
    captions = await asyncio.gather(*[_caption_one(sem, c[1], c[3]) for c in crops])
    out: dict[str, dict[str, object]] = {}
    for c, cap in zip(crops, captions):
        if not cap:
            continue
        aid, page, png = c[0], c[2], c[3]
        fname = f"{aid.replace('/', '_')}_p{page}.png"
        _ = (fig_dir / fname).write_bytes(png)
        out[aid] = {"page": page, "file": f"figures/{fname}", "caption": cap}
    return out
