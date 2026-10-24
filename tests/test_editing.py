from copy import deepcopy
import pytest
from shapely.geometry import Polygon, MultiPolygon, box, shape
from farm_mapping.core import Project, make_feature, project_geometry
from farm_mapping.editing import move_vertex, vertex_positions


def sample(geometry):
    p = Project('Editing', '/unused', {'crs': 'EPSG:32632'})
    p.edit([make_feature(project_geometry(geometry, 4326, 32632))])
    return p


def test_drag_first_vertex_closes_ring_and_undoes():
    p = sample(box(11, 48, 11.001, 48.001))
    before = deepcopy(p.features)
    p.approve()
    identifier = p.features[0]['id']
    move_vertex(p, identifier, 0, 0, 0, 11.0012, 48)
    assert not p.approved
    geom = project_geometry(shape(p.features[0]['geometry']), 32632, 4326)
    assert geom.exterior.coords[0] == geom.exterior.coords[-1]
    assert geom.exterior.coords[0][:2] == pytest.approx((11.0012, 48))
    p.undo()
    assert p.features[0]['geometry'] == before[0]['geometry']
    p.redo()
    assert p.features[0]['geometry'] != before[0]['geometry']


def test_multipolygon_hole_preserved():
    polygon = Polygon([(11,48),(11.004,48),(11.004,48.004),(11,48.004)],
                      holes=[[(11.001,48.001),(11.002,48.001),(11.002,48.002),(11.001,48.002)]])
    p = sample(MultiPolygon([polygon, box(11.01,48,11.011,48.001)]))
    assert len(list(vertex_positions(p.features[0], 32632))) == 12
    move_vertex(p, p.features[0]['id'], 0, 1, 0, 11.0009, 48.001)
    geom = shape(p.features[0]['geometry'])
    assert len(geom.geoms) == 2 and len(geom.geoms[0].interiors) == 1


def test_invalid_drag_is_atomic():
    p = sample(box(11,48,11.001,48.001))
    before = p.snapshot()
    # Move the first corner across the opposite edge, creating a self-intersection.
    with pytest.raises(ValueError):
        move_vertex(p, p.features[0]['id'], 0, 0, 0, 10.999,48.0005)
    assert p.snapshot() == before
    with pytest.raises(ValueError):
        move_vertex(p, p.features[0]['id'], 0, 0, 99, 11,48)
    assert p.snapshot() == before


@pytest.mark.parametrize('edge', [0, 3])
def test_insert_preserves_shape_and_history(edge, tmp_path):
    from farm_mapping.editing import insert_vertex, edge_midpoints
    p = sample(box(11,48,11.001,48.001))
    before = deepcopy(p.features[0])
    original = shape(before['geometry'])
    assert len(list(edge_midpoints(before, 32632))) == 4
    p.approve()
    insert_vertex(p, before['id'], 0, 0, edge)
    assert not p.approved
    changed = shape(p.features[0]['geometry'])
    assert len(changed.exterior.coords) == 6
    assert changed.hausdorff_distance(original) < 1e-8
    assert changed.area == pytest.approx(original.area)
    assert changed.exterior.coords[0] == changed.exterior.coords[-1]
    p.save(tmp_path / 'insert.json')
    restored = Project.load(tmp_path / 'insert.json')
    assert len(list(vertex_positions(restored.features[0], 32632))) == 5
    p.undo()
    assert shape(p.features[0]['geometry']).equals_exact(original, 0)
    p.redo()
    assert len(list(vertex_positions(p.features[0], 32632))) == 5


def test_insert_hole_and_second_part_and_invalid_edge():
    from farm_mapping.editing import insert_vertex
    polygon = Polygon([(11,48),(11.004,48),(11.004,48.004),(11,48.004)],
                      holes=[[(11.001,48.001),(11.002,48.001),(11.002,48.002),(11.001,48.002)]])
    p = sample(MultiPolygon([polygon, box(11.01,48,11.011,48.001)]))
    identifier = p.features[0]['id']
    insert_vertex(p, identifier, 0, 1, 3)
    insert_vertex(p, identifier, 1, 0, 1)
    geom = shape(p.features[0]['geometry'])
    assert len(geom.geoms[0].interiors[0].coords) == 6
    assert len(geom.geoms[1].exterior.coords) == 6
    before = p.snapshot()
    for indices in [(0,0,99),(-1,0,0),(99,0,0)]:
        with pytest.raises(ValueError):
            insert_vertex(p, identifier, *indices)
        assert p.snapshot() == before
