# Offline Farm Mapping

Inkrementeller Prototyp gemäß `Projektplan_Farm_Mapping_KI.md`.
Eigenständiger Python-Geodatenkern und lokale NiceGUI-/Leaflet-Oberfläche.

## Installation und Start (Linux/macOS)

Python 3.12 empfohlen. Einmalige Installation mit Internet erforderlich.
Die folgenden Befehle erstellen eine isolierte Umgebung, installieren das Projekt,
erzeugen Testdaten und starten die lokale Oberfläche:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python examples/synthetic_demo.py
farm-mapping
```

Browser: http://127.0.0.1:8080 . Zum Testen dort den absoluten Pfad zu
`workspace/demo.project.json` eingeben und „Projekt öffnen“ klicken.
Alternativ ein RGB-GeoTIFF öffnen. Pfade beziehen sich auf den lokalen Server.
Mit der Polygon-Schaltfläche zeichnen; bestehende Polygone im Auswahlfeld wählen.
Attribute und WGS84-Geometrie im Formular bearbeiten und übernehmen.
Alternativ ein Polygon anklicken, „Stützpunkte auf der Karte verschieben“ aktivieren
und die Marker ziehen. Gültige Änderungen werden direkt übernommen; Undo macht sie rückgängig.
Projekt speichern; GeoJSON wird über den Browser heruntergeladen.

Der folgende Befehl führt die Tests für CRS, Persistenz, Geometrie, Import und Export aus:

```bash
python -m pytest
```

## Stand und Grenzen

Implementiert: RGB-GeoTIFF-Prüfung mit SHA256, reprojizierte lokale Vorschau,
Polygonzeichnen, Geometrie-/Attributformular, Löschen, Undo/Redo,
atomare Projektspeicherung inklusive Bearbeitungshistorie, metrische Sicherheitszonen,
Abstandseinstellungen je Unterkategorie, separater Sperrzonen-GeoJSON-Export, Entwurfs-GeoJSON,
Gesamtkartenfreigabe und deren Invalidierung bei Bearbeitung.

**Dies ist noch nicht der vollständige nutzbare Prototyp.** Ausstehend:
automatische klassische/KI-Erkennung,
Teilbereichsanalyse, Ableitung konfliktfreier Navigationsflächen,
PNG/JPG-Kartenexport, Evaluation und reale Datenvalidierung.
Sperrzonen erscheinen violett und bleiben von Originalpolygonen getrennt.
Unter „Sicherheitsabstände und Sperrzonen“ Abstände je Unterkategorie ändern und
„Abstände übernehmen“ klicken. Originalpolygone bleiben unverändert; die
Gesamtkartenfreigabe wird widerrufen. Undo/Redo berücksichtigt Abstandänderungen.
Hindernisse und explizit nicht befahrbare Objekte erzeugen Sperrzonen.
Nicht konfigurierte Unterkategorien verwenden vorläufig 0 m Zusatzpuffer.
Diese Defaults müssen fachlich geprüft werden. Unbekannte Flächen erhalten keine
Befahrbarkeitsfreigabe. Ladestationen werden nicht automatisch als Hindernis klassifiziert.
Export ist ein neutrales Objekt-GeoJSON, keine bestätigte Feldfreund-Navigationskarte.
Die Freigabe ist eine Kartendatenfreigabe, keine Sicherheitszertifizierung.

Keine Online-Kachelserver: Standard-Leaflet-Kacheln werden entfernt.
NiceGUI liefert seine Frontend-Abhängigkeiten lokal. Ein Browser-Test ohne Netzwerk
steht noch aus; vollständiger Offline-Betrieb ist deshalb noch nicht nachgewiesen.
Vorschau auf maximal 1600 Pixel begrenzt, Original bleibt unverändert.
RGB-Bänder 1–3 sind vorläufiger Default; Multispektral-/Bandzuordnung noch offen.

Prüfstand: 12 Tests bestanden (Import, CRS, Persistenz, Export und metrische Puffer),
keine Shapely-Deprecation-Warnungen. Der erste UI-Durchstich wurde vom Nutzer unter
Linux gestartet. Die neue Sicherheitszonen-Oberfläche ist noch nicht im Browser
validiert. Ein HTTP-Smoke-Test aus der eingeschränkten Ausführungsumgebung konnte
den lokalen Server trotz NiceGUI-Startmeldung nicht erreichen.

## Bildübersicht

Beim Öffnen eines GeoTIFFs oder gespeicherten Projekts erscheint über der Karte
 eine Übersicht mit Dateiname, Auflösung in cm/Pixel (X/Y), gültiger Bildfläche
in ha, Pixelmaßen und CRS. Die Fläche zählt Pixel mit gültiger Rastermaske;
transparente/NoData-Ränder sind ausgenommen. Pixel werden blockweise gezählt.
Die Pixelfläche folgt aus dem Betrag der Determinante der affinen Transformation,
umgerechnet aus den projizierten CRS-Einheiten in Quadratmeter. Es handelt sich
um die projizierte Bildabdeckung, nicht um eine vermessene Feldgrenze.
Bei geografischen CRS ist die metrische Auflösung/Fläche derzeit nicht verfügbar.
Ältere Projektdateien bekommen diese Metadaten beim Öffnen ergänzt.
Prüfstand dieser Ergänzung: 15 Tests bestanden; Werte zusätzlich mit beiden
bereitgestellten GeoTIFFs geprüft. Visuelle Browserprüfung steht aus.

## Kartenbearbeitung

Ausgewählte Polygone lassen sich mit verschiebbaren Stützpunkt-Markern bearbeiten.
Innenringe und MultiPolygone bleiben erhalten. Ungültige Änderungen werden verworfen.
Jede gültige Änderung aktualisiert Sperrzonen und widerruft eine Kartenfreigabe.
Prüfstand: 21 Bibliothekstests bestanden; interaktive Browserprüfung noch offen.

### Weitere Stützpunkte

Im Modus „Stützpunkte auf der Karte verschieben“ erscheinen blaue Plus-Punkte
auf der Mitte jeder Kante des ausgewählten Polygons. Ein Klick fügt dort einen
Stützpunkt ein. Den neuen Marker anschließend an die gewünschte Position ziehen.
Einfügen funktioniert auch auf der schließenden Kante, Innenringen und weiteren
Teilen eines MultiPolygons. Undo/Redo und Projektspeicherung erhalten die Punkte.
Das Einfügen widerruft eine bestehende Kartenfreigabe.
Prüfstand: 24 Tests bestanden; Browserinteraktion für Plus-Marker noch zu prüfen.

## Versionsverwaltung und Backup

Der aktuelle Ausgangsstand ist in [CHANGELOG.md](CHANGELOG.md) beschrieben.
[Git-/GitHub-Anleitung](docs/version-control.md) erklärt Erstinstallation,
kleine Entwicklungs-Commits, Branches und das Rückgängigmachen mit `git revert`.
TIFFs und bearbeitete Kartenprojekte sind von Git ausgeschlossen und müssen
separat gesichert werden.
