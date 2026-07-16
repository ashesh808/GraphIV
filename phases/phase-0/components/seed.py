"""Kaggle seed download: fetch the arxiv metadata zip, extract the JSONL, atomic-replace.

The Kaggle download endpoint rejects HEAD but serves unauthenticated ranged GETs, so the
remote snapshot size comes from a 1-byte Range request's Content-Range total. That size is
recorded in seed_state.json and doubles as the idempotency marker: same remote size + an
existing arxiv.json = snapshot unchanged, skip (override with --include-force).
"""

import json
import shutil
import subprocess
import time
import zipfile
from urllib.request import Request, urlopen

from _common import ARXIV_JSON, SEED_STATE


def remote_zip_size(url: str) -> int | None:
    """Total zip size via a 1-byte Range GET (endpoint has no HEAD support)."""
    req = Request(url, headers={"Range": "bytes=0-0"})
    try:
        with urlopen(req, timeout=60) as resp:
            content_range: str = resp.headers.get("Content-Range", "")
    except OSError as e:
        print(f"[phase-0] remote size probe failed: {e}")
        return None
    return int(content_range.rsplit("/", 1)[1]) if "/" in content_range else None


def _state() -> dict[str, object]:
    if SEED_STATE.exists():
        data: dict[str, object] = json.loads(SEED_STATE.read_text())
        return data
    return {}


def up_to_date(url: str) -> tuple[bool, int | None]:
    """(skip, remote_size): skip when arxiv.json exists and the remote zip size matches state."""
    size = remote_zip_size(url)
    fresh = (
        ARXIV_JSON.exists() and size is not None and _state().get("zip_size") == size
    )
    return fresh, size


def run(url: str, force: bool, keep_zip: bool) -> None:
    skip, size = up_to_date(url)
    if skip and not force:
        print(f"[phase-0] snapshot unchanged (zip {size:,} B) — nothing to do")
        return

    zip_path = ARXIV_JSON.with_suffix(".zip")
    print(f"[phase-0] downloading {url} -> {zip_path} ({size or '?'} B, resumable)")
    _ = subprocess.run(
        ["curl", "-fsSL", "--retry", "3", "-C", "-", "-o", str(zip_path), url],
        check=True,
    )

    with zipfile.ZipFile(zip_path) as z:
        member = next(n for n in z.namelist() if n.endswith(".json"))
        tmp = ARXIV_JSON.with_name(ARXIV_JSON.name + ".new")
        print(f"[phase-0] extracting {member} -> {tmp}")
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
    print(f"[phase-0] done: {ARXIV_JSON} ({ARXIV_JSON.stat().st_size:,} B)")
