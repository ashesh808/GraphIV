-- arxivkg phase_3 citation graph schema.
-- Applied idempotently on startup by phase_3.parse.db.ensure_schema().

CREATE TABLE IF NOT EXISTS paper (
    id        INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    arxiv_id  TEXT UNIQUE NOT NULL
);

-- Primary key is (citing_id, ordinal): the citation occurrence itself is the
-- unique identity. Re-parsing the same HTML produces the same ordinal, so
-- ingest is idempotent via ON CONFLICT.
CREATE TABLE IF NOT EXISTS citation (
    citing_id       INT  NOT NULL REFERENCES paper(id),
    ordinal         INT  NOT NULL,
    bib_local_id    TEXT NOT NULL,
    cited_id        INT  REFERENCES paper(id),       -- NULL when unresolved
    method          TEXT NOT NULL,                   -- link|text|doi|jref|title-*|rejected-*|none
    score           REAL,
    section         TEXT,
    sentence        TEXT,
    paragraph       TEXT,
    raw_bib_text    TEXT,
    co_cited_bibs   TEXT[],
    intent          TEXT,
    intent_score    REAL,
    intent_model    TEXT,
    PRIMARY KEY (citing_id, ordinal)
);

-- Created AFTER bulk load by ensure_indexes():
--   CREATE INDEX citation_cited_idx       ON citation(cited_id) WHERE cited_id IS NOT NULL;
--   CREATE INDEX citation_intent_null_idx ON citation(citing_id, ordinal) WHERE intent IS NULL;
