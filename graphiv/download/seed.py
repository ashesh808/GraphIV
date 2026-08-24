"""
Kaggle seed download: fetch the metadata zip, extract the JSONL, replace atomically

The endpoint rejects HEAD, so the remote size comes from a one-byte ranged GET
That size is the idempotency marker, which makes an unchanged snapshot a no-op
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
import zipfile
from urllib.request import Request, urlopen

from graphiv.download._common import ARXIV_JSON, SEED_STATE


def remote_zip_size(url: str) -> int | None:
    """
    Total zip size via a 1-byte Range GET (endpoint has no HEAD support)
    """
    req = Request(url, headers={"Range": "bytes=0-0"})
    try:
        with urlopen(req, timeout=60) as resp:
            content_range: str = resp.headers.get("Content-Range", "")
    except OSError as e:
        print(f"[seed] remote size probe failed: {e}")
        return None
    return int(content_range.rsplit("/", 1)[1]) if "/" in content_range else None


def _state() -> dict[str, object]:
    """
    Parsed seed_state.json, or {} on first run
    """
    if SEED_STATE.exists():
        data: dict[str, object] = json.loads(SEED_STATE.read_text())
        return data
    return {}


def up_to_date(url: str) -> tuple[bool, int | None]:
    """
    (skip, remote_size), skipping when arxiv.json exists and the remote size matches state
    """
    size = remote_zip_size(url)
    fresh = ARXIV_JSON.exists() and size is not None and _state().get("zip_size") == size
    return fresh, size


def run(url: str, force: bool = False, keep_zip: bool = False) -> None:
    """
    Refresh data/arxiv.json from the Kaggle snapshot (idempotent by zip size)

    Args:
        url: Kaggle dataset download URL.
        force: re-download even when the snapshot is unchanged.
        keep_zip: keep the downloaded zip next to arxiv.json.
    """
    skip, size = up_to_date(url)
    if skip and not force:
        print(f"[seed] snapshot unchanged (zip {size:,} B) — nothing to do")
        return

    zip_path = ARXIV_JSON.with_suffix(".zip")
    print(f"[seed] downloading {url} -> {zip_path} ({size or '?'} B, resumable)")
    _ = subprocess.run(
        ["curl", "-fsSL", "--retry", "3", "-C", "-", "-o", str(zip_path), url],
        check=True,
    )

    with zipfile.ZipFile(zip_path) as z:
        member = next(n for n in z.namelist() if n.endswith(".json"))
        tmp = ARXIV_JSON.with_name(ARXIV_JSON.name + ".new")
        print(f"[seed] extracting {member} -> {tmp}")
        with z.open(member) as src, open(tmp, "wb") as dst:
            shutil.copyfileobj(src, dst, 1 << 20)
    _ = tmp.replace(ARXIV_JSON)

    SEED_STATE.parent.mkdir(parents=True, exist_ok=True)
    _ = SEED_STATE.write_text(
        json.dumps(
            {
                "zip_size": size or zip_path.stat().st_size,
                "member": member,
                "json_size": ARXIV_JSON.stat().st_size,
                "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            },
            indent=2,
        )
    )
    if not keep_zip:
        zip_path.unlink()
    print(f"[seed] done: {ARXIV_JSON} ({ARXIV_JSON.stat().st_size:,} B)")
