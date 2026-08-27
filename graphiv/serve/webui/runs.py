"""
Reading the run directory: the card list, the cached question, cache purging

A run's facts come from run.json alone, so listing the index costs no extra file reads.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from graphiv.core.settings import DATA_DIR

_GRADE_DB = DATA_DIR / "metadata" / "grade_cache.db"
_CRIT_DB = DATA_DIR / "metadata" / "critique_cache.db"


def _scan_runs(out: Path) -> list[dict[str, Any]]:  # pyright: ignore[reportExplicitAny]
    runs: list[dict[str, Any]] = []  # pyright: ignore[reportExplicitAny]
    if not out.is_dir():
        return runs
    for slug_dir in sorted(out.iterdir()):
        if not slug_dir.is_dir():
            continue
        for cfg_dir in sorted(slug_dir.iterdir()):
            if not cfg_dir.is_dir():
                continue
            rj, pj = cfg_dir / "run.json", cfg_dir / "progress.json"
            if not rj.exists() and not pj.exists():
                continue
            entry: dict[str, Any] = {  # pyright: ignore[reportExplicitAny]
                "slug": slug_dir.name,
                "config": cfg_dir.name,
                "question": "",
                "status": "stale",
                "started_at": "",
                "total_seconds": None,
                "stages": {},
                "judge": {},
                "n_landmarks": None,
                "grounded": None,
                "has": {
                    k: (cfg_dir / f).exists()
                    for k, f in (
                        ("report", "report.md"),
                        ("pdf", "report.pdf"),
                        ("graph", "graph.html"),
                        ("papers", "papers.json"),
                        ("tex", "report.tex"),
                    )
                },
            }
            if rj.exists():
                try:
                    meta = json.loads(rj.read_text())  # pyright: ignore[reportAny]
                    entry["status"] = "done"
                    entry["question"] = str(meta.get("question", ""))  # pyright: ignore[reportAny]
                    entry["judge"] = meta.get("judge_scores_final") or {}
                    entry["n_landmarks"] = meta.get("n_landmarks")
                    entry["grounded"] = len(meta.get("grounded") or [])
                    entry["effort"] = meta.get("effort")
                    entry["preset"] = meta.get("preset", "")
                    entry["rounds"] = meta.get("rounds_run")
                    entry["n_figures"] = meta.get("n_figures")
                    roles: dict[str, int] = {}
                    years: list[int] = []
                    for lm in meta.get("landmarks") or []:  # pyright: ignore[reportAny]
                        role = str(lm.get("role") or "ungraded")  # pyright: ignore[reportAny]
                        roles[role] = roles.get(role, 0) + 1
                        y = lm.get("year")  # pyright: ignore[reportAny]
                        if isinstance(y, int):
                            years.append(y)
                    entry["roles"] = roles
                    entry["years"] = [min(years), max(years)] if years else None
                    tm = meta.get("timings") or {}  # pyright: ignore[reportAny]
                    if isinstance(tm, dict):
                        entry["started_at"] = str(
                            tm.get("started_at", "")
                        )  # pyright: ignore[reportAny]
                        entry["total_seconds"] = tm.get("total_seconds")
                        entry["stages"] = tm.get("stages") or {}
                except Exception:  # noqa: BLE001
                    pass
            elif pj.exists():
                try:
                    prog = json.loads(pj.read_text())  # pyright: ignore[reportAny]
                    entry["question"] = str(prog.get("question", ""))  # pyright: ignore[reportAny]
                    entry["started_at"] = str(
                        prog.get("started_at", "")
                    )  # pyright: ignore[reportAny]
                    entry["total_seconds"] = prog.get("elapsed")
                    stages: dict[str, float] = {}
                    cur = None
                    for s in prog.get("stages") or []:  # pyright: ignore[reportAny]
                        name = str(s.get("name"))  # pyright: ignore[reportAny]
                        sec = s.get("seconds")  # pyright: ignore[reportAny]
                        if isinstance(sec, (int, float)):
                            stages[name] = stages.get(name, 0.0) + float(sec)
                        else:
                            cur = name
                    entry["stages"] = stages
                    entry["current_stage"] = cur
                    import time as _t  # noqa: PLC0415

                    fresh = (_t.time() - pj.stat().st_mtime) < 900
                    entry["status"] = "running" if (not prog.get("done") and fresh) else "stale"
                except Exception:  # noqa: BLE001
                    pass
            runs.append(entry)
    runs.sort(key=lambda r: str(r.get("started_at") or ""), reverse=True)
    return runs


def _purge_caches(question: str) -> dict[str, int]:
    """
    Delete this question's grade + critique cache rows (extract/summary stay: shared)
    """
    qhash = hashlib.sha1(question.encode()).hexdigest()[:12]
    out: dict[str, int] = {}
    for name, db, table in (
        ("grades", _GRADE_DB, "grade"),
        ("critiques", _CRIT_DB, "critique"),
    ):
        n = 0
        if db.exists():
            conn = sqlite3.connect(db)
            try:
                cur = conn.execute(f"DELETE FROM {table} WHERE qhash=?", (qhash,))  # noqa: S608
                n = cur.rowcount
                conn.commit()
            except sqlite3.OperationalError:
                pass
            conn.close()
        out[name] = n
    return out


_DATA_RE = re.compile(r"const DATA = (\{.*\});")


def _run_question(d: Path) -> str:
    for f in ("run.json", "progress.json"):
        p = d / f
        if p.exists():
            try:
                return str(
                    json.loads(p.read_text()).get("question", "")
                )  # pyright: ignore[reportAny]
            except Exception:  # noqa: BLE001
                pass
    return ""
