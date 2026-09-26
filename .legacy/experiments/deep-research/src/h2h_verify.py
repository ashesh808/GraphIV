"""
Head-to-head citation verifier: objective recency/grounding counts for ANY report

Extracts arXiv ids (arXiv:ID inline or arxiv.org/abs|pdf/ID links, commercial deep-research outputs cite by link), verifies each against the corpus, and double-checks non-corpus ids against arxiv.org live (rate-limited) so papers newer than our corpus delta are counted as real, not fabricated.
Reports: total unique ids, verified, fabricated, >=2025, 2026.
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve()
_REPO = _HERE.parents[3]
_ID = r"[a-z][a-z.\-]+/\d{7}|\d{4}\.\d{4,5}"
_PATTERNS = (
    re.compile(rf"arXiv:\s?({_ID})", re.IGNORECASE),
    re.compile(rf"arxiv\.org/(?:abs|pdf|html)/({_ID})(?:v\d+)?", re.IGNORECASE),
)


def extract_ids(text: str) -> list[str]:
    found: set[str] = set()
    for pat in _PATTERNS:
        found.update(m.group(1).lower() for m in pat.finditer(text))
    return sorted(found)


def _year(aid: str) -> int | None:
    from graphiv.core.settings import arxiv_year

    return arxiv_year(aid)


def _live_exists(aid: str) -> bool:
    req = urllib.request.Request(
        f"https://arxiv.org/abs/{aid}",
        method="HEAD",
        headers={"User-Agent": "GraphIV-verify"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return bool(resp.status == 200)
    except Exception:  # noqa: BLE001
        return False


def verify(path: Path) -> dict[str, Any]:
    """
    Citation counts for one report file (corpus check + live fallback for misses)
    """
    from graphiv.generate.narrate import verify_ids_exist

    ids = extract_ids(path.read_text(encoding="utf-8", errors="ignore"))
    in_corpus = {i.lower() for i in verify_ids_exist(ids)}
    missing = [i for i in ids if i not in in_corpus]
    live_ok: set[str] = set()
    for aid in missing:  # papers newer than the corpus delta are real, not fabricated
        if _live_exists(aid):
            live_ok.add(aid)
        time.sleep(3.0)
    verified = [i for i in ids if i in in_corpus or i in live_ok]
    fabricated = [i for i in ids if i not in in_corpus and i not in live_ok]
    years = {i: _year(i) for i in verified}
    return {
        "file": str(path),
        "total_ids": len(ids),
        "verified": len(verified),
        "in_corpus": len(in_corpus),
        "live_only": sorted(live_ok),
        "fabricated": fabricated,
        "ge_2025": sum(1 for y in years.values() if y is not None and y >= 2025),
        "n_2026": sum(1 for y in years.values() if y == 2026),
    }


def main() -> None:
    rows = [verify(Path(a)) for a in sys.argv[1:]]
    for r in rows:
        print(json.dumps(r, indent=1))
    if len(rows) > 1:
        cols = ("file", "total_ids", "verified", "fabricated", "ge_2025", "n_2026")
        print("\n| " + " | ".join(cols) + " |")
        print("| " + " | ".join("---" for _ in cols) + " |")
        for r in rows:
            vals = [
                Path(str(r["file"])).parent.name[:40],
                r["total_ids"],
                r["verified"],
                len(r["fabricated"]),  # pyright: ignore[reportArgumentType]
                r["ge_2025"],
                r["n_2026"],
            ]
            print("| " + " | ".join(str(v) for v in vals) + " |")


if __name__ == "__main__":
    main()
