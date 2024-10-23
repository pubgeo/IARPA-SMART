# © 2024 The Johns Hopkins University Applied Physics Laboratory LLC.  This material was sponsored by the U.S. Government under contract number 2020-20081800401.
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the “Software”), to deal in
# the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import os
import json
import numpy as np
from pystac_client import Client
from fastkml import kml

def get_params(sensor):
    # STAC urls and relevant collections for publicly available Sentinel-2 and Landsat-8 imagery
    sensor_params = {'S2': {'STAC': "https://earth-search.aws.element84.com/v1",
                            'collections': ['sentinel-2-l2a', 'sentinel-2-l1c']},
                     'S2_v0': {'STAC': "https://earth-search.aws.element84.com/v0",
                               'collections': ['sentinel-s2-l2a', 'sentinel-s2-l1c']},
                     'LS': {'STAC': "https://landsatlook.usgs.gov/stac-server", 'collections': ['landsat-c2l1']}}
    return sensor_params[sensor]

def get_bounds_from_kml(kml_path):
    with open(kml_path, 'rt', encoding="utf-8") as f:
        data = f.read().encode('utf-8')
    k = kml.KML()
    k.from_string(data)
    features = list(k.features())
    f2 = list(features[0].features())
    bbox_bounds = f2[0].geometry # assumes geometry is always at top level of kml
    return bbox_bounds.bounds # returns bbox, not complex polygon geometry, to match STAC query needs

def get_bounds_from_geojson(geojson_path):
    with open(geojson_path, 'rt', encoding="utf-8") as f:
        data = json.load(f)
    polygon_bounds = data['features'][0]['geometry']['coordinates'] # assumes geometry is always in first feat index
    polygon_bounds = np.array(polygon_bounds).flatten()
    lon_idx = np.arange(0, len(polygon_bounds), 2)
    lat_idx = np.arange(1, len(polygon_bounds), 2)
    bbox_bounds = (max(polygon_bounds[lon_idx]), min(polygon_bounds[lat_idx]),
                   min(polygon_bounds[lon_idx]), max(polygon_bounds[lat_idx]))
    return bbox_bounds # returns bbox, not complex polygon geometry, to match STAC query needs

def searchSTACByBox(sensor='S2', bbox=(-72.5, 40.5, -72, 41), dates='2019-01-01/2019-12-31',
                     cloudCover=100, verbose=True, collection='All'):
    """
    searchSTACByBox(sensor='S2', bbox=(-72.5, 40.5, -72, 41), dates='2019-01-01/2019-12-31', cloudCover=100)
    Searches a particular sensor's STAC collections by a bounding box and date/cloud cover filters.
    The date format is finicky. If it's not formatted as YYYY-mm-dd/YYYY-mm-dd, it will error out.
    """

    headers = None
    params = get_params(sensor) # get STAC url and any relevant collections
    catalog = Client.open(url=params['STAC'], headers=headers) # open STAC catalog
    if collection == 'All': # search all collections in the STAC
        search = catalog.search(bbox=bbox, datetime=dates, query={'eo:cloud_cover': {'lt': cloudCover}})
    else: # search specific collections in the STAC
        search = catalog.search(bbox=bbox, datetime=dates, collections=params['collections'],
                                query={'eo:cloud_cover': {'lt': cloudCover}})
    try:
        items = search.get_all_items() # try to pull items out of the search
    except Exception as err:
        print(f'Error occurred in search site by box.  Error = {err}')
        exit(1)

    if verbose: # print info about returns if desired
        itemCounter = 0
        collectionList = []
        for item in items:
            itemCounter += 1
            if item.collection_id not in collectionList:
                collectionList.append(item.collection_id)
        print(f'Number of items found:  {itemCounter}')
        print(f'From these collections:  {collectionList}')

    return items


