"""Step 6 - report: report/REPORT.md, charts (PNG) and report/results.geojson."""
import json, math, os, shutil
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from common import P, SCENARIOS, SIDES, SIDE_NAME, JUNCTIONS, cfg, read_net

C = cfg()
os.makedirs(P('report'), exist_ok=True)
M = json.load(open(P('out', 'metrics', 'metrics.json')))
scns = [s for s in SCENARIOS if any(r['scenario'] == s for r in M['summary'])]
LABEL = {'baseline': 'Today', 'trial_crossings': 'Trial crossings', 'flyover_opened': 'Trial + flyover open'}
COL = {'baseline': '#868e96', 'trial_crossings': '#1c7ed6', 'flyover_opened': '#2f9e44'}
for k, v in C.get('proposals', {}).items():                  # drawn proposals (make_proposal.py)
    if not k.startswith('_'): LABEL[k] = v.get('label', k); COL[k] = '#e8590c'
S = {r['scenario']: r for r in M['summary']}
get = lambda rows, **kw: next((r for r in rows if all(r.get(k) == v for k, v in kw.items())), None)

def bars(ax, groups, value, title, ylabel):
    w = 0.8 / len(scns)
    for i, s in enumerate(scns):
        ys = [value(s, g) for g in groups]
        ax.bar([k + i * w for k in range(len(groups))], [y if y is not None else 0 for y in ys], w, label=LABEL[s], color=COL[s])
    ax.set_xticks([k + w * (len(scns) - 1) / 2 for k in range(len(groups))])
    ax.set_title(title, fontsize=11); ax.set_ylabel(ylabel); ax.spines[['top', 'right']].set_visible(False)

# ---- people
fig, axs = plt.subplots(1, 2, figsize=(11, 4))
bars(axs[0], SIDES, lambda s, g: (get(M['people'], scenario=s, side=g) or {}).get('trip_time_mean_s'), 'Time to cross and reach the place', 'seconds (mean)')
bars(axs[1], SIDES, lambda s, g: (get(M['people'], scenario=s, side=g) or {}).get('extra_walk_m_mean'), 'Extra walking to find a crossing', 'metres (mean)')
for ax in axs: ax.set_xticklabels([SIDE_NAME[g] for g in SIDES])
axs[0].legend(frameon=False, fontsize=9); fig.tight_layout(); fig.savefig(P('report', 'people.png'), dpi=130); plt.close(fig)

# ---- vehicles
dirs = [(r['side'], r['direction']) for r in M['vehicles'] if r['scenario'] == 'baseline']
fig, ax = plt.subplots(figsize=(11, 4))
bars(ax, dirs, lambda s, g: (get(M['vehicles'], scenario=s, side=g[0], direction=g[1]) or {}).get('travel_time_s'),
     f"Vehicle travel time along each loop road, {C['time']['metrics_begin']}-{C['time']['metrics_end']}", 'seconds')
ax.set_xticklabels([f"{SIDE_NAME[sd]}\n{d.replace('>', ' to ')}" for sd, d in dirs], fontsize=8)
ax.legend(frameon=False, fontsize=9); fig.tight_layout(); fig.savefig(P('report', 'vehicles.png'), dpi=130); plt.close(fig)

# ---- queues
sigs = sorted({r['signal'] for r in M['queues']}, key=lambda x: (len(x), x))
fig, ax = plt.subplots(figsize=(11, 3.6))
bars(ax, sigs, lambda s, g: (get(M['queues'], scenario=s, signal=g) or {}).get('max_queue_m'), 'Longest queue on any approach lane', 'metres')
ax.set_xticklabels(sigs); ax.legend(frameon=False, fontsize=9); fig.tight_layout(); fig.savefig(P('report', 'queues.png'), dpi=130); plt.close(fig)

