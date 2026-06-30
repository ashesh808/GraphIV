"""Judge validity: known-fact accuracy + degradation detection + position/verbosity bias."""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from random import Random
from typing import Any, LiteralString, cast

import psycopg

_HERE = Path(__file__).resolve()
_EXP = _HERE.parents[1]
_REPO = _HERE.parents[4]
sys.path.insert(0, str(_REPO / "experiments"))

from _harness._boot import JUDGE_MODEL  # noqa: E402
from _harness._llm import chat as jchat  # noqa: E402
from _harness._llm import parse_json  # noqa: E402
from _harness.digest import adjacency_digest  # noqa: E402
from _harness.judge import _pair_once, judge_pairwise  # noqa: E402
from _harness.retrieval import retrieve_subgraph  # noqa: E402
from _harness.topics import TOPICS  # noqa: E402
from _harness.viz import bar_chart  # noqa: E402

from llm import NO_THINK, chat_sync  # noqa: E402
from pipeline import _free_router_vram  # noqa: E402
from retrieve import embed_query, free_model  # noqa: E402
from store import Store  # noqa: E402

CACHE = _EXP / "cache"
RESULTS = _EXP / "results"
PG_DSN = f"host={_REPO}/.pg port=5433 dbname=arxivkg"
TODAY = datetime.now().strftime("%Y-%m-%d")
NARRATOR = "Gemma-4-26B-Code"
BASE_TOPICS = ["diffusion", "testtime", "transformer"]

CLAIMS: list[tuple[str, str, bool, str]] = [
    (
        "2006.11239",
        "introduces denoising diffusion probabilistic models for image generation",
        True,
        "true",
    ),
    (
        "1312.6114",
        "introduces the variational autoencoder using the reparameterization trick",
        True,
        "true",
    ),
    (
        "1706.03762",
        "introduces the Transformer, a sequence model based entirely on attention",
        True,
        "true",
    ),
    (
        "1810.04805",
        "introduces BERT, deep bidirectional transformer pre-training for language",
        True,
        "true",
    ),
    (
        "1512.03385",
        "introduces deep residual learning with skip (shortcut) connections",
        True,
        "true",
    ),
    (
        "2112.10752",
        "performs high-resolution image synthesis via diffusion in a latent space",
        True,
        "true",
    ),
    (
        "1412.6980",
        "introduces Adam, a first-order gradient-based stochastic optimization method",
        True,
        "true",
    ),
    (
        "2103.00020",
        "learns transferable visual representations from natural-language supervision",
        True,
        "true",
    ),
    (
        "2005.14165",
        "shows large language models are few-shot learners via in-context learning",
        True,
        "true",
    ),
    (
        "1505.04597",
        "introduces U-Net, a convolutional encoder-decoder for biomedical segmentation",
        True,
        "true",
    ),
    (
        "1406.2661",
        "introduces generative adversarial networks (a generator vs a discriminator)",
        True,
        "true",
    ),
    (
        "2010.11929",
        "applies a pure transformer to image patches for image classification",
        True,
        "true",
    ),
    (
        "2006.11239",
        "introduces the Transformer architecture based on self-attention",
        False,
        "false_topic",
    ),
    (
        "1312.6114",
        "introduces deep residual learning to train very deep networks",
        False,
        "false_topic",
    ),
    (
        "1706.03762",
        "is a denoising diffusion probabilistic model for image generation",
        False,
        "false_topic",
    ),
    ("1810.04805", "introduces the Adam optimization algorithm", False, "false_topic"),
    (
        "1512.03385",
        "learns image representations from natural-language supervision (CLIP)",
        False,
        "false_topic",
    ),
    (
        "2103.00020",
        "is a U-Net encoder-decoder for biomedical image segmentation",
        False,
        "false_topic",
    ),
    ("2005.14165", "introduces generative adversarial networks", False, "false_topic"),
    (
        "1406.2661",
        "demonstrates few-shot in-context learning in large language models",
        False,
        "false_topic",
    ),
    (
        "2006.11239",
        "achieves image generation using a generative adversarial (GAN) objective",
        False,
        "false_subtle",
    ),
    (
        "1706.03762",
        "relies on recurrent (RNN) connections to model long-range dependencies",
        False,
        "false_subtle",
    ),
    (
        "1810.04805",
        "is trained with a left-to-right autoregressive language-modeling objective",
        False,
        "false_subtle",
    ),
    (
        "1512.03385",
        "uses self-attention as its core building block",
        False,
        "false_subtle",
    ),
]

