#!/usr/bin/env python3
"""Build qgis/madiwala_contract.zip: the planners' template plus the flyover contract's drawings.

A separate template: it copies the output of make_template.py (qgis/madiwala_proposals/) and adds, in
its own folder:
  - the contract's General Alignment Drawing sheets 1-2 as georeferenced images (multiply blend), and
  - map layers traced from them: proposed elevated corridor deck (Level-1 loop, rotary, ramps), Ejipura
    flyover approach, BMRCL land, Metro Phase-3A tunnel alignment, and the drawing's labels,
  - a "Contract drawings" map theme.
make_template.py and its zip are not changed.

Steps (system Python with PyQGIS for this script; the project venv for extract.py):
    python3 qgis/make_template.py                 # base template, if not built yet
    .venv/bin/python qgis/contract/extract.py     # georeference + trace (needs the contract PDF)
    python3 qgis/make_contract_template.py
"""
import os, shutil, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(HERE, 'madiwala_proposals')
SRC = os.path.join(HERE, 'contract', 'out')
PKG = os.path.join(HERE, 'madiwala_contract')
ZIP = os.path.join(HERE, 'madiwala_contract.zip')
for need, how in ((os.path.join(BASE, 'madiwala.qgz'), 'python3 qgis/make_template.py'),
                  (os.path.join(SRC, 'contract_structures.geojson'), '.venv/bin/python qgis/contract/extract.py')):
    if not os.path.exists(need): sys.exit(f'missing {need} - run: {how}')

from osgeo import gdal
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor, QFont, QPainter
from qgis.core import (Qgis, QgsApplication, QgsProject, QgsVectorLayer, QgsRasterLayer, QgsVectorFileWriter,
                       QgsSymbol, QgsRendererCategory, QgsCategorizedSymbolRenderer, QgsSingleSymbolRenderer,
                       QgsMarkerSymbol, QgsSimpleMarkerSymbolLayer, QgsPalLayerSettings, QgsTextFormat,
                       QgsTextBufferSettings, QgsVectorLayerSimpleLabeling, QgsMapThemeCollection, QgsLayerTreeModel,
                       QgsLayerNotesUtils)

shutil.rmtree(PKG, ignore_errors=True)
shutil.copytree(BASE, PKG)
GPKG = os.path.join(PKG, 'contract_drawings.gpkg')
gdal.UseExceptions()

# sheet images -> GeoTIFF (UTM 43N; the PNG world files carry the fitted rotation and scale)
sheets = []
for n in (1, 2):
    tif = os.path.join(PKG, f'contract_sheet_{n}.tif')
    gdal.Translate(tif, os.path.join(SRC, f'contract_sheet_{n}.png'), outputSRS='EPSG:32643',
                   creationOptions=['COMPRESS=DEFLATE', 'TILED=YES', 'PREDICTOR=2'])
    sheets.append(tif)

qgs = QgsApplication([], False); qgs.initQgis()
proj = QgsProject.instance()
if not proj.read(os.path.join(PKG, 'madiwala.qgz')): sys.exit('could not open the copied project')
proj.setTitle('Madiwala loop - study map, proposals and flyover contract drawings')

first = True
for name in ('contract_structures', 'contract_labels'):
    src = QgsVectorLayer(os.path.join(SRC, name + '.geojson'), name, 'ogr')
    o = QgsVectorFileWriter.SaveVectorOptions(); o.driverName = 'GPKG'; o.layerName = name
    o.actionOnExistingFile = (QgsVectorFileWriter.ActionOnExistingFile.CreateOrOverwriteFile if first
                              else QgsVectorFileWriter.ActionOnExistingFile.CreateOrOverwriteLayer)
    err = QgsVectorFileWriter.writeAsVectorFormatV3(src, GPKG, proj.transformContext(), o)
    if err[0] != QgsVectorFileWriter.WriterError.NoError: sys.exit(f'writing {name}: {err}')
    first = False

SMALL = '<span style="color:#666;font-size:90%">'
STYLE = {   # layer -> (legend, fill, opacity, hatch)
    'proposed_flyover': ('Proposed elevated corridor (Level-1 loop, rotary, ramps)', '#f76707', 0.55, False),
    'ejipura_flyover': ('Ejipura flyover approach (under construction)', '#4dabf7', 0.55, False),
    'bmrcl_land': ('BMRCL (metro) land', '#63e6be', 0.45, False),
    'metro_tunnel': ('Metro Phase-3A tunnel alignment (underground)', '#d6336c', 0.9, True),
}
struct = QgsVectorLayer(f'{GPKG}|layername=contract_structures', 'Planned structures (traced from the contract drawings)', 'ogr')
cats = []
for key, (legend, color, opacity, hatch) in STYLE.items():
    s = QgsSymbol.defaultSymbol(struct.geometryType())
    sl = s.symbolLayer(0); c = QColor(color)
    if hatch:
        sl.setBrushStyle(Qt.BrushStyle.FDiagPattern); sl.setColor(c)
    else:
        c.setAlphaF(opacity); sl.setColor(c)
    sl.setStrokeColor(QColor(color)); sl.setStrokeWidth(0.3)
    cats.append(QgsRendererCategory(key, s, legend))
