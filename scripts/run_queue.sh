#!/bin/bash
# Run many (scenario, seed) simulations, a few at a time, each into out/seeds/<scenario>/<seed>/.
#   scripts/run_queue.sh jobs.txt [parallel=11]      jobs.txt: one "scenario seed" per line
# Then: python scripts/seeds.py <scenario> <seeds...> --no-sim, and scripts/compare.py.
cd "$(dirname "$0")"
PY="$(pwd)/../.venv/bin/python"
run() {
  out="$(pwd)/../out/seeds/$1/$2"; mkdir -p "$out"
  SIM_OUT="$out" SUMO_SEED="$2" "$PY" run_sim.py "$1" > "$out/run.log" 2>&1 && SIM_OUT="$out" "$PY" metrics.py >> "$out/run.log" 2>&1 \
    && echo "done $1 $2" || echo "FAILED $1 $2 (see $out/run.log)"
}
export -f run; export PY
xargs -P "${2:-11}" -L 1 bash -c 'run "$0" "$1"' < "$1"
