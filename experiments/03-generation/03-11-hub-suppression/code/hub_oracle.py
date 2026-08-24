"""
The topic-conditioned judge that decides whether a paper is specific or generic

It is independent of the sweep, which is what makes it usable as ground truth
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from _harness._boot import JUDGE_MODEL  # noqa: E402
from _harness._llm import chat, parse_json  # noqa: E402
from _harness.topics import TOPICS  # noqa: E402

from graphiv.core.settings import PG_DSN
from graphiv.core.store import Store

_HERE = Path(__file__).resolve()
_EXP = _HERE.parents[1]
_REPO = _HERE.parents[4]

RESULTS = _EXP / "results"
CACHE = _EXP / "cache"
ARMS = ("none", "lift", "pr_ratio", "pop_bg3", "pop_bg5", "pop_bg7", "pop_bg10")

_SYS = (
    "You curate a FOCUSED literature review on a specific TOPIC. For one PAPER decide its role:\n"
    "- specific: its method/result is genuinely about THIS topic; a focused review should discuss it.\n"
    "- generic: it appears mainly because it is universally cited across ML — a general-purpose "
    "architecture/optimizer/benchmark/foundation (e.g. an optimizer, a backbone, a base LM) that is "
    "NOT specific to this topic and would be boilerplate in this review.\n"
    "Judge relative to THIS topic only: a paper can be specific to its own field yet generic here. "
    'Output ONLY JSON: {"label":"specific"|"generic"}.'
)


def _judge(q: str, title: str, abstract: str) -> str:
    obj = parse_json(
        chat(
            JUDGE_MODEL,
            _SYS,
            f"TOPIC: {q}\n\nPAPER\ntitle: {title}\nabstract: {abstract[:2500] or '(n/a)'}",
            temperature=0.0,
            max_tokens=20,
        )
    )
    lab = str(obj.get("label", "")).strip().lower() if isinstance(obj, dict) else ""
    return lab if lab in ("specific", "generic") else "specific"


def main() -> None:
    data: dict[str, Any] = json.loads((RESULTS / "structural.json").read_text())
    sets: dict[str, dict[str, list[str]]] = data["sets"]
    meta: dict[str, dict[str, Any]] = data["meta"]
    CACHE.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(CACHE / "oracle.db")
    _ = conn.execute(
        "CREATE TABLE IF NOT EXISTS lab (topic TEXT, arxiv_id TEXT, label TEXT, PRIMARY KEY(topic, arxiv_id))"
    )
    conn.commit()

    store = Store(PG_DSN, emb_space="asym")
    labels: dict[tuple[str, str], str] = {}
    done = 0
    for k in sorted(meta):
        ids = list(meta[k])
        abs_d = store.abstracts(ids)
        for aid in ids:
            row: tuple[str] | None = conn.execute(
                "SELECT label FROM lab WHERE topic=? AND arxiv_id=?", (k, aid)
            ).fetchone()
            if row is None:
                lab = _judge(TOPICS[k].query, meta[k][aid]["title"], abs_d.get(aid, ""))
                _ = conn.execute("INSERT OR REPLACE INTO lab VALUES (?,?,?)", (k, aid, lab))
                conn.commit()
                done += 1
                if done % 50 == 0:
                    print(f"[oracle] judged {done}", flush=True)
            else:
                lab = row[0]
            labels[(k, aid)] = lab
    store.close()
    conn.close()

    rows: list[dict[str, Any]] = []
    for arm in ARMS:
        gfracs: list[float] = []
        srets: list[float] = []
        for k in sets:
            sel = sets[k][arm]
            specific_pool = [a for a in meta[k] if labels.get((k, a)) == "specific"]
            gfracs.append(
                sum(1 for a in sel if labels.get((k, a)) == "generic") / len(sel) if sel else 0.0
            )
            if specific_pool:
                srets.append(len(set(sel) & set(specific_pool)) / len(specific_pool))
        rows.append(
            {
                "arm": arm,
                "generic_frac": round(sum(gfracs) / len(gfracs), 3),
                "specific_retained": (round(sum(srets) / len(srets), 3) if srets else 0.0),
            }
        )
    cols = ["arm", "generic_frac", "specific_retained"]
    md = ["| " + " | ".join(cols) + " |", "| " + " | ".join("---" for _ in cols) + " |"]
    for r in rows:
        md.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    _ = (RESULTS / "oracle.md").write_text("\n".join(md) + "\n")
    _ = (RESULTS / "oracle.json").write_text(json.dumps(rows, indent=1))
    print("\n" + "\n".join(md), flush=True)


if __name__ == "__main__":
    main()
