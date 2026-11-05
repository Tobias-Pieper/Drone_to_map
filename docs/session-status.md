# Übergabestand – 25. Oktober 2026

## Nutzerwunsch

Arbeit auf Wunsch des Nutzers unterbrochen. Bei Fortsetzung zuerst diesen Stand
lesen. Keine weiteren Erkennungsänderungen ohne die Wiederaufnahme der Arbeit.

## Projekt und Sicherung

- Arbeitsordner: `/home/tobi/Projects/Drone_to_map`.
- Privates persönliches Repository: https://github.com/Tobias-Pieper/Drone_to_map
- Der Nutzer hat den Ausgangsstand selbst erfolgreich auf `main` hochgeladen.
- Spätere Erkennungsänderungen sind möglicherweise noch nicht committed/gepusht;
  bei Wiederaufnahme `git status` und Verlauf prüfen, keine Sicherung behaupten.
- Git-Schreibzugriffe des Agenten scheiterten wiederholt an schreibgeschütztem
  `.git` (`index.lock`). Nutzer kann Git-Befehle selbst im Terminal ausführen.
- `data/`, `workspace/`, TIFFs und `.venv/` sind von Git ausgeschlossen.
  Originalbilder und manuelle Karten benötigen ein separates Backup.

## Start

Im Projektordner die Umgebung aktivieren und Anwendung starten:

```bash
source .venv/bin/activate
farm-mapping
```

Browser: http://127.0.0.1:8080 . Nach Codeänderungen Server neu starten und Seite
neu laden. Ziele sind Linux und macOS; Nutzer arbeitet derzeit unter Linux.

## Funktionierender Stand

- Separater Python-Geodatenkern und lokale NiceGUI-/Leaflet-Oberfläche.
- GeoTIFF-/RGBA-Import, Offline-Bildhintergrund, große Karte (70 vh, min. 500 px).
- Dateiauswahl aus `data/` und verständliche Pfadprüfung.
- Bildübersicht: cm/Pixel, gültige Bildfläche in ha ohne transparente Ränder,
  Pixelmaße und CRS.
- Polygone zeichnen, auswählen, Kategorie/Unterkategorie/Befahrbarkeit ändern,
  löschen; Stützpunkte verschieben und per Plus-Marker ergänzen.
- Polygonliste nach Hauptkategorie vor den Sicherheitsabständen.
- Undo/Redo, atomare Projektspeicherung und Wiederöffnen samt Historie.
- Metrische Sicherheitszonen, editierbare Abstände und separater Export.
- Gesamtkartenfreigabe; Bearbeitungen widerrufen sie.
- Neutraler WGS84-GeoJSON-Export; kein abgestimmtes Feldfreund-Navigationsschema.
- Nutzer hat die grundlegenden interaktiven Funktionen erfolgreich ausprobiert.

## Eingabedaten und manuelle Referenz

- `data/elies_rgb.tif`: EPSG:32634, ca. 5 cm/Pixel, gültige Bildfläche ca. 1,7485 ha.
- `data/rodia_rgb.tif`: EPSG:32634, ca. 5 cm/Pixel, gültige Bildfläche ca. 4,0860 ha.
- `workspace/project.json` enthielt beim letzten Vergleich die manuelle Vorlage:
  12 Polygone, Revision 12. Pfad kann später überschrieben worden sein: prüfen.
- Gesicherte Referenzkopie:
  `workspace/reference_check/manual-reference-84d8bdf3a2ef.project.json`.
- Die zwei Arbeitsflächen der Vorlage umfassen ca. 3342 und 910 m²;
  zusätzlich Gebäude-, Baum- und Zaunbereiche.
- Frei vergebene Unterkategorien enthalten u.a. `house`, `trees`, `field` auch bei
  Hindernissen. Nicht stillschweigend normalisieren oder Sicherheitsregeln erfinden.

## Fachlich bestätigte Regel

Regelmäßige Baumreihen mit Zwischenräumen bilden eine zusammenhängende
Arbeitsfläche einschließlich Baumkronen und Zwischenräumen. Einzelne Bäume,
Hecken und unstrukturierte größere Baumflächen sind Hindernisse.
Arbeitsflächenzuordnung ist kein Nachweis tatsächlich freier/befahrbarer Flächen;
Befahrbarkeit automatischer Vorschläge bleibt `unknown`.

