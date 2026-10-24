"""Project geometry is stored in its source CRS; GeoJSON is always WGS84."""
from copy import deepcopy
from dataclasses import dataclass, field, asdict
from pathlib import Path
import hashlib
import json
import math
import os
import tempfile
from uuid import uuid4
from .paths import input_file

from pyproj import CRS, Transformer
from shapely.geometry import shape, mapping
from shapely import transform

CATEGORIES = ('work_area', 'navigable_area', 'obstacle')
TRAVERSABILITY = ('unknown', 'traversable', 'non_traversable')


def project_geometry(geometry, source, target):
    return transform(geometry, Transformer.from_crs(source, target, always_xy=True).transform,
                     interleaved=False)


def validate_feature(feature):
    geom = shape(feature['geometry'])
    if geom.geom_type not in ('Polygon', 'MultiPolygon') or geom.is_empty or not geom.is_valid:
        raise ValueError('Eine gültige Polygongeometrie ist erforderlich.')
    if not all(math.isfinite(v) for v in geom.bounds):
        raise ValueError('Ungültige Koordinaten.')
    props = feature['properties']
    if props['category'] not in CATEGORIES or props['traversability'] not in TRAVERSABILITY:
        raise ValueError('Ungültige Kategorie oder Befahrbarkeit.')
    if not props.get('subcategory') or props.get('review_status') not in ('auto_detected', 'manually_edited', 'approved'):
        raise ValueError('Unterkategorie und Prüfstatus sind erforderlich.')
    if props.get('id') != feature['id']:
        raise ValueError('Objekt-IDs stimmen nicht überein.')


def make_feature(geometry, category='work_area', subcategory='field', **properties):
    identifier = str(uuid4())
    result = {'type': 'Feature', 'id': identifier, 'geometry': mapping(geometry), 'properties': {
        'id': identifier, 'category': category, 'subcategory': subcategory,
        'traversability': 'unknown', 'review_status': 'manually_edited',
        'review_flag': True, **properties}}
    validate_feature(result)
    return result


@dataclass
class Project:
    name: str
    raster_path: str
    raster: dict
    features: list = field(default_factory=list)
    safety_distances: dict = field(default_factory=lambda: {'water': 1.0, 'tree': 0.0})
    approved: bool = False
    revision: int = 0
    schema_version: int = 1
    _undo: list = field(default_factory=list, repr=False)
    _redo: list = field(default_factory=list, repr=False)

    def snapshot(self):
        return deepcopy({'features': self.features, 'safety_distances': self.safety_distances})

    def edit(self, features=None, safety_distances=None):
        proposed = deepcopy(self.features if features is None else features)
        for feature in proposed:
            validate_feature(feature)
        if len({f['id'] for f in proposed}) != len(proposed):
            raise ValueError('Doppelte Objekt-ID.')
        distances = dict(self.safety_distances if safety_distances is None else safety_distances)
        if any(not math.isfinite(v) or v < 0 for v in distances.values()):
            raise ValueError('Abstände müssen endlich und nicht negativ sein.')
        self._undo.append(self.snapshot())
        self._redo.clear()
        self.features, self.safety_distances = proposed, distances
        self.invalidate()

    def invalidate(self):
        self.approved = False
        self.revision += 1
        for f in self.features:
            if f['properties']['review_status'] == 'approved':
                f['properties']['review_status'] = 'manually_edited'

    def undo(self):
        self._restore(self._undo, self._redo)

    def redo(self):
        self._restore(self._redo, self._undo)

    def _restore(self, source, target):
        if source:
            target.append(self.snapshot())
            state = source.pop()
            self.features, self.safety_distances = state['features'], state['safety_distances']
            self.invalidate()

    def approve(self):
        if not self.features:
            raise ValueError('Eine leere Karte kann nicht freigegeben werden.')
        for f in self.features:
            validate_feature(f)
            f['properties']['review_status'] = 'approved'
        self.approved = True

    def geojson(self, final=False):
        if final and not self.approved:
            raise ValueError('Vor dem finalen Export muss die Gesamtkarte freigegeben werden.')
        features = deepcopy(self.features)
        for f in features:
            validate_feature(f)
            f['geometry'] = mapping(project_geometry(shape(f['geometry']), self.raster['crs'], 'EPSG:4326'))
        return {'type': 'FeatureCollection', 'features': features, 'farm_mapping': {
            'source_crs': self.raster['crs'], 'approved': self.approved,
            'revision': self.revision, 'format': 'neutral-draft-v1',
            'robot_schema_verified': False}}

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(self)
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
        try:
            with os.fdopen(fd, 'w') as stream:
                json.dump(data, stream, ensure_ascii=False, allow_nan=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    @classmethod
    def load(cls, path):
        path = input_file(path, ('.json',), 'Projekt-JSON')
        data = json.loads(path.read_text())
        if data.get('schema_version') != 1:
            raise ValueError('Unbekannte Projektversion.')
        result = cls(**data)
        CRS.from_user_input(result.raster['crs'])
        for f in result.features:
            validate_feature(f)
        return result

    def verify_raster(self):
        if not Path(self.raster_path).is_file():
            raise ValueError('Original-GeoTIFF fehlt. Bitte Originalpfad wiederherstellen.')
        if file_hash(self.raster_path) != self.raster['sha256']:
            raise ValueError('GeoTIFF-Prüfsumme stimmt nicht mit dem Projekt überein.')


def file_hash(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()
