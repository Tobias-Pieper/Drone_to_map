"""Full-resolution Web Mercator tiles, cut from the original GeoTIFF on demand.

The 1600-pixel preview covers the zoomed-out view. From the zoom level where
the preview becomes coarser than a tile, Leaflet requests 256-pixel tiles.
Each tile warps only the small source window it covers, so large
orthomosaics need neither overviews nor a pre-built tile pyramid.
"""
from functools import lru_cache
from io import BytesIO
import math

import numpy as np
import rasterio
from rasterio.enums import ColorInterp, Resampling
from rasterio.transform import from_bounds
from rasterio.vrt import WarpedVRT
from rasterio.warp import reproject
from PIL import Image

TILE_SIZE = 256
ORIGIN = 20037508.342789244  # half the Web Mercator world width in metres
MAX_ZOOM = 24
_registry = {}


def _empty_tile():
    buffer = BytesIO()
    Image.new('RGBA', (TILE_SIZE, TILE_SIZE)).save(buffer, 'PNG')
    return buffer.getvalue()


EMPTY_TILE = _empty_tile()


def _tile_resolution(zoom):
    return 2 * ORIGIN / (TILE_SIZE * 2 ** zoom)


def register(path, sha256, preview_size=1600):
    """Make a GeoTIFF available as tiles; returns (token, min_zoom, max_native_zoom).

    The token is derived from the checksum, so a changed file gets new URLs
    and browser-cached tiles never show outdated imagery.
    """
    token = sha256[:16]
    with rasterio.open(path) as src, WarpedVRT(src, crs='EPSG:3857') as vrt:
        native = min(vrt.res)
        preview = max(native, max(vrt.width, vrt.height) * native / preview_size)
        stretch = None if src.dtypes[0] == 'uint8' else _stretch(src)
        alpha = (src.colorinterp.index(ColorInterp.alpha) + 1
                 if ColorInterp.alpha in src.colorinterp else None)
        _registry[token] = {'path': str(path), 'bounds': tuple(vrt.bounds),
                            'alpha': alpha, 'stretch': stretch}
    max_native = min(MAX_ZOOM, math.ceil(math.log2(_tile_resolution(0) / native)))
    min_zoom = min(max_native, math.floor(math.log2(_tile_resolution(0) / preview)) + 1)
    return token, min_zoom, max_native


def _stretch(src):
    """2-98 % percentile stretch for 16-bit or float imagery, from a decimated read."""
    scale = min(1, 1024 / max(src.width, src.height))
    shape = (max(1, round(src.height * scale)), max(1, round(src.width * scale)))
    data = src.read([1, 2, 3], out_shape=(3, *shape), resampling=Resampling.nearest)
    valid = data[:, src.dataset_mask(out_shape=shape) > 0]
    lo, hi = np.percentile(valid, [2, 98]) if valid.size else (0, 1)
    return float(lo), float(max(hi - lo, 1))


@lru_cache(maxsize=2048)
def render_tile(token, z, x, y):
    """PNG bytes of one tile; transparent outside the image. KeyError if unknown."""
    entry = _registry[token]
    count = 2 ** z
    if not (0 <= z <= MAX_ZOOM and 0 <= x < count and 0 <= y < count):
        return EMPTY_TILE
    size = 2 * ORIGIN / count
    west, north = -ORIGIN + x * size, ORIGIN - y * size
    east, south = west + size, north - size
    left, bottom, right, top = entry['bounds']
    if east <= left or west >= right or north <= bottom or south >= top:
        return EMPTY_TILE
    with rasterio.open(entry['path']) as src:
        bands = [1, 2, 3] + ([entry['alpha']] if entry['alpha'] else [])
        tile = np.zeros((4, TILE_SIZE, TILE_SIZE), dtype=src.dtypes[0])
        reproject(source=rasterio.band(src, bands), destination=tile,
                  src_alpha=4 if entry['alpha'] else 0, dst_alpha=4,
                  dst_transform=from_bounds(west, south, east, north, TILE_SIZE, TILE_SIZE),
                  dst_crs='EPSG:3857', resampling=Resampling.bilinear)
    alpha = np.where(tile[3] > 0, 255, 0).astype('uint8')
    if not alpha.any():
        return EMPTY_TILE
    rgb = tile[:3]
    if entry['stretch']:
        lo, span = entry['stretch']
        rgb = np.clip((rgb.astype(float) - lo) * 255 / span, 0, 255)
    buffer = BytesIO()
    Image.fromarray(np.dstack([rgb.transpose(1, 2, 0).astype('uint8'), alpha])).save(buffer, 'PNG')
    return buffer.getvalue()
