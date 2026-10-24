"""Validate local input files before passing them to format readers."""
from pathlib import Path


def input_file(value, suffixes, label):
    text = str(value or '').strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ('"', "'"):
        text = text[1:-1].strip()
    if not text:
        raise ValueError(f'Bitte eine {label}-Datei auswählen oder ihren vollständigen Pfad eingeben.')
    path = Path(text).expanduser()
    if path.is_dir():
        raise ValueError(f'Der Pfad zeigt auf einen Ordner. Bitte eine {label}-Datei mit Dateinamen auswählen.')
    if not path.is_file():
        raise ValueError(f'Datei nicht gefunden: {path}')
    if path.suffix.lower() not in suffixes:
        raise ValueError(f'Bitte eine {label}-Datei auswählen ({", ".join(suffixes)}).')
    return path.resolve()
