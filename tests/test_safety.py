from copy import deepcopy
import math
import pytest
from shapely.geometry import box, shape
from farm_mapping.core import Project, make_feature, project_geometry
from farm_mapping.safety import exclusion_zones


def project(crs='EPSG:32632'):
    p = Project('Safety', '/unused', {'crs': crs})
    geom = project_geometry(box(690000, 5330000, 690010, 5330010), 32632, crs)
    p.edit([make_feature(geom, 'obstacle', 'water')])
    return p


def test_buffer_preserves_original_and_recalculates():
    p = project()
    original = deepcopy(p.features)
    zone = shape(exclusion_zones(p, 32632)['features'][0]['geometry'])
    assert zone.area == pytest.approx(100 + 40 + math.pi, abs=.03)
    p.approve()
    p.edit(safety_distances={'water': 1.5})
    assert not p.approved
    assert p.features[0]['geometry'] == original[0]['geometry']
    assert shape(exclusion_zones(p, 32632)['features'][0]['geometry']).area > zone.area
    p.undo()
    assert p.safety_distances['water'] == 1.0


@pytest.mark.parametrize('crs', ['EPSG:4326', 'EPSG:2263'])
def test_metric_buffer_for_nonmetric_crs(crs):
    # Use a local NYC polygon for the US-foot CRS, within its area of use.
    p = project(crs)
    if crs == 'EPSG:2263':
        center = project_geometry(box(-74, 40.7, -73.9999, 40.7001), 4326, 2263)
        p.edit([make_feature(center, 'obstacle', 'water')])
    data = exclusion_zones(p)
    feature = data['features'][0]
    metric = feature['properties']['metric_crs']
    buffered = project_geometry(shape(feature['geometry']), 4326, metric)
    original = project_geometry(shape(p.features[0]['geometry']), crs, metric)
    assert buffered.bounds[0] == pytest.approx(original.bounds[0] - 1, abs=.02)


def test_exclusion_rules_and_zero_buffer():
    p = project()
    geom = box(690000, 5330000, 690010, 5330010)
    obstacle = make_feature(geom, 'obstacle', 'tree', traversability='traversable')
    unknown = make_feature(geom, 'work_area', 'field')
    blocked = make_feature(geom, 'navigable_area', 'path', traversability='non_traversable')
    p.edit([obstacle, unknown, blocked])
    zones = exclusion_zones(p, 32632)['features']
    assert {f['properties']['source_id'] for f in zones} == {obstacle['id'], blocked['id']}
    assert all(shape(f['geometry']).equals(geom) for f in zones)


def test_invalid_distance_rejected():
    p = project()
    p.safety_distances['water'] = float('nan')
    with pytest.raises(ValueError):
        exclusion_zones(p)
