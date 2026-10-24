# Versionsverwaltung mit Git und GitHub

Git speichert lokale Entwicklungsstände; GitHub hält eine entfernte Kopie.
`main` enthält den geprüften Hauptstand. Größere Änderungen entstehen auf einem
eigenen Branch und können vor dem Zusammenführen als Pull Request geprüft werden.

## Erstes Repository

Alle Befehle im Projektordner ausführen. Zuerst Git mit Hauptbranch `main`
initialisieren und die geplanten Dateien vor dem Commit prüfen:

```bash
git init -b main
git status --short
git add .gitignore pyproject.toml README.md CHANGELOG.md Projektplan_Farm_Mapping_KI.md src tests examples docs
git diff --cached --stat
```

Tests ausführen und den geprüften Ausgangsstand festhalten:

```bash
.venv/bin/python -m pytest -q
git commit -m "feat: add offline farm mapping prototype with polygon editing"
```

Bei GitHub anmelden. Zugangsdaten ausschließlich im GitHub-Anmeldeablauf eingeben,
nicht in Projektdateien oder Chatnachrichten:

```bash
gh auth login -h github.com
```

Ein privates Repository erstellen, es als `origin` verbinden und den lokalen
Hauptbranch hochladen. Dieser Befehl veröffentlicht den bisherigen Code im
privaten GitHub-Repository des angemeldeten Accounts:

```bash
gh repo create Drone_to_map --private --source=. --remote=origin --push
```

## Weitere Entwicklung

Vor einem zusammengehörigen Arbeitsschritt einen Branch anlegen:

```bash
git switch -c feature/beschreibender-name
```

Nach Änderungen Tests ausführen und den Unterschied prüfen:

```bash
.venv/bin/python -m pytest -q
git diff
git status --short
```

Die zugehörigen Dateien gezielt mit `git add DATEIPFAD` vormerken.
Einen kleinen, verständlich beschriebenen Commit erstellen und den Branch sichern:

```bash
git commit -m "feat: describe the implemented change"
git push -u origin HEAD
```

`feat:` bezeichnet Funktionen, `fix:` Fehlerkorrekturen und `docs:` Dokumentation.
Nach dem Push kann auf GitHub ein Pull Request nach `main` erstellt werden.
Keine erfundene Feingranularität: Ein Commit umfasst einen tatsächlich geprüften,
zusammengehörigen Entwicklungsstand.

## Historie und Rücknahme

Die letzten Änderungen mit ihren Commit-IDs anzeigen:

```bash
git log --oneline --decorate -15
```

Einen bestimmten Stand ansehen:

```bash
git show COMMIT_ID
```

Eine bereits veröffentlichte Änderung durch einen neuen Gegen-Commit zurücknehmen
und diesen hochladen. Dafür vorher sicherstellen, dass keine ungespeicherten
Arbeitsänderungen vorhanden sind. Bei abhängigen Änderungen können Konflikte
auftreten, die geprüft werden müssen:

```bash
git revert COMMIT_ID
git push
```

Die bestehende Historie bleibt dabei erhalten. Ungeprüfte `reset --hard`- oder
Force-Push-Befehle sind für diesen normalen Rücknahmeablauf nicht nötig.

## Was gesichert wird

Code, Tests, Dokumentation und synthetischer Demo-Generator gehören in Git.
`data/`, TIFFs, `.venv/`, `workspace/` und lokale Zugangsdaten sind ausgeschlossen.
Die bearbeitete Karte liegt derzeit in `workspace/project.json`; die Original-TIFFs
liegen in `data/`. Beide getrennt sichern, einschließlich zusammengehöriger
Originaldaten. Die Projektdatei referenziert den Originalpfad und eine Prüfsumme.
Ein Wiederherstellen des Codes ändert gespeicherte Kartenprojekte nicht automatisch.

Das Repository erhält noch keine willkürlich ausgewählte Lizenz: Vor einer
öffentlichen Weitergabe muss die gewünschte Open-Source-Lizenz festgelegt werden.
