-- GraphIV store: one row per paper, one row per citation occurrence, one row per topic node.

CREATE EXTENSION IF NOT EXISTS vector;

-- stage is the only queue: 0 added, 1 pdf, 2 html, 3 embedded, 4 clustered
CREATE TABLE IF NOT EXISTS papers (
    arxiv_id         text PRIMARY KEY,
    stage            smallint NOT NULL DEFAULT 0 CHECK (stage BETWEEN 0 AND 4),
    title            text,
    abstract         text,
    date             date,
    primary_category text,
    authors          text,
    surnames         text[],
    latest_version   text NOT NULL,
    doi              text,
    journal_ref      text,
    embed_full       halfvec(768),
    embed_umap       vector(50),
    level_0          smallint,
    level_1          smallint,
    level_2          smallint
);

-- citation_id is the only key as one paper can cite the same target more than once
CREATE TABLE IF NOT EXISTS citations (
    citation_id  bigserial PRIMARY KEY,
    source_id    text NOT NULL,
    target_id    text,
    stage        smallint NOT NULL DEFAULT 0,
    section      text,
    resolved_by  text,
    sentence     text,
    intent       text,
    intent_score real
);

-- One row per tree node, with level_1 and level_2 null on a parent and a grandparent.
-- A primary key cannot hold null, so the node identity is a unique index that treats nulls as equal
CREATE TABLE IF NOT EXISTS topics (
    topic_id bigserial PRIMARY KEY,
    level_0  smallint NOT NULL,
    level_1  smallint,
    level_2  smallint,
    name     text NOT NULL,
    UNIQUE NULLS NOT DISTINCT (level_0, level_1, level_2)
);
