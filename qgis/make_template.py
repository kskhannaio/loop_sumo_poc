#!/usr/bin/env python3
"""Build qgis/madiwala_proposals.zip: the template to send to planners.

The zip holds one folder with
  madiwala.qgz              the QGIS project (double-click to open)
  madiwala_proposals.gpkg   all data: the study layers (locked), the 8 trial crossings as an example,
                            empty layers for proposals, and the website's story, figures and checklist
  READ ME FIRST.txt         planner instructions
Planners draw, save, and send back the .gpkg (renaming it then is fine). The project finds the data
by file name, so the files inside the folder must not be renamed while working.

The template mirrors the study website (corridor_design_challenge/index.html): the same layers and
symbols, its popups as QGIS map tips, its tabs as map themes, and its text and figures as tables.
Study layers are read from the website repo's data/ folder (read-only), so the template matches the
published site. Run with the system Python that has PyQGIS (installed with QGIS):
    python3 qgis/make_template.py [path/to/website/data]
"""
import json, os, shutil, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PKG = os.path.join(HERE, 'madiwala_proposals')
OUT = os.path.join(PKG, 'madiwala_proposals.gpkg')
QGZ = os.path.join(PKG, 'madiwala.qgz')
ZIP = os.path.join(HERE, 'madiwala_proposals.zip')
DATA = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, '..', 'corridor_design_challenge', 'data'))
if not os.path.isdir(DATA): sys.exit(f'website data folder not found: {DATA}')

from qgis.PyQt.QtCore import QMetaType, Qt
from qgis.PyQt.QtGui import QColor, QFont
from qgis.core import (
    Qgis, QgsApplication, QgsProject, QgsVectorLayer, QgsRasterLayer, QgsField, QgsFeature, QgsGeometry,
    QgsPointXY, QgsVectorFileWriter, QgsCoordinateReferenceSystem, QgsEditorWidgetSetup, QgsSymbol,
    QgsRendererCategory, QgsCategorizedSymbolRenderer, QgsSingleSymbolRenderer, QgsRuleBasedRenderer,
    QgsPalLayerSettings, QgsTextFormat, QgsTextBufferSettings, QgsVectorLayerSimpleLabeling, QgsSnappingConfig,
    QgsReferencedRectangle, QgsFieldConstraints, QgsDefaultValue, QgsProperty, QgsSymbolLayer,
    QgsSimpleLineSymbolLayer, QgsMarkerLineSymbolLayer, QgsMarkerSymbol, QgsSimpleMarkerSymbolLayer,
    QgsMapThemeCollection, QgsLayerTreeModel, QgsLayerNotesUtils)

qgs = QgsApplication([], False)
qgs.initQgis()
WGS84 = QgsCoordinateReferenceSystem('EPSG:4326')
J = lambda name: json.load(open(os.path.join(DATA, name)))

# ================================================================ wording shared with the website
ROADS = {'AB': ('100 Feet Road', 'A', 'B', 'Masjid side', 'IIA side'),
         'BC': ('Hosur Road', 'B', 'C', "east side (St John's grounds)", 'west side (Maruthi Nagar)'),
         'CA': ('Sarjapura Road', 'C', 'A', "south side (St John's grounds)", "north side (St John's Hospital)")}
JN = {'A': 'Water Tank junction', 'B': 'Madiwala underpass', 'C': "St John's junction"}
FP_SIDE = {'SE': 'IIA side', 'NW': 'Masjid side'}
CATS = {'Institutional': '#e8a200', 'Healthcare': '#d6336c', 'Religious': '#8e5bd6', 'Recreational': '#2f9e44',
        'Public amenities': '#0c8599', 'Commercial': '#8a8780'}
CAT_LABEL = {'Institutional': 'Schools & institutes', 'Healthcare': 'Hospitals & clinics', 'Religious': 'Temples & mosques',
             'Recreational': 'Parks & recreation', 'Public amenities': 'Public services', 'Commercial': 'Shops & food'}
PRIVATE_BUS = '#e8590c'

def qmap(d):                       # python dict -> QGIS expression map()
    return 'map(' + ', '.join(f"'{k}', '{str(v).replace(chr(39), chr(39) * 2)}'" for k, v in d.items()) + ')'
ROAD_NAME = qmap({k: v[0] for k, v in ROADS.items()})
ROAD_START = qmap({k: JN[v[1]] for k, v in ROADS.items()})
ROAD_SIDE = 'map(' + ', '.join(f"'{k}', map('inside', '{v[3].replace(chr(39), chr(39) * 2)}', 'outside', '{v[4].replace(chr(39), chr(39) * 2)}')"
                               for k, v in ROADS.items()) + ')'
ROUTES = "array_to_string(array_slice(coalesce(try(from_json(\"routes\")), \"routes\"), 0, 13), ', ')" \
         " || if(\"n_routes\" > 14, ' and ' || (\"n_routes\" - 14) || ' more', '')"
SMALL = '<span style="color:#666;font-size:90%">'

# ================================================================ choices offered to planners
POINT_TYPES = ['Signalised crossing', 'Zebra crossing', 'Remove crossing', 'Move or add bus stop',
               'Turn ban', 'Signal timing', 'New destination', 'Other (describe in notes)']
LINE_TYPES = ['Close lanes', 'Widen footpath', 'New footpath', 'Pedestrianise', 'Other (describe in notes)']
POINT_COLOURS = ['#7048e8', '#1c7ed6', '#e03131', '#f08c00', '#c2255c', '#2f9e44', '#0c8599', '#495057']
LINE_COLOURS = ['#e03131', '#2f9e44', '#0c8599', '#f08c00', '#495057']

# ================================================================ write everything into the GeoPackage
shutil.rmtree(PKG, ignore_errors=True); os.makedirs(PKG)
first = [True]
S, I, D = QMetaType.Type.QString, QMetaType.Type.Int, QMetaType.Type.Double

def write(layer, name):
    opts = QgsVectorFileWriter.SaveVectorOptions()
    opts.driverName = 'GPKG'; opts.layerName = name; opts.fileEncoding = 'UTF-8'
    opts.actionOnExistingFile = (QgsVectorFileWriter.ActionOnExistingFile.CreateOrOverwriteFile if first[0]
                                 else QgsVectorFileWriter.ActionOnExistingFile.CreateOrOverwriteLayer)
    err = QgsVectorFileWriter.writeAsVectorFormatV3(layer, OUT, QgsProject.instance().transformContext(), opts)
    if err[0] != QgsVectorFileWriter.WriterError.NoError: sys.exit(f'writing {name}: {err}')
    first[0] = False

