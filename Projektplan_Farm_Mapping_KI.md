# Projektplan und Implementierungsauftrag: Offline Farm Mapping für Zauberzeug

**Stand:** 23. Oktober 2026  
**Zweck:** Technische Projektspezifikation und ausführlicher Arbeitsauftrag für eine Coding-KI  
**Projekt:** Automatische Farmstruktur-Erkennung aus Drohnen-Orthomosaiken und Export robotertauglicher Navigationskarten  
**Auftraggeber/Anwendungskontext:** Hochschulprojekt Digital Farming mit Zauberzeug / Feldfreund

---

## 1. Auftrag an die umsetzende KI

Entwickle eine modular aufgebaute, lokal und offline nutzbare Open-Source-Python-Anwendung, die fertig zusammengesetzte, georeferenzierte Drohnen-Orthomosaike einliest, landwirtschaftliche Strukturen automatisch erkennt und klassifiziert, die Ergebnisse als georeferenzierte Polygone visualisiert und manuell bearbeiten lässt und nach einer bewussten Nutzerfreigabe eine robotertaugliche Navigationskarte exportiert.

Die eigentliche Routenplanung und Robotersteuerung sind **nicht** Teil dieser Anwendung. Sie erfolgen im System des Feldfreunds. Die Anwendung soll Daten dafür vorbereiten, ohne zu behaupten, dass aus einem Luftbild allein die tatsächliche Befahrbarkeit oder Betriebssicherheit nachgewiesen werden kann.

**Arbeitsmodus der Coding-KI:**
1. Lies diese Spezifikation vollständig und behandle die ausdrücklich festgelegten Anforderungen als verbindlich.
2. Unterscheide strikt zwischen **MUSS**, **SOLL**, **KANN** und **OFFEN**.
3. Beginne mit einer überprüfbaren, lauffähigen Architektur und einem kleinen End-to-End-Durchstich; implementiere dann iterativ.
4. Treffe keine stillschweigenden Entscheidungen zu offenen Punkten, insbesondere zu Modellwahl, Hardware, Ziel-GeoJSON-Schema des Roboters oder erforderlicher Positionsgenauigkeit. Wähle für einen Prototypen reversible Defaults und dokumentiere sie.
5. Verwende möglichst gut gepflegte, kompatible Open-Source-Bibliotheken und dokumentiere Lizenz, Modellgewichte, Download- und Offline-Setup.
6. Baue reproduzierbare Tests und nachvollziehbare Qualitätsmessungen ein.
7. Erkläre vor der Ausführung vorgeschlagener Shell-, Git- und Terminalbefehle, was jeder Befehl tut.
8. Vermeide unnötige Komplexität. Implementiere zuerst einen funktionierenden Kern und keine umfangreiche Infrastruktur ohne Bedarf.

---

## 2. Projektziel und fachlicher Kontext

Die Software soll eine Farm aus der Vogelperspektive analysieren. Eingabe sind **bereits fertig gestitchte Orthomosaike**, idealerweise georeferenzierte GeoTIFFs. Es werden sowohl Aufnahmen einer Drohne mit RTK-GNSS als auch einer Drohne mit herkömmlichem GPS verarbeitet. Beide werden durch dieselbe Verarbeitungspipeline geführt. Die Bilddaten sollen in einer lokalen Weboberfläche dargestellt werden.

Die automatische Analyse soll drei Hauptkategorien erzeugen:

| Hauptkategorie | Bedeutung | Mögliche Unterkategorien |
|---|---|---|
| `work_area` | Arbeitsflächen des Roboters | Feld, Beet |
| `navigable_area` | Potenziell befahrbare Wege und Flächen | befestigte Straße, Feldweg, Fahrspur |
| `obstacle` | Hindernisse oder grundsätzlich zu prüfende Sperrbereiche | Gebäude, Baum, Graben, Zaun, Agri-PV, Wasser |

Zusätzlich sind **Ladestationen** als mögliche wichtige Objekte zu berücksichtigen. Ihre genaue Modellierung (Punkt/Polygon, Zielort, POI) ist noch offen. Sie dürfen nicht pauschal als Hindernis behandelt werden. Neue Unterkategorien sollen später ergänzt werden können, ohne die Architektur neu zu schreiben.

Die Software erkennt Strukturen **automatisch** und präsentiert die Ergebnisse zur **manuellen Prüfung**. Nach Korrekturen und expliziter Freigabe kann eine finale Navigationskarte exportiert werden. Nicht bestätigte oder unsichere Bereiche dürfen nicht stillschweigend als sicher befahrbar gelten.

---

## 3. Verbindliche Anforderungen aus dem Projektinterview

### R1 – Automatische Erkennung mit manueller Kontrolle
- MUSS: Die gesamte Karte kann automatisiert analysiert und klassifiziert werden.
- MUSS: Ergebnisse werden als bearbeitbare Polygone angezeigt.
- MUSS: Menschliche Kontrolle und Korrektur sind Bestandteil des Workflows.
- MUSS: Kein Zwang, jedes einzelne Polygon einzeln zu bestätigen; stattdessen Freigabe der geprüften Gesamtkarte.

