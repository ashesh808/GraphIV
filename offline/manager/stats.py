"""
The dashboard's numbers: one query per chart, run in the background and kept as json on disk

A query over citations that no index covers reads the whole table, so nothing here runs per request
Each result is its own file, so one slow query never holds back the rest of the page
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, LiteralString

import psycopg

LOG = logging.getLogger(__name__)


@dataclass
class Query:
    """
    One chart's rows, and the table the page files it under
    """

    name: str
    table: str
    sql: LiteralString


QUERIES = [
    Query("p_totals", "papers", "SELECT count(*), min(date), max(date) FROM papers"),
    Query("p_stage", "papers", "SELECT stage, count(*) FROM papers GROUP BY 1 ORDER BY 1"),
    Query(
        "p_year",
        "papers",
        "SELECT extract(year FROM date)::int, count(*) FROM papers GROUP BY 1 ORDER BY 1",
    ),
    Query(
        "p_month",
        "papers",
        """SELECT to_char(date_trunc('month', date), 'YYYY-MM'), count(*) FROM papers
           WHERE date >= date_trunc('month', now()) - interval '35 months' GROUP BY 1 ORDER BY 1""",
    ),
    Query(
        "p_archive",
        "papers",
        """SELECT split_part(primary_category, '.', 1), count(*) FROM papers
           GROUP BY 1 ORDER BY 2 DESC""",
    ),
    Query(
        "p_category",
        "papers",
        "SELECT primary_category, count(*) FROM papers GROUP BY 1 ORDER BY 2 DESC LIMIT 30",
    ),
    Query(
        "p_survey",
        "papers",
        """SELECT width_bucket(survey_probability, 0, 1.000001, 20), count(*) FROM papers
           WHERE survey_probability IS NOT NULL GROUP BY 1 ORDER BY 1""",
    ),
    Query(
        "p_versions",
        "papers",
        """SELECT least(nullif(regexp_replace(latest_version, '\\D', '', 'g'), '')::int, 10),
                  count(*)
           FROM papers GROUP BY 1 ORDER BY 1""",
    ),
    Query(
        "p_authors",
        "papers",
        """SELECT least(coalesce(array_length(surnames, 1), 0), 30), count(*) FROM papers
           GROUP BY 1 ORDER BY 1""",
    ),
    Query(
        "p_parsable",
        "papers",
        "SELECT is_citation_parsable::text, count(*) FROM papers GROUP BY 1 ORDER BY 1",
    ),
    Query(
        "p_published",
        "papers",
        """SELECT count(*) FILTER (WHERE doi IS NOT NULL),
                  count(*) FILTER (WHERE journal_ref IS NOT NULL),
                  count(*) FILTER (WHERE survey_probability >= 0.5) FROM papers""",
    ),
    Query("t_stage", "tree", "SELECT stage, count(*) FROM topic_tree GROUP BY 1 ORDER BY 1"),
    Query(
        "t_grand",
        "tree",
        """SELECT t.level_0, n.name, count(*) FROM topic_tree t
           LEFT JOIN topic_names n ON n.level_0 = t.level_0 AND n.level_1 IS NULL
           GROUP BY 1, 2 ORDER BY 3 DESC""",
    ),
    Query(
        "t_parents",
        "tree",
        """SELECT t.level_0, t.level_1, n.name, count(*) FROM topic_tree t
           LEFT JOIN topic_names n
             ON n.level_0 = t.level_0 AND n.level_1 = t.level_1 AND n.level_2 IS NULL
           GROUP BY 1, 2, 3 ORDER BY 4 DESC""",
    ),
    Query(
        "t_leaves",
        "tree",
        """SELECT t.level_0, t.level_1, t.level_2, n.name, count(*) FROM topic_tree t
           LEFT JOIN topic_names n
             ON n.level_0 = t.level_0 AND n.level_1 = t.level_1 AND n.level_2 = t.level_2
           GROUP BY 1, 2, 3, 4 ORDER BY 5 DESC""",
    ),
    Query(
        "t_names",
        "tree",
        """SELECT CASE WHEN level_1 IS NULL THEN 0 WHEN level_2 IS NULL THEN 1 ELSE 2 END, count(*)
           FROM topic_names GROUP BY 1 ORDER BY 1""",
    ),
    Query(
        "c_totals",
        "citations",
        """SELECT 'rows', count(*) FROM citations
           UNION ALL SELECT 'resolved', count(*) FROM citations WHERE target_id IS NOT NULL""",
    ),
    Query(
        "c_intent",
        "citations",
        """SELECT coalesce(intent, 'unlabeled'), stage, count(*) FROM citations
           WHERE target_id IS NOT NULL GROUP BY 1, 2 ORDER BY 3 DESC""",
    ),
    Query(
        "c_resolved_by",
        "citations",
        """SELECT coalesce(resolved_by, 'unresolved'), count(*) FROM citations
           GROUP BY 1 ORDER BY 2 DESC""",
    ),
    Query(
        "c_section",
        "citations",
        """SELECT coalesce(
                    nullif(regexp_replace(lower(section), '^([0-9]+|[ivx]+)[.)]?\\s+', ''), ''),
                    'none'),
                  count(*)
           FROM citations GROUP BY 1 ORDER BY 2 DESC LIMIT 20""",
    ),
    Query(
        "c_out",
        "citations",
        """SELECT least(n, 300) / 10, count(*) FROM
           (SELECT count(*) AS n FROM citations GROUP BY source_id) s GROUP BY 1 ORDER BY 1""",
    ),
    Query(
        "c_in",
        "citations",
        """SELECT CASE WHEN n < 1000 THEN width_bucket(ln(n), 0, ln(1000), 15) ELSE 16 END, count(*)
           FROM (SELECT count(*) AS n FROM citations WHERE target_id IS NOT NULL
                 GROUP BY target_id) s
           GROUP BY 1 ORDER BY 1""",
    ),
    Query(
        "c_top",
        "citations",
        """SELECT c.target_id, p.title, p.date, c.n FROM
           (SELECT target_id, count(*) AS n FROM citations WHERE target_id IS NOT NULL
            GROUP BY 1 ORDER BY 2 DESC LIMIT 20) c
           JOIN papers p ON p.arxiv_id = c.target_id ORDER BY c.n DESC""",
    ),
    Query(
        "c_score",
        "citations",
        """SELECT intent, width_bucket(intent_score, 0, 1.000001, 20), count(*) FROM citations
           WHERE target_id IS NOT NULL AND intent IS NOT NULL GROUP BY 1, 2 ORDER BY 1, 2""",
    ),
    Query(
        "s_tables",
        "storage",
        """SELECT c.relname, pg_total_relation_size(c.oid), pg_relation_size(c.oid),
                  pg_indexes_size(c.oid), c.reltuples::bigint
           FROM pg_class c JOIN pg_namespace s ON s.oid = c.relnamespace
           WHERE s.nspname = 'public' AND c.relkind = 'r' ORDER BY 2 DESC""",
    ),
    Query(
        "s_indexes",
        "storage",
        """SELECT indexrelname, relname, pg_relation_size(indexrelid), idx_scan
           FROM pg_stat_user_indexes ORDER BY 3 DESC""",
    ),
    Query("s_database", "storage", "SELECT pg_database_size(current_database())"),
]


def plain(value: object) -> object:
    """
    One cell as json can hold it

    Args:
        value: What psycopg returned.

    Returns:
        A string, number, bool or None.
    """
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def read(root: Path) -> dict[str, Any]:
    """
    Every result on disk, which is what the page draws from

    Args:
        root: The stats directory.

    Returns:
        Each query's rows and when it ran, keyed by name.
    """
    out: dict[str, Any] = {}
    for query in QUERIES:
        try:
            out[query.name] = json.loads((root / f"{query.name}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
    return out


def refresh(dsn: str, root: Path, only: str = "") -> None:
    """
    Runs every query, or one table's, writing each result the moment it lands

    Args:
        dsn: libpq connection string.
        root: The stats directory.
        only: A table to limit the run to, empty for all of them.
    """
    root.mkdir(parents=True, exist_ok=True)
    with psycopg.connect(dsn, autocommit=True) as conn:
        _ = conn.execute("SET application_name = 'graphiv-manager:stats'")
        for query in QUERIES:
            if only and query.table != only:
                continue
            clock = time.time()
            try:
                rows = [[plain(v) for v in row] for row in conn.execute(query.sql).fetchall()]
            except psycopg.Error as err:
                LOG.warning("%s failed: %s", query.name, err)
                continue
            said = {"rows": rows, "seconds": round(time.time() - clock, 2), "taken": time.time()}
            part = root / f"{query.name}.json.part"
            _ = part.write_text(json.dumps(said), encoding="utf-8")
            os.replace(part, root / f"{query.name}.json")
            LOG.info("%s: %d rows in %.1fs", query.name, len(rows), said["seconds"])