## Automatische Erkennung: bisher nur klassische Heuristiken

- Austauschbare Schnittstelle in `src/farm_mapping/detection/`.
- Aktuelle Methode: `rgb-structure-v2`; noch kein vortrainiertes KI-Modell,
  kein eigenes Training, keine installierten Modellgewichte.
- RGB-Regeln für Vegetation, helle Weg-, rötliche Dach- und dunkle Baumkandidaten.
- Strukturheuristik: mindestens neun Kronenkandidaten in einer regelmäßigen
  zweidimensionalen Anordnung; gedrehte Raster werden berücksichtigt.
  Einzelreihen reichen nicht für eine Obstfläche (`work_area` / `orchard`).
- Fragmentzusammenfassung, einstellbarer Radius standardmäßig 1 m.
- Standard: längste Analyseseite 1600 px, Mindestfläche 4 m², max. 300 Vorschläge.
- Hintergrundprozess, türkis gestrichelte Vorschau, explizite Übernahme/Verwerfen.
- Bestehende Polygone haben Vorrang: neue werden um bestehende herum ausgeschnitten.
- Übernahme ist ein Undo-Schritt; neue Objekte sind prüfpflichtige Entwürfe.
- Provenienz/Parameter/SHA256 werden gespeichert, keine erfundene Confidence.
- Zum Vergleich GeoTIFF neu öffnen und separates Projekt speichern; vorhandene
  manuelle Referenzpolygone würden die Vorschläge bei Übernahme sonst überdecken.

## Letzte Prüfung

- 36 Tests bestanden, einschließlich synthetischer Strukturtests und serverseitiger
  NiceGUI-Benutzersimulation (Vorschau/Verwerfen/Übernehmen/Undo).
- Benutzersimulation ersetzt den Worker-Start; kein vollständiger Browsertest.
- Letzter realer Strukturlauf: `elies_rgb.tif` 72 Vorschläge
  (1 orchard, 17 field, 20 path, 33 tree, 1 building), ca. 20 s.
- Erkannte Obstfläche ca. 2850,52 m² gegenüber manuellen 3341,98 m²;
  IoU ca. 0,7988 auf diesem Entwicklungsbeispiel, keine allgemeine Genauigkeit.
- `rodia_rgb.tif`: 234 Vorschläge (131 field, 83 path, 20 tree),
  keine Obstfläche erkannt, ca. 25 s.
- Ergebnisse getrennt unter `workspace/structure_check/`, ältere Baseline unter
  `workspace/detection_check/`, Referenzvergleich unter `workspace/reference_check/`.
- Originalprojekt und Referenz wurden durch Agenten-Testläufe nicht überschrieben.

## Letzte Rückmeldung und nächster Schritt

Nutzer: „Es ist schon besser geworden aber nicht perfekt.“ Noch nicht geklärt,
welche Grenzen/Objekte im neuen Ergebnis konkret falsch sind. Zuletzt angeboten:
separat gespeicherten aktuellen Erkennungsstand mit manueller Referenz vergleichen
und gezielt zwischen zu kleinen/großen Konturen, Fragmentierung, fehlenden Objekten
und falschen Klassen unterscheiden. Nutzer hat noch keinen neuen Vergleichspfad
oder spezifischen Fehler genannt und möchte später weitermachen.

Bei Wiederaufnahme erst diesen Punkt klären bzw. vorhandene neue Projektdateien
prüfen. Nicht blind weitere Schwellen an genau einem Bild optimieren.
Vortrainierte Modellkandidaten, Lizenz-/Gewichtsprüfung, Hardwarebedarf und ein
unabhängiger Referenzvergleich stehen noch aus. SAM allein liefert keine
semantischen Farmklassen. Ebenfalls offen: Teilbereichsanalyse, vollständige
Evaluation, Bildexport, macOS-/Offline-Endprüfung und Roboter-Zielschema.

Weitere Details: `docs/detection.md`, `docs/implementation.md`, `CHANGELOG.md`
und verbindliche Spezifikation `Projektplan_Farm_Mapping_KI.md`.

