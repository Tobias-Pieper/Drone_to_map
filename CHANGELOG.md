# Änderungsverlauf

Dieses Dokument beschreibt fachliche Änderungen. Die vollständige technische
Historie wird ab dem ersten Repository-Commit in Git geführt.

## Unveröffentlicht

### Automatische Vorschläge: klassische Baseline

- Austauschbare Backend-Schnittstelle und experimentelle RGB-Regeln für Feld-,
  Weg-, Baum- und Dachkandidaten, ohne vortrainiertes KI-Modell.
- Begrenzte Analyseauflösung, Mindestfläche, Maskierung und Polygonlimit.
- Berechnung im Hintergrundprozess, separate Vorschau, Übernehmen/Verwerfen.
- Bestehende Geometrien behalten Vorrang; Übernahme ist per Undo rückgängig machbar.
- Unsicherheitskennzeichnung und reproduzierbare Laufmetadaten statt Confidence.
- Tests für Baseline und Datenintegrität sowie serverseitigen UI-Ablauf.


### Ausgangsstand vor automatischer Erkennung

- Lokale NiceGUI-/Leaflet-Oberfläche und separater Python-Geodatenkern.
- Georeferenzierte RGB-/RGBA-GeoTIFFs öffnen und lokal darstellen.
- Bildübersicht mit Auflösung, gültiger Bildfläche, Bildmaßen und CRS.
- Polygone zeichnen, auswählen, umklassifizieren und löschen.
- Stützpunkte verschieben und auf Kanten ergänzen.
- Übersicht aller Polygone nach Kategorie.
- Undo/Redo und atomare Projektspeicherung einschließlich Bearbeitungshistorie.
- Einstellbare metrische Sicherheitsabstände und separate Sperrzonen.
- Gesamtkarte freigeben; Bearbeitungen widerrufen die Freigabe.
- Neutraler WGS84-GeoJSON-Export für Objekte und Sperrzonen.
- 24 automatisierte Tests; interaktive Grundfunktionen unter Linux durch Nutzer geprüft.

### Noch offen

- Automatische Erkennung und Modellvergleich.
- Teilbereichsanalyse, quantitative Evaluation und Kartenbildexport.
- Abgestimmtes Feldfreund-Navigationsschema.
- Vollständige Offline- und macOS-Validierung.

Frühere Entwicklungsschritte sind noch keine separaten Git-Commits und werden
nicht nachträglich als solche dargestellt.

### Zusammenhängende Obstflächen und Strukturen

- Regelmäßige zweidimensionale Baumreihen werden als Arbeitsflächenkandidaten
  (`orchard`) erkannt; Einzelreihen reichen für diese Zuordnung nicht.
- Größere zusammenhängende Vorschläge durch einstellbare Fragmentverbindung.
- Bestehende andere Klassen, Masken und Originalprojekte bleiben geschützt.
- Neue Tests für gedrehte Baumraster, Einzelreihen, unregelmäßige Gruppen und Grenzen.

### Räumliche Zusammenfassung von Arbeitsflächen

- Neue Methode `rgb-context-v3`: zusätzliche einstellbare Flächenzusammenfassung
  (0–5 m, Default 3 m), um nahe Feldteile trotz Bildvariation zu verbinden.
- Kleine kompakte helle Innenflecken können in Feldvorschläge eingehen;
  langgezogene Wege, Baum-/Gebäudekandidaten und Rastermaske bleiben ausgespart.
- Kontextparameter und Zahl einbezogener heller Flecken in Laufmetadaten.
- Regressionstests für Hindernisse, Wege, Masken, metrische Einheiten und Abschalten.

### Konturglättung und Schattenhypothesen

- `rgb-appearance-v4`: metrische Vereinfachung der Feldaußenkonturen (0–2 m,
  Default 0,5 m), mit maximal 5 % symmetrischer Flächenänderung je Ausgangsteil.