_FACT_SYS = (
    "You verify whether a research paper supports a factual CLAIM about it, using ONLY its title and "
    "abstract. Be strict: if the claim misattributes the paper's contribution or contradicts the "
    'abstract, answer "no". Output ONLY JSON: {"supports":"yes|partial|no"}.'
)
_COMPOSE_SYS = (
    "Write a thorough chronological literature review answering the question, grounded ONLY in the "
    "provided GRAPH (papers + typed citation edges). Origins -> advances -> frontier; cite every "
    "claim as arXiv:<id>; never invent. Use headers."
)
_ARXIV = re.compile(r"arXiv:\s?[\w./-]+", re.IGNORECASE)
_YEAR = re.compile(r"\b(19[89]\d|20[0-3]\d)\b")
_FILLER = [
    "It is worth noting that this represents a meaningful development in the broader landscape.",
    "This contribution reflects the evolving priorities of the field.",
    "Such advances underscore the cumulative nature of research progress.",
    "These considerations situate the work within a wider trajectory of inquiry.",
]


def _meta(ids: list[str]) -> dict[str, tuple[str, str]]:
    with psycopg.connect(PG_DSN) as conn:
        rows: list[tuple[Any, ...]] = conn.execute(
            cast(
                LiteralString,
                "SELECT arxiv_id, title, abstract FROM paper_meta WHERE arxiv_id = ANY(%s)",
            ),
            (ids,),
        ).fetchall()
    return {str(a): (str(t or ""), str(ab or "")) for a, t, ab in rows}


def _fact_check(title: str, abstract: str, claim: str) -> str:
    obj = parse_json(
        jchat(
            JUDGE_MODEL,
            _FACT_SYS,
            f"PAPER TITLE: {title}\nABSTRACT: {abstract[:2500]}\n\nCLAIM: {claim}",
            temperature=0.0,
            max_tokens=60,
        )
    )
    return str(obj.get("supports", "")).strip().lower() if isinstance(obj, dict) else ""


def facts_test() -> dict[str, Any]:
    meta = _meta(sorted({c[0] for c in CLAIMS}))
    rows: list[dict[str, Any]] = []
    for aid, claim, is_true, kind in CLAIMS:
        if aid not in meta:
            continue
        sup = _fact_check(meta[aid][0], meta[aid][1], claim)
        score = (
            (1.0 if sup == "yes" else 0.5 if sup == "partial" else 0.0)
            if is_true
            else (1.0 if sup == "no" else 0.5 if sup == "partial" else 0.0)
        )
        rows.append(
            {
                "aid": aid,
                "kind": kind,
                "is_true": is_true,
                "supports": sup,
                "correct": score,
            }
        )

    def acc(sub: list[dict[str, Any]]) -> float:
        return round(sum(r["correct"] for r in sub) / len(sub), 3) if sub else 0.0

    return {
        "rows": rows,
        "overall": acc(rows),
        "true": acc([r for r in rows if r["is_true"]]),
        "false_topic": acc([r for r in rows if r["kind"] == "false_topic"]),
        "false_subtle": acc([r for r in rows if r["kind"] == "false_subtle"]),
    }


def _paras(t: str) -> list[str]:
    return [p for p in t.split("\n\n") if p.strip()]


def _truncate(t: str, frac: float) -> str:
    return "\n\n".join(_paras(t)[: max(1, round(len(_paras(t)) * frac))])