### R2 – Erkennungsklassen
- MUSS: Drei Hauptkategorien `work_area`, `navigable_area`, `obstacle`.
- SOLL: Unterkategorien Feld, Beet, Straße, Feldweg/Fahrspur, Gebäude, Baum, Graben, Zaun, Agri-PV, Wasser.
- OFFEN: Ladestation als POI/Punkt/Polygon und eventuelle weitere Klassen.
- MUSS: Erweiterbare Klassendefinitionen und klare Trennung von **sichtbarer Objektklasse** und **Befahrbarkeitsstatus**.

### R3 – Hardware
- OFFEN: Zielhardware und Mindestanforderungen.
- SOLL: Verarbeitung möglichst hardwareunabhängig; CPU- und GPU-Unterstützung prüfen, aber keine unbelegte CPU-only-Leistung versprechen.
- MUSS: Keine zwingende Cloud-Verarbeitung.

### R4 – Polygonbearbeitung
- MUSS: Polygon auswählen und Klasse ändern.
- MUSS: Polygonkontur durch Verschieben von Stützpunkten bearbeiten.
- MUSS: Fehlende Polygone manuell zeichnen.
- MUSS: Falsch erkannte Polygone löschen.
- MUSS: Eigenschaften ändern, z. B. Befahrbarkeit, Name/Bemerkung falls vorhanden.
- MUSS: Undo/Redo für Editieraktionen.
- NICHT ZWINGEND: Polygone verschmelzen oder teilen; zunächst nicht Teil des MVP.

### R5 – Eingabeformate
- OFFEN: Langfristige Formatauswahl.
- MUSS für ersten funktionsfähigen Durchstich: georeferenziertes GeoTIFF.
- KANN später: zusätzliche georeferenzierte Rasterformate.
- Nicht einfach gewöhnliche PNG/JPG als georeferenziert behandeln; ohne passende Georeferenzierung ist ein verlässlicher GeoJSON-Koordinatenexport nicht möglich.

### R6 – Benutzeroberfläche
- MUSS: Lokale Weboberfläche mit **NiceGUI + Leaflet** oder sauber eingebundener Leaflet-Karte.
- MUSS: Offline-Funktion einschließlich lokaler JS-/CSS-Assets und Kartenhintergründe; keine zwingende Verbindung zu Online-Kachelservern.
- MUSS: Browseroberfläche von Python-Verarbeitungsbibliothek trennen.

### R7 – Verarbeitungsbereich
- MUSS: Nutzer kann komplette Karte oder einen ausgewählten rechteckigen Teilbereich analysieren.
- MUSS: Ergebnisse der Teilbereichsanalyse in das bestehende Projekt übernehmen können, ohne andere Ergebnisse unkontrolliert zu löschen.
- SOLL: Fortschritt und Fehlermeldungen sichtbar machen.

### R8 – Erkennungsqualität
- MUSS: Möglichst zuverlässige automatische Erkennung, manuelle Korrektur bleibt vorgesehen.
- OFFEN: Konkrete geforderte Positionsgenauigkeit; hängt vom Feldfreund ab.
- MUSS: Keine erfundenen Genauigkeitsgarantien.

### R9 – Speichern und Export
- MUSS: GeoJSON mit georeferenzierten Polygonen.
- MUSS: Vollständiges Projekt speichern und später wieder öffnen, inklusive aller manuellen Korrekturen.
- MUSS: Objektattribute speichern: Kategorie, Befahrbarkeit, Prüfstatus, eindeutige ID, Unterkategorie.
- MUSS: Geografische Koordinaten und CRS korrekt erhalten und dokumentieren.
- MUSS: Kartenansicht samt Polygonen als PNG/JPG exportieren.
- KANN: Weitere GIS-Formate, etwa GeoPackage; nicht verpflichtend.
- KANN: Export eines veränderten GeoTIFFs; nicht angefordert.

### R10 – Erkennungsansatz
- MUSS: Hybridansatz aus vortrainierten Open-Source-KI-Modellen und klassischer Bildverarbeitung.
- MUSS: Zunächst **kein eigenes Modelltraining** voraussetzen.
- SOLL: Methoden modular und austauschbar implementieren.
- OFFEN: Konkrete Modelle und Pipeline erst nach empirischen Tests auswählen.
- WICHTIG: SAM/SamGeo kann Polygonvorschläge erzeugen, ist aber nicht automatisch eine zuverlässige semantische Farmklassen-Klassifikation.

### R11 – Plattform und Bereitstellung
- MUSS: Linux und macOS als Zielplattformen berücksichtigen.
- MUSS: Zunächst als Python-Projekt installierbar und ausführbar.
- KANN: Docker, Standalone-App oder Windows später ergänzen.
- SOLL: Hardware-/Modellkompatibilität auf beiden Plattformen dokumentieren; insbesondere GPU-Beschleunigung nicht als überall identisch voraussetzen.

