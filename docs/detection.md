# Automatische Polygonvorschläge: klassische Baseline

## Bedienung

1. GeoTIFF oder gespeichertes Projekt öffnen.
2. Unter der Karte „Ganze Karte analysieren“ klicken.
3. Türkis gestrichelte Vorschau prüfen. Die Zählung zeigt Vorschläge je Hauptkategorie.
4. „Vorschläge übernehmen“ ergänzt die Ergebnisse im aktuellen Projekt.
5. Einzelne Vorschläge auswählen, Geometrie/Klasse korrigieren oder löschen.
6. „Projekt speichern“ sichert die übernommenen Vorschläge und ihre Herkunft.

„Vorschau verwerfen“ ändert die Projektgeometrien nicht. Eine Vorschau allein wird
nicht gespeichert. Die Übernahme bildet genau einen Undo-Schritt und widerruft
eine vorhandene Freigabe. Bestehende Polygone haben Vorrang: neue Vorschläge
werden um ihre Flächen herum ausgeschnitten. Bestehende Konturen und Attribute
bleiben erhalten, abgesehen von der notwendigen Invalidierung des Freigabestatus.
Dies kann Vorschläge abschneiden oder vollständig ausschließen; die angezeigte
Vorschau zeigt deshalb noch nicht zwingend die endgültige Kontur nach Übernahme.
Überlappende, manuell gezeichnete Referenzen werden ebenfalls ausgespart.

Ein noch vorhandener identischer Analyselauf kann nicht erneut übernommen werden.
Dazu dienen deterministische Lauf- und Objekt-IDs. Nach Löschen sämtlicher
Objekte dieses Laufs ist eine erneute Übernahme möglich. Änderungen der
Analyseparameter erzeugen einen neuen Lauf; vorhandene Flächen behalten Vorrang.
Ändert sich das Projekt während der Berechnung oder nach Erzeugung der Vorschau,
wird der veraltete Stand nicht übernommen. Vollständig verdeckte Vorschläge
führen weder zu leeren Objekten noch zu einem unnötigen Undo-Schritt.

## Methode und reversible Defaults

`Detector` definiert die UI-unabhängige Backend-Schnittstelle. `ColorBaseline`
ist die erste Implementierung. Keine zusätzlichen Pakete, Cloud-Dienste,
Modellgewichte oder eigenes Training sind notwendig. Es handelt sich um
klassische Bildverarbeitung, noch nicht um den geforderten KI-Hybridansatz.

Die Analyse verwendet höchstens 1600 Pixel an der längsten Seite (einstellbar
800–2048) und zunächst 4 m² Mindestfläche. Das Raster wird direkt beim Lesen
verkleinert. Diese Baseline ist bewusst eine begrenzte Übersichtsanalyse, noch
keine kachelbasierte Inferenz in Originalauflösung. Kleine/schmale Objekte können
verschwinden. Originalraster werden nicht verändert.

Unterstützt werden zunächst 8-Bit-RGB-Bänder 1–3 mit expliziter RGB-Zuordnung und
projiziertem CRS, einschließlich korrekter Umrechnung der CRS-Einheiten in Meter.
Andere Bandbelegungen, Datentypen und geografische CRS werden mit einem Hinweis
abgewiesen. Eine Eingabedatei muss zur beim Öffnen gespeicherten SHA256 passen.
NoData-/Alpha-Masken werden in Analysauflösung berücksichtigt.

Nach einem 5×5-Medianfilter gelten feste Regeln in RGB-Werten von 0 bis 1:

- Grüne Vegetation: G > 1,08 R, G > 1,12 B, G > 0,12 → Arbeitsflächenkandidat `field`.
- Helle Fläche: mittlere Helligkeit > 0,40 und Kanalspreizung < 0,16,
  keine Vegetation → Wegkandidat `path`.
- Rötliche Fläche: R > 1,25 G, R > 1,3 B, R > 0,30 → Gebäudekandidat `building`.
- Dunkle Vegetation: Vegetationsregel und mittlere Helligkeit < 0,25,
  G > 1,18 R → Baumkandidat `tree` (ersetzt dort `field`).

Kleine zusammenhängende Regionen werden je Klasse gesiebt. Danach entstehen
Polygone mit der korrekt skalierten affinen Rastertransformation. Vereinfachung
ist topologieerhaltend und bleibt durch Rückschnitt innerhalb der klassifizierten
Fläche. Höchstens 300 größte Vorschläge werden ausgegeben; ausgelassene Vorschläge
werden gezählt. Die Begrenzung kann besonders viele kleine Hindernisse auslassen!
Nicht klassifizierte Pixel bleiben ohne Polygon und werden nicht als befahrbar
interpretiert. Flächenabdeckung ist damit nicht vollständig.

Alle Vorschläge haben `review_status=auto_detected`, `review_flag=true` und
`traversability=unknown`. Es gibt keine kalibrierte Confidence und keinen
künstlichen Prozentwert. Der jeweilige Prüfhinweis erscheint bei Auswahl.
Datei-SHA256, Methoden-/Softwareversionen, Parameter, Analysegröße, Quell-CRS,
Lauf-ID und Zahl ausgelassener Kandidaten werden als Objektmetadaten gespeichert
und mit dem GeoJSON exportiert. Noch nicht übernommene Vorschauen liegen nur im
Arbeitsspeicher und verschwinden beim Neuladen der Seite.

