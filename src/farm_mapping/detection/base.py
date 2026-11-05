from copy import deepcopy
from dataclasses import dataclass, field
import math
from typing import Protocol
from shapely.geometry import shape, mapping
from shapely.ops import unary_union
from ..core import Project, validate_feature


@dataclass(frozen=True)
class DetectionSettings:
    max_dimension: int = 1600
    minimum_area_m2: float = 4.0
    max_features: int = 300
    grouping_distance_m: float = 1.0
    detect_orchards: bool = True
    field_context_radius_m: float = 3.0
    outline_smoothing_m: float = 0.5
    compensate_shadows: bool = False
    reconsider_bright_interiors: bool = True
    detect_rows: bool = True
    separate_structure_groups: bool = True

    def validate(self):
        if not isinstance(self.max_dimension, int) or not 64 <= self.max_dimension <= 2048:
            raise ValueError('Analyselänge muss zwischen 64 und 2048 Pixel liegen.')
        if not math.isfinite(self.minimum_area_m2) or self.minimum_area_m2 <= 0:
            raise ValueError('Mindestfläche muss endlich und größer als null sein.')
        if not math.isfinite(self.grouping_distance_m) or not 0 <= self.grouping_distance_m <= 3:
            raise ValueError('Zusammenfassungsabstand muss zwischen 0 und 3 Metern liegen.')
        if not math.isfinite(self.field_context_radius_m) or not 0 <= self.field_context_radius_m <= 5:
            raise ValueError('Flächenzusammenfassung muss zwischen 0 und 5 Metern liegen.')
        if not math.isfinite(self.outline_smoothing_m) or not 0 <= self.outline_smoothing_m <= 2:
            raise ValueError('Konturglättung muss zwischen 0 und 2 Metern liegen.')
        if not isinstance(self.max_features, int) or not 1 <= self.max_features <= 1000:
            raise ValueError('Polygonlimit muss zwischen 1 und 1000 liegen.')


@dataclass
class DetectionResult:
    features: list
    metadata: dict
    review_overlays: list = field(default_factory=list)


class Detector(Protocol):
    def detect(self, raster_path: str, expected_sha256: str,
               settings: DetectionSettings) -> DetectionResult: ...


def accept_proposals(project: Project, result: DetectionResult):
    """Append proposals without overwriting existing geometries or duplicating a run."""
    if result.metadata['input_sha256'] != project.raster['sha256']:
        raise ValueError('Die Vorschläge gehören zu einem anderen GeoTIFF.')
    if result.metadata['source_crs'] != project.raster['crs']:
        from pyproj import CRS
        if CRS(result.metadata['source_crs']) != CRS(project.raster['crs']):
            raise ValueError('Das Koordinatensystem der Vorschläge stimmt nicht überein.')
    run_id = result.metadata['run_id']
    if any(f['properties'].get('detection_run_id') == run_id for f in project.features):
        raise ValueError('Dieser Analyselauf wurde bereits übernommen.')
    existing = unary_union([shape(f['geometry']) for f in project.features])
    additions = []
    for original in result.features:
        feature = deepcopy(original)
        validate_feature(feature)
        geometry = shape(feature['geometry']).difference(existing)
        # Difference against a polygon can also leave line fragments.
        def polygons(geom):
            if geom.is_empty:
                return []
            if geom.geom_type == 'Polygon':
                return [geom]
            if hasattr(geom, 'geoms'):
                return [p for part in geom.geoms for p in polygons(part)]
            return []
        parts = polygons(geometry)
        if not parts:
            continue
        feature['geometry'] = mapping(unary_union(parts))
        feature['properties'].update(review_status='auto_detected', review_flag=True,
                                     traversability='unknown', detection_run_id=run_id,
                                     detection_metadata=deepcopy(result.metadata))
        validate_feature(feature)
        additions.append(feature)
    if additions:
        project.edit(project.features + additions)
    return len(additions)