### R12 – Robotertaugliche Navigationskarte
- MUSS: Ausgabekarte mit Arbeitsflächen, potenziell befahrbaren Bereichen, Hindernissen und Sperrzonen.
- MUSS: Routenplanung bleibt beim Feldfreund.
- OFFEN: Verbindliches Datenmodell und Schnittstelle zu Zauberzeug.
- WICHTIG: Aus Luftbildern abgeleitete Befahrbarkeit ist eine Hypothese, keine Sicherheitsfreigabe.

### R13 – Flächengröße und Auflösung (korrigierte Festlegung)
- MUSS: Flächen bis **maximal 5 ha** für den vorgesehenen Anwendungsfall.
- MUSS: Erwartete GSD **größer als 5 cm/Pixel und kleiner als 10 cm/Pixel**.
- SOLL: Kachelverarbeitung ermöglichen, wenn Bild- oder Modellgröße es erfordert.
- HINWEIS: Eine zuvor diskutierte 15-ha-Farm ist ausdrücklich **nicht** das Ziel für diesen Anwendungsfall.
- ORIENTIERUNG: 5 ha entsprechen bei 5–10 cm/Pixel etwa 5–20 Millionen Pixeln.

### R14 – Unsichere Erkennungen
- MUSS: Unsichere Objekte sichtbar markieren und zur manuellen Kontrolle anbieten.
- NICHT FESTGELEGT: Eigene `unknown`-Klasse ist nicht zwingend.
- MUSS: Falls ein Modell keine kalibrierte Confidence liefert, Unsicherheit nicht als scheinpräzisen Prozentwert darstellen. Ggf. Heuristiken/Review-Flags getrennt ausweisen.

### R15 – Review und Freigabe
- MUSS: Ergebnisse zunächst als Entwurf behandeln.
- MUSS: Manuelle Kontrolle und ausdrückliche Freigabe vor finalem Roboternavigations-Export.
- MUSS: Entwurfsspeicherung auch ohne Freigabe ermöglichen.
- SOLL: Bearbeitungen und Freigabestatus nachvollziehbar speichern.

### R16 – Polygonattribute
Pflichtattribute:
- `id`: eindeutige stabile Objekt-ID.
- `category`: `work_area` / `navigable_area` / `obstacle`.
- `subcategory`: z. B. `field`, `bed`, `road`, `path`, `building`, `tree`, `ditch`, `fence`, `agripv`, `water`.
- `traversability`: `traversable` / `non_traversable` / `unknown`.
- `review_status`: z. B. `auto_detected` / `manually_edited` / `approved`.

Optional erweiterbar: `name`, `notes`, `source_method`, `review_flag`, `confidence` (nur wenn sinnvoll), `created_at`, `updated_at`.

### R17 – Klassenspezifische Sicherheitsabstände
- MUSS: Sicherheitsabstände in zentralen Einstellungen **je Objekt-Unterkategorie** konfigurierbar.
- MUSS: Sperrzonen geometrisch aus Originalpolygonen und Sicherheitsabständen erzeugen.
- MUSS: Originalpolygone **unverändert erhalten**.
- MUSS: Änderung eines Abstands löst Neuberechnung der Sperrzonen aus, ohne erneute KI-Inferenz.
- BEISPIELWERTE (keine universellen Sicherheitsgarantien): Wasser 1,0 m; Baum 0,0 m zusätzlicher Puffer.
- WICHTIG: Baumkronen und tatsächlicher Stamm/Fußabdruck können auseinanderfallen. `0 m` bedeutet nicht, dass Baumstämme befahrbar sind.
- MUSS: Bufferberechnung in einem geeigneten **metrischen projizierten CRS**, nicht direkt in Längen-/Breitengraden.

### R18 – Quantitative Evaluation und Drohnenvergleich
- MUSS: Manuell erstellte Referenzpolygone zur quantitativen Bewertung unterstützen.
- MUSS: IoU sowie geeignete Precision-/Recall-Kennzahlen pro Kategorie und insgesamt berechnen, sofern Referenzdaten vorliegen.
- MUSS: Orthomosaike sowohl aus RTK- als auch aus normalem GPS-Drohnenworkflow verarbeiten.
- SOLL: Vergleich der Positionsgenauigkeit anhand unabhängiger Referenzaufnahmen methodisch ermöglichen; Umsetzung kann separat erfolgen.
- OFFEN: Genaues Messverfahren und Messgenauigkeit der Referenzpunkte.
- WICHTIG: Pixelbasierte Erkennungsqualität und absolute geografische Positionsgenauigkeit getrennt berichten.

### R19 – Integration von Referenzmessungen
- OFFEN: Ob Import und Positionsfehlerauswertung in die Webanwendung integriert oder extern durchgeführt werden.
- MUSS: Architektur darf externe Auswertung nicht behindern; CRS, Geometrien und Metadaten sauber exportieren.

### R20 – Image Stitching
- MUSS: **Nur fertige Orthomosaike verarbeiten.**
- AUSSERHALB DES SCOPES: Stitching einzelner Drohnenbilder und Photogrammetrie innerhalb dieser Anwendung.
- RTK/GPS bezieht sich auf Herkunft und Genauigkeit der Orthomosaike, nicht auf zwei verschiedene Pflicht-Importer.