## Fortsetzung – 1. November 2026

Nutzer konkretisiert das Problem: zu viele kleine Teilflächen durch uneinheitliches
Aussehen; Umsetzung der Flächenzusammenfassung ausdrücklich beauftragt.

- Neue Methode `rgb-context-v3`, zusätzliche Kontextstufe `coherent_fields`.
- UI: „Arbeitsflächen zusammenfassen (m; 0 = aus)“, Default 3 m, maximal 5 m.
- Schließt Lücken zwischen Feldteilen und begrenzte Innenlöcher bis 100 m²;
  kleine kompakte helle Innenflecken dürfen einbezogen werden. Langgezogene
  Wegkandidaten und Baum-/Gebäude-/Obstflächenkandidaten bleiben ausgespart.
- Originale und manuelle Referenz nicht überschrieben. Neue Vergleichsprojekte:
  `workspace/context_check/elies_rgb.project.json` und `rodia_rgb.project.json`.
  Zahlen und Referenzabdeckung: `workspace/context_check/report.json`.
- Elies: 72 → 60 Vorschläge, Feldpolygone 17 → 10; Rodia: 234 → 141,
  Feldpolygone 131 → 67. Vergleich jeweils gegen gespeicherten v2-Stand.
- Abdeckung der zwei manuellen Arbeitsflächen auf Elies: 86,72 → 88,79 % und
  57,98 → 65,51 %. Überlappende Vorschläge (mindestens 1 m²): 10 → 8 und 6 → 5.
  Dies ist nur Referenzabdeckung, kein Beleg für allgemein bessere Genauigkeit.
- Baum-, Gebäude- und Obstflächengeometrien auf beiden Bildern numerisch mit
  v2 verglichen: unverändert; keine Überlappung neuer Feldflächen mit anderen
  ausgegebenen Klassen. 40 Tests bestanden; UI weiterhin visuell zu prüfen.
- Kompakte reale Plätze/Wege können als Bodenvariation einbezogen werden;
  größere Radien können echte Grenzen überbrücken. Dunkle Baumkandidaten bleiben
  erhalten: Schattenproblem weiterhin offen. Manuelles Mehrfach-Zusammenführen
  wurde noch nicht ergänzt. Nächster Schritt: Nutzer prüft die neuen Konturen.

## Weitere Fortsetzung – Konturen und Schatten, 1. November 2026

Nutzer: Ergebnis deutlich besser, aber untypisch zackige Konturen und dunkle
Schattenstellen. Neue Methode `rgb-appearance-v4`:

- Feldaußenkonturen werden standardmäßig mit 0,5 m Toleranz vereinfacht.
  0–2 m einstellbar, 0 schaltet aus. Symmetrische Flächenänderung pro
  Ausgangspolygon maximal 5 %, sonst Toleranz reduzieren oder Original behalten.
  Innenlöcher, andere ausgegebene Klassen und gültige Rastermaske ausgespart.
- Separate Checkbox für experimentelle Schattenbehandlung, standardmäßig AUS.
  Lokaler Vergleich normalisierter RGB-Farbe mit heller Feldvegetation und
  Helligkeitsstreuung; kompakte dunkle Komponenten bis 55 m² geschützt.
  Die ursprünglichen Dunkelkomponenten bleiben Basis der Obstflächenerkennung.
- Schattenhypothesen vor Polygonfilterung im Lauf gespeichert; keine sichere
  Unterscheidung von Schatten und Gehölzen. Visuelle Diagnose auf Elies zeigt
  sowohl plausible Schattenpixel als auch falsch erfasste Teile von Gehölzen.
  Nicht als gelöst darstellen, Option bleibt separat und experimentell.
- 48 Tests bestanden (einschließlich Pipeline mit Schattenoption, Schutz kompakter
  Kronen, Farbabgleich, Masken, Glättung, metrische Einheiten und Abschalten).
- Vergleichsprojekte unter `workspace/appearance_check/`, getrennt nach
  `*-smooth.project.json` und `*-shadows.project.json`.
  Magenta markierte Schattenhypothesen: `elies-shadow-hypotheses.png`.
