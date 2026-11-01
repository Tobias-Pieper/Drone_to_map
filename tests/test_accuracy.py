import csv
from pathlib import Path
import pytest
from pyproj import Transformer
from farm_mapping.accuracy import (read_reference_points, read_measured_points, point_errors,
                                   summarize, evaluate, missing_points)
from farm_mapping.metadata import read_flight_log, validate_flight, flight_log_csv

TEMPLATES = Path(__file__).parents[1] / 'templates'
FLIGHT = dict(map_id='M1', farm='F1', flight_date='2026-11-03', drone_model='X', drone_class='rtk',
              flight_altitude_m='40', front_overlap_pct='80', side_overlap_pct='70', gcp_count='0')


def write(path, rows, delimiter=','):
    with open(path, 'w', newline='') as stream:
        writer = csv.DictWriter(stream, list(rows[0]), delimiter=delimiter)
        writer.writeheader()
        writer.writerows(rows)
    return path


def reference_rows():
    return [dict(point_id=f'CP{i}', farm='F1', easting=str(700000 + 10 * i), northing='5360000',
                 crs='EPSG:25832', role='check', structure_type='post') for i in range(4)] + [
        dict(point_id='G1', farm='F1', easting='700100', northing='5360000',
             crs='EPSG:25832', role='gcp', structure_type='marker')]


def test_errors_and_statistics(tmp_path):
    reference = read_reference_points(write(tmp_path / 'r.csv', reference_rows()))
    offsets = [(0.03, 0.04), (-0.03, -0.04), (0.06, 0.08), (0.0, 0.0), (5.0, 5.0)]
    measured = read_measured_points(write(tmp_path / 'm.csv', [
        dict(map_id='M1', point_id=row['point_id'], x=str(float(row['easting']) + dx),
             y=str(float(row['northing']) + dy), crs='EPSG:25832')
        for row, (dx, dy) in zip(reference_rows(), offsets)]))
    flights = {'M1': validate_flight(FLIGHT)}
    rows = point_errors(reference, measured, flights)
    assert [round(r['error_2d_m'], 6) for r in rows] == [0.05, 0.05, 0.1, 0.0, pytest.approx(7.071068)]
    (summary,) = summarize(rows)
    assert summary['n_points'] == 4  # the GCP is excluded
    assert summary['rmse_2d_m'] == pytest.approx((0.05 ** 2 * 2 + 0.1 ** 2) ** .5 / 2)
    assert summary['max_2d_m'] == pytest.approx(0.1)
    assert summary['pct_within_10cm'] == 100
    assert summarize(rows, include_gcps=True)[0]['n_points'] == 5


def test_constant_shift_is_bias(tmp_path):
    reference = read_reference_points(write(tmp_path / 'r.csv', reference_rows()))
    measured = read_measured_points(write(tmp_path / 'm.csv', [
        dict(map_id='M1', point_id=f'CP{i}', x=str(700000 + 10 * i + 0.8), y='5360000.6',
             crs='EPSG:25832') for i in range(4)]))
    (summary,) = summarize(point_errors(reference, measured, {'M1': validate_flight(FLIGHT)}))
    assert summary['mean_dx_m'] == pytest.approx(0.8)
    assert summary['rmse_2d_m'] == pytest.approx(1.0)
    assert summary['rmse_2d_bias_removed_m'] == pytest.approx(0, abs=1e-6)


def test_measured_points_in_other_crs(tmp_path):
    reference = read_reference_points(write(tmp_path / 'r.csv', reference_rows()))
    lon, lat = Transformer.from_crs('EPSG:25832', 'EPSG:4326', always_xy=True).transform(700000, 5360000)
    measured = read_measured_points(write(tmp_path / 'm.csv', [
        dict(map_id='M1', point_id='CP0', x=str(lon), y=str(lat), crs='EPSG:4326')]))
    (row,) = point_errors(reference, measured, {'M1': validate_flight(FLIGHT)})
    assert row['error_2d_m'] < 0.001


