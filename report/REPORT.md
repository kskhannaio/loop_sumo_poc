# Madiwala loop — SUMO traffic and pedestrian simulation

Weekday morning peak (metrics for trips starting 08:00–09:00; simulated 07:30–09:15 with warm-up),
same seeded demand in every scenario so differences come from the street changes.

**Read this first.** Road layout, signals, bus routes and bus times come from data (OpenStreetMap, BMTC GTFS). Traffic
volumes, pedestrian volumes and signal timings are **assumptions** until the site walk and counts replace them
(`config/assumptions.json`). Treat the numbers as a comparison between scenarios, not a forecast.

## Scenarios
- **Today (baseline)** — people can cross only where netconvert finds junction crossings (signalised at A, B, C; unsignalised at side-street mouths).
- **Trial crossings** — 8 signalised mid-block crossings (100 Feet Road: 250, 410 m, Hosur Road: 175, 340, 500 m, Sarjapura Road: 210, 370, 520 m from each road's first junction), 75 s cycle with 18 s pedestrian green.
- **Trial + flyover open** — as above, with 53% of corridor traffic (IRR>HS, HS>IRR, SE>HS, HS>SE) moved onto the elevated road.

## Headline results

| Scenario | People crossing (trips) | Crossing trip time, s (Δ vs today) | Extra walk, m (Δ) | Time lost walking, s (Δ) | Vehicle delay per trip incl. waiting to enter, s (Δ) | Bus delay per trip, s (Δ) | Vehicles never let in | Teleports | Collisions |
|---|---|---|---|---|---|---|---|---|---|
| Today | 2610 | 205.3 (+0.0) | 145.9 (+0.0) | 72.5 (+0.0) | 506.3 (+0.0) | 536.4 (+0.0) | 4160 | 233 | 8 |
| Trial crossings | 2609 | 146.5 (-58.8) | 95.2 (-50.7) | 51.0 (-21.5) | 683.5 (+177.2) | 1008.0 (+471.6) | 2343 | 134 | 25 |
| Trial + flyover open | 2609 | 146.8 (-58.5) | 95.0 (-50.9) | 51.8 (-20.7) | 375.3 (-131.0) | 564.6 (+28.2) | 353 | 74 | 14 |

*Vehicles never let in* = demand that could not enter the network before the simulation ended — a sign the assumed volumes exceed what the entries and signals can carry (Madiwala is congested at peak, but the volumes are uncalibrated).

![people](people.png)

### People crossing each road
| Scenario | Road | Trips | Trip time mean s | p85 s | Time lost s | Walked m | Straight-line m | Extra m | Detour factor (median) |
|---|---|---|---|---|---|---|---|---|---|
| Today | 100 Feet Road | 825 | 103.9 | 164.0 | 49.0 | 75.5 | 33.5 | 42.0 | 1.49 |
| Today | Hosur Road | 994 | 318.1 | 533.5 | 96.0 | 303.9 | 39.6 | 264.3 | 5.81 |
| Today | Sarjapura Road | 791 | 169.2 | 277.5 | 67.3 | 140.0 | 34.6 | 105.4 | 2.96 |
| Trial crossings | 100 Feet Road | 824 | 104.7 | 137.5 | 36.2 | 93.9 | 33.5 | 60.4 | 1.41 |
| Trial crossings | Hosur Road | 994 | 205.8 | 436.0 | 61.4 | 198.7 | 39.6 | 159.1 | 3.23 |
| Trial crossings | Sarjapura Road | 791 | 115.7 | 177.5 | 53.1 | 85.7 | 34.6 | 51.1 | 2.35 |
| Trial + flyover open | 100 Feet Road | 824 | 105.5 | 138.5 | 37.5 | 93.9 | 33.5 | 60.4 | 1.41 |
| Trial + flyover open | Hosur Road | 994 | 202.2 | 442.5 | 58.5 | 198.3 | 39.6 | 158.7 | 3.21 |
| Trial + flyover open | Sarjapura Road | 791 | 120.3 | 184.5 | 58.1 | 85.6 | 34.6 | 51.0 | 2.36 |

### Vehicles along each loop road
![vehicles](vehicles.png)

| Scenario | Road | Direction | Length m | Travel time s | Free-flow s | Delay s | Avg speed km/h | Vehicles/h (max edge) |
|---|---|---|---|---|---|---|---|---|
| Today | 100 Feet Road | A>B | 478 | 2576.9 | 37.4 | 2539.5 | 0.7 | 337 |
| Today | 100 Feet Road | B>A | 474 | 105.3 | 56.9 | 48.4 | 16.2 | 565 |
| Today | Hosur Road | B>C | 830 | 5507.9 | 65.2 | 5442.7 | 0.5 | 348 |
| Today | Hosur Road | C>B | 723 | 137.3 | 48.8 | 88.4 | 19.0 | 2268 |
| Today | Sarjapura Road | C>A | 750 | 141.2 | 51.3 | 89.9 | 19.1 | 2268 |
| Today | Sarjapura Road | A>C | 922 | 162.2 | 66.4 | 95.8 | 20.5 | 1538 |
| Trial crossings | 100 Feet Road | A>B | 463 | 329.6 | 36.3 | 293.2 | 5.1 | 695 |
| Trial crossings | 100 Feet Road | B>A | 460 | 144.9 | 55.2 | 89.7 | 11.4 | 831 |
| Trial crossings | Hosur Road | B>C | 820 | 426.8 | 64.4 | 362.4 | 6.9 | 1876 |
| Trial crossings | Hosur Road | C>B | 790 | 215.4 | 57.5 | 157.9 | 13.2 | 1960 |
| Trial crossings | Sarjapura Road | C>A | 737 | 203.7 | 50.4 | 153.2 | 13.0 | 1960 |
| Trial crossings | Sarjapura Road | A>C | 910 | 150.2 | 65.5 | 84.6 | 21.8 | 929 |
| Trial + flyover open | 100 Feet Road | A>B | 463 | 196.3 | 36.3 | 160.0 | 8.5 | 693 |
| Trial + flyover open | 100 Feet Road | B>A | 460 | 230.5 | 55.2 | 175.2 | 7.2 | 597 |
| Trial + flyover open | Hosur Road | B>C | 820 | 454.7 | 64.4 | 390.3 | 6.5 | 1365 |
| Trial + flyover open | Hosur Road | C>B | 790 | 174.5 | 57.5 | 117.0 | 16.3 | 2282 |
| Trial + flyover open | Sarjapura Road | C>A | 737 | 203.5 | 50.4 | 153.1 | 13.0 | 2282 |
| Trial + flyover open | Sarjapura Road | A>C | 910 | 199.9 | 65.5 | 134.4 | 16.4 | 964 |

### Queues at signals
![queues](queues.png)

| Scenario | Signal (A/B/C, X0-X7 = trial crossings) | Approach lanes | Mean queue, worst lane m | Max queue m |
|---|---|---|---|---|
| Today | A | 14 | 29.1 | 149.1 |
| Today | B | 10 | 141.5 | 150.1 |
| Today | C | 12 | 44.3 | 149.7 |
| Trial crossings | A | 14 | 27.1 | 96.5 |
| Trial crossings | B | 10 | 23.5 | 39.4 |
| Trial crossings | C | 12 | 142.6 | 150.1 |
| Trial crossings | X0 | 8 | 2.4 | 40.0 |
| Trial crossings | X1 | 8 | 58.9 | 140.0 |
| Trial crossings | X2 | 4 | 0.2 | 4.3 |
| Trial crossings | X3 | 14 | 12.1 | 29.5 |
| Trial crossings | X4 | 14 | 68.5 | 73.2 |
| Trial crossings | X5 | 12 | 4.9 | 83.5 |
| Trial crossings | X6 | 12 | 1.6 | 41.3 |
| Trial crossings | X7 | 12 | 3.7 | 139.4 |
| Trial + flyover open | A | 14 | 62.0 | 150.1 |
| Trial + flyover open | B | 10 | 19.9 | 39.4 |
| Trial + flyover open | C | 12 | 105.7 | 150.1 |
| Trial + flyover open | X0 | 8 | 2.2 | 45.0 |
| Trial + flyover open | X1 | 8 | 44.6 | 139.5 |
| Trial + flyover open | X2 | 4 | 0.1 | 4.3 |
| Trial + flyover open | X3 | 14 | 15.7 | 27.7 |
| Trial + flyover open | X4 | 14 | 69.2 | 73.2 |
| Trial + flyover open | X5 | 12 | 21.2 | 149.1 |
| Trial + flyover open | X6 | 12 | 1.8 | 53.9 |
| Trial + flyover open | X7 | 12 | 4.1 | 139.3 |

Queue detectors cover the last 150 m of each approach lane, so 150 m means "the queue reaches past the detector".

### Crossing use (people per hour)
| Scenario | Crossing | People/h |
|---|---|---|
| Today | A | 1110 |
| Today | B | 1557 |
| Today | C | 1160 |
| Today | FOB BC@612 | 494 |
| Today | FOB CA@415 | 146 |
| Today | foot bridges off the loop | 5 |
| Today | other junctions | 5946 |
| Trial crossings | A | 1132 |
| Trial crossings | B | 472 |
| Trial crossings | C | 981 |
| Trial crossings | FOB BC@612 | 204 |
| Trial crossings | FOB CA@415 | 0 |
| Trial crossings | X0 | 12 |
| Trial crossings | X1 | 338 |
| Trial crossings | X2 | 262 |
| Trial crossings | X3 | 482 |
| Trial crossings | X4 | 109 |
| Trial crossings | X5 | 157 |
| Trial crossings | X6 | 39 |
| Trial crossings | X7 | 74 |
| Trial crossings | foot bridges off the loop | 5 |
| Trial crossings | other junctions | 5083 |
| Trial + flyover open | A | 1122 |
| Trial + flyover open | B | 482 |
| Trial + flyover open | C | 990 |
| Trial + flyover open | FOB BC@612 | 205 |
| Trial + flyover open | FOB CA@415 | 0 |
| Trial + flyover open | X0 | 12 |
| Trial + flyover open | X1 | 344 |
| Trial + flyover open | X2 | 246 |
| Trial + flyover open | X3 | 481 |
| Trial + flyover open | X4 | 109 |
| Trial + flyover open | X5 | 156 |
| Trial + flyover open | X6 | 38 |
| Trial + flyover open | X7 | 74 |
| Trial + flyover open | foot bridges off the loop | 5 |
| Trial + flyover open | other junctions | 5090 |

### Buses
| Scenario | Buses (finished) | Trip time in area s | Delay mean s | Delay p85 s |
|---|---|---|---|---|
| Today | 99 | 688.4 | 536.4 | 1163.2 |
| Trial crossings | 154 | 1161.3 | 1008.0 | 1726.4 |
| Trial + flyover open | 179 | 721.8 | 564.6 | 1242.3 |

### Map
![map](map.png)

`results.geojson` holds per-edge speed / delay / volume for each loop road and scenario, plus the trial crossing points, ready for the website.

## Assumptions (all in `config/assumptions.json`)
| Item | Value | Status |
|---|---|---|
| Peak-hour vehicle flows between gateways | IRR>HS 1150, HS>IRR 1150, HN>HS 1500, HS>HN 1500, HN>SE 400, SE>HN 400, SE>HS 250, HS>SE 250, IRR>HN 200, HN>IRR 200, SE>TW 150, HS>TW 150, local_random 400, HN>TW 150 veh/h | ASSUMED (corridor ~1,150/dir derived from the OD study's 27,300/day) |
| Vehicle mix | 2W 11758, car 7968, van 1335, auto 3478, goods auto 480, LCV 1039, truck 262 (relative) | DATA (OD study) |
| Buses | real Monday trips from BMTC GTFS, dwell 20 s | DATA + ASSUMED dwell |
| Signals A, B, C | fixed time, 120 s cycle, programmes generated by netconvert | ASSUMED |
| Trial crossings | 75 s cycle, 18 s pedestrian green | proposal |
| People crossing | bus stops: buses in 8–9 am × 6 pax × 0.5 crossing; places: Healthcare 60/h, Institutional 60/h, Religious 25/h, Recreational 25/h, Public amenities 25/h, Side street 30/h; origins -60…60 m along the far footpath | ASSUMED |
| Background walking | 600 trips/h, 150–600 m | ASSUMED |
| Flyover diversion | 53% of corridor ODs | DATA-derived (OD/toll study, 45–62%) |
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