def from_geojson(fname, subset, name, geom):
    # the study files mix points and lines, so name the geometry type explicitly
    lyr = QgsVectorLayer(os.path.join(DATA, fname) + f'|geometrytype={geom}', name, 'ogr')
    if not lyr.isValid(): sys.exit(f'cannot read {DATA}/{fname}')
    if subset: lyr.setSubsetString(subset)
    write(lyr, name)

def memory(geom, fields, rows=(), geoms=None):
    lyr = QgsVectorLayer(f'{geom}?crs=EPSG:4326', 'x', 'memory')
    lyr.dataProvider().addAttributes([QgsField(n, t) for n, t in fields]); lyr.updateFields()
    feats = []
    for i, r in enumerate(rows):
        f = QgsFeature(lyr.fields()); f.setAttributes(list(r))
        if geoms: f.setGeometry(geoms[i])
        feats.append(f)
    lyr.dataProvider().addFeatures(feats)
    return lyr

def table(name, fields, rows):
    write(memory('NoGeometry', fields, rows), name)

PROP = [('change_type', S), ('cycle_s', I), ('ped_green_s', I), ('notes', S), ('proposed_by', S)]
write(memory('Point', PROP), 'proposed_points')
write(memory('LineString', [('change_type', S), ('lanes', I), ('width_m', D), ('notes', S), ('proposed_by', S)]), 'proposed_lines')
table('about_this_proposal', [('title', S), ('description', S), ('proposed_by', S), ('contact', S), ('date', S)], [])

# example scenario: the 8 trial crossings, in the same form a planner would draw them
cfg = json.load(open(os.path.join(ROOT, 'config', 'assumptions.json')))
ex_rows, ex_geoms = [], []
for f in json.load(open(os.path.join(ROOT, 'report', 'results.geojson')))['features']:
    p = f['properties']
    if p.get('kind') != 'trial_crossing': continue
    ex_rows.append(['Signalised crossing', cfg['signals']['midblock_cycle_s'], cfg['signals']['midblock_ped_green_s'],
                    f"{ROADS[p['side']][0]}, {p['dist_from_first_junction_m']} m from the {JN[ROADS[p['side']][1]]}", 'Study team'])
    ex_geoms.append(QgsGeometry.fromPointXY(QgsPointXY(*f['geometry']['coordinates'])))
write(memory('Point', PROP, ex_rows, ex_geoms), 'example_trial_crossings')

for fname, subset, name, geom in [
        ('stretch.geojson', "\"kind\" = 'carriageway'", 'loop_roads', 'LineString'),
        ('stretch.geojson', "\"kind\" = 'junction'", 'junctions', 'Point'),
        ('crossings.geojson', "\"kind\" = 'crossing'", 'existing_crossings', 'Point'),
        ('crossings.geojson', "\"kind\" = 'gap'", 'gaps_without_crossings', 'LineString'),
        ('crossings.geojson', "\"kind\" = 'generator'", 'places_people_cross_to', 'Point'),
        ('crossings.geojson', "\"kind\" = 'desire'", 'desire_lines', 'LineString'),
        ('crossings.geojson', "\"kind\" = 'tick'", 'distance_ticks', 'Point'),
        ('bus_stops.geojson', None, 'bus_stops', 'Point'),
        ('bus_routes.geojson', None, 'bus_routes', 'LineString'),
        ('poi.geojson', "\"category\" = 'Private buses'", 'private_bus_operators', 'Point'),
        ('poi.geojson', "\"category\" <> 'Private buses'", 'places_nearby', 'Point'),
        ('catchments.geojson', None, 'walking_distance', 'Polygon'),
        ('contract.geojson', "\"kind\" = 're_wall'", 'flyover_ramp_wall', 'Polygon'),
        ('contract.geojson', "\"kind\" = 'zone' AND \"status\" <> 'junction'", 'crossing_zones_100ft', 'LineString'),
        ('construction.geojson', None, 'under_construction', 'LineString')]:
    from_geojson(fname, subset, name, geom)

# footpath widths: the data does not say which side of the road each dot is on (the website shows a blank),
# so work it out from the geometry. Website convention: the IIA side is on the left walking from A to B.
cl = next(f['geometry']['coordinates'] for f in J('crossings.geojson')['features']
          if f['properties']['kind'] == 'centreline' and f['properties']['side'] == 'AB')
def side_of_ab(pt):
    best = None
    for (x1, y1), (x2, y2) in zip(cl, cl[1:]):
        dx, dy = x2 - x1, y2 - y1; L2 = dx * dx + dy * dy or 1e-18
        t_ = max(0, min(1, ((pt[0] - x1) * dx + (pt[1] - y1) * dy) / L2))
        d = (pt[0] - x1 - t_ * dx) ** 2 + (pt[1] - y1 - t_ * dy) ** 2
        if best is None or d < best[0]: best = (d, dx * (pt[1] - y1) - dy * (pt[0] - x1))
    return FP_SIDE['SE'] if best[1] > 0 else FP_SIDE['NW']
fp_rows, fp_geoms = [], []
for f in J('contract.geojson')['features']:
    p = f['properties']
    if p['kind'] != 'fp': continue
    fp_rows.append([p['chainage_m'], p['fp_m'], p['fp_flag'], side_of_ab(f['geometry']['coordinates']), p.get('row_m'), p.get('cw')])
    fp_geoms.append(QgsGeometry.fromPointXY(QgsPointXY(*f['geometry']['coordinates'])))
write(memory('Point', [('chainage_m', I), ('fp_m', D), ('fp_flag', S), ('side_of_road', S), ('row_m', D), ('cw', S)],
             fp_rows, fp_geoms), 'footpath_widths')

# ---------------------------------------------------------------- the website's figures and text, as tables
X = [f['properties'] for f in J('crossings.geojson')['features']]
contract, sc, bs = J('contract.json'), J('scorecard.json'), J('bus_summary.json')
stops = [f['properties'] for f in J('bus_stops.geojson')['features']]
poi = [f['properties'] for f in J('poi.geojson')['features']]
gaps = [p for p in X if p['kind'] == 'gap']
sides = []
for sid, (name, a, b, *_ ) in ROADS.items():
    g = [p for p in gaps if p['side'] == sid]
    sides.append((sid, name, next(p['length_m'] for p in X if p['kind'] == 'centreline' and p['side'] == sid),
                  max(p['length_m'] for p in g), sum(p['crossings_needed'] for p in g)))