## Grenzen und bisherige Prüfung

Die Regeln verwechseln unter anderem Baumkronen mit Nutzvegetation, Schatten mit
Bäumen, Boden mit Dächern und helle Bodenflächen mit Wegen. Zäune, Gräben, Wasser,
Agri-PV und Ladestationen werden nicht zuverlässig erkannt. Klassennamen sind
Hypothesen; Konturen und sichtbarer Bildinhalt liefern keine Befahrbarkeitsfreigabe.

Technischer Lauf auf den zwei lokalen TIFFs (Defaults, diese Entwicklungsumgebung):

| Datei | Feldkandidaten | Wegkandidaten | Baumkandidaten | Gebäudekandidaten | Zeit einschließlich Import/Prüfung/Speicherung |
|---|---:|---:|---:|---:|---:|
| elies_rgb.tif | 60 | 41 | 74 | 1 | ca. 6,2 s |
| rodia_rgb.tif | 164 | 126 | 10 | 0 | ca. 5,4 s |

Beim zweiten Bild greift das 300-Polygon-Limit. Das sind keine Qualitätskennzahlen
und keine Laufzeitgarantie. Testausgaben liegen getrennt in
`workspace/detection_check/`; Nutzerprojekte werden dafür nicht überschrieben.

Automatisierte Tests prüfen synthetische Farbfälle, Georeferenzierung,
Transparenzränder, Herkunftsattribute, deterministische IDs, Limits,
Originaldatenerhalt, Überlappungsbehandlung, Undo/Redo und Persistenz.
Eine serverseitige NiceGUI-Benutzersimulation prüft Import, Vorschau, Verwerfen,
Übernehmen und Undo mit der echten Baseline. Die Prozessauslagerung wird darin
ersetzt; tatsächlicher Worker-Start, Leaflet-Rendering, Linux-/macOS-Browser und
Offline-Gesamtdurchlauf müssen praktisch geprüft werden.

## Nächster Schritt zum KI-Hybridansatz

Die Bibliothek kann weitere Backends mit identischer Ergebnisschnittstelle
aufnehmen. Noch kein Modell ist als endgültige Lösung ausgewählt. Vor einer
Gewichtsinstallation sind Modell-/Gewichtslizenz, lokale Bereitstellung und
Hardwarebedarf zu prüfen. SAM allein würde keine Farmklassen liefern.

Für den sinnvollen Vergleich benötigen wir einen separaten, manuell annotierten
Referenzstand: repräsentative Arbeitsflächen, Wege sowie Bäume/Gebäude auf beiden
Bildern und einen klar definierten, vollständig annotierten Auswertungsbereich.
Unmarkierte Flächen dürfen nicht ungeprüft als negative Beispiele gelten.
Dann können wir IoU und flächenbezogene Precision/Recall messen und geeignete
vortrainierte Kandidaten vergleichen. Absolute Lagegenauigkeit ist separat zu
untersuchen. Teilbereichsanalyse und Evaluations-UI stehen noch aus.

API-Quellen:
- https://rasterio.readthedocs.io/en/stable/topics/features.html
- https://rasterio.readthedocs.io/en/stable/api/rasterio.features.html
- https://github.com/zauberzeug/nicegui/blob/main/nicegui/llms.md

## Strukturregel für Obstflächen (aktuelle Erweiterung)

Fachliche Festlegung: Regelmäßig angeordnete Bäume mit Zwischenräumen bilden
zusammen eine Arbeitsfläche (`work_area`, Unterkategorie `orchard`). Hecken,
Einzelbäume und unstrukturierte Gehölzflächen gelten als Hinderniskandidaten.
Die Ausweisung einer Obstfläche bestätigt weder freie Baumzwischenräume noch
Befahrbarkeit der Baumstämme. Befahrbarkeit bleibt `unknown`.

Die Methode heißt nun `rgb-structure-v2`. Zuerst werden isolierte dunkle
Vegetationskomponenten als vorläufige Baumkronen extrahiert (0,7–55 m², kein
stark langgestreckter Grundriss). Die Strukturheuristik sucht räumlich verbundene
Gruppen mit mindestens neun Kronen, wiederkehrenden Abständen in zwei ungefähr
rechtwinkligen Richtungen und belegter zweidimensionaler Anordnung. Der Suchbereich
für Nachbarabstände liegt vorläufig bei 2–12 m. Eine einzelne Reihe reicht nicht.
Die Winkelbestimmung berücksichtigt gedrehte Anlagen. Über 1500 Kronenkandidaten
wird diese begrenzte Heuristik aus Speichergründen übersprungen.

Die Hülle einer erkannten Anordnung wird um 40 % des kleineren geschätzten
Rasterabstands erweitert und als zusammenhängende Obstfläche vorgeschlagen.
Gebäude-/Wegkandidaten und ungültige Bildpixel werden ausgespart. Innerhalb einer
Obstfläche treten ihre Baumkronen nicht zusätzlich als einzelne Baumhindernisse
auf. Die Regel kann bewusst per Checkbox abgeschaltet werden.

