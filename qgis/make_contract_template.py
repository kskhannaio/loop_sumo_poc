#!/usr/bin/env python3
"""Build qgis/madiwala_contract.zip: the planners' template plus the flyover contract's drawings.

A separate template: it copies the output of make_template.py (qgis/madiwala_proposals/) and adds, in
its own folder, everything extracted from the B-SMILE elevated-corridor tender drawings (17 sheets,
the loop south to Bommanahalli):
  - named structures: proposed deck, existing flyovers, Ejipura flyover, metro line and stations,
    underpasses, Metro Phase-3A tunnel, BMRCL land, land to be acquired; and the drawings' labels,
  - the full drawing data: every line, filled shape and text item, in the drawing's colours,
  - all 17 sheets as images,
  - map themes per drawing set. The map opens on the whole corridor; the loop themes are unchanged.
make_template.py and its zip are not changed.

    python3 qgis/make_template.py                 # base template, if not built yet
    python main.py                (in the PDF pipeline repo, ../corridor_pdf_pipeline)   # ends with its export step
    python3 qgis/make_contract_template.py        # system Python with PyQGIS

The drawing data comes ready-made from the pipeline's exports/qgis/: corridor_drawings.gpkg (structures, labels and the
full drawing data) and sheets/ (the 17 tender sheets as images with world files). This script only styles and packages it.
"""
import json, os, shutil, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(HERE, 'madiwala_proposals')
SRC = os.environ.get('PIPELINE_EXPORTS', os.path.join(HERE, '..', '..', 'corridor_pdf_pipeline', 'exports', 'qgis'))   # the PDF pipeline repo's QGIS export
SRC_GPKG = os.path.join(SRC, 'corridor_drawings.gpkg')
PKG = os.path.join(HERE, 'madiwala_contract')
ZIP = os.path.join(HERE, 'madiwala_contract.zip')
for need, how in ((os.path.join(BASE, 'madiwala.qgz'), 'python3 qgis/make_template.py'),
                  (SRC_GPKG, 'python main.py --only export   (in the PDF pipeline repo)')):
    if not os.path.exists(need): sys.exit(f'missing {need} - run: {how}')

from osgeo import gdal
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor, QFont, QPainter
from qgis.core import (Qgis, QgsApplication, QgsProject, QgsVectorLayer, QgsRasterLayer, QgsVectorFileWriter, QgsSymbol,
                       QgsRendererCategory, QgsCategorizedSymbolRenderer, QgsSingleSymbolRenderer, QgsMarkerSymbol,
                       QgsSimpleMarkerSymbolLayer, QgsPalLayerSettings, QgsTextFormat, QgsTextBufferSettings,
                       QgsVectorLayerSimpleLabeling, QgsMapThemeCollection, QgsLayerTreeModel, QgsLayerNotesUtils, QgsProperty,
                       QgsSymbolLayer, QgsPropertyCollection, QgsReferencedRectangle, QgsCoordinateReferenceSystem, QgsRectangle)

shutil.rmtree(PKG, ignore_errors=True)
shutil.copytree(BASE, PKG)
GPKG = os.path.join(PKG, 'contract_drawings.gpkg')
gdal.UseExceptions()

# sheet images -> GeoTIFF (UTM 43N; the world files carry each sheet's fitted rotation and scale)
os.makedirs(os.path.join(PKG, 'contract_sheets'))
SETS = {'gad': 'General alignment drawing', 'la': 'Land acquisition plan', 'topo': 'Topographical survey'}
sheets = []
for f in sorted(os.listdir(os.path.join(SRC, 'sheets'))):              # png + world file (.pgw) + .prj from the pipeline
    if not f.endswith('.png'): continue
    code, n = f[:-4].split('_')
    tif = os.path.join(PKG, 'contract_sheets', f[:-4] + '.tif')
    gdal.Translate(tif, os.path.join(SRC, 'sheets', f), outputSRS='EPSG:32643', creationOptions=['COMPRESS=DEFLATE', 'TILED=YES', 'PREDICTOR=2'])
    sheets.append((code, int(n), tif))

qgs = QgsApplication([], False); qgs.initQgis()
proj = QgsProject.instance()
if not proj.read(os.path.join(PKG, 'madiwala.qgz')): sys.exit('could not open the copied project')
proj.setTitle('Madiwala loop - study map, proposals and flyover contract drawings')

