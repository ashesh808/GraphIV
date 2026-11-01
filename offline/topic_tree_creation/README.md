# topic_tree_creation

Sorts every embedded paper into a three-level topic tree and gives every node a label.
It reads `papers.embed_full` and writes two tables of its own, so it never rewrites a column of `papers`.

```
schema.sql                   the topic_tree and topic_names tables, applied once before anything else
indexes.sql                  both indexes, applied after the bulk loads
stage0_umap.py               fits the reducer, then projects the whole corpus through it
stage1_create_topic_tree.py  clusters the projected vectors into three levels
stage2_topic_labeling.py     labels every node of the tree with the LLM, leaves first
```

## The Stage Column

```
0  projected, not yet placed in the tree
1  placed, level_0 through level_2 written
```

Labeling has no stage, since a label belongs to a node and not to a paper.
Stage 2 refuses to run while any row is still at 0, and rebuilds `topic_names` in full every time, because stage 1 reassigns what each leaf id means.

## Running It

```sh
uv run python offline/topic_tree_creation/stage0_umap.py
uv run python offline/topic_tree_creation/stage1_create_topic_tree.py
uv run python offline/topic_tree_creation/stage2_topic_labeling.py
```

`stage0` takes `--skip-fit` to project through the model already on disk, which only makes sense when the corpus has not grown since that fit.
It refuses to fit while any paper still sits at papers stage 2, since a fit on part of the corpus looks fine and has the wrong neighborhoods.

Stages 0 and 1 rewrite their whole table with one `TRUNCATE` and one `COPY` rather than an `UPDATE`, because a refit changes every vector and every label.
That leaves no dead rows for vacuum, where the same work as an `UPDATE` cost an hour of index maintenance back when these columns lived in `papers`.

Stage 0 needs no service.
Stage 2 needs `llama-router` running, and labels each leaf from the papers nearest its centroid, then each parent and grandparent from its children's labels.
Reasoning is turned off on every call, or the model spends its whole budget thinking and returns nothing.
