"""Experimental RGB rules. These are class hypotheses, not a trained AI model."""
from dataclasses import asdict
import hashlib
import json
import math
import platform
import numpy as np
from PIL import Image, ImageFilter
import rasterio
from rasterio.enums import ColorInterp, Resampling
from rasterio.features import shapes, sieve
from rasterio.transform import Affine
from pyproj import CRS
from shapely.geometry import shape, mapping
from shapely import make_valid, transform
from shapely.ops import unary_union
from ..core import make_feature, file_hash
from .. import __version__
from ..paths import input_file
from .base import DetectionResult, DetectionSettings
from .structure import crown_candidates, regular_orchards, consolidate, polygon_parts, coherent_fields, smooth_fields, resolve_bright_interiors
from .appearance import shadow_hypotheses
from .rows import row_regions, apply_row_regions
from .groups import partition_fields

METHOD = 'rgb-groups-v8'
# Labels describe suggested semantic classes; each always carries a review reason.
CLASSES = {
    1: ('work_area', 'field', 'Vegetation bzw. regelmäßige Reihenstruktur mit räumlich zusammengefassten Teilflächen; helle Innenbereiche und Zwischenräume können einbezogen sein. Grenzen und mögliche Wege prüfen; Arbeitsfläche nicht nachgewiesen.'),
    2: ('navigable_area', 'path', 'Helle, wenig gesättigte Fläche; Weg/Befahrbarkeit nicht nachgewiesen.'),
    3: ('obstacle', 'building', 'Rötliche Fläche; Dach nur vermutet, auch Boden kann ähnlich aussehen.'),
    4: ('obstacle', 'tree', 'Dunkle Vegetation außerhalb erkannter Obstflächen; Gehölz nur vermutet.'),
    5: ('work_area', 'orchard', 'Regelmäßige Baumreihen mit Zwischenräumen; Obstfläche als Ganzes vermutet. Baumstämme und Befahrbarkeit separat prüfen.'),
}


def classify_rgb(rgb, valid):
    """Return sparse rule labels; unclassified pixels retain value zero."""
    image = np.asarray(Image.fromarray(rgb.transpose(1, 2, 0)).filter(ImageFilter.MedianFilter(5)),
                       dtype=np.float32) / 255
    red, green, blue = image.transpose(2, 0, 1)
    brightness = (red + green + blue) / 3
    spread = image.max(axis=2) - image.min(axis=2)
    vegetation = (green > red * 1.08) & (green > blue * 1.12) & (green > .12)
    labels = np.zeros(valid.shape, dtype='uint8')
    labels[vegetation] = 1
    labels[(brightness > .40) & (spread < .16) & ~vegetation] = 2
    labels[(red > green * 1.25) & (red > blue * 1.3) & (red > .30)] = 3
    labels[vegetation & (brightness < .25) & (green > red * 1.18)] = 4
    labels[~valid] = 0
    return labels