# the pipeline's GeoPackage, copied layer by layer into the package's own GeoPackage under the template's layer names
first = True
for name, src in (('contract_structures', 'structures'), ('contract_labels', 'labels'),
                  ('drawing_lines', 'drawing_lines'), ('drawing_shapes', 'drawing_shapes'), ('drawing_text', 'drawing_text')):
    lyr = QgsVectorLayer(f'{SRC_GPKG}|layername={src}', name, 'ogr')
    if not lyr.isValid(): sys.exit(f'cannot read layer {src} in {SRC_GPKG}')
    o = QgsVectorFileWriter.SaveVectorOptions(); o.driverName = 'GPKG'; o.layerName = name
    o.actionOnExistingFile = (QgsVectorFileWriter.ActionOnExistingFile.CreateOrOverwriteFile if first
                              else QgsVectorFileWriter.ActionOnExistingFile.CreateOrOverwriteLayer)
    err = QgsVectorFileWriter.writeAsVectorFormatV3(lyr, GPKG, proj.transformContext(), o)
    if err[0] != QgsVectorFileWriter.WriterError.NoError: sys.exit(f'writing {name}: {err}')
    first = False

SMALL = '<span style="color:#666;font-size:90%">'
SOURCE = SMALL + 'Source: [% "source" %]</span>'
load = lambda name, title: QgsVectorLayer(f'{GPKG}|layername={name}', title, 'ogr')
def fill_symbol(lyr, color, opacity, hatch=False):
    s = QgsSymbol.defaultSymbol(lyr.geometryType()); sl = s.symbolLayer(0); c = QColor(color)
    if hatch: sl.setBrushStyle(Qt.BrushStyle.FDiagPattern)
    else: c.setAlphaF(opacity)
    sl.setColor(c); sl.setStrokeColor(QColor(color).darker(180)); sl.setStrokeWidth(0.4)
    return s
def text_style(size=8, color='#212529', bold=True):
    fmt = QgsTextFormat(); f = QFont('Sans Serif'); f.setBold(bold); fmt.setFont(f); fmt.setSize(size); fmt.setColor(QColor(color))
    b = QgsTextBufferSettings(); b.setEnabled(True); b.setSize(1); b.setColor(QColor('white')); fmt.setBuffer(b)
    return fmt

# named structures
STYLE = {   # the same colours as the website's "What's planned" tab
    'proposed_deck': ('Proposed elevated corridor deck, Level-1 (loops, rotary, ramps)', '#1971c2', 0.5, False),
    'proposed_deck_level2': ('Proposed deck, second level over Level-1 (Silk Board)', '#0b3a75', 0.55, False),
    'existing_flyover': ('Existing flyovers, incl. the Silk Board double-decker', '#495057', 0.5, False),
    'ejipura_flyover': ('Ejipura flyover approach (under construction)', '#0c8599', 0.55, False),
    'underpass': ('Underpass (existing)', '#212529', 0.5, False),
    'metro': ('Metro line and stations (elevated)', '#862e9c', 0.6, False),
    'metro_station': ('Metro Phase-3A stations (from the metro survey sheets)', '#5f3dc4', 0.6, False),
    'metro_station_land': ('Land, parking and structures for St John\'s Hospital station', '#7950f2', 0.4, False),
    'metro_line': ('Metro Phase-3A line, St John\'s Hospital to Jakkasandra', '#5f3dc4', 0.6, False),
    'metro_structure': ('Metro structure and land at junction A', '#7048e8', 0.55, False),
    'metro_tunnel': ('Entry Ramp 08: ramp from Sarjapura Road into the road tunnel (underground)', '#c2255c', 0.9, True),
    'tunnel_tube': ('Hebbal-Silk Board road tunnel: its two tubes (underground, cars only)', '#a61e4d', 0.9, True),
    'tunnel_portal': ('TBM shaft, where the two bored tubes end', '#a61e4d', 0.45, False),
    'tunnel_ramp': ('Tunnel ramps at St John\'s junction, incl. Exit Ramp 01', '#c2255c', 0.45, False),
    'tunnel_strip': ('Tunnel approach connecting the road tunnel to the Audgodi loop', '#e64980', 0.5, False),
    'subway': ('Pedestrian subway under Sarjapura Road at the metro station', '#2b8a3e', 0.6, False),
    'land_acquisition': ('Land to be acquired (land acquisition plan)', '#f59f00', 0.45, False),
    'bmrcl_land': ('BMRCL (metro) land', '#099268', 0.45, False),
    'tunnel_land': ('Land needed for the road tunnel at St John\'s (tunnel land acquisition plan, Aug 2025)', '#8c5a2b', 0.45, False),
}
struct = load('contract_structures', 'Planned and existing structures (from the contract drawings)')
struct.setRenderer(QgsCategorizedSymbolRenderer('layer', [QgsRendererCategory(k, fill_symbol(struct, c, o, h), l)
                                                         for k, (l, c, o, h) in STYLE.items()]))