### R21 – Modellauswahl
- Nicht entschieden; die entsprechende Interviewfrage wurde wegen Überschneidung mit R10 übersprungen.
- OFFEN: Expertenmodus, manuelle Modellwahl und Vergleichsansicht.

### R22 – Umfang des ersten Prototyps
- MUSS: Automatische Erkennung, manuelle Polygonbearbeitung, Projektspeicherung.
- MUSS: Einstellbare Sicherheitsabstände und passender Kartenexport.
- MUSS: Die weiteren vereinbarten Kernfunktionen schrittweise ergänzen, insbesondere Review/Freigabe, Teilbereichsanalyse und georeferenzierte Ausgaben.
- NICHT ERFORDERLICH im ersten Schritt: umfangreiches Modell-Benchmarking-UI, eigenes Training, Stitching.

### R23 – Bibliotheksarchitektur
- MUSS: Eigenständige Python-Bibliothek, unabhängig von NiceGUI nutzbar.
- MUSS: Separate lokale NiceGUI-/Leaflet-Weboberfläche.
- KANN: CLI später ergänzen; aktuell nicht verbindlich.

### R24 – Konkrete Erkennungspipeline
- OFFEN: Die zuletzt gestellte Frage nach Segmentierung-then-Klassifikation, direkter semantischer Segmentierung oder kategoriespezifischen Pipelines wurde **nicht beantwortet**.
- Daher **keine** dieser Varianten als verbindlich festschreiben. Teste geeignete Kandidaten mit echten Orthomosaiken und Referenzdaten.

---

## 4. Empfohlene technische Architektur (Vorschlag, nicht vollständig beschlossen)

### 4.1 Komponenten

1. **Raster-I/O und Georeferenzierung:** GeoTIFF öffnen, Metadaten prüfen, CRS und affine Transformation auslesen, Übersichtskacheln für die Webkarte bereitstellen. Kandidaten: `rasterio`, `pyproj`.
2. **Inference/Detection:** austauschbare Detektor-/Segmentierungs-Backends, kachelbasierte Verarbeitung, geometrisches Zusammenführen überlappender Kacheln. Kandidaten: `samgeo`/SAM-Varianten, geeignete vortrainierte semantische Modelle, OpenCV. Die konkrete Auswahl ist experimentell zu validieren.
3. **Postprocessing:** Rastermasken zu Polygonen vektorisieren, Topologie reparieren, Kleinstartefakte filtern, Kategorien und Unterkategorien zuweisen, Überlappungen behandeln.
4. **Feature-/Projektmodell:** stabile Objekt-IDs, Attribute, Review-Status, Geometrien, Änderungsverlauf, Projekt-Metadaten und Sicherheitseinstellungen.
5. **Safety-Zone-Engine:** klassenspezifische Puffer im metrischen CRS berechnen, abgeleitete Sperrzonen separat von Originalgeometrien halten.
6. **Export:** GeoJSON, roboterbezogenes Navigationsschema (nach Abstimmung), PNG/JPG der Kartenansicht.
7. **Evaluation:** Referenzpolygone laden und IoU/Precision/Recall berechnen; optional separates Modul für GNSS-Positionsvergleiche.
8. **Web UI:** NiceGUI mit Leaflet, Bildnavigation, Auswahl, Zeichnen, Vertex-Editing, Attributbearbeitung, Undo/Redo, Review/Freigabe, Einstellungen und Export.

### 4.2 Wichtige Entwurfsprinzipien

- **Core-first:** Die Python-Bibliothek darf keine NiceGUI-Imports benötigen.
- **Lokaler Betrieb:** Keine Cloud-API für die Laufzeit nötig. Alle Modellgewichte und Frontend-Assets müssen vorab lokal verfügbar sein. Für das initiale Setup darf ein dokumentierter Download erforderlich sein.
- **Reproduzierbarkeit:** Modellversion, Parameter, Eingabedatei-Hash, CRS, GSD und Softwareversion protokollieren.
- **Datenintegrität:** Änderungen atomar speichern; automatische Backups oder Recovery bei unerwartetem Abbruch prüfen.
- **Geometrische Korrektheit:** CRS-Transformationen explizit und testbar; Polygongeometrien validieren; abgeleitete Sicherheitszonen separat speichern.
- **Keine Überversprechen:** Unklare Objektklassifikation, Baumkronen, verdeckte Hindernisse und nicht sichtbare Geländegegebenheiten als Grenzen dokumentieren.
- **Lizenzprüfung:** Quellcode- und Modellgewicht-Lizenzen gesondert prüfen, bevor sie im Repository oder Produkt verteilt werden.

### 4.3 Vorgeschlagene Repository-Struktur

