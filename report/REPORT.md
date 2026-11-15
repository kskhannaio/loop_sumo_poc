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
| Today | 2610 | 196.6 (+0.0) | 145.4 (+0.0) | 64.4 (+0.0) | 834.0 (+0.0) | 972.1 (+0.0) | 3547 | 174 | 23 |
| Trial crossings | 2609 | 141.2 (-55.4) | 95.1 (-50.3) | 45.7 (-18.7) | 713.8 (-120.2) | 1052.4 (+80.3) | 2936 | 148 | 25 |
| Trial + flyover open | 2609 | 141.2 (-55.4) | 94.8 (-50.6) | 46.0 (-18.4) | 293.9 (-540.1) | 539.1 (-433.0) | 160 | 94 | 10 |

*Vehicles never let in* = demand that could not enter the network before the simulation ended — a sign the assumed volumes exceed what the entries and signals can carry (Madiwala is congested at peak, but the volumes are uncalibrated).

![people](people.png)

### People crossing each road
| Scenario | Road | Trips | Trip time mean s | p85 s | Time lost s | Walked m | Straight-line m | Extra m | Detour factor (median) |
|---|---|---|---|---|---|---|---|---|---|
| Today | 100 Feet Road | 825 | 99.5 | 162.0 | 44.4 | 75.5 | 33.5 | 42.0 | 1.5 |
| Today | Hosur Road | 994 | 297.1 | 517.0 | 77.1 | 302.5 | 39.6 | 262.9 | 5.79 |
| Today | Sarjapura Road | 791 | 171.5 | 283.5 | 69.4 | 140.2 | 34.6 | 105.6 | 2.96 |
| Trial crossings | 100 Feet Road | 824 | 99.0 | 134.5 | 30.7 | 94.0 | 33.5 | 60.5 | 1.42 |
| Trial crossings | Hosur Road | 994 | 197.3 | 432.0 | 53.0 | 198.3 | 39.6 | 158.7 | 3.22 |
| Trial crossings | Sarjapura Road | 791 | 114.8 | 176.0 | 52.1 | 85.7 | 34.6 | 51.1 | 2.35 |
| Trial + flyover open | 100 Feet Road | 824 | 98.8 | 128.5 | 30.7 | 94.0 | 33.5 | 60.5 | 1.42 |
| Trial + flyover open | Hosur Road | 994 | 196.2 | 438.0 | 52.2 | 197.6 | 39.6 | 158.0 | 3.22 |
| Trial + flyover open | Sarjapura Road | 791 | 116.1 | 173.5 | 54.2 | 85.6 | 34.6 | 51.0 | 2.35 |

### Vehicles along each loop road
![vehicles](vehicles.png)

| Scenario | Road | Direction | Length m | Travel time s | Free-flow s | Delay s | Avg speed km/h | Vehicles/h (max edge) |
|---|---|---|---|---|---|---|---|---|
| Today | 100 Feet Road | A>B | 478 | 839.5 | 37.4 | 802.1 | 2.1 | 306 |
| Today | 100 Feet Road | B>A | 474 | 397.7 | 56.9 | 340.8 | 4.3 | 714 |
| Today | Hosur Road | B>C | 829 | 2311.0 | 65.1 | 2245.8 | 1.3 | 526 |
| Today | Hosur Road | C>B | 725 | 109.0 | 49.1 | 59.8 | 24.0 | 2243 |
| Today | Sarjapura Road | C>A | 750 | 150.9 | 51.3 | 99.6 | 17.9 | 2243 |
| Today | Sarjapura Road | A>C | 922 | 181.0 | 66.4 | 114.5 | 18.4 | 1407 |
| Trial crossings | 100 Feet Road | A>B | 463 | 68.8 | 36.3 | 32.5 | 24.2 | 900 |
| Trial crossings | 100 Feet Road | B>A | 460 | 294.3 | 55.2 | 239.0 | 5.6 | 384 |
| Trial crossings | Hosur Road | B>C | 819 | 1182.6 | 64.4 | 1118.2 | 2.5 | 689 |
| Trial crossings | Hosur Road | C>B | 793 | 127.4 | 57.8 | 69.6 | 22.4 | 2263 |
| Trial crossings | Sarjapura Road | C>A | 737 | 128.3 | 50.4 | 77.9 | 20.7 | 2263 |
| Trial crossings | Sarjapura Road | A>C | 910 | 145.5 | 65.5 | 80.0 | 22.5 | 1094 |
| Trial + flyover open | 100 Feet Road | A>B | 463 | 51.3 | 36.3 | 15.0 | 32.5 | 572 |
| Trial + flyover open | 100 Feet Road | B>A | 460 | 327.8 | 55.2 | 272.5 | 5.1 | 534 |
| Trial + flyover open | Hosur Road | B>C | 819 | 286.7 | 64.4 | 222.4 | 10.3 | 1744 |
| Trial + flyover open | Hosur Road | C>B | 793 | 196.1 | 57.8 | 138.3 | 14.5 | 2143 |
| Trial + flyover open | Sarjapura Road | C>A | 737 | 225.0 | 50.4 | 174.5 | 11.8 | 2143 |
| Trial + flyover open | Sarjapura Road | A>C | 910 | 165.1 | 65.5 | 99.5 | 19.9 | 855 |

