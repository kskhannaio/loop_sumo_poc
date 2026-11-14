#!/usr/bin/env python3
"""Watch a scenario in sumo-gui with the project's readable colour scheme.

  python view.py                    trial_crossings
  python view.py baseline           (or flyover_opened)
Colours: two-wheelers orange, cars blue, autos green, goods/trucks brown, buses red, people magenta.
Starts at 07:30 (warm-up; metrics count from 08:00). Use the speed slider ("Delay") to slow down or speed up.
"""
import os, subprocess, sys
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from common import BIN, P, cfg, hhmm
s = sys.argv[1] if len(sys.argv) > 1 else 'trial_crossings'
T = cfg()['time']
if not os.path.exists(P('demand', s, 'vehicles.rou.xml')): sys.exit(f'no demand for {s} - run `python run.py` first')
adds = [P('demand', s, 'busstops.add.xml')] + ([P('net', 'trial_tls.add.xml')] if s != 'baseline' else [])
subprocess.run([BIN('sumo-gui'), '-n', P('net', f'{s}.net.xml'),
                '-r', ','.join(P('demand', s, f) for f in ('vehicles.rou.xml', 'buses.rou.xml', 'persons.rou.xml')),
                '-a', ','.join(adds), '--gui-settings-file', P('config', 'gui-settings.xml'),
                '--begin', str(hhmm(T['sim_begin'])), '--end', str(hhmm(T['sim_end'])), '--step-length', str(T['step_length_s']),
                '--lateral-resolution', str(T['lateral_resolution_m']), '--seed', str(T['seed']),
                '--pedestrian.model', 'striping', '--time-to-teleport', '300', '--ignore-route-errors', 'true',
                '--no-warnings', 'true', '--delay', '40', '--start', '--window-size', '1400,900',
                '--window-pos', '40,40'])
