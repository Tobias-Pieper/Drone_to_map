"""Positional accuracy of orthomosaics against RTK GNSS reference points.

Reference points are surveyed with the RTK rover. Measured points are the same
targets located on each orthomosaic (one row per map and point). Errors are
computed in one metric evaluation CRS: dx = map minus rover (east), dy (north).

Points used as GCPs while stitching are excluded by default: they were forced
onto the reference and would make the map look more accurate than it is.

Datum note: PROJ treats ETRS89 and WGS84 as identical by default, but in 2026
they differ by roughly 0.9 m in Central Europe. Rover (SAPOS) and RTK-drone
coordinates are normally ETRS89; plain-GPS drones record WGS84. A consumer
map therefore shows such a shift as bias (mean_dx/mean_dy). This is a real
error from the robot's point of view, so it is reported rather than hidden;
`rmse_2d_bias_removed` shows what remains after a single shift correction.
"""
import argparse
import csv
import io
import math
from pathlib import Path

import numpy as np
from pyproj import CRS, Transformer

from .metadata import read_flight_log, _delimiter

ROLES = ('check', 'gcp')
REFERENCE_COLUMNS = ('point_id', 'farm', 'easting', 'northing', 'crs', 'role', 'structure_type')
MEASURED_COLUMNS = ('map_id', 'point_id', 'x', 'y', 'crs')
THRESHOLDS_CM = (10, 15)
DEFAULT_GROUPS = (
    ('map_id',),
    ('drone_class',),
    ('drone_class', 'flight_altitude_m'),
    ('drone_class', 'gcp_count'),
    ('farm', 'drone_class'),
    ('structure_type', 'drone_class'),
)


def read_rows(path, required):
    """(line, row) pairs of stripped text values; checks required columns."""
    with open(path, newline='', encoding='utf-8-sig') as stream:
        reader = csv.DictReader(stream, delimiter=_delimiter(stream))
        missing = set(required) - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f'{Path(path).name}: Spalten fehlen: {", ".join(sorted(missing))}')
        rows = []
        for line, row in enumerate(reader, 2):
            row = {key: (value or '').strip() for key, value in row.items() if key}
            if any(row.values()):
                rows.append((line, row))
        return rows


def _number(text, name, source, line):
    try:
        value = float(text.replace(',', '.'))
    except ValueError:
        value = math.nan
    if not math.isfinite(value):
        raise ValueError(f'{source}, Zeile {line}: „{name}“ ist keine Zahl: {text!r}')
    return value


def read_reference_points(path):
    """Read rover points into {(farm, point_id): point}."""
    return parse_reference_points(read_rows(path, REFERENCE_COLUMNS), Path(path).name)


def parse_reference_points(numbered_rows, source):
    """Validate (line, row) pairs of text values; shared by CSV files and projects."""
    points = {}
    for line, row in numbered_rows:
        role = row['role'].lower()
        if role not in ROLES:
            raise ValueError(f'{source}, Zeile {line}: role muss check oder gcp sein.')
        key = (row['farm'], row['point_id'])
        if not all(key):
            raise ValueError(f'{source}, Zeile {line}: farm und point_id sind erforderlich.')
        if key in points:
            raise ValueError(f'{source}, Zeile {line}: Punkt {key[1]} auf {key[0]} doppelt.')
        points[key] = {**row, 'role': role,
                       'easting': _number(row['easting'], 'easting', source, line),
                       'northing': _number(row['northing'], 'northing', source, line),
                       'crs': CRS.from_user_input(row['crs'])}
    return points


def read_measured_points(path):
    """Read positions picked on the maps (e.g. exported from QGIS)."""
    measured = []
    seen = set()
    for line, row in read_rows(path, MEASURED_COLUMNS):
        source = Path(path).name
        key = (row['map_id'], row['point_id'])
        if key in seen:
            raise ValueError(f'{source}, Zeile {line}: Punkt {key[1]} in Karte {key[0]} doppelt.')
        seen.add(key)
        measured.append({**row, 'line': line,
                         'x': _number(row['x'], 'x', source, line),
                         'y': _number(row['y'], 'y', source, line),
                         'crs': CRS.from_user_input(row['crs'])})
    return measured


