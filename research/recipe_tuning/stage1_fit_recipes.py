"""
Fits each tuned recipe on its benchmark's train split, then writes the exponents to its toml

The log of the score is linear in the exponents, so a smooth recall@k is fit by gradient
CMA-ES then searches the exact recall from there, and val picks it, the fit or the shipped point
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import optuna
import torch
from driver import get_release
from stage0_cache_terms import TERMS, cache_path

from src.core.config import load_config
from src.core.paths import OFFLINE_CONFIG
from src.retrieve.recipe import read_recipe

# each tuned recipe, the benchmark it is fit on and the cutoff its headline recall is read at
TARGETS = {
    "survey": ("SurveyMatch", 1000),
    "frontier": ("FrontierMatch", 1000),
    "consensus": ("ConsensusMatch", 100),
}
# the seed-paper recipes, each a tuned point with one direction of the walk set to zero
ZEROED = {
    "ancestry": ("survey", ("fro", "fro2", "fro_decay")),
    "evolution": ("frontier", ("anc", "anc2", "anc_decay")),
}
# val holds 13 ConsensusMatch cases, too few to choose on alone
POOLED = {"consensus"}
EPOCHS = 80
CHUNK = 128
TRIALS = 200
SEED = 0
FIXED = TERMS.index("cos")

Case = tuple[torch.Tensor, torch.Tensor, int]


def load_cases(path: Path, device: str) -> list[Case]:
    """
    One cached split as per-case features, answer masks and answer sizes

    Every term becomes log(1 + term), with the hub's sign flipped since it divides the score.

    Args:
        path: The npz stage 0 wrote.
        device: Where the tensors live.

    Returns:
        (features, answer mask, answer size) per case.
    """
    data = np.load(path)
    features = data["terms"]
    # in place, so the raw terms and their logs never sit in memory together
    _ = np.log1p(features, out=features)
    features[:, TERMS.index("hub")] *= -1
    offsets = data["offsets"]
    out: list[Case] = []
    for i, n_key in enumerate(data["n_key"]):
        lo, hi = int(offsets[i]), int(offsets[i + 1])
        x = torch.from_numpy(features[lo:hi]).to(device)
        y = torch.from_numpy(data["hits"][lo:hi]).to(device)
        out.append((x, y, int(n_key)))
    return out


def recall_at(cases: list[Case], exponents: torch.Tensor, k: int) -> float:
    """
    The exact mean recall@k of a set of exponents, ties broken toward the answer

    Args:
        cases: The cached cases.
        exponents: One exponent per term.
        k: The cutoff.

    Returns:
        The mean over cases.
    """
    total = 0.0
    with torch.no_grad():
        for x, y, n_key in cases:
            score = x @ exponents
            top = score >= torch.topk(score, min(k, len(score))).values[-1]
            total += float((top & y).sum()) / n_key
    return total / len(cases)


def to_exponents(free: torch.Tensor) -> torch.Tensor:
    """
    The full exponent vector, cos pinned at 1 and every other term kept non-negative

    Args:
        free: One unconstrained value per term other than cos.

    Returns:
        One exponent per term.
    """
    rest = torch.nn.functional.softplus(free)
    return torch.cat([rest[:FIXED], torch.ones(1, device=free.device), rest[FIXED:]])


def from_exponents(exponents: torch.Tensor) -> torch.Tensor:
    """
    The unconstrained values that give these exponents, after scaling cos to 1

    Args:
        exponents: One exponent per term, cos above zero.

    Returns:
        One value per term other than cos.
    """
    scaled = (exponents / exponents[FIXED]).clamp(min=1e-3)
    rest = torch.cat([scaled[:FIXED], scaled[FIXED + 1 :]])
    return torch.log(torch.expm1(rest))


def fit(cases: list[Case], start: torch.Tensor, k: int) -> torch.Tensor:
    """
    Gradient ascent on a smooth recall@k, from a starting point

    A paper counts by a sigmoid of how far its score sits above the case's k-th score, and the
    sigmoid sharpens over the epochs so the end point is judged on nearly the real recall.

    Args:
        cases: The cached train cases.
        start: The exponents to start from.
        k: The cutoff.

    Returns:
        The fitted exponents.
    """
    free = from_exponents(start).clone().requires_grad_(True)
    optimizer = torch.optim.Adam([free], lr=0.05)
    for epoch in range(EPOCHS):
        sharpness = 0.3 * (0.05 / 0.3) ** (epoch / (EPOCHS - 1))
        optimizer.zero_grad()
        # the gradient is accumulated a chunk at a time, so only one chunk's graph is ever held
        for lo in range(0, len(cases), CHUNK):
            exponents = to_exponents(free)
            loss = torch.zeros((), device=free.device)
            for x, y, n_key in cases[lo : lo + CHUNK]:
                score = x @ exponents
                # the cut and scale move with the exponents, so inflating every score gains nothing
                spread = score.std() + 1e-6
                edge = torch.topk(score, min(k, len(score))).values[-1]
                hit = torch.sigmoid((score[y] - edge) / (sharpness * spread))
                loss = loss - hit.sum() / n_key
            (loss / len(cases)).backward()
        optimizer.step()
    return to_exponents(free).detach()


def search(cases: list[Case], start: torch.Tensor, k: int) -> torch.Tensor:
    """
    CMA-ES on the exact recall@k, started at a point, as the check on the smooth fit

    Args:
        cases: The cached train cases.
        start: The exponents to start from.
        k: The cutoff.

    Returns:
        The best exponents it found.
    """
    names = [t for t in TERMS if t != "cos"]
    origin = {t: float(v) for t, v in zip(TERMS, start / start[FIXED], strict=True) if t != "cos"}

    def exponents_of(params: dict[str, float]) -> torch.Tensor:
        values = [1.0 if t == "cos" else max(params[t], 0.0) for t in TERMS]
        return torch.tensor(values, dtype=torch.float32, device=start.device)

    def objective(trial: optuna.Trial) -> float:
        params = {t: trial.suggest_float(t, -1.0, 10.0) for t in names}
        return recall_at(cases, exponents_of(params), k)

    sampler = optuna.samplers.CmaEsSampler(x0=origin, sigma0=0.5, seed=SEED)
    study = optuna.create_study(direction="maximize", sampler=sampler)
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study.optimize(objective, n_trials=TRIALS)
    return exponents_of(study.best_params)


def shipped(recipe_path: Path, device: str) -> torch.Tensor:
    """
    A recipe's current exponents as a vector

    Args:
        recipe_path: The recipe file.
        device: Where the tensor lives.

    Returns:
        One exponent per term.
    """
    weights = read_recipe(recipe_path)["component"][-1]["weights"]
    return torch.tensor([float(weights[t.upper()]) for t in TERMS], device=device)


def write_weights(path: Path, exponents: dict[str, float], provenance: str) -> None:
    """
    Rewrites a recipe's weights block and its provenance line, leaving everything else as it was

    Args:
        path: The recipe file.
        exponents: One exponent per term.
        provenance: What the first comment line says after the recipe's own description.
    """
    text = path.read_text(encoding="utf-8")
    for term, value in exponents.items():
        number = f"{round(value, 3):g}"
        text = re.sub(rf"^{term.upper()} = .*$", f"{term.upper()} = {number}", text, flags=re.M)
    first, rest = text.split("\n", 1)
    head = first.split(", tuned on")[0].split(", untuned")[0]
    path.write_text(f"{head}, {provenance}\n{rest}", encoding="utf-8")


def main() -> None:
    """
    Fits, searches and picks each tuned recipe, then writes it and the two zeroed recipes
    """
    ap = argparse.ArgumentParser()
    _ = ap.add_argument("--config_path", default=str(OFFLINE_CONFIG))
    _ = ap.add_argument("--dry-run", action="store_true", help="report, write no recipe")
    _ = ap.add_argument("--device", default="cpu", help="cpu, or cuda when the router leaves room")
    args = ap.parse_args()
    config = load_config(str(args.config_path))
    settings = config["recipe_tuning"]
    recipes = Path(str(settings["RECIPE_PATH"]))
    version = get_release(config).name
    device = str(args.device)
    torch.manual_seed(SEED)
    report: dict[str, Any] = {"version": version}
    chosen: dict[str, dict[str, float]] = {}
    for name, (metric, k) in TARGETS.items():
        train = load_cases(cache_path(config, metric, "train"), device)
        val = load_cases(cache_path(config, metric, "val"), device)
        judge = train + val if name in POOLED else val
        start = shipped(recipes / f"{name}.toml", device)
        fitted = fit(train, start, k)
        searched = search(train, fitted, k)
        rows = {}
        for label, exponents in (("shipped", start), ("fit", fitted), ("search", searched)):
            scaled = exponents / exponents[FIXED]
            rows[label] = {
                "train": recall_at(train, scaled, k),
                "judged": recall_at(judge, scaled, k),
                "exponents": {t: float(v) for t, v in zip(TERMS, scaled, strict=True)},
            }
            print(
                f"[fit] {name} {label:8} train R@{k} {rows[label]['train']:.4f}"
                f" {'train+val' if name in POOLED else 'val'} R@{k} {rows[label]['judged']:.4f}",
                flush=True,
            )
        best = max(rows, key=lambda r: rows[r]["judged"])
        chosen[name] = rows[best]["exponents"]
        report[name] = {"metric": metric, "k": k, "picked": best, "candidates": rows}
        print(f"[fit] {name}: {best} picked", flush=True)
    for name, (base, zeroed) in ZEROED.items():
        chosen[name] = {t: 0.0 if t in zeroed else v for t, v in chosen[base].items()}
    out = Path(str(settings["OUTPUT_PATH"])) / "tuning" / f"{version}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(f"[fit] wrote {out}", flush=True)
    if args.dry_run:
        return
    for name, exponents in chosen.items():
        if name in TARGETS:
            metric = TARGETS[name][0]
            line = f"tuned on {metric} train, {version}"
        else:
            line = f"untuned, the {ZEROED[name][0]} point with one direction at zero"
        write_weights(recipes / f"{name}.toml", exponents, line)
        print(f"[fit] wrote {name}.toml", flush=True)


if __name__ == "__main__":
    main()