need, loop_m = sum(s[4] for s in sides), sum(s[2] for s in sides)
feas = next(f['properties'] for f in J('contract.geojson')['features'] if f['properties']['kind'] == 'zone' and f['properties']['status'] == 'feasible')
wall = contract['re_wall']
rows = contract['inventory']['rows']
fpv = [v for r in rows for v in (r['fp_lhs'], r['fp_rhs'])]
fp_below, fp_none = sum(1 for v in fpv if v < 2.5), [r['ch'] for r in rows if not r['fp_lhs'] and not r['fp_rhs']]
loop_stops = sorted([s for s in stops if s.get('on_loop') and s.get('timetabled')], key=lambda s: -s['buses_day'])
top = loop_stops[0]; gap_s = round(3600 / max(1, top['buses_peak']))
n_private = sum(1 for p in poi if p['category'] == 'Private buses')
near = [p for p in poi if p['dist_m'] <= 500 and p['category'] in CATS]
t = contract['traffic']; r500 = lambda n: round(n / 500) * 500
st_low, st_high = r500(t['adt_2025'] - t['diverted_od']), r500(t['adt_2025'] - t['diverted_tollable'])
crit = sc['criteria']; nrat = lambda r: sum(1 for c in crit if c['rating'] == r); checked = len(crit) - nrat('verify')
fmt = lambda n: f'{n:,}'

story = [
 ('Overview', 'A busy loop of streets about to be reshaped by a flyover',
  f"A {loop_m / 1000:.1f} km loop around Madiwala: 100 Feet Road from the Water Tank junction (A) to the Madiwala underpass (B), "
  "Hosur Road up to St John's junction (C), and Sarjapura Road back to A. Along it are St John's Hospital, a school, mosques and "
  "temples, bus stops and busy shops - and inside it, the St John's sports grounds. Loops like this are what the tactical urbanism "
  "guidebooks say to test first. A tolled flyover is due over part of it from 2026."),
 ('Overview', 'Key figures',
  f"{need} safe crossings missing around the loop (none mid-block on any side; the guidebook asks for one every 80-150 m). "
  f"~{fmt(round(bs['buses_day_at_loop_stops'] / 100) * 100)} buses stop on the loop every weekday, up to one every "
  f"{round(3600 / max(s['buses_peak'] for s in stops if s.get('on_loop')))} seconds in the morning peak. "
  f"{fp_below}/{len(fpv)} footpath measurements below standard on 100 Ft Road (none at all at {', '.join(map(str, fp_none))} m). "
  "About half of today's traffic is expected to move up to the flyover."),
 ('Overview', 'Places within a 7 minute walk',
  '; '.join(f"{CAT_LABEL[k]}: {sum(1 for p in near if p['category'] == k)}" for k in CATS) +
  f". {sum(1 for p in near if not p.get('listed'))} are mapped in OpenStreetMap; {sum(1 for p in near if p.get('listed'))} more come from "
  "business listings (Overture Maps and Foursquare) and have not been checked on the ground. Street vendors and tea stalls are still "
  "missing - the site walk will add them."),
 ('Crossing', 'No street-level crossing between the junctions, on any side',
  f"All the mapped street-level crossings are at the three junctions. Away from them, the only way across is by foot over bridge, "
  f"by stairs, near St John's Hospital. In between are bus stops, the hospital, a mosque and a school that people cross to reach "
  f"every day. The guidebook asks for a crossing every 80-150 m on streets like these. Even counting the bridges, that's {need} "
  "missing around the loop. " + ' '.join(f"{n}: {L} m long, no crossing for {lg} m, {nd} missing." for _, n, L, lg, nd in sides) +
  f" On 100 Feet Road the flyover ramp wall fills the middle of the road, so new crossings there can only go {feas['from_m']}-{feas['to_m']} m "
  "from the Water Tank junction. The flyover contract adds crossings only at junctions."),
 ('Crossing', 'How we know this',
  "Existing crossings and side streets: OpenStreetMap. Zebras at junction A are mapped; junctions B and C have signals but no mapped "
  f"crossing on these roads - to check on the walk. Foot over bridges: OpenStreetMap and the metro survey sheets; they count as "
  f"crossing points when measuring the gaps, although stairs rule them out for many people. Ramp wall ({wall['from']}-{wall['to']} m, {wall['width']} m wide): B-SMILE flyover "
  "contract, Schedule A. Crossing spacing of 80-150 m for mixed-use streets: GIZ/MoHUA Tactical Urbanism Guidebook (after IRC 103). "
  "Places people cross to reach: bus stops, side streets and destinations within 80 m of the road."),
 ('Buses', f'A bus every {gap_s} seconds at the busiest stops',
  f"About {fmt(bs['buses_day_at_loop_stops'])} buses stop on the loop on a weekday, on {bs['routes_at_loop_stops']} routes. At "
  f"{top['name']} it's {fmt(top['buses_day'])} a day - {top['buses_peak']} between 8 and 9 am. Every one of those passengers is a "
  f"pedestrian at one end of the trip, and most stops have no safe crossing nearby. {n_private} private bus operators - SRS, KPN, VRL, "
  "Kerala Lines, FlixBus and more - line Hosur Road near Madiwala. Inter-city passengers with luggage gather here in the evenings, "
  "on the same narrow footpaths."),
 ('Buses', 'Stops on the loop (buses per weekday)',
  '; '.join(f"{s['name']} ({ROADS[s['side']][0]}): {fmt(s['buses_day'])}, {s['buses_peak']} in the 8-9 am hour, {s['n_routes']} routes" for s in loop_stops)),
 ('Buses', 'How we know this',
  "Routes, stops and timetables: unofficial BMTC GTFS feed by Vonter, built from the Namma BMTC 2.0 app (ODbL), for a typical weekday. "
  "The app is known to have timetable errors, so treat counts as indicative. Stop positions cross-checked with the Karnataka GIS (KGIS) "
  f"BMTC stop layer published by OpenCity: {sum(1 for s in stops if s.get('confirmed') and s.get('timetabled'))} of "
  f"{sum(1 for s in stops if s.get('timetabled'))} timetabled stops match a KGIS stop within 60 m. "
  f"{sum(1 for s in stops if not s.get('timetabled'))} KGIS stops have no buses timetabled. Route lines are the bus paths inside the "
  "7-minute-walk area, simplified; overlapping routes on the same path are merged. The data has no southbound buses on Hosur Road "
  "between St John's and Madiwala and very few on 100 Feet Road towards Madiwala - worth checking on the walk."),
 ('Footpaths', "100 Feet Road's footpaths are narrow - and vanish beside the ramp wall",
  f"Footpaths were measured every 100 m. {fp_below} of {len(fpv)} measurements are narrower than the 2.5 m a busy street needs, and at "
  f"{', '.join(map(str, fp_none))} m there is no footpath on either side, so people walk in the road. Hosur Road and Sarjapura Road "
  "weren't part of this survey - the site walk will measure them."),
 ('Footpaths', 'How we know this',
  "Widths: chainage-wise survey in the B-SMILE flyover contract (Schedule A, Annex I). To be spot-checked on the walk. Standard: IRC 103 "
  "via the GIZ/MoHUA guidebook - 2.5 m for mixed-use streets, 1.8 m minimum anywhere. The contract labels sides LHS/RHS; we read LHS as "
  "the IIA side (left when walking from A to B). At 300 m the survey records the road as undivided, while the contract's drawing near "
  "there shows a median - another thing to check."),
 ('Street', 'The flyover contract disagrees with itself',
  "Its drawing keeps almost all the road for vehicles. Its written text describes a much narrower road with wider footpaths. The "
  "street-level design is still to be finalised - a low-cost trial now can show which works. See the Street sections table."),
 ('Street', 'Why a narrower road could work',
  f"About {fmt(t['adt_2025'])} vehicles a day use this corridor now. The flyover's traffic study expects {fmt(t['diverted_tollable'])}-"
  f"{fmt(t['diverted_od'])} of them to use the tolled flyover from {t['toll_from']}, leaving roughly {fmt(st_low)}-{fmt(st_high)} at street "
  "level - about half of today."),
 ('Site check', f'Is the site ready for a trial? {checked} of {len(crit)} checks done',
  f"The guidebook's site checklist: {nrat('favourable')} good, {nrat('acceptable')} okay, {nrat('not_favourable')} a concern, "
  f"{nrat('verify')} not checked. Each item is in the Site checklist table with the finding and its source."),
 ('About the data', 'Sources',
  "DULT (Govt. of Karnataka) Guidebook for Tactical Urbanism, 2022. GIZ/MoHUA A Tactical Urbanism Guidebook, 2020 (site scoring, "
  "crossing spacing, footpath widths after IRC 103). B-SMILE elevated-corridor tender, Schedules A-I, and its OD & toll analysis. "
  "OpenStreetMap contributors (ODbL). Overture Maps Foundation (CDLA-Permissive-2.0), confidence 0.5 or above plus all schools, health "
  "facilities and places of worship. Foursquare Open Source Places (Apache 2.0), listings updated since 2024. Buses: BMTC GTFS by "
  "Vonter (ODbL) with KGIS stop positions via OpenCity. Esri World Imagery."),
 ('About the data', 'Known gaps',
  "Business listings (shown as rings) are not checked on the ground. No source covers street vendors, tea stalls or informal stops. "
  "The contract is a tender: chainages and designs may change. The width survey covers 100 Feet Road only. Footpath sides are inferred "
  "from LHS/RHS labels. Traffic figures cover the whole Indiranagar-Silk Board corridor and are projections. Bus timetables come from "
  f"BMTC's app and are indicative. {nrat('verify')} site-check items are not yet checked. Distances along each road are measured from "
  "its first junction (A, B or C)."),
]
table('story', [('n', I), ('tab', S), ('heading', S), ('text', S)], [(i + 1, *r) for i, r in enumerate(story)])
table('buses_by_road', [('road', S), ('direction', S), ('buses_per_weekday', I)],
      [(n, f'{JN[x]} ({x}) to {JN[y]} ({y})', bs['sides'].get(f'{sid}:{x}>{y}', 0))
       for sid, (n, a, b, *_ ) in ROADS.items() for x, y in ((a, b), (b, a))])