def _shuffle(t: str) -> str:
    ps = _paras(t)
    body = ps[1:]
    Random(0).shuffle(body)
    return "\n\n".join(ps[:1] + body)


def _corrupt_chrono(t: str) -> str:
    years = sorted({int(y) for y in _YEAR.findall(t)})
    if len(years) < 3:
        return t
    rev = {y: years[len(years) - 1 - i] for i, y in enumerate(years)}
    return _YEAR.sub(lambda m: str(rev[int(m.group(0))]), t)


def _pad(t: str) -> str:
    out: list[str] = []
    for i, p in enumerate(_paras(t)):
        out += [p, _FILLER[i % len(_FILLER)]]
    return "\n\n".join(out)


VARIANTS: dict[str, Any] = {
    "identical": lambda t: t,
    "truncated_75": lambda t: _truncate(t, 0.75),
    "truncated_50": lambda t: _truncate(t, 0.50),
    "truncated_25": lambda t: _truncate(t, 0.25),
    "citations_stripped": lambda t: _ARXIV.sub("[ref]", t),
    "shuffled": _shuffle,
    "chronology_corrupted": _corrupt_chrono,
    "verbose_pad": _pad,
}
_AXIS = {
    "identical": "sanity/position",
    "truncated_75": "coverage",
    "truncated_50": "coverage",
    "truncated_25": "coverage",
    "citations_stripped": "grounding",
    "shuffled": "lineage (reorder)",
    "chronology_corrupted": "lineage (year-flip)",
    "verbose_pad": "verbosity",
}