```text
farm-mapping/
├── pyproject.toml
├── README.md
├── LICENSE
├── .gitignore
├── configs/
│   ├── default.yaml
│   └── safety_distances.yaml
├── src/farm_mapping/
│   ├── __init__.py
│   ├── models.py                 # Datenmodelle und Enums
│   ├── raster/
│   │   ├── io.py                 # GeoTIFF, CRS, GSD
│   │   └── tiling.py             # Bildausschnitte
│   ├── detection/
│   │   ├── base.py               # Austauschbare Backend-Schnittstelle
│   │   ├── opencv_baseline.py
│   │   └── postprocess.py
│   ├── geometry/
│   │   ├── polygons.py
│   │   └── safety_buffers.py
│   ├── project/
│   │   ├── storage.py
│   │   └── history.py
│   ├── export/
│   │   ├── geojson.py
│   │   └── navigation.py
│   └── evaluation/
│       └── segmentation_metrics.py
├── app/
│   ├── main.py                  # NiceGUI-Einstieg
│   ├── map_view.py              # Leaflet-Einbindung
│   ├── editing.py
│   └── settings.py
├── tests/
│   ├── test_crs.py
│   ├── test_buffers.py
│   ├── test_project_roundtrip.py
│   ├── test_geojson_export.py
│   └── test_metrics.py
├── examples/
│   └── synthetic_demo.py
└── docs/
    ├── architecture.md
    ├── installation.md
    ├── data_format.md
    ├── evaluation.md
    └── limitations.md
```

Die Struktur ist ein Vorschlag und kann mit nachvollziehbarer Begründung angepasst werden.

---

## 5. Datenmodell und Koordinatensysteme

### 5.1 Projekt

Ein Projekt enthält mindestens:
- Referenz auf die Original-Orthomosaikdatei (plus optional Prüfsumme, um falsche Bildzuordnung zu erkennen).
- Raster-Metadaten: CRS, Bounding Box, GSD, Breite/Höhe, NoData, Pixeltransform.
- Georeferenzierte Originalpolygone mit Attributen.
- Sicherheitsregeln je Unterkategorie.
- Abgeleitete Sperrzonen.
- Projekt- und Freigabestatus.
- Änderungs- und Undo/Redo-Daten soweit technisch nötig.
- Verarbeitungsmetadaten (Modell-/Parameter-Versionen).

**Empfohlene Speicherform:** versioniertes Projektverzeichnis mit `project.json` oder einer lokalen SQLite-/GeoPackage-Datenbank für bearbeitete Geometrien. Das GeoTIFF kann referenziert statt dupliziert werden; fehlende Pfade beim Wiederöffnen müssen behandelt werden. Format vor Implementierung dokumentieren.

### 5.2 Feature-Beispiel (konzeptionell)

```json
{
  "type": "Feature",
  "id": "feature-001",
  "properties": {
    "category": "obstacle",
    "subcategory": "water",
    "traversability": "non_traversable",
    "review_status": "approved",
    "review_flag": false
  },
  "geometry": {
    "type": "Polygon",
    "coordinates": [[[11.0, 48.0], [11.001, 48.0], [11.001, 48.001], [11.0, 48.0]]]
  }
}
```

**Wichtig:** Dieses Beispiel illustriert die Struktur, nicht reale Geometrien. Für standardkonformes GeoJSON nach RFC 7946 sind die Koordinaten in WGS84-Länge/Breite auszugeben. Das originale metrische Projekt-CRS muss als Metadatum separat erhalten bleiben; eine alternative roboterspezifische Projektion ist erst nach Abstimmung mit Zauberzeug festzulegen. Die Software darf CRS nicht stillschweigend verwechseln.

### 5.3 Geometrie und Topologie

- Polygone müssen gültig sein (keine Selbstüberschneidungen, definierte Innenringe).
- Sicherheitszonen müssen bei Bedarf mit Nachbarflächen verschnitten werden; überlappende Sperrzonen dürfen nicht als befahrbar interpretiert werden.
- Bei widersprüchlichen Klassen gilt für die Navigationsableitung eine konservative Priorisierung, deren Regeln konfigurierbar und sichtbar sein müssen.
- `traversability` darf nicht automatisch allein aus `category` als endgültig sicher abgeleitet werden.
- Der Status `approved` beschreibt menschliche Kartendatenfreigabe, keine Zertifizierung der Robotersicherheit.

---

## 6. Geplanter Bedienablauf

1. **Projekt anlegen:** Name vergeben, GeoTIFF auswählen, Metadaten prüfen, GSD und CRS anzeigen.
2. **Karte anzeigen:** Orthomosaik offline im Browser darstellen, Zoom/Pan und Maßstab anbieten.
3. **Erkennung starten:** Ganze Karte oder rechteckigen Bereich auswählen; Pipeline ausführen; Fortschritt/Fehler anzeigen.
4. **Ergebnisse anzeigen:** Polygone farblich nach Hauptkategorie darstellen, Unterkategorie und Attribute bei Auswahl anzeigen, unsichere Objekte hervorheben.
5. **Manuell korrigieren:** Klasse ändern, Stützpunkte verschieben, neue Polygone zeichnen, löschen, Attribute bearbeiten; Undo/Redo.
6. **Sicherheitsabstände einstellen:** Werte je Unterkategorie festlegen, abgeleitete Sperrzonen in einer separaten Ebene anzeigen; Originalpolygone nicht überschreiben.
7. **Entwurf speichern:** Projekt vollständig persistieren und später wieder öffnen.
8. **Karte überprüfen und freigeben:** Bewusster Nutzer-Workflow; Freigabestatus speichern; Änderungen nach Freigabe machen erneute Prüfung erforderlich.
9. **Exportieren:** GeoJSON der Objekte, robotertaugliche Navigationskarte nach abgestimmtem Schema und Kartenbild als PNG/JPG.
10. **Optional evaluieren:** Vorhersagepolygone mit Referenzpolygonen vergleichen, Kennzahlen pro Klasse ausgeben.

