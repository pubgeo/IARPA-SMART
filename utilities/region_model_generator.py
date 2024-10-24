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
import geopandas as gp
import mgrs
import numpy as np
import pandas as pd
from shapely import geometry, wkb
# standard packages
from argparse import ArgumentError, ArgumentParser, ArgumentTypeError
import collections
import geojson
import json
import os
from pathlib import Path


def check_date_format(date):
    if date is None:
        return True
    split_date = date.split('-')
    if len(split_date) != 3:
        return False
    if len(split_date[0]) != 4:
        return False
    if len(split_date[1]) != 2:
        return False
    if len(split_date[2]) != 2:
        return False
    for date in split_date:
        if not date.isdecimal():
            return False
    return True

def read_geojson(geojson_path):
    data = gp.read_file(geojson_path)
    return data


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


def generate_site_summary(site_df, geojson_file, errors):
    summary = collections.OrderedDict()
    summary['type'] = 'site_summary'
    summary['status'] = 'positive_annotated'
    summary['site_id'] = geojson_file.split('.geojson')[0]
    summary['geometry'] = geometry.box(*site_df['geometry'].total_bounds)
    # Round all coordinates to 6 digits of precision
    summary['geometry'] = geometry.Polygon([(round(x, 6), round(y, 6)) for (x,y) in summary['geometry'].exterior.coords])
    if ('type' in site_df.columns and site_df.iloc[0]['type'] == 'site'):
        summary['geometry'] = site_df.iloc[0]['geometry']
        summary['version'] = site_df.iloc[0]['version']
        summary['mgrs'] = site_df.iloc[0]['mgrs']
        summary['status'] = site_df.iloc[0]['status']
        summary['start_date'] = site_df.iloc[0]['start_date']
        summary['end_date'] = site_df.iloc[0]['end_date']
    else:
        summary['start_date'] = min(site_df['observation_date'])
        summary['end_date'] = max(site_df['observation_date'])
    if not check_date_format(summary['start_date']):
        errors.append("Site summary of site " + summary['site_id'] + " has an invalid start date of " + summary['start_date'])
    if not check_date_format(summary['end_date']):
        errors.append("Site summary of site " + summary['site_id'] + " has an invalid end date of " + summary['end_date'])
    summary['score'] = 1.0
    return summary, errors


