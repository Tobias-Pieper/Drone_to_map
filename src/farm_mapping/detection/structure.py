"""Spatial heuristics for regular orchards; no references or learned weights used."""
import math
import numpy as np
from rasterio.features import shapes
from shapely.geometry import shape, MultiPoint, Polygon
from shapely.ops import unary_union


def regular_orchards(crowns):
    """Find connected, two-dimensional approximately orthogonal crown lattices.

    Input coordinates must be metric. One row is deliberately insufficient.
    These provisional thresholds describe small agricultural tree crowns.
    """
    if len(crowns) < 9 or len(crowns) > 1500:
        return []
    points = np.array([(g.centroid.x, g.centroid.y) for g in crowns])
    delta = points[None, :, :] - points[:, None, :]
    distance = np.linalg.norm(delta, axis=2)
    eligible = (distance >= 2.0) & (distance <= 12.0)
    # Each crown votes through its closest neighbors, reducing far-pair bias.
    neighbors = np.argsort(np.where(eligible, distance, np.inf), axis=1)[:, :6]
    selected = np.zeros_like(eligible)
    np.put_along_axis(selected, neighbors, True, axis=1)
    selected &= eligible
    if selected.sum() < 16:
        return []
    angles = np.mod(np.arctan2(delta[:, :, 1], delta[:, :, 0]), math.pi / 2)
    histogram, edges = np.histogram(angles[selected], bins=90, range=(0, math.pi / 2))
    smoothed = sum(np.roll(histogram, shift) for shift in range(-4, 5))
    theta = (edges[int(smoothed.argmax())] + math.pi / 360)
    axis = np.array([math.cos(theta), math.sin(theta)])
    cross = np.array([-axis[1], axis[0]])
    x = np.abs(delta @ axis)
    y = np.abs(delta @ cross)
    aligned_x = eligible & (y < .22 * x)
    aligned_y = eligible & (x < .22 * y)
    def spacing(values, aligned):
        nearest = np.min(np.where(aligned, values, np.inf), axis=1)
        nearest = nearest[np.isfinite(nearest)]
        return float(np.median(nearest)) if len(nearest) >= 6 else None
    sx, sy = spacing(x, aligned_x), spacing(y, aligned_y)
    if sx is None or sy is None:
        return []
    edge_x = aligned_x & (np.abs(x - sx) <= .25 * sx)
    edge_y = aligned_y & (np.abs(y - sy) <= .25 * sy)
    adjacency = edge_x | edge_y
    visited = set()
    results = []
    for start in range(len(points)):
        if start in visited:
            continue
        component, pending = [], [start]
        visited.add(start)
        while pending:
            index = pending.pop()
            component.append(index)
            for neighbor in np.flatnonzero(adjacency[index]):
                if int(neighbor) not in visited:
                    visited.add(int(neighbor))
                    pending.append(int(neighbor))
        if len(component) < 9:
            continue
        indices = np.array(component)
        two_axes = edge_x[np.ix_(indices, indices)].any(axis=1) & edge_y[np.ix_(indices, indices)].any(axis=1)
        local = points[indices]
        extent_x = float(np.ptp(local @ axis))
        extent_y = float(np.ptp(local @ cross))
        if two_axes.mean() < .55 or extent_x < 1.8 * sx or extent_y < 1.8 * sy:
            continue
        hull = MultiPoint(local).convex_hull
        # Crowns must substantially occupy the inferred lattice, not an arbitrary hull.
        if hull.area <= 0 or len(indices) * sx * sy / hull.area < .55:
            continue
        results.append(hull.buffer(min(sx, sy) * .4, join_style=2))
    return results


def crown_candidates(labels, affine, factor):
    """Isolated dark vegetation blobs; long hedges and broad woods are excluded."""
    from shapely import transform
    candidates = []
    for geometry, _ in shapes((labels == 4).astype('uint8'), mask=labels == 4, transform=affine):
        polygon = shape(geometry)
        area = polygon.area * factor ** 2
        if not .7 <= area <= 55:
            continue
        bounds = polygon.bounds
        w, h = bounds[2] - bounds[0], bounds[3] - bounds[1]
        if min(w, h) <= 0 or max(w, h) / min(w, h) > 3:
            continue
        candidates.append(transform(polygon, lambda xy: xy * factor))
    return candidates


