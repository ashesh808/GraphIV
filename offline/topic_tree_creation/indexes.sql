-- Built after the bulk loads, never before, since an index on an empty table only slows the load.

SET maintenance_work_mem = '8GB';
SET max_parallel_maintenance_workers = 4;

CREATE INDEX IF NOT EXISTS topic_tree_stage_idx  ON topic_tree (stage);
CREATE INDEX IF NOT EXISTS topic_tree_levels_idx ON topic_tree (level_0, level_1, level_2);
