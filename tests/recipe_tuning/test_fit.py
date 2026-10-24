import torch
from stage0_cache_terms import TERMS
from stage1_fit_recipes import FIXED, fit, from_exponents, recall_at, to_exponents


def _cases(planted: torch.Tensor, n_cases: int = 40, pool: int = 300, k: int = 30):
    """
    Pools whose answer is the planted ranking's top k, so the planted exponents score recall 1
    """
    gen = torch.Generator().manual_seed(0)
    out = []
    for _ in range(n_cases):
        x = torch.rand(pool, len(TERMS), generator=gen)
        y = torch.zeros(pool, dtype=torch.bool)
        y[torch.topk(x @ planted, k).indices] = True
        out.append((x, y, k))
    return out


def test_the_constraint_round_trips():
    exponents = torch.tensor([0.5 if t != "cos" else 2.0 for t in TERMS])
    back = to_exponents(from_exponents(exponents))
    assert torch.allclose(back, exponents / exponents[FIXED], atol=1e-4)
    assert back[FIXED] == 1


def test_the_fit_recovers_a_planted_ranking():
    planted = torch.tensor([3.0 if t == "anc" else 1.0 if t == "cos" else 0.0 for t in TERMS])
    cases = _cases(planted)
    start = torch.ones(len(TERMS))
    before = recall_at(cases, start, 30)
    fitted = fit(cases, start, 30)
    assert recall_at(cases, fitted, 30) > max(before + 0.2, 0.85)
    assert fitted[TERMS.index("anc")] == fitted.max()
