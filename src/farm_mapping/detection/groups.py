"""Partition work proposals by persistent structure groups after all consolidation."""
import math
import numpy as np
from rasterio.features import shapes
from rasterio.transform import Affine
from shapely import points, distance
from shapely.geometry import shape
from shapely.ops import unary_union
from .structure import polygon_parts

PALETTE = ['#2563eb','#0d9488','#4f46e5','#0891b2','#ca8a04','#475569','#0284c7','#64748b']


def compatible(first, second, factor):
    delta = abs(np.angle(np.exp(2j*(first['direction']-second['direction']))))/2
    a,b=np.array(first['color']),np.array(second['color'])
    chroma=np.linalg.norm(a/max(a.sum(),.01)-b/max(b.sum(),.01))
    return (delta <= np.deg2rad(15)
            and max(first['spacing'],second['spacing'])/min(first['spacing'],second['spacing']) <= 1.35
            and chroma <= .1 and abs(a.mean()-b.mean()) <= .18
            and first['geometry'].distance(second['geometry'])*factor <= 12)


def partition_fields(candidates, descriptors, affine, width, height, factor):
    """Return (geometry, label, group properties), conserving the entire work mask.

    Nearby compatible evidence is grouped first. Nearest supported group may
    extend at most 6 m beyond evidence. Remaining vegetation stays separate;
    absence of periodic evidence does not imply a meadow or traversability.
    """
    clusters=[]
    for item in sorted(descriptors,key=lambda d:(-d['geometry'].area,d['geometry'].wkb_hex)):
        match=next((c for c in clusters if compatible(c,item,factor)),None)
        if match is None:
            clusters.append(dict(item))
        else:
            match['geometry']=unary_union([match['geometry'],item['geometry']])
    # Reject isolated tiny pattern islands as boundaries, while conserving field area.
    clusters=[c for c in clusters if c['geometry'].area*factor**2 >= 250]
    fields=unary_union([g for g,label in candidates if label==1])
    result=[(g,label,{}) for g,label in candidates if label!=1]
    if fields.is_empty:
        return result
    if not clusters:
        return result+[(g,1,{'structure_type':'vegetation','structure_group':'vegetation-1',
                            'structure_color':'#16a34a'}) for g in polygon_parts(fields)]
    pixel_m=math.sqrt(abs(affine.a*affine.e-affine.b*affine.d))*factor
    step=max(1,round(1/pixel_m),math.ceil(max(width,height)/512))
    grid=Affine(affine.a*step,affine.b*step,affine.c,
                affine.d*step,affine.e*step,affine.f)
    h,w=math.ceil(height/step),math.ceil(width/step)
    yy,xx=np.mgrid[:h,:w]
    x=grid.a*(xx+.5)+grid.b*(yy+.5)+grid.c
    y=grid.d*(xx+.5)+grid.e*(yy+.5)+grid.f
    centers=points(x.ravel(),y.ravel())
    best=np.full(x.size,6/factor)
    labels=np.zeros(x.size,dtype='int32')
    for index,cluster in enumerate(clusters,1):
        distances=distance(centers,cluster['geometry'])
        selected=distances<best
        best[selected]=distances[selected];labels[selected]=index
    # The shared raster boundary partitions exactly; no post-partition union/glättung.
    for geometry,index in shapes(labels.reshape(h,w),transform=grid):
        index=int(index)
        cut=shape(geometry).intersection(fields)
        if cut.is_empty:
            continue
        properties={'structure_group':f'rows-{index}' if index else 'vegetation-1',
                    'structure_type':'rows' if index else 'vegetation',
                    'structure_color':PALETTE[(index-1)%len(PALETTE)] if index else '#16a34a'}
        if index:
            cluster=clusters[index-1]
            properties.update(row_direction_deg=math.degrees(cluster['direction']),
                              row_spacing_m=cluster['spacing'])
        result.extend((p,1,properties.copy()) for p in polygon_parts(cut))
    # Small fragments along a provisional boundary do not justify extra objects.
    masks = {}
    properties_by_group = {}
    for geometry,label,properties in result:
        if label == 1:
            key = properties['structure_group']
            masks.setdefault(key,[]).append(geometry)
            properties_by_group[key] = properties
    masks = {key: unary_union(parts) for key,parts in masks.items()}
    # A small surrounded island can be a Fourier harmonic (every second row),
    # rather than a separate planting. Never use this to join two large fields.
    for key in sorted(masks):
        if not key.startswith('rows-') or masks[key].is_empty:
            continue
        source = clusters[int(key.split('-')[1])-1]
        for other in sorted(masks):
            if other == key or not other.startswith('rows-') or masks[other].is_empty:
                continue
            if masks[key].area > .12*masks[other].area:
                continue
            target = clusters[int(other.split('-')[1])-1]
            ratio = max(source['spacing'],target['spacing'])/min(source['spacing'],target['spacing'])
            angle = abs(np.angle(np.exp(2j*(source['direction']-target['direction']))))/2
            a,b=np.array(source['color']),np.array(target['color'])
            chroma=np.linalg.norm(a/max(a.sum(),.01)-b/max(b.sum(),.01))
            shared = masks[key].boundary.intersection(masks[other].boundary).length
            if (abs(ratio/2-1) <= .15 and angle <= np.deg2rad(15) and chroma <= .1
                    and shared >= .6*masks[key].boundary.length):
                masks[other]=unary_union([masks[other],masks[key]])
                masks[key]=masks[key].difference(masks[key])
                break
    for key in sorted(masks):
        for part in polygon_parts(masks[key]):
            if part.area*factor**2 >= 25:
                continue
            neighbours = [(part.boundary.intersection(g.boundary).length,other)
                          for other,g in masks.items() if other != key and not g.is_empty]
            length,other = max(neighbours,default=(0,None))
            if length*factor > .1:
                masks[key] = masks[key].difference(part)
                masks[other] = unary_union([masks[other],part])
    return ([(g,label,p) for g,label,p in result if label != 1]
            + [(part,1,properties_by_group[key].copy()) for key,g in masks.items()
               for part in polygon_parts(g)])