class ColorBaseline:
    def detect(self, raster_path, expected_sha256, settings=DetectionSettings()):
        settings.validate()
        path = input_file(raster_path, ('.tif', '.tiff'), 'GeoTIFF')
        checksum = file_hash(path)
        if checksum != expected_sha256:
            raise ValueError('Das GeoTIFF wurde seit dem Öffnen verändert.')
        with rasterio.open(path) as src:
            crs = CRS(src.crs) if src.crs else None
            if not crs or not crs.is_projected:
                raise ValueError('Die Baseline benötigt zunächst ein projiziertes GeoTIFF-CRS.')
            if src.count < 3 or any(dtype != 'uint8' for dtype in src.dtypes[:3]):
                raise ValueError('Die Baseline unterstützt zunächst RGB-Bänder als uint8 (8 Bit).')
            if tuple(src.colorinterp[:3]) != (ColorInterp.red, ColorInterp.green, ColorInterp.blue):
                raise ValueError('Die Baseline benötigt explizit als Rot, Grün, Blau markierte Bänder 1–3.')
            factor = crs.axis_info[0].unit_conversion_factor
            scale = min(1, settings.max_dimension / max(src.width, src.height))
            height, width = max(1, round(src.height * scale)), max(1, round(src.width * scale))
            # Nearest sampling avoids mixing transparent black borders into RGB values.
            rgb = src.read([1, 2, 3], out_shape=(3, height, width), resampling=Resampling.nearest)
            valid = src.dataset_mask(out_shape=(height, width), resampling=Resampling.nearest) > 0
            sx, sy = src.width / width, src.height / height
            t = src.transform
            affine = Affine(t.a * sx, t.b * sy, t.c, t.d * sx, t.e * sy, t.f)
            source_crs = src.crs.to_wkt()
        labels = classify_rgb(rgb, valid)
        shadow_mask = (shadow_hypotheses(rgb, labels, valid, affine, factor)
                       if settings.compensate_shadows else np.zeros_like(valid))
        original_labels = labels.copy()
        labels[shadow_mask] = 1
        pixel_area = abs(affine.a * affine.e - affine.b * affine.d) * factor ** 2
        min_pixels = max(1, math.ceil(settings.minimum_area_m2 / pixel_area))
        # Sieve each class independently so removing a small class cannot promote its neighbor.
        cleaned = np.zeros_like(labels)
        for label in (1, 2, 3, 4):
            binary = (labels == label).astype('uint8')
            filtered = sieve(binary, size=min(min_pixels, height * width), connectivity=4)
            cleaned[(filtered > 0) & (labels == label) & valid] = label
        candidates = []
        tolerance = min(math.hypot(affine.a, affine.d), math.hypot(affine.b, affine.e)) / 2
        for geometry, label in shapes(cleaned, mask=(cleaned > 0) & valid, transform=affine):
            polygon = make_valid(shape(geometry))
            if polygon.geom_type not in ('Polygon', 'MultiPolygon') or polygon.area * factor ** 2 < settings.minimum_area_m2:
                continue
            polygon = polygon.simplify(tolerance, preserve_topology=True)
            # Keep boundaries within the classified valid footprint after simplification.
            polygon = polygon.intersection(shape(geometry))
            if polygon.is_empty or polygon.geom_type not in ('Polygon', 'MultiPolygon'):
                continue
            candidates.append((polygon, int(label)))
        crowns = crown_candidates(original_labels, affine, factor) if settings.detect_orchards else []
        orchards_metric = regular_orchards(crowns) if settings.detect_orchards else []
        orchards = [transform(geometry, lambda xy: xy / factor) for geometry in orchards_metric]
        candidates.extend((geometry, 5) for geometry in orchards)
        footprint = unary_union([shape(geometry) for geometry, _ in shapes(
            valid.astype('uint8'), mask=valid, transform=affine)])
        # Orchard overrides vegetation fragments; retain roof and path evidence.
        if orchards:
            orchard_union = unary_union(orchards)
            candidates = [(part, label) for geometry, label in candidates
                          for part in polygon_parts(geometry.difference(orchard_union)
                                                    if label in (1, 4) else geometry)]
        if settings.grouping_distance_m or orchards:
            candidates = consolidate(candidates, footprint, factor, settings.grouping_distance_m)
        before_context = len(candidates)
        included = []
        if settings.reconsider_bright_interiors:
            candidates, included = resolve_bright_interiors(
                candidates, footprint, factor, settings.field_context_radius_m)
        regions, row_metadata, descriptors = (row_regions(rgb, valid, affine, factor, with_groups=True) if settings.detect_rows
                                 else ([], {'row_windows': 0, 'row_supported_cells': 0, 'row_strong_cells': 0}, []))
        candidates, row_included = apply_row_regions(candidates, regions, footprint, factor)
        candidates, absorbed = coherent_fields(candidates, footprint, factor,
                                               settings.field_context_radius_m,
                                               preserve_bright=settings.reconsider_bright_interiors)
        # Sub-threshold fragments must not leave invisible jagged constraints.
        candidates = [(geometry, label) for geometry, label in candidates
                      if geometry.area * factor ** 2 >= settings.minimum_area_m2]
        candidates = smooth_fields(candidates, footprint, factor, settings.outline_smoothing_m)
        candidates = [(geometry, label) for geometry, label in candidates
                      if geometry.area * factor ** 2 >= settings.minimum_area_m2]
        if settings.separate_structure_groups:
            candidates = partition_fields(candidates, descriptors, affine, width, height, factor)
        else:
            candidates = [(g,label,{}) for g,label in candidates]
        candidates.sort(key=lambda item: (-item[0].area, item[1], item[0].wkb_hex))
        metadata = {'method': METHOD, 'parameters': asdict(settings), 'input_sha256': checksum,
                    'source_crs': source_crs, 'analysis_size': [width, height],
                    'analysis_pixel_area_m2': pixel_area,
                    'crown_candidate_count': len(crowns), 'orchard_candidate_count': len(orchards),
                    'software_version': __version__, 'numpy_version': np.__version__,
                    'rasterio_version': rasterio.__version__, 'python_version': platform.python_version(),
                    'candidate_count': len(candidates),
                    'candidates_before_field_context': before_context,
                    'absorbed_bright_patches': absorbed,
                    'reconsidered_bright_components': len(included),
                    'reconsidered_bright_area_m2': sum(g.area for g in included) * factor**2,
                    **row_metadata,
                    'row_region_count': len(regions),
                    'row_added_area_m2': sum(g.area for g in row_included) * factor**2,
                    'structure_group_count': len({props['structure_group'] for _,_,props in candidates
                                                  if 'structure_group' in props}) + sum(label == 5 for _,label,_ in candidates),
                    'shadow_hypothesis_area_m2': float(shadow_mask.sum() * pixel_area),
                    'omitted_by_limit': max(0, len(candidates) - settings.max_features)}
        fingerprint = json.dumps(metadata, sort_keys=True).encode()
        metadata['run_id'] = hashlib.sha256(fingerprint).hexdigest()
        features = []
        has_shadow_hypotheses = bool(shadow_mask.any())
        for index, (polygon, label, group_properties) in enumerate(candidates[:settings.max_features]):
            category, subcategory, reason = CLASSES[label]
            if label == 5 and settings.separate_structure_groups:
                group_properties = {'structure_group': f'orchard-{index}', 'structure_type': 'orchard',
                                    'structure_color': '#b45309'}
            if group_properties:
                reason += ' Strukturgruppe ist ein Grenzvorschlag; Verlauf und angrenzende Gruppen prüfen.'
            if label in (1, 5) and has_shadow_hypotheses:
                reason += ' Schattenausgleich aktiv: dunkle Pixel wurden versuchsweise als Vegetation eingeordnet; mögliche Gehölze besonders prüfen.'
            feature = make_feature(polygon, category, subcategory,
                                   review_status='auto_detected', review_flag=True,
                                   source_method=METHOD, review_reason=reason,
                                   **group_properties,
                                   detection_run_id=metadata['run_id'], detection_metadata=metadata)
            identifier = f"detection-{metadata['run_id'][:20]}-{index}"
            feature['id'] = feature['properties']['id'] = identifier
            features.append(feature)
        # Only highlight portions actually present in the final, limited proposals.
        work = unary_union([shape(f['geometry']) for f in features
                            if f['properties']['category'] == 'work_area'])
        overlay = unary_union(included + row_included).intersection(work)
        overlays = [{'type': 'Feature', 'properties': {'review_reason': 'Innenbereich oder regelmäßige Reihenstruktur als Arbeitsfläche vermutet'},
                     'geometry': mapping(p)} for p in polygon_parts(overlay)]
        return DetectionResult(features, metadata, overlays)
