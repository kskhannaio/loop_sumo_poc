# How the SUMO model was built

A traffic and pedestrian simulation of a ~2 km triangle of roads in Bengaluru (the "Madiwala loop", junctions A, B, C),
for the 9:30–10:30 am peak. Scenarios run on identical demand: `baseline` (today), `trial_crossings` (8 extra signalised
pedestrian crossings), `flyover_opened` (the crossings, with ~half the through traffic moved onto a new flyover), and any
proposal drawn on the website (see the end of this page).
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
| 0 | `prep_gtfs.py` | Cuts the 450 MB BMTC feed down to buses crossing the area during the simulated time, plus 15 minutes either side → `inputs/gtfs_peak.json` (committed). Re-run after changing `time`. |
| 1 | `build_net.py` | Patches the OSM extract (config `network`: lane counts, entrance length, foot over bridges), then two `netconvert` passes: OSM → network (left-hand traffic, urban speeds, footpaths), then signals at A, B, C joined into one controller each. |
| 2 | `make_scenarios.py` | Builds the trial network: splits both carriageways at each crossing position, joins the two split points into one junction, adds a crossing and a 75 s signal plan (shared code in `netpatch.py`). |
| 2b | `make_proposal.py` | Turns each proposal drawn on the website's Draw tab (config `proposals`) into a scenario on today's network. Says how every drawn feature was applied in `out/checks/<scenario>.txt`. |
| 3 | `make_demand.py` | Writes a scenario-independent demand spec in lon/lat once (seeded), then maps it onto each network. |
| 4 | `run_sim.py` | Runs each scenario with the sublane model (two-wheelers filter between cars) and pedestrian "striping" model. |
| 5–6 | `metrics.py`, `report.py` | CSVs, charts, `report/REPORT.md`, `results.geojson`. `junction_throughput.csv` counts vehicles leaving each junction, 40 m down every exit, so traffic using a drawn slip road still counts. |
| – | `seeds.py`, `run_queue.sh`, `compare.py` | Runs with different random seeds (`out/seeds/`; `run_queue.sh jobs.txt` runs many, 11 at a time), and a paired comparison of two scenarios over the same seeds. |
| – | `clip.py`, `follow.py`, `wait_heat.py`, `walk_reach.py` | Pictures and videos on satellite imagery: side-by-side clips (`--hour` for 9:30–10:30 at 60x), one person followed through both scenarios, where people wait, and how far you can walk in five minutes. |

All assumed numbers (volumes, signal timings, pedestrian rates) are in `config/assumptions.json`.

## Things that bit us (read before changing anything)