table('footpath_survey_100ft', [('m_from_A', I), ('footpath_iia_side_m', D), ('footpath_masjid_side_m', D),
                                ('vehicle_lanes_and_middle', S), ('wall_to_wall_m', D)],
      [(r['ch'], r['fp_lhs'], r['fp_rhs'],
        f"{r['cw_lhs']} + {r['median']} + {r['cw_rhs']} m" if r.get('cw_lhs') is not None else f"{r['cw_total']} m, undivided", r['row'])
       for r in rows])
why = {'existing': 'Most of the width goes to vehicles.', 'tcs09': "Same footpaths as today; vehicles keep almost everything.",
       'text': 'A narrow road with wide footpaths - but where the other 12 m goes is not said.',
       'tactical': 'Two lanes each way, wider footpaths and space for bus stops and vendors - testable in a week with cones and paint.'}
table('street_sections', [('section', S), ('what_it_means', S), ('layout_left_to_right', S), ('source', S)],
      [(it['title'], why.get(it['id'], ''), ' | '.join(f"{p[2]} {p[1]} m" for p in it['parts']), it.get('ref', ''))
       for it in contract['sections']['items']])
table('site_checklist', [('question', S), ('rating', S), ('suggested', S), ('finding', S), ('source', S)],
      [(c['question'], sc['ratings'][c['rating']], sc['ratings'].get(c.get('suggested'), '') if c.get('suggested') else '',
        c['finding'], c['source']) for c in crit])

# ================================================================ project
proj = QgsProject.instance()
proj.clear()
proj.setTitle('Madiwala loop - study map and proposals')
proj.setCrs(QgsCoordinateReferenceSystem('EPSG:3857'))
Shape = Qgis.MarkerShape
expr = QgsProperty.fromExpression

def load(name, title, tip=None, display=None):
    lyr = QgsVectorLayer(f'{OUT}|layername={name}', title, 'ogr')
    if not lyr.isValid(): sys.exit(f'cannot load {name} from the GeoPackage')
    proj.addMapLayer(lyr, False)
    if tip: lyr.setMapTipTemplate(tip)
    if display: lyr.setDisplayExpression(display)
    return lyr

def marker(color, size, shape=Shape.Circle, stroke='#ffffff', stroke_w=0.4):
    sl = QgsSimpleMarkerSymbolLayer(shape, size)
    sl.setColor(QColor(color)); sl.setStrokeColor(QColor(stroke)); sl.setStrokeWidth(stroke_w)
    return QgsMarkerSymbol([sl])