---

## 7. Entwicklungsphasen und konkrete Aufgaben

### Phase 0 – Machbarkeit und Datensatzprüfung

**Ziel:** Prüfen, ob die automatische Klassifikation der gewünschten Farmstrukturen mit verfügbaren vortrainierten Modellen auf echten Orthomosaiken grundsätzlich funktioniert.

Aufgaben:
- Zwei bis drei repräsentative Orthomosaike beschaffen bzw. vom Projektteam erhalten, einschließlich RTK-/GPS-Daten soweit verfügbar.
- Rastergröße, GSD, CRS, Bildqualität und Dateigröße untersuchen.
- Kleine manuelle Referenzpolygone für alle drei Hauptkategorien erstellen.
- Kandidaten prüfen: OpenCV-Baseline, ein geeignetes vortrainiertes Segmentierungsmodell und, falls verfügbar, ein tatsächlich semantisch klassifizierendes Modell.
- Dokumentieren, welche Klassen zuverlässig erkannt werden und wo Bildinhalt allein nicht ausreicht.
- Hardwarebedarf und Lizenzkompatibilität prüfen.

**Ergebnis:** Machbarkeitsbericht und begründete erste Pipelinewahl; keine voreilige Festlegung auf SAM allein.

### Phase 1 – Geodatenkern und erstes End-to-End-Beispiel

**Ziel:** Eine GeoTIFF-Datei laden, eine kleine Beispielgeometrie georeferenziert darstellen, speichern und exportieren.

Aufgaben:
- Python-Projekt und Paketstruktur anlegen.
- GeoTIFF-Importer, CRS-/GSD-Prüfung, Bounding Box.
- Feature- und Projektmodelle implementieren.
- Polygonvalidierung und GeoJSON-Export erstellen.
- Unit-Tests für CRS, Geometrie und Projektspeicherung.
- Minimalen NiceGUI-/Leaflet-Viewer anbinden.

**Akzeptanz:** Ein Test-GeoTIFF lässt sich lokal öffnen; ein Polygon ist an korrekter geografischer Position sichtbar; nach Speichern/Neuladen bleibt es erhalten; GeoJSON ist GIS-kompatibel.

### Phase 2 – Automatische Erkennung

**Ziel:** Aus einem Orthomosaik automatisch polygonisierte, kategorisierte Vorschläge generieren.

Aufgaben:
- Detektor-Schnittstelle definieren: Eingabe Rasterfenster/Metadaten, Ausgabe Masken/Polygone plus Klasse und Unsicherheitskennzeichnung.
- Mindestens eine klassische Baseline und eine vortrainierte KI-Methode evaluieren.
- Kachelverarbeitung mit Überlappung und geometrischem Merging, falls nötig.
- Masken in gültige Polygone umwandeln.
- Ergebnisqualität anhand der Referenzpolygone messen.
- Verarbeitungsbereich auf gesamte Karte oder Rechteck begrenzen.
- Keine Klassenkonfidenz erfinden, wenn Modell keine belastbare Schätzung liefert.

**Akzeptanz:** Auf einer echten Testkarte werden automatisch Polygone vorgeschlagen; Zuordnungen und erkennbare Unsicherheiten sind dokumentiert; Ergebnisse bleiben geografisch korrekt.

### Phase 3 – Polygoneditor und Projektpersistenz

**Ziel:** Vollständig bearbeitbare Ergebnisse mit robustem Speichern.

Aufgaben:
- Polygone auswählen und Klassen/Unterkategorien ändern.
- Vertex-Editing, manuelles Zeichnen und Löschen.
- Undo/Redo über definierte Editieraktionen.
- Befahrbarkeit und Review-Status editieren.
- Projekt speichern, schließen und wieder öffnen.
- Änderungen an einzelnen Features nachvollziehbar machen.

**Akzeptanz:** Alle Pflichtaktionen funktionieren ohne Datenverlust; Undo/Redo stellt vorherige Geometrien/Attribute wieder her; Projekt-Roundtrip ist getestet.

### Phase 4 – Sicherheitszonen, Freigabe und Navigations-Export

**Ziel:** Geprüfte Polygone in eine konsistente, für Zauberzeug weiterverwendbare Karte überführen.

Aufgaben:
- Zentrale Sicherheitseinstellungen je Unterkategorie implementieren.
- Puffer im metrischen CRS berechnen; Originalgeometrien erhalten.
- Überlappungen und Konflikte konservativ behandeln.
- Vorschau der Sperrzonen auf der Karte.
- Freigabe-Workflow für die Gesamtkarte.
- Finalen GeoJSON-Export implementieren; Ziel-Schema mit Zauberzeug abstimmen.
- PNG/JPG-Kartenexport implementieren, inklusive lokaler Hintergrundbilddaten.