# ---- map: loop roads coloured by speed, per scenario
geo = json.load(open(P('out', 'metrics', 'results.geojson')))
base = read_net(P('net', 'baseline.net.xml'))
fig, axs = plt.subplots(1, len(scns), figsize=(5.2 * len(scns), 5.2))
cmap = plt.get_cmap('RdYlGn')
for ax, s in zip(axs if len(scns) > 1 else [axs], scns):
    for e in base.getEdges():
        if e.allows('passenger'):
            xs, ys = zip(*[base.convertXY2LonLat(*p) for p in e.getShape()]); ax.plot(xs, ys, color='#dee2e6', lw=0.8, zorder=1)
    for f in geo['features']:
        p = f['properties']
        if p.get('scenario') != s: continue
        if f['geometry']['type'] == 'LineString' and p.get('speed_kmh') is not None:
            xs, ys = zip(*f['geometry']['coordinates'])
            ax.plot(xs, ys, color=cmap(min(1, p['speed_kmh'] / 40)), lw=3.2, zorder=2, solid_capstyle='round')
    for f in geo['features']:
        if f['properties'].get('kind') == 'trial_crossing' and s != 'baseline':
            ax.plot(*f['geometry']['coordinates'], marker='s', ms=7, color='#7048e8', zorder=4)
    for j, (lon, lat) in JUNCTIONS.items():
        ax.plot(lon, lat, 'o', ms=13, color='black', zorder=5); ax.text(lon, lat, j, color='white', ha='center', va='center', fontsize=8, zorder=6)
    ax.set_title(LABEL[s], fontsize=11); ax.set_aspect(1 / math.cos(math.radians(12.927))); ax.axis('off')
    ax.set_xlim(77.6125, 77.6235); ax.set_ylim(12.9225, 12.9320)
sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(0, 40)); sm.set_array([])
fig.colorbar(sm, ax=axs, shrink=0.6, label='mean vehicle speed on loop roads, km/h (purple squares = trial crossings)')
fig.savefig(P('report', 'map.png'), dpi=130, bbox_inches='tight'); plt.close(fig)
shutil.copy(P('out', 'metrics', 'results.geojson'), P('report', 'results.geojson'))

# ---- markdown
def tbl(rows, cols, heads):
    out = ['| ' + ' | '.join(heads) + ' |', '|' + '---|' * len(heads)]
    for r in rows: out.append('| ' + ' | '.join(str(r.get(c, '')) for c in cols) + ' |')
    return '\n'.join(out)
def delta(s, key, base='baseline'):
    a, b = S.get(base, {}).get(key), S.get(s, {}).get(key)
    if a in (None, '') or b in (None, ''): return ''
    return f"{b} ({'+' if b - a >= 0 else ''}{b - a:.1f})"