„Fragmente verbinden (m)“ steuert einen geometrischen Schließungsradius,
vorläufig 1 m (0 schaltet ihn aus). Dadurch können innerhalb einer Kategorie
kleine Lücken geschlossen werden; kleine Löcher bis 20 m² werden gefüllt.
Vorhandene andere Klassen und ungültige Bildflächen bleiben ausgespart.
Neu entstandene Überlappungen werden in Reihenfolge Obstfläche, Gebäude, Weg,
Baum, sonstige Arbeitsfläche aufgelöst. Einstellungen und Kandidatenzahlen werden
in den Laufmetadaten gespeichert. Keine Referenzgeometrie wird als Eingabe der
Erkennung genutzt und kein eigenes Modelltraining durchgeführt.

Diese allgemeinen Schwellen sind erste überprüfbare Defaults, keine bereits
validierte Semantik. Unregelmäßige Obstflächen, perspektivisch/verdeckt erkennbare
Kronen, kleine Anlagen, stark unterschiedliche Baumabstände und ähnlich angelegte
unproduktive Baumbestände können falsch erkannt werden. Die äußere Feldgrenze
ist aus der Kronenanordnung nur angenähert. Die Referenz auf diesem einen Bild
dient der Entwicklung und ist kein unabhängiger Testdatensatz. Weitere Bilder
und vortrainierte Modelle bleiben für die eigentliche KI-Pipeline erforderlich.

Ein Vergleich sollte über das rohe GeoTIFF in einem neuen Entwurfsprojekt laufen:
Beim Laden der manuell gezeichneten Referenzdatei behalten deren vorhandene
Polygone weiterhin Vorrang vor neuen Vorschlägen. Die Referenz zuerst separat
sichern und das Vergleichsprojekt unter anderem Dateinamen speichern.

## Räumliche Zusammenfassung von Arbeitsflächen (rgb-context-v3)

„Arbeitsflächen zusammenfassen (m; 0 = aus)“ steuert eine zusätzliche
Kontextstufe nach der bisherigen Fragmentverbindung. Standardradius: 3 m,
Bereich: 0–5 m. Geometrisches Schließen verbindet nahe Feldkandidaten;
begrenzte Innenlöcher bis 100 m² werden als mögliche Bild-/Vegetationsvariation
gefüllt. Der Radius ist kein maximaler Lückenabstand: beidseitige Erweiterung
kann Lücken bis ungefähr zum doppelten Radius schließen.

Kleine helle Wegkandidaten bis 100 m² dürfen in diese Hülle eingehen, wenn sie
vollständig mit mindestens 25 cm Rand darin liegen und ihr gedrehtes
Begrenzungsrechteck ein Seitenverhältnis von höchstens 3 hat. Langgezogene
Wegkandidaten, helle Randflächen, Baum-, Gebäude- und Obstflächenkandidaten
werden ausgespart. Ungültige Rasterbereiche bleiben ausgeschlossen.
Die Zusammenfassung nutzt ausschließlich die automatisch erzeugten Kandidaten,
keine manuellen Referenzgeometrien. Herkunftsmetadaten enthalten den Radius,
die Kandidatenzahl vor dieser Stufe und die Zahl einbezogener heller Flecken.

Auch ein kompakter heller Fleck kann ein echter Weg oder Platz sein. Dunkle
Flecken bleiben als Baumkandidaten bestehen, weil Schatten und tatsächliche
Gehölze mit diesen RGB-Regeln nicht zuverlässig unterscheidbar sind.
Diese Stufe löst deshalb nicht jede Fragmentierung. Kleine Objekte, die bereits
bei der Rasterklassifikation oder Mindestflächenfilterung fehlen, werden durch
sie nicht geschützt. Vorschläge bleiben prüfpflichtig und Befahrbarkeit unbekannt.

Zum Vergleich das GeoTIFF frisch öffnen, die Vorschau prüfen und unter neuem
Projektnamen speichern. Radius 0 deaktiviert nur diese neue Kontextstufe;
„Fragmente verbinden“ und die Obstflächenerkennung haben eigene Einstellungen.

Prüfung vom 1. November 2026: 40 Tests bestanden. Vergleich gegen gespeicherte
v2-Ausgaben mit Defaults:

| Bild | Vorschläge vorher → nachher | Feldpolygone vorher → nachher |
|---|---:|---:|
| elies_rgb.tif | 72 → 60 | 17 → 10 |
| rodia_rgb.tif | 234 → 141 | 131 → 67 |

Auf Elies steigt die Abdeckung der beiden manuell eingezeichneten Arbeitsflächen
von 86,72 auf 88,79 % bzw. 57,98 auf 65,51 %. Zusätzliche Abdeckung außerhalb der
Referenzen ist damit nicht bewertet. Baum-, Gebäude- und Obstflächengeometrien
beider Bilder bleiben gegenüber den gespeicherten v2-Ausgaben unverändert.
Vergleichsprojekte und Bericht: `workspace/context_check/`. Visuelle Prüfung im
Browser steht noch aus.

## Konturglättung und experimentelle Schattenbehandlung (historischer Stand v4)