def _evaluation_crs(reference, eval_crs):
    crs = CRS.from_user_input(eval_crs) if eval_crs else next(iter(reference.values()))['crs']
    if not crs.is_projected or any(abs(axis.unit_conversion_factor - 1) > 1e-12 for axis in crs.axis_info[:2]):
        raise ValueError(f'Auswerte-CRS muss metrisch projiziert sein (z. B. EPSG:25832), nicht {crs.name}.')
    return crs


def _to(crs_from, crs_to, x, y):
    if crs_from == crs_to:
        return x, y
    return Transformer.from_crs(crs_from, crs_to, always_xy=True).transform(x, y)


def point_errors(reference, measured, flights, eval_crs=None):
    """One row per measured point with dx, dy and 2D error in metres."""
    crs = _evaluation_crs(reference, eval_crs)
    rows = []
    for m in measured:
        flight = flights.get(m['map_id'])
        if flight is None:
            raise ValueError(f'Karte {m["map_id"]} fehlt im Flugprotokoll.')
        ref = reference.get((flight['farm'], m['point_id']))
        if ref is None:
            raise ValueError(f'Punkt {m["point_id"]} (Karte {m["map_id"]}) fehlt in den '
                             f'Referenzpunkten von {flight["farm"]}.')
        ref_e, ref_n = _to(ref['crs'], crs, ref['easting'], ref['northing'])
        map_e, map_n = _to(m['crs'], crs, m['x'], m['y'])
        dx, dy = map_e - ref_e, map_n - ref_n
        rows.append({**{name: flight[name] for name in flight},
                     'point_id': m['point_id'], 'role': ref['role'],
                     'structure_type': ref['structure_type'],
                     'ref_easting': ref_e, 'ref_northing': ref_n,
                     'map_easting': map_e, 'map_northing': map_n,
                     'dx_m': dx, 'dy_m': dy, 'error_2d_m': math.hypot(dx, dy),
                     'evaluation_crs': crs.to_string()})
    return rows


def crs_label(crs):
    """Short 'EPSG:xxxx' where possible, otherwise WKT."""
    crs = CRS.from_user_input(crs)
    authority = crs.to_authority()
    return ':'.join(authority) if authority else crs.to_wkt()


def project_reference(project):
    """Reference points stored in a project, keyed like read_reference_points."""
    return parse_reference_points(enumerate(project.reference_points, 2), 'Referenzpunkte im Projekt')


def project_measured_points(project):
    """Points clicked in the app, in the format of measured_points.csv."""
    if not project.flight:
        raise ValueError('Bitte zuerst die Flugdaten übernehmen (map_id, farm).')
    crs = crs_label(project.raster['crs'])
    return [{'map_id': project.flight['map_id'], 'point_id': point_id,
             'x': point['x'], 'y': point['y'], 'crs': crs,
             'measured_by': point.get('measured_by', ''), 'notes': point.get('notes', '')}
            for point_id, point in sorted(project.measurements.items())]


def project_point_errors(project):
    """Errors of the points measured in one project."""
    measured = [{**row, 'crs': CRS.from_user_input(row['crs'])} for row in project_measured_points(project)]
    if not measured:
        return []
    return point_errors(project_reference(project), measured, {project.flight['map_id']: project.flight})


def summarize(rows, group_by=('map_id',), include_gcps=False):
    """Error statistics per group; metres unless the column name says cm."""
    groups = {}
    for row in rows:
        if include_gcps or row['role'] == 'check':
            groups.setdefault(tuple(row[key] for key in group_by), []).append(row)
    result = []
    for key in sorted(groups, key=lambda k: tuple('' if v is None else str(v) for v in k)):
        members = groups[key]
        dx = np.array([r['dx_m'] for r in members])
        dy = np.array([r['dy_m'] for r in members])
        d2 = np.hypot(dx, dy)
        bias_removed = np.hypot(dx - dx.mean(), dy - dy.mean())
        result.append({
            **dict(zip(group_by, key)),
            'n_points': len(members),
            'n_maps': len({r['map_id'] for r in members}),
            'mean_dx_m': dx.mean(), 'mean_dy_m': dy.mean(),
            'std_dx_m': dx.std(), 'std_dy_m': dy.std(),
            'rmse_x_m': math.sqrt(np.mean(dx ** 2)), 'rmse_y_m': math.sqrt(np.mean(dy ** 2)),
            'rmse_2d_m': math.sqrt(np.mean(d2 ** 2)),
            'mean_2d_m': d2.mean(), 'median_2d_m': float(np.median(d2)),
            'p95_2d_m': float(np.percentile(d2, 95)), 'max_2d_m': d2.max(),
            'rmse_2d_bias_removed_m': math.sqrt(np.mean(bias_removed ** 2)),
            # 1e-6 m tolerance: a point exactly on the limit counts as within it.
            **{f'pct_within_{cm}cm': 100 * np.mean(d2 <= cm / 100 + 1e-6) for cm in THRESHOLDS_CM},
        })
    return result


