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
| Today | 2647 | 194.3 (+0.0) | 155.8 (+0.0) | 54.7 (+0.0) | 734.4 (+0.0) | 996.7 (+0.0) | 3855 | 158 | 11 |
| Trial crossings | 2633 | 123.2 (-71.1) | 70.8 (-85.0) | 45.4 (-9.3) | 656.7 (-77.7) | 776.9 (-219.8) | 3420 | 128 | 20 |
| Trial + flyover open | 2633 | 119.9 (-74.4) | 70.8 (-85.0) | 42.1 (-12.6) | 332.5 (-401.9) | 342.0 (-654.7) | 576 | 40 | 14 |

*Vehicles never let in* = demand that could not enter the network before the simulation ended — a sign the assumed volumes exceed what the entries and signals can carry (Madiwala is congested at peak, but the volumes are uncalibrated).

![people](people.png)

### People crossing each road
| Scenario | Road | Trips | Trip time mean s | p85 s | Time lost s | Walked m | Straight-line m | Extra m | Detour factor (median) |
|---|---|---|---|---|---|---|---|---|---|
| Today | 100 Feet Road | 840 | 81.8 | 131.0 | 26.8 | 75.9 | 33.9 | 41.9 | 1.55 |
| Today | Hosur Road | 978 | 285.6 | 488.0 | 68.6 | 298.8 | 39.2 | 259.6 | 5.37 |
| Today | Sarjapura Road | 829 | 200.7 | 372.0 | 66.7 | 183.3 | 34.5 | 148.8 | 3.12 |
| Trial crossings | 100 Feet Road | 837 | 84.5 | 129.5 | 33.2 | 70.1 | 34.0 | 36.2 | 1.41 |
| Trial crossings | Hosur Road | 968 | 165.3 | 212.0 | 52.0 | 155.8 | 39.1 | 116.7 | 2.71 |
| Trial crossings | Sarjapura Road | 828 | 113.0 | 168.5 | 50.0 | 86.8 | 34.5 | 52.3 | 2.36 |
| Trial + flyover open | 100 Feet Road | 837 | 79.8 | 120.0 | 29.3 | 70.1 | 34.0 | 36.1 | 1.41 |
| Trial + flyover open | Hosur Road | 968 | 160.3 | 191.0 | 46.3 | 155.8 | 39.1 | 116.7 | 2.71 |
| Trial + flyover open | Sarjapura Road | 828 | 113.1 | 170.0 | 50.1 | 86.6 | 34.5 | 52.1 | 2.36 |

### Vehicles along each loop road
![vehicles](vehicles.png)

| Scenario | Road | Direction | Length m | Travel time s | Free-flow s | Delay s | Avg speed km/h | Vehicles/h (max edge) |
|---|---|---|---|---|---|---|---|---|
| Today | 100 Feet Road | A>B | 480 | 280.4 | 37.5 | 242.9 | 6.2 | 309 |
| Today | 100 Feet Road | B>A | 476 | 102.8 | 57.1 | 45.7 | 16.7 | 603 |
| Today | Hosur Road | B>C | 676 | 915.3 | 54.0 | 861.2 | 2.7 | 711 |
| Today | Hosur Road | C>B | 728 | 192.4 | 49.2 | 143.2 | 13.6 | 2212 |
| Today | Sarjapura Road | C>A | 798 | 214.0 | 54.8 | 159.3 | 13.4 | 2212 |
| Today | Sarjapura Road | A>C | 927 | 165.7 | 66.8 | 99.0 | 20.1 | 937 |
| Trial crossings | 100 Feet Road | A>B | 465 | 442.7 | 36.4 | 406.2 | 3.8 | 832 |
| Trial crossings | 100 Feet Road | B>A | 462 | 117.4 | 55.4 | 61.9 | 14.2 | 335 |
| Trial crossings | Hosur Road | B>C | 666 | 617.1 | 53.3 | 563.8 | 3.9 | 1006 |
| Trial crossings | Hosur Road | C>B | 796 | 265.6 | 57.9 | 207.7 | 10.8 | 2204 |
| Trial crossings | Sarjapura Road | C>A | 785 | 272.1 | 53.9 | 218.2 | 10.4 | 2204 |
| Trial crossings | Sarjapura Road | A>C | 915 | 155.3 | 65.9 | 89.4 | 21.2 | 934 |
| Trial + flyover open | 100 Feet Road | A>B | 465 | 152.4 | 36.4 | 116.0 | 11.0 | 757 |
| Trial + flyover open | 100 Feet Road | B>A | 462 | 106.6 | 55.4 | 51.2 | 15.6 | 596 |
| Trial + flyover open | Hosur Road | B>C | 666 | 187.2 | 53.3 | 133.9 | 12.8 | 1777 |
| Trial + flyover open | Hosur Road | C>B | 796 | 282.4 | 57.9 | 224.6 | 10.1 | 2017 |
| Trial + flyover open | Sarjapura Road | C>A | 785 | 295.1 | 53.9 | 241.2 | 9.6 | 2017 |
| Trial + flyover open | Sarjapura Road | A>C | 915 | 155.3 | 65.9 | 89.4 | 21.2 | 796 |

