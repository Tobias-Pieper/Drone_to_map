import numpy as np
import pytest
from rasterio.transform import from_origin, Affine
from shapely.geometry import box
from shapely.ops import unary_union
from farm_mapping.detection.rows import row_regions, apply_row_regions


def stripes(angle=0, spacing=2):
    yy,xx=np.mgrid[:240,:240]*.1
    normal=xx*np.cos(np.deg2rad(angle))+yy*np.sin(np.deg2rad(angle))
    wave=(np.cos(2*np.pi*normal/spacing)+1)/2
    rgb=np.stack([90+40*wave,110+45*wave,60+35*wave]).astype('uint8')
    # A color/brightness step must not break the repeating spatial structure.
    rgb[:,:,120:]=np.clip(rgb[:,:,120:]*.72,0,255).astype('uint8')
    return rgb


@pytest.mark.parametrize('angle', [0, 23, 65])
def test_periodic_rows_survive_color_boundaries_and_rotation(angle):
    valid=np.ones((240,240),bool)
    regions,metadata=row_regions(stripes(angle),valid,from_origin(0,24,.1,.1),1)
    union=unary_union(regions)
    assert union.area>100
    assert metadata['row_supported_cells']>10
    assert union.intersection(box(8,8,11,16)).area>10
    assert union.intersection(box(13,8,16,16)).area>10


def test_uniform_noise_and_single_brightness_edge_are_not_rows():
    rng=np.random.default_rng(8)
    uniform=np.full((3,240,240),120,dtype='uint8')
    edge=uniform.copy();edge[:,:,120:]=40
    noise=rng.integers(40,180,(3,240,240),dtype='uint8')
    diagonal=uniform.copy()
    yy,xx=np.mgrid[:240,:240];diagonal[:,xx+yy>240]=40
    for image in (uniform,edge,diagonal,noise):
        regions,_=row_regions(image,np.ones((240,240),bool),from_origin(0,24,.1,.1),1)
        assert regions==[]


def test_rows_respect_validity_and_projected_units():
    image=stripes(23)
    valid=np.ones((240,240),bool);valid[:,:120]=False
    metric=from_origin(0,24,.1,.1)
    regions,_=row_regions(image,valid,metric,1)
    assert all(g.bounds[0]>=12 for g in regions)
    feet=Affine(metric.a/.3048,0,0,0,metric.e/.3048,metric.f/.3048)
    scaled,_=row_regions(image,valid,feet,.3048)
    assert sum(g.area for g in scaled)*.3048**2==pytest.approx(sum(g.area for g in regions))


def test_structural_region_absorbs_bright_patch_but_protects_road_and_obstacles():
    region=box(0,0,20,20)
    interior=box(4,4,10,8)
    road=box(19,0,23,50)
    tree=box(10,10,12,12); building=box(2,12,5,15)
    candidates=[(box(0,0,4,20),1),(interior,2),(road,2),(tree,4),(building,3)]
    result,added=apply_row_regions(candidates,[region],box(0,0,50,50),1)
    fields=unary_union([g for g,label in result if label==1])
    assert fields.covers(interior)
    assert fields.intersection(unary_union([road,tree,building])).area==0
    assert unary_union([g for g,label in result if label==2]).equals(road)
    assert unary_union(added).area>0


def test_pipeline_row_toggle_adds_work_area_and_review_evidence(tmp_path):
    import rasterio
    from shapely.geometry import shape
    from farm_mapping.raster import open_project
    from farm_mapping.detection import ColorBaseline, DetectionSettings
    yy,xx=np.mgrid[:320,:320]
    bands=np.cos(2*np.pi*xx/20)>.2
    image=np.empty((3,320,320),dtype='uint8')
    image[:]=np.array([75,140,65])[:,None,None]
    image[:,bands]=np.array([170,170,165])[:,None]
    path=tmp_path/'rows.tif'
    with rasterio.open(path,'w',driver='GTiff',width=320,height=320,count=3,
                       dtype='uint8',crs='EPSG:32632',transform=from_origin(690000,5330000,.1,.1)) as dst:
        dst.write(image)
    p=open_project(path)
    results=[ColorBaseline().detect(p.raster_path,p.raster['sha256'],
        DetectionSettings(max_dimension=320,detect_rows=enabled,outline_smoothing_m=0)) for enabled in (False,True)]
    before,after=results
    area=lambda r: unary_union([shape(f['geometry']) for f in r.features
                                if f['properties']['category']=='work_area'])
    assert area(after).area>area(before).area+20
    assert before.metadata['row_region_count']==0
    assert after.metadata['row_added_area_m2']>0
    assert before.metadata['run_id']!=after.metadata['run_id']
    assert after.review_overlays
    assert all(shape(f['geometry']).difference(area(after)).area<1e-6 for f in after.review_overlays)
    assert all(f['properties']['traversability']=='unknown' for f in after.features)

    # Group identities and display colors must survive real project storage/undo.
    from farm_mapping.detection import accept_proposals
    from farm_mapping.core import Project
    accept_proposals(p,after)
    target=tmp_path/'groups.project.json'
    p.save(target)
    restored=Project.load(target)
    group_info=lambda fs:[(f['properties'].get('structure_group'),f['properties'].get('structure_color')) for f in fs]
    assert group_info(restored.features)==group_info(after.features)
    p.undo()
    assert p.features==[]
    p.redo()
    assert group_info(p.features)==group_info(after.features)
