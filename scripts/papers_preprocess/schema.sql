-- GraphIV store: one row per paper, one row per citation occurrence.

CREATE EXTENSION IF NOT EXISTS vector;

-- stage is the only queue: 0 added, 1 pdf, 2 html, 3 embedded, 4 scored
-- is_citation_parsable records whether parsing the html ever yielded a citation, so a paper that
-- yields none is asked once rather than on every run
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
    survey_probability real,
    is_citation_parsable boolean
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
