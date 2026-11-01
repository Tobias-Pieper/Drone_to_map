from io import BytesIO
import math
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from PIL import Image
from pyproj import Transformer
from farm_mapping.core import file_hash
from farm_mapping.tiles import register, render_tile, EMPTY_TILE, ORIGIN


def tile_at(lon, lat, z):
    x, y = Transformer.from_crs('EPSG:4326', 'EPSG:3857', always_xy=True).transform(lon, lat)
    size = 2 * ORIGIN / 2 ** z
    return int((x + ORIGIN) // size), int((ORIGIN - y) // size)


@pytest.mark.parametrize('dtype,bands', [('uint8', 3), ('uint8', 4), ('uint16', 3)])
def test_full_resolution_tiles(tmp_path, dtype, bands):
    # 4000 px at 1.5 cm: the 1600 px preview would show only ~3.75 cm per pixel.
    path = tmp_path / 'ortho.tif'
    data = np.zeros((bands, 4000, 4000), dtype=dtype)
    high = 200 if dtype == 'uint8' else 40000
    data[:3, :, ::2] = high  # 1.5 cm stripes, only visible at full resolution
    if bands == 4:
        data[3] = 255
        data[3, :, 2000:] = 0
    with rasterio.open(path, 'w', driver='GTiff', width=4000, height=4000, count=bands, dtype=dtype,
                       crs='EPSG:32632', transform=from_origin(700000, 5360000, .015, .015),
                       photometric='RGB', **({'alpha': 'YES'} if bands == 4 else {})) as dst:
        dst.write(data)
    token, min_zoom, max_native = register(path, file_hash(path))
    assert max_native >= 23 and min_zoom < max_native
    lon, lat = Transformer.from_crs('EPSG:32632', 'EPSG:4326', always_xy=True).transform(700010, 5359990)
    tile = render_tile(token, max_native, *tile_at(lon, lat, max_native))
    image = np.array(Image.open(BytesIO(tile)))
    assert image.shape == (256, 256, 4) and image[..., 3].min() == 255
    assert image[..., 0].std() > 50  # stripes resolved, not blurred to grey
    assert render_tile(token, 3, 0, 0) == EMPTY_TILE  # far away from the field
    if bands == 4:  # transparent half of the orthomosaic stays transparent
        lon, lat = Transformer.from_crs('EPSG:32632', 'EPSG:4326', always_xy=True).transform(700050, 5359990)
        assert render_tile(token, max_native, *tile_at(lon, lat, max_native)) == EMPTY_TILE
    with pytest.raises(KeyError):
        render_tile('unknown', 1, 0, 0)
