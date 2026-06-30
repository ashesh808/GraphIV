#!/usr/bin/env bash
# Re-run every COMPOSING experiment + the flagship against the shipped phase-6 (asym + compose guard).
# Multi-hour marathon (judge-loop/critique/vision deep cells dominate). Clears the per-experiment and
# shared-deep run caches first so composes are genuinely fresh. 01-preprocessing/02-retrieval are
# SQL/retrieval-only (no compose) and are intentionally NOT re-run here.
#
#   bash experiments/rerun.sh            # full marathon
#   bash experiments/rerun.sh cheap      # only the cheap single-pass set
set -euo pipefail
cd "$(dirname "$0")/.."

CHEAP=(03-generation/03-03-embedding-format 03-generation/03-05-frontier-pull
       03-generation/03-02-component-ablation 03-generation/03-04-recency-knob
       03-generation/03-01-judge-validity)
DEEP=(03-generation/03-06-landmark-selection 03-generation/03-07-graph-representation
      03-generation/03-08-judge-loop 03-generation/03-09-critique-depth
      03-generation/03-10-vision-figures deep-research)

rm -rf experiments/showcase/runs/*   # shared DEEP_RUNS cache (forces fresh deep cells)

run_one() {
  local e="$1"
  echo "=== re-running $e ($(date +%H:%M)) ==="
  rm -rf "experiments/$e/results/runs"
  uv run python "experiments/$e/run.py"
  [ "$e" = "03-generation/03-07-graph-representation" ] && uv run python "experiments/$e/run.py" --phase2
}

for e in "${CHEAP[@]}"; do run_one "$e"; done
[ "${1:-}" = "cheap" ] && { echo "CHEAP set done."; exit 0; }
for e in "${DEEP[@]}"; do run_one "$e"; done

echo "MARATHON DONE. Driver experiments auto-refreshed metrics.json/md/ablation.png/table.tex."
echo "Next: refresh each report's prose/numbers from the fresh results, recompile report PDFs (latexmk),"
echo "then update paper/main.tex headline numbers + recompile."