def polygon_parts(geometry):
    if geometry.is_empty:
        return []
    if geometry.geom_type == 'Polygon':
        return [geometry]
    if hasattr(geometry, 'geoms'):
        return [p for g in geometry.geoms for p in polygon_parts(g)]
    return []


def resolve_bright_interiors(candidates, valid_footprint, factor, radius_m):
    """Reconsider bright components using field enclosure and road continuity.

    Long continuous corridors, boundary contacts, building access and direct
    connections to major corridors retain priority. Returned geometries are
    review evidence, not additional map objects.
    """
    if not radius_m:
        return candidates, []
    fields = unary_union([g for g, label in candidates if label in (1, 5)])
    if fields.is_empty:
        return candidates, []
    radius = radius_m / factor
    envelope = fields.buffer(radius, join_style=2, mitre_limit=2).buffer(
        -radius, join_style=2, mitre_limit=2)
    envelope = unary_union([Polygon(p.exterior) for p in polygon_parts(envelope)])
    bright = polygon_parts(unary_union([g for g, label in candidates if label == 2]))
    dimensions = []
    for geometry in bright:
        coords = list(geometry.minimum_rotated_rectangle.exterior.coords)
        sides = [math.dist(coords[i], coords[i+1]) * factor for i in range(4)]
        dimensions.append((max(sides), max(sides) / max(min(sides), 1e-9)))
    major = [g for g, (length, aspect) in zip(bright, dimensions)
             if (length >= 30 and aspect >= 5)
             or (length >= 15 and g.distance(valid_footprint.boundary) * factor < .5)]
    network = unary_union(major)
    buildings = unary_union([g for g, label in candidates if label == 3])
    orchard_shell = unary_union([Polygon(p.exterior) for g, label in candidates
                                if label == 5 for p in polygon_parts(g)])
    retained = [(g, label) for g, label in candidates if label != 2]
    included = []
    for geometry, (length, aspect) in zip(bright, dimensions):
        ring = geometry.buffer(radius).difference(geometry).intersection(valid_footprint)
        support = ring.intersection(fields).area / ring.area if ring.area else 0
        # Broken strips can open a shell to unclassified soil. Strong local
        # field support may establish an interior even without a closed ring.
        closed_interior = envelope.covers(geometry.buffer(.25 / factor))
        enclosed = closed_interior or support >= .7
        connected = not network.is_empty and geometry.distance(network) * factor <= .5
        access = not buildings.is_empty and geometry.distance(buildings) * factor <= 1
        boundary = geometry.distance(valid_footprint.boundary) * factor < .5
        compact_interior = closed_interior and aspect <= 3 and geometry.area * factor**2 <= 100
        if (enclosed and (support >= .6 or compact_interior) and not connected and not access and not boundary
                and geometry.area * factor**2 <= 300 and length < 30):
            included.append(geometry)
            # Orchard interiors keep the orchard class instead of becoming fields.
            retained.extend((p, 5) for p in polygon_parts(geometry.intersection(orchard_shell)))
            retained.extend((p, 1) for p in polygon_parts(geometry.difference(orchard_shell)))
        else:
            retained.append((geometry, 2))
    # Remove same-class seams introduced by reclassification before smoothing.
    output = []
    for label in (1, 2, 3, 4, 5):
        output.extend((p, label) for p in polygon_parts(unary_union(
            [g for g, key in retained if key == label])))
    return output, included