struct.setMapTipTemplate('<strong>[% "what" %]</strong><br>About [% format_number("area_m2", 0) %] m²<br>'
                         + '[% if("statement" is not null, "statement" || \'<br>\', \'\') %]'
                         + '[% if("name_confidence" is not null, \'' + SMALL + 'Name is a best-guess reading (confidence: \' || "name_confidence" || \'): \' || "name_basis" || \'</span><br>\', \'\') %]' + SOURCE)
struct.setDisplayExpression('"what"')

labels = load('contract_labels', 'Labels from the contract drawings')
m = QgsSimpleMarkerSymbolLayer(Qgis.MarkerShape.Circle, 1.4); m.setColor(QColor('#862e9c')); m.setStrokeColor(QColor('white'))
labels.setRenderer(QgsSingleSymbolRenderer(QgsMarkerSymbol([m])))
pal = QgsPalLayerSettings(); pal.fieldName = 'label'; pal.setFormat(text_style(8, '#862e9c'))
labels.setLabeling(QgsVectorLayerSimpleLabeling(pal)); labels.setLabelsEnabled(True)
labels.setMapTipTemplate('<strong>[% "label" %]</strong><br>' + SMALL + 'Text on the contract drawings ([% "source" %])'
                         + '[% if("placed" is not null, \'. Placed \' || "placed", \'\') %]</span>')

# full drawing data, in the drawing's own colours
lines = load('drawing_lines', 'All drawn lines (drawing colours)')
s = QgsSymbol.defaultSymbol(lines.geometryType()); s.symbolLayer(0).setWidth(0.15)
s.symbolLayer(0).setDataDefinedProperty(QgsSymbolLayer.Property.StrokeColor, QgsProperty.fromExpression('coalesce("stroke", \'#000000\')'))
lines.setRenderer(QgsSingleSymbolRenderer(s))
shapes = load('drawing_shapes', 'All filled shapes (drawing colours)')
s = QgsSymbol.defaultSymbol(shapes.geometryType()); sl = s.symbolLayer(0)
sl.setDataDefinedProperty(QgsSymbolLayer.Property.FillColor, QgsProperty.fromExpression('set_color_part(coalesce("fill", \'#cccccc\'), \'alpha\', 150)'))
sl.setDataDefinedProperty(QgsSymbolLayer.Property.StrokeColor, QgsProperty.fromExpression('coalesce("stroke", "fill", \'#999999\')'))
sl.setStrokeWidth(0.1)
shapes.setRenderer(QgsSingleSymbolRenderer(s))
text = load('drawing_text', 'All text on the drawings')
text.setRenderer(QgsSingleSymbolRenderer(QgsMarkerSymbol([QgsSimpleMarkerSymbolLayer(Qgis.MarkerShape.Circle, 0.01)])))
pal = QgsPalLayerSettings(); pal.fieldName = 'text'; fmt = text_style(8, '#1d1d1b', False); pal.setFormat(fmt)
pal.placement = Qgis.LabelPlacement.OverPoint
dd = QgsPropertyCollection()
dd.setProperty(QgsPalLayerSettings.Property.LabelRotation, QgsProperty.fromField('rotation'))
dd.setProperty(QgsPalLayerSettings.Property.Size, QgsProperty.fromExpression('"size_m" * 1.0'))
dd.setProperty(QgsPalLayerSettings.Property.Color, QgsProperty.fromExpression('coalesce("colour", \'#1d1d1b\')'))
pal.setDataDefinedProperties(dd)
fmt.setSizeUnit(Qgis.RenderUnit.MapUnits); pal.setFormat(fmt)
pal.obstacleSettings().setIsObstacle(False); pal.placementSettings().setOverlapHandling(Qgis.LabelOverlapHandling.AllowOverlapIfRequired)
text.setLabeling(QgsVectorLayerSimpleLabeling(pal)); text.setLabelsEnabled(True)
text.setMapTipTemplate('<strong>[% "text" %]</strong><br>' + SMALL + 'Drawing [% "sets" %], sheet [% "sheet" %]'
                       '[% if("ocr" = \'yes\', \'<br>Drawn as linework; read by OCR as "\' || "ocr_read_as" || \'" (\' || "ocr_fix" || \')\', \'\') %]</span>')
for lyr in (lines, shapes):
    lyr.setMapTipTemplate('<strong>Drawing: [% "sets" %], sheet [% "sheet" %]</strong><br>' + SMALL +
                          'line [% "stroke" %], fill [% "fill" %], width [% "width_m" %] m (PDF page [% "page" %])</span>')
for lyr in (struct, labels, lines, shapes, text): lyr.setReadOnly(True)