def test_rejects_bad_input(tmp_path):
    rows = reference_rows()
    rows[0]['role'] = 'maybe'
    with pytest.raises(ValueError, match='role'):
        read_reference_points(write(tmp_path / 'r.csv', rows))
    reference = read_reference_points(write(tmp_path / 'r2.csv', reference_rows()))
    measured = read_measured_points(write(tmp_path / 'm.csv', [
        dict(map_id='M2', point_id='CP0', x='1', y='2', crs='EPSG:25832')]))
    with pytest.raises(ValueError, match='Flugprotokoll'):
        point_errors(reference, measured, {'M1': validate_flight(FLIGHT)})
    with pytest.raises(ValueError, match='metrisch'):
        point_errors(reference, measured, {'M1': validate_flight(FLIGHT)}, eval_crs='EPSG:4326')


def test_missing_check_points(tmp_path):
    reference = read_reference_points(write(tmp_path / 'r.csv', reference_rows()))
    measured = read_measured_points(write(tmp_path / 'm.csv', [
        dict(map_id='M1', point_id='CP0', x='700000', y='5360000', crs='EPSG:25832')]))
    missing = missing_points(reference, measured, {'M1': validate_flight(FLIGHT)})
    assert [m['point_id'] for m in missing] == ['CP1', 'CP2', 'CP3']


def test_flight_validation():
    flight = validate_flight({**FLIGHT, 'drone_class': 'RTK', 'flight_altitude_m': '42,5'})
    assert flight['drone_class'] == 'rtk' and flight['flight_altitude_m'] == 42.5
    assert flight['flight_speed_mps'] is None
    for change, message in [({'drone_class': 'plane'}, 'drone_class'), ({'gcp_count': ''}, 'gcp_count'),
                            ({'side_overlap_pct': '120'}, 'side_overlap_pct'),
                            ({'flight_date': '3.11.2026'}, 'flight_date')]:
        with pytest.raises(ValueError, match=message):
            validate_flight({**FLIGHT, **change})


def test_semicolon_csv_with_decimal_comma(tmp_path):
    path = tmp_path / 'flights.csv'
    path.write_text(flight_log_csv([validate_flight(FLIGHT)]).replace(',', ';').replace('40.0', '40,5'))
    assert read_flight_log(path)['M1']['flight_altitude_m'] == 40.5


def test_templates_run_end_to_end(tmp_path):
    written, rows = evaluate(TEMPLATES / 'reference_points.csv', TEMPLATES / 'measured_points.csv',
                             TEMPLATES / 'flight_log.csv', tmp_path)
    assert all(path.is_file() for path in written)
    by_class = {row['drone_class']: row for row in summarize(rows, ('drone_class',))}
    assert by_class['rtk']['rmse_2d_m'] < by_class['consumer']['rmse_2d_m']


def test_measurements_stored_in_project(tmp_path):
    from farm_mapping.accuracy import project_point_errors, project_measured_points, read_rows, REFERENCE_COLUMNS
    from farm_mapping.core import Project
    project = Project('M1', 'unused.tif', {'crs': 'EPSG:32632'})
    with pytest.raises(ValueError, match='Flugdaten'):
        project_measured_points(project)
    project.flight = validate_flight(FLIGHT)
    project.reference_points = [row for _, row in read_rows(
        write(tmp_path / 'r.csv', reference_rows()), REFERENCE_COLUMNS)]
    # Map in WGS84/UTM 32N, rover in ETRS89/UTM 32N: PROJ treats them as identical (< 1 mm).
    project.measurements = {'CP1': {'x': 700010.03, 'y': 5360000.04}, 'G1': {'x': 700100.0, 'y': 5360000.0}}
    rows = project_measured_points(project)
    assert [r['crs'] for r in rows] == ['EPSG:32632', 'EPSG:32632']
    errors = {row['point_id']: row for row in project_point_errors(project)}
    assert errors['CP1']['error_2d_m'] == pytest.approx(0.05, abs=0.001)
    assert errors['G1']['role'] == 'gcp'
    project.save(tmp_path / 'p.json')
    assert Project.load(tmp_path / 'p.json').measurements['CP1']['x'] == 700010.03