def _base_reviews(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    todo = [
        t
        for t in BASE_TOPICS
        if not conn.execute("SELECT 1 FROM base WHERE topic=?", (t,)).fetchone()
    ]
    if todo:
        _free_router_vram()
        digs: dict[str, str] = {}
        for t in todo:
            qv = embed_query(TOPICS[t].query, mode="asym")
            store = Store(PG_DSN, emb_space="asym")
            try:
                sg = retrieve_subgraph(store, qv, TOPICS[t].query)
                absd = store.abstracts([lm.arxiv_id for lm in sg.landmarks])
            finally:
                store.close()
            digs[t] = adjacency_digest(sg.landmarks, sg.edges, absd)
        free_model()
        for t in todo:
            rep, _, _ = chat_sync(
                NARRATOR,
                _COMPOSE_SYS,
                f"Question: {TOPICS[t].query}\n\nGRAPH:\n{digs[t]}",
                0.0,
                3500,
                extra_body=NO_THINK,
            )
            _ = conn.execute("INSERT INTO base VALUES (?,?)", (t, rep))
            conn.commit()
    for t in BASE_TOPICS:
        row: tuple[str] | None = conn.execute(
            "SELECT report FROM base WHERE topic=?", (t,)
        ).fetchone()
        if row:
            out.append((t, row[0]))
    return out


def degrade_test(conn: sqlite3.Connection) -> dict[str, Any]:
    bases = _base_reviews(conn)
    res: dict[str, dict[str, int]] = {
        v: {"full": 0, "tie": 0, "variant": 0} for v in VARIANTS
    }
    pos_bias = pos_total = 0
    for topic, full in bases:
        q = f"(Today is {TODAY}.) {TOPICS[topic].query}"
        canon = list(TOPICS[topic].canonical)
        for vname, fn in VARIANTS.items():
            v = fn(full)
            o = judge_pairwise(q, full, v, canon)["overall"]
            res[vname]["full" if o == "A" else "variant" if o == "B" else "tie"] += 1
            if vname == "identical":
                pos_total += 2
                pos_bias += (_pair_once(q, full, v, canon)["overall"] != "tie") + (
                    _pair_once(q, v, full, canon)["overall"] != "tie"
                )
    return {"res": res, "n": len(bases), "pos_bias": pos_bias, "pos_total": pos_total}


def _figure(facts: dict[str, Any], deg: dict[str, Any]) -> None:
    n = deg["n"]
    r = deg["res"]
    rows = [
        {
            "metric": "facts_acc",
            "v": facts["overall"],
        },
        {"metric": "coverage", "v": r["truncated_50"]["full"] / n},
        {"metric": "grounding", "v": r["citations_stripped"]["full"] / n},
        {"metric": "lineage", "v": r["chronology_corrupted"]["full"] / n},
        {
            "metric": "no_position_bias",
            "v": 1 - (deg["pos_bias"] / max(1, deg["pos_total"])),
        },
        {"metric": "no_verbosity_bias", "v": 1 - (r["verbose_pad"]["variant"] / n)},
    ]
    bar_chart(
        rows,
        "metric",
        [("v", "judge validity (1 = pass)")],
        RESULTS / "validity.png",
        title="Judge validity — Gemma-4 (facts accuracy + degradation detection + bias-free)",
    )


def _tables(facts: dict[str, Any], deg: dict[str, Any]) -> None:
    n = deg["n"]
    md = [
        f"**Known-fact accuracy: {facts['overall']}** "
        f"(true {facts['true']}, false-topic {facts['false_topic']}, false-subtle {facts['false_subtle']}; "
        f"n={len(facts['rows'])}).",
        "",
        "| degradation | full wins | tie | variant wins | axis |",
        "|---|--:|--:|--:|---|",
    ]
    for v in VARIANTS:
        r = deg["res"][v]
        md.append(
            f"| {v} | {r['full']}/{n} | {r['tie']}/{n} | {r['variant']}/{n} | {_AXIS[v]} |"
        )
    md += [
        "",
        f"- position bias (non-tie on identical): {deg['pos_bias']}/{deg['pos_total']} "
        f"({'CLEAN' if deg['pos_bias'] == 0 else 'PRESENT'})",
        f"- verbosity bias (verbose_pad wins): {deg['res']['verbose_pad']['variant']}/{n} "
        f"({'none' if deg['res']['verbose_pad']['variant'] == 0 else 'PRESENT'})",
    ]
    _ = (RESULTS / "metrics.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    macros = [
        f"\\newcommand{{\\FactAcc}}{{{facts['overall']}}}",
        f"\\newcommand{{\\CovDetect}}{{{deg['res']['truncated_50']['full']}/{n}}}",
        f"\\newcommand{{\\GndDetect}}{{{deg['res']['citations_stripped']['full']}/{n}}}",
        f"\\newcommand{{\\LinDetect}}{{{deg['res']['chronology_corrupted']['full']}/{n}}}",
    ]
    _ = (RESULTS / "macros.tex").write_text("\n".join(macros) + "\n", encoding="utf-8")
    tab = [
        "\\begin{tabular}{lrrr}",
        "\\toprule",
        "degradation & full & tie & variant \\\\",
        "\\midrule",
    ]
    for v in VARIANTS:
        r = deg["res"][v]
        tab.append(
            f"{v.replace('_', '-')} & {r['full']} & {r['tie']} & {r['variant']} \\\\"
        )
    tab += ["\\bottomrule", "\\end{tabular}"]
    _ = (RESULTS / "table.tex").write_text("\n".join(tab) + "\n", encoding="utf-8")


def _cache() -> sqlite3.Connection:
    CACHE.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(CACHE / "base.db")
    _ = conn.execute(
        "CREATE TABLE IF NOT EXISTS base (topic TEXT PRIMARY KEY, report TEXT)"
    )
    conn.commit()
    return conn


def run() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    conn = _cache()
    facts = facts_test()
    print(f"[validity] facts accuracy {facts['overall']}", flush=True)
    deg = degrade_test(conn)
    conn.close()
    _figure(facts, deg)
    _tables(facts, deg)
    _ = (RESULTS / "metrics.json").write_text(
        json.dumps(
            {"facts": {k: v for k, v in facts.items() if k != "rows"}, "degrade": deg},
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"[validity] done; pos_bias {deg['pos_bias']}/{deg['pos_total']}", flush=True)
