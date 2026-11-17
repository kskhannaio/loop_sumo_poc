"""Bring numbers from the PDF pipeline's exports into the simulation's settings.

The pipeline (../corridor_pdf_pipeline, `python main.py`) pulls the origin-destination study's tables out of the PDF and
writes exports/od/od_summary.json. This script turns them into the settings the simulation uses:

  vehicle_mix                 vehicles a day by type (buses left out: real buses come from the BMTC timetable)
  flyover_opened.divert_share the share of corridor traffic expected to use the elevated corridor: the midpoint of the
                              study's two figures (tollable vehicles, and all diverted vehicles, over the day's total)

  python scripts/import_pipeline.py            show what would change
  python scripts/import_pipeline.py --write    write the changes into config/assumptions.json

Other pipeline exports (the planned structures in exports/qgis/corridor_drawings.gpkg) are not used by the simulation yet;
when an "after it is built" scenario is added, the conversion from those shapes to SUMO network edits belongs here too.
"""
import json, os, sys
from common import P

SRC = os.environ.get('PIPELINE_EXPORTS', os.path.join(P(), '..', 'corridor_pdf_pipeline', 'exports'))
od_path = os.path.join(SRC, 'od', 'od_summary.json')
if not os.path.exists(od_path): sys.exit(f'missing {od_path} - run `python main.py --only od,export` in the pipeline repo')
od = json.load(open(od_path))
v = od['vehicles_per_day']
mix = {'two_wheeler': v['Two Wheelers'], 'car': v['Cars/ Jeeps'], 'van_maxicab': v['Pickup Vans/ Maxicabs'], 'auto': v['Passenger Auto'],
       'goods_auto': v['Goods Auto'], 'lcv': v['LCVs'], 'truck': v['2-Axle Trucks'] + v['3-Axle Trucks'] + v['MAVs']}
total = od['vehicles_per_day_total']
share = round((od['tollable_vehicles_per_day'] / total + od['diverted_vehicles_per_day'] / total) / 2, 2)

cfg_path = P('config', 'assumptions.json')
cfg = json.load(open(cfg_path))
changes = []
for k, val in mix.items():
    if cfg['vehicle_mix'].get(k) != val: changes.append((f'vehicle_mix.{k}', cfg['vehicle_mix'].get(k), val)); cfg['vehicle_mix'][k] = val
if cfg['flyover_opened'].get('divert_share') != share:
    changes.append(('flyover_opened.divert_share', cfg['flyover_opened'].get('divert_share'), share)); cfg['flyover_opened']['divert_share'] = share
print(f"pipeline OD summary: {od['source']}, {od['year']}; {total:,} vehicles a day; diverting {od['tollable_vehicles_per_day']:,}-{od['diverted_vehicles_per_day']:,}")
if not changes: print('settings already match the pipeline'); sys.exit(0)
for k, old, new in changes: print(f'  {k}: {old} -> {new}')
if '--write' in sys.argv:
    json.dump(cfg, open(cfg_path, 'w'), indent=2, ensure_ascii=False); open(cfg_path, 'a').write('\n')
    print('written to config/assumptions.json; rebuild with `python run.py --from demand`')
else:
    print('run with --write to apply')