def coherent_fields(candidates, valid_footprint, factor, radius_m, preserve_bright=False):
    """Join nearby field evidence while retaining obstacles and elongated paths.

    A compact bright patch fully enclosed by the inferred field envelope may be
    dry soil rather than a road. This is a reviewable hypothesis, not semantics.
    All distances/areas are evaluated in metric units, including rotated rasters.
    """
    if not radius_m:
        return candidates, 0
    fields = unary_union([g for g, label in candidates if label == 1])
    if fields.is_empty:
        return candidates, 0
    radius = radius_m / factor
    envelope = fields.buffer(radius, join_style=2).buffer(-radius, join_style=2)
    # Fill bounded illumination holes, never arbitrary exterior background.
    envelope = unary_union([
        Polygon(p.exterior.coords, [ring.coords for ring in p.interiors
                if Polygon(ring).area * factor ** 2 > 100])
        for p in polygon_parts(envelope)])
    retained, absorbed = [], 0
    for geometry, label in candidates:
        if label == 1:
            continue
        rectangle = geometry.minimum_rotated_rectangle
        coordinates = list(rectangle.exterior.coords)
        sides = [math.dist(coordinates[i], coordinates[i + 1]) for i in range(4)]
        compact = min(sides) > 0 and max(sides) / min(sides) <= 3
        # Require a margin: paths along the outside boundary stay separate.
        inside = envelope.covers(geometry.buffer(.25 / factor))
        if not preserve_bright and label == 2 and geometry.area * factor ** 2 <= 100 and compact and inside:
            absorbed += 1
        else:
            retained.append((geometry, label))
    protected = unary_union([g for g, _ in retained])
    field = envelope.intersection(valid_footprint).difference(protected)
    return retained + [(p, 1) for p in polygon_parts(field)], absorbed


def smooth_fields(candidates, valid_footprint, factor, tolerance_m):
    """Close narrow notches and open narrow spurs on field exteriors.

    Radius controls the size of features removed, rather than a vertex-only
    simplification tolerance. Holes and other classes are restored afterwards.
    Small standalone fields survive even when opening would erase them.
    """
    if not tolerance_m:
        return candidates
    retained = [(g, label) for g, label in candidates if label != 1]
    protected = unary_union([g for g, _ in retained])
    result = []
    for polygon, label in candidates:
        if label != 1:
            continue
        holes = unary_union([Polygon(ring) for ring in polygon.interiors])
        exterior = Polygon(polygon.exterior)
        radius = tolerance_m / factor
        # Mitred joins retain large straight corners; limited mitres avoid spikes.
        closed = exterior.buffer(radius, join_style=2, mitre_limit=2).buffer(
            -radius, join_style=2, mitre_limit=2)
        opened = closed.buffer(-radius, join_style=2, mitre_limit=2).buffer(
            radius, join_style=2, mitre_limit=2)
        outline = opened if not opened.is_empty else exterior
        outline = outline.simplify(radius / 4, preserve_topology=True)
        candidate = outline.difference(holes).difference(protected).intersection(valid_footprint)
        result.append(candidate if not candidate.is_empty else polygon)
    # Neighbouring simplified field outlines may touch or overlap.
    return retained + [(part, 1) for part in polygon_parts(unary_union(result))]


def consolidate(candidates, valid_footprint, factor, gap_m):
    """Close small within-class gaps; preserve visible other-class boundaries."""
    groups = {}
    for polygon, label in candidates:
        groups.setdefault(label, []).append(polygon)
    original = {key: unary_union(value) for key, value in groups.items()}
    output = []
    claimed = unary_union([])
    for label in (5, 3, 2, 4, 1):
        if label not in original:
            continue
        geometry = original[label]
        if gap_m and label != 5:
            radius = gap_m / factor
            geometry = geometry.buffer(radius, join_style=2).buffer(-radius, join_style=2)
            # Small holes from illumination should not split a structure into islands.
            filled = []
            for polygon in polygon_parts(geometry):
                holes = [ring.coords for ring in polygon.interiors
                         if Polygon(ring).area * factor ** 2 > 20]
                filled.append(Polygon(polygon.exterior.coords, holes))
            geometry = unary_union(filled)
        others = unary_union([geom for key, geom in original.items() if key != label and not (label == 5 and key in (1, 4))])
        geometry = geometry.difference(others).difference(claimed).intersection(valid_footprint)
        claimed = unary_union([claimed, geometry])
        output.extend((part, label) for part in polygon_parts(geometry))
    return output
