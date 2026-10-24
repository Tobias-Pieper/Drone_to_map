# Änderungsverlauf

Dieses Dokument beschreibt fachliche Änderungen. Die vollständige technische
Historie wird ab dem ersten Repository-Commit in Git geführt.

## Unveröffentlicht

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
