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
vortrainierte KI-Erkennung und empirischer Modellvergleich,
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

## Automatische Polygonvorschläge

Nach dem Laden unter der Karte „Ganze Karte analysieren“ anklicken. Die neue
experimentelle klassische RGB-Baseline erzeugt eine türkis gestrichelte Vorschau.
„Vorschläge übernehmen“ ergänzt Entwürfe um bestehende Polygone herum; „Vorschau
verwerfen“ entfernt sie. Übernommene Vorschläge prüfen und das Projekt speichern.
Undo nimmt die gesamte Übernahme zurück. Keine neuen Abhängigkeiten erforderlich.

Dies ist noch kein vortrainiertes KI-Modell und noch keine validierte semantische
Erkennung. Alle Vorschläge erhalten Befahrbarkeit „unbekannt“ und einen Prüfhinweis.
Mindestfläche: 4 m², längste Analyseseite: 1600 Pixel, höchstens 300 Polygone.
Schmale/kleine Hindernisse und Klassen können fehlen. Übersicht und Grenzen:
[Erkennungspipeline](docs/detection.md).

### Zusammenhängende Obstflächen

Die aktuelle Strukturheuristik sucht regelmäßige Baumkronen-Anordnungen in zwei
Richtungen und schlägt die gesamte Anlage einschließlich Zwischenräumen als
Arbeitsfläche `orchard` vor. Einzelbäume, Hecken und unstrukturierte Gehölze bleiben
Hinderniskandidaten. Die Checkbox für Obstflächen und „Fragmente verbinden (m)“
steuern diese experimentelle Zusammenfassung. Kein KI-Modell und keine
Befahrbarkeitsgarantie; Konturen und Kategorien weiterhin prüfen.

Zum Vergleich das GeoTIFF neu öffnen und ein separates Projekt speichern, damit
bereits manuell gezeichnete Referenzbereiche die neue Erkennung nicht überdecken.

### Weniger kleine Teilflächen

Die Erkennung `rgb-context-v3` ergänzt „Arbeitsflächen zusammenfassen“
(standardmäßig 3 m; 0 schaltet diese Stufe aus). Sie verbindet nahe Feldteile
und bezieht kleine kompakte helle Innenflecken als mögliche Bodenvariation ein.
Langgezogene Wegkandidaten sowie Baum- und Gebäudekandidaten bleiben ausgespart.
Ein größerer Radius verbindet stärker, kann aber echte Flächengrenzen überbrücken.
Vorschläge deshalb prüfen. Details und Grenzen: [Erkennungspipeline](docs/detection.md).
Nach Neustart das GeoTIFF frisch öffnen und eine neue Analyse starten;
vorhandene Polygone werden beim Übernehmen weiterhin ausgespart.

### Weniger zackige Konturen und Schattenprüfung

„Flächenränder glätten“ schließt kleine Einbuchtungen und entfernt schmale
Ausläufer an Feldrändern (standardmäßig 0,5 m Radius, maximal 2 m; 0 = aus).
Der gewählte Radius wird direkt angewendet. Innenlöcher und andere ausgegebene
Klassen bleiben ausgespart; kompakte kleine eigenständige Felder bleiben erhalten.
Zum Vergleich eine neue Analyse starten: Bereits übernommene Konturen ändern
sich dadurch nicht. Einzelheiten und Grenzen stehen in der Erkennungspipeline.

Die separate Checkbox „Experimentell: mögliche Schatten in Arbeitsflächen
einbeziehen“ vergleicht dunkle Stellen mit der Farbe benachbarter heller Vegetation.
Sie ist zunächst ausgeschaltet: RGB-Bilder erlauben keine sichere Trennung von
Schatten und Gehölzen. Ergebnisse mit dieser Option besonders prüfen.

### Helle Innenbereiche statt künstlicher Feldtrennungen

„Helle Innenbereiche räumlich prüfen und zusammenfassen“ bewertet helle Flecken
und unterbrochene Streifen nach ihrer Lage in Arbeitsflächen. Größere durchgehende
Wegzüge, direkte Anschlüsse, Maskenränder und Gebäudezufahrtskandidaten bleiben
ausgespart. Neu zugeordnete Bereiche erscheinen in der Analysevorschau orange.
Diese Stellen besonders prüfen: kleine echte Wege können ähnlich aussehen.
Die Checkbox ist standardmäßig aktiv; Abschalten ermöglicht den Vergleich mit
der bisherigen Regel. Regleränderungen erfordern einen neuen Analyselauf.
Schattenbehandlung und manuell gezeichnete Objekte bleiben unverändert.

### Strukturerkennung für Pflanzstreifen und Baumreihen

Die neue standardmäßig aktive Checkbox „Regelmäßige Pflanzstreifen anhand
Richtung und Abstand erkennen“ verbindet passende Reihenmuster auch über
Farb-/Helligkeitsunterschiede und unklassifizierte Bodenbereiche hinweg.
Die bestehende Obstflächen-Checkbox prüft weiterhin regelmäßige Baumabstände
in mehreren Reihen. Beide liefern experimentelle Arbeitsflächenvorschläge,
keine Befahrbarkeitsfreigabe. Neue Zuordnungen erscheinen in der Analyse orange.

Vorbereitete Vergleichsprojekte (Radius 2 m, Schattenoption aus):
`workspace/row_check/elies_rgb.project.json` und
`workspace/row_check/rodia_rgb.project.json`. Daneben liegen PNG-Vergleiche.
Besonders prüfen: zusammengehörige linke Streifenfläche auf Elies, tatsächliche
Feldwege und Grenzen zwischen unterschiedlich bewirtschafteten Flächen auf Rodia.

### Getrennte Strukturgruppen statt einer großen Arbeitsfläche

„Arbeitsflächen nach Strukturgruppen getrennt halten“ trennt unterschiedliche
Reihenmuster von Vegetation ohne sicheren Reihenbeleg und von Obstflächen.
Kleine Flecken genügen nicht für eine neue Grenze. Gruppen werden unterschiedlich
eingefärbt und behalten ihre Kennung beim Speichern. Grün steht für Vegetation
ohne sicheren Reihenbeleg, Braun für Obstflächen, weitere Farben für Reihengruppen;
alle gehören weiterhin zur Kategorie Arbeitsfläche. Gruppengrenzen sind Vorschläge.

Vorbereitete Projekte: `workspace/group_check/elies_rgb.project.json` und
`workspace/group_check/rodia_rgb.project.json`, jeweils mit PNG-Vergleich.
Für eine neue Analyse das GeoTIFF frisch öffnen. Bereits übernommene Polygone
haben weiterhin Vorrang vor neuen Vorschlägen. Bei Gruppentrennung zeigen die
Farben die Gruppen; die orange Ergänzungsschicht wird dafür ausgeblendet.