if __name__ == "__main__":
    # stac_query_example.py provides sample STAC calls for publicly-available Sentinel-2 and Landsat 8 imagery
    # NOTE: queries that return a very large quantity of imagery can sometimes error out; we often break queries
    #       into periods of a year or less to avoid this problem, though that is a significantly more conservative
    #       time limit than you'll generally need to avoid errors if your bounds aren't full countries/continents
    # For additional guidance on how to interact with STAC query results, see https://stacspec.org/en/tutorials/1-read-stac-python/

    #bounds_path = '' # INSERT PATH TO FILE WITH POLYGON BOUNDS (e.g. a kml, a site model (code will use site feature geometry), an empty region model)
    bounds_path = 'IARPA-SMART/annotations/site_models/AE_R001_0000.geojson'

    # Set up spatial bound filtering
    if os.path.splitext(bounds_path)[-1] == '.kml':
        bounds = get_bounds_from_kml(bounds_path)
    elif os.path.splitext(bounds_path)[-1] == '.geojson':
        bounds = get_bounds_from_geojson(bounds_path)
    else:
        print('Please provide a path to a kml or geojson with bounds for spatial filtering. Exiting.')
        exit(1)

    # Set up other filters
    #start_date = 'YYYY-mm-dd' # INSERT DATE RANGE OF INTEREST (must be in YYYY-mm-dd format)
    #end_date = 'YYYY-mm-dd' # INSERT DATE RANGE OF INTEREST (must be in YYYY-mm-dd format)
    start_date = '2018-01-01'
    end_date = '2018-01-31'
    #cloud_cover_ceiling = 100 # INSERT FILTER THRESHOLD (filter out any image with over X% cloud cover)
    cloud_cover_ceiling = 90

    # Query for Sentinel-2 imagery data, STAC v1
    # Note this Sentinel query pulls from two STAC collections, L2A and L1C. L1C has the default top-of-atmosphere
    #   version of images, L2A has an atmosphere-corrected version. We primarily used L2A, but L1C is available
    #   slightly earlier in some places than L2A (pre-2017), so it's also used in some annotations.
    # Note the Sentinel v0 STAC catalog was retired in 2022, so queries should generally use v1. A v0 example
    #   is included below because most of our annotations were made before the switch to v1, and there are some
    #   sites with annotated images that can only be found in v0.
    sensor = 'S2'
    s2_items = searchSTACByBox(sensor=sensor, bbox=bounds, dates=f'{start_date}/{end_date}',
                            cloudCover=cloud_cover_ceiling, verbose=True, collection='Sensor-Specific')
    # Query for Sentinel-2 imagery data, STAC v0
    # sensor = 'S2_v0'
    # s2v0_items = searchSTACByBox(sensor=sensor, bbox=bounds, dates=f'{start_date}/{end_date}',
    #                            cloudCover=cloud_cover_ceiling, verbose=True, collection='Sensor-Specific')

    # Query for Landsat-8 imagery data
    sensor = 'LS'
    ls_items = searchSTACByBox(sensor=sensor, bbox=bounds, dates=f'{start_date}/{end_date}',
                    cloudCover=cloud_cover_ceiling, verbose=True, collection='Sensor-Specific')

    # Most relevant fields in an image return are:
    #     image id (items[i].id)
    #     image capture date (items[i].datetime)
    #     image geometry (items[i].geometry)
    # Other useful fields include:
    #     image cloud cover (item.properties['eo:cloud_cover'])
    #     variety of other metadata fields stored in item.properties, contents differ for each imagery source
    # Again, see https://stacspec.org/en/tutorials/1-read-stac-python/ for more detail on working with STAC returns
    print('S2 images that match bounds/time/cloud cover filter:')
    for item in s2_items:
        print(f"image id: {item.id}, capture date: {item.datetime}, % cloud cover: {item.properties['eo:cloud_cover']}")
    print('LS images that match bounds/time/cloud cover filter:')
    for item in ls_items:
        print(f"image id: {item.id}, capture date: {item.datetime}, % cloud cover: {item.properties['eo:cloud_cover']}")

    '''
    If run with given example filters (AE_R001_0000 site model bounds for January 2018 at 90% max cloud cover), results should be: 
        26 S2 images across collections {'sentinel-2-l2a', 'sentinel-2-l1c}
            - images are available from dates 1/4/18 (n=2), 1/9/18 (8), 1/14/18 (4), 1/19/18 (4), 1/24/18 (4), and 1/29/18 (4)
        4 LS images in collection 'landsat-c2l1'
            - images are available from dates 1/5/2018, 1/13/2018, 1/21/2018, and 1/29/2018
    '''
