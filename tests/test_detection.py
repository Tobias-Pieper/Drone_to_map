from copy import deepcopy
import numpy as np
import pytest
import rasterio
from rasterio.enums import ColorInterp
from rasterio.transform import from_origin
from shapely.geometry import box, shape
from farm_mapping.core import Project, make_feature
from farm_mapping.raster import open_project
from farm_mapping.detection import ColorBaseline, DetectionSettings, accept_proposals


@pytest.fixture
def scene(tmp_path):
    path = tmp_path / 'scene.tif'
    image = np.zeros((4, 128, 128), dtype='uint8')
    image[3] = 255
    # Well separated, simple rule targets; not a semantic quality benchmark.
    for rows, cols, color in [((8,48),(8,48),(75,150,65)),
                               ((8,48),(72,112),(180,180,175)),
                               ((72,112),(8,48),(180,90,70)),
                               ((72,112),(72,112),(30,70,25))]:
        image[:3, rows[0]:rows[1], cols[0]:cols[1]] = np.array(color)[:,None,None]
    image[3, :4] = 0
    with rasterio.open(path, 'w', driver='GTiff', width=128, height=128,
                       count=4, dtype='uint8', crs='EPSG:32632',
                       transform=from_origin(690000,5330000,.1,.1)) as dst:
        dst.colorinterp = (ColorInterp.red,ColorInterp.green,ColorInterp.blue,ColorInterp.alpha)
        dst.write(image)
    return open_project(path)


def test_detection_classes_georeference_and_provenance(scene):
    settings = DetectionSettings(max_dimension=128, minimum_area_m2=1)
    result = ColorBaseline().detect(scene.raster_path,scene.raster['sha256'],settings)
    assert {f['properties']['category'] for f in result.features} == {'work_area','navigable_area','obstacle'}
    assert {f['properties']['subcategory'] for f in result.features} == {'field','path','building','tree'}
    for feature in result.features:
        geom = shape(feature['geometry'])
        assert geom.is_valid and geom.bounds[0] >= 690000
        assert geom.bounds[3] <= 5330000 - .4
        props = feature['properties']
        assert props['review_status'] == 'auto_detected' and props['review_flag']
        assert props['traversability'] == 'unknown' and 'confidence' not in props
        assert props['detection_metadata']['input_sha256'] == scene.raster['sha256']
    again = ColorBaseline().detect(scene.raster_path,scene.raster['sha256'],settings)
    assert [f['id'] for f in again.features] == [f['id'] for f in result.features]
    assert result.metadata['omitted_by_limit'] == 0


def test_accept_preserves_existing_and_supports_undo(scene,tmp_path):
    settings=DetectionSettings(max_dimension=128,minimum_area_m2=1)
    result=ColorBaseline().detect(scene.raster_path,scene.raster['sha256'],settings)
    original=make_feature(box(690000,5329994,690005,5330000), notes='manual reference')
    scene.edit([original])
    before=deepcopy(scene.features)
    scene.approve()
    assert accept_proposals(scene,result)>0
    assert not scene.approved
    assert scene.features[0]['geometry'] == before[0]['geometry']
    assert scene.features[0]['properties']['notes']=='manual reference'
    for feature in scene.features[1:]:
        assert shape(feature['geometry']).intersection(shape(original['geometry'])).area == pytest.approx(0)
    with pytest.raises(ValueError,match='bereits'):
        accept_proposals(scene,result)
    scene.save(tmp_path/'project.json')
    restored=Project.load(tmp_path/'project.json')
    assert restored.features[-1]['properties']['detection_metadata']['run_id']==result.metadata['run_id']
    scene.undo()
    assert len(scene.features)==1
    scene.redo()
    assert len(scene.features)>1


def test_fully_covered_scene_and_empty_output(scene):
    result=ColorBaseline().detect(scene.raster_path,scene.raster['sha256'],DetectionSettings(max_dimension=128))
    scene.edit([make_feature(box(689000,5329000,691000,5331000))])
    revision=scene.revision
    assert accept_proposals(scene,result)==0
    assert scene.revision==revision


def test_limits_hash_and_settings(scene):
    detector=ColorBaseline()
    with pytest.raises(ValueError,match='verändert'):
        detector.detect(scene.raster_path,'wrong')
    with pytest.raises(ValueError):
        detector.detect(scene.raster_path,scene.raster['sha256'],DetectionSettings(minimum_area_m2=float('nan')))
    limited=detector.detect(scene.raster_path,scene.raster['sha256'],DetectionSettings(max_dimension=64,minimum_area_m2=1,max_features=1))
    assert len(limited.features)==1 and limited.metadata['omitted_by_limit']>=1
    assert max(limited.metadata['analysis_size'])==64
    other=deepcopy(limited)
    other.metadata['input_sha256']='wrong'
    with pytest.raises(ValueError,match='anderen'):
        accept_proposals(scene,other)


def test_regular_tree_grid_is_a_whole_work_area(tmp_path):
    path=tmp_path/'orchard.tif'
    image=np.empty((3,200,200),dtype='uint8')
    image[:]=np.array([95,140,70])[:,None,None]
    yy,xx=np.ogrid[:200,:200]
    for row in range(4):
        for col in range(5):
            mask=(xx-(30+col*20))**2+(yy-(30+row*24))**2 <= 5**2
            image[:,mask]=np.array([30,70,25])[:,None]
    with rasterio.open(path,'w',driver='GTiff',width=200,height=200,count=3,
                       dtype='uint8',crs='EPSG:32632',
                       transform=from_origin(690000,5330000,.25,.25)) as dst:
        dst.write(image)
    p=open_project(path)
    result=ColorBaseline().detect(p.raster_path,p.raster['sha256'],DetectionSettings(max_dimension=200))
    orchards=[f for f in result.features if f['properties']['subcategory']=='orchard']
    assert len(orchards)==1
    orchard=shape(orchards[0]['geometry'])
    assert orchard.area>300
    assert orchards[0]['properties']['category']=='work_area'
    assert orchards[0]['properties']['traversability']=='unknown'
    for feature in result.features:
        if feature['properties']['category']=='obstacle':
            assert shape(feature['geometry']).intersection(orchard).area == pytest.approx(0)
    settings=DetectionSettings(max_dimension=200,detect_orchards=False,grouping_distance_m=0)
    simple=ColorBaseline().detect(p.raster_path,p.raster['sha256'],settings)
    assert not any(f['properties']['subcategory']=='orchard' for f in simple.features)