- **Signals at A.** OSM didn't tag junction A as signalised. Signal nodes are now picked geometrically (main-road nodes near each junction). Passing an *already* signalised node to `--tls.set` crashes `netconvert`, so those are skipped.
- **Missing footpaths.** `netconvert` only guesses sidewalks on roads ≤ 50 km/h; Hosur Road is tagged 60. Raised the threshold.
- **Splitting edges drops crossings.** When a carriageway is split, the piece next to a junction gets a new id (`E` → `E.300`) and `netconvert` silently deletes junction crossings that referenced `E`. `make_scenarios.py` re-declares them and fails if the trial network has fewer crossings than the baseline.
- **Edge ids differ between scenarios.** That's why demand is specified in lon/lat and mapped per network, and why metrics expand each baseline edge to its split pieces so every scenario is measured over the same stretch.
- **Gateways.** Trips enter/leave at hand-picked lon/lat anchors at the network boundary. Tavarekere Road is one-way in OSM, so it's exit-only.
- **Bus stops.** Stops placed at the very end of an edge, or on a lane with no onward connection, made buses stuck and "teleport" (SUMO's way of clearing a jam). Stops now end ≥ 50 m before the edge end, on a lane that connects onward.
- **Entrances.** The Hosur Road south entrance was a 33 m edge, so any queue blocked every vehicle entering there. It is now
  extended 400 m (`network.entrance_extensions`). A gateway's entry edge is the one its anchor lies on; picking the edge
  whose start is merely nearest fed Hosur Road traffic in on the road next door.
- **Slip roads at B.** The two turns between 100 Feet Road and Hosur Road south are single-lane links in OSM, but carry the
  corridor's main flow. They are assumed to be 2 lanes (`network.lane_overrides`); confirm on the walk.
- **Signals.** Fixed 120 s plans starved the busy approaches (C gave Hosur Road northbound 44 s). Junction signals are now
  `actuated`, so green follows the queues (`signals.junction_type`).
- **0.2 m approach edges.** OSM has a node a few metres before junctions A and C, which netconvert turns into an approach
  edge 0.2 m long. An actuated signal puts its sensor on that edge, sees nothing and cuts every green to the minimum
  (C passed 325 veh/h). `build_net.py` merges such edges into the junction before the signals are built; the join needs
  explicit x/y or netconvert leaves the merged node unplaced, and `--crossings.guess` to rebuild its crossings.
- **Turns across oncoming traffic starve.** On Hosur Road northbound at C the median lane was shared between straight on
  and the right turn, which netconvert makes permissive. No gaps ever came, and the single-file queue ran 800 m back
  through the underpass while three lanes stood empty. `signals.turn_only_median_lane_at` makes that lane turn-only with
  a protected green (`--tls.rebuild`). Applying it at A as well made netconvert split A into three 32 s phases and
  jammed Sarjapura Road, so it is on at C only. A workaround for lane logic, not a claim about the street.
- **Seeing a jam without a screen.** `scripts/snapshot.py` draws a still from `sumo --fcd-output`; tables did not show
  the single-file queue, the picture did at once.
- **Which junctions have signals** is `signals.signalised_junctions`. B is off, following the tender's route map; without a
  signal the turn from 100 Feet Road cannot merge into Hosur Road southbound. Unresolved.
- **Foot over bridges.** OSM maps the bridges and their stairs but does not join them to the roads, so netconvert drops them.
  `build_net.py` adds `osm/footbridges.osm.xml` and joins each stair foot to the nearest main carriageway with a short footway.
  Stairs get a slow walking speed (`network.foot_over_bridges`). `metrics.py` reports people using each bridge as `FOB <road>@<m>`.
- **Oversaturation.** The assumed volumes exceed capacity, so thousands of vehicles never enter. Vehicle delay includes waiting to enter (`departDelay`); treat vehicle results as unreliable until volumes are calibrated.

## Sanity checks to watch

`out/<scenario>/stats.xml`: teleports and collisions should stay low (currently ~40–160 teleports per run).
`out/checks/`: `network_checks.txt` (signals and footpaths), `trial_crossings.csv` (each crossing got vehicle and pedestrian links).

## Common changes

- **Different volumes or timings:** edit `config/assumptions.json`, then `python run.py --from demand`.
- **Move or add trial crossings:** edit `trial_crossings` in the same file (metres along each road), then `python run.py --from scenarios`.
- **New scenario:** for a drawn proposal, see the end of this page. Otherwise add its name to `SCENARIOS` in `scripts/common.py`, build its network in `make_scenarios.py`, and adjust demand in `make_demand.py` if it changes traffic.
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
- **Signals:** A, B and C follow the queues (actuated, 8–60 s greens); trial crossings fixed, 75 s cycle, 18 s pedestrian green.
- **People:** bus-stop crossings = peak buses × 6 boarding/alighting × 50% crossing; other places 25–60 trips/h by
  type; 600 background walking trips/h. Nobody jaywalks: people cross only at a crossing or over a foot bridge.
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

### Flyover contract template (separate)

`qgis/make_contract_template.py` builds `qgis/madiwala_contract.zip`: the planner template plus everything on the
B-SMILE tender's 17 drawing sheets, from the loop south to Bommanahalli. It copies the base template and leaves
`make_template.py` unchanged. The drawing data comes from the **PDF pipeline repo** (`../corridor_pdf_pipeline`),
which places the sheets on the map, traces and names the structures:

```sh
(cd ../corridor_pdf_pipeline && ./.venv/bin/python main.py)   # extract from the PDFs (about 15 min first time)
python3 qgis/make_template.py                                # base template (if not built)
python3 qgis/make_contract_template.py                       # reads ../corridor_pdf_pipeline/out
```
The zip is derived from the tender drawings and is not committed.

## Testing a proposal drawn on the website

1. Save the file from the Draw tab into `proposals/`.
2. Add an entry under `proposals` in `config/assumptions.json`: the file, and how to read it. A drawing says where, not
   how, so the entry says what a zebra means (only `signalised` so far), what each zone label does (`closed_to_traffic`,
   `widen_footpath`, `bus_stop`), and the lanes and speed of new roads. Write down any reading agreed with the planner.
3. `python run.py --from proposals --scenarios <name>` builds and runs it once; read `out/checks/<name>.txt` first,
   which lists every drawn feature and what the model did with it (or why it skipped it).
4. `python scripts/seeds.py baseline` and `python scripts/seeds.py <name>`, then `python scripts/compare.py baseline <name>`.
   Vehicle results move by about a quarter between seeds, so only changes that hold in every seed are called gains or losses.

What the reader does with each kind of mark:
- **Zebra / signalised crossing**: at a junction arm that already has a crossing, nothing; mid-block, the same signalised
  crossing as the trial crossings.
- **New road**: a one-way link joining the roads nearest its two ends, in the direction traffic can flow; connected to
  every lane of both roads.
- **New footpath**: a footway between the footpaths of the two nearest roads.
- **Zones**: `closed_to_traffic` turns a road inside the shape into footway only if 15 m or more of it lies inside (smaller
  overlaps are drawing tolerance); `widen_footpath` widens footpaths inside the shape; `bus_stop` moves the nearest existing
  stops on the road beside the shape into it, along the same road, and a shape of 200 m² or more becomes an off-road bay
  where the stopped bus leaves the running lane.

## Behaviour settings worth knowing

- **People who cannot use stairs** (`pedestrians.step_free_share`, 10%): they walk as SUMO's wheelchair class, and
  `make_demand.py` opens every walkway except stairs to that class in each scenario network.
- **Driver route choice** (`vehicles`): at departure only, from recent travel times. Rerouting on the way crashes
  SUMO 1.28 on this network (`std::bad_alloc`) in about half the runs; buses never reroute.
- **Crossing on red** is not modelled. `jmDriveAfterRedTime` on people, or giving crossings a give-way green, both sent
  people into moving traffic in a test junction (vehicle delay 17 s to 91 s, people slower too).