def line_sym(lyr, layers):
    s = QgsSymbol.defaultSymbol(lyr.geometryType()); s.deleteSymbolLayer(0)
    for color, width, opacity, dash in layers:
        sl = QgsSimpleLineSymbolLayer(QColor(color), width)
        c = QColor(color); c.setAlphaF(opacity); sl.setColor(c)
        sl.setPenCapStyle(Qt.PenCapStyle.RoundCap)
        if dash == 'dash': sl.setPenStyle(Qt.PenStyle.DashLine)
        elif dash == 'dot': sl.setPenStyle(Qt.PenStyle.DotLine)
        elif dash == 'stripe':
            sl.setUseCustomDashPattern(True); sl.setCustomDashVector([0.6, 0.6]); sl.setPenCapStyle(Qt.PenCapStyle.FlatCap)
        s.appendSymbolLayer(sl)
    return s

def label(lyr, ex, size=8, color='#212529', max_scale=None, placement=None, bold=False, buffer=True):
    pal = QgsPalLayerSettings(); pal.fieldName = ex; pal.isExpression = True
    if max_scale: pal.scaleVisibility = True; pal.maximumScale = 0; pal.minimumScale = max_scale
    if placement is not None: pal.placement = placement
    f = QFont('Sans Serif'); f.setBold(bold)
    fmt_ = QgsTextFormat(); fmt_.setFont(f); fmt_.setSize(size); fmt_.setColor(QColor(color))
    if buffer:
        b = QgsTextBufferSettings(); b.setEnabled(True); b.setSize(1); b.setColor(QColor('white')); fmt_.setBuffer(b)
    pal.setFormat(fmt_)
    lyr.setLabeling(QgsVectorLayerSimpleLabeling(pal)); lyr.setLabelsEnabled(True)

def categorized(lyr, field, cats):            # cats: [(value, label, symbol)]
    lyr.setRenderer(QgsCategorizedSymbolRenderer(field, [QgsRendererCategory(v, s, l) for v, l, s in cats]))

def value_map(lyr, field, values, alias=None):
    idx = lyr.fields().indexOf(field)
    lyr.setEditorWidgetSetup(idx, QgsEditorWidgetSetup('ValueMap', {'map': [{str(v): v} for v in values]}))
    if alias: lyr.setFieldAlias(idx, alias)

# ---------------------------------------------------------------- proposals (editable)
pts = load('proposed_points', 'Proposed changes (points)', display='"change_type"')
lines = load('proposed_lines', 'Proposed changes (lines)', display='"change_type"')
about = load('about_this_proposal', 'About this proposal (one row: title, your name)')
categorized(pts, 'change_type', [(v, v, marker(c, 4.2, stroke='white', stroke_w=0.6)) for v, c in zip(POINT_TYPES, POINT_COLOURS)])
categorized(lines, 'change_type', [(v, v, line_sym(lines, [(c, 1.6, 1, None)])) for v, c in zip(LINE_TYPES, LINE_COLOURS)])
value_map(pts, 'change_type', POINT_TYPES, 'What change?')
value_map(pts, 'cycle_s', [60, 75, 90, 120], 'Signal cycle (seconds) - crossings and signal timing only')
value_map(pts, 'ped_green_s', [12, 18, 24, 30], 'Pedestrian green (seconds) - crossings and signal timing only')
value_map(lines, 'change_type', LINE_TYPES, 'What change?')
value_map(lines, 'lanes', [1, 2], 'Lanes to remove - lane closures only')
lines.setFieldAlias(lines.fields().indexOf('width_m'), 'New footpath width (m) - footpaths only')
for lyr in (pts, lines):
    i = lyr.fields().indexOf('change_type')
    lyr.setFieldConstraint(i, QgsFieldConstraints.Constraint.ConstraintNotNull, QgsFieldConstraints.ConstraintStrength.ConstraintStrengthHard)
    lyr.setFieldAlias(lyr.fields().indexOf('notes'), 'Notes (why, anything we should know)')
    lyr.setFieldAlias(lyr.fields().indexOf('proposed_by'), 'Your name')
    lyr.setDefaultValueDefinition(lyr.fields().indexOf('proposed_by'), QgsDefaultValue('@user_full_name'))
    lyr.setMapTipTemplate('<strong>[% "change_type" %]</strong><br>[% "notes" %]<br>' + SMALL + 'Proposed by [% "proposed_by" %]</span>')
    label(lyr, '"change_type"', 8, '#343a40')

ex = load('example_trial_crossings', 'Example: the study\'s 8 trial crossings', display='"notes"',
          tip='<strong>Trial crossing (study proposal)</strong><br>[% "notes" %]<br>' + SMALL +
              'Signalised, [% "cycle_s" %] s cycle, [% "ped_green_s" %] s pedestrian green</span>')
ex.setRenderer(QgsSingleSymbolRenderer(marker('#d0bfff', 3.4, Shape.Square, '#7048e8', 0.5)))

# ---------------------------------------------------------------- crossings study (website: Crossing tab)
junc = load('junctions', 'Junctions A, B, C', display='"id" || \' - \' || "name"',
            tip='<strong>[% "id" %] - [% "name" %]</strong><br>' + SMALL + '[% "note" %]</span>')
junc.setRenderer(QgsSingleSymbolRenderer(marker('#1d1d1b', 6.5, stroke='#ffffff', stroke_w=0.6)))
label(junc, '"id"', 9, '#ffffff', placement=Qgis.LabelPlacement.OverPoint, bold=True, buffer=False)

xing = load('existing_crossings', 'Existing crossings (green = marked zebra, blue = foot over bridge)', display='"name"',
            tip='<strong>[% "name" %]</strong><br>[% if("fob", \'Stairs up and over the road. Not step-free.\', if("verified", \'Marked zebra crossing\', replace("type", \' in OSM\', \' on the map\') || \' - to check on the walk\')) %]'
                f'<br>{SMALL}[% map_get({ROAD_NAME}, "side") %]</span>')
s = marker('#ffffff', 3.6, stroke='#1d1d1b', stroke_w=0.8)
s.symbolLayer(0).setDataDefinedProperty(QgsSymbolLayer.Property.FillColor, expr("if(\"fob\", '#74c0fc', if(\"verified\", '#2f9e44', '#ffffff'))"))
s.symbolLayer(0).setDataDefinedProperty(QgsSymbolLayer.Property.StrokeColor, expr("if(\"fob\", '#1864ab', if(\"verified\", '#1b7a3a', '#1d1d1b'))"))
xing.setRenderer(QgsSingleSymbolRenderer(s))