- Auf Elies reduziert Glättung allein die Zahl der Feldaußenstützpunkte von
  7242 auf 6524, Gesamtfeldfläche 8617,92 → 8604,38 m². Feldzahl bleibt 10.
  Mit Schattenversuch: 97,83 m² umklassifizierte Pixel; Feldzahl 8, Baumzahl 28.
  Weniger Baumkandidaten sind kein Qualitätsbeleg und können falsch sein.
- Neue UI-Regler und Checkbox noch nicht interaktiv im Browser geprüft.
- Abschließender Rodia-Vergleich: Feldaußenstützpunkte 23729 → 22230 nur mit
  Glättung; Feldfläche 19261,44 → 19178,06 m². Schattenoption markiert 174,85 m²
  Pixel. Alle vier Ausgaben samt `report.json` gespeichert und Geometriegültigkeit
  geprüft; numerische Klassenüberlappung jeweils unter 0,0001 m².

## Flächenränder auf Nutzerwunsch überarbeitet

Nutzer zeigt Screenshots mit Glättung 0 und 2: kaum Unterschied. Expliziter
Auftrag: zuerst die Flächenränder bearbeiten, Schatten noch nicht weiter ändern.

- Methode `rgb-boundaries-v5`: `smooth_fields` schließt schmale Einbuchtungen
  und entfernt schmale Ausläufer durch Schließen/Öffnen der Außenhüllen.
  Restvereinfachung mit einem Viertel des Radius, Gehrungslimit 2.
- Keine stille Reduktion des Radius durch 5-%-Bremse mehr. Parameter heißt
  jetzt „Flächenränder glätten (Radius in m; 0 = aus)“, weiterhin 0–2 m.
- Kleine ganze Flächen werden bei leerem Öffnungsergebnis erhalten. Innenlöcher,
  andere ausgegebene Kategorien und Rastermaske bleiben ausgespart.
- Sub-Mindestflächenfragmente werden vor der Glättung entfernt, damit keine
  unsichtbaren kleinen Randzwänge entstehen. Schattenlogik nicht geändert.
- 51 Tests bestanden, einschließlich neuer Kerben-/Ausläuferfälle mit 0,2/2 m,
  metrischen Einheiten, echter großer Ecke und kleinem eigenständigem Feld.
- Vergleich 0/2 m frisch gerechnet unter `workspace/boundary_check/`, ohne
  Schattenoption. Projektdateien: `elies_rgb-radius-0.project.json`,
  `elies_rgb-radius-2.project.json`, entsprechende Rodia-Dateien.
- PNGs `*-comparison.png` zeigen nur Feldaußenkonturen nebeneinander, 0 links,
  2 rechts. Elies-PNG vom Agenten visuell geprüft: schmale Randspitzen reduziert;
  gemeinsame Grenzen zu Baum-/Schattenkandidaten bleiben erwartungsgemäß zackig.
- Elies: Außenrandlänge 2349,51 → 1953,06 m, Außenstützpunkte 7242 → 5001,
  Feldfläche 8617,92 → 8325,94 m². Feldzahl 10 → 11 durch getrennten schmalen
  Anschluss. Geometrien gültig; andere ausgegebene Kategorien unverändert.
- Größere Radien können reale schmale Randformen verändern oder Verbindungen
  trennen. Das ist eine überprüfbare Formglättung, keine Feldgrenzvermessung.
- Rodia abschließend: Außenrandlänge 8269,45 → 6892,11 m, Außenstützpunkte
  23729 → 17411, Feldfläche 19261,44 → 18448,39 m². Feldzahl 67 → 68.
  Andere ausgegebene Kategorien unverändert, alle vier Läufe gültig.
- UI-Hinweis ergänzt: Regleränderungen erfordern „Ganze Karte analysieren“;
  geladene/übernommene Polygone ändern sich nicht automatisch. Abschließend
  51 Tests bestanden und `git diff --check` erfolgreich.

## Helle Innenbereiche – autorisierter Umbau umgesetzt

Nutzerauftrag nach weiterem Screenshotvergleich: helle Innenbereiche anhand
räumlichen Zusammenhangs neu bewerten statt ausschließlich stärker glätten.

