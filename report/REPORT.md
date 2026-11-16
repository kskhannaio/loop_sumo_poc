# Madiwala loop — SUMO traffic and pedestrian simulation

Weekday morning peak (metrics for trips starting 09:30–10:30; simulated 09:00–10:45 with warm-up),
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
| Today | 2610 | 210.3 (+0.0) | 145.1 (+0.0) | 78.4 (+0.0) | 710.6 (+0.0) | 882.4 (+0.0) | 1962 | 147 | 16 |
| Trial crossings | 2609 | 146.6 (-63.7) | 94.6 (-50.5) | 51.2 (-27.2) | 489.3 (-221.3) | 805.7 (-76.7) | 1754 | 142 | 22 |
| Trial + flyover open | 2609 | 143.1 (-67.2) | 94.9 (-50.2) | 47.9 (-30.5) | 264.1 (-446.5) | 367.8 (-514.6) | 217 | 95 | 9 |
| Planner proposal at C | 2610 | 165.5 (-44.8) | 121.3 (-23.8) | 51.0 (-27.4) | 604.6 (-106.0) | 741.4 (-141.0) | 1408 | 219 | 24 |

*Vehicles never let in* = demand that could not enter the network before the simulation ended — a sign the assumed volumes exceed what the entries and signals can carry (Madiwala is congested at peak, but the volumes are uncalibrated).

![people](people.png)

### People crossing each road
| Scenario | Road | Trips | Trip time mean s | p85 s | Time lost s | Walked m | Straight-line m | Extra m | Detour factor (median) |
|---|---|---|---|---|---|---|---|---|---|
| Today | 100 Feet Road | 825 | 121.5 | 174.5 | 66.5 | 75.5 | 33.5 | 42.0 | 1.5 |
| Today | Hosur Road | 994 | 292.2 | 503.5 | 72.9 | 301.8 | 39.6 | 262.2 | 5.79 |
| Today | Sarjapura Road | 791 | 200.0 | 310.5 | 97.8 | 140.1 | 34.6 | 105.5 | 2.96 |
| Trial crossings | 100 Feet Road | 824 | 91.0 | 120.5 | 22.6 | 94.0 | 33.5 | 60.5 | 1.41 |
| Trial crossings | Hosur Road | 994 | 199.0 | 437.5 | 55.0 | 197.1 | 39.6 | 157.5 | 3.2 |
| Trial crossings | Sarjapura Road | 791 | 138.8 | 213.0 | 76.2 | 85.7 | 34.6 | 51.1 | 2.36 |
| Trial + flyover open | 100 Feet Road | 824 | 94.6 | 126.5 | 26.5 | 94.0 | 33.5 | 60.5 | 1.42 |
| Trial + flyover open | Hosur Road | 994 | 198.4 | 466.0 | 54.1 | 197.8 | 39.6 | 158.2 | 3.19 |
| Trial + flyover open | Sarjapura Road | 791 | 124.2 | 187.5 | 62.2 | 85.7 | 34.6 | 51.0 | 2.35 |
| Planner proposal at C | 100 Feet Road | 825 | 111.7 | 178.0 | 56.6 | 75.5 | 33.5 | 42.0 | 1.5 |
| Planner proposal at C | Hosur Road | 994 | 240.0 | 401.0 | 53.7 | 256.5 | 39.6 | 216.9 | 5.44 |
| Planner proposal at C | Sarjapura Road | 791 | 128.0 | 234.5 | 41.6 | 118.3 | 34.6 | 83.7 | 2.29 |

### Vehicles along each loop road
![vehicles](vehicles.png)