gen = load('places_people_cross_to', 'Places people cross the road to reach', display='"name"',
           tip=f'<strong>[% "name" %]</strong><br>People cross [% map_get({ROAD_NAME}, "side") %] to reach this<br>{SMALL}'
               f'[% "chainage_m" %] m from the [% map_get({ROAD_START}, "side") %] - '
               f'[% coalesce(map_get(map_get({ROAD_SIDE}, "side"), "road_side"), "road_side") %]</span>')
gen.setRenderer(QgsSingleSymbolRenderer(marker('#ffffff', 2.6, stroke='#7048e8', stroke_w=0.8)))
label(gen, '"name"', 7, '#5f3dc4', max_scale=5000)

gaps_l = load('gaps_without_crossings', 'Stretches with no crossing', display='"length_m" || \' m with no crossing\'',
              tip=f'<strong>[% "length_m" %] m of [% map_get({ROAD_NAME}, "side") %] with no crossing</strong><br>{SMALL}'
                  'The guidebook asks for one every 80-150 m on a busy street like this.</span>')
categorized(gaps_l, 'status', [('too-long', 'Too long without a crossing', line_sym(gaps_l, [('#c92a2a', 1.4, 0.9, None)])),
                               ('residential-only', 'Residential frontage only', line_sym(gaps_l, [('#e8a200', 1.4, 0.9, None)])),
                               ('ok', 'Within guidance', line_sym(gaps_l, [('#2f9e44', 1.4, 0.9, None)]))])
label(gaps_l, '"length_m" || \' m with no crossing\'', 8, '#c92a2a', placement=Qgis.LabelPlacement.Line, bold=True)

desire = load('desire_lines', 'Desire lines (where people want to cross)',
              tip='<strong>Where people want to cross</strong><br>' + SMALL + 'From the nearest footpath to a place people cross to reach</span>')
desire.setRenderer(QgsSingleSymbolRenderer(line_sym(desire, [('#7048e8', 0.45, 1, 'dash')])))

ticks = load('distance_ticks', 'Distance along each road (m)', display='"chainage_m" || \' m\'',
             tip=f'<strong>[% map_get({ROAD_NAME}, "side") %]</strong><br>[% "chainage_m" %] m from the [% map_get({ROAD_START}, "side") %]')
s = marker('#ffffff', 1.6, stroke='#1d1d1b', stroke_w=0.5)
s.symbolLayer(0).setDataDefinedProperty(QgsSymbolLayer.Property.Size, expr('if("major", 2.2, 1.6)'))
ticks.setRenderer(QgsSingleSymbolRenderer(s))
label(ticks, 'if("major", "chainage_m" || \' m\', \'\')', 7, '#1d1d1b', max_scale=6000)

# ---------------------------------------------------------------- flyover contract (website: Footpaths / Street tabs)
wall_l = load('flyover_ramp_wall', 'Flyover ramp wall - no crossing possible',
              tip='<strong>Flyover ramp wall</strong><br>A solid [% "width_m" %] m wall of packed earth down the middle of the road, '
                  '[% "from_m" %]-[% "to_m" %] m from the Water Tank junction. No one can cross here.')
ws = QgsSymbol.defaultSymbol(wall_l.geometryType()); ws.setColor(QColor('#6b5a49')); ws.setOpacity(0.6)
ws.symbolLayer(0).setStrokeColor(QColor('#3d3227')); wall_l.setRenderer(QgsSingleSymbolRenderer(ws))

zones = load('crossing_zones_100ft', 'Where a crossing can go on 100 Ft Road', display='"name"',
             tip="[% if(\"status\" = 'feasible', '<strong>A crossing is possible here</strong><br>" + SMALL +
                 "' || \"from_m\" || '-' || \"to_m\" || ' m from the Water Tank junction. The middle of the road is open, so a crossing "
                 "with a safe island in the middle can fit.</span>', '<strong>No crossing possible</strong><br>" + SMALL +
                 "The flyover ramp wall fills the middle of the road here.</span>') %]")
categorized(zones, 'status', [('feasible', 'A new crossing could go here', line_sym(zones, [('#2f9e44', 4.0, 0.4, None)])),
                              ('blocked', 'Blocked by the ramp wall', line_sym(zones, [('#6b5a49', 4.0, 0.5, None)]))])

fpw = load('footpath_widths', 'Footpath widths on 100 Ft Road (survey)', display='"fp_m" || \' m\'',
           tip=f'<strong>[% if("fp_m" > 0, \'Footpath \' || "fp_m" || \' m wide\', \'No footpath\') %]</strong> - '
               f'[% "side_of_road" %]<br>[% "chainage_m" %] m from the Water Tank junction<br>{SMALL}'
               "Standard for a busy mixed-use street: 2.5 m. Measured in the flyover contract's survey.</span>")
categorized(fpw, 'fp_flag', [('ok', '2.5 m or more - meets the standard', marker('#2f9e44', 3.2, stroke='#1d1d1b')),
                             ('below-2.5', '1.8-2.5 m - too narrow for a busy street', marker('#fab005', 3.2, stroke='#1d1d1b')),
                             ('below-1.8', 'Under 1.8 m - below the minimum', marker('#f76707', 3.2, stroke='#1d1d1b')),
                             ('none', 'No footpath', marker('#c92a2a', 3.2, stroke='#1d1d1b'))])
label(fpw, "if(\"fp_m\" = 0, 'no footpath', \"fp_m\" || ' m')", 8, '#1d1d1b', max_scale=4000, bold=True)

uc = load('under_construction', 'Ejipura flyover - under construction', display='"name"',
          tip='<strong>Ejipura flyover - under construction</strong><br>[% if("elevated", \'Raised section, heading north-east to Ejipura\', '
              '\'Ramp coming down to street level\') %]<br>' + SMALL + 'From OpenStreetMap ([% "osm" %])</span>')
uc.setRenderer(QgsSingleSymbolRenderer(line_sym(uc, [('#ffffff', 2.6, 0.95, None), ('#f59f00', 1.8, 1, None), ('#1d1d1b', 1.8, 1, 'stripe')])))
label(uc, "if(\"elevated\", 'Ejipura flyover - under construction', '')", 8, '#7a4a00', placement=Qgis.LabelPlacement.Line, bold=True)

