"""
Dump the whole store into one pg_dump archive, which is the file a restore starts from

pg_dump prints nothing while it copies, so progress is read off pg_stat_progress_copy instead
The archive keeps a .part name until pg_dump exits zero, so a stopped dump never looks finished
"""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

import psycopg

from src.core.config import load_config

COMPRESS = "zstd:3"
POLL = 10.0
# the dump may share a disk with the cluster, which cannot write its WAL to a full one
FLOOR = 10 * 1024**3


def tables(conn: psycopg.Connection) -> dict[int, int]:
    """
    Every table pg_dump copies, with the planner's row estimate

    Args:
        conn: An open connection to the store.

    Returns:
        The estimated rows per table oid.
    """
    rows = conn.execute(
        "SELECT c.oid, greatest(c.reltuples, 0)::bigint FROM pg_class c"
        " JOIN pg_namespace n ON n.oid = c.relnamespace"
        " WHERE n.nspname = 'public' AND c.relkind = 'r'"
    ).fetchall()
    return {int(oid): int(est) for oid, est in rows}


def copying(conn: psycopg.Connection, app: str) -> tuple[int, int] | None:
    """
    The table pg_dump is copying now and how many of its rows have gone out

    Args:
        conn: An open connection to the store.
        app: The application_name pg_dump connected with.

    Returns:
        The table oid and its rows so far, None between tables.
    """
    row = conn.execute(
        "SELECT p.relid, p.tuples_processed FROM pg_stat_progress_copy p"
        " JOIN pg_stat_activity a USING (pid) WHERE a.application_name = %s",
        (app,),
    ).fetchone()
    return (int(row[0]), int(row[1])) if row else None


def dump(dsn: str, target: Path) -> None:
    """
    Runs pg_dump into target, printing rows copied against the estimate as it goes

    Args:
        dsn: libpq connection string.
        target: The archive to write.
    """
    if shutil.which("pg_dump") is None:
        sys.exit("[dump] pg_dump is not on PATH")
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_name(f"{target.name}.part")
    app = f"{os.environ.get('PGAPPNAME', 'graphiv')}:pg_dump"
    with psycopg.connect(dsn, autocommit=True) as conn:
        estimate = tables(conn)
        seen: dict[int, int] = {}
        finished: set[int] = set()
        now = 0
        print(f"[dump] {len(estimate)} tables into {target}", flush=True)
        clock = time.time()
        proc = subprocess.Popen(
            ["pg_dump", "-Fc", f"--compress={COMPRESS}", "-f", str(part), "-d", dsn],
            env=dict(os.environ, PGAPPNAME=app),
        )
        stopped, code = "", -1
        try:
            while True:
                try:
                    code = proc.wait(timeout=POLL)
                    break
                except subprocess.TimeoutExpired:
                    pass
                found = copying(conn, app)
                if now and (found is None or found[0] != now):
                    finished.add(now)
                now = found[0] if found else 0
                if found:
                    seen[now] = max(seen.get(now, 0), found[1])
                rows = {oid: max(est, seen.get(oid, 0)) for oid, est in estimate.items()}
                done = sum(rows[oid] for oid in finished) + (seen[now] if now else 0)
                written = part.stat().st_size if part.exists() else 0
                print(
                    f"[dump] {done:,}/{sum(rows.values()):,} rows, {written / 1e9:.1f} GB written",
                    flush=True,
                )
                free = shutil.disk_usage(target.parent).free
                if free < FLOOR:
                    stopped = f"[dump] stopped at {free / 1e9:.1f} GB free on {target.parent}"
                    proc.send_signal(signal.SIGINT)
                    code = proc.wait()
                    break
        finally:
            if proc.poll() is None:
                proc.send_signal(signal.SIGINT)
                _ = proc.wait()
            if proc.returncode != 0 or stopped:
                part.unlink(missing_ok=True)
    if stopped:
        sys.exit(stopped)
    if code != 0:
        sys.exit(code)
    os.replace(part, target)
    total = sum(max(est, seen.get(oid, 0)) for oid, est in estimate.items())
    print(f"[dump] {total:,}/{total:,} rows", flush=True)
    print(
        f"[dump] wrote {target}, {target.stat().st_size / 1e9:.1f} GB"
        f" in {time.time() - clock:.0f} s",
        flush=True,
    )


def main() -> None:
    """
    Read the config, then dump the store to graphiv-<date>.dump under EXPORT_PATH
    """
    ap = argparse.ArgumentParser()
    _ = ap.add_argument("--config_path", default="config.toml")
    args = ap.parse_args()

    cfg = load_config(str(args.config_path))
    root = Path(str(cfg["export"]["EXPORT_PATH"]))
    dump(str(cfg["database"]["PG_DEST"]), root / f"graphiv-{date.today().isoformat()}.dump")


if __name__ == "__main__":
    main()
