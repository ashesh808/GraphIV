-- arxivkg SINGLE-STORE schema (Postgres + pgvector).
--
-- Consolidates the former SQLite (metadata), Postgres (citations), and Neo4j (graph + vector
-- index) stores into ONE project-owned Postgres under ./data/pg. Applied idempotently.
--
-- `citation` mirrors the live global-DB columns (so phase-3 parse stays drop-in compatible), but
-- the migration leaves the bulky parse-scratch (paragraph / raw_bib_text / co_cited_bibs) NULL —
-- they are build-time only and not needed to serve phase-6. That keeps the store slim.
--
-- No FK constraints: this is a serving store loaded by bulk COPY from already-clean data; FK
-- checks on the 173M-row citation load would be ruinous. Joins are by id / arxiv_id regardless.

CREATE EXTENSION IF NOT EXISTS vector;

-- Interned id map: the citation occurrence is the identity. Integer ids are PRESERVED from the
-- source DB at migration (citation.citing_id/cited_id reference them).
CREATE TABLE IF NOT EXISTS paper (
    id        INT PRIMARY KEY,
    arxiv_id  TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS citation (
    citing_id       INT  NOT NULL,
    ordinal         INT  NOT NULL,
    bib_local_id    TEXT NOT NULL,
    cited_id        INT,                             -- NULL when unresolved
    method          TEXT NOT NULL,                   -- link|text|doi|jref|title-*|rejected-*|none
    score           REAL,
    section         TEXT,
    sentence        TEXT,                            -- kept: small, used by label/bert + grounding
    paragraph       TEXT,                            -- parse-scratch; migration leaves NULL
    raw_bib_text    TEXT,                            -- parse-scratch; migration leaves NULL
    co_cited_bibs   TEXT[],                          -- parse-scratch; migration leaves NULL
    intent          TEXT,
    intent_score    REAL,
    intent_model    TEXT,
    polarity        TEXT,
    polarity_score  REAL,
    PRIMARY KEY (citing_id, ordinal)
);

-- Corpus metadata (migrated from SQLite arxiv.db). Keyed by arxiv_id.
CREATE TABLE IF NOT EXISTS paper_meta (
    arxiv_id          TEXT PRIMARY KEY,
    title             TEXT,
    abstract          TEXT,
    year              SMALLINT,        -- derived from arxiv_id at migration (arxiv_year)
    primary_category  TEXT,
    authors           TEXT             -- raw comma-separated author string (Kaggle dump)
);
CREATE INDEX IF NOT EXISTS paper_meta_year_idx ON paper_meta(year);
CREATE INDEX IF NOT EXISTS paper_meta_cat_idx  ON paper_meta(primary_category);

-- Embeddings (replaces the Neo4j `paper_emb` vector index). Normalized nomic 768-d vectors.
CREATE TABLE IF NOT EXISTS paper_embedding (
    arxiv_id   TEXT PRIMARY KEY,
    embedding  halfvec(768) NOT NULL   -- float16: halves footprint, negligible cosine loss
);
-- HNSW cosine index built AFTER bulk load by the migration:
--   CREATE INDEX paper_emb_hnsw ON paper_embedding USING hnsw (embedding halfvec_cosine_ops);

-- Topic tree (migrated from SQLite topic_tree_nomic.db). Every paper gets a leaf; no noise bucket.
CREATE TABLE IF NOT EXISTS leaf (
    leaf_id  INT PRIMARY KEY,
    size     INT,
    depth    INT,
    radius   REAL
);
CREATE TABLE IF NOT EXISTS paper_topic (
    arxiv_id  TEXT PRIMARY KEY,
    leaf_id   INT,
    path      TEXT,
    depth     INT
);
CREATE INDEX IF NOT EXISTS paper_topic_leaf_idx ON paper_topic(leaf_id);

-- Human-gold intent/polarity labels (Phase C web labeling tool -> E2 stage-2 benchmark).
CREATE TABLE IF NOT EXISTS gold_label (
    citing_id   INT  NOT NULL,
    ordinal     INT  NOT NULL,
    intent      TEXT,
    polarity    TEXT,
    labeler     TEXT,
    labeled_at  TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (citing_id, ordinal)
);

-- Built AFTER bulk load by the migration:
--   CREATE INDEX citation_cited_idx       ON citation(cited_id) WHERE cited_id IS NOT NULL;
--   CREATE INDEX citation_intent_null_idx ON citation(citing_id, ordinal) WHERE intent IS NULL;
--   CREATE INDEX citation_citing_idx      ON citation(citing_id);