| Scenario | Road | Direction | Length m | Travel time s | Free-flow s | Delay s | Avg speed km/h | Vehicles/h (max edge) |
|---|---|---|---|---|---|---|---|---|
| Today | 100 Feet Road | A>B | 417 | 41.4 | 30.0 | 11.4 | 36.2 | 984 |
| Today | 100 Feet Road | B>A | 395 | 256.9 | 47.4 | 209.5 | 5.5 | 447 |
| Today | Hosur Road | B>C | 535 | 268.5 | 40.6 | 227.9 | 7.2 | 1761 |
| Today | Hosur Road | C>B | 505 | 67.5 | 35.9 | 31.6 | 26.9 | 1552 |
| Today | Sarjapura Road | C>A | 529 | 228.2 | 38.1 | 190.1 | 8.4 | 903 |
| Today | Sarjapura Road | A>C | 606 | 152.1 | 43.7 | 108.4 | 14.4 | 663 |
| Trial crossings | 100 Feet Road | A>B | 402 | 47.7 | 28.9 | 18.8 | 30.3 | 698 |
| Trial crossings | 100 Feet Road | B>A | 381 | 285.4 | 45.7 | 239.6 | 4.8 | 373 |
| Trial crossings | Hosur Road | B>C | 525 | 228.0 | 39.9 | 188.1 | 8.3 | 2089 |
| Trial crossings | Hosur Road | C>B | 573 | 70.2 | 44.6 | 25.6 | 29.4 | 1512 |
| Trial crossings | Sarjapura Road | C>A | 517 | 140.6 | 37.2 | 103.3 | 13.2 | 1047 |
| Trial crossings | Sarjapura Road | A>C | 594 | 126.9 | 42.8 | 84.1 | 16.9 | 643 |
| Trial + flyover open | 100 Feet Road | A>B | 402 | 44.1 | 28.9 | 15.2 | 32.8 | 567 |
| Trial + flyover open | 100 Feet Road | B>A | 381 | 263.3 | 45.7 | 217.6 | 5.2 | 557 |
| Trial + flyover open | Hosur Road | B>C | 525 | 155.3 | 39.9 | 115.4 | 12.2 | 2001 |
| Trial + flyover open | Hosur Road | C>B | 573 | 72.5 | 44.6 | 28.0 | 28.4 | 1513 |
| Trial + flyover open | Sarjapura Road | C>A | 517 | 161.6 | 37.2 | 124.3 | 11.5 | 760 |
| Trial + flyover open | Sarjapura Road | A>C | 594 | 136.3 | 42.8 | 93.5 | 15.7 | 654 |
| Planner proposal at C | 100 Feet Road | A>B | 417 | 72.3 | 30.0 | 42.4 | 20.7 | 1354 |
| Planner proposal at C | 100 Feet Road | B>A | 395 | 153.1 | 47.4 | 105.7 | 9.3 | 810 |
| Planner proposal at C | Hosur Road | B>C | 530 | 423.2 | 40.3 | 382.9 | 4.5 | 1692 |
| Planner proposal at C | Hosur Road | C>B | 484 | 67.7 | 34.7 | 33.0 | 25.8 | 1484 |
| Planner proposal at C | Sarjapura Road | C>A | 525 | 116.7 | 37.8 | 78.9 | 16.2 | 712 |
| Planner proposal at C | Sarjapura Road | A>C | 576 | 243.4 | 41.4 | 201.9 | 8.5 | 711 |

### Queues at signals
![queues](queues.png)

| Scenario | Signal (A/B/C, X0-X7 = trial crossings) | Approach lanes | Mean queue, worst lane m | Max queue m |
|---|---|---|---|---|
| Today | A | 18 | 103.3 | 150.1 |
| Today | C | 20 | 82.4 | 150.1 |
| Trial crossings | A | 18 | 66.8 | 150.1 |
| Trial crossings | C | 20 | 76.2 | 150.1 |
| Trial crossings | X0 | 8 | 1.2 | 26.6 |
| Trial crossings | X1 | 8 | 3.1 | 41.5 |
| Trial crossings | X2 | 4 | 0.1 | 10.2 |
| Trial crossings | X3 | 14 | 6.6 | 30.9 |
| Trial crossings | X4 | 14 | 39.0 | 73.2 |
| Trial crossings | X5 | 12 | 2.8 | 64.9 |
| Trial crossings | X6 | 12 | 19.9 | 146.0 |
| Trial crossings | X7 | 12 | 3.0 | 118.9 |
| Trial + flyover open | A | 18 | 89.1 | 150.1 |
| Trial + flyover open | C | 20 | 58.2 | 150.1 |
| Trial + flyover open | X0 | 8 | 8.9 | 83.2 |
| Trial + flyover open | X1 | 8 | 2.6 | 38.9 |
| Trial + flyover open | X2 | 4 | 0.6 | 23.4 |
| Trial + flyover open | X3 | 14 | 2.2 | 32.9 |
| Trial + flyover open | X4 | 14 | 41.3 | 73.2 |
| Trial + flyover open | X5 | 12 | 10.6 | 122.3 |
| Trial + flyover open | X6 | 12 | 6.4 | 70.6 |
| Trial + flyover open | X7 | 12 | 3.0 | 140.7 |
| Planner proposal at C | A | 18 | 74.9 | 150.1 |
| Planner proposal at C | C | 14 | 86.2 | 150.1 |
| Planner proposal at C | P0 | 12 | 99.7 | 150.0 |
| Planner proposal at C | P1 | 8 | 80.4 | 119.8 |

