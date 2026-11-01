"""
Score every embedded paper for how much it looks like a literature review

The checkpoint and its recipe live in [survey] MODEL_PATH, which is also what trained them
The probability is stored rather than a verdict, so the threshold is chosen when the table is read
"""

from __future__ import annotations

import argparse
import tomllib
from pathlib import Path

import psycopg
import torch
from torch import nn
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from src.core.config import load_config
from src.core.paths import OFFLINE_CONFIG


class SurveyLabeler:
    """
    The trained classifier and the stage 3 queue it drains
    """

    def __init__(self, batch: int, model_dir: Path) -> None:
        """
        Args:
            batch: papers per forward pass.
            model_dir: the directory holding model.pt and hyperparam.toml.
        """
        recipe = tomllib.loads((model_dir / "hyperparam.toml").read_text(encoding="utf-8"))
        self.base = str(recipe["model"]["NAME"])
        self.max_len = int(recipe["model"]["MAX_LEN"])
        self.batch = batch
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.tok = AutoTokenizer.from_pretrained(self.base)
        model: nn.Module = AutoModelForSequenceClassification.from_pretrained(
            self.base, num_labels=2
        )
        _ = model.load_state_dict(torch.load(model_dir / "model.pt", map_location="cpu"))
        self.model = model.to(self.device)
        _ = self.model.eval()

    def score(self, docs: list[str]) -> list[float]:
        """
        Run the classifier over one chunk of papers

        Args:
            docs: the title and abstract of each paper, already joined.

        Returns:
            One probability per paper, in order.
        """
        out: list[float] = []
        with torch.no_grad():
            for i in range(0, len(docs), self.batch):
                enc = self.tok(
                    docs[i : i + self.batch],
                    truncation=True,
                    max_length=self.max_len,
                    padding=True,
                    return_tensors="pt",
                )
                half = torch.bfloat16  # pyright: ignore[reportPrivateImportUsage]
                with torch.autocast("cuda", dtype=half, enabled=self.device == "cuda"):
                    logits = self.model(
                        input_ids=enc["input_ids"].to(self.device),
                        attention_mask=enc["attention_mask"].to(self.device),
                    ).logits
                prob = nn.functional.softmax(logits.float(), dim=-1)[:, 1]
                out.extend(prob.cpu().tolist())
        return out

    def label(self, pg_dest: str, chunk: int) -> int:
        """
        Drain the queue, writing the score and advancing the stage in the same statement

        Args:
            pg_dest: libpq connection string.
            chunk: papers per commit.

        Returns:
            How many papers were scored.
        """
        done, likely = 0, 0
        with psycopg.connect(pg_dest, autocommit=True) as conn:
            row = conn.execute(
                "SELECT count(*) FROM papers WHERE stage >= 3 AND survey_probability IS NULL"
            ).fetchone()
            total = int(row[0]) if row else 0
            print(f"[stage4] {total:,} papers to score", flush=True)
            # autocommit ends the transaction at once, so the staging table is made once and reused
            _ = conn.execute("CREATE TEMP TABLE r (arxiv_id text, v real)")
            while True:
                rows: list[tuple[str, str | None, str | None]] = conn.execute(
                    "SELECT arxiv_id, title, abstract FROM papers"
                    " WHERE stage >= 3 AND survey_probability IS NULL LIMIT %s",
                    (chunk,),
                ).fetchall()
                if not rows:
                    break
                scores = self.score([f"{t or ''}\n\n{a or ''}" for _, t, a in rows])
                with conn.cursor().copy("COPY r (arxiv_id, v) FROM STDIN") as cp:
                    for (arxiv_id, _t, _a), value in zip(rows, scores, strict=True):
                        cp.write_row((arxiv_id, value))
                _ = conn.execute(
                    "UPDATE papers p SET survey_probability = r.v, stage = 4"
                    " FROM r WHERE p.arxiv_id = r.arxiv_id"
                )
                _ = conn.execute("TRUNCATE r")
                done += len(rows)
                likely += sum(1 for v in scores if v >= 0.5)
                print(f"[stage4] {done:,}/{total:,} scored, {likely:,} over 0.5", flush=True)
        return done


def main() -> None:
    """
    Read the config, then score every paper that has no score
    """
    ap = argparse.ArgumentParser()
    _ = ap.add_argument("--config_path", default=str(OFFLINE_CONFIG))
    args = ap.parse_args()

    cfg = load_config(str(args.config_path))
    sv = cfg["survey"]
    labeler = SurveyLabeler(batch=int(sv["BATCH"]), model_dir=Path(str(sv["MODEL_PATH"])))
    _ = labeler.label(str(cfg["database"]["PG_DEST"]), chunk=int(sv["CHUNK"]))


if __name__ == "__main__":
    main()
