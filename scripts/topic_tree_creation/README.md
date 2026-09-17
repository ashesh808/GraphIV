# topic_tree_creation

Projects every embedded paper into a 50-dimension space, clusters it into a fixed-depth tree, and names every node. Reads `papers.embed_full` and writes two tables of its own, so nothing here ever rewrites a column of `papers`.

```
schema.sql                    topic_tree and topic_names, applied once before anything else
indexes.sql                   both indexes, applied after the bulk loads
stage0_umap.py                fit the reducer, then rebuild topic_tree through it
stage1_create_topic_tree.py   cluster the projected vectors into three levels
stage2_topic_labeling.py      name every node of the tree with an LLM
```

## The stage column

```
0  projected, no place in the tree
1  clustered, level_0 through level_2
```

Naming has no stage of its own, since a name belongs to a node and not to a paper. `stage2` refuses to run while any row sits at 0, and rebuilds `topic_names` in full every time, because stage 1 reassigns what a given leaf id means.

## Running it

```sh
uv run python scripts/topic_tree_creation/stage0_umap.py
uv run python scripts/topic_tree_creation/stage1_create_topic_tree.py
uv run python scripts/topic_tree_creation/stage2_topic_labeling.py
```

`stage0` takes `--skip-fit` to project through the model already on disk instead of fitting a new one, which only makes sense when the corpus has not grown since that fit.

Both of the first two stages rewrite the whole table rather than updating it, one `TRUNCATE` and one `COPY`, because a refit moves every vector and reassigns every label. That writes no dead rows and leaves nothing for vacuum, where the same work as an `UPDATE` cost an hour of index maintenance when these columns still lived in `papers`.

Stage 0 needs no service. Stage 2 needs `llama-router` up, and names leaves from the papers nearest their centroid, then parents and grandparents from their children's names. Reasoning is disabled on every call, without which the model spends its whole completion budget on chain of thought and returns nothing.