Queue detectors cover the last 150 m of each approach lane, so 150 m means "the queue reaches past the detector".

### Crossing use (people per hour)
| Scenario | Crossing | People/h |
|---|---|---|
| Today | A | 1124 |
| Today | B | 1635 |
| Today | C | 1198 |
| Today | FOB BC@612 | 469 |
| Today | FOB CA@415 | 145 |
| Today | foot bridges off the loop | 9 |
| Today | other junctions | 11711 |
| Trial crossings | A | 1128 |
| Trial crossings | B | 678 |
| Trial crossings | C | 993 |
| Trial crossings | FOB BC@612 | 192 |
| Trial crossings | FOB CA@415 | 0 |
| Trial crossings | X0 | 14 |
| Trial crossings | X1 | 265 |
| Trial crossings | X2 | 236 |
| Trial crossings | X3 | 479 |
| Trial crossings | X4 | 107 |
| Trial crossings | X5 | 158 |
| Trial crossings | X6 | 39 |
| Trial crossings | X7 | 74 |
| Trial crossings | foot bridges off the loop | 8 |
| Trial crossings | other junctions | 9374 |
| Trial + flyover open | A | 1124 |
| Trial + flyover open | B | 682 |
| Trial + flyover open | C | 991 |
| Trial + flyover open | FOB BC@612 | 198 |
| Trial + flyover open | FOB CA@415 | 0 |
| Trial + flyover open | X0 | 14 |
| Trial + flyover open | X1 | 261 |
| Trial + flyover open | X2 | 231 |
| Trial + flyover open | X3 | 479 |
| Trial + flyover open | X4 | 107 |
| Trial + flyover open | X5 | 158 |
| Trial + flyover open | X6 | 40 |
| Trial + flyover open | X7 | 76 |
| Trial + flyover open | foot bridges off the loop | 8 |
| Trial + flyover open | other junctions | 9344 |
| Planner proposal at C | A | 1129 |
| Planner proposal at C | B | 1580 |
| Planner proposal at C | C | 296 |
| Planner proposal at C | FOB BC@612 | 60 |
| Planner proposal at C | FOB CA@415 | 124 |
| Planner proposal at C | P0 | 429 |
| Planner proposal at C | P1 | 916 |
| Planner proposal at C | foot bridges off the loop | 9 |
| Planner proposal at C | other junctions | 10341 |

### Buses
| Scenario | Buses (finished) | Trip time in area s | Delay mean s | Delay p85 s |
|---|---|---|---|---|
| Today | 119 | 1038.1 | 882.4 | 1686.4 |
| Trial crossings | 128 | 963.2 | 805.7 | 1580.3 |
| Trial + flyover open | 164 | 535.0 | 367.8 | 505.2 |
| Planner proposal at C | 132 | 894.3 | 741.4 | 1282.6 |

### Map
![map](map.png)

`results.geojson` holds per-edge speed / delay / volume for each loop road and scenario, plus the trial crossing points, ready for the website.

## Assumptions (all in `config/assumptions.json`)
| Item | Value | Status |
|---|---|---|
| Peak-hour vehicle flows between gateways | IRR>HS 1150, HS>IRR 1150, HN>HS 1500, HS>HN 1500, HN>SE 400, SE>HN 400, SE>HS 250, HS>SE 250, IRR>HN 200, HN>IRR 200, SE>TW 150, HS>TW 150, local_random 400, HN>TW 150 veh/h | ASSUMED (the 1,150 each way on the 100 Feet Road–Hosur Road south movement borrows a count taken between Indiranagar and Domlur, about 6 km north; nothing is counted on the loop) |
| Vehicle mix | 2W 11758, car 7968, van 1335, auto 3478, goods auto 480, LCV 1039, truck 262 (relative) | DATA, but counted between Indiranagar and Domlur, not on the loop |
| Buses | real Monday trips from BMTC GTFS, dwell 20 s | DATA + ASSUMED dwell |
| Signals A, B, C | fixed time, 120 s cycle, programmes generated by netconvert | ASSUMED |
| Trial crossings | 75 s cycle, 18 s pedestrian green | proposal |
| People crossing | bus stops: buses in the simulated hour × 6 pax × 0.5 crossing; places: Healthcare 60/h, Institutional 60/h, Religious 25/h, Recreational 25/h, Public amenities 25/h, Side street 30/h; origins -60…60 m along the far footpath | ASSUMED |
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
