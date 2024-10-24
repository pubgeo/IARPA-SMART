#!/usr/bin/env python
# © 2024 The Johns Hopkins University Applied Physics Laboratory LLC.  This material was sponsored by the U.S. Government under contract number 2020-20081800401.
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the “Software”), to deal in
# the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# packages to install
from fastkml import kml
import geopandas as gpd
import git
import mgrs
import numpy as np
import shapely
# standard packages
from argparse import ArgumentParser
from collections import OrderedDict
import datetime
from pathlib import Path
import json
import os
import sys


def verify_date(date_string):
    try:
        date_object = datetime.datetime.strptime(date_string, '%Y-%m-%d')
        return date_object.strftime('%Y-%m-%d')
    except ValueError:
        print("Error: Date should be formatted as YYYY-MM-DD. Exiting...")
        exit(1)

def get_bounds_from_kml(kml_path):
    with open(Path(kml_path), 'rt', encoding="utf-8") as my_file:
        doc = my_file.read().encode('utf-8')
    k = kml.KML()
    k.from_string(doc)
    features = list(k.features())
    f2 = list(features[0].features())
    try:
        bounds = f2[0].geometry
    except AttributeError as e:
        f3 = list(f2[0].features())
        bounds = f3[0].geometry
    return bounds


def create_smart_site_models(site_models, merged_site_model, filename, output_dir, site_model_number, version_number, label, overwrite, git_hash):
    from shapely.ops import unary_union
    from shapely.geometry import MultiPolygon, Polygon
    import shapely.wkt as wkt

    for index, row in site_models.iterrows():
        geometry = row['geometry']
        all_wkt = []
        # Resize to (x,y) and round all coordinates to 6 digits of precision
        geometry = shapely.wkb.loads(shapely.wkb.dumps(geometry, output_dimension=2))
        geometry = Polygon([(round(x, 6), round(y, 6)) for (x, y) in unary_union(geometry).exterior.coords])
        all_wkt.extend([geometry.wkt])
        row['geometry'] = MultiPolygon(map(wkt.loads, all_wkt))
        merged_site_model = merged_site_model.append(row)

    # Write out individual site model
    # Reorder rows by date
    merged_site_model = merged_site_model.sort_values('observation_date')
    merged_site_model['type'] = 'observation'
    # Reorder columns to fit spec and add new columns to fit spec
    column_order = ['geometry', 'observation_date', 'source', 'sensor_name', 'type', 'current_phase',
                    'is_occluded', 'is_site_boundary', 'score']
    merged_site_model = merged_site_model.assign(score=1.0)
    merged_site_model = merged_site_model.reindex(column_order, axis=1)
    # Get MGRS code from the site model geometry
    centroid = list(merged_site_model.centroid)[0]  # uses first centroid in merged_site_model to determine MGRS code
    lat, lon = centroid.y, centroid.x
    m = mgrs.MGRS()
    mgrs_code = m.toMGRS(lat, lon)[0:5]
    # Get zero padded site model name
    region_name = '_'.join((filename[:-4].split('_'))[0:2])
    site_model_name = f'{region_name}_{str(int(site_model_number)).zfill(4)}.geojson'
    # Creates file path for the site model using specified output directory
    site_model_path = Path(output_dir) / site_model_name
    # Check if geojson file already exists in this directory
    if os.path.isfile(site_model_path) and not (overwrite.lower() == "true"):
        print(f"Error: {os.path.basename(site_model_path)} already exists in {output_dir}. Exiting to prevent overwriting.")
        exit(1)
    # Convert rows to booleans
    merged_site_model.to_file(str(site_model_path), driver='GeoJSON')
    # Write in custom properties
    with open(site_model_path, 'r+') as f:
        data = json.load(f)
        ordered_data = OrderedDict(data)
        site_properties = {'type': 'site'}
        site_properties['region_id'] = region_name
        site_properties['site_id'] = region_name + '_' + str(int(site_model_number)).zfill(4)
        site_properties['type'] = 'site'
        site_properties['version'] = version_number
        site_properties['status'] = label
        site_properties['mgrs'] = mgrs_code
        site_properties['score'] = 1.0
        site_properties['start_date'] = merged_site_model['observation_date'][0]
        site_properties['end_date'] = merged_site_model['observation_date'][1]
        site_properties['model_content'] = 'annotation'
        site_properties['originator'] = 'te'
        site_properties['validated'] = 'True'
        site_properties['misc_info'] = {'commit_hash': git_hash}
        ordered_properties = OrderedDict(site_properties)
        ordered_properties.move_to_end('misc_info', last=False)
        ordered_properties.move_to_end('validated', last=False)
        ordered_properties.move_to_end('originator', last=False)
        ordered_properties.move_to_end('model_content', last=False)
        ordered_properties.move_to_end('end_date', last=False)
        ordered_properties.move_to_end('start_date', last=False)
        ordered_properties.move_to_end('score', last=False)
        ordered_properties.move_to_end('mgrs', last=False)
        ordered_properties.move_to_end('status', last=False)
        ordered_properties.move_to_end('version', last=False)
        ordered_properties.move_to_end('site_id', last=False)
        ordered_properties.move_to_end('region_id', last=False)
        ordered_properties.move_to_end('type', last=False)
        full_geometry = shapely.geometry.mapping(unary_union(merged_site_model["geometry"].tolist()))
        full_geometry['coordinates'] = np.round(np.array(full_geometry['coordinates']),6).tolist()
        # Remote duplicate points
        duplicate_indices = []
        for index, point in enumerate(full_geometry["coordinates"][0]):
            if index == 0:
                continue
            if point == full_geometry["coordinates"][0][index - 1]:
                # Remove duplicate
                duplicate_indices.append(index)
        for index in duplicate_indices:
            del full_geometry["coordinates"][0][index]
        # Format data
        ordered_data['features'].insert(0, {'type': 'Feature', 'properties': ordered_properties, 'geometry': full_geometry})
        f.seek(0)
        json.dump(ordered_data, f, indent=4)
        f.truncate()


