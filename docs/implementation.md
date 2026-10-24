# Architektur und offene Validierung

## Architektur

`farm_mapping.core` enthält Modelle, Geometrieprüfung, CRS-Transformation,
Historie, Persistenz und GeoJSON. Keine UI-Abhängigkeit beim Core-Import.
`farm_mapping.raster` lädt RGB-GeoTIFFs und erstellt eine begrenzte Vorschau
in Web Mercator, passend zur Leaflet-Projektion.
`farm_mapping.app` ist die lokale NiceGUI-Oberfläche auf 127.0.0.1.

Projektformat v1: eine JSON-Datei mit Originaldateipfad, SHA256, WKT-CRS,
Rastermetadaten, Originalgeometrien im Raster-CRS, Objektattributen,
Sicherheitsabständen, Freigabe und Undo-/Redo-Snapshots.
Originalraster wird referenziert, nicht kopiert. Fehlende oder veränderte
Originaldateien blockieren die Vorschau mit Fehlermeldung.
GeoJSON verwendet WGS84 in Reihenfolge Länge/Breite, Quell-CRS als Metadatum.
Alle Bearbeitungen und Undo/Redo widerrufen die Freigabe.

## Bibliotheken

Rasterio (BSD-3-Clause), PyProj (MIT), Shapely (BSD-3-Clause),
NumPy (BSD-3-Clause), Pillow (HPND), NiceGUI (MIT), Pytest (MIT).
Diese Angaben sind eine Orientierung; bei Weitergabe müssen die tatsächlich
installierten Versionen und transitiven Lizenztexte mitgeprüft werden.
Kein KI-Modell und keine Modellgewichte ausgewählt oder heruntergeladen.
Versionsbereiche sind noch kein getesteter Lockfile.

API-Grundlagen:
- https://nicegui.io/documentation/leaflet
- https://rasterio.readthedocs.io/en/stable/topics/reproject.html

## Nächste Schritte

1. Abhängigkeiten installieren und Tests ausführen; UI-APIs im Browser prüfen.
2. Kartenbasiertes Vertex-Editing einschließlich gespeicherter Polygone integrieren.
3. Konfliktfreie Navigationsflächen unter Berücksichtigung der Sperrzonen ableiten.
4. Gekachelte klassische Baseline und austauschbare Modell-Schnittstelle erstellen.
5. Mit echten Orthomosaiken/Referenzpolygonen vortrainierte Kandidaten vergleichen.
6. Bereichsanalyse, Flächenmetriken, Bildexport und Offline-Browsertest ergänzen.

Offen bleiben Hardware, reale Datensätze, konkrete KI-Pipeline und Lizenzen der
Gewichte, Genauigkeitsziele, Ziel-Roboterschema, POI-Darstellung der Ladestation,
verbindliche Sicherheitsabstände und Referenzmessverfahren.

## Sicherheitszonen

`farm_mapping.safety` leitet Sperrzonen von Hindernissen und explizit nicht
befahrbaren Objekten ab. Metrische projizierte Quell-CRS werden direkt verwendet;
sonst dient eine lokale azimutale äquidistante Projektion als Berechnungs-CRS.
Originalgeometrien bleiben unverändert. Abgeleitete Zonen werden deterministisch
neu berechnet und separat exportiert; Distanzregeln liegen im Projekt und in der
Undo-/Redo-Historie. Überlappungen bleiben Sperrzonen; eine Berechnung konfliktfreier
befahrbarer Navigationsflächen ist noch nicht implementiert.

## Prüfstand

12 Tests bestanden, einschließlich Meter-Puffern aus geografischen und US-Fuß-CRS,
0-m-Puffern, Originaldatenerhalt und Freigabeinvalidierung. Shapely verwendet nun
`shapely.transform(..., interleaved=False)` ohne die bisherige Deprecation-Warnung.
Die Polygonanzeige verwendet die installierte NiceGUI-API `generic_layer('geoJSON')`.
Der Nutzer hat den ersten UI-Stand unter Linux gestartet. Die neue UI und Offline-
sowie macOS-Validierung stehen aus. NiceGUI meldet Serverstart, ein lokaler HTTP-
Aufruf aus der eingeschränkten Ausführungsumgebung schlug jedoch fehl.
Keine Erkennungs- oder Positionsgenauigkeit wird behauptet.
