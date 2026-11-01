"""Create a synthetic field orthomosaic with check-point targets for the accuracy workflow.

Writes to workspace/accuracy_demo/:
  demo_field.tif                     2 cm/px map, 60 x 40 m, EPSG:25832
  reference_points.csv               "RTK rover" positions of the targets
  flight_log.csv                     flight data of the demo map
  measured_points_answer_key.csv     where the targets really are in the map

The map is deliberately off by about 3-6 cm (shift plus noise), like a real
orthomosaic. Clicking the targets exactly should reproduce the answer key:
  farm-accuracy reference_points.csv measured_points_answer_key.csv flight_log.csv --out results
No real farm data is used.
"""
import csv
from pathlib import Path
import numpy as np
import rasterio
from rasterio.transform import from_origin

GSD = 0.02
WIDTH, HEIGHT = 3000, 2000  # 60 x 40 m
WEST, NORTH = 702850.0, 5364780.0
CRS = 'EPSG:25832'
SHIFT = np.array([0.03, -0.02])  # systematic offset of the map, metres
TARGET = 20  # 40 cm checkerboard plate
FARM, MAP_ID = 'DEMO', 'DEMO-RTK-40m'

output = Path('workspace/accuracy_demo')
output.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(27)

# Field texture: grass, crop rows, a path and a gravel yard.
noise = rng.normal(0, 1, (HEIGHT // 25 + 1, WIDTH // 25 + 1))
texture = np.kron(noise, np.ones((25, 25)))[:HEIGHT, :WIDTH] * 8 + rng.normal(0, 4, (HEIGHT, WIDTH))
data = np.empty((3, HEIGHT, WIDTH), dtype=float)
data[:] = np.array([85, 135, 60])[:, None, None]
rows = (np.arange(HEIGHT) % 38) < 12  # crop rows every 76 cm
data[:, rows, :WIDTH * 2 // 3] = np.array([60, 105, 45])[:, None, None]
data[:, 900:1050, :] = np.array([150, 125, 95])[:, None, None]  # 3 m path
data[:, :, WIDTH * 2 // 3:] = np.array([140, 140, 135])[:, None, None]  # yard
data += texture

# Targets: (point_id, column, row, role, structure_type). Centres lie on pixel corners.
targets = [(f'CP{i + 1:02d}', col, row, 'check', kind) for i, (col, row, kind) in enumerate([
    (300, 250, 'ground_marker'), (1500, 250, 'ground_marker'), (2700, 250, 'building_corner'),
    (300, 975, 'path_edge'), (1500, 975, 'path_edge'), (2700, 975, 'charging_station'),
    (300, 1750, 'field_corner'), (1500, 1750, 'bed_edge'), (2700, 1750, 'fence_post')])]
targets += [('GCP01', 900, 600, 'gcp', 'ground_marker'), ('GCP02', 2100, 1400, 'gcp', 'ground_marker')]

reference, answers = [], []
for point_id, col, row, role, kind in targets:
    half = TARGET // 2
    plate = np.full((TARGET, TARGET), 245.0)
    plate[:half, :half] = plate[half:, half:] = 20
    data[:, row - half:row + half, col - half:col + half] = plate
    mapped = np.array([WEST + col * GSD, NORTH - row * GSD])
    # GCPs were used for stitching, so the map sits exactly on them.
    error = np.zeros(2) if role == 'gcp' else SHIFT + rng.normal(0, 0.02, 2)
    true = mapped - error
    reference.append(dict(point_id=point_id, farm=FARM, easting=f'{true[0]:.3f}', northing=f'{true[1]:.3f}',
                          height='448.000', crs=CRS, role=role, structure_type=kind, fix_quality='rtk_fixed',
                          h_precision_m='0.012', survey_date='2026-11-03', notes='synthetic demo'))
    answers.append(dict(map_id=MAP_ID, point_id=point_id, x=f'{mapped[0]:.3f}', y=f'{mapped[1]:.3f}',
                        crs=CRS, measured_by='answer key', notes=''))

with rasterio.open(output / 'demo_field.tif', 'w', driver='GTiff', width=WIDTH, height=HEIGHT, count=3,
                   dtype='uint8', crs=CRS, transform=from_origin(WEST, NORTH, GSD, GSD),
                   photometric='RGB', compress='deflate', tiled=True) as dst:
    dst.write(np.clip(data, 0, 255).astype('uint8'))


def write(name, rows):
    with open(output / name, 'w', newline='') as stream:
        writer = csv.DictWriter(stream, list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


write('reference_points.csv', reference)
write('measured_points_answer_key.csv', answers)
write('flight_log.csv', [dict(
    map_id=MAP_ID, farm=FARM, flight_date='2026-11-03', drone_model='Synthetic RTK drone', drone_class='rtk',
    flight_altitude_m=40, front_overlap_pct=80, side_overlap_pct=70, flight_speed_mps=8, gcp_count=2,
    image_count=180, flight_duration_min=12, processing_software='synthetic', processing_duration_min=0,
    gsd_cm=2, weather='synthetic', notes='demo map, no real data')])
print(f'Demo files in {output}/')
