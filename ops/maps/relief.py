"""Prepare a verified, local Copernicus GLO-30 hillshade. Run in the map container."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import subprocess
import tempfile
import numpy as np

from osgeo import gdal, osr

from cartography import DEM_DISCLAIMER, DEM_LICENSE_URL, DEM_NOTICE, relief_bounds

gdal.UseExceptions()
BASE_URL = 'https://copernicus-dem-30m.s3.amazonaws.com'
PARAMETERS = {'source': 'Copernicus DEM GLO-30 Public (2021)', 'resolution_m': 30,
              'working_crs': 'EPSG:32719', 'output_crs': 'EPSG:3857',
              'azimuth': 315, 'altitude': 45, 'vertical_exaggeration': 1}


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def source_tiles(bounds):
    west, south, east, north = bounds
    for lat in range(math.floor(south), math.ceil(north)):
        for lon in range(math.floor(west), math.ceil(east)):
            name = (f'Copernicus_DSM_COG_10_{"N" if lat >= 0 else "S"}{abs(lat):02d}_00_'
                    f'{"E" if lon >= 0 else "W"}{abs(lon):03d}_00_DEM')
            yield name + '.tif', f'{BASE_URL}/{name}/{name}.tif'


def ocean_tile(identifier, indexes):
    if identifier in indexes[30]:
        return False
    if identifier.replace('_COG_10_', '_COG_30_') in indexes[90]:
        raise ValueError(f'Ésta es una tesela terrestre sin GLO-30 público: {identifier}')
    return True


def projected_bounds(bounds, destination):
    geographic = osr.SpatialReference()
    geographic.ImportFromEPSG(4326)
    geographic.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    projected = osr.SpatialReference()
    projected.SetFromUserInput(destination)
    transform = osr.CoordinateTransformation(geographic, projected)
    # UTM edges curve. Transforming only opposite corners clips valid terrain.
    return transform.TransformBounds(*bounds, 21)


def download(url, target):
    partial = target.with_name(target.name + '.part')
    if partial.exists():
        raise ValueError(f'Descarga incompleta: {partial}. Archívala antes de reintentar.')
    subprocess.run(['curl', '-fsSL', '--retry', '3', '--connect-timeout', '20',
                    '--max-time', '900', '-o', str(partial), url], check=True)
    partial.rename(target)


def validate_raster(path, expected_crs=None):
    dataset = gdal.Open(str(path))
    if not dataset or dataset.RasterCount != 1:
        raise ValueError(f'Elevación inválida: {path}')
    if expected_crs and dataset.GetSpatialRef().GetAuthorityCode(None) != expected_crs:
        raise ValueError(f'Proyección inesperada: {path}')
    band = dataset.GetRasterBand(1)
    for y in range(0, dataset.RasterYSize, 256):
        height = min(256, dataset.RasterYSize - y)
        data = band.ReadAsArray(0, y, dataset.RasterXSize, height)
        mask = band.GetMaskBand().ReadAsArray(0, y, dataset.RasterXSize, height)
        if not np.isfinite(data).all() or (mask == 0).any():
            raise ValueError(f'Faltan elevaciones dentro de la cobertura: {path}')
    return dataset


def verified_hillshade(path, min_zoom=8, max_zoom=16):
    record = json.loads(path.with_name('relief.json').read_text())
    if record['hillshade_sha256'] != digest(path):
        raise ValueError('SHA256 del relieve incorrecto.')
    if record.get('parameters') != PARAMETERS or record.get('bounds') != list(relief_bounds()):
        raise ValueError('La procedencia del relieve no corresponde a la configuración actual.')
    if not 8 <= min_zoom <= max_zoom <= 16:
        raise ValueError('El relieve del atlas cubre únicamente los niveles 8–16.')
    dataset = validate_raster(path, '3857')
    geographic = osr.SpatialReference()
    geographic.ImportFromEPSG(4326)
    geographic.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    transform = osr.CoordinateTransformation(geographic, dataset.GetSpatialRef())
    inverse = gdal.InvGeoTransform(dataset.GetGeoTransform())
    west, south, east, north = relief_bounds(min_zoom, max_zoom)
    for lon, lat in ((west, south), (west, north), (east, south), (east, north)):
        x, y, _ = transform.TransformPoint(lon, lat)
        px, py = gdal.ApplyGeoTransform(inverse, x, y)
        # GDAL rounds the extent to the nearest output pixel.
        if not (-.51 <= px <= dataset.RasterXSize + .51 and -.51 <= py <= dataset.RasterYSize + .51):
            raise ValueError('El relieve está desplazado o no cubre todas las teselas publicadas.')
    return record


def prepare(root):
    root.mkdir(parents=True, exist_ok=True)
    target = root / 'hillshade.tif'
    manifest = root / 'relief.json'
    bounds = relief_bounds()
    if target.exists() or manifest.exists():
        if not target.exists() or not manifest.exists():
            raise ValueError('Relieve incompleto. Archiva la carpeta relief antes de regenerar.')
        record = json.loads(manifest.read_text())
        if record['parameters'] != PARAMETERS or record['bounds'] != list(bounds):
            raise ValueError('Cambió la configuración del relieve; archiva relief antes de regenerar.')
        if record['hillshade_sha256'] != digest(target):
            raise ValueError('El relieve no coincide con su SHA256; conserva y revisa el archivo.')
        verified_hillshade(target)
        return target
    partial = root / 'hillshade.part.tif'
    if partial.exists():
        raise ValueError('Existe hillshade.part.tif; archívalo antes de reintentar.')
    sources = []
    # GLO-90 is global: a tile absent from BOTH official lists is ocean,
    # for which the publisher explicitly prescribes elevation zero.
    lists = {}
    for resolution in (30, 90):
        listing = root / f'tileList-{resolution}.txt'
        if not listing.exists():
            download(f'https://copernicus-dem-{resolution}m.s3.amazonaws.com/tileList.txt', listing)
        lists[resolution] = set(listing.read_text().split())
        if len(lists[resolution]) < 10000 or not all(
                name.startswith('Copernicus_DSM_COG_') and name.endswith('_DEM')
                for name in lists[resolution]):
            raise ValueError(f'Índice de cobertura inválido: {listing}; archívalo antes de reintentar.')
    # Extra geographic buffer supports the projected derivative at outer edges.
    download_bounds = (bounds[0] - .05, bounds[1] - .05, bounds[2] + .05, bounds[3] + .05)
    for name, url in source_tiles(download_bounds):
        path = root / name
        receipt = root / (name + '.json')
        identifier = name.removesuffix('.tif')
        ocean = ocean_tile(identifier, lists)
        if path.exists():
            if not receipt.exists() or json.loads(receipt.read_text())['sha256'] != digest(path):
                raise ValueError(f'Fuente sin procedencia válida: {path}; archívala antes de reintentar.')
        else:
            print(f'Descargando elevaciones: {name}', flush=True)
            if ocean:
                # The identifiers encode the southwest corner of the source grid.
                lat, lon = identifier.split('_')[4], identifier.split('_')[6]
                south = int(lat[1:]) * (-1 if lat[0] == 'S' else 1)
                west = int(lon[1:]) * (-1 if lon[0] == 'W' else 1)
                dataset = gdal.GetDriverByName('GTiff').Create(str(path), 3600, 3600, 1, gdal.GDT_Float32,
                            options=['COMPRESS=DEFLATE', 'TILED=YES'])
                srs = osr.SpatialReference()
                srs.ImportFromEPSG(4326)
                dataset.SetProjection(srs.ExportToWkt())
                # Match the COG pixel-center convention (half a pixel west/north).
                dataset.SetGeoTransform((west - 1 / 7200, 1 / 3600, 0, south + 1 + 1 / 7200, 0, -1 / 3600))
                dataset.GetRasterBand(1).Fill(0)
                dataset = None
            else:
                download(url, path)
            validate_raster(path, '4326')
            receipt.write_text(json.dumps({'url': url, 'sha256': digest(path)}))
        sources.append({'file': name, 'url': None if ocean else url, 'sha256': digest(path),
                        'ocean_zero_from_global_index': ocean})
    license_path = root / 'COPERNICUS-DEM-LICENSE.pdf'
    if not license_path.exists():
        download(DEM_LICENSE_URL, license_path)
    if not license_path.read_bytes().startswith(b'%PDF-'):
        raise ValueError('La licencia descargada no es un PDF válido.')
    (root / 'NOTICE.txt').write_text(DEM_NOTICE + '\n\n' + DEM_DISCLAIMER + '\n')
    with tempfile.TemporaryDirectory(prefix='building-', dir=root) as temporary:
        work = Path(temporary)
        vrt = gdal.BuildVRT(str(work / 'dem.vrt'), [str(root / s['file']) for s in sources])
        vrt = None
        print('Reproyectando elevaciones a UTM 19S, 30 m…', flush=True)
        dem = gdal.Warp(str(work / 'dem.tif'), str(work / 'dem.vrt'), dstSRS='EPSG:32719',
                        outputBounds=projected_bounds(download_bounds, 'EPSG:32719'),
                        xRes=30, yRes=30, resampleAlg='bilinear', dstNodata=-9999,
                        creationOptions=['COMPRESS=DEFLATE', 'TILED=YES', 'BIGTIFF=IF_SAFER'])
        dem = None
        shade = gdal.DEMProcessing(str(work / 'shade.tif'), str(work / 'dem.tif'), 'hillshade',
                                   azimuth=315, altitude=45, zFactor=1, scale=1, computeEdges=True,
                                   creationOptions=['COMPRESS=DEFLATE', 'TILED=YES'])
        shade = None
        output = gdal.Warp(str(partial), str(work / 'shade.tif'), dstSRS='EPSG:3857',
                           outputBounds=bounds, outputBoundsSRS='EPSG:4326', xRes=38, yRes=38,
                           resampleAlg='bilinear', dstNodata=0,
                           creationOptions=['COMPRESS=DEFLATE', 'TILED=YES', 'BIGTIFF=IF_SAFER'])
        output = None
        validate_raster(partial, '3857')
    record = {'parameters': PARAMETERS, 'bounds': list(bounds), 'sources': sources,
              'tile_indexes': {str(r): {'url': f'https://copernicus-dem-{r}m.s3.amazonaws.com/tileList.txt',
                                      'sha256': digest(root / f'tileList-{r}.txt')} for r in (30, 90)},
              'prepared_at': datetime.now(timezone.utc).isoformat(),
              'license_url': DEM_LICENSE_URL, 'notice': DEM_NOTICE, 'disclaimer': DEM_DISCLAIMER,
              'license_sha256': digest(license_path), 'hillshade_sha256': digest(partial),
              'gdal': gdal.VersionInfo('--version')}
    partial.rename(target)
    manifest.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    print(prepare(args.directory))