Die reine Konturvereinfachung und ihre 5-%-Bremse wurden durch v5 ersetzt
(siehe nächsten Abschnitt). Die Schattenoption bleibt unverändert.

„Konturen glätten (m; 0 = aus)“ vereinfacht die Außenkonturen der Feldvorschläge
mit einer metrischen Toleranz von standardmäßig 0,5 m (maximal 2 m). Echte große
Ecken bleiben durch die topologieerhaltende Vereinfachung erhalten. Innenlöcher
werden nicht geglättet, andere ausgegebene Klassen und die gültige Rastermaske
werden ausgespart. Pro Ausgangspolygon darf die symmetrische Flächenänderung
höchstens 5 % betragen; andernfalls wird die Toleranz bis zu viermal halbiert
oder die ursprüngliche Kontur beibehalten. Das ist keine geometrische Begradigung
aller Feldgrenzen und keine Annahme, dass jede Fläche rechteckig sein muss.
Die Glättung betrifft neu berechnete Vorschläge, keine manuellen Konturen.

„Experimentell: mögliche Schatten in Arbeitsflächen einbeziehen“ ist zunächst
ausgeschaltet. Bei Aktivierung werden dunkle Pixel mit der normalisierten
RGB-Farbverteilung benachbarter heller Vegetation verglichen. Ein lokales,
maskengewichtetes Helligkeits-/Texturmaß und ausreichende helle Nachbarschaft
begrenzen die Kandidaten. Kompakte dunkle Komponenten bis 55 m² mit einem
Seitenverhältnis bis 3 bleiben als mögliche Baumkronen geschützt. Die ursprüngliche
Dunkelvegetationskarte bleibt Eingabe der Obstflächen-Strukturerkennung.

Passende Pixel werden versuchsweise als Vegetation statt als Dunkelvegetation
oder unklassifizierter Bereich behandelt. Das Ergebnis ist eine Schattenhypothese,
keine zuverlässige Baum-/Schattentrennung: farbähnliche Gehölze können einbezogen
werden, kompakte oder farbverschobene Schatten können fehlen. Deshalb ist diese
Option separat abschaltbar; Arbeitsflächen bleiben prüfpflichtig und Befahrbarkeit
unbekannt. Herkunftsmetadaten speichern beide Parameter und die umklassifizierte
Pixelfläche unter `shadow_hypothesis_area_m2` (vor Polygonfilterung/Obstflächen).
Der Prüfhinweis weist bei einem Lauf mit Schattenhypothesen darauf hin.

Technisch: normalisierte RGB-Kanäle, 2-m-Gauß-Nachbarschaft (1–50 Analysepixel
Radius), mindestens 15 % helle Feldstützung, höchstens 0,045 Kanalabweichung,
relative lokale Helligkeitsstreuung unter 0,5. Helligkeitsbereich 0,03–0,25.
Diese Schwellen sind provisorisch und nicht mit unabhängigen Schattenreferenzen
validiert. Keine neuen Pakete oder Modellgewichte erforderlich.

Prüfung dieser Erweiterung: 48 Tests bestanden. Vergleichsausgaben getrennt unter
`workspace/appearance_check/`; `*-smooth.project.json` nutzt nur Glättung,
`*-shadows.project.json` zusätzlich die experimentelle Schattenoption.

| Bild | Feldaußenstützpunkte vorher | Nur Glättung | Feldfläche vorher → nur Glättung |
|---|---:|---:|---:|
| Elies | 7242 | 6524 | 8617,92 → 8604,38 m² |
| Rodia | 23729 | 22230 | 19261,44 → 19178,06 m² |

Die Schattenoption markiert auf Elies 97,83 m² und auf Rodia 174,85 m² Pixel
als mögliche Schatten. Die Bilddiagnose auf Elies zeigt auch Fehlzuordnungen
innerhalb tatsächlicher Gehölze; die Schattenfrage ist damit nicht gelöst.
`elies-shadow-hypotheses.png` markiert die betreffenden Pixel magenta.
Ausgegebene Geometrien sind gültig; numerische Überlappungen von Feldflächen
mit anderen Klassen liegen unter 0,0001 m². Die UI-Erweiterung ist noch nicht
interaktiv im Browser geprüft.

## Flächenränder formen statt nur vereinfachen (rgb-boundaries-v5)

Nutzerrückmeldung anhand von Screenshots: Zwischen 0 und 2 m kaum sichtbarer
Unterschied. Die reine Stützpunktvereinfachung und die 5-%-Bremse aus v4 reichen
für schmale Einbuchtungen und Ausläufer nicht aus.

„Flächenränder glätten (Radius in m; 0 = aus)“ verwendet nun auf den Außenhüllen
der Feldkandidaten ein geometrisches Schließen, gefolgt von Öffnen mit dem
gewählten Radius. Dies füllt schmale Einbuchtungen und entfernt schmale Ausläufer.
Gehrungsverbindungen erhalten große gerade Ecken, ein Gehrungslimit von 2 begrenzt
Spitzen. Anschließend werden Reststützpunkte mit einem Viertel des Radius
vereinfacht. Die stille Reduktion des Radius bei 5 % Flächenänderung entfällt.
Der Standard bleibt 0,5 m, der Einstellbereich 0–2 m.