- Neue Methode `rgb-interiors-v6`, zusätzliche standardmäßig aktive Checkbox
  „Helle Innenbereiche räumlich prüfen und zusammenfassen“.
- `resolve_bright_interiors` prüft helle Komponenten auf Arbeitsflächenumgebung,
  Innenlage, Größe/Länge und Anschluss an größere Wegzüge. Geschlossene kompakte
  Flecken bleiben möglich; kurze unterbrochene Streifen können bei mindestens
  70 % Arbeitsflächenumgebung auch ohne geschlossene Hülle einbezogen werden.
- Durchgehende längliche oder randberührende größere Wegzüge, direkte Anschlüsse,
  Maskenränder und helle Gebäudenähe bleiben ausgespart. Regeln/Schwellen stehen
  in `docs/detection.md`. Keine manuelle Referenz als Erkennungseingabe verwendet.
- Neue Zuordnungen werden vor Formglättung vereinigt. Obstflächen-Innenlöcher
  bleiben `orchard`. Zurückbehaltene Wege werden nicht nachträglich von der alten
  kompakten-Innenflecken-Regel übernommen. Abschalten stellt v5-Regel wieder her.
- `DetectionResult.review_overlays` trägt separate orange Vorschaugeometrien,
  begrenzt auf tatsächlich ausgegebene Arbeitsflächen. UI entfernt die Prüfschicht
  beim Verwerfen/Übernehmen/Projektwechsel. Keine zusätzlichen Kartenobjekte.
  Laden eines gespeicherten Projekts rekonstruiert die orange Prüfschicht nicht;
  für diese eine neue Analyse starten oder den PNG-Vergleich öffnen.
- Neue Vergleichsprojekte: `workspace/interior_check/elies_rgb.project.json` und
  `rodia_rgb.project.json`, jeweils Glättungsradius 2 m und Schattenoption aus.
  `*-comparison.png`: v5 links, v6 rechts, orange neue helle Zuordnungen.
  `*-review.geojson` enthält Prüfschicht im Quell-CRS; `report.json` Vergleichszahlen.
- Elies Wegkandidaten 15 → 8, Feldkandidaten 11 → 11, 256,16 m² neu zugeordnet
  vor Glättung. Rodia Wege 54 → 28, Felder 68 → 62, 603,14 m² neu zugeordnet.
- Größter bisheriger Wegkandidat auf beiden Bildern vollständig erhalten,
  Baum-/Gebäudegeometrien unverändert. Alle Geometrien gültig, Klassenüberlappung
  unter 0,0001 m². Manuelle Objekte bleiben durch bestehende Übernahmefunktion
  geschützt (Regressionstests mit aktivierter neuer Default-Einstellung bestanden).
- Elies Referenzabdeckung große Fläche 86,88 → 86,82 %, kleine 64,34 → 77,94 %;
  keine allgemeine Genauigkeitsbehauptung. Beide PNGs vom Agenten visuell geprüft:
  weniger helle Einzelobjekte, weiterhin starke Reihen-/Schattenfragmentierung.
- 55 Tests bestanden; `git diff --check` erfolgreich. Neuer UI-Ablauf inklusive
  Innenfleck serverseitig geprüft, interaktiver Browsertest der orangefarbenen
  Vorschau noch offen. Schattenlogik blieb unverändert.

## Strukturerkennung auf ausdrücklichen Nutzerauftrag umgesetzt

Nutzer bestätigt zusammengehörige linke Streifenflächen und fragt nach analogen
regelmäßigen Baumabständen; Auftrag: Strukturerkennung implementieren, Nutzer prüft.

- Methode `rgb-rows-v7`, neues Modul `detection/rows.py`. Lokale Fourierprüfung
  auf wiederkehrende Pflanzstreifen mit Richtung und metrischem Abstand,
  Verbindung kompatibler Nachbarfenster über Farb-/Helligkeitsunterschiede.
- Mindestens vier starke Musterfenster bilden Ausgang; kompatible schwächere
  Muster dürfen fortsetzen. Fensterkern benötigt eigenen Kontrast. Keine
  beliebige konvexe Hülle über die ganze Karte; nur lokale Zusammenfassung.