### Queues at signals
![queues](queues.png)

| Scenario | Signal (A/B/C, X0-X7 = trial crossings) | Approach lanes | Mean queue, worst lane m | Max queue m |
|---|---|---|---|---|
| Today | A | 14 | 19.6 | 134.7 |
| Today | B | 8 | 16.1 | 39.4 |
| Today | C | 12 | 122.5 | 150.1 |
| Trial crossings | A | 14 | 17.2 | 76.1 |
| Trial crossings | B | 8 | 33.8 | 40.4 |
| Trial crossings | C | 12 | 144.8 | 150.1 |
| Trial crossings | X0 | 8 | 0.7 | 30.9 |
| Trial crossings | X1 | 8 | 78.1 | 138.7 |
| Trial crossings | X2 | 4 | 0.3 | 4.3 |
| Trial crossings | X3 | 14 | 26.0 | 35.6 |
| Trial crossings | X4 | 14 | 77.7 | 82.6 |
| Trial crossings | X5 | 12 | 2.1 | 38.3 |
| Trial crossings | X6 | 12 | 2.2 | 36.5 |
| Trial crossings | X7 | 12 | 4.1 | 139.4 |
| Trial + flyover open | A | 14 | 15.8 | 82.2 |
| Trial + flyover open | B | 8 | 18.1 | 40.4 |
| Trial + flyover open | C | 12 | 148.8 | 150.1 |
| Trial + flyover open | X0 | 8 | 1.3 | 29.1 |
| Trial + flyover open | X1 | 8 | 31.5 | 138.0 |
| Trial + flyover open | X2 | 4 | 0.1 | 8.8 |
| Trial + flyover open | X3 | 14 | 4.0 | 32.1 |
| Trial + flyover open | X4 | 14 | 34.7 | 82.6 |
| Trial + flyover open | X5 | 12 | 2.0 | 38.9 |
| Trial + flyover open | X6 | 12 | 1.3 | 30.7 |
| Trial + flyover open | X7 | 12 | 4.8 | 139.3 |

Queue detectors cover the last 150 m of each approach lane, so 150 m means "the queue reaches past the detector".

### Crossing use (people per hour)
| Scenario | Crossing | People/h |
|---|---|---|
| Today | A | 1191 |
| Today | B | 1577 |
| Today | C | 2270 |
| Today | other junctions | 6367 |
| Trial crossings | A | 1104 |
| Trial crossings | B | 537 |
| Trial crossings | C | 1287 |
| Trial crossings | X0 | 14 |
| Trial crossings | X1 | 332 |
| Trial crossings | X2 | 208 |
| Trial crossings | X3 | 446 |
| Trial crossings | X4 | 197 |
| Trial crossings | X5 | 186 |
| Trial crossings | X6 | 68 |
| Trial crossings | X7 | 66 |
| Trial crossings | other junctions | 5269 |
| Trial + flyover open | A | 1103 |
| Trial + flyover open | B | 520 |
| Trial + flyover open | C | 1294 |
| Trial + flyover open | X0 | 12 |
| Trial + flyover open | X1 | 340 |
| Trial + flyover open | X2 | 211 |
| Trial + flyover open | X3 | 447 |
| Trial + flyover open | X4 | 196 |
| Trial + flyover open | X5 | 183 |
| Trial + flyover open | X6 | 68 |
| Trial + flyover open | X7 | 66 |
| Trial + flyover open | other junctions | 5278 |

### Buses
| Scenario | Buses (finished) | Trip time in area s | Delay mean s | Delay p85 s |
|---|---|---|---|---|
| Today | 176 | 1164.9 | 996.7 | 1926.6 |
| Trial crossings | 183 | 931.9 | 776.9 | 1087.0 |
| Trial + flyover open | 186 | 493.1 | 342.0 | 348.6 |

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
