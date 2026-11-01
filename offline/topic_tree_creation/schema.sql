-- The projection of every embedded paper, and the name of every node it can be clustered into.

-- stage is the only queue: 0 projected, 1 placed in the tree
CREATE TABLE IF NOT EXISTS topic_tree (
    arxiv_id   text PRIMARY KEY REFERENCES papers (arxiv_id) ON DELETE CASCADE,
    stage      smallint NOT NULL DEFAULT 0 CHECK (stage BETWEEN 0 AND 1),
    embed_umap vector(50) NOT NULL,
    level_0    smallint,
    level_1    smallint,
    level_2    smallint
);

-- One row per node, with level_1 and level_2 null on a parent and a grandparent.
-- A primary key cannot hold null, so the node identity is a unique index that treats nulls as equal
CREATE TABLE IF NOT EXISTS topic_names (
    level_0 smallint NOT NULL,
    level_1 smallint,
    level_2 smallint,
    name    text NOT NULL,
    UNIQUE NULLS NOT DISTINCT (level_0, level_1, level_2)
);
