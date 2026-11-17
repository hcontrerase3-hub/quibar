"""Shared extents for raster tiles and the elevation preparation."""
import math

BOUNDS = (-72.2, -38.05, -71.35, -37.55)
WORLD = 20037508.342789244
STYLE_VERSION = 'atlas-2'
DEM_LICENSE_URL = 'https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/DEM/resources/license/License-COPDEM-30.pdf'
DEM_NOTICE = ('produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and '
              '© Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS '
              'by the European Union and ESA; all rights reserved')
DEM_DISCLAIMER = ('Las organizaciones a cargo del programa Copernicus por ley o delegación '
                  'no incurren en responsabilidad alguna por cualquier uso de Copernicus WorldDEM-30.')


def tile(longitude, latitude, zoom):
    count = 2 ** zoom
    return (int((longitude + 180) / 360 * count),
            int((1 - math.asinh(math.tan(math.radians(latitude))) / math.pi) / 2 * count))


def tile_extent(zoom):
    west, south, east, north = BOUNDS
    left, top = tile(west, north, zoom)
    right, bottom = tile(east, south, zoom)
    return max(0, left - 1), max(0, top - 1), min(2 ** zoom - 1, right + 1), min(2 ** zoom - 1, bottom + 1)


def relief_bounds(min_zoom=8, max_zoom=16):
    """All published tiles, plus a buffer for hillshade derivatives."""
    extents = []
    for zoom in range(min_zoom, max_zoom + 1):
        left, top, right, bottom = tile_extent(zoom)
        count = 2 ** zoom
        latitude = lambda row: math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * row / count))))
        extents.append((left / count * 360 - 180, latitude(bottom + 1),
                        (right + 1) / count * 360 - 180, latitude(top)))
    return (min(e[0] for e in extents) - .01, min(e[1] for e in extents) - .01,
            max(e[2] for e in extents) + .01, max(e[3] for e in extents) + .01)
