"""Local first-increment UI. All paths refer to the server's local filesystem."""
from copy import deepcopy
from functools import partial
import json
import os
from pathlib import Path
from uuid import uuid4
from shapely.geometry import Point, Polygon, shape, mapping
from fastapi import Response
from nicegui import app, ui
from .core import Project, CATEGORIES, TRAVERSABILITY, make_feature, project_geometry, file_hash
from .raster import open_project, preview, ensure_raster_summary
from .safety import exclusion_zones
from .editing import vertex_positions, move_vertex, edge_midpoints, insert_vertex
from .metadata import FLIGHT_FIELDS, DRONE_CLASSES, validate_flight, flight_log_csv
from .tiles import MAX_ZOOM, register, render_tile
from .accuracy import (REFERENCE_COLUMNS, read_rows, parse_reference_points, project_reference,
                       project_measured_points, project_point_errors, summarize, csv_text)


def main():
    workspace = Path('workspace').resolve()
    workspace.mkdir(exist_ok=True)
    data_dir = Path('data').resolve()
    data_dir.mkdir(exist_ok=True)
    app.add_static_files('/local-previews', str(workspace))

    @app.get('/tiles/{token}/{z}/{x}/{y}.png')
    def tile(token: str, z: int, x: int, y: int):
        try:
            content = render_tile(token, z, x, y)
        except KeyError:
            return Response(status_code=404)
        return Response(content, media_type='image/png', headers={'Cache-Control': 'max-age=86400'})

    @ui.page('/')
    def page():
        state = {'project': None, 'layers': [], 'vertices': [], 'measure_layers': [], 'max_native_zoom': 0}
        vertex_event = 'farm-vertex-' + str(uuid4())
        selection_event = 'farm-selection-' + str(uuid4())
        insert_event = 'farm-insert-' + str(uuid4())
        ui.add_css('.farm-measuring, .farm-measuring .leaflet-interactive { cursor: crosshair !important; }')
        ui.add_css('.farm-insert-label { background: transparent; border: none; box-shadow: none; color: white; font-weight: bold; font-size: 16px; }')
        ui.label('Farm Mapping · Kartenprüfung').classes('text-2xl')
        ui.label('Entwürfe prüfen. Neutraler GeoJSON-Export; Feldfreund-Schnittstelle noch offen.')
        with ui.card().classes('w-full'):
            ui.label('Karte öffnen').classes('text-lg font-medium')
            ui.upload(label='GeoTIFF (.tif/.tiff) oder Projekt (.json) hochladen',
                      auto_upload=True, on_upload=lambda e: uploaded(e)).props(
                          'accept=".tif,.tiff,.json" flat bordered').classes('w-full')
            ui.label('Datei hierher ziehen oder auf „+“ klicken. GeoTIFFs werden im Ordner '
                     '„data“ gespeichert, Projekte in „workspace“, und direkt geöffnet.').classes('text-sm text-gray-600')
            recent = ui.select({}, label='Bereits hochgeladene Datei öffnen',
                               on_change=lambda e: e.value and guard(lambda: open_file(e.value))).classes('w-full')
            with ui.expansion('Erweitert: Datei über lokalen Pfad öffnen').classes('w-full'):
                path = ui.input('Lokaler GeoTIFF- oder Projekt-JSON-Pfad').classes('w-full')
                with ui.row():
                    ui.button('GeoTIFF öffnen', on_click=lambda: guard(load_raster))
                    ui.button('Projekt öffnen', on_click=lambda: guard(load_project))
        status = ui.label('Kein Projekt geladen')

        def refresh_recent():
            files = sorted(data_dir.glob('*.tif')) + sorted(data_dir.glob('*.tiff')) + sorted(
                file for file in workspace.glob('*.json') if not file.name.startswith('.'))
            recent.set_options({str(file): f'{file.parent.name}/{file.name}' for file in files})

        def open_file(value):
            path.value = value
            if Path(value).suffix.lower() == '.json':
                load_project()
            else:
                load_raster()

        def unique_path(folder, name):
            target = folder / Path(name).name
            stem, suffix, index = target.stem, target.suffix, 1
            while target.exists():  # never overwrite an earlier upload
                target = target.with_name(f'{stem}-{index}{suffix}')
                index += 1
            return target

        async def uploaded(e):
            suffix = Path(e.file.name).suffix.lower()
            if suffix not in ('.tif', '.tiff', '.json'):
                ui.notify('Bitte eine .tif/.tiff- oder .json-Datei hochladen.', type='negative')
                return
            folder = workspace if suffix == '.json' else data_dir
            target = unique_path(folder, e.file.name)
            await e.file.save(target)
            e.sender.reset()
            digest = file_hash(target)
            same_name_first = lambda file: (file.name != Path(e.file.name).name, file.name)
            duplicate = next((file for file in sorted(folder.glob('*' + suffix), key=same_name_first)
                              if file != target and file.stat().st_size == target.stat().st_size
                              and file_hash(file) == digest), None)
            if duplicate:  # identical file already uploaded: open that one instead of keeping a copy
                target.unlink()
                target = duplicate
                ui.notify(f'Datei war schon vorhanden: {target.name}', type='info')
            else:
                ui.notify(f'{target.name} hochgeladen.', type='positive')
            refresh_recent()
            guard(lambda: open_file(str(target)))
        with ui.card().classes('w-full') as image_overview:
            ui.label('Bildübersicht').classes('text-lg font-medium')
            image_name = ui.label()
            with ui.row().classes('gap-8'):
                image_resolution = ui.label()
                image_area = ui.label()
                image_dimensions = ui.label()
                image_crs = ui.label()
            ui.label('Bildfläche ohne transparente/ungültige Pixel; keine Feldgrenzenmessung.').classes('text-sm text-gray-600')
        image_overview.set_visibility(False)
        m = ui.leaflet(options={'maxZoom': MAX_ZOOM}, draw_control={
            'draw': {'polygon': True, 'rectangle': False, 'marker': False, 'circle': False,
                     'polyline': False, 'circlemarker': False},
            'edit': {'edit': False, 'remove': False}}, hide_drawn_items=True).classes('w-full').style('height: 70vh; min-height: 500px')
        m.clear_layers()  # remove default online OpenStreetMap tiles
        selected = ui.select({}, label='Polygon').classes('w-full')
        edit_vertices = ui.switch('Stützpunkte auf der Karte verschieben', value=False,
                                  on_change=lambda: guard(render_vertices))
        ui.label('Polygon auf der Karte anklicken oder in der Liste auswählen. '
                 'Zum Bearbeiten den Schalter aktivieren und die Marker ziehen. '
                 'Blaue Plus-Punkte auf einer Kante fügen einen neuen Stützpunkt hinzu.')
        with ui.row():
            category = ui.select(list(CATEGORIES), value='work_area', label='Kategorie')
            subtype = ui.input('Unterkategorie', value='field')
            traversal = ui.select(list(TRAVERSABILITY), value='unknown', label='Befahrbarkeit')
        notes = ui.input('Bemerkung').classes('w-full')
        coordinates = ui.textarea('Geometrie bearbeiten: GeoJSON in WGS84 (Länge, Breite)').classes('w-full')
        with ui.card().classes('w-full'):
            ui.label('Polygone und Bereiche').classes('text-lg font-medium')
            ui.label('Eintrag anklicken, um das Polygon zur Bearbeitung auszuwählen.').classes('text-sm text-gray-600')
            polygon_list = ui.column().classes('w-full gap-3')
            with polygon_list:
                ui.label('Noch keine Polygone vorhanden. Zeichne ein Polygon oder öffne ein gespeichertes Projekt.')
        with ui.expansion('Sicherheitsabstände und Sperrzonen', value=True).classes('w-full'):
            ui.label('Zusatzabstände in Metern. Prototyp-Defaults: Wasser 1 m, sonst 0 m. '
                     'Hindernisse bleiben auch bei 0 m gesperrt.')
            show_zones = ui.switch('Sperrzonen anzeigen', value=True,
                                   on_change=lambda: guard(refresh))
            safety_form = ui.column().classes('w-full')
            ui.button('Abstände übernehmen', on_click=lambda: guard(apply_safety))
            ui.button('Sperrzonen als GeoJSON', on_click=lambda: guard(export_zones))
        with ui.expansion('Flugdaten für die Genauigkeitsauswertung').classes('w-full'):
            ui.label('Wie wurde diese Karte erstellt? Gleiche Felder wie templates/flight_log.csv. '
                     'Pflichtfelder mit *.').classes('text-sm text-gray-600')
            flight_inputs = {}
            with ui.grid(columns=3).classes('w-full'):
                for name, kind, required, hint in FLIGHT_FIELDS:
                    label = name + (' *' if required else '')
                    if name == 'drone_class':
                        flight_inputs[name] = ui.select(list(DRONE_CLASSES), label=label)
                    elif kind in (int, float):
                        flight_inputs[name] = ui.number(label, min=0, format='%.6g')
                    else:
                        flight_inputs[name] = ui.input(label)
                    flight_inputs[name].tooltip(hint)
            with ui.row():
                ui.button('Flugdaten übernehmen', on_click=lambda: guard(apply_flight))
                ui.button('Flugdaten als CSV-Zeile', on_click=lambda: guard(export_flight))
        with ui.expansion('Kontrollpunkte messen').classes('w-full'):
            ui.label('1. Flugdaten übernehmen (farm, map_id). 2. reference_points.csv des RTK-Rovers '
                     'hochladen. 3. Punkt wählen, Messmodus einschalten, ganz hineinzoomen und auf die '
                     'Mitte des Ziels im Bild klicken. Danach ist der nächste offene Punkt gewählt.'
                     ).classes('text-sm text-gray-600')
            ui.upload(label='reference_points.csv hochladen', auto_upload=True,
                      on_upload=lambda e: reference_uploaded(e)).props(
                          'accept=".csv" flat bordered').classes('w-full')
            reference_info = ui.label('Keine Referenzpunkte geladen.')
            with ui.row().classes('w-full items-center'):
                point_select = ui.select({}, label='Kontrollpunkt').classes('w-72')
                # Toggle the cursor class in the browser: m.classes() would replace Leaflet's own classes.
                measure_mode = ui.switch('Messmodus: Klick setzt den Punkt', on_change=lambda e: ui.run_javascript(
                    f'getElement({m.id}).map.getContainer().classList.toggle("farm-measuring", {str(e.value).lower()})'))
                show_references = ui.switch('Referenzpositionen als Suchhilfe', value=True,
                                            on_change=lambda: guard(render_measurements))
                show_errors = ui.switch('Fehler anzeigen', on_change=lambda: guard(render_measurements))
                show_errors.tooltip('Erst nach dem Messen einschalten, damit die Klicks unbeeinflusst bleiben.')
            with ui.row():
                ui.button('Messung löschen', on_click=lambda: guard(delete_measurement))
                ui.button('Messpunkte als CSV', on_click=lambda: guard(export_measurements))
            measure_summary = ui.label()
            measure_table = ui.table(columns=[
                {'name': name, 'label': label, 'field': name, 'align': 'left'} for name, label in (
                    ('point_id', 'Punkt'), ('role', 'Rolle'), ('structure_type', 'Struktur'),
                    ('status', 'Status'), ('dx_cm', 'dx (cm)'), ('dy_cm', 'dy (cm)'),
                    ('error_cm', 'Fehler 2D (cm)'))], rows=[], row_key='point_id').classes('w-full')
        safety_inputs = {}
        output = ui.input('Projekt-Speicherpfad', value=str(workspace / 'project.json')).classes('w-full')

        def guard(action):
            try:
                action()
            except Exception as exc:
                ui.notify(str(exc), type='negative')

        def project():
            if state['project'] is None:
                raise ValueError('Bitte zuerst ein Projekt öffnen.')
            return state['project']

        def render_polygon_list():
            features = project().features
            polygon_list.clear()
            labels = {'work_area': ('Arbeitsflächen', 'green'),
                      'navigable_area': ('Potenziell befahrbare Bereiche', 'orange'),
                      'obstacle': ('Hindernisse', 'red')}
            traversal_labels = {'unknown': 'Befahrbarkeit unbekannt',
                                'traversable': 'als befahrbar markiert',
                                'non_traversable': 'nicht befahrbar'}
            with polygon_list:
                if not features:
                    ui.label('Noch keine Polygone vorhanden. Zeichne ein Polygon oder öffne ein gespeichertes Projekt.')
                    return
                for category_key, (label, color) in labels.items():
                    members = [(index, feature) for index, feature in enumerate(features, 1)
                               if feature['properties']['category'] == category_key]
                    with ui.column().classes('w-full gap-1'):
                        with ui.row().classes('items-center gap-2'):
                            ui.badge(str(len(members)), color=color)
                            ui.label(label).classes('font-medium')
                        for index, feature in members:
                            props = feature['properties']
                            name = props.get('name') or f'Polygon {index}'
                            text = (f"{name} · {props['subcategory']} · "
                                    f"{traversal_labels[props['traversability']]} · ID {feature['id'][:8]}")
                            ui.button(text, color=color,
                                      on_click=partial(selected.set_value, feature['id'])).props(
                                          'flat no-caps align=left').classes('w-full').style(
                                              f'border-left: 4px solid {color}')

        def refresh():
            p = project()
            for layer in state['layers']:
                m.remove_layer(layer)
            state['layers'] = []
            colors = dict(work_area='green', navigable_area='orange', obstacle='red')
            for f in p.geojson()['features']:
                layer = m.generic_layer(name='geoJSON', args=[f, {
                    'style': {'color': colors[f['properties']['category']], 'dashArray': '5 5'}}])
                state['layers'].append(layer)
                layer.run_method(':on', json.dumps('click'),
                                 f'e => emitEvent({json.dumps(selection_event)}, {json.dumps(f["id"])})')
            if show_zones.value:
                state['layers'].append(m.generic_layer(name='geoJSON', args=[exclusion_zones(p), {
                    'style': {'color': '#a21caf', 'fillColor': '#a21caf', 'fillOpacity': 0.22,
                              'weight': 2, 'interactive': False}}]))
            safety_form.clear()
            safety_inputs.clear()
            subcategories = sorted(set(p.safety_distances) | {
                f['properties']['subcategory'] for f in p.features})
            with safety_form:
                for subcategory in subcategories:
                    safety_inputs[subcategory] = ui.number(
                        f'{subcategory} · Meter', value=p.safety_distances.get(subcategory, 0.0),
                        min=0, step=0.1, precision=2)
            selected.set_options({f['id']: f"{f['properties']['subcategory']} · {f['id'][:8]}" for f in p.features})
            render_polygon_list()
            render_vertices()
            status.set_text(f'{p.name} · {len(p.features)} Polygone · ' + ('freigegeben' if p.approved else 'Entwurf'))

        def display():
            p = project()
            target = workspace / f'{uuid4()}.png'
            bounds = preview(p, target)
            ensure_raster_summary(p)
            metadata = p.raster
            image_name.set_text(Path(p.raster_path).name)
            resolution = metadata.get('gsd_m')
            if resolution:
                image_resolution.set_text('Auflösung: ' + ' × '.join(
                    f'{value * 100:.2f}'.replace('.', ',') for value in resolution) + ' cm/Pixel')
            else:
                image_resolution.set_text('Auflösung in Metern: nicht verfügbar für dieses CRS')
            area = metadata.get('image_area_ha')
            image_area.set_text('Gültige Bildfläche: ' + (
                f'{area:.2f}'.replace('.', ',') + ' ha' if area is not None
                else 'nicht verfügbar für dieses CRS'))
            image_dimensions.set_text(f"Bildgröße: {metadata['width']} × {metadata['height']} Pixel")
            image_crs.set_text('CRS: ' + metadata.get('crs_label', metadata['crs']))
            image_overview.set_visibility(True)
            m.clear_layers()
            state['layers'] = []
            state['vertices'] = []
            selected.value = None
            # Preview below the tiles: Leaflet stacks tile layers above images in the same pane.
            m.image_overlay(url='/local-previews/' + target.name, bounds=bounds,
                            options={'pane': 'tilePane'})
            token, min_zoom, max_native_zoom = register(p.raster_path, p.raster['sha256'])
            m.tile_layer(url_template=f'/tiles/{token}/{{z}}/{{x}}/{{y}}.png',
                         options={'minZoom': min_zoom, 'maxNativeZoom': max_native_zoom,
                                  'maxZoom': MAX_ZOOM})
            fill_flight_form(p)
            state['max_native_zoom'] = max_native_zoom
            state['measure_layers'] = []
            m.run_map_method('fitBounds', bounds)
            refresh()
            render_measurements()
            if p.reference_points:
                point_select.value = next_open_point()

        def fill_flight_form(p):
            gsd = p.raster.get('gsd_m')
            defaults = {'map_id': p.name, 'gsd_cm': round(gsd[0] * 100, 2) if gsd else None}
            for name, element in flight_inputs.items():
                element.value = p.flight.get(name, defaults.get(name))

        def apply_flight():
            p = project()
            p.flight = validate_flight({name: element.value for name, element in flight_inputs.items()})
            ui.notify('Flugdaten übernommen. Zum Sichern das Projekt speichern.', type='positive')

        def export_flight():
            p = project()
            if not p.flight:
                raise ValueError('Bitte zuerst die Flugdaten übernehmen.')
            ui.download(flight_log_csv([p.flight]).encode(), f"{p.flight['map_id']}.flight_log.csv")

        def load_raster():
            p = open_project(path.value)
            state['project'] = p
            output.value = str(workspace / f'{p.name}.project.json')
            display()

        def load_project():
            p = Project.load(path.value)
            # A project from another computer: look for its GeoTIFF among the uploads.
            uploaded_raster = data_dir / Path(p.raster_path).name
            if not Path(p.raster_path).is_file() and uploaded_raster.is_file():
                p.raster_path = str(uploaded_raster)
            p.verify_raster()
            state['project'] = p
            output.value = str(Path(path.value).expanduser().resolve())
            display()

        def save():
            project().save(output.value)
            refresh_recent()
            ui.notify(f'Gespeichert: {Path(output.value).name}', type='positive')

        def choose(e):
            p = project()
            f = next((f for f in p.features if f['id'] == e.value), None)
            if f:
                props = f['properties']
                category.value, subtype.value = props['category'], props['subcategory']
                traversal.value, notes.value = props['traversability'], props.get('notes', '')
                coordinates.value = json.dumps(mapping(project_geometry(shape(f['geometry']), p.raster['crs'], 'EPSG:4326')))
            render_vertices()
        selected.on_value_change(lambda e: guard(lambda: choose(e)))

        def render_vertices():
            for marker in state['vertices']:
                if marker in m.layers:
                    m.remove_layer(marker)
            state['vertices'] = []
            if not edit_vertices.value or state['project'] is None:
                return
            p = project()
            feature = next((f for f in p.features if f['id'] == selected.value), None)
            if feature is None:
                return
            for part, ring, index, coordinate in vertex_positions(feature, p.raster['crs']):
                marker = m.marker(latlng=(coordinate[1], coordinate[0]), options={'draggable': True})
                state['vertices'].append(marker)
                payload = json.dumps({'id': feature['id'], 'part': part, 'ring': ring,
                                      'index': index, 'revision': p.revision})
                marker.run_method(':on', json.dumps('dragend'),
                                  f'e => {{const p=e.target.getLatLng(); '
                                  f'emitEvent({json.dumps(vertex_event)}, '
                                  f'{{...{payload}, lng:p.lng, lat:p.lat}});}}')

            for part, ring, index, coordinate in edge_midpoints(feature, p.raster['crs']):
                marker = m.generic_layer(name='circleMarker', args=[
                    [coordinate[1], coordinate[0]],
                    {'radius': 9, 'color': '#ffffff', 'weight': 2,
                     'fillColor': '#2563eb', 'fillOpacity': 1, 'bubblingMouseEvents': False}])
                state['vertices'].append(marker)
                marker.run_method('bindTooltip', '+', {'permanent': True, 'direction': 'center',
                                                       'className': 'farm-insert-label'})
                payload = json.dumps({'id': feature['id'], 'part': part, 'ring': ring,
                                      'index': index, 'revision': p.revision})
                marker.run_method(':on', json.dumps('click'),
                                  f'e => emitEvent({json.dumps(insert_event)}, {payload})')

        def vertex_inserted(e):
            try:
                p = project()
                data = e.args
                if data['revision'] != p.revision:
                    raise ValueError('Die Karte hat sich geändert. Bitte die Kante erneut auswählen.')
                insert_vertex(p, data['id'], data['part'], data['ring'], data['index'])
                refresh()
                feature = next(f for f in p.geojson()['features'] if f['id'] == data['id'])
                coordinates.value = json.dumps(feature['geometry'])
            finally:
                render_vertices()

        ui.on(insert_event, lambda e: guard(lambda: vertex_inserted(e)))

        def vertex_dragged(e):
            try:
                p = project()
                data = e.args
                if data['revision'] != p.revision:
                    raise ValueError('Die Karte hat sich geändert. Bitte den Stützpunkt erneut verschieben.')
                move_vertex(p, data['id'], data['part'], data['ring'], data['index'], data['lng'], data['lat'])
                refresh()
                feature = next(f for f in p.geojson()['features'] if f['id'] == data['id'])
                coordinates.value = json.dumps(feature['geometry'])
            finally:
                render_vertices()

        ui.on(vertex_event, lambda e: guard(lambda: vertex_dragged(e)))
        ui.on(selection_event, lambda e: measure_mode.value or selected.set_value(e.args))

        async def reference_uploaded(e):
            target = unique_path(workspace, e.file.name)
            await e.file.save(target)
            e.sender.reset()
            guard(lambda: load_references(target))

        def load_references(path):
            p = project()
            if not p.flight:
                raise ValueError('Bitte zuerst die Flugdaten übernehmen (farm, map_id).')
            rows = read_rows(path, REFERENCE_COLUMNS)
            parse_reference_points(rows, Path(path).name)  # validate the whole file
            farms = sorted({row['farm'] for _, row in rows})
            p.reference_points = [row for _, row in rows if row['farm'] == p.flight['farm']]
            if not p.reference_points:
                raise ValueError(f"Keine Punkte für Hof {p.flight['farm']} in {Path(path).name} "
                                 f"(enthalten: {', '.join(farms)}).")
            known = {row['point_id'] for row in p.reference_points}
            dropped = sorted(set(p.measurements) - known)
            for point_id in dropped:
                del p.measurements[point_id]
            render_measurements()  # fills the point options before one is selected
            point_select.value = next_open_point()
            ui.notify(f'{len(known)} Referenzpunkte für {p.flight["farm"]} geladen.'
                      + (f' Messungen ohne Referenz entfernt: {", ".join(dropped)}' if dropped else ''),
                      type='positive')

        def next_open_point(after=None):
            p = project()
            ids = [row['point_id'] for row in p.reference_points]
            start = ids.index(after) + 1 if after in ids else 0
            return next((i for i in ids[start:] + ids[:start] if i not in p.measurements), None)

        def map_clicked(e):
            if not measure_mode.value or state['project'] is None:
                return
            p = project()
            point_id = point_select.value
            if not point_id:
                raise ValueError('Bitte zuerst einen Kontrollpunkt wählen.')
            if e.args['zoom'] < state['max_native_zoom'] - 1:
                raise ValueError('Für eine genaue Messung weiter hineinzoomen (bis die Pixel sichtbar sind).')
            latlng = e.args['latlng']
            point = project_geometry(Point(latlng['lng'], latlng['lat']), 'EPSG:4326', p.raster['crs'])
            p.measurements[point_id] = {'x': point.x, 'y': point.y, 'zoom': e.args['zoom']}
            following = next_open_point(point_id)
            point_select.value = following
            render_measurements()
            ui.notify(f'{point_id} gemessen. ' + (f'Weiter mit {following}.' if following
                                                   else 'Alle Punkte gemessen.'), type='positive')
        m.on('map-click', lambda e: guard(lambda: map_clicked(e)))

        def delete_measurement():
            p = project()
            if point_select.value not in p.measurements:
                raise ValueError('Für diesen Punkt gibt es keine Messung.')
            del p.measurements[point_select.value]
            render_measurements()

        def export_measurements():
            p = project()
            if not p.measurements:
                raise ValueError('Noch keine Punkte gemessen.')
            ui.download(csv_text(project_measured_points(p)).encode(),
                        f"{p.flight['map_id']}.measured_points.csv")

        def render_measurements():
            for layer in state['measure_layers']:
                if layer in m.layers:
                    m.remove_layer(layer)
            state['measure_layers'] = []
            p = state['project']
            if p is None or not p.reference_points:
                return
            reference = {point_id: point for (_, point_id), point in project_reference(p).items()}
            errors = {row['point_id']: row for row in project_point_errors(p)}
            point_select.set_options({point_id: f"{point_id} · {point['role']} · {point['structure_type']}"
                                      f" · {'✓' if point_id in p.measurements else 'offen'}"
                                      for point_id, point in reference.items()})

            def marker(point, crs, style, label=None):
                position = project_geometry(Point(*point), crs, 'EPSG:4326')
                layer = m.generic_layer(name='circleMarker', args=[
                    [position.y, position.x], {'interactive': False, 'bubblingMouseEvents': True, **style}])
                if label:  # beside the circle, so the target itself stays visible
                    layer.run_method('bindTooltip', label, {'permanent': True, 'direction': 'right',
                                                            'offset': [style['radius'] + 4, 0]})
                state['measure_layers'].append(layer)

            if show_references.value:
                for point_id, point in reference.items():
                    marker((point['easting'], point['northing']), point['crs'],
                           {'radius': 16, 'color': '#06b6d4', 'weight': 2, 'fill': False}, point_id)
            for point in p.measurements.values():
                marker((point['x'], point['y']), p.raster['crs'],
                       {'radius': 3, 'color': '#ffffff', 'weight': 1, 'fillColor': '#f97316', 'fillOpacity': 1})

            def cm(value):
                return f'{value * 100:.1f}' if show_errors.value else '–'
            measure_table.rows = [{
                'point_id': point_id, 'role': point['role'], 'structure_type': point['structure_type'],
                'status': 'gemessen' if point_id in p.measurements else 'offen',
                **({'dx_cm': cm(errors[point_id]['dx_m']), 'dy_cm': cm(errors[point_id]['dy_m']),
                    'error_cm': cm(errors[point_id]['error_2d_m'])} if point_id in errors else {}),
            } for point_id, point in reference.items()]
            checks = [point_id for point_id, point in reference.items() if point['role'] == 'check']
            measured = [point_id for point_id in checks if point_id in p.measurements]
            text = (f"Hof {p.flight['farm']} · Karte {p.flight['map_id']} · "
                    f"Kontrollpunkte gemessen: {len(measured)}/{len(checks)}")
            summary = summarize(list(errors.values()))
            if summary and show_errors.value:
                s = summary[0]
                text += (f" · RMSE 2D {s['rmse_2d_m'] * 100:.1f} cm · P95 {s['p95_2d_m'] * 100:.1f} cm"
                         f" · ≤10 cm {s['pct_within_10cm']:.0f} % · Bias {s['mean_dx_m'] * 100:.1f}/"
                         f"{s['mean_dy_m'] * 100:.1f} cm (O/N)")
            measure_summary.set_text(text + ' · GCPs werden nicht ausgewertet.')
            reference_info.set_text(f'{len(reference)} Referenzpunkte geladen ({len(checks)} Kontrollpunkte).')
        refresh_recent()

        def drawn(e):
            p = project()
            points = e.args['layer']['_latlngs']
            while isinstance(points[0], list):
                points = points[0]
            geom = Polygon([(v['lng'], v['lat']) for v in points])
            feature = make_feature(project_geometry(geom, 'EPSG:4326', p.raster['crs']), category.value, subtype.value.strip())
            p.edit(p.features + [feature])
            refresh()
        m.on('draw:created', lambda e: guard(lambda: drawn(e)))

        def update():
            p = project()
            features = deepcopy(p.features)
            f = next(f for f in features if f['id'] == selected.value)
            geom = shape(json.loads(coordinates.value))
            if not geom.is_valid:
                raise ValueError('Ungültiges Polygon.')
            f['geometry'] = mapping(project_geometry(geom, 'EPSG:4326', p.raster['crs']))
            f['properties'].update(category=category.value, subcategory=subtype.value.strip(),
                                   traversability=traversal.value, notes=notes.value,
                                   review_status='manually_edited')
            p.edit(features)
            refresh()

        def delete():
            p = project()
            if not selected.value:
                raise ValueError('Polygon auswählen.')
            p.edit([f for f in p.features if f['id'] != selected.value])
            refresh()

        def apply_safety():
            distances = {key: float(element.value) for key, element in safety_inputs.items()}
            p = project()
            p.edit(safety_distances=distances)
            refresh()

        def export_zones():
            data = exclusion_zones(project())
            ui.download(json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2).encode(),
                        'farm-exclusion-zones.geojson')

        def history(direction):
            getattr(project(), direction)()
            refresh()

        def approve():
            project().approve()
            refresh()

        def export(final=False):
            data = project().geojson(final=final)
            ui.download(json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2).encode(), 'farm-map.geojson')

        with ui.row():
            ui.button('Änderungen übernehmen', on_click=lambda: guard(update))
            ui.button('Polygon löschen', on_click=lambda: guard(delete))
            ui.button('Undo', on_click=lambda: guard(lambda: history('undo')))
            ui.button('Redo', on_click=lambda: guard(lambda: history('redo')))
        with ui.row():
            ui.button('Projekt speichern', on_click=lambda: guard(save))
            ui.button('Entwurf als GeoJSON', on_click=lambda: guard(export))
            ui.button('Geprüfte Gesamtkarte freigeben', on_click=lambda: guard(approve))
            ui.button('Freigegebenes GeoJSON', on_click=lambda: guard(lambda: export(True)))
    # FARM_HOST=0.0.0.0 makes the app reachable from other machines on the network.
    ui.run(host=os.environ.get('FARM_HOST', '127.0.0.1'), port=int(os.environ.get('FARM_PORT', 8080)), title='Farm Mapping', reload=False)


if __name__ == '__main__':
    main()
