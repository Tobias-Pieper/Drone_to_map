import numpy as np
import pytest
from shapely.geometry import Point, box
from shapely.affinity import rotate
from shapely.ops import unary_union
from farm_mapping.detection.structure import regular_orchards, consolidate


@pytest.mark.parametrize('angle', [0, 23, 65])
def test_regular_grid_becomes_one_orchard(angle):
    crowns=[rotate(Point(x*5,y*6).buffer(1),angle,origin=(0,0)) for x in range(5) for y in range(4)]
    result=regular_orchards(crowns)
    assert len(result)==1
    assert all(result[0].covers(crown.centroid) for crown in crowns)


def test_single_row_and_random_woods_are_not_orchards():
    assert regular_orchards([Point(x*5,0).buffer(1) for x in range(15)]) == []
    rng=np.random.default_rng(42)
    assert regular_orchards([Point(*xy).buffer(1) for xy in rng.uniform(0,45,(30,2))]) == []


def test_grouping_preserves_roads_and_valid_footprint():
    left,right=box(0,0,4,10),box(4.5,0,10,10)
    road=box(4,0,4.5,10)
    valid=box(0,0,10,10)
    result=consolidate([(left,1),(right,1),(road,2)],valid,1,1)
    field=unary_union([g for g,label in result if label==1])
    assert field.intersection(road).area == pytest.approx(0)
    assert field.difference(valid).area == pytest.approx(0)


def test_grouping_connects_gaps_without_cross_class_overlaps():
    original=[(box(0,0,4,10),1),(box(4.5,0,10,10),1)]
    result=consolidate(original,box(0,0,10,10),1,1)
    assert len(result)==1
    assert result[0][0].area == pytest.approx(100)


@pytest.mark.parametrize('factor', [1, .3048])
def test_context_joins_fields_and_absorbs_enclosed_bright_patch(factor):
    from shapely.affinity import scale
    from farm_mapping.detection.structure import coherent_fields
    patch = box(4, 4, 6, 6)
    field = box(0, 0, 10, 10).difference(patch)
    convert = lambda g: scale(g, xfact=1/factor, yfact=1/factor, origin=(0, 0))
    candidates = [(convert(field), 1), (convert(patch), 2)]
    result, absorbed = coherent_fields(candidates, convert(box(0, 0, 10, 10)), factor, 3)
    assert absorbed == 1
    assert len(result) == 1 and result[0][1] == 1
    assert result[0][0].area * factor**2 == pytest.approx(100)
    unchanged, count = coherent_fields(candidates, convert(box(0, 0, 10, 10)), factor, 0)
    assert unchanged == candidates and count == 0


def test_context_preserves_long_road_obstacles_mask_and_boundary_patch():
    from farm_mapping.detection.structure import coherent_fields
    road = box(4, 0, 5, 20)
    tree = box(7, 7, 8, 8)
    building = box(1, 1, 3, 3)
    edge_patch = box(8, 0, 10, 2)
    valid = box(0, 0, 10, 20).difference(box(8, 18, 10, 20))
    blockers = unary_union([road, tree, building, edge_patch])
    candidates = [(valid.difference(blockers), 1), (road, 2), (tree, 4),
                  (building, 3), (edge_patch, 2)]
    result, absorbed = coherent_fields(candidates, valid, 1, 3)
    assert absorbed == 0
    fields = unary_union([g for g, label in result if label == 1])
    assert fields.intersection(blockers).area == pytest.approx(0)
    assert fields.difference(valid).area == pytest.approx(0)


def test_context_connects_nearby_field_parts_but_not_distant_fields():
    from farm_mapping.detection.structure import coherent_fields
    candidates = [(box(0, 0, 4, 10), 1), (box(6, 0, 10, 10), 1),
                  (box(25, 0, 30, 10), 1)]
    result, _ = coherent_fields(candidates, box(0, 0, 30, 10), 1, 3)
    assert len(result) == 2
    assert sum(g.area for g, _ in result) == pytest.approx(150)


@pytest.mark.parametrize('factor', [1, .3048])
def test_bright_interior_strips_join_field_but_continuous_road_and_access_remain(factor):
    from shapely.affinity import scale
    from farm_mapping.detection.structure import resolve_bright_interiors
    valid = box(0, 0, 70, 60)
    road = box(34, 0, 37, 60)
    branch = box(30, 20, 34, 22)
    strip = box(10, 15, 11, 35)  # Elongated interior, rejected by old compact-patch rule.
    access = box(50, 20, 52, 30)
    building = box(50, 30, 55, 35)
    tree = box(10, 40, 15, 45)
    blockers = unary_union([road, branch, strip, access, building, tree])
    candidates = [(valid.difference(blockers), 1), (road, 2), (branch, 2),
                  (strip, 2), (access, 2), (building, 3), (tree, 4)]
    convert = lambda g: scale(g, xfact=1/factor, yfact=1/factor, origin=(0,0))
    candidates = [(convert(g), label) for g, label in candidates]
    result, included = resolve_bright_interiors(candidates, convert(valid), factor, 3)
    assert unary_union(included).symmetric_difference(convert(strip)).area < 1e-8
    paths = unary_union([g for g, label in result if label == 2])
    assert paths.symmetric_difference(convert(unary_union([road, branch, access]))).area < 1e-8
    fields = unary_union([g for g, label in result if label == 1])
    assert fields.covers(convert(strip))
    assert fields.intersection(convert(unary_union([road, branch, access, building, tree]))).area == 0
    assert len([g for g, label in result if label == 1]) == 2
    unchanged, included = resolve_bright_interiors(candidates, convert(valid), factor, 0)
    assert unchanged == candidates and included == []


def test_bright_enclosure_required_and_orchard_class_retained():
    from farm_mapping.detection.structure import resolve_bright_interiors
    interior = box(10, 10, 12, 15)
    outside = box(40, 10, 42, 15)
    orchard = box(0, 0, 30, 30).difference(interior)
    result, included = resolve_bright_interiors([(orchard, 5), (interior, 2), (outside, 2)],
                                               box(-5, -5, 50, 50), 1, 3)
    assert len(included) == 1
    assert unary_union([g for g, label in result if label == 5]).covers(interior)
    assert not any(label == 1 for _, label in result)
    assert unary_union([g for g, label in result if label == 2]).equals(outside)


def test_open_broken_strip_uses_surrounding_field_support():
    from farm_mapping.detection.structure import resolve_bright_interiors
    strip = box(10, 8, 11, 25)
    # A thin unknown gap opens the field shell; no exact enclosure is available.
    unknown = box(10, 0, 11, 8)
    field = box(0, 0, 30, 30).difference(unary_union([strip, unknown]))
    result, included = resolve_bright_interiors([(field, 1), (strip, 2)], box(-5,-5,35,35), 1, 3)
    assert included and unary_union(included).equals(strip)
    assert not any(label == 2 for _, label in result)