- Neue standardmäßig aktive Checkbox „Regelmäßige Pflanzstreifen anhand Richtung
  und Abstand erkennen“. Bestehende zweidimensionale Baumkronen-Rasterregel bleibt
  unverändert über eigene Obstflächen-Checkbox aktiv. Schattenlogik unverändert.
- Strukturflächen können auch unklassifizierte Bodenbereiche ergänzen. Helle
  Komponenten werden nur bei überwiegendem Reihenbeleg teilweise umgeordnet;
  bei weniger als 50 % Überdeckung bleibt die ganze helle Komponente ausgespart.
  Baum-/Gebäude-/Obstflächen geschützt; neue Bereiche mit bestehenden Feldern
  vereinigt und anschließend geglättet. Befahrbarkeit weiter unbekannt.
- Orange Prüfschicht umfasst neue Innenbereiche UND strukturell ergänzte Flächen.
  UI erklärt dies und meldet Anzahl Strukturregionen sowie ergänzte Fläche.
- 62 Tests bestanden, einschließlich gedrehter Reihen, Farbwechsel, Rauschen,
  gleichmäßiger Flächen, einzelner gerader/diagonaler Kanten, Masken, Einheiten,
  Straßenschutz und vollständiger Pipeline mit Ein-/Ausschalten und Prüfschicht.
- Neue Vergleichsprojekte: `workspace/row_check/elies_rgb.project.json` und
  `rodia_rgb.project.json` (Radius 2 m, Schattenoption aus), dazu PNG-Vergleiche,
  Prüfschicht-GeoJSONs im Quell-CRS und `report.json`. Beide PNGs visuell geprüft;
  orange in PNGs halbtransparent. Interaktiver Browsertest bleibt offen.
- Elies: Feldpolygone 11 → 9, Wegkandidaten 8 → 7; 12 Strukturregionen,
  1889,26 m² zusätzliche Arbeitsfläche vor Abschlussglättung. Die große linke
  helle Streifenfläche wird wesentlich einbezogen. Asphaltstraßenkomponente
  vollständig erhalten. Baum-/Gebäudegeometrien unverändert.
- Rodia: Feldpolygone 62 → 8, Wegkandidaten 28 → 55; 32 Strukturregionen,
  15966,25 m² neue Arbeitsfläche vor Abschlussglättung. Wegzahl steigt, weil
  bisher große helle Komponenten in strukturierte Arbeitsfläche und mehrere
  helle Restpolygone zerlegt werden. Größter alter Rodia-Wegkandidat verliert
  4016,37 m²; alte Farbklasse ist keine fachliche Wegreferenz. Tatsächliche
  Feldwege und versehentlich verbundene Schläge muss Nutzer besonders prüfen.
- Alle Ausgabegeometrien gültig, Feldüberlappungen numerisch unter 0,0001 m².
  Baum-/Gebäudegeometrien auch Rodia unverändert. Referenzabdeckung Elies große
  Arbeitsfläche 86,82 → 87,07 %, kleine 77,94 → 77,95 %; keine allgemeine
  Genauigkeitsbehauptung und keine unabhängige Texturvalidierung vorhanden.
- Details/Schwellen in `docs/detection.md`. Originale und manuelle Referenz nicht
  überschrieben. Geladene Projekte zeigen keine rekonstruierte orange Prüfschicht;
  dafür GeoTIFF frisch analysieren. Neue Klassifizierung beim Nutzer prüfen lassen.

## Strukturgruppen getrennt erhalten – umgesetzt

Nutzer bemängelt eine große grüne Arbeitsfläche trotz unterschiedlicher Muster
und Grüntöne. Plan erklärt und ausdrücklich beauftragt: Gruppen nach Richtung,
Abstand und Farbe bilden, getrennt bis zur Ausgabe erhalten, farbig prüfen.

- Methode `rgb-groups-v8`, neues Modul `detection/groups.py`.
- `row_regions(..., with_groups=True)` liefert neben Geometrien Richtung,
  medianen Abstand und mediane RGB-Farbe je Region. Alte Zweiwert-API bleibt
  für vorhandene Aufrufer unverändert. Keine neuen Abhängigkeiten.
