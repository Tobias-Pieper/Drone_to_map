"""Create a synthetic RGB GeoTIFF and one test polygon; no real farm data."""
from pathlib import Path
import numpy as np
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box
from farm_mapping.raster import open_project
from farm_mapping.core import make_feature

output = Path('workspace')
output.mkdir(exist_ok=True)
path = output / 'demo.tif'
data = np.zeros((3, 256, 256), dtype='uint8')
data[:] = np.array([80, 140, 60])[:, None, None]
data[:, 80:120, :] = np.array([160, 150, 130])[:, None, None]
with rasterio.open(path, 'w', driver='GTiff', width=256, height=256, count=3,
                   dtype='uint8', crs='EPSG:32632', transform=from_origin(690000, 5330000, .08, .08)) as dst:
    dst.write(data)
p = open_project(path, 'Synthetische Demo')
p.edit([make_feature(box(690002, 5329985, 690008, 5329990))])
p.save(output / 'demo.project.json')
print('Demo-Projekt: workspace/demo.project.json')