def missing_points(reference, measured, flights):
    """Check points surveyed on a farm but not measured on one of its maps."""
    found = {(m['map_id'], m['point_id']) for m in measured}
    return [{'map_id': map_id, 'farm': flight['farm'], 'point_id': point_id}
            for map_id, flight in sorted(flights.items())
            if any(m['map_id'] == map_id for m in measured)
            for (farm, point_id), ref in sorted(reference.items())
            if farm == flight['farm'] and ref['role'] == 'check' and (map_id, point_id) not in found]


def csv_text(rows):
    stream = io.StringIO()
    columns = list(dict.fromkeys(key for row in rows for key in row))
    writer = csv.DictWriter(stream, columns, lineterminator='\n')
    writer.writeheader()
    for row in rows:
        writer.writerow({key: _format(row.get(key)) for key in columns})
    return stream.getvalue()


def write_csv(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(csv_text(rows), encoding='utf-8')


def _format(value):
    if isinstance(value, (float, np.floating)):
        return f'{float(value):.4f}'
    return '' if value is None else value


def evaluate(reference_csv, measured_csv, flight_log_csv, out_dir,
             eval_crs=None, include_gcps=False, groups=DEFAULT_GROUPS):
    """Run the whole evaluation and write CSV files; returns paths and point rows."""
    reference = read_reference_points(reference_csv)
    measured = read_measured_points(measured_csv)
    flights = read_flight_log(flight_log_csv)
    rows = point_errors(reference, measured, flights, eval_crs)
    out_dir = Path(out_dir)
    written = [out_dir / 'point_errors.csv']
    write_csv(written[0], rows)
    for group in groups:
        path = out_dir / f'summary_by_{"_".join(group)}.csv'
        write_csv(path, summarize(rows, group, include_gcps))
        written.append(path)
    missing = missing_points(reference, measured, flights)
    if missing:
        written.append(out_dir / 'missing_check_points.csv')
        write_csv(written[-1], missing)
    return written, rows


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog='farm-accuracy',
        description='Lagegenauigkeit von Orthomosaiken gegenüber RTK-Referenzpunkten.')
    parser.add_argument('reference', help='reference_points.csv (RTK-Rover)')
    parser.add_argument('measured', help='measured_points.csv (Positionen in den Karten)')
    parser.add_argument('flights', help='flight_log.csv (eine Zeile pro Karte)')
    parser.add_argument('--out', default='results', help='Ausgabeordner (Standard: results)')
    parser.add_argument('--eval-crs', help='metrisches Auswerte-CRS, Standard: CRS der Referenzpunkte')
    parser.add_argument('--include-gcps', action='store_true',
                        help='GCPs mitauswerten (nur zum Vergleich, nicht für das Ergebnis)')
    args = parser.parse_args(argv)
    try:
        written, rows = evaluate(args.reference, args.measured, args.flights, args.out,
                           args.eval_crs, args.include_gcps)
    except (OSError, ValueError) as exc:
        parser.exit(1, f'Fehler: {exc}\n')
    for path in written:
        print(path)
    by_map = summarize(rows, ('map_id',), args.include_gcps)
    print('\nmap_id                     n   RMSE 2D   P95 2D   ≤10 cm')
    for row in by_map:
        print(f"{row['map_id']:<24} {row['n_points']:>3} {row['rmse_2d_m'] * 100:7.1f} cm"
              f" {row['p95_2d_m'] * 100:6.1f} cm {row['pct_within_10cm']:6.0f} %")


if __name__ == '__main__':
    main()
