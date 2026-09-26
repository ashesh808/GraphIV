| rule | family | dev | test | headroom taken |
| --- | --- | --- | --- | --- |
| blend 0.5 graph | smooth blend | 333 | 341 | 35% |
| blend 0.65 graph | smooth blend | 332 | 335 | 34% |
| multiply, graph x grade | smooth blend | 331 | 338 | 33% |
| blend 0.35 graph | smooth blend | 330 | 343 | 33% |
| grade first, graph breaks ties | smooth blend | 324 | 338 | 28% |
| blend 0.8 graph | smooth blend | 318 | 322 | 23% |
| rrf, graph + reader | smooth blend | 317 | 344 | 23% |
| rrf, all three | smooth blend | 315 | 345 | 21% |
| quota 60 graph / 20 reader | hard split | 299 | 334 | 9% |
| quota 40 graph / 40 reader | hard split | 298 | 339 | 8% |
| quota 20 graph / 60 reader | hard split | 294 | 335 | 5% |
| multiply, cosine x grade | weak input | 292 | 303 | 4% |
| graph only | single signal | 287 | 310 | 0% |
| reader only | single signal | 284 | 312 | -2% |
| cosine only | single signal | 190 | 209 | -73% |

_One budget of 80 slots per survey, no reservation and no LeyLine quota_
