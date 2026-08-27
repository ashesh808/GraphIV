"""
Paired per-survey comparison on the held-out half, for the shortlist chosen on dev

Bootstrap over surveys because the arms share a pool and their errors are not independent
Reports gold papers gained, not a rate, so the size of a win is legible
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from statistics import mean
from typing import Any

from sweep import all_arms, load

HERE = Path(__file__).parent
THR = 3
SHORT = [
    "agen_relw0.35_ley0_nores",
    "agen_relw0.35_ley4_nores",
    "agen_relw0.35_ley16_nores",
    "agen_only_nores",
    "agen_relw0.35_ley8_nores",
    "agen_relw0.35_ley8",
    "agen_relw0.45_ley8",
    "agen_relw0.35",
    "agen_only",
    "rrf_pf_ley8",
    "ley_front_q8",
    "frontier",
    "trajectory",
    "ppr",
    "indegree",
    "ORACLE",
]


def boot(d: list[int], n: int = 20000, seed: int = 0) -> tuple[float, float]:
    """
    Percentile bootstrap interval on the mean paired difference
    """
    rng = random.Random(seed)
    means = sorted(mean(rng.choices(d, k=len(d))) for _ in range(n))
    return means[int(0.025 * n)], means[int(0.975 * n)]


def main() -> None:
    """
    Print the held-out table and every shortlisted arm's paired delta against two baselines
    """
    cs = load()
    per: dict[str, dict[str, list[int]]] = {}
    ceil = {"dev": 0, "test": 0}
    for c in cs:
        sp = str(c["meta"].get("split", "dev"))
        gold = {k for k, v in c["qrels"].items() if v >= THR}
        ceil[sp] += len(gold & set(c["pool"]))
        for name, ids in all_arms(c).items():
            per.setdefault(name, {"dev": [], "test": []})[sp].append(len(ids & gold))
    out: dict[str, Any] = {"ceiling": ceil, "per_survey": per}  # pyright: ignore[reportExplicitAny]
    _ = (HERE / "data" / "final_per_survey.json").write_text(json.dumps(out))

    print(f"HELD-OUT TEST, 30 surveys, {ceil['test']} in-pool gold papers\n")
    print(f"{'selector':<26} {'found':>6} {'of':>5} {'share':>7}")
    for n in sorted(SHORT, key=lambda x: -sum(per[x]["test"])):
        t = sum(per[n]["test"])
        print(f"{n:<26} {t:>6} {ceil['test']:>5} {t / ceil['test']:>7.3f}")

    for base in ("frontier", "trajectory"):
        print(f"\npaired against {base} on TEST, papers gained per survey\n")
        print(
            f"{'selector':<26} {'total':>6} {'mean':>7} {'95% lo':>8} {'95% hi':>8} {'W/T/L':>10}"
        )
        for n in sorted(SHORT, key=lambda x: -sum(per[x]["test"])):
            if n in (base, "ORACLE"):
                continue
            d = [a - b for a, b in zip(per[n]["test"], per[base]["test"], strict=True)]
            lo, hi = boot(d)
            w = sum(1 for x in d if x > 0)
            t_ = sum(1 for x in d if x == 0)
            print(
                f"{n:<26} {sum(d):>+6} {mean(d):>+7.2f} {lo:>+8.2f} {hi:>+8.2f} "
                f"{f'{w}/{t_}/{len(d) - w - t_}':>10}"
            )


if __name__ == "__main__":
    main()