- Optionale Schattenhypothesen anhand lokaler normalisierter RGB-Farbe und
  Helligkeitsstreuung, standardmäßig aus; kompakte Kronenkandidaten geschützt.
- Originalklassifikation bleibt Grundlage der Obstflächen-Strukturerkennung.
- Parameter, umklassifizierte Pixelfläche und Prüfhinweis im Analyseergebnis.

### Wirksame Formglättung der Feldaußenränder

- `rgb-boundaries-v5`: geometrisches Schließen und Öffnen gleicht schmale
  Einbuchtungen und Ausläufer aus; reine Stützpunktvereinfachung ersetzt.
- Gewählter Radius wird direkt angewendet, ohne stille 5-%-Rückstufung.
- Kleine eigenständige Felder, Innenlöcher und andere ausgegebene Klassen geschützt;
  unterhalb der Mindestfläche liegende Fragmente vor Glättung herausgefiltert.
- UI nennt den Parameter jetzt „Flächenränder glätten (Radius in m; 0 = aus)“.
- Schattenbehandlung bleibt unverändert. 51 Tests bestanden.

### Räumliche Neubewertung heller Innenbereiche

- `rgb-interiors-v6`: helle Komponenten anhand benachbarter Arbeitsflächen,
  Innenlage und Zusammenhang mit größeren Wegzügen bewerten.
- Kurze unterbrochene Innenstreifen können trotz fehlender geschlossener
  Kontur übernommen werden; größere Wegzüge, direkte Anschlüsse und
  Gebäudezufahrtskandidaten bleiben ausgespart.
- Separate Checkbox für Vergleich; orange Prüfschicht in der Analysevorschau,
  ohne zusätzliche Kartenobjekte, mit Bereinigung beim Verwerfen/Übernehmen.
- Metrische Regressionstests für Straße, Anschluss, Gebäudezugang, Obstflächen,
  fehlende Innenlage und unterbrochene Streifen; UI-Simulation mit Innenfleck.

### Strukturerkennung für wiederkehrende Pflanzreihen

- `rgb-rows-v7`: lokale periodische Muster anhand Richtung und metrischem
  Abstand aus RGB erkennen, passende Nachbarbereiche über Farbwechsel verbinden.
- Starke Muster als Ausgang, kompatible schwächere Muster als Fortsetzung;
  Textur nur am Fensterrand genügt nicht. Separate Checkbox zum Vergleich.
- Reihenbeleg kann helle und unklassifizierte Zwischenräume als Arbeitsfläche
  ergänzen; Gebäude-/Baum-/Obstflächen und nicht überwiegend strukturierte
  helle Wegkomponenten bleiben ausgespart.
- Bestehende Baumraster-Erkennung bleibt separat aktiv. Neue Arbeitsbereiche
  in orangefarbener Prüfschicht; Parameter und strukturelle Flächenmetadaten.
- 62 Tests bestanden, frische Vergleichsprojekte unter `workspace/row_check/`.

### Arbeitsflächen nach Strukturgruppen partitionieren

- `rgb-groups-v8`: Richtung, Abstand und Farbe der Reihenregionen bleiben bis
  zur Ausgabe erhalten. Passende nahe Regionen gruppieren, unterschiedliche
  Reihenmuster, Vegetation ohne sicheren Reihenbeleg und Obstflächen trennen.
- Gemeinsame Partition erhält die erkannte Feldmaske ohne doppelte Flächen;
  keine nachträgliche Vereinigung unterschiedlicher Gruppen.
- Mindestbeleg für neue Grenzen, begrenzte Bereinigung kleiner harmonischer
  Inseln und kleiner Grenzreste gegen neue Kleinteiligkeit.
- Separate Checkbox, Gruppenfarben in Vorschau und gespeicherter Karte sowie
  Gruppenkennung in Auswahl. Orange Prüfschicht bei Gruppentrennung ausgeblendet.
- 70 Tests bestanden, einschließlich Gruppenpersistenz und Undo/Redo.