- Ähnliche nahe Regionen gruppieren (15°, Abstandverhältnis 1,35, normalisierte
  Farbdistanz 0,1, Helligkeitsunterschied 0,18, räumlicher Abstand 12 m).
  Ankermerkmale der großen Ausgangsregion bleiben konstant gegen Kettendrift.
- Mindestens 250 m² Strukturbeleg für neue Gruppen-Grenzen. Die zuvor erkannte
  Feldmaske wird abschließend gemeinsam partitioniert: nächster Gruppenbeleg,
  maximal 6 m Fortsetzung, übrige Vegetation separate Gruppe. Raster ungefähr
  1 m, maximal 512 Zellen je Achse. Danach keine globale Vereinigung mehr.
- Kleine überwiegend umschlossene Inseln mit ungefähr doppeltem Abstand können
  Fourierharmonische derselben Reihen sein; nur bis 12 % einer großen Nachbar-
  gruppenfläche, 60 % gemeinsame Grenze, ähnliche Richtung/Farbe. Große Felder
  werden so nicht zusammengeführt. Grenzreste unter 25 m² zu längster direkt
  angrenzender Gruppe; isolierte ursprüngliche Flächen bleiben erhalten.
- Eigenschaften `structure_group`, `structure_type`, `structure_color` sowie
  `row_direction_deg`/`row_spacing_m` bleiben beim Speichern und Undo/Redo erhalten.
  IDs sind laufbezogen, keine fachlichen Schlag-IDs. Vegetation ohne sicheren
  Reihenbeleg ist ausdrücklich keine bestätigte Wiese.
- Neue standardmäßig aktive Checkbox „Arbeitsflächen nach Strukturgruppen getrennt
  halten“. Farben in Vorschau UND gespeicherter Karte; Grün = übrige Vegetation,
  Braun = Obstfläche, weitere Farben = Reihengruppen. Auswahl nennt Gruppen-ID.
  Orange Ergänzungsmarkierung bei Gruppentrennung ausgeblendet, sonst wie bisher.
  Auf Hindernis umklassifizierte Objekte verwenden wieder die Kategorie-Farbe.
- Vergleichsprojekte: `workspace/group_check/elies_rgb.project.json` und
  `rodia_rgb.project.json`, PNGs daneben, Bericht `report.json`.
  Beide PNGs visuell geprüft. Parameter Radius 2 m, Schatten aus.
- Elies: 4 Gruppen, linke Streifenfläche zusammenhängend blau (3399,79 m²),
  obere Reihenfläche türkis (1315,98 m²), Obstfläche braun (2850,52 m²), übrige
  Vegetation grün. Feldpolygone 9 → 13 plus Obstfläche; die zusätzliche Zahl
  folgt teilweise beabsichtigter Aufteilung, übrige Vegetation in 11 Teilen.
- Rodia: 8 Gruppen, Feldpolygone 8 → 28; noch kleinere Teilgruppen und grobe
  Übergänge. Vor allem Grenzen zwischen Reihentypen und restlicher Vegetation
  fachlich prüfen, keine Genauigkeitsbehauptung.
- Gesamte Arbeitsflächenmaske gegenüber v7 unverändert (Elies exakt, Rodia
  Differenz ca. 6e-9 m²). Wege, Gebäude-, Baum- und Obstflächengeometrien unverändert.
  Alle Geometrien gültig, keine relevanten Gruppenüberlappungen, kein Limit erreicht.
- 70 Tests bestanden, einschließlich Richtung/Abstand/Farbe, Schatten-Farbwechsel,
  kleiner harmonischer Inseln, metrischer Einheiten, Maskenerhalt ohne Überlappung,
  Gruppeneigenschaften bei Speichern/Öffnen und Undo/Redo. Interaktiver UI-Test offen.
- Bestehende bereits übernommene große Polygone haben weiter Vorrang; zum Prüfen
  neues Vergleichsprojekt öffnen oder GeoTIFF frisch analysieren. Originalprojekte
  und Referenz nicht überschrieben. Schattenbehandlung nicht verändert.
