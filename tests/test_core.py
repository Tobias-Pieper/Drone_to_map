import json
import pytest
from shapely.geometry import box, Polygon, shape
from farm_mapping.core import Project, make_feature, project_geometry


def sample():
    return Project('Test', '/missing.tif', {'crs': 'EPSG:32632'})


def test_crs_roundtrip():
    polygon = box(690000, 5330000, 690010, 5330010)
    converted = project_geometry(polygon, 32632, 4326)
    assert 11 < converted.centroid.x < 12
    assert 48 < converted.centroid.y < 49
    assert project_geometry(converted, 4326, 32632).hausdorff_distance(polygon) < 1e-6


def test_invalid_geometry():
    with pytest.raises(ValueError):
        make_feature(Polygon([(0, 0), (1, 1), (1, 0), (0, 1), (0, 0)]))


def test_storage_history_and_approval(tmp_path):
    p = sample()
    f = make_feature(box(690000, 5330000, 690010, 5330010))
    p.edit([f])
    p.approve()
    p.edit([])
    assert not p.approved
    p.undo()
    assert len(p.features) == 1 and not p.approved
    p.save(tmp_path / 'project.json')
    restored = Project.load(tmp_path / 'project.json')
    assert restored.snapshot() == json.loads(json.dumps(p.snapshot()))
    restored.redo()
    assert restored.features == []


def test_export_gate_and_coordinates():
    p = sample()
    p.edit([make_feature(box(690000, 5330000, 690010, 5330010))])
    with pytest.raises(ValueError):
        p.geojson(final=True)
    p.approve()
    exported = p.geojson(final=True)
    assert 11 < shape(exported['features'][0]['geometry']).centroid.x < 12
    assert exported['features'][0]['properties']['id'] == p.features[0]['id']
    assert shape(p.features[0]['geometry']).centroid.x > 690000


def test_invalid_edit_is_atomic():
    p = sample()
    p.edit([make_feature(box(0, 0, 1, 1))])
    before = p.snapshot()
    with pytest.raises(ValueError):
        p.edit(safety_distances={'water': -1})
    assert p.snapshot() == before