Innenlöcher und andere ausgegebene Kategorien werden wieder ausgespart, das
Ergebnis an der gültigen Rastermaske beschnitten. Diese geschützten Konturen
können deshalb weiterhin zackig erscheinen. Baum-/Schattenkonturen, Gebäude-,
Weg- und Obstflächenvorschläge werden durch diese Stufe nicht geglättet.
Unterhalb der Mindestfläche liegende Kandidaten werden vor der Glättung entfernt,
damit nicht ausgegebene Kleinstfragmente keine unsichtbaren Randzwänge erzeugen.
Ist eine ganze kleine Außenhülle nach dem Öffnen leer, bleibt ihre Außenhülle
als Ausgang für die Vereinfachung erhalten. Benachbarte Feldteile können sich
nach der Glättung verbinden; schmale Feldverbindungen können getrennt werden.

Der Radius beschreibt die geometrische Bearbeitungsgröße, keine Garantie für
maximale Randverschiebung. Dicht stehende schmale Ausläufer können durch Schließen
auch zusammenwachsen. Reale schmale Randstrukturen können verändert werden;
daher 0 für unveränderte Vorschläge wählen und größere Radien visuell prüfen.
Es erfolgt keine Rechteckannahme oder automatische Grenzvermessung.

Regressionstests prüfen metrische Einheiten, schmale Kerben und Ausläufer,
unterschiedliche Radien, kleine eigenständige Felder, eine große echte Ecke,
Innenlöcher, Hindernisse, Rastermaske und den ausgeschalteten Modus.
51 Tests bestanden. Schattenbehandlung unverändert und standardmäßig aus.

Frische Vergleichsläufe ohne Schattenoption, Radius 0 → 2 m:

| Bild | Feldaußenrandlänge | Außenstützpunkte | Feldfläche |
|---|---:|---:|---:|
| Elies | 2349,51 → 1953,06 m | 7242 → 5001 | 8617,92 → 8325,94 m² |
| Rodia | 8269,45 → 6892,11 m | 23729 → 17411 | 19261,44 → 18448,39 m² |

Andere ausgegebene Kategorien bleiben in beiden Vergleichen geometrisch
unverändert. Die Feldzahl steigt durch das Trennen schmaler Verbindungen von
10 auf 11 bzw. 67 auf 68. Alle Geometrien gültig, numerische Klassenüberlappung
unter 0,0001 m². Außenrandlänge und Stützpunktzahl beschreiben die Formänderung,
keine fachliche Genauigkeit. Projekte, PNG-Vergleiche (links 0, rechts 2) und
Bericht stehen unter `workspace/boundary_check/`. Elies-PNG visuell geprüft;
interaktiver Browsercheck der UI steht aus. Änderungen des Reglers erfordern
einen neuen Analyselauf und verändern keine bereits übernommenen Polygone.

## Helle Innenbereiche räumlich bewerten (rgb-interiors-v6)

Neue, standardmäßig aktivierte Checkbox „Helle Innenbereiche räumlich prüfen und
zusammenfassen“. Die Stufe läuft nach der bisherigen Klassenkonsolidierung,
vor Zusammenfassung und Formglättung der Arbeitsflächen. Abschalten stellt die
bisherige kompakte-Innenflecken-Regel aus v5 wieder her. Kontextabstand 0
schaltet beide räumlichen Zusammenfassungen aus.

Helle Komponenten werden zunächst gemeinsam betrachtet. Ein langer schmaler
Korridor (mindestens 30 m, Seitenverhältnis mindestens 5) oder eine mindestens
15 m lange Komponente bis 0,5 m vom Bildmaskenrand gilt als größerer Wegzug.
Komponenten bis 0,5 m von solchen Wegzügen bleiben ebenfalls erhalten.
Auch helle Bereiche bis 1 m von Gebäudekandidaten sowie bis 0,5 m vom Maskenrand
werden nicht einbezogen. Dies sind konservative räumliche Regeln, keine
bestätigte Wegklassifikation; insbesondere kann auch ein langer Feldstreifen
weiterhin als Wegkandidat erhalten bleiben.

Für übrige Komponenten unter 30 m Länge und höchstens 300 m² Fläche wird der
Zusammenhang mit Feld-/Obstflächen geprüft: mindestens 60 % Arbeitsflächenanteil
in der lokalen Umgebung (Kontextabstand als Ringbreite) plus eine räumliche
Innenlage. Die Innenlage folgt aus einer geschlossenen Arbeitsflächenhülle mit
25 cm Rand oder aus mindestens 70 % Arbeitsflächenanteil in der Umgebung.
Kompakte, vollständig eingeschlossene Flecken bis 100 m² und Seitenverhältnis 3
benötigen keinen zusätzlichen Mindestanteil. Berechnungen erfolgen metrisch,
unabhängig von gedrehter Lage und projizierter CRS-Einheit.