od = {k: v for k, v in C['od_peak_veh_per_hour'].items() if not k.startswith('_')}
pd = C['pedestrians']
md = f"""# Madiwala loop — SUMO traffic and pedestrian simulation

Weekday morning peak (metrics for trips starting {C['time']['metrics_begin']}–{C['time']['metrics_end']}; simulated {C['time']['sim_begin']}–{C['time']['sim_end']} with warm-up),
same seeded demand in every scenario so differences come from the street changes.

**Read this first.** Road layout, signals, bus routes and bus times come from data (OpenStreetMap, BMTC GTFS). Traffic
volumes, pedestrian volumes and signal timings are **assumptions** until the site walk and counts replace them
(`config/assumptions.json`). Treat the numbers as a comparison between scenarios, not a forecast.

## Scenarios
- **Today (baseline)** — people can cross only where netconvert finds junction crossings (signalised at A, B, C; unsignalised at side-street mouths).
- **Trial crossings** — 8 signalised mid-block crossings ({', '.join(f"{SIDE_NAME[s]}: {', '.join(str(d) for d in C['trial_crossings'][s])} m" for s in SIDES)} from each road's first junction), {C['signals']['midblock_cycle_s']} s cycle with {C['signals']['midblock_ped_green_s']} s pedestrian green.
- **Trial + flyover open** — as above, with {round(C['flyover_opened']['divert_share'] * 100)}% of corridor traffic ({', '.join(C['flyover_opened']['applies_to'])}) moved onto the elevated road.

## Headline results

{tbl([{**S[s], 'name': LABEL[s],
       'ped': delta(s, 'ped_trip_time_mean_s'), 'extra': delta(s, 'ped_extra_walk_m_mean'), 'lost': delta(s, 'ped_time_lost_mean_s'),
       'vd': delta(s, 'veh_delay_mean_s'), 'bd': delta(s, 'bus_delay_mean_s')} for s in scns],
     ['name', 'people_crossing_trips', 'ped', 'extra', 'lost', 'vd', 'bd', 'vehicles_not_inserted', 'teleports', 'collisions'],
     ['Scenario', 'People crossing (trips)', 'Crossing trip time, s (Δ vs today)', 'Extra walk, m (Δ)', 'Time lost walking, s (Δ)',
      'Vehicle delay per trip incl. waiting to enter, s (Δ)', 'Bus delay per trip, s (Δ)', 'Vehicles never let in', 'Teleports', 'Collisions'])}

*Vehicles never let in* = demand that could not enter the network before the simulation ended — a sign the assumed volumes exceed what the entries and signals can carry (Madiwala is congested at peak, but the volumes are uncalibrated).

![people](people.png)

### People crossing each road
{tbl([{**r, 'scenario': LABEL[r['scenario']]} for r in M['people']],
     ['scenario', 'road', 'people', 'trip_time_mean_s', 'trip_time_p85_s', 'time_lost_mean_s', 'walk_m_mean', 'straight_m_mean', 'extra_walk_m_mean', 'detour_factor_median'],
     ['Scenario', 'Road', 'Trips', 'Trip time mean s', 'p85 s', 'Time lost s', 'Walked m', 'Straight-line m', 'Extra m', 'Detour factor (median)'])}

### Vehicles along each loop road
![vehicles](vehicles.png)

{tbl([{**r, 'scenario': LABEL[r['scenario']]} for r in M['vehicles']],
     ['scenario', 'road', 'direction', 'length_m', 'travel_time_s', 'free_flow_s', 'delay_s', 'avg_speed_kmh', 'vehicles_per_h'],
     ['Scenario', 'Road', 'Direction', 'Length m', 'Travel time s', 'Free-flow s', 'Delay s', 'Avg speed km/h', 'Vehicles/h (max edge)'])}

### Queues at signals
![queues](queues.png)

{tbl([{**r, 'scenario': LABEL[r['scenario']]} for r in M['queues']],
     ['scenario', 'signal', 'approach_lanes', 'mean_queue_m_worst_lane', 'max_queue_m'],
     ['Scenario', 'Signal (A/B/C, X0-X7 = trial crossings)', 'Approach lanes', 'Mean queue, worst lane m', 'Max queue m'])}

Queue detectors cover the last 150 m of each approach lane, so 150 m means "the queue reaches past the detector".

### Crossing use (people per hour)
{tbl([{**r, 'scenario': LABEL[r['scenario']]} for r in M['crossings']], ['scenario', 'crossing', 'people_per_h'], ['Scenario', 'Crossing', 'People/h'])}

### Buses
{tbl([{**r, 'scenario': LABEL[r['scenario']]} for r in M['buses']], ['scenario', 'buses', 'trip_time_mean_s', 'delay_mean_s', 'delay_p85_s'],
     ['Scenario', 'Buses (finished)', 'Trip time in area s', 'Delay mean s', 'Delay p85 s'])}

### Map
![map](map.png)

`results.geojson` holds per-edge speed / delay / volume for each loop road and scenario, plus the trial crossing points, ready for the website.

## Assumptions (all in `config/assumptions.json`)
| Item | Value | Status |
|---|---|---|
| Peak-hour vehicle flows between gateways | {', '.join(f'{k} {v}' for k, v in od.items())} veh/h | ASSUMED (the 1,150 each way on the 100 Feet Road–Hosur Road south movement borrows a count taken between Indiranagar and Domlur, about 6 km north; nothing is counted on the loop) |
| Vehicle mix | 2W {C['vehicle_mix']['two_wheeler']}, car {C['vehicle_mix']['car']}, van {C['vehicle_mix']['van_maxicab']}, auto {C['vehicle_mix']['auto']}, goods auto {C['vehicle_mix']['goods_auto']}, LCV {C['vehicle_mix']['lcv']}, truck {C['vehicle_mix']['truck']} (relative) | DATA, but counted between Indiranagar and Domlur, not on the loop |
| Buses | real Monday trips from BMTC GTFS, dwell {C['buses']['dwell_s']} s | DATA + ASSUMED dwell |
| Signals A, B, C | fixed time, {C['signals']['junction_cycle_s']} s cycle, programmes generated by netconvert | ASSUMED |
| Trial crossings | {C['signals']['midblock_cycle_s']} s cycle, {C['signals']['midblock_ped_green_s']} s pedestrian green | proposal |
| People crossing | bus stops: buses in the simulated hour × {pd['pax_per_bus_board_alight']} pax × {pd['share_of_bus_pax_crossing_the_road']} crossing; places: {', '.join(f'{k} {v}/h' for k, v in pd['crossing_trips_per_hour_by_type'].items() if v)}; origins {pd['origin_offset_m'][0]}…{pd['origin_offset_m'][1]} m along the far footpath | ASSUMED |
| Background walking | {pd['background_walk_trips_per_hour']} trips/h, 150–600 m | ASSUMED |
| Flyover diversion | {round(C['flyover_opened']['divert_share'] * 100)}% of corridor ODs | DATA-derived (OD/toll study, 45–62%) |
| Speeds | 50 km/h main roads, 40 km/h 100 Ft Rd, 30 km/h side streets, OSM maxspeed where tagged | ASSUMED / OSM |

## Limits — what this model cannot tell you
- **No jaywalking.** Simulated people only cross where the network has a crossing (junctions, side-street mouths, trial crossings). In reality people cross anywhere through gaps, so "today" understates how many people cross mid-block — and overstates their detours. The trial-crossing benefit is best read as *time and distance saved for people who use a crossing*.
- **Uncalibrated volumes.** Flows are plausible guesses; queues and delays scale with them. Calibrate before quoting absolute numbers.
- **Network cut at the edges.** The OSM extract ends close to the loop; the southern Hosur Rd exit is where southbound Hosur Rd meets Madiwala–Sarjapura Rd, and Tavarekere Main Rd is exit-only (one-way in OSM).
- **Signals** are netconvert-generated fixed-time plans, not the real phasing.
- **Two-wheeler behaviour** uses SUMO's sublane model (filtering between cars); Indian lane-free driving is only approximated.
- **Bus data** comes from the BMTC app, which has known timetable errors; it shows no southbound buses on Hosur Rd between C and B.
- Results are one seeded run per scenario; run several seeds before relying on small differences.

## Calibrating with the site walk
| Walk data (form section) | Replaces | Where |
|---|---|---|
| Crossing counts P1–P6 (§7) | `pedestrians.crossing_trips_per_hour_by_type` and the bus-stop share | scale rates so simulated crossings near each P-spot match the counts; check against `out/metrics/crossings_use.csv` |
| Turning counts at A, B, C (to add to the form) | `od_peak_veh_per_hour` | adjust OD flows until simulated edge counts (`results.geojson` `vehicles_per_h`) match |
| Signal cycle and green times at A, B, C (to add) | `signals.junction_*` | or write measured programmes into a tlLogic additional file |
| Bus direction check on Hosur Rd | GTFS assumption | if southbound buses exist, add them as extra trips |
| Footpath widths / blockages (§1) | — | narrow or remove sidewalk lanes in `net/` to test walkability |

Rebuild everything with `python run.py` after editing the config.
"""
open(P('report', 'REPORT.md'), 'w').write(md)
print('wrote report/REPORT.md + people.png vehicles.png queues.png map.png results.geojson')

import network_figures
network_figures.main()
