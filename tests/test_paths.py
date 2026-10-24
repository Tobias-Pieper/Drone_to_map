import pytest
from farm_mapping.paths import input_file
from farm_mapping.core import Project
from farm_mapping.raster import open_project


@pytest.mark.parametrize('reader', [open_project, Project.load])
def test_empty_and_directory(reader, tmp_path):
    with pytest.raises(ValueError, match='vollständigen Pfad'):
        reader('')
    with pytest.raises(ValueError, match='Ordner'):
        reader(tmp_path)


def test_missing_wrong_extension_and_quotes(tmp_path):
    with pytest.raises(ValueError, match='nicht gefunden'):
        input_file(tmp_path / 'missing.tif', ('.tif',), 'GeoTIFF')
    file = tmp_path / 'file with spaces.tif'
    file.touch()
    assert input_file(f'"{file}"', ('.tif',), 'GeoTIFF') == file.resolve()
    with pytest.raises(ValueError, match='Projekt-JSON'):
        Project.load(file)
