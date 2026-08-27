"""Build pasa_mapped.jsonl once the gated PaSa dataset is reachable.

Needs an HF token with CarlanLark/pasa-dataset accepted; run `hf auth login` first.
Gold papers are arXiv ids by construction, so the only question this answers is which of them our corpus holds.
"""

import json
import subprocess
from pathlib import Path
from typing import Any

EXT = Path(__file__).resolve().parent
PG = ["psql", "-h", "/home/kuroma/Documents/projects/nlp/arxivkg/.pg", "-p", "5433", "-d", "arxivkg", "-t", "-A"]
SPLITS = {
    "autoscholarquery_test": "AutoScholarQuery/test.jsonl",
    "realscholarquery_test": "RealScholarQuery/test.jsonl",
}


def download() -> None:
    """Pull the two test splits into raw/pasa/."""
    from huggingface_hub import hf_hub_download

    for name, path in SPLITS.items():
        got = hf_hub_download("CarlanLark/pasa-dataset", path, repo_type="dataset")
        dst = EXT / "raw" / "pasa" / f"data_{path.replace('/', '_')}"
        _ = dst.write_bytes(Path(got).read_bytes())
        print(f"{name}: {dst}")


def in_corpus(ids: list[str]) -> set[str]:
    """Return the subset of arxiv ids that paper_meta holds."""
    if not ids:
        return set()
    arr = ",".join("'" + i.replace("'", "''") + "'" for i in sorted(set(ids)))
    sql = f"SELECT arxiv_id FROM paper_meta WHERE arxiv_id = ANY(ARRAY[{arr}]);"
    out = subprocess.run([*PG, "-c", sql], capture_output=True, text=True, check=True)
    return {line.strip() for line in out.stdout.splitlines() if line.strip()}


def gold_ids(rec: dict[str, Any]) -> list[str]:  # pyright: ignore[reportExplicitAny]
    """Read the gold arXiv ids out of whichever field the split uses."""
    for key in ("answer_arxiv_id", "arxiv_id", "answer_ids"):
        if key in rec:
            v = rec[key]
            return [str(x).split("v")[0] for x in (v if isinstance(v, list) else [v])]
    raise KeyError(f"no gold id field in {sorted(rec)}")


def main() -> None:
    download()
    rows: list[dict[str, Any]] = []  # pyright: ignore[reportExplicitAny]
    for name, path in SPLITS.items():
        src = EXT / "raw" / "pasa" / f"data_{path.replace('/', '_')}"
        recs = [json.loads(line) for line in src.read_text().splitlines() if line.strip()]
        every = [i for r in recs for i in gold_ids(r)]
        present = in_corpus(every)
        for r in recs:
            g = gold_ids(r)
            rows.append(
                {
                    "query": r.get("question") or r.get("query"),
                    "gold_arxiv_ids": [i for i in g if i in present],
                    "n_gold_original": len(g),
                    "n_gold_mapped": len([i for i in g if i in present]),
                    "split": name,
                    "query_date": (r.get("source_meta") or {}).get("published_time") or r.get("query_date"),
                }
            )
        hit = sum(1 for i in every if i in present)
        print(f"{name}: {len(recs)} queries, {hit}/{len(every)} gold papers in our corpus")
    with (EXT / "pasa_mapped.jsonl").open("w") as f:
        for row in rows:
            _ = f.write(json.dumps(row) + "\n")
    print(f"wrote {EXT / 'pasa_mapped.jsonl'} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