Angenommene Komponenten werden zur Arbeitsfläche hinzugefügt und gleichklassige
Konturen vor der Glättung vereinigt. Eingeschlossene Obstflächen-Löcher behalten
die Unterkategorie `orchard`. Zurückbehaltene Wegkandidaten können nicht danach
von der alten kompakten-Flecken-Regel übernommen werden. Gebäude-/Baumgeometrien
werden durch diese Neubewertung nicht verändert. Manuelle Polygone behalten bei
Übernahme weiterhin Vorrang und werden nicht als Erkennungseingabe verwendet.

Orange Flächen in der Analysevorschau zeigen die neu einbezogenen hellen
Bereiche, begrenzt auf die tatsächlich ausgegebenen Arbeitsflächen. Die orange
Prüfschicht wird beim Verwerfen, Übernehmen oder Wechsel des Projekts entfernt;
sie ist kein weiteres Kartenobjekt und wird nicht als solches exportiert.
Die Vorschau vor Übernahme berücksichtigt noch keinen Rückschnitt an manuelle
Objekte. Gespeicherte Projekte enthalten die Laufmetadaten, nicht die separate
orange Vorschau. Metadaten: `reconsidered_bright_components` und
`reconsidered_bright_area_m2` beschreiben die vor Glättung neu zugeordneten
Komponenten. Befahrbarkeit bleibt unbekannt, alle Vorschläge prüfpflichtig.

Kleine reale Feldwege können räumlich ähnlich aussehen und falsch einbezogen
werden. Die orange Schicht deshalb prüfen; diese Stufe ist gezielt für helle
Innenbereiche und löst weder Schatten noch alle unklassifizierten Lücken.

Vergleich gegen v5 bei gleichem Glättungsradius 2 m, Schattenoption aus:

| Bild | Wegkandidaten vorher → nachher | Feldkandidaten vorher → nachher | Neu zugeordnete helle Fläche vor Glättung |
|---|---:|---:|---:|
| Elies | 15 → 8 | 11 → 11 | 256,16 m² |
| Rodia | 54 → 28 | 68 → 62 | 603,14 m² |

Der jeweils größte bisherige Wegkandidat bleibt vollständig erhalten; Baum- und
Gebäudeflächen sind gegenüber v5 geometrisch unverändert. Alle Ausgabegeometrien
gültig, numerische Feldüberlappungen mit anderen Klassen unter 0,0001 m².
Auf Elies ändert sich die Referenzabdeckung der großen Arbeitsfläche von 86,88
auf 86,82 %, die der kleineren von 64,34 auf 77,94 %; überlappende Vorschläge auf
der kleineren Fläche sinken von fünf auf vier. Referenzabdeckung und weniger
Polygone belegen keine allgemeine Klassifikationsgenauigkeit.

Projekte, Prüfschicht-GeoJSONs im Quell-CRS, Bericht und PNG-Vergleiche liegen unter
`workspace/interior_check/`. Beide PNGs visuell geprüft. Sie zeigen auch die
weiterhin beträchtliche Fragmentierung in Reihen und Schatten: Diese Erweiterung
behandelt gezielt helle Innenbereiche und ist noch keine vollständige flächige
Farmsegmentierung. 55 Tests bestanden, einschließlich serverseitigem UI-Ablauf
mit hellem Innenfleck; interaktiver Browsercheck der orangefarbenen Schicht offen.

## Pflanzstreifen als Strukturhinweis (rgb-rows-v7)

Die Checkbox „Regelmäßige Pflanzstreifen anhand Richtung und Abstand erkennen“
ist standardmäßig aktiv. Die bisherige Prüfung regelmäßiger Baumkronen in zwei
Richtungen bleibt separat über die Obstflächen-Checkbox aktiv. Keine Gewichte,
Referenzpolygone oder zusätzlichen Pakete werden verwendet; dies ist eine
experimentelle klassische Strukturheuristik, kein vortrainiertes KI-Modell.

Lokale Bildfenster von ungefähr 12 m Seitenlänge (32–192 Analysepixel) werden
mit Viertelfenster-Schritt untersucht. Aus Helligkeit und normalisiertem
Grün-Rot-Unterschied werden über eine zweidimensionale Fouriertransformation
Richtung und Wiederholungsabstand geschätzt. Das volle inverse transponierte
Affine-System rechnet Frequenzen in metrische Weltkoordinaten um. Betrachtete
Perioden: 0,6–6 m. Ein Hann-Fenster reduziert künstliche Fensterränder.

Ein akzeptierter Bereich benötigt mindestens vier starke Fenster und Ausdehnung
in beiden Rasterrichtungen. Schwächere Nachbarfenster dürfen einen Bereich
fortsetzen, wenn Richtung (höchstens 20° Unterschied) und Abstand (Verhältnis
höchstens 1,5) kompatibel sind. So können ungleichmäßige Reihen und Farbwechsel
innerhalb einer Anlage zusammengehören. Eine unbegrenzte Hülle über beliebige
Lücken wird nicht gebildet: nur geprüfte benachbarte Kernzellen werden vereinigt,
kleine Lücken lokal geschlossen und anschließend Flächen ab 40 m² berücksichtigt.

