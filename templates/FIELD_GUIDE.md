# Field guide: accuracy data

Three CSV files feed the accuracy evaluation. The files in this folder contain
**example rows** (marked `EXAMPLE`). Copy them, delete the example rows and fill
in real data. Excel with comma or semicolon separators both work; decimal commas
are accepted.

```
reference_points.csv   RTK rover: where each target really is
flight_log.csv         one row per orthomosaic: how it was made
measured_points.csv    where each target appears in each orthomosaic
```

Run the evaluation:

```bash
farm-accuracy reference_points.csv measured_points.csv flight_log.csv --out results
```

Results land in `results/` and open in Excel: `point_errors.csv` (one row per
point and map) and `summary_by_*.csv` (RMSE, 95th percentile, share within
10/15 cm, grouped by map, drone class, altitude, GCP count, farm, structure).

## Before the flight

- Mark targets that are **visible from 50 m**: painted crosses or checkerboard
  plates of at least 30 × 30 cm, or sharp natural corners (building corner,
  fence post, charging station base, bed or path edge).
- Spread **check points** over the whole area, including the edges and the
  farmyard. Aim for 8–15 per farm.
- If you also use **GCPs** for stitching, they must be **different targets**
  from the check points. Mark them `gcp` in `role`. They are excluded from the
  result because the stitching forced them onto their coordinates.
- Name points uniquely per farm: `CP01`, `CP02`, … and `GCP01`, …

## `reference_points.csv` (RTK rover)

| column | meaning |
|---|---|
| `point_id` | target name, e.g. `CP03` |
| `farm` | farm code, the same in all three files, e.g. `HSWT-F1` |
| `easting`, `northing` | rover coordinates in metres |
| `height` | optional, ellipsoidal or NHN height |
| `crs` | coordinate system of the rover export. With SAPOS in Bavaria usually **`EPSG:25832`** (ETRS89 / UTM 32N). Check the rover settings! |
| `role` | `check` (evaluated) or `gcp` (used for stitching) |
| `structure_type` | `fence_post`, `building_corner`, `bed_edge`, `path_edge`, `charging_station`, `field_corner`, `ground_marker`, … |
| `fix_quality` | only use **RTK fixed** points; re-measure floats |
| `h_precision_m` | horizontal precision shown by the rover |
| `survey_date`, `notes` | optional |

Measure the **centre** of the target. Hold the pole vertical (bubble level),
average for a few seconds.

## `flight_log.csv` (one row per map)

`map_id` must be unique, e.g. `F1-RTK-40m` (farm, drone, altitude). Required:
`map_id, farm, flight_date, drone_model, drone_class (rtk|consumer),
flight_altitude_m, front_overlap_pct, side_overlap_pct, gcp_count`.
Useful for the time and cost evaluation: `flight_speed_mps, image_count,
flight_duration_min, processing_software, processing_duration_min, gsd_cm,
weather`.

The same fields can be entered in the app under **Flugdaten** and downloaded
as a one-row CSV.

## `measured_points.csv` (positions in the maps)

For every map, find every check point in the orthomosaic and record the
centre of the target.

**In the app (recommended):**

1. Open the orthomosaic and fill in **Flugdaten** (at least `farm` and
   `map_id`), then click *Flugdaten übernehmen*.
2. Under **Kontrollpunkte messen**, upload `reference_points.csv`. Only the
   points of this farm are kept and stored in the project.
3. Switch on **Messmodus**. A cyan circle shows where the rover measured each
   point. On a consumer-drone map the target can be a metre or more away from
   it, so the circle is only a search aid. Click the **target in the image**,
   not the circle.
4. **Zoom in fully** until single pixels are visible. The app refuses clicks
   from further out. Click the exact centre where the checkerboard squares
   meet. Being off by a few screen pixels already means several cm of error.
5. The next open point is selected automatically. To redo a point, select it
   and click again; *Messung löschen* removes it.
6. Leave **Fehler anzeigen** (show errors) off while measuring, so the numbers
   don't influence where you click. Switch it on afterwards to see the errors
   and RMSE for this map.
7. **Projekt speichern**, then *Messpunkte als CSV* gives this map's rows for
   `measured_points.csv`.

**Alternatively in QGIS:**

| column | meaning |
|---|---|
| `map_id` | as in the flight log |
| `point_id` | as in the reference file |
| `x`, `y` | coordinates read from the map |
| `crs` | CRS of `x`/`y`, usually the CRS of the orthomosaic (shown in the app's image overview) |
| `measured_by`, `notes` | optional |

Open the orthomosaic, create a point layer in the same CRS with a
`point_id` field, click each target, then *Export → Save Features As → CSV*
with geometry `AS_XY`. Rename the columns to `x`, `y` and add `map_id` and
`crs`.

## Coordinate systems: watch out

The rover (SAPOS) and RTK drones normally deliver **ETRS89**. A consumer drone
with plain GPS records **WGS84**. In 2026 these differ by about **0.9 m** in
Germany, but most software treats them as identical. The evaluation therefore
reports the consumer map's offset as bias (`mean_dx_m`, `mean_dy_m`) and also
`rmse_2d_bias_removed_m`: the error left after shifting the map once, for
example with one GCP. Both numbers matter for the recommendation.
