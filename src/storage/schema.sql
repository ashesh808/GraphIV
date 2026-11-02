-- GraphIV immutable corpus metadata, schema version 1.
-- Dates are ISO YYYY-MM-DD strings. Vector blobs are little-endian float32
-- unless corpus_metadata.vector_dtype explicitly declares float16. Published
-- GraphIV embeddings/PostgreSQL halfvec values are losslessly stored as float16.
PRAGMA foreign_keys = ON;

CREATE TABLE corpus_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
INSERT INTO corpus_metadata VALUES ('schema_version', '1');
-- Builders also write embedding_dimension/model, vector_dtype, and FAISS
-- candidate-index settings faiss_index_kind/nlist/nprobe/oversample.

CREATE TABLE papers (
    arxiv_id TEXT PRIMARY KEY,
    stage INTEGER NOT NULL DEFAULT 0 CHECK (stage BETWEEN 0 AND 4),
    title TEXT,
    abstract TEXT,
    date TEXT,
    primary_category TEXT,
    authors TEXT,
    surnames TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(surnames)),
    embed_full BLOB,
    survey_probability REAL
);
CREATE INDEX papers_stage_date ON papers(stage, date);

-- Every FAISS result label must resolve through this table. A plain IndexFlatIP
-- uses sequential labels 0..ntotal-1. The index stores L2-normalized vectors and
-- uses inner product; papers.embed_full remains available for exact reranking.
CREATE TABLE vector_ids (
    faiss_id INTEGER PRIMARY KEY CHECK (faiss_id >= 0),
    arxiv_id TEXT NOT NULL UNIQUE REFERENCES papers(arxiv_id)
);

CREATE TABLE paper_surnames (
    surname TEXT NOT NULL,
    arxiv_id TEXT NOT NULL REFERENCES papers(arxiv_id) ON DELETE CASCADE,
    PRIMARY KEY (surname, arxiv_id)
);
CREATE TRIGGER papers_surnames_insert AFTER INSERT ON papers BEGIN
    INSERT OR IGNORE INTO paper_surnames(surname, arxiv_id)
    SELECT value, NEW.arxiv_id FROM json_each(NEW.surnames);
END;
CREATE TRIGGER papers_surnames_update AFTER UPDATE OF surnames ON papers BEGIN
    DELETE FROM paper_surnames WHERE arxiv_id = NEW.arxiv_id;
    INSERT OR IGNORE INTO paper_surnames(surname, arxiv_id)
    SELECT value, NEW.arxiv_id FROM json_each(NEW.surnames);
END;

CREATE TABLE citations (
    citation_id INTEGER PRIMARY KEY,
    source_id TEXT NOT NULL,
    target_id TEXT,
    stage INTEGER NOT NULL DEFAULT 0,
    sentence TEXT,
    intent TEXT,
    intent_score REAL
);
CREATE INDEX citations_source ON citations(source_id);
CREATE INDEX citations_target ON citations(target_id, stage, intent);

CREATE TABLE topic_tree (
    arxiv_id TEXT PRIMARY KEY REFERENCES papers(arxiv_id),
    stage INTEGER NOT NULL DEFAULT 0 CHECK (stage BETWEEN 0 AND 1),
    level_0 INTEGER,
    level_1 INTEGER,
    level_2 INTEGER
);
CREATE TABLE topic_names (
    level_0 INTEGER NOT NULL,
    level_1 INTEGER,
    level_2 INTEGER,
    name TEXT NOT NULL
);
CREATE UNIQUE INDEX topic_names_root ON topic_names(level_0)
    WHERE level_1 IS NULL AND level_2 IS NULL;
CREATE UNIQUE INDEX topic_names_parent ON topic_names(level_0, level_1)
    WHERE level_1 IS NOT NULL AND level_2 IS NULL;
CREATE UNIQUE INDEX topic_names_leaf ON topic_names(level_0, level_1, level_2)
    WHERE level_2 IS NOT NULL;
