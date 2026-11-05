import numpy as np
import pytest
from rasterio.transform import from_origin
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
from farm_mapping.detection.appearance import shadow_hypotheses
from farm_mapping.detection.baseline import classify_rgb
from farm_mapping.detection.structure import smooth_fields
from farm_mapping.detection import DetectionSettings


def test_shadow_color_match_preserves_compact_crown_and_distinct_dark_vegetation():
    rgb = np.empty((3, 120, 120), dtype='uint8')
    rgb[:] = np.array([100, 150, 80])[:, None, None]
    # Same chromaticity, lower illumination; long, narrow shadow region.
    rgb[:, 30:35, 10:110] = np.array([30, 45, 24])[:, None, None]
    # Compact crown-sized object of identical color must still be protected.
    rgb[:, 65:75, 20:30] = np.array([30, 45, 24])[:, None, None]
    # Distinct chromaticity, elongated dark vegetation remains uncorrected.
    rgb[:, 90:95, 10:110] = np.array([15, 65, 10])[:, None, None]
    valid = np.ones((120, 120), dtype=bool)
    labels = classify_rgb(rgb, valid)
    shadows = shadow_hypotheses(rgb, labels, valid, from_origin(0, 30, .25, .25), 1)
    assert shadows[30:35, 10:110].sum() > 100
    assert not shadows[65:75, 20:30].any()
    assert not shadows[90:95, 10:110].any()
    assert not shadows[labels == 1].any()
    valid[30:35, 10:110] = False
    assert not shadow_hypotheses(rgb, labels, valid, from_origin(0, 30, .25, .25), 1)[~valid].any()


def test_dark_image_without_lit_field_is_not_promoted():
    rgb = np.full((3, 40, 40), 20, dtype='uint8')
    labels = np.zeros((40, 40), dtype='uint8')
    assert not shadow_hypotheses(rgb, labels, np.ones_like(labels, dtype=bool),
                                 from_origin(0, 40, 1, 1), 1).any()


@pytest.mark.parametrize('factor', [1, .3048])
def test_smoothing_reduces_staircase_preserves_holes_obstacles_and_mask(factor):
    from shapely.affinity import scale
    edge = [(i, i + (.1 if i % 2 else -.1)) for i in range(1, 20)]
    original = Polygon([(0, 0), (20, 0), (20, 20), *reversed(edge)]).difference(box(10, 3, 11, 4))
    obstacle = box(6, 5, 7, 6)
    original = original.difference(obstacle)
    valid = box(0, 0, 20, 20)
    convert = lambda g: scale(g, xfact=1/factor, yfact=1/factor, origin=(0, 0))
    candidates = [(convert(original), 1), (convert(obstacle), 4)]
    result = smooth_fields(candidates, convert(valid), factor, .5)
    field = unary_union([g for g, label in result if label == 1])
    assert field.is_valid
    assert len(field.exterior.coords) < len(original.exterior.coords)
    assert field.symmetric_difference(convert(original)).area <= .05 * convert(original).area
    assert field.intersection(convert(box(10, 3, 11, 4))).area == 0
    assert field.intersection(convert(obstacle)).area == 0
    assert field.difference(convert(valid)).area == 0
    assert smooth_fields(candidates, convert(valid), factor, 0) == candidates


@pytest.mark.parametrize('setting', [dict(outline_smoothing_m=-1),
    dict(outline_smoothing_m=float('nan')), dict(outline_smoothing_m=3)])
def test_smoothing_parameter_validation(setting):
    with pytest.raises(ValueError):
        DetectionSettings(**setting).validate()


def test_shadow_toggle_pipeline_and_review_metadata(tmp_path):
    import rasterio
    from farm_mapping.raster import open_project
    from farm_mapping.detection import ColorBaseline
    rgb = np.empty((3, 120, 120), dtype='uint8')
    rgb[:] = np.array([100, 150, 80])[:, None, None]
    rgb[:, 30:35, 10:110] = np.array([30, 45, 24])[:, None, None]
    path = tmp_path / 'shadow.tif'
    with rasterio.open(path, 'w', driver='GTiff', count=3, width=120, height=120,
                       dtype='uint8', crs='EPSG:32632',
                       transform=from_origin(690000, 5330000, .25, .25)) as dst:
        dst.write(rgb)
    project = open_project(path)
    results = []
    for enabled in (False, True):
        settings = DetectionSettings(max_dimension=120, minimum_area_m2=1,
            grouping_distance_m=0, field_context_radius_m=0, outline_smoothing_m=0,
            detect_orchards=False, compensate_shadows=enabled)
        results.append(ColorBaseline().detect(project.raster_path, project.raster['sha256'], settings))
    before, after = results
    assert before.metadata['shadow_hypothesis_area_m2'] == 0
    assert after.metadata['shadow_hypothesis_area_m2'] > 0
    assert before.metadata['run_id'] != after.metadata['run_id']
    tree_area = lambda result: sum(shape_area(f) for f in result.features if f['properties']['subcategory'] == 'tree')
    assert tree_area(after) < tree_area(before)
    for feature in after.features:
        assert feature['properties']['traversability'] == 'unknown'
        if feature['properties']['subcategory'] == 'field':
            assert 'Schattenausgleich aktiv' in feature['properties']['review_reason']


def shape_area(feature):
    from shapely.geometry import shape
    return shape(feature['geometry']).area


@pytest.mark.parametrize('factor', [1, .3048])
def test_boundary_smoothing_fills_notches_and_removes_spurs_at_selected_scale(factor):
    from shapely.affinity import scale
    base = box(0, 0, 30, 30)
    notches = unary_union([box(x, 27, x+1, 31) for x in range(2, 28, 2)])
    spurs = unary_union([box(x, -3, x+1, 1) for x in range(2, 28, 6)])
    original = base.difference(notches).union(spurs)
    convert = lambda g: scale(g, xfact=1/factor, yfact=1/factor, origin=(0, 0))
    candidate = [(convert(original), 1)]
    fine = unary_union([g for g, _ in smooth_fields(candidate, convert(box(-5,-5,35,35)), factor, .2)])
    coarse = unary_union([g for g, _ in smooth_fields(candidate, convert(box(-5,-5,35,35)), factor, 2)])
    assert coarse.symmetric_difference(convert(base)).area < fine.symmetric_difference(convert(base)).area / 4
    # Proves the former 5% fallback no longer silently cancels the requested radius.
    assert coarse.symmetric_difference(convert(original)).area > .05 * convert(original).area
    assert len(coarse.exterior.coords) < len(original.exterior.coords) / 4
    assert coarse.is_valid


def test_boundary_smoothing_retains_small_standalone_field_and_large_corner():
    small, corner = box(40, 0, 41, 1), Polygon([(0,0),(20,0),(20,10),(10,10),(10,20),(0,20)])
    result = smooth_fields([(small, 1),(corner, 1)], box(-5,-5,50,30), 1, 2)
    field = unary_union([g for g, _ in result])
    assert field.covers(small)
    assert field.symmetric_difference(unary_union([small,corner])).area < 1e-8
