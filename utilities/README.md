# SMART TA-2 Data Curation Utilities

Scripts in this folder support data curation activities such as preparing sites and regions for processing by algorithms and the evaluation test harness in `src`. In addition to formatting site and region information as properly-formatted geojsons, data curation also includes collecting associated imagery for sites. Descriptions and usage of the contained scripts are included below.

Copyright 2024

The Johns Hopkins University Applied Physics Laboratory

## Contact

Send email to: iarpa.smart@jhuapl.edu

## Requirements

Requires Python 3.10 (*note that this differs from `src`*)

Dependencies are included in `requirements.txt` and can be installed with `pip install -r requirements.txt`.

## Usage Examples

### Site and Region Model Generation

SMART-defined sites and regions are formatted as SMART-defined geojsons before use. This section details information on building simple annotation geojson files (i.e. those without observations).

These scripts make use of the Python standard library `argparse` package (see https://docs.python.org/3/library/argparse.html). Command line arguments are specified using two dashed lines `--` before the variable. 

#### Site Model

First, a site model is generated from basic site information: a kml boundary, start date (nullable), end date (nullable), and label. The script also has options for the user to specify an output directory and version number, as well as the option to overwrite an existing geojson.

The resulting name of the site model file (and therefore the official site ID) is determined by the region code which should prepend the kml file name. The user may then supply their own 4-digit ID to append to this region code, or a default 0000 is used. This is intended to support batch-processing, where each site kml is located within some region (and tagged as such), and supplied an ID that the user may increment themselves or pull from the kml filename if they keep the same site ID format. The simplest way to do this is to keep all site kmls formatted the same as their eventual site ID, and to extract out that "starting_id" from the filename.

The example below shows the site model generation process for an example site (AE_R001_0014), which would produce the site model found in `../annotations/primary_dataset/site_models/AE_R001_0014.geojson` just with a different version as this particular site saw a minor update before release, and this script will default back to 2.0.0 for the version.

```bash
# gets command line argument descriptions
python site_model_generator.py --help

# evaluates BR_R002
python site_model_generator.py --kml_path sample_kmls/AE_R001_0014.kml --starting_id 0014 --label positive_pending --start_date 2021-02-01 --end_date 2022-08-26
```

#### Region Model

A collection of site models typically resides within a defined region, and that collection is the resulting "region model." These region models are the main files used in broad area search processing and evaluation, as they contain all of the basic site information without the observations.

Generating a region model technically only requires a region kml, as there is a `-e` flag the user may specify to create an "empty" region model. If, however, you want to include sites within the region itself, you will point to a directory with site models within that region. Note: this is determined by file name, not by containment.

In the following example, the user creates a new copy of the AE_R001 region model, by pointing to the site models in this repository. Default start and end dates will be used, as specified in the help documentation.

```bash
# gets command line argument descriptions
python region_model_generator.py --help

# evaluates BR_R002
python site_model_generator.py --region_id AE_R001 --region_kml sample_kmls/AE_R001.kml --geojson_dir ../annotations/primary_dataset/site_models
```

### STAC Query Example

While not intended to be a standalone utility, `stac_query_example.py` provides documentation and guidelines on collecting publicly-available imagery from the Sentinel-2 and Landsat-8 collections.

The script runs without any command line arguments, and is supplied with an example boundary file, hard-coded into the script. Functions exist within the script to handle either geojson or kml bounding boxes on which to query STAC. Each of these functions is commented extensively with a working example in addition to a generalized description of relevant fields and query returns.

