"""Local periodic row evidence from RGB; no reference geometries or learned weights."""
import math
import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union
from .structure import polygon_parts


def row_regions(rgb, valid, affine, factor, with_groups=False):
    """Group neighbouring windows with compatible orientation and row spacing.

    Fourier peaks must be directional and periodic, with contrast inside the
    centre cell as well as the surrounding window. Cells do not span unchecked
    gaps. Pixel footprints are mapped through the complete affine transform.
    """
    pixel_m = math.sqrt(abs(affine.a * affine.e - affine.b * affine.d)) * factor
    size = min(192, max(32, round(12 / pixel_m)))
    stride = max(8, size // 4)
    h, w = valid.shape
    if min(h, w) < size:
        result = ([], {'row_windows': 0, 'row_supported_cells': 0, 'row_strong_cells': 0})
        return (*result, []) if with_groups else result
    data = rgb.astype(np.float32) / 255
    red, green, blue = data
    channels = [(green-red) / np.maximum(red+green+blue, .05), data.mean(axis=0)]
    taper = np.outer(np.hanning(size), np.hanning(size))
    frequencies = np.fft.fftfreq(size)
    image_fx, image_fy = np.meshgrid(frequencies, frequencies)
    inverse = np.linalg.inv(np.array([[affine.a, affine.b],
                                      [affine.d, affine.e]]) * factor).T
    fx = inverse[0, 0]*image_fx + inverse[0, 1]*image_fy
    fy = inverse[1, 0]*image_fx + inverse[1, 1]*image_fy
    frequency = np.hypot(fx, fy)
    band = (frequency >= 1/6) & (frequency <= 1/.6)
    angles = np.mod(np.arctan2(fy, fx), np.pi)
    def world(x, y):
        return (affine.a*x+affine.b*y+affine.c, affine.d*x+affine.e*y+affine.f)

    cells = {}
    checked = 0
    for iy, y in enumerate(range(0, h-size+1, stride)):
        for ix, x in enumerate(range(0, w-size+1, stride)):
            if valid[y:y+size, x:x+size].mean() < .95:
                continue
            checked += 1
            lo = (size-stride)//2
            core = (slice(y+lo,y+lo+stride), slice(x+lo,x+lo+stride))
            if not valid[core].all():
                continue
            best = None
            for channel in channels:
                patch = channel[y:y+size,x:x+size]
                if patch.std() < .01 or channel[core].std() < .006:
                    continue
                power = abs(np.fft.fft2((patch-patch.mean())*taper))**2
                power[~band] = 0
                total = power.sum()
                if total <= 0:
                    continue
                peak = np.unravel_index(power.argmax(),power.shape)
                angle, freq = angles[peak], frequency[peak]
                delta = np.abs(np.angle(np.exp(2j*(angles-angle))))/2
                directional = power[delta < np.deg2rad(15)].sum()/total
                periodic = power[(delta < np.deg2rad(15)) & (abs(frequency-freq) < max(.025, freq*.25))].sum()/total
                if directional < .3 or periodic < .12 or power[peak] < total/max(1,band.sum())*5:
                    continue
                score = float(periodic)
                if best is None or score > best[0]:
                    best = (score,float(angle),float(1/freq),
                            bool(directional >= .45 and periodic >= .2
                                 and power[peak] >= total/max(1,band.sum())*8))
            if best:
                cells[iy,ix] = (best[1],best[2],x+lo,y+lo,best[3])
    visited = set()
    regions = []
    descriptors = []
    for start in sorted(cells):
        if start in visited:
            continue
        pending, group = [start], []
        visited.add(start)
        while pending:
            key = pending.pop(); group.append(key)
            angle, spacing, _, _, _ = cells[key]
            for dy,dx in ((-1,0),(1,0),(0,-1),(0,1)):
                neighbor = (key[0]+dy,key[1]+dx)
                if neighbor not in cells or neighbor in visited:
                    continue
                other, distance, _, _, _ = cells[neighbor]
                difference = abs(np.angle(np.exp(2j*(angle-other))))/2
                if difference <= np.deg2rad(20) and max(spacing,distance)/min(spacing,distance) <= 1.5:
                    pending.append(neighbor); visited.add(neighbor)
        if sum(cells[k][4] for k in group) < 4:
            continue
        # A single line of matching windows is insufficient for a whole field.
        if len({k[0] for k in group}) < 2 or len({k[1] for k in group}) < 2:
            continue
        tiles = []
        for key in group:
            _,_,x,y,_ = cells[key]
            tiles.append(Polygon([world(x,y),world(x+stride,y),
                                  world(x+stride,y+stride),world(x,y+stride)]))
        geometry = unary_union(tiles)
        radius = stride * .75 * pixel_m / factor
        geometry = geometry.buffer(radius, join_style=2, mitre_limit=2).buffer(
            -radius, join_style=2, mitre_limit=2)
        geometry = geometry.intersection(unary_union(tiles).buffer(radius))
        if geometry.area*factor**2 >= 40:
            vector = np.mean([np.exp(2j*cells[k][0]) for k in group])
            direction = float(np.angle(vector)/2 % np.pi)
            spacing = float(np.median([cells[k][1] for k in group]))
            colors = []
            for key in group:
                _,_,x,y,_ = cells[key]
                colors.append(np.median(data[:,y:y+stride,x:x+stride],axis=(1,2)))
            color = np.median(colors,axis=0)
            for part in polygon_parts(geometry):
                regions.append(part)
                descriptors.append({'geometry': part, 'direction': direction,
                                    'spacing': spacing, 'color': color.tolist()})
    result = (regions, {'row_windows': checked, 'row_supported_cells': len(cells),
                        'row_strong_cells': sum(value[4] for value in cells.values())})
    return (*result, descriptors) if with_groups else result


def apply_row_regions(candidates, regions, footprint, factor):
    """Use periodic texture to span color gaps, retaining non-row road networks."""
    if not regions:
        return candidates, []
    evidence = unary_union(regions).intersection(footprint)
    retained = []
    for geometry,label in candidates:
        if label != 2:
            retained.append((geometry,label)); continue
        coverage = geometry.intersection(evidence).area/geometry.area
        # Retain the complete connected component, including accesses, when
        # most of its footprint has no row evidence (e.g. an asphalt road).
        if coverage < .5:
            retained.append((geometry,label))
        else:
            retained.extend((p,label) for p in polygon_parts(geometry.difference(evidence)))
    protected = unary_union([g for g,label in retained if label in (2,3,4,5)])
    work = evidence.difference(protected)
    original = unary_union([g for g,label in retained if label == 1])
    fields = unary_union([original,work]).difference(protected)
    return ([(g,label) for g,label in retained if label != 1]
            + [(p,1) for p in polygon_parts(fields)]), polygon_parts(work.difference(original))
