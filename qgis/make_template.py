#!/usr/bin/env python3
"""Build qgis/madiwala_proposals.zip: the template to send to planners.

The zip holds one folder with
  madiwala.qgz              the QGIS project (double-click to open): styles, drop-downs, background map, snapping
  madiwala_proposals.gpkg   all data: study layers (locked), the 8 trial crossings as an example,
                            and empty layers for proposals
Planners draw, save, and send back the .gpkg (renaming it then is fine). The project finds the data
by file name, so the files inside the folder must not be renamed while working.

Run with the system Python that has PyQGIS (installed with QGIS), not the project venv:
    python3 qgis/make_template.py
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PKG = os.path.join(HERE, 'madiwala_proposals')
OUT = os.path.join(PKG, 'madiwala_proposals.gpkg')
QGZ = os.path.join(PKG, 'madiwala.qgz')
ZIP = os.path.join(HERE, 'madiwala_proposals.zip')

from qgis.PyQt.QtCore import QMetaType
from qgis.PyQt.QtGui import QColor, QFont
from qgis.core import (
    Qgis, QgsApplication, QgsProject, QgsVectorLayer, QgsRasterLayer, QgsField, QgsFeature, QgsGeometry,
    QgsPointXY, QgsVectorFileWriter, QgsCoordinateReferenceSystem, QgsEditorWidgetSetup, QgsSymbol,
    QgsRendererCategory, QgsCategorizedSymbolRenderer, QgsSingleSymbolRenderer, QgsPalLayerSettings,
    QgsTextFormat, QgsTextBufferSettings, QgsVectorLayerSimpleLabeling, QgsSnappingConfig, QgsTolerance,
    QgsReferencedRectangle, QgsRectangle, QgsFieldConstraints, QgsDefaultValue, QgsMapLayer)

qgs = QgsApplication([], False)
qgs.initQgis()
WGS84 = QgsCoordinateReferenceSystem('EPSG:4326')

# ---------------------------------------------------------------- choices offered to planners
POINT_TYPES = ['Signalised crossing', 'Zebra crossing', 'Remove crossing', 'Move or add bus stop',
               'Turn ban', 'Signal timing', 'New destination', 'Other (describe in notes)']
LINE_TYPES = ['Close lanes', 'Widen footpath', 'New footpath', 'Pedestrianise', 'Other (describe in notes)']
POINT_COLOURS = ['#7048e8', '#1c7ed6', '#e03131', '#f08c00', '#c2255c', '#2f9e44', '#0c8599', '#495057']
LINE_COLOURS = ['#e03131', '#2f9e44', '#0c8599', '#f08c00', '#495057']
CYCLES = [60, 75, 90, 120]
PED_GREENS = [12, 18, 24, 30]

# ---------------------------------------------------------------- write layers into the GeoPackage
import shutil, zipfile
shutil.rmtree(PKG, ignore_errors=True); os.makedirs(PKG)
first = [True]

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
    lyr = QgsVectorLayer(os.path.join(ROOT, 'inputs', fname) + f'|geometrytype={geom}', name, 'ogr')
    if not lyr.isValid(): sys.exit(f'cannot read inputs/{fname}')
    if subset: lyr.setSubsetString(subset)
    write(lyr, name)

def empty(geom, name, fields):
    lyr = QgsVectorLayer(f'{geom}?crs=EPSG:4326', name, 'memory')
    lyr.dataProvider().addAttributes([QgsField(n, t) for n, t in fields]); lyr.updateFields()
    write(lyr, name)

S, I, D = QMetaType.Type.QString, QMetaType.Type.Int, QMetaType.Type.Double
empty('Point', 'proposed_points', [('change_type', S), ('cycle_s', I), ('ped_green_s', I), ('notes', S), ('proposed_by', S)])
empty('LineString', 'proposed_lines', [('change_type', S), ('lanes', I), ('width_m', D), ('notes', S), ('proposed_by', S)])
empty('NoGeometry', 'about_this_proposal', [('title', S), ('description', S), ('proposed_by', S), ('contact', S), ('date', S)])

# example scenario: the 8 trial crossings, in the same form a planner would draw them
ex = QgsVectorLayer('Point?crs=EPSG:4326', 'x', 'memory')
ex.dataProvider().addAttributes([QgsField(n, t) for n, t in
                                 [('change_type', S), ('cycle_s', I), ('ped_green_s', I), ('notes', S), ('proposed_by', S)]])
ex.updateFields()
cfg = json.load(open(os.path.join(ROOT, 'config', 'assumptions.json')))
names = {'AB': '100 Feet Road', 'BC': 'Hosur Road', 'CA': 'Sarjapura Road'}
feats = []
for f in json.load(open(os.path.join(ROOT, 'report', 'results.geojson')))['features']:
    p = f['properties']
    if p.get('kind') != 'trial_crossing': continue
    q = QgsFeature(ex.fields())
    q.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(*f['geometry']['coordinates'])))
    q.setAttributes(['Signalised crossing', cfg['signals']['midblock_cycle_s'], cfg['signals']['midblock_ped_green_s'],
                     f"{names[p['side']]}, {p['dist_from_first_junction_m']} m from {p['side'][0]}", 'Study team'])
    feats.append(q)
ex.dataProvider().addFeatures(feats)
write(ex, 'example_trial_crossings')

from_geojson('stretch.geojson', "\"kind\" = 'carriageway'", 'loop_roads', 'LineString')
from_geojson('stretch.geojson', "\"kind\" = 'junction'", 'junctions', 'Point')
from_geojson('crossings.geojson', "\"kind\" = 'crossing'", 'existing_crossings', 'Point')
from_geojson('crossings.geojson', "\"kind\" = 'gap'", 'gaps_without_crossings', 'LineString')
from_geojson('crossings.geojson', "\"kind\" = 'generator'", 'places_people_cross_to', 'Point')
from_geojson('bus_stops.geojson', None, 'bus_stops', 'Point')

# ---------------------------------------------------------------- project
proj = QgsProject.instance()
proj.clear()
proj.setTitle('Madiwala loop - proposals template')
proj.setCrs(QgsCoordinateReferenceSystem('EPSG:3857'))

def load(name):
    lyr = QgsVectorLayer(f'{OUT}|layername={name}', name.replace('_', ' ').capitalize(), 'ogr')
    if not lyr.isValid(): sys.exit(f'cannot load {name} from the GeoPackage')
    proj.addMapLayer(lyr, False)
    return lyr

def symbol(lyr, **kw):
    s = QgsSymbol.defaultSymbol(lyr.geometryType())
    if 'color' in kw: s.setColor(QColor(kw['color']))
    sl = s.symbolLayer(0)
    if 'width' in kw: sl.setWidth(kw['width'])
    if 'size' in kw: sl.setSize(kw['size'])
    if 'shape' in kw: sl.setShape(kw['shape'])
    if 'stroke' in kw:
        sl.setStrokeColor(QColor(kw['stroke'])); sl.setStrokeWidth(kw.get('stroke_w', 0.4))
    if 'pen' in kw: sl.setPenStyle(kw['pen'])
    if 'opacity' in kw: s.setOpacity(kw['opacity'])
    return s

def label(lyr, expr, size=8, color='#212529', max_scale=None):
    pal = QgsPalLayerSettings(); pal.fieldName = expr; pal.isExpression = True
    if max_scale:                                    # only label when zoomed in closer than 1:max_scale
        pal.scaleVisibility = True; pal.maximumScale = 0; pal.minimumScale = max_scale
    fmt = QgsTextFormat(); fmt.setFont(QFont('Sans Serif')); fmt.setSize(size); fmt.setColor(QColor(color))
    buf = QgsTextBufferSettings(); buf.setEnabled(True); buf.setSize(1); buf.setColor(QColor('white'))
    fmt.setBuffer(buf); pal.setFormat(fmt)
    lyr.setLabeling(QgsVectorLayerSimpleLabeling(pal)); lyr.setLabelsEnabled(True)

def value_map(lyr, field, values, alias=None):
    idx = lyr.fields().indexOf(field)
    lyr.setEditorWidgetSetup(idx, QgsEditorWidgetSetup('ValueMap', {'map': [{str(v): v} for v in values]}))
    if alias: lyr.setFieldAlias(idx, alias)

def categorized(lyr, field, values, colours, **kw):
    cats = [QgsRendererCategory(v, symbol(lyr, color=c, **kw), v) for v, c in zip(values, colours)]
    lyr.setRenderer(QgsCategorizedSymbolRenderer(field, cats))

Shape = Qgis.MarkerShape
# proposals (editable)
pts = load('proposed_points'); lines = load('proposed_lines'); about = load('about_this_proposal')
pts.setName('Proposed changes (points)'); lines.setName('Proposed changes (lines)'); about.setName('About this proposal')
categorized(pts, 'change_type', POINT_TYPES, POINT_COLOURS, size=4.2, stroke='white', stroke_w=0.6)
categorized(lines, 'change_type', LINE_TYPES, LINE_COLOURS, width=1.6)
value_map(pts, 'change_type', POINT_TYPES, 'What change?')
value_map(pts, 'cycle_s', CYCLES, 'Signal cycle (seconds) - crossings and signal timing only')
value_map(pts, 'ped_green_s', PED_GREENS, 'Pedestrian green (seconds) - crossings and signal timing only')
value_map(lines, 'change_type', LINE_TYPES, 'What change?')
value_map(lines, 'lanes', [1, 2], 'Lanes to remove - lane closures only')
for lyr in (pts, lines):
    i = lyr.fields().indexOf('change_type')
    lyr.setFieldConstraint(i, QgsFieldConstraints.Constraint.ConstraintNotNull, QgsFieldConstraints.ConstraintStrength.ConstraintStrengthHard)
    lyr.setFieldAlias(lyr.fields().indexOf('notes'), 'Notes (why, anything we should know)')
    lyr.setFieldAlias(lyr.fields().indexOf('proposed_by'), 'Your name')
    lyr.setDefaultValueDefinition(lyr.fields().indexOf('proposed_by'), QgsDefaultValue("@user_full_name"))
    lyr.setDisplayExpression('"change_type"')
    label(lyr, '"change_type"', 8, '#343a40')
lines.setFieldAlias(lines.fields().indexOf('width_m'), 'New footpath width (m) - footpaths only')

# example (locked)
ex = load('example_trial_crossings'); ex.setName('Example: 8 trial crossings (study proposal)')
ex.setRenderer(QgsSingleSymbolRenderer(symbol(ex, color='#d0bfff', size=3.4, shape=Shape.Square, stroke='#7048e8', stroke_w=0.5)))

# study data (locked)
roads = load('loop_roads'); roads.setName('Loop roads (carriageways)')
roads.setRenderer(QgsSingleSymbolRenderer(symbol(roads, color='#343a40', width=0.9, opacity=0.8)))
junc = load('junctions'); junc.setName('Junctions A, B, C')
junc.setRenderer(QgsSingleSymbolRenderer(symbol(junc, color='#212529', size=5, stroke='white', stroke_w=0.6)))
label(junc, 'coalesce("id", "name")', 11)
xing = load('existing_crossings'); xing.setName('Existing crossings')
xing.setRenderer(QgsSingleSymbolRenderer(symbol(xing, color='white', size=3, shape=Shape.Square, stroke='#212529', stroke_w=0.6)))
gaps = load('gaps_without_crossings'); gaps.setName('Gaps with no crossing')
gaps.setRenderer(QgsSingleSymbolRenderer(symbol(gaps, color='#e03131', width=2.6, opacity=0.35)))
gen = load('places_people_cross_to'); gen.setName('Places people cross to reach')
gen.setRenderer(QgsSingleSymbolRenderer(symbol(gen, color='#0c8599', size=2.2, stroke='white', stroke_w=0.3)))
label(gen, '"name"', 7, '#0b7285', max_scale=5000)
bus = load('bus_stops'); bus.setName('Bus stops')
bus.setRenderer(QgsSingleSymbolRenderer(symbol(bus, color='#1971c2', size=2.6, shape=Shape.Diamond, stroke='white', stroke_w=0.3)))
for lyr in (ex, roads, junc, xing, gaps, gen, bus): lyr.setReadOnly(True)

osm = QgsRasterLayer('type=xyz&url=https://tile.openstreetmap.org/{z}/{x}/{y}.png&zmin=0&zmax=19', 'OpenStreetMap', 'wms')
osm.setOpacity(0.75)
proj.addMapLayer(osm, False)

# layer tree: proposals on top, background at the bottom
root = proj.layerTreeRoot()
for title, layers, expanded in (('Your proposals - draw here', [pts, lines, about], True),
                                ('Example scenario', [ex], False),
                                ('Study data (locked)', [junc, xing, bus, gen, gaps, roads], True),
                                ('Background', [osm], False)):
    g = root.addGroup(title); g.setExpanded(expanded)
    for lyr in layers: g.addLayer(lyr)

# styles also stored in the GeoPackage, so the drop-downs survive if a layer is dragged in on its own
for lyr in (pts, lines, ex, roads, junc, xing, gaps, gen, bus):
    res = lyr.saveStyleToDatabaseV2(lyr.name()[:30], 'Madiwala template style', True, '')
    if res[0] != QgsMapLayer.SaveStyleResult.Success if hasattr(QgsMapLayer, 'SaveStyleResult') else not res[0]:
        print(f'  style not stored for {lyr.name()}: {res}')

# snapping onto the loop roads and existing features
sc = QgsSnappingConfig(proj)
sc.setEnabled(True)
sc.setMode(Qgis.SnappingMode.AllLayers)
sc.setTypeFlag(Qgis.SnappingType.Vertex | Qgis.SnappingType.Segment)
sc.setTolerance(12); sc.setUnits(Qgis.MapToolUnit.Pixels)
proj.setSnappingConfig(sc)

# open zoomed on the loop
ext = roads.extent(); ext.grow(0.0015)
proj.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(ext, WGS84))

proj.writeEntryBool('Paths', '/Absolute', False)           # find the .gpkg next to the project, wherever unzipped
if not proj.write(QGZ): sys.exit('could not save the project')
with open(os.path.join(PKG, 'READ ME FIRST.txt'), 'w') as f:
    f.write(open(os.path.join(HERE, 'planner_instructions.txt')).read())
n_layers = len(proj.mapLayers())
qgs.exitQgis()
if os.path.exists(ZIP): os.remove(ZIP)
with zipfile.ZipFile(ZIP, 'w', zipfile.ZIP_DEFLATED) as z:
    for n in sorted(os.listdir(PKG)): z.write(os.path.join(PKG, n), os.path.join('madiwala_proposals', n))
print(f'wrote {ZIP} ({os.path.getsize(ZIP) // 1024} KB): project + {n_layers} layers')
sys.exit(0)
qgs.exitQgis()
