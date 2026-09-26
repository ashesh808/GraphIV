# 02-07-frontier-reach

**What:** the frontier reservation is a slot count, not an on-off switch.
This sweeps it from 0 to 48 with the joint score held fixed, so the reservation is the only thing
that moves, and scores both coverage and how new the picks are.

**Conclusion:** it is close to free up to about 32 slots.
Reserving 32 of 80 buys 343 more picks under two years old and costs one gold paper on dev and six
on test.
Only at 48 does it start actually costing coverage, at 10 dev papers.

Run: `uv run python run.py` (reads `cache/frontier_reach.json`, a few seconds).

## The sweep

Gold in pool: dev 419, test 441.
`< 2yr` counts picks published within one year of the survey's own cutoff.

| reservation | dev | test | gold cost (dev) | median age | picks < 2yr | recency gain |
| --- | --- | --- | --- | --- | --- | --- |
| reserve 24 slots | **337** | 331 | +5 | 4.0 | 946 | +223 |
| reserve 16 slots | 334 | 331 | +2 | 5.0 | 862 | +139 |
| reserve 8 slots | 333 | 332 | +1 | 5.0 | 785 | +62 |
| reserve 32 slots (shipped) | 333 | 329 | +1 | 4.0 | 1066 | +343 |
| no reservation | 332 | 335 | 0 | 5.0 | 723 | 0 |
| reserve 48 slots | 322 | 319 | -10 | 3.0 | 1307 | +584 |

## Reading it

Coverage is flat across the first five rows.
Dev spans 332 to 337 and test spans 329 to 335, and both ranges are smaller than the dev-to-test
gap of any single arm, so nothing between 0 and 32 reserved slots is distinguishable on coverage.

Recency is not flat at all.
Picks under two years old go from 723 to 1066 over the same range, a 47 percent increase, and the
median age drops from 5 years to 4.

So the reservation is not a trade in the 0 to 32 range.
It is a free parameter that buys recency and is paid for out of slack rather than out of gold.

At 48 the slack runs out.
Coverage falls 10 papers on dev and 16 on test while recency keeps climbing, which is the trade
finally arriving.

## Correcting an earlier reading

The joint selector was chosen with the reservation off, and that was read as evidence that dropping
the reservation is what made it win.
The sweep says otherwise: turning the reservation off is worth zero to two papers, well inside
noise, and the win came from the fused score.

Practically this means the two are independent.
Use the fused score for coverage and set the reservation by how new an answer the question needs,
without trading one against the other.

## For the arc

This is the first lever in the retrieval stage that is genuinely a control surface rather than a
setting with a right answer.
Everything else measured here has an optimum.
This one is a dial the caller should own, and the shipped adaptive floor already sits near the top
of its useful range.