# ---------------------------------------------------------------- buses (website: Buses tab)
bus = load('bus_stops', 'Bus stops (bigger = more buses; hollow = no timetable)', display='"name"',
           tip='[% if("timetabled", '
               "'<strong>' || \"name\" || '</strong> bus stop<br><strong>' || format_number(\"buses_day\", 0) || '</strong> buses a weekday - ' "
               "|| \"buses_peak\" || ' between 8 and 9 am<br>" + SMALL + "' || \"n_routes\" || ' routes: ' || " + ROUTES +
               " || '</span><br>" + SMALL + "From ' || \"source\" || ' - timetables are indicative</span>', "
               "'<strong>' || \"name\" || '</strong> bus stop<br>' || if(left(\"source\", 13) = 'OpenStreetMap', "
               "'Mapped in OpenStreetMap - often the stop on the other side of the road from a timetabled one.', "
               "'Listed in the government (KGIS) stop layer, but no buses are timetabled here in the BMTC app data.') || "
               "'<br>" + SMALL + "No timetable - check on the walk whether it''s in use.</span>') %]")
s = marker('#1c7ed6', 3, stroke='#ffffff', stroke_w=0.7)
s.symbolLayer(0).setDataDefinedProperty(QgsSymbolLayer.Property.Size, expr(
    'CASE WHEN coalesce("buses_day", 0) <= 100 THEN scale_linear(coalesce("buses_day", 0), 0, 100, 2.6, 3.6) '
    'WHEN "buses_day" <= 500 THEN scale_linear("buses_day", 100, 500, 3.6, 5.2) ELSE scale_linear("buses_day", 500, 1700, 5.2, 8.8) END'))
s.symbolLayer(0).setDataDefinedProperty(QgsSymbolLayer.Property.FillColor, expr("if(\"timetabled\", '#1c7ed6', '#ffffff')"))
s.symbolLayer(0).setDataDefinedProperty(QgsSymbolLayer.Property.StrokeColor, expr("if(\"timetabled\", '#ffffff', '#1c7ed6')"))
bus.setRenderer(QgsSingleSymbolRenderer(s))
label(bus, "if(\"timetabled\", \"name\" || '\n' || \"buses_day\" || ' buses/day', '')", 7.5, '#0b4f8a', max_scale=6000, bold=True)

routes = load('bus_routes', 'Bus routes (thicker = more buses)',
              tip='<strong>Bus routes on this road</strong><br>About <strong>[% format_number("buses_day", 0) %]</strong> buses a weekday on this path'
                  '<br>' + SMALL + '[% "n_routes" %] routes: [% ' + ROUTES + ' %]</span>')
rs = line_sym(routes, [('#ffffff', 1.4, 0.8, None), ('#1c7ed6', 0.6, 0.7, None)])
wexpr = ('CASE WHEN "buses_day" <= 300 THEN scale_linear("buses_day", 0, 300, 0.4, 1.05) '
         'ELSE scale_linear("buses_day", 300, 1500, 1.05, 3.2) END')
rs.symbolLayer(0).setDataDefinedProperty(QgsSymbolLayer.Property.StrokeWidth, expr(f'({wexpr}) + 0.8'))
rs.symbolLayer(1).setDataDefinedProperty(QgsSymbolLayer.Property.StrokeWidth, expr(wexpr))
routes.setRenderer(QgsSingleSymbolRenderer(rs))

POI_TIP = ('<strong>[% "name" %]</strong><br>[% "type" %] - [% {cat} %]<br>' + SMALL + 'About [% "dist_m" %] m from the road</span>'
           '[% if("hours" IS NOT NULL, \'<br><strong>Open:</strong> \' || "hours" || if("hours_note" IS NOT NULL, \'<br>' + SMALL +
           '\' || "hours_note" || \'</span>\', \'\'), \'\') %]<br>' + SMALL +
           '[% if("listed", \'Business listing, not checked on the ground\', \'Mapped place\') %] - from '
           '[% regexp_replace(coalesce(array_to_string(coalesce(try(from_json("sources")), "sources"), \', \'), "source"), \'[\\\\[\\\\]"]\', \'\') %]</span>')
priv = load('private_bus_operators', 'Private bus operators (offices and boarding points)', display='"name"',
            tip=POI_TIP.replace('{cat}', "'Private bus operator'"))
priv.setRenderer(QgsSingleSymbolRenderer(marker(PRIVATE_BUS, 2.6, stroke='#ffffff', stroke_w=0.5)))
label(priv, '"name"', 7, '#8a3204', max_scale=2500)

# ---------------------------------------------------------------- places and walking distance (website: Overview tab)
places = load('places_nearby', 'Places nearby (ring = business listing, not checked)', display='"name"',
              tip=POI_TIP.replace('{cat}', f"coalesce(map_get({qmap(CAT_LABEL)}, \"category\"), \"category\")"))
root_rule = QgsRuleBasedRenderer.Rule(None)
for cat, col in CATS.items():
    size = 1.6 if cat == 'Commercial' else 2.4
    r = QgsRuleBasedRenderer.Rule(None, 0, 0, f"\"category\" = '{cat}'", CAT_LABEL[cat])
    r.appendChild(QgsRuleBasedRenderer.Rule(marker(col, size, stroke='#ffffff', stroke_w=0.4), 0, 0, 'NOT coalesce("listed", false)', 'Mapped place'))
    r.appendChild(QgsRuleBasedRenderer.Rule(marker('#ffffff', size, stroke=col, stroke_w=0.55), 0, 0, 'coalesce("listed", false)', 'Business listing'))
    root_rule.appendChild(r)
places.setRenderer(QgsRuleBasedRenderer(root_rule))
label(places, "if(\"category\" = 'Commercial', '', \"name\")", 7, '#222222', max_scale=4000)

rings = load('walking_distance', 'Walking distance from the loop (4 and 7 minutes)', display='"label"')
rr = line_sym(rings, [('#ffffff', 1.3, 0.55, None), ('#1d1d1b', 0.65, 0.75, 'dot')])
fs = QgsSymbol.defaultSymbol(rings.geometryType()); fs.deleteSymbolLayer(0)
for i in range(rr.symbolLayerCount()): fs.appendSymbolLayer(rr.symbolLayer(i).clone())
rings.setRenderer(QgsSingleSymbolRenderer(fs))
label(rings, '"label"', 8.5, '#1d1d1b', placement=Qgis.LabelPlacement.Line, bold=True)

