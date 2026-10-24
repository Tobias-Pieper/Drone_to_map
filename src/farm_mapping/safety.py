"""Derived exclusion zones. Source geometry is never modified."""
import math
from pyproj import CRS
from shapely.geometry import shape, mapping
from .core import project_geometry, validate_feature


def metric_crs(source_crs, geometry):
    """Use the source CRS if metric, otherwise a local azimuthal metric CRS."""
    source = CRS.from_user_input(source_crs)
    if source.is_projected and all(abs(axis.unit_conversion_factor - 1) < 1e-12
                                   for axis in source.axis_info[:2]):
        return source
    center = project_geometry(geometry, source, 'EPSG:4326').centroid
    return CRS.from_proj4(f'+proj=aeqd +lat_0={center.y} +lon_0={center.x} '
                         '+datum=WGS84 +units=m +no_defs')


def exclusion_zones(project, target_crs='EPSG:4326'):
    """Obstacles and explicit non-traversable areas override traversal hypotheses.

    Distances default to zero where unspecified. Unknown areas are not promoted
    to traversable, and charging stations require a separate future POI model.
    """
    zones = []
    for feature in project.features:
        validate_feature(feature)
        props = feature['properties']
        if props['category'] != 'obstacle' and props['traversability'] != 'non_traversable':
            continue
        distance = project.safety_distances.get(props['subcategory'], 0.0)
        if not math.isfinite(distance) or distance < 0:
            raise ValueError('Sicherheitsabstände müssen endlich und nicht negativ sein.')
        original = shape(feature['geometry'])
        metric = metric_crs(project.raster['crs'], original)
        projected = project_geometry(original, project.raster['crs'], metric)
        buffered = projected.buffer(distance) if distance else projected
        zones.append({'type': 'Feature', 'id': f"exclusion-{feature['id']}",
                      'geometry': mapping(project_geometry(buffered, metric, target_crs)),
                      'properties': {'source_id': feature['id'], 'subcategory': props['subcategory'],
                                     'zone_type': 'exclusion', 'buffer_m': distance,
                                     'metric_crs': metric.to_string()}})
    return {'type': 'FeatureCollection', 'features': zones,
            'farm_mapping': {'source_crs': project.raster['crs'],
                             'derived': True, 'revision': project.revision,
                             'approved': project.approved, 'robot_schema_verified': False}}
