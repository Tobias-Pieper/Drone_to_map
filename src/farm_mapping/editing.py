"""UI-independent polygon vertex editing in WGS84."""
from copy import deepcopy
import math
from shapely.geometry import shape, mapping
from .core import project_geometry


def vertex_positions(feature, source_crs):
    geometry = mapping(project_geometry(shape(feature['geometry']), source_crs, 'EPSG:4326'))
    parts = geometry['coordinates'] if geometry['type'] == 'MultiPolygon' else [geometry['coordinates']]
    for part_index, rings in enumerate(parts):
        for ring_index, ring in enumerate(rings):
            for vertex_index, coordinate in enumerate(ring[:-1]):
                yield part_index, ring_index, vertex_index, coordinate


def move_vertex(project, feature_id, part_index, ring_index, vertex_index, longitude, latitude):
    if not (math.isfinite(longitude) and math.isfinite(latitude)
            and -180 <= longitude <= 180 and -90 <= latitude <= 90):
        raise ValueError('Ungültige geografische Koordinaten.')
    features = deepcopy(project.features)
    feature = next((f for f in features if f['id'] == feature_id), None)
    if feature is None:
        raise ValueError('Das Polygon ist nicht mehr vorhanden.')
    geometry = mapping(project_geometry(shape(feature['geometry']), project.raster['crs'], 'EPSG:4326'))
    # Convert nested tuples to mutable lists, preserving holes and multipolygons.
    def mutable(value):
        return [mutable(item) for item in value] if isinstance(value, (tuple, list)) else value
    coordinates = mutable(geometry['coordinates'])
    parts = coordinates if geometry['type'] == 'MultiPolygon' else [coordinates]
    if min(part_index, ring_index, vertex_index) < 0:
        raise ValueError('Ungültiger Stützpunkt.')
    try:
        ring = parts[part_index][ring_index]
        if vertex_index >= len(ring) - 1:
            raise IndexError
        ring[vertex_index] = [longitude, latitude]
        if vertex_index == 0:
            ring[-1] = [longitude, latitude]
    except IndexError as exc:
        raise ValueError('Ungültiger Stützpunkt.') from exc
    changed = shape({'type': geometry['type'], 'coordinates': coordinates})
    if not changed.is_valid or changed.is_empty:
        raise ValueError('Diese Änderung erzeugt ein ungültiges Polygon; sie wurde verworfen.')
    feature['geometry'] = mapping(project_geometry(changed, 'EPSG:4326', project.raster['crs']))
    feature['properties']['review_status'] = 'manually_edited'
    project.edit(features)


def edge_midpoints(feature, source_crs):
    """Yield source-grid edge midpoints transformed for display on Leaflet."""
    from shapely.geometry import Point
    geometry = feature['geometry']
    parts = geometry['coordinates'] if geometry['type'] == 'MultiPolygon' else [geometry['coordinates']]
    for part_index, rings in enumerate(parts):
        for ring_index, ring in enumerate(rings):
            for edge_index, (start, end) in enumerate(zip(ring, ring[1:])):
                point = Point((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
                displayed = project_geometry(point, source_crs, 'EPSG:4326')
                yield part_index, ring_index, edge_index, (displayed.x, displayed.y)


def insert_vertex(project, feature_id, part_index, ring_index, edge_index):
    """Insert one vertex on an edge in source coordinates, preserving the shape."""
    features = deepcopy(project.features)
    feature = next((f for f in features if f['id'] == feature_id), None)
    if feature is None:
        raise ValueError('Das Polygon ist nicht mehr vorhanden.')
    def mutable(value):
        return [mutable(item) for item in value] if isinstance(value, (tuple, list)) else value
    geometry = feature['geometry']
    coordinates = mutable(geometry['coordinates'])
    parts = coordinates if geometry['type'] == 'MultiPolygon' else [coordinates]
    if min(part_index, ring_index, edge_index) < 0:
        raise ValueError('Ungültige Polygonkante.')
    try:
        ring = parts[part_index][ring_index]
        if edge_index >= len(ring) - 1:
            raise IndexError
        start, end = ring[edge_index:edge_index + 2]
        ring.insert(edge_index + 1, [(a + b) / 2 for a, b in zip(start, end)])
    except IndexError as exc:
        raise ValueError('Ungültige Polygonkante.') from exc
    feature['geometry'] = {'type': geometry['type'], 'coordinates': coordinates}
    feature['properties']['review_status'] = 'manually_edited'
    project.edit(features)
