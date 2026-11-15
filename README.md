# Madiwala loop — SUMO simulation

A traffic and pedestrian simulation of the Madiwala loop in Bengaluru — **100 Feet Road (A–B), Hosur Road (B–C) and
Sarjapura Road (C–A)** — for the weekday 8–9 am peak, built with [SUMO](https://eclipse.dev/sumo/).

It asks: *what changes for people on foot, and for traffic, if signalised crossings are added between the junctions?*
Three scenarios run on identical, seeded demand:

| Scenario | Streets |
|---|---|
| `baseline` | Today: people cross only at junctions and side-street mouths |
| `trial_crossings` | 8 new signalised mid-block crossings at the study's proposed positions |
| `flyover_opened` | The trial crossings, with ~53% of corridor traffic moved onto the new flyover |

## Results so far

| | Today | Trial crossings | + flyover open |
|---|---|---|---|
| Time for people crossing a loop road to reach their destination | 194 s | 123 s | 120 s |
| Extra walking to find a crossing | 156 m | 71 m | 71 m |

Pedestrian results are the robust part. Traffic volumes are still estimates and the network is oversaturated, so
vehicle results are indicative only until the site-walk counts are added. Full results: [`report/REPORT.md`](report/REPORT.md).

## Quick start

```sh
python3 -m venv .venv
./.venv/bin/pip install eclipse-sumo pyproj matplotlib rtree   # SUMO itself comes with eclipse-sumo
./.venv/bin/python run.py                                      # rebuild and run everything (~15 min)
./.venv/bin/python view.py trial_crossings                     # watch a scenario in sumo-gui
```

All assumed numbers (traffic volumes, signal timings, pedestrian rates, crossing positions) are in
[`config/assumptions.json`](config/assumptions.json). Edit it, then `./.venv/bin/python run.py --from demand`.

## Documents

| For | Document |
|---|---|
| Developers | [`HOWTO.md`](HOWTO.md): how it was built, the pipeline, pitfalls, how to change it |
| Planners | [`doc/simulation-overview.org`](doc/simulation-overview.org): plain-language overview (also as `doc/index.html` and PDF) |
| Planners | [`doc/scenario-drawing-proposal.org`](doc/scenario-drawing-proposal.org): proposal for drawing scenarios on a map |
| Planners | `qgis/`: builds a QGIS template for planners to propose changes (see HOWTO) |

## Layout

```
run.py, view.py        run everything / watch a scenario
scripts/               pipeline steps (network, scenarios, demand, simulation, metrics, report)
config/                assumptions.json, sumo-gui colours
inputs/                study data and the BMTC bus extract
osm/, net/             OpenStreetMap extract and network build settings
report/                results: REPORT.md, charts, results.geojson
doc/, qgis/            documents and the planners' QGIS template
```

`demand/`, `out/` and the generated networks are rebuilt by `run.py` and not committed.

## Data and licences

Roads: © OpenStreetMap contributors (ODbL). Buses: unofficial BMTC GTFS by Vonter, from the Namma BMTC 2.0 app (ODbL).
Vehicle mix and flyover diversion: B-SMILE OD & toll analysis. Study geometry: the Madiwala loop study's own data.