**Akzeptanz:** Ändern des Wasserpuffers von z. B. 1,0 auf 1,5 m ändert nur abgeleitete Sperrzonen; Ursprungsgeometrien bleiben gleich. Ungeprüfte Karten können nicht als finale robotertaugliche Karten exportiert werden.

### Phase 5 – Validierung, Offline-Betrieb und Übergabe

**Ziel:** Reproduzierbarer Prototyp mit dokumentierter Qualität.

Aufgaben:
- Test auf Linux und macOS; Einschränkungen für KI-Beschleunigung dokumentieren.
- Nach vorbereitender Installation Netzwerkverbindung trennen und alle Kernfunktionen testen.
- GeoJSON in QGIS oder gleichwertigem GIS prüfen.
- IoU, Precision und Recall je Kategorie und gesamt auswerten; Referenzdaten und Metrikdefinitionen dokumentieren.
- RTK- und GPS-Orthomosaike mit identischem Workflow verarbeiten; absolute Positionsgenauigkeit ggf. separat analysieren.
- Installationsanleitung, Nutzerhandbuch, Entwicklerdokumentation und bekannte Grenzen erstellen.
- Lizenz- und Datenschutzprüfung für Code, Modelle und Beispielbilder.

**Akzeptanz:** Installation reproduzierbar, vollständiger Offline-Durchlauf möglich, gespeicherte Projekte erneut nutzbar, Evaluation nachvollziehbar.

---

## 8. Tests und Qualitätskriterien

### Funktionale Tests
- GeoTIFF mit gültigem CRS wird korrekt geladen.
- GeoTIFF ohne erforderliche Georeferenzierung führt zu klarer Fehlermeldung, nicht zu falschen Koordinaten.
- Auswahl eines Teilbereichs verändert nicht versehentlich Polygone außerhalb des Bereichs.
- Erstellte/edierte/gelöschte Polygone bleiben nach Projektspeicherung konsistent.
- Undo/Redo funktioniert für Geometrie- und Attributänderungen.
- Sicherheitsabstände erzeugen erwartete geometrische Puffer in Metern.
- Originalgeometrien bleiben bei Neuberechnung unverändert.
- Änderungen nach einer Freigabe invalidieren den finalen Freigabestatus oder verlangen erneute Freigabe.
- GeoJSON enthält die vereinbarten Pflichtattribute und gültige Geometrien.
- Offline-Start und Offline-Kartenansicht funktionieren ohne externe CDN-/Tile-Requests.

### Quantitative Erkennungsbewertung
- Pro Klasse und gesamt: IoU sowie klar definierte Precision/Recall-Metriken.
- Trenne Pixel-/Flächenmetriken von objektbasierten Metriken; nicht vermischen.
- Vergleiche KI-Polygone mit manuell erstellten Referenzpolygonen auf demselben georeferenzierten Bild.
- Dokumentiere Testflächen, Klassenhäufigkeiten, nicht annotierte Bereiche und eventuelle Toleranzen.
- Bewerte Fehlklassifikationen mit besonderer Aufmerksamkeit für übersehene Hindernisse.
- Setze zunächst **keine erfundenen numerischen Erfolgsgrenzen**; Zielwerte nach Machbarkeit und mit Zauberzeug definieren.

### Absolute Positionsgenauigkeit der Orthomosaike
- Vergleiche unabhängige Referenzmessungen mit identifizierbaren Bildpunkten.
- Prüfe verwendetes CRS, Messmethode und Unsicherheit der Referenz.
- Berichte horizontale Abweichungen getrennt für RTK- und GPS-basierte Orthomosaike.
- Die konkrete Integration dieser Analyse in die App ist **offen**.

---

## 9. Technische Risiken und Gegenmaßnahmen

| Risiko | Auswirkung | Gegenmaßnahme |
|---|---|---|
| Vortrainierte Modelle erkennen Farmklassen nicht zuverlässig | Falsche oder fehlende Polygone | Frühe Machbarkeitsphase; Baseline und Modellkandidaten testen; manuelle Korrektur |
| SAM erzeugt nur Masken ohne Klassen | Keine automatische semantische Zuordnung | Separate Klassifikation oder geeignetes semantisches Modell evaluieren |
| GPS-Orthomosaik geografisch verschoben | Falsche Lage der Navigationskarte | CRS-Prüfung, unabhängige Referenzmessungen, keine Genauigkeitsgarantien |
| Baumkronen verdecken Stamm/Weg | Falsche Befahrbarkeitsannahmen | Subtypen und Review-Flags; konservative Freigabe; Feldvalidierung |
| Große Raster/hoher Modell-RAM-Bedarf | Langsame Verarbeitung oder Abstürze | Kacheln, Overviews, begrenzte Parallelität, Hardwareprofiling |
| Leaflet-Editor/Offline-Assets inkompatibel | Eingeschränkte Bearbeitung offline | Früher UI-Prototyp; lokale JS-Assets; Integrationstests |
| Uneinheitliche CRS-Einheiten | Fehlerhafte Meter-Puffer | Vor Buffer in geeignetes metrisches CRS transformieren |
| Roboterschema unbekannt | Export nicht direkt nutzbar | Exportadapter und Abstimmung mit Zauberzeug |
| Modell-/Code-Lizenzen unklar | Keine zulässige Weitergabe | Lizenzen von Paketen und Gewichten separat dokumentieren |

