# How the SUMO model was built

A traffic and pedestrian simulation of a ~2 km triangle of roads in Bengaluru (the "Madiwala loop", junctions A, B, C),
for the 8–9 am peak. Three scenarios run on identical demand: `baseline` (today), `trial_crossings` (8 extra signalised
pedestrian crossings) and `flyover_opened` (the crossings, with ~half the through traffic moved onto a new flyover).
Everything is rebuilt from scratch by `python run.py`. Setup is in the [README](README.md).

## Terms you'll meet

| Term | Meaning |
|---|---|
| Carriageway | One direction of a road. The loop roads are *divided*: two one-way carriageways with a median between them. |
| Mid-block crossing | A pedestrian crossing between junctions, not at one. The thing being tested. |
| Chainage | Distance in metres along a road from its first junction. Crossing positions are given this way. |
| OD (origin–destination) | Where trips start and end. Demand is defined as vehicles/hour between gateways at the network edge. |
| Peak hour | 8–9 am. The simulation starts at 7:30 so the network fills up first (warm-up). |
| GTFS | Standard public-transit timetable format. Used for the real BMTC bus trips. |

## SUMO in five pieces

| Piece | File | Made by |
|---|---|---|
| Network: edges (road segments), lanes, junctions, signals, footpaths, crossings | `*.net.xml` | `netconvert` from OpenStreetMap |
| Demand: vehicles, buses, people and their trips | `*.rou.xml` | our Python (`make_demand.py`) |
| Additionals: bus stops, signal programmes, detectors | `*.add.xml` | our Python |
| Run | — | `sumo` (headless) or `sumo-gui` (`view.py`) |
| Outputs: per-trip and per-edge statistics | `out/<scenario>/*.xml` | SUMO, parsed by `metrics.py` |

SUMO ships as a pip package (`eclipse-sumo`); `sumolib` (bundled) reads networks in Python. We don't use TraCI (live control).

## Pipeline

| Step | Script | Notes |
|---|---|---|
| 0 | `prep_gtfs.py` | Cuts the 450 MB BMTC feed down to buses crossing the area 7:15–9:30 → `inputs/gtfs_peak.json` (committed). |
| 1 | `build_net.py` | Two `netconvert` passes: OSM → network (left-hand traffic, urban speeds, footpaths), then signals at A, B, C joined into one controller each. |
| 2 | `make_scenarios.py` | Builds the trial network: splits both carriageways at each crossing position, joins the two split points into one junction, adds a crossing and a 75 s signal plan. |
| 3 | `make_demand.py` | Writes a scenario-independent demand spec in lon/lat once (seeded), then maps it onto each network. |
| 4 | `run_sim.py` | Runs each scenario with the sublane model (two-wheelers filter between cars) and pedestrian "striping" model. |
| 5–6 | `metrics.py`, `report.py` | CSVs, charts, `report/REPORT.md`, `results.geojson`. |

All assumed numbers (volumes, signal timings, pedestrian rates) are in `config/assumptions.json`.

## Things that bit us (read before changing anything)