Starke Fenster: mindestens 45 % gerichtete und 20 % periodische spektrale Energie,
Spitzenleistung mindestens achtmal Bandmittel. Schwächere Fortsetzungsfenster:
30 %, 12 %, fünfmal Bandmittel. Zusätzlich ist Kontrast im zentralen Kernbereich
nötig; ein Muster nur am Fensterrand reicht nicht. Mindestens 95 % des Fensters
und der gesamte Kern müssen gültige Pixel enthalten. Dies sind provisorische
allgemeine Schwellen, keine kalibrierten Wahrscheinlichkeiten.

Die so unterstützten Bereiche können Arbeitsflächen auch über unklassifizierten
Boden und helle Farbinseln hinweg ergänzen. Gebäude-, Baum- und Obstflächen werden
ausgespart. Bei einem hellen zusammenhängenden Kandidaten ohne Reihenbeleg auf
mindestens der Hälfte seiner Fläche bleibt die ganze Komponente erhalten,
einschließlich angeschlossener Zufahrten. Bei überwiegendem Reihenbeleg werden
nur die strukturell unterstützten Teile als Arbeitsfläche umgeordnet. Übrige
helle Teile können dadurch in mehrere Restkandidaten zerfallen. Feldkonturen
werden danach gemeinsam konsolidiert und mit dem gewählten Radius geglättet.

Orange Vorschau zeigt neue Innenbereiche UND neue Arbeitsfläche aus Reihenbeleg,
begrenzt auf die tatsächlich ausgegebenen Arbeitsflächen. Metadaten enthalten
`row_windows`, `row_supported_cells` (starke und schwächere Kandidatenfenster),
`row_strong_cells`, `row_region_count` und `row_added_area_m2` vor abschließender
Zusammenfassung/Glättung. Diese Bereiche sind keine garantierten Feldgrenzen.
Textur kann auch in Furchen, Fahrspuren und anderen wiederholten Mustern vorkommen;
zusammenhängende benachbarte Schläge können versehentlich verbunden werden.
Schatten-/Baumtrennung bleibt unverändert und unvollständig.

Prüfung: 62 Tests bestanden, darunter gedrehte Reihen, Farb-/Helligkeitswechsel,
gleichmäßige Flächen, Zufallstextur, einzelne gerade/diagonale Helligkeitskanten,
Masken, CRS-Einheiten, Straßenschutz, Hindernisse und kompletter Analysepfad mit
Ein-/Ausschalten sowie Prüfschicht. Kein vollständiger interaktiver Browsertest.

Vergleich gegen v6 bei Radius 2 m und Schattenoption aus:

| Bild | Feldpolygone vorher → nachher | Wegkandidaten vorher → nachher | Neue Arbeitsfläche aus Reihenbeleg vor Glättung |
|---|---:|---:|---:|
| Elies | 11 → 9 | 8 → 7 | 1889,26 m² |
| Rodia | 62 → 8 | 28 → 55 | 15966,25 m² |

Baum-/Gebäudegeometrien beider Bilder unverändert, Elies-Straßenkomponente
vollständig erhalten. Auf Rodia werden große bisherige helle Kandidaten teilweise
als gestreifte Arbeitsfläche interpretiert; deshalb erhöht sich dort die Zahl
der verbleibenden hellen Restpolygone. Der größte alte Rodia-Wegkandidat verliert
4016,37 m² an die neue Zuordnung: die alte Farbklasse ist keine Wegreferenz.
Der Nutzer muss insbesondere tatsächliche Feldwege und Grenzen auf Rodia prüfen.
Alle Ausgabegeometrien gültig, numerische Feldüberlappungen mit anderen Klassen
unter 0,0001 m². Elies-Referenzabdeckung: große Arbeitsfläche 86,82 → 87,07 %,
kleine 77,94 → 77,95 %; keine allgemeine Genauigkeitsmessung.

Projekte, Prüfschichten im Quell-CRS, PNG-Vergleiche und Bericht liegen unter
`workspace/row_check/`. Vergleiche: v6 links, v7 rechts, orange halbtransparent
neu einbezogene Bereiche. Gespeicherte Projekte rekonstruieren die orange
Analyseschicht nicht; dafür GeoTIFF frisch analysieren. Originalprojekte und
manuelle Referenzen wurden nicht überschrieben.

## Getrennte Strukturgruppen erhalten (rgb-groups-v8)

„Arbeitsflächen nach Strukturgruppen getrennt halten“ ist standardmäßig aktiv.
Die bisherige Vereinigung aller Feldvorschläge wird nach der äußeren
Flächenkonsolidierung durch eine gemeinsame Partition ergänzt. Danach werden
verschiedene Gruppen nicht wieder vereinigt. Abschalten erlaubt den Vergleich
mit der bisherigen zusammengefassten Arbeitsfläche.

Jede Reihenregion erhält mittlere Richtung, medianen Reihenabstand und mediane
RGB-Farbe aus ihren gültigen Kernfenstern. Nahe Regionen können derselben Gruppe
zugeordnet werden, wenn ihre Richtung höchstens 15° abweicht, die Abstände ein
Verhältnis bis 1,35 haben, die normalisierte Farbdistanz höchstens 0,1 beträgt
und ihre mittlere Helligkeit höchstens 0,18 auseinanderliegt. Räumlicher Abstand:
höchstens 12 m. Die Merkmale des zuerst aufgenommenen großen Gruppenankers bleiben
Referenz; damit wächst eine Gruppe nicht durch beliebige kleine Farb-/Richtungs-
Änderungen schrittweise in eine ganz andere Struktur hinein.

