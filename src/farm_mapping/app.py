"""Local first-increment UI. All paths refer to the server's local filesystem."""
from copy import deepcopy
from functools import partial
import json
from pathlib import Path
from uuid import uuid4
from shapely.geometry import Polygon, shape, mapping
from nicegui import app, ui, run
from .core import Project, CATEGORIES, TRAVERSABILITY, make_feature, project_geometry
from .raster import open_project, preview, ensure_raster_summary
from .safety import exclusion_zones
from .editing import vertex_positions, move_vertex, edge_midpoints, insert_vertex
from .detection import ColorBaseline, DetectionSettings, accept_proposals


def main():
    workspace = Path('workspace').resolve()
    workspace.mkdir(exist_ok=True)
    app.add_static_files('/local-previews', str(workspace))

    @ui.page('/')
    def page():
        state = {'project': None, 'layers': [], 'vertices': [],
                 'proposals': None, 'proposal_layer': None, 'review_layer': None, 'group_layers': [], 'proposal_revision': None}
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
        with ui.card().classes('w-full'):
            ui.label('Automatische Polygonvorschläge · experimentell').classes('text-lg font-medium')
            ui.label('RGB- und Strukturheuristik, noch kein KI-Modell. Alle Zuordnungen prüfen; '
                     'es wird keine Befahrbarkeit bestätigt. Vorschau: türkis gestrichelt.')
            with ui.row():
                detection_size = ui.select([800, 1200, 1600, 2048], value=1600,
                                           label='Längste Analyseseite (Pixel)')
                detection_area = ui.number('Mindestfläche (m²)', value=4.0, min=0.1, step=1)
                detection_gap = ui.number('Fragmente verbinden (m)', value=1.0, min=0, max=3, step=0.1)
                detection_context = ui.number('Arbeitsflächen zusammenfassen (m; 0 = aus)', value=3.0, min=0, max=5, step=0.5)
                detection_smoothing = ui.number('Flächenränder glätten (Radius in m; 0 = aus)', value=0.5, min=0, max=2, step=0.1)
            ui.label('Nach Änderungen „Ganze Karte analysieren“ starten. Bereits übernommene Polygone bleiben unverändert.').classes('text-sm text-grey-7')
            detection_shadows = ui.checkbox('Experimentell: mögliche Schatten in Arbeitsflächen einbeziehen', value=False)
            detection_interiors = ui.checkbox('Helle Innenbereiche räumlich prüfen und zusammenfassen', value=True)
            detection_rows = ui.checkbox('Regelmäßige Pflanzstreifen anhand Richtung und Abstand erkennen', value=True)
            detection_groups = ui.checkbox('Arbeitsflächen nach Strukturgruppen getrennt halten', value=True)
            ui.label('Strukturgruppen: Grün = ohne sicheren Reihenbeleg, Braun = Obstfläche; weitere Farben = getrennte Reihengruppen. Alle bleiben Arbeitsflächen.').classes('text-sm text-grey-7')
            ui.label('Bei getrennten Strukturgruppen zeigen die Farben die Gruppen. Ohne Gruppentrennung markiert Orange neu einbezogene Bereiche.').classes('text-sm text-grey-7')
            ui.label('Schattenoption: Dunkle Stellen können auch Gehölze sein. Ergebnisse besonders prüfen.').classes('text-sm text-grey-7')
            detection_orchards = ui.checkbox('Regelmäßige Baumreihen als zusammenhängende Obstfläche erkennen', value=True)
            with ui.row().classes('items-center'):
                analyze_button = ui.button('Ganze Karte analysieren')
                accept_button = ui.button('Vorschläge übernehmen', on_click=lambda: guard(accept_detection))
                discard_button = ui.button('Vorschau verwerfen', on_click=lambda: guard(clear_detection))
                detection_spinner = ui.spinner()
            detection_spinner.set_visibility(False)
            accept_button.disable()
            discard_button.disable()
            detection_status = ui.label('Noch keine Analyse gestartet.')
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
        review_hint = ui.label().classes('text-amber-800')
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
                            if props.get('review_flag'):
                                text += ' · Prüfung erforderlich'
                            ui.button(text, color=color,
                                      on_click=partial(selected.set_value, feature['id'])).props(
                                          'flat no-caps align=left').classes('w-full').style(
                                              f'border-left: 4px solid {color}')

        def refresh():
            p = project()
            if state['proposals'] is not None and state['proposal_revision'] != p.revision:
                clear_detection()
                detection_status.set_text('Karte geändert: vorherige Analysevorschau verworfen.')
            for layer in state['layers']:
                m.remove_layer(layer)
            state['layers'] = []
            colors = dict(work_area='green', navigable_area='orange', obstacle='red')
            for f in p.geojson()['features']:
                layer = m.generic_layer(name='geoJSON', args=[f, {
                    'style': {'color': (f['properties'].get('structure_color', 'green') if f['properties']['category'] == 'work_area' else colors[f['properties']['category']]), 'dashArray': '5 5'}}])
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
            selected.set_options({f['id']: f"{f['properties']['subcategory']} · {f['properties'].get('structure_group', '')} · {f['id'][:8]}" for f in p.features})
            render_polygon_list()
            render_vertices()
            status.set_text(f'{p.name} · {len(p.features)} Polygone · ' + ('freigegeben' if p.approved else 'Entwurf'))

        def clear_detection():
            for layer in state['group_layers']:
                if layer in m.layers:
                    m.remove_layer(layer)
            state['group_layers'] = []
            for key in ('proposal_layer', 'review_layer'):
                layer = state[key]
                if layer is not None and layer in m.layers:
                    m.remove_layer(layer)
            state.update(proposals=None, proposal_layer=None, review_layer=None, proposal_revision=None)
            accept_button.disable()
            discard_button.disable()
            detection_status.set_text('Keine ausstehenden Vorschläge.')

        async def analyze():
            analyze_button.disable()
            detection_spinner.set_visibility(True)
            try:
                p = project()
                revision = p.revision
                settings = DetectionSettings(max_dimension=int(detection_size.value),
                                             minimum_area_m2=float(detection_area.value),
                                             grouping_distance_m=float(detection_gap.value),
                                             field_context_radius_m=float(detection_context.value),
                                             outline_smoothing_m=float(detection_smoothing.value),
                                             compensate_shadows=detection_shadows.value,
                                             reconsider_bright_interiors=detection_interiors.value,
                                             detect_rows=detection_rows.value,
                                             separate_structure_groups=detection_groups.value,
                                             detect_orchards=detection_orchards.value)
                settings.validate()
                clear_detection()
                detection_status.set_text('Analyse läuft: Raster lesen, RGB-Regeln anwenden, Polygone erzeugen …')
                result = await run.cpu_bound(ColorBaseline().detect, p.raster_path, p.raster['sha256'], settings)
                if state['project'] is not p or p.revision != revision:
                    raise ValueError('Projekt während der Analyse geändert. Bitte erneut analysieren.')
                counts = {key: sum(f['properties']['category'] == key for f in result.features)
                          for key in CATEGORIES}
                detection_status.set_text(
                    f"{len(result.features)} Vorschläge: {counts['work_area']} Arbeitsflächen, "
                    f"{counts['navigable_area']} Wegkandidaten, {counts['obstacle']} Hinderniskandidaten. "
                    f"Davon {result.metadata['orchard_candidate_count']} vermutete Obstflächen. "
                    f"{result.metadata.get('reconsidered_bright_area_m2', 0):.1f} m² helle Innenbereiche neu zugeordnet. "
                    f"{result.metadata.get('row_region_count', 0)} Bereiche mit Pflanzstreifen; "
                    f"{result.metadata.get('row_added_area_m2', 0):.1f} m² dadurch ergänzt. "
                    f"{result.metadata.get('structure_group_count', 0)} getrennte Strukturgruppen. "
                    f"{result.metadata['omitted_by_limit']} weitere wegen Polygonlimit ausgelassen. "
                    'Noch nicht im Projekt gespeichert. Bestehende Polygone haben beim Übernehmen Vorrang.')
                if result.features:
                    state.update(proposals=result, proposal_revision=revision)
                    displayed = []
                    for feature in result.features:
                        displayed.append({**feature, 'geometry': mapping(project_geometry(
                            shape(feature['geometry']), p.raster['crs'], 'EPSG:4326'))})
                    state['proposal_layer'] = m.generic_layer(name='geoJSON', args=[
                        {'type': 'FeatureCollection', 'features': [f for f in displayed if not f['properties'].get('structure_color')]},
                        {'style': {'color': '#0891b2', 'fillOpacity': 0.12, 'dashArray': '6 6',
                                   'weight': 2, 'interactive': False}}])
                    for color in sorted({f['properties']['structure_color'] for f in displayed
                                         if 'structure_color' in f['properties']}):
                        group_features = [f for f in displayed if f['properties'].get('structure_color') == color]
                        state['group_layers'].append(m.generic_layer(name='geoJSON', args=[
                            {'type': 'FeatureCollection', 'features': group_features},
                            {'style': {'color': color, 'fillColor': color, 'fillOpacity': 0.22,
                                       'weight': 2, 'interactive': False}}]))
                    if result.review_overlays and not settings.separate_structure_groups:
                        overlays = [{**f, 'geometry': mapping(project_geometry(
                            shape(f['geometry']), p.raster['crs'], 'EPSG:4326'))}
                            for f in result.review_overlays]
                        state['review_layer'] = m.generic_layer(name='geoJSON', args=[
                            {'type': 'FeatureCollection', 'features': overlays},
                            {'style': {'color': '#f97316', 'fillColor': '#f97316',
                                       'fillOpacity': 0.5, 'weight': 2, 'interactive': False}}])
                    accept_button.enable()
                    discard_button.enable()
            except Exception as exc:
                detection_status.set_text(f'Analyse fehlgeschlagen: {exc}')
                ui.notify(str(exc), type='negative')
            finally:
                analyze_button.enable()
                detection_spinner.set_visibility(False)

        analyze_button.on('click', analyze)

        def accept_detection():
            p = project()
            result = state['proposals']
            if result is None or p.revision != state['proposal_revision']:
                raise ValueError('Keine aktuelle Vorschau vorhanden. Bitte erneut analysieren.')
            count = accept_proposals(p, result)
            clear_detection()
            refresh()
            detection_status.set_text(f'{count} Vorschläge ergänzt. Bitte prüfen und Projekt speichern. '
                                      'Mit Undo lässt sich die Übernahme zurücknehmen.')

        def display():
            p = project()
            clear_detection()
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
                review_hint.set_text(props.get('review_reason', '') if props.get('review_flag') else '')
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