def main(args=None):
    if args is None:
        args = sys.argv[1:]

    parser = ArgumentParser()
    parser.add_argument('-k', '--kml_path', help='Directory with the single KML file, or path directly to the KML file for the site boundary. File name should begin with region code (e.g. US_R001) for proper formatting', required=True)
    parser.add_argument('-v', '--version_number', help='Version number for the site model, keeping Major.Minor.Patch convention (see documentation)', required=False, default='2.0.0')
    parser.add_argument('-s', '--starting_id', help='Sets zero-padded four-digit identifier added to region code to create the full site ID. Will use 0 ("0000") unless specified', required=False, type=int, default=0)
    parser.add_argument('-o', '--output_dir', help='Location to save resulting site model', required=False, default='.')
    parser.add_argument('-sd', '--start_date', help='Site start date entered as YYYY-MM-DD, defined as last date before activity begins. See documentation for more details', required=False, default=None)
    parser.add_argument('-ed', '--end_date', help='Site end date entered as YYYY-MM-DD, defined as first date after activity finishes. See documentation for more details', required=False, default=None)
    parser.add_argument('-l', '--label', help='Site annotation label, one of: positive_pending, positive_excluded, ignore, negative. See documentation for more details', required=True)
    parser.add_argument('-ov', '--overwrite', required=False, default=False)
    args, unknown = parser.parse_known_args(args)
    if unknown:
        print('Unknown input arguments:')
        print(unknown)
        return

    # Check version number input
    version_number = args.version_number
    version_split = version_number.split('.')
    if len(version_split) != 3:
        print("Error: Version number must be formatted as #.#.#. Exiting...")
        exit(1)
    for num in version_split:
        if not num.isdigit():
            print("Error: Version number must be formatted as #.#.#. Exiting...")
            exit(1)

    # Check date input
    start_date = args.start_date
    end_date = args.end_date
    if start_date != None:
        start_date = verify_date(args.start_date)
    if end_date != None:
        end_date = verify_date(args.end_date)

    # Check label input
    label = args.label
    if label not in ["positive_pending", "positive_excluded", "negative", "ignore"]:
        print('Error: Label must be one of "positive_pending", "positive_excluded", "negative", or "ignore". Exiting...')
        exit(1)

    # Get git commit hash for file versioning
    repo = git.Repo(search_parent_directories=True)
    sha = repo.head.object.hexsha

    print("Reading in kml...")
    # Check input directory/file
    # Directory
    if os.path.isdir(args.kml_path):
        files = [f for f in os.listdir(args.kml_path) if os.path.splitext(f)[1] == ".kml"]
        if len(files) > 1:
            print("Error: Only one .kml per input directory is supported. Exiting...")
            exit(1)
        elif len(files) == 0:
            print("Error: No .kml in this directory. Exiting...")
            exit(1)
        else:
            kml_file = str(args.kml_path) + '/' + str(files[0])
            geometry = get_bounds_from_kml(kml_file)
            site_model_number = int(args.starting_id)
            output_dir = args.output_dir
            site_models = gpd.GeoDataFrame()
            site_models['geometry'] = [geometry, geometry]
            site_models['observation_date'] = [start_date, end_date]
            site_models['Image Name'] = ["Start", "End"]

            merged_site_model = gpd.GeoDataFrame()

            create_smart_site_models(site_models, merged_site_model, files[0], output_dir, site_model_number, version_number, label, args.overwrite, sha)
    # File
    elif os.path.isfile(args.kml_path):
        filename = args.kml_path
        if filename.lower().endswith('.kml'):
            geometry = get_bounds_from_kml(filename)
            site_model_number = int(args.starting_id)
            output_dir = args.output_dir
            site_models = gpd.GeoDataFrame()
            site_models['geometry'] = [geometry, geometry]
            site_models['observation_date'] = [start_date, end_date]
            site_models['Image Name'] = ["Start", "End"]

            merged_site_model = gpd.GeoDataFrame()

            create_smart_site_models(site_models, merged_site_model, os.path.basename(filename), output_dir, site_model_number, version_number, label, args.overwrite, sha)
        else:
            print("Error: Input file must be .kml. Exiting...")
            exit(1)
    else:
        print("Error: input is neither a valid directory nor a valid file. Exiting...")
        exit(1)

if __name__ == "__main__":
    main()