---

## 10. Bewusst offene Entscheidungen

Diese Punkte dürfen von der umsetzenden KI nicht stillschweigend als abgeschlossen dargestellt werden:

1. Zielhardware und Mindestanforderungen.
2. Zusätzliche Eingabeformate neben georeferenziertem GeoTIFF.
3. Verbindliche Positionsgenauigkeit für den Feldfreund.
4. Exaktes GeoJSON-/Navigationsschema und mögliche POI-Darstellung von Ladestationen.
5. Integration der Referenzpunkt- und RTK-vs.-GPS-Auswertung in die UI.
6. Konkrete vortrainierte Modelle und Erkennungspipeline.
7. Optionale manuelle Modellauswahl oder Expertenansicht.
8. Exakte quantitative Zielwerte für IoU, Precision und Recall.
9. Sicherheitsabstände für alle Objekt-Unterkategorien und deren Freigabe durch Zauberzeug.
10. Datensatzverfügbarkeit und Umfang der Referenzannotation.

---

## 11. Definition of Done für den ersten nutzbaren Prototyp

Ein Prototyp gilt als funktional, wenn ein Nutzer auf Linux oder macOS nach dokumentierter Installation:

1. die Anwendung lokal und ohne Internetverbindung starten kann;
2. ein georeferenziertes GeoTIFF bis zum vorgesehenen 5-ha-Anwendungsfall laden und anzeigen kann, soweit die verfügbare Hardware ausreicht;
3. die komplette Karte oder einen ausgewählten Bereich automatisch analysieren kann;
4. Polygonvorschläge in den drei Hauptkategorien sehen und unsichere Vorschläge erkennen kann;
5. Polygone zeichnen, löschen, umklassifizieren, an Stützpunkten bearbeiten und Aktionen rückgängig machen/wiederholen kann;
6. das Projekt inklusive aller Änderungen speichern und wieder öffnen kann;
7. Sicherheitsabstände je Unterkategorie einstellen und daraus neue Sperrzonen berechnen kann, ohne Originalpolygone zu verändern;
8. eine geprüfte Karte ausdrücklich freigeben kann;
9. GeoJSON und eine Kartenabbildung (PNG/JPG) exportieren kann;
10. den Export in einem GIS öffnen und Koordinaten sowie Attribute prüfen kann;
11. die Erkennung anhand vorhandener Referenzpolygone quantitativ bewerten kann.

**Wichtig:** Ob das Exportformat unmittelbar vom Feldfreund konsumiert werden kann, hängt von der noch offenen Schnittstellenabstimmung mit Zauberzeug ab. Bis dahin wird ein dokumentiertes, georeferenziertes neutrales Exportformat implementiert.

---

## 12. Konkrete Startanweisung an die Coding-KI

> Du bist Lead Python-/Geospatial-/Computer-Vision-Entwickler für dieses Projekt. Setze die oben beschriebene Anwendung iterativ um. Beginne **nicht** sofort mit einem großen monolithischen Codeblock. Gib zuerst (1) eine kompakte Architektur, (2) eine begründete Auswahl der minimal nötigen Bibliotheken, (3) eine Liste technischer Risiken, (4) eine Reihenfolge kleiner Implementierungsschritte und (5) höchstens die wenigen Rückfragen, die das erste lauffähige Inkrement tatsächlich blockieren. Erstelle danach die Projektstruktur und implementiere als erstes einen End-to-End-Durchstich: georeferenziertes GeoTIFF laden → lokal in NiceGUI/Leaflet anzeigen → ein Testpolygon erzeugen/bearbeiten → Projekt speichern → gültiges GeoJSON exportieren. Schreibe Tests für CRS, Geometrie und Persistenz. Erkläre vor jedem vorgeschlagenen Terminalbefehl dessen Zweck. Implementiere die automatische Erkennung anschließend als austauschbares Backend und validiere ihre semantische Qualität an echten Referenzdaten, bevor du ein bestimmtes KI-Modell als Lösung festlegst. Halte den gesamten Laufzeit-Workflow offline-fähig und dokumentiere alle offenen Entscheidungen.

---

## 13. Priorisierte nächste Abstimmungen mit Zauberzeug

1. Welche GeoJSON-Struktur oder andere Kartenschnittstelle kann der Feldfreund einlesen?
2. Wie werden `work_area`, `navigable_area`, `obstacle`, Ladestationen und Sperrzonen robotseitig interpretiert?
3. Welche Positionsgenauigkeit und welche Sicherheitsabstände werden tatsächlich benötigt?
4. Wie sollen nicht erkennbare Hindernisse, Baumkronen, Fahrspurbreiten und unsichere Bereiche behandelt werden?
5. Welche Test-Orthomosaike, Referenzpolygone und GNSS-Messdaten stehen zur Verfügung?

**Ende des Projektplans.**
