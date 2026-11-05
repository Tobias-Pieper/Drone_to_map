"""Server-side user simulation; does not replace interactive Leaflet browser tests."""
import asyncio
from unittest.mock import patch
import numpy as np
import rasterio
from rasterio.transform import from_origin
from nicegui import ui, run
from nicegui.testing.user_simulation import user_simulation
from farm_mapping.app import main


def test_preview_accept_undo_and_discard(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path=tmp_path/'test.tif'
    with rasterio.open(path,'w',driver='GTiff',width=64,height=64,count=3,
                       dtype='uint8',crs='EPSG:32632',
                       transform=from_origin(690000,5330000,.5,.5)) as dst:
        image=np.empty((3,64,64),dtype='uint8')
        image[:]=np.array([75,150,65])[:,None,None]
        # A bright interior must produce a review overlay without adding map objects.
        image[:,20:26,20:40]=np.array([180,180,175])[:,None,None]
        dst.write(image)

    async def in_process(function,*args,**kwargs):
        return function(*args,**kwargs)

    async def scenario():
        async with user_simulation() as user:
            with patch.object(ui,'run'):
                main()
            with patch.object(run,'cpu_bound',in_process):
                await user.open('/')
                user.find('Lokaler GeoTIFF- oder Projekt-JSON-Pfad').type(str(path))
                user.find(kind=ui.button, content='GeoTIFF öffnen').click()
                await user.should_see('Gültige Bildfläche: 0,10 ha')
                user.find(kind=ui.button, content='Ganze Karte analysieren').click()
                await user.should_see('1 Vorschläge:', retries=20)
                user.find(kind=ui.button, content='Vorschau verwerfen').click()
                await user.should_see('Keine ausstehenden Vorschläge.')
                user.find(kind=ui.button, content='Ganze Karte analysieren').click()
                await user.should_see('1 Vorschläge:', retries=20)
                user.find(kind=ui.button, content='Vorschläge übernehmen').click()
                await user.should_see('1 Vorschläge ergänzt.')
                await user.should_see('Prüfung erforderlich')
                user.find(kind=ui.button, content='Undo').click()
                await user.should_see('0 Polygone')
    asyncio.run(scenario())
