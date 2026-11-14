#!/usr/bin/env python3
"""Rebuild and run the Madiwala loop simulation end to end.

  python run.py                     network -> scenarios -> demand -> runs -> metrics -> report
  python run.py --gtfs PATH         also re-extract bus trips from a GTFS folder first
  python run.py --from STEP         start at a step: net | scenarios | demand | sim | metrics | report
  python run.py --scenarios a,b     only simulate these scenarios (baseline,trial_crossings,flyover_opened)
"""
import argparse, os, subprocess, sys, time

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
STEPS = ['net', 'scenarios', 'demand', 'sim', 'metrics', 'report']
SCRIPT = {'net': 'build_net.py', 'scenarios': 'make_scenarios.py', 'demand': 'make_demand.py',
          'sim': 'run_sim.py', 'metrics': 'metrics.py', 'report': 'report.py'}

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument('--gtfs'); ap.add_argument('--from', dest='start', choices=STEPS, default='net'); ap.add_argument('--scenarios')
a = ap.parse_args()

def step(name, *args):
    t = time.time(); print(f'== {name}', flush=True)
    r = subprocess.run([PY, os.path.join(ROOT, 'scripts', name), *args], cwd=os.path.join(ROOT, 'scripts'))
    if r.returncode: sys.exit(f'step {name} failed')
    print(f'   ({time.time() - t:.0f}s)', flush=True)

if a.gtfs or not os.path.exists(os.path.join(ROOT, 'inputs', 'gtfs_peak.json')):
    step('prep_gtfs.py', *([a.gtfs] if a.gtfs else []))
for s in STEPS[STEPS.index(a.start):]:
    step(SCRIPT[s], *(a.scenarios.split(',') if s == 'sim' and a.scenarios else []))
print(f"\ndone - see {os.path.join(ROOT, 'report', 'REPORT.md')}")