rasters = {}
for code, n, tif in sheets:
    r = QgsRasterLayer(tif, f'{SETS[code]} {n}')
    if not r.isValid(): sys.exit(f'could not load {tif}')
    r.setBlendMode(QPainter.CompositionMode.CompositionMode_Multiply); r.renderer().setOpacity(0.85)
    rasters.setdefault(code, []).append(r)

root = proj.layerTreeRoot()
top = root.insertGroup(2, 'Flyover contract drawings (B-SMILE tender, loop to Bommanahalli)')
nodes = {}
for lyr in (labels, struct):
    proj.addMapLayer(lyr, False); nodes[lyr] = top.addLayer(lyr)
full = top.addGroup('Full drawing data (every line, shape and text)'); full.setExpanded(False)
for lyr in (text, lines, shapes):
    proj.addMapLayer(lyr, False); nodes[lyr] = full.addLayer(lyr)
for code in ('gad', 'la', 'topo'):
    grp = top.addGroup(f'Sheets: {SETS[code]}'); grp.setExpanded(False)
    for r in rasters.get(code, []):
        proj.addMapLayer(r, False); nodes[r] = grp.addLayer(r)
top.setExpanded(True)
QgsLayerNotesUtils.setLayerNotes(struct, 'Traced from the tender drawings (Oct 2026): 17 sheets at 1:2000, fitted to '
                                 'OpenStreetMap roads (median road-edge error about 1-1.5 m). The tunnel is underground.')

# themes: one per drawing set, over the study loop and proposals
def named(prefixes): return {l for l in proj.mapLayers().values() if any(l.name().startswith(p) for p in prefixes)}
ALWAYS = named(['Proposed changes', 'Junctions A, B, C', 'The study loop', 'OpenStreetMap'])
model = QgsLayerTreeModel(root)
def theme(name, on):
    for node in root.findLayers(): node.setItemVisibilityChecked(node.layer() in ALWAYS or node.layer() in on)
    for grp in root.findGroups(): grp.setItemVisibilityChecked(True)
    proj.mapThemeCollection().insert(name, QgsMapThemeCollection.createThemeFromCurrentState(root, model))
theme('Contract: alignment drawings', {struct, labels, *rasters.get('gad', [])})
theme('Contract: land acquisition', {struct, labels, *rasters.get('la', [])})
theme('Contract: survey sheets', {labels, *rasters.get('topo', [])})
theme('Contract: full drawing data', {lines, shapes, text})
# open on the drawing view with the structures and labels on (images and full data off), framed on the whole corridor
draw = proj.mapThemeCollection().mapThemeState('Draw proposals')
visible = {r.layer() for r in draw.layerRecords()} | {labels, struct}
for node in root.findLayers(): node.setItemVisibilityChecked(node.layer() in visible)
ext = QgsRectangle(struct.extent()); ext.grow(0.002)
proj.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(ext, QgsCoordinateReferenceSystem('EPSG:4326')))

proj.writeEntryBool('Paths', '/Absolute', False)
if not proj.write(os.path.join(PKG, 'madiwala.qgz')): sys.exit('could not save the project')
n_layers, themes = len(proj.mapLayers()), proj.mapThemeCollection().mapThemes()
qgs.exitQgis()

with open(os.path.join(PKG, 'READ ME FIRST.txt'), 'a') as f:
    f.write('''
FLYOVER CONTRACT DRAWINGS (this version only)
- The group "Flyover contract drawings" holds what the B-SMILE elevated-corridor tender drawings show from
  the loop south to Bommanahalli: the proposed deck (Level-1, and the second level at Silk Board), existing
  flyovers incl. the Silk Board double-decker, the Ejipura flyover, the metro line and stations, the Metro
  Phase-3A tunnel (underground), BMRCL land and land to be acquired - plus the drawings' labels.
- "Full drawing data" has every line, filled shape and text item from the 17 sheets in their drawing
  colours; "Sheets" has each sheet as an image. They are off at the start: tick them on, or pick a
  "Contract: ..." view with the eye icon in the Layers panel.
- The drawings were fitted to OpenStreetMap roads; expect positions to be off by about 1-2 m.
''')
if os.path.exists(ZIP): os.remove(ZIP)
with zipfile.ZipFile(ZIP, 'w', zipfile.ZIP_DEFLATED) as z:
    for dirpath, _, files in os.walk(PKG):
        for n in sorted(files):
            full_path = os.path.join(dirpath, n)
            z.write(full_path, os.path.join('madiwala_contract', os.path.relpath(full_path, PKG)))
print(f'wrote {ZIP} ({os.path.getsize(ZIP) // 1024 // 1024} MB): {n_layers} layers; themes {themes}')
sys.exit(0)
