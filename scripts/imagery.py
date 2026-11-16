"""Satellite imagery under matplotlib plots (Esri World Imagery tiles, cached in ~/design_challenge/cache/tiles)."""
import math, os, urllib.request
from PIL import Image

TILES = os.path.expanduser('~/design_challenge/cache/tiles'); os.makedirs(TILES, exist_ok=True)
CREDIT = 'Imagery: Esri World Imagery'

def merc(lon, lat, z):
    n = 2 ** z
    return (lon + 180) / 360 * n * 256, (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n * 256

def basemap(ax, lon0, lat0, lon1, lat1, z):
    """draw imagery for the box and set axes so plotting in (lon, lat) lines up (Web Mercator, small area)."""
    x0, y1 = merc(lon0, lat0, z); x1, y0 = merc(lon1, lat1, z)
    tx0, ty0, tx1, ty1 = int(x0 // 256), int(y0 // 256), int(x1 // 256), int(y1 // 256)
    im = Image.new('RGB', ((tx1 - tx0 + 1) * 256, (ty1 - ty0 + 1) * 256))
    for tx in range(tx0, tx1 + 1):
        for ty in range(ty0, ty1 + 1):
            f = os.path.join(TILES, f'{z}_{tx}_{ty}.jpg')
            if not os.path.exists(f):
                req = urllib.request.Request(f'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{ty}/{tx}',
                                             headers={'User-Agent': 'Mozilla/5.0'})
                open(f, 'wb').write(urllib.request.urlopen(req, timeout=30).read())
            im.paste(Image.open(f), ((tx - tx0) * 256, (ty - ty0) * 256))
    im = im.crop((int(x0 - tx0 * 256), int(y0 - ty0 * 256), int(x1 - tx0 * 256), int(y1 - ty0 * 256)))
    ax.imshow(im, extent=(lon0, lon1, lat0, lat1), aspect=1 / math.cos(math.radians((lat0 + lat1) / 2)))
    ax.set_xlim(lon0, lon1); ax.set_ylim(lat0, lat1); ax.set_xticks([]); ax.set_yticks([])

