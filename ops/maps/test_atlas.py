"""Geographic and preservation checks; run with the cartography container."""
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import mapnik
import numpy as np
from osgeo import gdal, osr
from PIL import Image

from cartography import relief_bounds, tile_extent
from relief import PARAMETERS, digest, download, ocean_tile, prepare, projected_bounds, source_tiles, validate_raster, verified_hillshade
from render import categorize, render, style


class AtlasTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / 'source.geojson'
        self.features = [
            {'type': 'Feature', 'properties': {'highway': 'primary', 'name': 'Prueba'},
             'geometry': {'type': 'LineString', 'coordinates': [[-72.02, -37.67], [-71.64, -37.88]]}},
            {'type': 'Feature', 'properties': {'natural': 'wood'},
             'geometry': {'type': 'Polygon', 'coordinates': [[[-72, -37.7], [-71.9, -37.7],
                                                           [-71.9, -37.8], [-72, -37.7]]]}},
        ]
        self.source.write_text(json.dumps({'type': 'FeatureCollection', 'features': self.features}))

    def raster(self, name='hillshade.tif', nodata=False):
        path = self.root / name
        west, south, east, north = relief_bounds()
        projection = osr.SpatialReference()
        projection.ImportFromEPSG(3857)
        geographic = osr.SpatialReference()
        geographic.ImportFromEPSG(4326)
        geographic.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        transform = osr.CoordinateTransformation(geographic, projection)
        x1, y1, _ = transform.TransformPoint(west, north)
        x2, y2, _ = transform.TransformPoint(east, south)
        dataset = gdal.GetDriverByName('GTiff').Create(str(path), 64, 64, 1, gdal.GDT_Byte)
        dataset.SetProjection(projection.ExportToWkt())
        dataset.SetGeoTransform((x1, (x2 - x1) / 64, 0, y1, 0, (y2 - y1) / 64))
        data = np.full((64, 64), 180, dtype=np.uint8)
        if nodata:
            data[20, 20] = 0
        dataset.GetRasterBand(1).SetNoDataValue(0)
        dataset.GetRasterBand(1).WriteArray(data)
        dataset = None
        return path

    def test_geometry_and_source_are_preserved(self):
        directory = self.root / 'layers'
        directory.mkdir()
        before = digest(self.source)
        groups = categorize(self.source, directory)
        self.assertEqual(groups['roads'][0]['geometry'], self.features[0]['geometry'])
        self.assertEqual(groups['forest'][0]['geometry'], self.features[1]['geometry'])
        shade = self.raster()
        for zoom in (8, 12, 16):
            for variant in ('classic', 'atlas'):
                m = mapnik.Map(256, 256)
                mapnik.load_map_from_string(m, style(directory, zoom, variant, shade), True)
        self.assertEqual(before, digest(self.source))

    def test_relief_covers_every_published_tile(self):
        west, south, east, north = relief_bounds()
        for zoom in range(8, 17):
            left, top, right, bottom = tile_extent(zoom)
            from cartography import tile
            self.assertLessEqual(tile(west, north, zoom)[0], left)
            self.assertLessEqual(tile(west, north, zoom)[1], top)
            self.assertGreaterEqual(tile(east, south, zoom)[0], right)
            self.assertGreaterEqual(tile(east, south, zoom)[1], bottom)

    def test_missing_elevations_and_wrong_projection_fail(self):
        with self.assertRaisesRegex(ValueError, 'Faltan elevaciones'):
            validate_raster(self.raster(nodata=True), '3857')
        with self.assertRaisesRegex(ValueError, 'Proyección inesperada'):
            validate_raster(self.raster('wrong.tif'), '4326')

    def test_interrupted_download_never_becomes_a_source(self):
        target = self.root / 'dem.tif'
        with patch('relief.subprocess.run', side_effect=subprocess.CalledProcessError(22, 'curl')):
            with self.assertRaises(subprocess.CalledProcessError):
                download('https://example.invalid/dem.tif', target)
        self.assertFalse(target.exists())
        target.with_name('dem.tif.part').write_bytes(b'incomplete')
        with self.assertRaisesRegex(ValueError, 'Descarga incompleta'):
            download('https://example.invalid/dem.tif', target)

    def test_partial_relief_and_corrupt_hash_fail(self):
        shade = self.raster()
        with self.assertRaisesRegex(ValueError, 'Relieve incompleto'):
            prepare(self.root)
        (self.root / 'relief.json').write_text(json.dumps({'hillshade_sha256': 'incorrect'}))
        with self.assertRaisesRegex(ValueError, 'SHA256'):
            render(self.source, self.root / 'atlas.mbtiles', 8, 8, 'atlas', shade)

    def test_atlas_mbtiles_and_overwrite_protection(self):
        shade = self.raster()
        (self.root / 'relief.json').write_text(json.dumps({'hillshade_sha256': digest(shade),
            'parameters': PARAMETERS, 'bounds': relief_bounds()}))
        target = self.root / 'atlas.mbtiles'
        render(self.source, target, 8, 8, 'atlas', shade)
        before = digest(target)
        with sqlite3.connect(target) as db:
            metadata = dict(db.execute('SELECT name,value FROM metadata'))
            self.assertEqual(metadata['quibar_style'], 'atlas-2')
            self.assertIn('Copernicus', metadata['attribution'])
            self.assertEqual(db.execute('PRAGMA quick_check').fetchone()[0], 'ok')
            left, top, right, bottom = tile_extent(8)
            rows = db.execute('SELECT tile_column,tile_row,tile_data FROM tiles').fetchall()
            self.assertEqual(len(rows), (right - left + 1) * (bottom - top + 1))
            for x, y, png in rows:
                self.assertTrue(left <= x <= right)
                self.assertTrue(top <= 2 ** 8 - 1 - y <= bottom)
                self.assertEqual(Image.open(io.BytesIO(png)).size, (256, 256))
        with self.assertRaisesRegex(ValueError, 'destino ya existe'):
            render(self.source, target, 8, 8, 'atlas', shade)
        self.assertEqual(before, digest(target))

    def test_classic_and_partial_package_protection(self):
        target = self.root / 'classic.mbtiles'
        render(self.source, target, 8, 8)
        with sqlite3.connect(target) as db:
            metadata = dict(db.execute('SELECT name,value FROM metadata'))
            self.assertEqual(metadata['quibar_style'], 'classic-1')
            self.assertNotIn('Copernicus', metadata['attribution'])
        pending = self.root / 'pending.mbtiles'
        pending.with_suffix('.mbtiles.part').write_bytes(b'preserve')
        with self.assertRaisesRegex(ValueError, 'generación incompleta'):
            render(self.source, pending, 8, 8)
        self.assertEqual(pending.with_suffix('.mbtiles.part').read_bytes(), b'preserve')

    def test_source_grid_uses_real_southwest_tile_identifiers(self):
        tiles = list(source_tiles((-72.2, -38.05, -71.35, -37.55)))
        self.assertEqual(len(tiles), 4)
        self.assertIn('S39_00_W073_00', tiles[0][0])
        self.assertTrue(tiles[0][1].endswith('/' + tiles[0][0]))

    def test_missing_land_never_becomes_ocean(self):
        identifier = 'Copernicus_DSM_COG_10_S38_00_W072_00_DEM'
        self.assertFalse(ocean_tile(identifier, {30: {identifier}, 90: set()}))
        with self.assertRaisesRegex(ValueError, 'terrestre sin GLO-30'):
            ocean_tile(identifier, {30: set(), 90: {identifier.replace('_COG_10_', '_COG_30_')}})
        self.assertTrue(ocean_tile(identifier, {30: set(), 90: set()}))

    def test_shifted_relief_fails_even_with_matching_checksum(self):
        shade = self.raster()
        dataset = gdal.Open(str(shade), gdal.GA_Update)
        transform = list(dataset.GetGeoTransform())
        transform[0] += 1000000
        dataset.SetGeoTransform(transform)
        dataset = None
        (self.root / 'relief.json').write_text(json.dumps({'hillshade_sha256': digest(shade),
            'parameters': PARAMETERS, 'bounds': relief_bounds()}))
        with self.assertRaisesRegex(ValueError, 'desplazado'):
            verified_hillshade(shade)

    def test_utm_extent_contains_curved_geographic_edges(self):
        bounds = relief_bounds()
        left, bottom, right, top = projected_bounds(bounds, 'EPSG:32719')
        geographic, projected = osr.SpatialReference(), osr.SpatialReference()
        geographic.ImportFromEPSG(4326)
        geographic.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        projected.ImportFromEPSG(32719)
        transform = osr.CoordinateTransformation(geographic, projected)
        west, south, east, north = bounds
        for longitude in np.linspace(west, east, 23):
            for latitude in (south, north):
                x, y, _ = transform.TransformPoint(longitude, latitude)
                self.assertTrue(left - 1 <= x <= right + 1)
                self.assertTrue(bottom - 1 <= y <= top + 1)
        for latitude in np.linspace(south, north, 23):
            for longitude in (west, east):
                x, y, _ = transform.TransformPoint(longitude, latitude)
                self.assertTrue(left - 1 <= x <= right + 1)
                self.assertTrue(bottom - 1 <= y <= top + 1)


if __name__ == '__main__':
    unittest.main()
