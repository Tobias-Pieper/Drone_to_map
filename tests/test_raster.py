import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from farm_mapping.raster import open_project, preview, ensure_raster_summary


@pytest.mark.parametrize('bands', [3, 4])
def test_geotiff_preview(tmp_path, bands):
    path = tmp_path / 'test.tif'
    with rasterio.open(path, 'w', driver='GTiff', width=32, height=32,
                       count=bands, dtype='uint8', crs='EPSG:32632',
                       transform=from_origin(690000, 5330000, .08, .08)) as dst:
        data = np.full((bands, 32, 32), 120, dtype='uint8')
        if bands == 4:
            from rasterio.enums import ColorInterp
            dst.colorinterp = (ColorInterp.red, ColorInterp.green, ColorInterp.blue, ColorInterp.alpha)
            data[3] = 255
            data[3, :8, :8] = 0
        dst.write(data)
    p = open_project(path)
    assert p.raster['gsd_m'] == [.08, .08]
    expected_pixels = 32 * 32 - (8 * 8 if bands == 4 else 0)
    assert p.raster['valid_pixels'] == expected_pixels
    assert p.raster['image_area_ha'] == pytest.approx(expected_pixels * .08 ** 2 / 10000)
    assert p.raster['crs_label'] == 'EPSG:32632'
    del p.raster['image_area_ha']
    ensure_raster_summary(p)
    assert p.raster['image_area_ha'] == pytest.approx(expected_pixels * .08 ** 2 / 10000)
    bounds = preview(p, tmp_path / 'preview.png')
    assert bounds[0][0] < bounds[1][0]
    assert (tmp_path / 'preview.png').is_file()
    if bands == 4:
        from PIL import Image
        with Image.open(tmp_path / 'preview.png') as image:
            alpha = np.array(image)[:, :, 3]
            assert alpha.min() == 0 and alpha.max() == 255
    path.write_bytes(b'changed')
    with pytest.raises(ValueError, match='Prüfsumme'):
        p.verify_raster()


def test_missing_crs(tmp_path):
    path = tmp_path / 'bad.tif'
    with rasterio.open(path, 'w', driver='GTiff', width=8, height=8,
                       count=3, dtype='uint8', transform=from_origin(1, 2, 1, 1)) as dst:
        dst.write(np.zeros((3, 8, 8), dtype='uint8'))
    with pytest.raises(ValueError, match='Georeferenziertes'):
        open_project(path)


@pytest.mark.parametrize('crs,expected_factor', [('EPSG:4326', None), ('EPSG:2263', 0.30480060960121924)])
def test_summary_units(tmp_path, crs, expected_factor):
    path = tmp_path / 'units.tif'
    with rasterio.open(path, 'w', driver='GTiff', width=4, height=4,
                       count=3, dtype='uint8', crs=crs,
                       transform=from_origin(1, 2, .1, .1)) as dst:
        dst.write(np.ones((3, 4, 4), dtype='uint8'))
    p = open_project(path)
    if expected_factor is None:
        assert p.raster['image_area_ha'] is None
        assert p.raster['gsd_m'] is None
    else:
        assert p.raster['image_area_ha'] == pytest.approx(16 * .01 * expected_factor ** 2 / 10000)
        assert p.raster['gsd_m'][0] == pytest.approx(.1 * expected_factor)