### Queues at signals
![queues](queues.png)

| Scenario | Signal (A/B/C, X0-X7 = trial crossings) | Approach lanes | Mean queue, worst lane m | Max queue m |
|---|---|---|---|---|
| Today | A | 18 | 40.2 | 150.1 |
| Today | C | 20 | 61.9 | 150.1 |
| Trial crossings | A | 18 | 69.1 | 150.1 |
| Trial crossings | C | 20 | 38.1 | 150.1 |
| Trial crossings | X0 | 8 | 8.0 | 75.8 |
| Trial crossings | X1 | 8 | 4.4 | 80.9 |
| Trial crossings | X2 | 4 | 0.1 | 4.8 |
| Trial crossings | X3 | 14 | 17.6 | 29.1 |
| Trial crossings | X4 | 14 | 71.2 | 75.3 |
| Trial crossings | X5 | 12 | 3.0 | 53.2 |
| Trial crossings | X6 | 12 | 1.6 | 27.3 |
| Trial crossings | X7 | 12 | 3.6 | 139.3 |
| Trial + flyover open | A | 18 | 86.4 | 150.1 |
| Trial + flyover open | C | 20 | 143.5 | 150.1 |
| Trial + flyover open | X0 | 8 | 6.9 | 77.1 |
| Trial + flyover open | X1 | 8 | 4.0 | 45.1 |
| Trial + flyover open | X2 | 4 | 0.2 | 11.1 |
| Trial + flyover open | X3 | 14 | 9.2 | 35.9 |
| Trial + flyover open | X4 | 14 | 69.3 | 73.2 |
| Trial + flyover open | X5 | 12 | 3.8 | 59.6 |
| Trial + flyover open | X6 | 12 | 1.4 | 30.6 |
| Trial + flyover open | X7 | 12 | 5.0 | 139.4 |

Queue detectors cover the last 150 m of each approach lane, so 150 m means "the queue reaches past the detector".

### Crossing use (people per hour)
| Scenario | Crossing | People/h |
|---|---|---|
| Today | A | 1121 |
| Today | B | 1628 |
| Today | C | 1158 |
| Today | FOB BC@612 | 484 |
| Today | FOB CA@415 | 147 |
| Today | foot bridges off the loop | 9 |
| Today | other junctions | 11673 |
| Trial crossings | A | 1132 |
| Trial crossings | B | 676 |
| Trial crossings | C | 973 |
| Trial crossings | FOB BC@612 | 212 |
| Trial crossings | FOB CA@415 | 0 |
| Trial crossings | X0 | 14 |
| Trial crossings | X1 | 266 |
| Trial crossings | X2 | 236 |
| Trial crossings | X3 | 480 |
| Trial crossings | X4 | 107 |
| Trial crossings | X5 | 159 |
| Trial crossings | X6 | 39 |
| Trial crossings | X7 | 74 |
| Trial crossings | foot bridges off the loop | 9 |
| Trial crossings | other junctions | 9320 |
| Trial + flyover open | A | 1120 |
| Trial + flyover open | B | 681 |
| Trial + flyover open | C | 981 |
| Trial + flyover open | FOB BC@612 | 202 |
| Trial + flyover open | FOB CA@415 | 0 |
| Trial + flyover open | X0 | 14 |
| Trial + flyover open | X1 | 261 |
| Trial + flyover open | X2 | 233 |
| Trial + flyover open | X3 | 477 |
| Trial + flyover open | X4 | 107 |
| Trial + flyover open | X5 | 157 |
| Trial + flyover open | X6 | 39 |
| Trial + flyover open | X7 | 72 |
| Trial + flyover open | foot bridges off the loop | 8 |
| Trial + flyover open | other junctions | 9324 |

### Buses
| Scenario | Buses (finished) | Trip time in area s | Delay mean s | Delay p85 s |
|---|---|---|---|---|
| Today | 95 | 1147.4 | 972.1 | 2421.8 |
| Trial crossings | 118 | 1212.7 | 1052.4 | 2866.0 |
| Trial + flyover open | 229 | 705.6 | 539.1 | 1256.7 |

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
