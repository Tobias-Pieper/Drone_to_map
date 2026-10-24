from pathlib import Path
import numpy as np
import rasterio
from rasterio.enums import Resampling, ColorInterp
from rasterio.vrt import WarpedVRT
from rasterio.transform import Affine
from PIL import Image
from pyproj import CRS
from .core import Project, file_hash
from .paths import input_file


def raster_summary(src):
    """Count valid mask pixels; projected grid areas use the affine determinant.

    Area is map-plane image coverage, not surveyed ground area or a field boundary.
    Geographic CRS values are not misrepresented as meters or hectares.
    """
    crs = CRS(src.crs)
    valid_pixels = sum(int(np.count_nonzero(src.dataset_mask(window=window)))
                       for _, window in src.block_windows(1))
    unit_factor = (crs.axis_info[0].unit_conversion_factor
                   if crs.is_projected and len(crs.axis_info) >= 2 else None)
    resolution = [float(value * unit_factor) for value in src.res] if unit_factor else None
    pixel_area = abs(src.transform.a * src.transform.e - src.transform.b * src.transform.d)
    area = valid_pixels * pixel_area * unit_factor ** 2 / 10000 if unit_factor else None
    return {'gsd_m': resolution, 'valid_pixels': valid_pixels, 'image_area_ha': area,
            'crs_label': crs.to_string(), 'area_method': 'valid_mask_projected_grid' if unit_factor else None}


def ensure_raster_summary(project):
    """Populate older projects without changing their geometry or approval."""
    if 'image_area_ha' not in project.raster:
        with rasterio.open(project.raster_path) as src:
            project.raster.update(raster_summary(src))


def open_project(path, name=None):
    path = input_file(path, ('.tif', '.tiff'), 'GeoTIFF')
    with rasterio.open(path) as src:
        if src.driver != 'GTiff' or not src.crs or src.transform == Affine.identity():
            raise ValueError('Georeferenziertes GeoTIFF mit CRS und Pixeltransformation erforderlich.')
        if src.count < 3:
            raise ValueError('Der erste Viewer unterstützt RGB-GeoTIFFs mit mindestens drei Bändern.')
        metadata = {'crs': src.crs.to_wkt(), 'width': src.width, 'height': src.height,
                    'bounds': list(src.bounds), 'transform': list(src.transform),
                    'nodata': src.nodata, **raster_summary(src),
                    'sha256': file_hash(path)}
    return Project(name or path.stem, str(path), metadata)


def preview(project, destination):
    """Warp to Web Mercator so Leaflet image overlay aligns with the map."""
    project.verify_raster()
    with rasterio.open(project.raster_path) as src:
        with WarpedVRT(src, crs='EPSG:3857',
                       add_alpha=ColorInterp.alpha not in src.colorinterp) as vrt:
            scale = min(1, 1600 / max(vrt.width, vrt.height))
            h, w = max(1, round(vrt.height * scale)), max(1, round(vrt.width * scale))
            data = vrt.read([1, 2, 3], out_shape=(3, h, w), resampling=Resampling.bilinear)
            alpha = vrt.dataset_mask(out_shape=(h, w))
            if data.dtype != np.uint8:
                valid = data[:, alpha > 0]
                lo, hi = np.percentile(valid, [2, 98]) if valid.size else (0, 1)
                data = np.clip((data.astype(float) - lo) * 255 / max(hi - lo, 1), 0, 255).astype('uint8')
            rgba = np.dstack([data.transpose(1, 2, 0), alpha])
            Image.fromarray(rgba).save(destination)
            from rasterio.warp import transform_bounds
            west, south, east, north = transform_bounds(vrt.crs, 'EPSG:4326', *vrt.bounds)
            return [[south, west], [north, east]]
