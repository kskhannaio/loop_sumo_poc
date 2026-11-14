# Madiwala loop — SUMO simulation

Traffic + pedestrian simulation of the Madiwala loop (Bengaluru): **100 Feet Road (A–B), Hosur Road (B–C),
Sarjapura Road (C–A)**, for the weekday morning peak. It compares three scenarios on identical, seeded demand:

| Scenario | What changes |
|---|---|
| `baseline` | Today: people can cross only at junction crossings (signalised at A, B, C; unsignalised at side-street mouths) |
| `trial_crossings` | 8 signalised mid-block crossings at the study's proposed positions |
| `flyover_opened` | Trial crossings + ~53% of corridor traffic moved to the elevated road (OD/toll study) |

Results: `report/REPORT.md` (tables + charts), `out/metrics/*.csv`, and `report/results.geojson` (per-edge
speed/delay/volume and the crossing points, ready for the website).

## Setup (once)
```sh
cd ~/design_challenge/src/sumo_poc
python3 -m venv .venv
./.venv/bin/pip install eclipse-sumo pyproj matplotlib rtree
```
`eclipse-sumo` ships SUMO itself (netconvert, sumo, sumo-gui); no system install needed.

## Run
```sh
./.venv/bin/python run.py                         # everything: network -> scenarios -> demand -> runs -> metrics -> report
./.venv/bin/python run.py --from demand           # after editing config/assumptions.json (keeps the networks)
./.venv/bin/python run.py --from sim --scenarios baseline
./.venv/bin/python run.py --gtfs /path/to/bmtc-gtfs   # re-extract bus trips from a newer GTFS feed
```
A full run takes roughly 15–25 minutes (three 1¾-hour simulations with the sublane model).

To watch a scenario: `./.venv/bin/python view.py [baseline|trial_crossings|flyover_opened]` — opens sumo-gui with
`config/gui-settings.xml` (light background, grey roads, pale footpaths; two-wheelers orange, cars blue, autos green,
goods/trucks brown, buses red, people magenta). If an old view sticks, pick "madiwala" in the viewer's colour-scheme dropdown.

## Pipeline (scripts/)
| Step | Script | Does |
|---|---|---|
| 0 | `prep_gtfs.py` | Extracts the bus trips crossing the area in the simulated window from the BMTC GTFS into `inputs/gtfs_peak.json` (run only when the feed changes) |
| 1 | `build_net.py` | OSM (`osm/loop.osm.xml`) → `net/base.net.xml`: left-hand traffic, layer-separated underpass/flyover, urban speeds (`net/urban_speeds.typ.xml`), sidewalks and junction crossings guessed (incl. 60 km/h Hosur Rd), signals at A, B, C selected geometrically and joined per junction, fixed-time plans. Writes `out/checks/network_checks.txt` |
| 2 | `make_scenarios.py` | Splits both carriageways at each trial site, joins the split nodes into one junction, guesses the crossing, signalises it and imposes a fixed pedestrian plan (`net/trial_tls.add.xml`). Positions in `out/checks/trial_crossings.csv` |
| 3 | `make_demand.py` | Scenario-independent demand spec in lon/lat (`demand/spec.json`), mapped onto each network: OD vehicle flows, local trips, GTFS buses with stops, people crossing to places and bus stops, background walking. `demand/person_meta.csv` lists every person |
| 4 | `run_sim.py` | Runs SUMO per scenario → `out/<scenario>/` (tripinfo, stats, edge data incl. people on crossings, queue detectors on every approach to A/B/C and trial signals) |
| 5 | `metrics.py` | 08:00–09:00 metrics → `out/metrics/` |
| 6 | `report.py` | `report/REPORT.md`, `people.png`, `vehicles.png`, `queues.png`, `map.png`, `results.geojson` |

## Folders
```
config/assumptions.json   every assumed number, tagged ASSUMED / DATA
inputs/                   copies of the study data (stretch, crossings, bus stops) + gtfs_peak.json
osm/                      OSM extract + Overpass query
net/                      netconvert configs, generated networks
demand/                   generated demand per scenario
out/                      simulation outputs, checks, metrics
report/                   REPORT.md, charts, results.geojson
```

## Data sources
- Roads, signals: © OpenStreetMap contributors (ODbL).
- Study geometry (loop sides, trial positions, places people cross to reach, bus stops): copied read-only from the website repo `data/`.
- Buses: unofficial BMTC GTFS by Vonter, built from the Namma BMTC 2.0 app (ODbL); Monday service.
- Vehicle mix and flyover diversion: B-SMILE OD & toll analysis (Indiranagar–Silk Board corridor).

## Assumptions
All live in `config/assumptions.json`; the key ones:
- **Vehicle flows** between five gateways (Hosur Rd north/south, Sarjapura Rd east, 100 Ft/Inner Ring Rd north-east,
  Tavarekere Main Rd west — exit only, it is one-way in OSM) plus 400 veh/h local trips. Only the 100 Ft Rd corridor
  (~1,150 veh/h per direction) is derived from data; the rest are plausible guesses.
- **Signals**: fixed time, 120 s cycles at A, B, C (netconvert-generated phases); trial crossings 75 s cycle, 18 s pedestrian green.
- **People**: bus-stop crossings = 8–9 am buses × 6 boarding/alighting × 50% crossing; other places 25–60 trips/h by type;
  600 background walking trips/h.
- **Buses**: real trips, 20 s dwell at each stop.
- **Southern Hosur Rd**: the OSM extract ends where southbound Hosur Rd meets Madiwala–Sarjapura Rd; that edge is the exit.

## Calibrating with the site walk
| Walk data | Replaces in `config/assumptions.json` |
|---|---|
| Crossing counts P1–P6 (form §7) | `pedestrians.crossing_trips_per_hour_by_type` and `pedestrians.share_of_bus_pax_crossing_the_road` — compare with `out/metrics/crossings_use.csv` |
| Turning counts at A, B, C (add to the form) | `od_peak_veh_per_hour` — compare with `vehicles_per_h` in `report/results.geojson` |
| Signal cycle and greens at A, B, C (add to the form) | `signals.junction_*`, or a measured tlLogic file added in `run_sim.py` |
| Southbound buses on Hosur Rd | extra bus trips in `make_demand.py` if they exist |
| Footpath widths / blockages | sidewalk lanes in the network |

## Limits
- No jaywalking: people only cross at modelled crossings; real mid-block crossing through traffic gaps is not represented.
- Volumes and signal timings are uncalibrated; read results as scenario differences, not forecasts.
- One seed per scenario; vary `time.seed` and re-run before trusting small differences.
