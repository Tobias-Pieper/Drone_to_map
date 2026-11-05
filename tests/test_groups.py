import numpy as np
import pytest
from rasterio.transform import from_origin
from shapely.geometry import box
from shapely.ops import unary_union
from farm_mapping.detection.groups import partition_fields


def descriptor(geometry, angle=0, spacing=2, color=(.3,.5,.2)):
    return dict(geometry=geometry,direction=np.deg2rad(angle),spacing=spacing,color=list(color))


@pytest.mark.parametrize('factor',[1,.3048])
def test_touching_different_row_directions_remain_separate_without_area_loss(factor):
    from shapely.affinity import scale
    convert=lambda g:scale(g,xfact=1/factor,yfact=1/factor,origin=(0,0))
    field=convert(box(0,0,40,20))
    descriptors=[descriptor(convert(box(0,0,20,20))),descriptor(convert(box(20,0,40,20)),90)]
    result=partition_fields([(field,1)],descriptors,from_origin(0,20/factor,1/factor,1/factor),40,20,factor)
    work=[(g,p) for g,label,p in result if label==1]
    assert len({p['structure_group'] for g,p in work})==2
    assert unary_union([g for g,p in work]).symmetric_difference(field).area*factor**2<1e-8
    assert sum(g.area for g,p in work)==pytest.approx(field.area)
    assert all(g.is_valid for g,p in work)


@pytest.mark.parametrize('change', [dict(angle=40),dict(spacing=4),dict(color=(.65,.2,.15))])
def test_persistent_pattern_or_color_changes_separate_groups(change):
    descriptors=[descriptor(box(0,0,20,20)),descriptor(box(20,0,40,20),**change)]
    result=partition_fields([(box(0,0,40,20),1)],descriptors,from_origin(0,20,1,1),40,20,1)
    assert len({p['structure_group'] for _,label,p in result if label==1})==2


def test_compatible_brightness_change_joins_and_unstructured_area_stays_separate():
    field=box(0,0,50,20).difference(box(23,5,24,6))
    tree=box(23,5,24,6)
    descriptors=[descriptor(box(0,0,15,20)),descriptor(box(15,0,25,20),color=(.24,.4,.16))]
    result=partition_fields([(field,1),(tree,4)],descriptors,from_origin(0,20,1,1),50,20,1)
    groups={p['structure_group'] for _,label,p in result if label==1}
    assert groups=={'rows-1','vegetation-1'}
    assert unary_union([g for g,label,_ in result if label==1]).equals(field)
    assert unary_union([g for g,label,_ in result if label==4]).equals(tree)
    assert all(g.intersection(tree).area==0 for g,label,_ in result if label==1)


def test_weak_isolated_island_does_not_create_group_boundary():
    field=box(0,0,30,30)
    result=partition_fields([(field,1)],[descriptor(box(10,10,15,15))],
                            from_origin(0,30,1,1),30,30,1)
    assert len(result)==1 and result[0][0].equals(field)
    assert result[0][2]['structure_type']=='vegetation'


def test_small_surrounded_harmonic_is_not_a_new_field():
    field=box(0,0,80,50)
    island=box(20,20,40,35)
    descriptors=[descriptor(field.difference(island),spacing=2),descriptor(island,spacing=4)]
    result=partition_fields([(field,1)],descriptors,from_origin(0,50,1,1),80,50,1)
    assert len({p['structure_group'] for _,label,p in result if label==1})==1
    assert unary_union([g for g,label,_ in result if label==1]).equals(field)