struct.setRenderer(QgsCategorizedSymbolRenderer('layer', cats))
struct.setMapTipTemplate('<strong>[% "what" %]</strong><br>' + SMALL + 'From the B-SMILE elevated-corridor tender drawings '
                         '(General Alignment Drawing). Traced and placed on the map by matching the drawing\'s roads to '
                         'OpenStreetMap; positions approximate (about 2 m).</span>')
struct.setDisplayExpression('"what"')

labels = QgsVectorLayer(f'{GPKG}|layername=contract_labels', 'Labels from the contract drawings', 'ogr')
m = QgsSimpleMarkerSymbolLayer(Qgis.MarkerShape.Circle, 1.6); m.setColor(QColor('#862e9c')); m.setStrokeColor(QColor('white'))
labels.setRenderer(QgsSingleSymbolRenderer(QgsMarkerSymbol([m])))
pal = QgsPalLayerSettings(); pal.fieldName = 'label'
fmt = QgsTextFormat(); f = QFont('Sans Serif'); f.setBold(True); fmt.setFont(f); fmt.setSize(8); fmt.setColor(QColor('#862e9c'))
b = QgsTextBufferSettings(); b.setEnabled(True); b.setSize(1); b.setColor(QColor('white')); fmt.setBuffer(b); pal.setFormat(fmt)
labels.setLabeling(QgsVectorLayerSimpleLabeling(pal)); labels.setLabelsEnabled(True)
labels.setMapTipTemplate('<strong>[% "label" %]</strong><br>' + SMALL + 'Text on the contract drawing, [% "sheet" %]</span>')

rasters = []
for n, tif in enumerate(sheets, 1):
    r = QgsRasterLayer(tif, f'Contract drawing, sheet {n} (General Alignment Drawing)')
    if not r.isValid(): sys.exit(f'could not load {tif}')
    r.setBlendMode(QPainter.CompositionMode.CompositionMode_Multiply)
    r.renderer().setOpacity(0.8)
    rasters.append(r)

new = [labels, struct, *rasters]
for lyr in new:
    proj.addMapLayer(lyr, False)
    lyr.setReadOnly(True) if hasattr(lyr, 'setReadOnly') else None
root = proj.layerTreeRoot()
g = root.insertGroup(2, 'Flyover contract drawings (B-SMILE tender)')
nodes = {lyr: g.addLayer(lyr) for lyr in new}
g.setExpanded(True)
QgsLayerNotesUtils.setLayerNotes(struct, 'Traced from the contract\'s General Alignment Drawing sheets 1-2 (tender, Oct 2026). '
                                 'The tunnel is underground. Positions are approximate (about 2 m).')

# "Contract drawings" theme: the drawings and traced structures over the loop, with the proposal layers
def named(prefixes): return [l for l in proj.mapLayers().values() if any(l.name().startswith(p) for p in prefixes)]
ALWAYS = set(named(['Proposed changes', 'Junctions A, B, C', 'The study loop', 'OpenStreetMap', 'Example:']))
model = QgsLayerTreeModel(root)
for node in root.findLayers(): node.setItemVisibilityChecked(node.layer() in ALWAYS or node.layer() in new)
for grp in root.findGroups(): grp.setItemVisibilityChecked(True)
proj.mapThemeCollection().insert('Contract drawings', QgsMapThemeCollection.createThemeFromCurrentState(root, model))
# open on the drawing view as before, with the traced structures and labels switched on (images off)
draw = proj.mapThemeCollection().mapThemeState('Draw proposals')
visible = {r.layer() for r in draw.layerRecords()} | {labels, struct}
for node in root.findLayers(): node.setItemVisibilityChecked(node.layer() in visible)

proj.writeEntryBool('Paths', '/Absolute', False)
if not proj.write(os.path.join(PKG, 'madiwala.qgz')): sys.exit('could not save the project')
n_layers, themes = len(proj.mapLayers()), proj.mapThemeCollection().mapThemes()
qgs.exitQgis()

with open(os.path.join(PKG, 'READ ME FIRST.txt'), 'a') as f:
    f.write('''
FLYOVER CONTRACT DRAWINGS (this version only)
- The group "Flyover contract drawings" shows what the B-SMILE elevated-corridor tender plans around the loop:
  the Level-1 loop, rotary and ramps, the Ejipura flyover approach, BMRCL land and the Metro Phase-3A tunnel
  alignment (underground), traced from the tender drawings, plus the drawings themselves as images.
- Pick the "Contract drawings" view (eye icon in the Layers panel) to see the drawings over the map.
- The drawings were placed by matching their roads to OpenStreetMap; expect positions to be off by a few metres.
''')
if os.path.exists(ZIP): os.remove(ZIP)
with zipfile.ZipFile(ZIP, 'w', zipfile.ZIP_DEFLATED) as z:
    for n in sorted(os.listdir(PKG)): z.write(os.path.join(PKG, n), os.path.join('madiwala_contract', n))
print(f'wrote {ZIP} ({os.path.getsize(ZIP) // 1024 // 1024} MB): {n_layers} layers, themes {themes}')
sys.exit(0)