def region_model_generator(args):
    errors = []
    all_site_geojsons = sorted(os.listdir(args.geojson_dir))
    all_site_summaries = []
    if args.empty_region_model is False:
        for idx, site_geojson in enumerate(all_site_geojsons):
            if args.region_id in site_geojson:
                site_data = read_geojson(os.path.join(args.geojson_dir, site_geojson))
                site_summary, errors = generate_site_summary(site_data, site_geojson, errors)
                all_site_summaries.append(site_summary)

    all_site_summaries_df = pd.DataFrame.from_records(all_site_summaries)
    # add in region summary to beginning of dataframe
    region_summary = collections.OrderedDict()
    region_summary['type'] = 'region'
    region_summary['region_id'] = args.region_id
    region_summary['version'] = args.version
    region_geometry = args.region_bbox
    region_geometry = wkb.loads(wkb.dumps(region_geometry, output_dimension=2)) # remove z-values

    # Round all coordinates to 6 digits of precision
    region_summary['geometry'] = geometry.Polygon([(round(x, 6), round(y, 6)) for (x,y) in region_geometry.exterior.coords]).simplify(0)
    m = mgrs.MGRS()
    region_summary['mgrs'] = m.toMGRS(region_geometry.centroid.y, region_geometry.centroid.x)[0:5]
    region_summary['start_date'] = args.start_date
    region_summary['end_date'] = args.end_date
    region_summary_df = pd.DataFrame.from_records([region_summary])

    if args.empty_region_model is False:
        all_summaries_df = pd.concat([region_summary_df, all_site_summaries_df], axis=0, ignore_index=True)
        # force column order
        columns = ['type', 'status', 'region_id', 'version', 'site_id', 'mgrs', 'start_date', 'end_date', 'score', 'geometry']
        all_summaries_df = all_summaries_df[columns]
        all_summaries_df["originator"] = args.originator
        all_summaries_df["model_content"] = 'annotation'
        all_summaries_df["validated"] = "True"
    else:
        all_summaries_df = region_summary_df.copy()
        columns = ['type', 'region_id', 'version', 'mgrs', 'start_date', 'end_date', 'geometry']
        all_summaries_df = all_summaries_df[columns]
        all_summaries_df["originator"] = args.originator
        all_summaries_df["model_content"] = 'empty'
        all_summaries_df["comments"] = None

    all_summaries_gdf = gp.GeoDataFrame(all_summaries_df, geometry=all_summaries_df.geometry)
    output_filename = f'{args.region_id}.geojson'
    output_fullpath = Path(args.output_dir) / output_filename
    all_summaries_gdf.to_file(str(output_fullpath), driver="GeoJSON")

    with open(output_fullpath, 'r+') as f:
        data = json.load(f)
        ordered_data = collections.OrderedDict(data)
        # get rid of metadata fields that do not apply to region feature
        if args.empty_region_model is False:
            for feature in ordered_data['features']:
                if feature['properties']['type'] == 'region':
                    del feature['properties']['status']
                    del feature['properties']['site_id']
                    del feature['properties']['score']
                    del feature['properties']['validated']
                    feature['properties']['comments'] = None
                else:
                    del feature['properties']['region_id']
        # write to file
        f.seek(0)
        json.dump(ordered_data, f, indent=4)
        f.truncate()

        if len(errors) == 0:
            print("No errors were found")
            return
        print("Errors found:")
        print(json.dumps(errors, indent=4))
        # Creates file path for errors
        path_errors = Path(args.output_dir) / f'{args.region_id}_errors.json'
        if not os.path.isfile(path_errors):  # to save errors only once
            with open(path_errors, 'w') as f:
                json.dump(errors, f, indent=4)
                print(f'Find errors here: {path_errors}')

def main():
    parser = ArgumentParser()
    parser.add_argument('-id', '--region_id', type=str, dest='region_id', help='region code string (US_R001, KR_R002, etc.)')
    parser.add_argument('-v', '--version', type=str, dest='version', help='region model version (i.e. x.x.x)', default='2.0.0')
    parser.add_argument('-orig', '--originator', type=str, dest='originator', help="Originator of this region model. (e.g. 'te', 'imerit', etc.)", default='te')
    parser.add_argument('-kml', '--region_kml', type=str, dest='region_kml', help='path to kml file for the region boundary')
    parser.add_argument('-start', '--start_date', type=str, dest='start_date', help='Start date of the region model in YYYY-MM-DD format. Default is 2014-01-01.', default='2014-01-01')
    parser.add_argument('-end', '--end_date', type=str, dest='end_date', help='End date of the region model in YYYY-MM-DD format. Default is 2021-08-31.', default='2021-08-31')
    parser.add_argument('-o', '--output_dir', type=str, dest='output_dir', help='directory to which geojsons are output', default='.')
    parser.add_argument('-e', '--empty_region_model', action='store_true', help='Optional flag (-e) to create empty region geojson with no contained sites. Skip --geojson_dir if using')
    parser.add_argument('-g', '--geojson_dir', type=str, dest='geojson_dir', required=False, help='Folder with site model geojson files. required if generating non-empty region model. Pulls all sites with region code in string, does not perform containment check.')
    try:
        parsed = parser.parse_args()
    except ArgumentError as error:
        # seems redundant, but deals with closures
        raise error

    if parsed.empty_region_model is False and parsed.geojson_dir is None:
        raise Exception('If generating a full region model, site model geojson directory is required')
    if not check_date_format(parsed.start_date):
        raise Exception('The start date ' + parsed.start_date + ' is an invalid start date')
    if not check_date_format(parsed.end_date):
        raise Exception('The end date ' + parsed.end_date + ' is an invalid end date')

    parsed.region_bbox = get_bounds_from_kml(parsed.region_kml)
    region_model_generator(parsed)


if __name__ == "__main__":
    main()