# ---------------------------------------------------------------- the loop itself
roads = load('loop_roads', 'The study loop (arrows show traffic direction)', display='"name"',
             tip='<strong>[% "name" %]</strong><br>[% "direction" %]<br>' + SMALL +
                 '[% if("lanes" IS NOT NULL, "lanes" || \' lanes, \', \'\') %]one-way - [% "length_m" %] m</span>')
rs = line_sym(roads, [('#e4572e', 5.0, 0.2, None), ('#e4572e', 1.1, 1, None)])
arrow = QgsMarkerLineSymbolLayer(True, 18)
arrow.setPlacements(Qgis.MarkerLinePlacement.Interval)
am = marker('#ffffff', 1.6, Shape.ArrowHeadFilled, '#ffffff', 0); arrow.setSubSymbol(am)
rs.appendSymbolLayer(arrow)
roads.setRenderer(QgsSingleSymbolRenderer(rs))

# ---------------------------------------------------------------- tables
tables = {}
for name, title, disp in (('story', 'Story: the website text, by tab', '"tab" || \': \' || "heading"'),
                          ('buses_by_road', 'Buses along each road, by direction', '"road"'),
                          ('footpath_survey_100ft', 'Footpath survey, 100 Ft Road (every 100 m)', '"m_from_A"'),
                          ('street_sections', 'Street sections: today, contract, trial', '"section"'),
                          ('site_checklist', 'Site checklist (guidebook)', '"question"')):
    tables[name] = load(name, title, display=disp)

study = [ex, junc, xing, gen, gaps_l, desire, ticks, wall_l, zones, fpw, uc, bus, routes, priv, places, rings, roads, *tables.values()]
for lyr in study: lyr.setReadOnly(True)

osm = QgsRasterLayer('type=xyz&url=https://tile.openstreetmap.org/{z}/{x}/{y}.png&zmin=0&zmax=19', 'OpenStreetMap', 'wms')
osm.setOpacity(0.8)
sat = QgsRasterLayer('type=xyz&url=https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
                     '&zmin=0&zmax=19', 'Satellite (Esri World Imagery)', 'wms')
for r in (osm, sat): proj.addMapLayer(r, False)

# ---------------------------------------------------------------- layer tree
root = proj.layerTreeRoot()
GROUPS = [('Your proposals - draw here', [pts, lines, about], True),
          ('Example scenario', [ex], False),
          ('Crossings', [junc, xing, gen, ticks, desire, gaps_l, zones], True),
          ('Footpaths and the flyover', [fpw, wall_l, uc], False),
          ('Buses', [bus, priv, routes], False),
          ('Places and walking distance', [places, rings], False),
          ('The study loop', [roads], False),
          ('Story, figures and checklist (tables)', list(tables.values()), False),
          ('Background', [osm, sat], False)]
nodes = {}
for title, layers, expanded in GROUPS:
    g = root.addGroup(title); g.setExpanded(expanded)
    for lyr in layers: nodes[lyr] = g.addLayer(lyr)

# map themes = the website's tabs (plus one for drawing). Always on: proposals, junctions, the loop, background map.
ALWAYS = {pts, lines, about, junc, roads, osm, *tables.values()}
THEMES = {
    'Overview': {rings, places, uc},
    'Crossing': {zones, gaps_l, desire, ticks, gen, xing, wall_l},
    'Buses': {bus, routes, priv},
    'Footpaths': {fpw, wall_l},
    'Street': {uc, wall_l},
    'Site check': {uc},
    'Draw proposals': {ex, zones, gaps_l, gen, xing, wall_l, bus, ticks},
}
model = QgsLayerTreeModel(root)
mtc = proj.mapThemeCollection()
for name, on in THEMES.items():
    for lyr, node in nodes.items(): node.setItemVisibilityChecked(lyr in on or lyr in ALWAYS)
    for g in root.findGroups(): g.setItemVisibilityChecked(True)
    mtc.insert(name, QgsMapThemeCollection.createThemeFromCurrentState(root, model))
# open in the drawing view
for lyr, node in nodes.items(): node.setItemVisibilityChecked(lyr in THEMES['Draw proposals'] or lyr in ALWAYS)

notes = {pts: 'Click the pencil, then Add Point. Pick what the change is from the list.',
         tables['story']: 'The text of the study website, tab by tab. Right-click > Open Attribute Table to read it.',
         tables['site_checklist']: "The guidebook's 13-question site checklist, with what maps and documents suggest."}
for lyr, n in notes.items(): QgsLayerNotesUtils.setLayerNotes(lyr, n)

for lyr in (pts, lines, *[l for l in study if l.isSpatial()]):
    lyr.saveStyleToDatabaseV2(lyr.name()[:30], 'Madiwala template style', True, '')

# snapping onto the roads, junctions, crossings and distance ticks only (not onto every shop)
sc_ = QgsSnappingConfig(proj); sc_.setEnabled(True); sc_.setMode(Qgis.SnappingMode.AdvancedConfiguration)
for lyr in proj.mapLayers().values():
    if isinstance(lyr, QgsVectorLayer) and lyr.isSpatial():
        sc_.setIndividualLayerSettings(lyr, QgsSnappingConfig.IndividualLayerSettings(
            lyr in (roads, junc, xing, ticks, pts, lines), Qgis.SnappingType.Vertex | Qgis.SnappingType.Segment,
            12, Qgis.MapToolUnit.Pixels, 0, 0))
proj.setSnappingConfig(sc_)

ext = rings.extent(); ext.grow(0.0003)                     # open on the whole 500 m walking area
proj.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(ext, WGS84))
proj.writeEntryBool('Paths', '/Absolute', False)            # find the .gpkg next to the project, wherever unzipped
if not proj.write(QGZ): sys.exit('could not save the project')
with open(os.path.join(PKG, 'READ ME FIRST.txt'), 'w') as f:
    f.write(open(os.path.join(HERE, 'planner_instructions.txt')).read())
n_layers, n_themes = len(proj.mapLayers()), len(mtc.mapThemes())
qgs.exitQgis()
if os.path.exists(ZIP): os.remove(ZIP)
with zipfile.ZipFile(ZIP, 'w', zipfile.ZIP_DEFLATED) as z:
    for n in sorted(os.listdir(PKG)): z.write(os.path.join(PKG, n), os.path.join('madiwala_proposals', n))
print(f'wrote {ZIP} ({os.path.getsize(ZIP) // 1024} KB): {n_layers} layers, {n_themes} map themes; study data from {DATA}')
sys.exit(0)