Für neue Gruppengrenzen werden nur Gruppen mit mindestens 250 m² eigentlichem
Strukturbeleg verwendet. Kleinere Hinweise dürfen weiterhin die Arbeitsflächen-
Erkennung unterstützen, erzeugen aber keine eigene Grenze. Ein einzelner dunkler
Fleck oder ein kleiner Strukturrest soll so keine neue Gruppe bilden.

Die bestehende Feldmaske wird auf einem gemeinsamen Raster von nominal ungefähr
1 m, maximal 512 Zellen je Achse, zum nächstgelegenen Strukturbeleg zugeordnet.
Maximal 6 m Fortsetzung über dessen Grenze sind erlaubt. Nicht unterstützte
Vegetation bleibt eine eigene Gruppe; sie wird ausdrücklich nicht automatisch
als Wiese klassifiziert. Erkannte Obstflächen behalten ihre Kategorie und eigene
Gruppen. Die Gruppengrenzen sind vorläufige, teils rasterförmige Übergänge und
keine vermessenen Schlaggrenzen. Die äußere Formglättung geschieht zuvor; die
anschließende Partition erhält gemeinsame Grenzen ohne Lücken/Überlappungen.

Zwei begrenzte Bereinigungen verhindern neue Kleinteiligkeit: Ein kleiner,
überwiegend umschlossener Reihenbereich kann bei fast doppeltem Reihenabstand
als Frequenzharmonische zur großen Nachbargruppe gehören (höchstens 12 % deren
Fläche, mindestens 60 % gemeinsame Grenze, gleiche Richtung und ähnliche
normalisierte Farbe). Zwei große Flächen werden so nicht verbunden. Reststücke
unter 25 m² werden bei direkter gemeinsamer Grenze der angrenzenden Gruppe mit
der längsten gemeinsamen Grenze zugeordnet. Isolierte ursprüngliche Flächen
bleiben erhalten. Die gesamte zuvor erkannte Arbeitsflächenmaske bleibt bestehen.

Gespeicherte Eigenschaften: `structure_group`, `structure_type`, `structure_color`,
bei Reihen zusätzlich `row_direction_deg` und `row_spacing_m`. Gruppenkennungen
sind laufbezogen; sie sind keine dauerhaften fachlichen Feld-IDs. Mehrere räumlich
getrennte Polygone können zur selben Strukturgruppe gehören.

Vorschau UND gespeicherte Karte zeigen jetzt Gruppenfarben: Grün für Vegetation
ohne sicheren Reihenbeleg, Braun für Obstflächen, weitere Farben für Reihengruppen.
Alle bleiben Kategorie Arbeitsfläche. Die Auswahl nennt auch die Gruppenkennung.
Bei aktiver Gruppentrennung wird die orange Ergänzungsschicht ausgeblendet, damit
sie die Gruppenfarben nicht verdeckt. Ohne Gruppentrennung bleibt Orange wie
zuvor als Prüfschicht sichtbar. Manuell zu Hindernissen umklassifizierte Objekte
verwenden wieder die Kategorie-Farbe. Speichern, Wiederöffnen und Undo/Redo
bewahren die Gruppeneigenschaften.

Prüfung: 70 Tests bestanden, einschließlich unterschiedlicher Richtungen,
Abstände und Farben, Helligkeitswechsel, schwacher Inseln, kleiner harmonischer
Inseln, metrischer CRS-Einheiten, Erhaltung der gesamten Feldmaske, fehlender
Überlappungen und Persistenz/Undo/Redo. Neue Vergleichsprojekte und PNGs stehen
unter `workspace/group_check/`. Interaktive Browserprüfung bleibt offen.

Vergleich gegen v7 bei identischen Analyseparametern (Radius 2 m, Schatten aus):

| Bild | Strukturgruppen einschließlich übriger Vegetation/Obst | Feldpolygone vorher → nachher | Änderung der gesamten Arbeitsflächenmaske |
|---|---:|---:|---:|
| Elies | 4 | 9 → 13, plus 1 Obstfläche | 0 m² |
| Rodia | 8 | 8 → 28 | unter 0,000001 m² |

Mehr Polygone sind hier teilweise beabsichtigt: unterschiedliche Strukturgruppen
bleiben getrennt. Eine Gruppe kann außerdem wegen Hindernissen oder fehlender
Verbindung mehrere Polygone enthalten. Wege, Gebäude-, Baum- und Obstflächen-
Geometrien bleiben gegenüber v7 unverändert. Alle Geometrien gültig, keine
Überlappungen zwischen Gruppen oberhalb numerischer Toleranz, kein Polygonlimit
erreicht. Elies links bleibt eine zusammenhängende Reihengruppe; obere Reihen,
Obstfläche und übrige Vegetation sind davon getrennt. Rodia enthält noch kleinere
Gruppen und grobe, rasterförmige Übergänge. Beide PNG-Vergleiche visuell geprüft;
fachlich korrekte Grenzen muss der Nutzer prüfen. Schattenfrage bleibt offen.
