"""
The Preprocessor: wiring only, one method per graph-building stage

Heavy modules are imported inside the method that needs them, so construction stays cheap
The stage modules keep their own argv contract, which preserves their tested behavior exactly
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from graphiv.core.config import Config


@dataclass
class Preprocessor:
    """
    metadata + files -> labels + KG

    Methods map 1:1 onto the old phase stages; each is idempotent and resume-safe.
    """

    cfg: Config

    @classmethod
    def from_config(cls, cfg: Config | None = None) -> Preprocessor:
        """
        Build from config.toml (loaded fresh when omitted)
        """
        return cls(cfg=cfg or Config.load())

    def _run_main(self, module_main: object, argv: list[str]) -> None:
        """
        Drive an argparse main() with an explicit argv (restores sys.argv)
        """
        old = sys.argv
        sys.argv = [old[0], *argv]
        try:
            module_main()  # pyright: ignore[reportCallIssue]
        finally:
            sys.argv = old

    def parse(
        self,
        workers: int = 10,
        checkpoint_every: int = 100000,
        limit: int | None = None,
        no_write: bool = False,
    ) -> None:
        """
        HTML -> matched citations -> Postgres `citation` (resume-safe)
        """
        from graphiv.preprocess.parse.visualize import main

        argv = ["--workers", str(workers), "--checkpoint-every", str(checkpoint_every)]
        if limit:
            argv += ["--limit", str(limit)]
        if no_write:
            argv += ["--no-write"]
        self._run_main(main, argv)

    def label_sample(self, target: int = 100000) -> None:
        """
        Stratified citation sample -> sample.txt
        """
        from graphiv.preprocess.label.corpus_sample import main

        self._run_main(main, ["--target", str(target)])

    def label_sample_rare(self) -> None:
        """
        Oversample the rare intent classes into the existing sample
        """
        from graphiv.preprocess.label.sample_rare import main

        self._run_main(main, [])

    def label_refine(
        self,
        generations: int = 6,
        source: str = "gold",
        stratified: int = 300,
        rare: int = 0,
        seed: int = 0,
        batch_size: int = 25,
        parallelism: int = 4,
        holdout: float = 0.4,
    ) -> None:
        """
        Evolve the teacher policy against the labeled set -> prompts/ + the accuracy curve
        """
        from graphiv.preprocess.label.refine import run

        _ = run(
            generations=generations,
            source=source,
            n_stratified=stratified,
            n_rare=rare,
            seed=seed,
            batch_size=batch_size,
            parallelism=parallelism,
            holdout=holdout,
        )

    def label_gold(self) -> None:
        """
        Load the human labeling queue into gold_label, hand labels first
        """
        from graphiv.preprocess.label.gold_ingest import main

        self._run_main(main, [])

    def label_teacher(
        self,
        parallelism: int = 4,
        batch_size: int = 50,
        teacher_model: str = "",
        teacher_prompt: str = "",
        labels_db: str = "",
        model_tag: str = "",
    ) -> None:
        """
        Teacher pseudo-labeling -> a SQLite store (idempotent)
        """
        from graphiv.preprocess.label.teacher import main

        argv = ["--parallelism", str(parallelism), "--batch-size", str(batch_size)]
        for flag, value in (
            ("--model", teacher_model),
            ("--prompt", teacher_prompt),
            ("--labels-db", labels_db),
            ("--model-tag", model_tag),
        ):
            if value:
                argv += [flag, value]
        self._run_main(main, argv)

    def train_student(
        self,
        epochs: int = 4,
        batch_size: int = 64,
        suffix: str = "v1",
        labels_db: str = "",
        dataset_cache: str = "",
        oversample_power: float = 0.0,
        class_weights: bool = True,
    ) -> None:
        """
        DistilBERT student training on the teacher labels
        """
        from graphiv.preprocess.intent.train import main

        argv = [
            "--epochs",
            str(epochs),
            "--batch-size",
            str(batch_size),
            "--out-suffix",
            suffix,
            "--oversample-power",
            str(oversample_power),
        ]
        for flag, value in (("--labels-db", labels_db), ("--dataset-cache", dataset_cache)):
            if value:
                argv += [flag, value]
        if not class_weights:
            argv.append("--no-class-weights")
        self._run_main(main, argv)

    def infer_student(self, batch_size: int = 512, suffix: str = "v1") -> None:
        """
        Corpus-wide intent inference (resumable via WHERE intent IS NULL)
        """
        from graphiv.preprocess.intent.infer import main

        self._run_main(main, ["--suffix", suffix, "--batch-size", str(batch_size)])

    def relabel_edges(
        self,
        suffix: str = "v4",
        table: str = "citation_intent_v2",
        batch_size: int = 512,
        chunk: int = 200_000,
    ) -> None:
        """
        Label every resolved edge into a side table, leaving citation.intent alone
        """
        from graphiv.preprocess.intent.relabel import main

        self._run_main(
            main,
            [
                "--suffix",
                suffix,
                "--table",
                table,
                "--batch-size",
                str(batch_size),
                "--chunk",
                str(chunk),
            ],
        )

    def consolidate(self, stage: str = "all", force: bool = False) -> None:
        """
        Migrate or refresh the single Postgres store (paper, citation, meta, emb, topic)
        """
        from graphiv.preprocess.consolidate import main

        argv = ["--stage", stage]
        if force:
            argv.append("--force")
        self._run_main(main, argv)

    def embed_corpus(self) -> None:
        """
        Embed papers missing a vector, in both spaces, asym first

        An empty table makes this the from-zero corpus builder rather than a delta pass.
        """
        from graphiv.preprocess import embed_corpus

        embed_corpus.run()

    def build_topic_tree(
        self,
        min_leaf: int = 250,
        coherence: float = 0.14,
        target_leaf: int = 600,
        max_depth: int = 8,
        max_k: int = 12,
    ) -> None:
        """
        Density-aware topic tree over the UMAP-50 vectors

        This always builds, so skipping an existing tree is the caller's decision.
        """
        from graphiv.preprocess.topics import TreeParams, run_build

        run_build(
            TreeParams(
                min_leaf=min_leaf,
                coherence=coherence,
                target_leaf=target_leaf,
                max_depth=max_depth,
                max_k=max_k,
            )
        )

    def build_summaries(self, sample: int = 12, limit: int | None = None) -> None:
        """
        Per-leaf LLM community summaries (resumable)
        """
        from graphiv.preprocess.community_summary import run_summaries

        run_summaries(sample_per_leaf=sample, limit=limit)
