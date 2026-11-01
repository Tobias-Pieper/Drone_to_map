"""Flight metadata per orthomosaic: drone, flight parameters and processing.

One row of the flight log describes how one map was made. `map_id` links the
row to measured check points; the other fields become grouping keys for the
accuracy evaluation (drone class, altitude, overlap, GCPs, farm).
"""
import csv
import io
from datetime import date
import math
from pathlib import Path

DRONE_CLASSES = ('rtk', 'consumer')

# name, type, required, unit/description
FLIGHT_FIELDS = (
    ('map_id', str, True, 'unique map name, e.g. F1-RTK-40m'),
    ('farm', str, True, 'farm name or code, same as in reference_points.csv'),
    ('flight_date', date, True, 'YYYY-MM-DD'),
    ('drone_model', str, True, 'e.g. DJI Mavic 3 Enterprise RTK'),
    ('drone_class', str, True, 'rtk or consumer'),
    ('flight_altitude_m', float, True, 'metres above ground, max 50 in Freising'),
    ('front_overlap_pct', float, True, 'percent'),
    ('side_overlap_pct', float, True, 'percent'),
    ('flight_speed_mps', float, False, 'metres per second'),
    ('gcp_count', int, True, 'ground control points used during stitching, 0 if none'),
    ('image_count', int, False, 'number of photos'),
    ('flight_duration_min', float, False, 'minutes in the air'),
    ('processing_software', str, False, 'e.g. WebODM 2.x, Pix4D'),
    ('processing_duration_min', float, False, 'minutes for stitching'),
    ('gsd_cm', float, False, 'ground sampling distance of the orthomosaic'),
    ('weather', str, False, 'e.g. overcast, light wind'),
    ('notes', str, False, ''),
)
FIELD_NAMES = tuple(name for name, *_ in FLIGHT_FIELDS)


def validate_flight(values):
    """Return a cleaned copy; empty optional fields become None."""
    result = {}
    for name, kind, required, _ in FLIGHT_FIELDS:
        raw = values.get(name)
        text = '' if raw is None else str(raw).strip()
        if not text:
            if required:
                raise ValueError(f'Flugdaten: „{name}“ fehlt.')
            result[name] = None
            continue
        try:
            if kind is date:
                value = date.fromisoformat(text).isoformat()
            elif kind is int:
                value = int(float(text.replace(',', '.')))
            elif kind is float:
                value = float(text.replace(',', '.'))
            else:
                value = text
        except ValueError as exc:
            raise ValueError(f'Flugdaten: „{name}“ hat einen ungültigen Wert: {text}') from exc
        if kind in (int, float) and (not math.isfinite(value) or value < 0):
            raise ValueError(f'Flugdaten: „{name}“ muss eine nicht negative Zahl sein.')
        result[name] = value
    result['drone_class'] = result['drone_class'].lower()
    if result['drone_class'] not in DRONE_CLASSES:
        raise ValueError('Flugdaten: „drone_class“ muss rtk oder consumer sein.')
    for name in ('front_overlap_pct', 'side_overlap_pct'):
        if result[name] > 100:
            raise ValueError(f'Flugdaten: „{name}“ darf höchstens 100 % sein.')
    return result


def read_flight_log(path):
    """Read a flight log CSV into {map_id: flight}."""
    flights = {}
    with open(path, newline='', encoding='utf-8-sig') as stream:
        reader = csv.DictReader(stream, delimiter=_delimiter(stream))
        missing = {name for name, _, required, _ in FLIGHT_FIELDS if required} - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f'{Path(path).name}: Spalten fehlen: {", ".join(sorted(missing))}')
        for line, row in enumerate(reader, 2):
            if not any((value or '').strip() for value in row.values()):
                continue
            try:
                flight = validate_flight(row)
            except ValueError as exc:
                raise ValueError(f'{Path(path).name}, Zeile {line}: {exc}') from exc
            if flight['map_id'] in flights:
                raise ValueError(f'{Path(path).name}, Zeile {line}: map_id {flight["map_id"]} doppelt.')
            flights[flight['map_id']] = flight
    return flights


def flight_log_csv(flights):
    stream = io.StringIO()
    writer = csv.DictWriter(stream, FIELD_NAMES, lineterminator='\n')
    writer.writeheader()
    for flight in flights:
        writer.writerow({name: '' if flight.get(name) is None else flight[name] for name in FIELD_NAMES})
    return stream.getvalue()


def write_flight_log(path, flights):
    Path(path).write_text(flight_log_csv(flights), encoding='utf-8')


def _delimiter(stream):
    """Excel with German locale saves CSV with semicolons."""
    header = stream.readline()
    stream.seek(0)
    return ';' if header.count(';') > header.count(',') else ','