- **Signals at A.** OSM didn't tag junction A as signalised. Signal nodes are now picked geometrically (main-road nodes near each junction). Passing an *already* signalised node to `--tls.set` crashes `netconvert`, so those are skipped.
- **Missing footpaths.** `netconvert` only guesses sidewalks on roads ≤ 50 km/h; Hosur Road is tagged 60. Raised the threshold.
- **Splitting edges drops crossings.** When a carriageway is split, the piece next to a junction gets a new id (`E` → `E.300`) and `netconvert` silently deletes junction crossings that referenced `E`. `make_scenarios.py` re-declares them and fails if the trial network has fewer crossings than the baseline.
- **Edge ids differ between scenarios.** That's why demand is specified in lon/lat and mapped per network, and why metrics expand each baseline edge to its split pieces so every scenario is measured over the same stretch.
- **Gateways.** Trips enter/leave at hand-picked lon/lat anchors at the network boundary. Tavarekere Road is one-way in OSM, so it's exit-only.
- **Bus stops.** Stops placed at the very end of an edge, or on a lane with no onward connection, made buses stuck and "teleport" (SUMO's way of clearing a jam). Stops now end ≥ 50 m before the edge end, on a lane that connects onward.
- **Oversaturation.** The assumed volumes exceed capacity, so thousands of vehicles never enter. Vehicle delay includes waiting to enter (`departDelay`); treat vehicle results as unreliable until volumes are calibrated.

## Sanity checks to watch

`out/<scenario>/stats.xml`: teleports and collisions should stay low (currently ~40–160 teleports per run).
`out/checks/`: `network_checks.txt` (signals and footpaths), `trial_crossings.csv` (each crossing got vehicle and pedestrian links).

## Common changes

- **Different volumes or timings:** edit `config/assumptions.json`, then `python run.py --from demand`.
- **Move or add trial crossings:** edit `trial_crossings` in the same file (metres along each road), then `python run.py --from scenarios`.
- **New scenario:** add its name to `SCENARIOS` in `scripts/common.py`, build its network in `make_scenarios.py`, and adjust demand in `make_demand.py` if it changes traffic.
- **Watch it:** `python view.py trial_crossings`.

## Run options

```sh
./.venv/bin/python run.py                              # everything (~15 min)
./.venv/bin/python run.py --from demand                # after editing config/assumptions.json (keeps the networks)
./.venv/bin/python run.py --from sim --scenarios baseline
./.venv/bin/python run.py --gtfs /path/to/bmtc-gtfs    # re-extract buses from a newer GTFS feed
```
GTFS: <https://github.com/Vonter/bmtc-gtfs> (unzip `gtfs/bmtc.zip`). Only needed to refresh `inputs/gtfs_peak.json`.

## Key assumptions

All in `config/assumptions.json`, each tagged ASSUMED or DATA.

- **Vehicle flows** between five gateways (Hosur Rd north/south, Sarjapura Rd east, 100 Ft/Inner Ring Rd north-east,
  Tavarekere Rd west, exit only) plus 400 veh/h local trips. Only the 100 Ft Rd corridor (~1,150 veh/h per direction)
  comes from data. Vehicle mix (43% two-wheelers, 29% cars, 13% autos …) is from the OD study.
- **Signals:** fixed time, 120 s cycles at A, B, C (generated by netconvert); trial crossings 75 s cycle, 18 s pedestrian green.
- **People:** bus-stop crossings = peak buses × 6 boarding/alighting × 50% crossing; other places 25–60 trips/h by
  type; 600 background walking trips/h. Nobody jaywalks: people cross only where the network has a crossing.
- **Buses:** real Monday trips, 20 s dwell per stop.

## Calibrating with the site walk

| Walk data | Replaces | Compare with |
|---|---|---|
| Pedestrian crossing counts | `pedestrians.*` rates | `out/metrics/crossings_use.csv` |
| Turning counts at A, B, C | `od_peak_veh_per_hour` | `vehicles_per_h` in `report/results.geojson` |
| Signal timings at A, B, C | `signals.junction_*` | queues in `out/metrics/queues.csv` |
| Southbound buses on Hosur Rd | extra trips in `make_demand.py` | — |

## Documents and the QGIS template

The planner documents are Org files exported with Emacs (PDF also needs LaTeX):
```sh
cd doc && emacs --batch -l export.el -f overview-html   # doc/index.html
cd doc && emacs --batch -l export.el -f overview-pdf    # doc/simulation-overview.pdf
```
For GitHub Pages, deploy from `main`, folder `/ (root)`; the overview is then at `/doc/`.

`qgis/make_template.py` builds `qgis/madiwala_proposals.zip`, a QGIS project for planners to draw proposed changes.
It needs QGIS installed and runs with the system Python (PyQGIS), not the venv. It reads the study website's `data/`
folder, by default `../corridor_design_challenge/data`:
```sh
python3 qgis/make_template.py [path/to/website/data]
```
