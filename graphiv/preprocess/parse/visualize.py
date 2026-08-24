"""
Benchmark the citation resolver over a random sample and plot the result

Output PNGs and the raw JSON summary land in the citation stats directory
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import cast

import matplotlib  # pyright: ignore[reportMissingImports]

matplotlib.use("Agg")
import matplotlib.font_manager as fm  # pyright: ignore[reportMissingImports]
import matplotlib.pyplot as plt  # pyright: ignore[reportMissingImports]

from ._common import HTML_DIR  # pyright: ignore[reportUnusedImport]  # noqa: F401

_FONT_CONFIGURED: bool = False


def _configure_font() -> None:
    global _FONT_CONFIGURED
    if _FONT_CONFIGURED:
        return
    for path in [
        Path.home() / ".local/share/fonts/GoogleSansFlex-VariableFont.ttf",
        Path.home() / ".local/share/fonts/onlyoffice/GoogleSansFlex-VariableFont.ttf",
    ]:
        if path.exists():
            try:
                fm.fontManager.addfont(str(path))
                plt.rcParams["font.family"] = "Google Sans Flex"
                _FONT_CONFIGURED = True
                return
            except Exception as e:  # noqa: BLE001
                print(f"font load failed: {e}")
    _FONT_CONFIGURED = True  # don't retry


# apply at module import so any caller of plot_* gets the right font
_configure_font()


def _arxiv_id_from_filename(fp: Path) -> str:
    stem = fp.stem
    if "/" in stem or "." in stem:
        return stem
    m = re.match(r"([a-z\-]+)(\d{7})", stem)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    return stem


def _era_bucket(year: int | None) -> str:
    if year is None:
        return "unknown"
    if year < 2000:
        return "1900s"
    base = (year // 2) * 2
    return f"{base}-{base+1}"


def _all_files_sequential(limit: int | None = None) -> list[Path]:
    """
    All HTML files in (YYMM, filename) order, sequential disk reads
    """
    pool: list[Path] = []
    for m in sorted(HTML_DIR.iterdir()):
        if not m.is_dir():
            continue
        try:
            pool.extend(sorted(m.glob("*.html")))
        except OSError:
            continue
        if limit is not None and len(pool) >= limit:
            return pool[:limit]
    return pool if limit is None else pool[:limit]


def _resolved_count(c: Counter[str]) -> int:
    return sum(v for m, v in c.items() if not m.startswith(("none", "rejected")))


def plot_per_category(
    cat_counter: dict[str, Counter[str]],
    papers_per_cat: Counter[str],
    citations_per_cat: Counter[str],
    n_papers: int,
    n_cits: int,
    n_resolved: int,
    out_path: Path,
) -> None:
    """
    Resolution rate per arXiv category, as a horizontal bar chart
    """
    cats = sorted(cat_counter.keys(), key=lambda c: citations_per_cat[c], reverse=True)
    cats = [c for c in cats if citations_per_cat[c] >= 100]
    rates = [100 * _resolved_count(cat_counter[c]) / citations_per_cat[c] for c in cats]
    labels = [f"{c}  ({citations_per_cat[c]:,} cits, {papers_per_cat[c]} papers)" for c in cats]

    fig, ax = plt.subplots(figsize=(11, max(4, 0.32 * len(cats))))
    y = range(len(cats))
    bars = ax.barh(y, rates, color="#3b78e7")
    ax.set_yticks(list(y), labels=labels, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel("citation resolution rate (%)")
    ax.set_title(
        f"Citation resolution rate per top-level arXiv category "
        f"({n_papers:,} papers, {n_cits:,} citations)"
    )
    global_rate = 100 * n_resolved / max(n_cits, 1)
    ax.axvline(
        global_rate,
        color="#d62728",
        linestyle="--",
        linewidth=1,
        label=f"global = {global_rate:.1f}%",
    )
    ax.legend(loc="lower right", fontsize=8)
    for bar, rate in zip(bars, rates, strict=False):
        ax.text(
            rate + 0.5,
            bar.get_y() + bar.get_height() / 2,
            f"{rate:.0f}%",
            va="center",
            fontsize=8,
        )
    ax.set_xlim(0, max(max(rates, default=0) + 8, 100))
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def plot_per_era(era_counter: dict[str, Counter[str]], out_path: Path) -> None:
    """
    Resolution rate per publication era
    """

    def era_sort_key(e: str) -> tuple[int, str]:
        if e == "1900s":
            return (1900, e)
        if e == "unknown":
            return (3000, e)
        return (int(e.split("-", 1)[0]), e)

    eras = sorted([e for e in era_counter if e != "unknown"], key=era_sort_key)
    totals = [sum(era_counter[e].values()) for e in eras]
    rates = [100 * _resolved_count(era_counter[e]) / max(totals[i], 1) for i, e in enumerate(eras)]

    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.plot(eras, rates, marker="o", color="#3b78e7", linewidth=2)
    for i, (_, y_, n) in enumerate(zip(eras, rates, totals, strict=False)):
        # categorical x-axis: era i sits at position i
        ax.annotate(
            f"n={n}",
            (i, y_),
            textcoords="offset points",
            xytext=(0, 8),
            ha="center",
            fontsize=7,
            color="#555",
        )
    ax.set_ylabel("resolution rate (%)")
    ax.set_xlabel("citing-paper era (submission year)")
    ax.set_title("Citation resolution rate by era of the citing paper")
    ax.set_ylim(0, 100)
    ax.grid(True, linestyle=":", linewidth=0.6, alpha=0.6)
    fig.autofmt_xdate(rotation=45)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


METHOD_ORDER: list[str] = [
    "link",
    "text",
    "doi",
    "jref",
    "title-exact",
    "title-exact-noyr",
    "title-fuzzy",
    "rejected-overlap",
    "rejected-year",
    "rejected-author",
    "none",
]
METHOD_COLORS: dict[str, str] = {
    "link": "#1b9e77",
    "text": "#1b9e77",
    "doi": "#2cb88e",
    "jref": "#3fc9a5",
    "title-exact": "#3b78e7",
    "title-exact-noyr": "#6f9be9",
    "title-fuzzy": "#a4bcef",
    "rejected-overlap": "#f4a261",
    "rejected-year": "#e9c46a",
    "rejected-author": "#e76f51",
    "none": "#bbbbbb",
}


def plot_method_mix(
    cat_counter: dict[str, Counter[str]],
    citations_per_cat: Counter[str],
    out_path: Path,
) -> None:
    """
    Which ladder tier resolved each category, as stacked shares
    """
    cats = sorted(cat_counter.keys(), key=lambda c: citations_per_cat[c], reverse=True)
    cats = [c for c in cats if citations_per_cat[c] >= 100]

    fig, ax = plt.subplots(figsize=(12, max(4, 0.4 * len(cats))))
    bottoms = [0.0] * len(cats)
    for m in METHOD_ORDER:
        vals = [100 * cat_counter[c].get(m, 0) / max(citations_per_cat[c], 1) for c in cats]
        ax.barh(
            cats,
            vals,
            left=bottoms,
            color=METHOD_COLORS[m],
            label=m,
            edgecolor="white",
            linewidth=0.3,
        )
        bottoms = [b + v for b, v in zip(bottoms, vals, strict=False)]
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("share of citations (%)")
    ax.set_title("Resolution method mix per category")
    ax.legend(loc="lower right", bbox_to_anchor=(1.0, 1.02), ncol=6, fontsize=7, frameon=False)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140, bbox_inches="tight")
    plt.close(fig)


def plot_all(
    cat_counter: dict[str, Counter[str]],
    era_counter: dict[str, Counter[str]],
    global_counter: Counter[str],
    papers_per_cat: Counter[str],
    citations_per_cat: Counter[str],
    n_papers: int,
    out_dir: Path,
) -> None:
    """
    Write every benchmark figure into the output directory
    """
    n_cits = sum(global_counter.values())
    n_resolved = _resolved_count(global_counter)
    plot_per_category(
        cat_counter,
        papers_per_cat,
        citations_per_cat,
        n_papers,
        n_cits,
        n_resolved,
        out_dir / "per_category.png",
    )
    plot_per_era(era_counter, out_dir / "per_era.png")
    plot_method_mix(cat_counter, citations_per_cat, out_dir / "method_mix.png")


# parallel driver

import json  # noqa: E402
import multiprocessing as mp  # noqa: E402
import time  # noqa: E402
from collections import defaultdict  # noqa: E402

from . import db  # noqa: E402
from ._common import DB_PATH, STATS_DIR  # noqa: E402
from .matcher import Index, extract_citations, year_from_arxiv_id  # noqa: E402

_WORKER_INDEX: Index | None = None
_WORKER_PID_OF: dict[str, int] | None = None
_WORKER_FUZZY: int = 88
_WORKER_OVERLAP: int = 4


def _worker_init(
    index: Index,
    pid_of: dict[str, int],
    fuzzy: int,
    overlap: int,
) -> None:
    global _WORKER_INDEX, _WORKER_PID_OF, _WORKER_FUZZY, _WORKER_OVERLAP
    _WORKER_INDEX = index
    _WORKER_PID_OF = pid_of
    _WORKER_FUZZY = fuzzy
    _WORKER_OVERLAP = overlap


def _resolve_one(path_str: str) -> tuple[
    str,
    str,
    str,  # citing_arxiv_id, category_top, era
    list[
        tuple[
            int,
            int,
            str,
            int | None,
            str,
            float | None,
            str | None,
            str | None,
            str | None,
            str | None,
            list[str] | None,
        ]
    ],
    Counter[str],  # per-paper method counts
]:
    assert _WORKER_INDEX is not None and _WORKER_PID_OF is not None
    fp = Path(path_str)
    citing_arxiv = _arxiv_id_from_filename(fp)
    cat = _WORKER_INDEX.categories.get(citing_arxiv, "unknown")
    cat_top = cat.split(".", 1)[0]
    era = _era_bucket(year_from_arxiv_id(citing_arxiv))
    counts: Counter[str] = Counter()
    rows: list[
        tuple[
            int,
            int,
            str,
            int | None,
            str,
            float | None,
            str | None,
            str | None,
            str | None,
            str | None,
            list[str] | None,
        ]
    ] = []
    citing_id = _WORKER_PID_OF.get(citing_arxiv)
    if citing_id is None:
        return citing_arxiv, cat_top, era, rows, counts
    try:
        _bibs, occurs = extract_citations(fp, _WORKER_INDEX, _WORKER_FUZZY, _WORKER_OVERLAP)
    except (FileNotFoundError, OSError):
        # silently skip: file missing or unreadable (ZFS / vault transient)
        return citing_arxiv, cat_top, era, rows, counts
    except Exception as e:  # noqa: BLE001
        counts[f"error:{type(e).__name__}"] += 1
        return citing_arxiv, cat_top, era, rows, counts
    for o in occurs:
        cited_pid = _WORKER_PID_OF.get(o.cited_arxiv_id) if o.cited_arxiv_id else None
        counts[o.method] += 1
        rows.append(
            (
                citing_id,
                o.ordinal,
                o.bib_local_id,
                cited_pid,
                o.method,
                o.score,
                o.section,
                o.sentence,
                o.paragraph,
                o.raw_bib_text,
                o.co_cited_bibs or None,
            )
        )
    return citing_arxiv, cat_top, era, rows, counts


def main() -> None:
    """
    Parse the benchmark arguments, sample papers and plot
    """
    import argparse

    parser = argparse.ArgumentParser(description="phase_3 citation pipeline")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,  # pyright: ignore[reportUnusedCallResult]
        help="cap on papers to process (default: all)",
    )
    parser.add_argument(
        "--workers", type=int, default=10
    )  # pyright: ignore[reportUnusedCallResult]
    parser.add_argument(
        "--chunksize", type=int, default=8
    )  # pyright: ignore[reportUnusedCallResult]
    parser.add_argument(
        "--out-dir", type=Path, default=STATS_DIR
    )  # pyright: ignore[reportUnusedCallResult]
    parser.add_argument(
        "--checkpoint-every",
        type=int,
        default=100_000,  # pyright: ignore[reportUnusedCallResult]
        help="regenerate viz + summary every N processed papers",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",  # pyright: ignore[reportUnusedCallResult]
        help="skip COPY to Postgres (figures still emitted)",
    )
    args = parser.parse_args()
    limit: int | None = args.limit  # pyright: ignore[reportAny]
    workers: int = args.workers  # pyright: ignore[reportAny]
    chunksize: int = args.chunksize  # pyright: ignore[reportAny]
    out_dir: Path = args.out_dir  # pyright: ignore[reportAny]
    checkpoint_every: int = args.checkpoint_every  # pyright: ignore[reportAny]
    no_write: bool = args.no_write  # pyright: ignore[reportAny]
    out_dir.mkdir(parents=True, exist_ok=True)

    _configure_font()

    print("loading index from sqlite ...", flush=True)
    t0 = time.time()
    index = Index.load(DB_PATH, verbose=True)
    print(f"index loaded in {time.time()-t0:.1f}s\n", flush=True)

    pid_of: dict[str, int] = {}
    done_citing: set[int] = set()
    if not no_write:
        print("connecting to postgres + ensuring schema ...", flush=True)
        conn = db.connect()
        db.ensure_schema(conn)
        t1 = time.time()
        all_aids = sorted(
            index.categories.keys()
            | index.authors.keys()
            | {r.arxiv_id for rs in index.by_norm_title.values() for r in rs}
        )
        pid_of = db.populate_paper_table(conn, all_aids)
        print(f"  paper table: {len(pid_of):,} ids in {time.time()-t1:.1f}s", flush=True)
        # resume: skip citing papers that already have any rows
        t2 = time.time()
        rows = cast(
            "list[tuple[int]]",
            conn.execute("SELECT DISTINCT citing_id FROM citation").fetchall(),
        )
        done_citing = {r[0] for r in rows}
        print(
            f"  resume: {len(done_citing):,} papers already in citation "
            f"({time.time()-t2:.1f}s)\n",
            flush=True,
        )
        conn.close()

    print(
        f"scanning HTML_DIR sequentially{' (limit '+str(limit)+')' if limit else ''} ...",
        flush=True,
    )
    all_files = _all_files_sequential(limit=limit)
    if done_citing:
        before = len(all_files)
        all_files = [
            fp for fp in all_files if pid_of.get(_arxiv_id_from_filename(fp), -1) not in done_citing
        ]
        print(
            f"  skipping {before-len(all_files):,} already-done papers; "
            f"{len(all_files):,} remain",
            flush=True,
        )
    print(f"running on {workers} workers (sequential file order) ...\n", flush=True)

    cat_counter: dict[str, Counter[str]] = defaultdict(Counter)
    era_counter: dict[str, Counter[str]] = defaultdict(Counter)
    global_counter: Counter[str] = Counter()
    papers_per_cat: Counter[str] = Counter()
    citations_per_cat: Counter[str] = Counter()

    paths = [str(fp) for fp in all_files]
    ctx = mp.get_context("fork")

    n_rows_written = 0
    wall0 = time.time()

    write_conn = None if no_write else db.connect()
    pending_rows: list[
        tuple[
            int,
            int,
            str,
            int | None,
            str,
            float | None,
            str | None,
            str | None,
            str | None,
            str | None,
            list[str] | None,
        ]
    ] = []
    flush_every = 50_000

    def _snapshot_viz(done: int) -> None:
        plot_all(
            cat_counter,
            era_counter,
            global_counter,
            papers_per_cat,
            citations_per_cat,
            done,
            out_dir,
        )
        n_c = sum(global_counter.values())
        n_r = _resolved_count(global_counter)
        snap = {
            "n_papers_processed": done,
            "n_citations": n_c,
            "n_resolved": n_r,
            "n_rows_written": n_rows_written,
            "elapsed_s": time.time() - wall0,
            "workers": workers,
            "global": dict(global_counter),
            "by_category": {k: dict(v) for k, v in cat_counter.items()},
            "by_era": {k: dict(v) for k, v in era_counter.items()},
            "papers_per_category": dict(papers_per_cat),
        }
        _ = (out_dir / "summary.json").write_text(json.dumps(snap, indent=2))
        print(
            f"  -> snapshot at {done:,} papers "
            f"({n_r:,}/{n_c:,} resolved, {100*n_r/max(n_c,1):.1f}%)",
            flush=True,
        )

    with ctx.Pool(
        processes=workers,
        initializer=_worker_init,
        initargs=(index, pid_of, 88, 4),
    ) as pool:
        done = 0
        last_ckpt = 0
        for _citing_arxiv, cat_top, era, rows_out, counts in pool.imap_unordered(
            _resolve_one,
            paths,
            chunksize=chunksize,
        ):
            papers_per_cat[cat_top] += 1
            for m, c in counts.items():
                cat_counter[cat_top][m] += c
                era_counter[era][m] += c
                global_counter[m] += c
                citations_per_cat[cat_top] += c
            if write_conn is not None and rows_out:
                pending_rows.extend(rows_out)
                if len(pending_rows) >= flush_every:
                    n_rows_written += db.copy_citations(write_conn, pending_rows)
                    write_conn.commit()
                    pending_rows.clear()
            done += 1
            if done % 1000 == 0:
                print(
                    f"  {done}/{len(paths)}  " f"({done/(time.time()-wall0):.1f} papers/s)",
                    flush=True,
                )
            if done - last_ckpt >= checkpoint_every:
                if write_conn is not None and pending_rows:
                    n_rows_written += db.copy_citations(write_conn, pending_rows)
                    write_conn.commit()
                    pending_rows.clear()
                _snapshot_viz(done)
                last_ckpt = done

    if write_conn is not None and pending_rows:
        n_rows_written += db.copy_citations(write_conn, pending_rows)
        write_conn.commit()
    if write_conn is not None:
        print("creating indexes ...", flush=True)
        db.ensure_indexes(write_conn)
        write_conn.close()

    wall = time.time() - wall0
    n_cits = sum(global_counter.values())
    n_resolved = _resolved_count(global_counter)
    print(
        f"\n=== {len(paths):,} papers, {n_cits:,} citations in {wall:.1f}s "
        f"({len(paths)/max(wall,1e-9):.1f} papers/s, {n_cits/max(wall,1e-9):.0f} cits/s) ==="
    )
    if not no_write:
        print(f"wrote {n_rows_written:,} citation rows to postgres")
    print(f"\nGLOBAL: {n_resolved:,}/{n_cits:,} resolved " f"({100*n_resolved/max(n_cits,1):.1f}%)")
    for m, c in global_counter.most_common():
        print(f"  {m:22s}  {c:7d}  ({100*c/max(n_cits,1):.1f}%)")
    _snapshot_viz(len(paths))
    print(f"\nwrote: {out_dir}/per_category.png  per_era.png  method_mix.png  summary.json")
