"""Local first-increment UI. All paths refer to the server's local filesystem."""
from copy import deepcopy
from functools import partial
import json
from pathlib import Path
from uuid import uuid4
from shapely.geometry import Polygon, shape, mapping
from nicegui import app, ui
from .core import Project, CATEGORIES, TRAVERSABILITY, make_feature, project_geometry
from .raster import open_project, preview, ensure_raster_summary
from .safety import exclusion_zones
from .editing import vertex_positions, move_vertex, edge_midpoints, insert_vertex


def main():
    workspace = Path('workspace').resolve()
    workspace.mkdir(exist_ok=True)
    app.add_static_files('/local-previews', str(workspace))

    @ui.page('/')
    def page():
        state = {'project': None, 'layers': [], 'vertices': []}
        vertex_event = 'farm-vertex-' + str(uuid4())
        selection_event = 'farm-selection-' + str(uuid4())
        insert_event = 'farm-insert-' + str(uuid4())
        ui.add_css('.farm-insert-label { background: transparent; border: none; box-shadow: none; color: white; font-weight: bold; font-size: 16px; }')
        ui.label('Farm Mapping · Kartenprüfung').classes('text-2xl')
        ui.label('Entwürfe prüfen. Neutraler GeoJSON-Export; Feldfreund-Schnittstelle noch offen.')
        path = ui.input('Lokaler GeoTIFF- oder Projekt-JSON-Pfad').classes('w-full')
        ui.label('GeoTIFF öffnen: .tif/.tiff · Projekt öffnen: zuvor gespeicherte .json-Datei.').classes('text-sm')
        data_files = {str(file.resolve()): file.name for file in sorted(Path('data').glob('*'))
                      if file.is_file() and file.suffix.lower() in ('.tif', '.tiff')}
        ui.select(data_files, label='TIFF-Dateien aus data auswählen',
                  on_change=lambda e: path.set_value(e.value or '')).classes('w-full')
        status = ui.label('Kein Projekt geladen')
        with ui.row():
            ui.button('GeoTIFF öffnen', on_click=lambda: guard(load_raster))
            ui.button('Projekt öffnen', on_click=lambda: guard(load_project))
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
        m = ui.leaflet(draw_control={
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
            m.image_overlay(url='/local-previews/' + target.name, bounds=bounds)
            m.run_map_method('fitBounds', bounds)
            refresh()

        def load_raster():
            p = open_project(path.value)
            state['project'] = p
            display()

        def load_project():
            p = Project.load(path.value)
            p.verify_raster()
            state['project'] = p
            display()

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
        ui.on(selection_event, lambda e: selected.set_value(e.args))

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
            ui.button('Projekt speichern', on_click=lambda: guard(lambda: project().save(output.value)))
            ui.button('Entwurf als GeoJSON', on_click=lambda: guard(export))
            ui.button('Geprüfte Gesamtkarte freigeben', on_click=lambda: guard(approve))
            ui.button('Freigegebenes GeoJSON', on_click=lambda: guard(lambda: export(True)))
    ui.run(host='127.0.0.1', port=8080, title='Farm Mapping', reload=False)


if __name__ == '__main__':
    main()
