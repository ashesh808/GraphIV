-- Built after the bulk loads, never before, since an index on an empty table only slows the load.
-- Run this once each stage that fills a column has finished.

SET maintenance_work_mem = '8GB';
SET max_parallel_maintenance_workers = 4;

CREATE INDEX IF NOT EXISTS papers_stage_idx  ON papers (stage);
CREATE INDEX IF NOT EXISTS papers_levels_idx ON papers (level_0, level_1, level_2);
CREATE INDEX IF NOT EXISTS papers_hnsw_idx   ON papers USING hnsw (embed_full halfvec_cosine_ops);

CREATE INDEX IF NOT EXISTS citations_source_idx ON citations (source_id);

-- Partial as only 72.8M of 180.7M rows carry a target
CREATE INDEX IF NOT EXISTS citations_target_idx ON citations (target_id) WHERE target_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS citations_queue_idx  ON citations (stage) WHERE target_id IS NOT NULL;
