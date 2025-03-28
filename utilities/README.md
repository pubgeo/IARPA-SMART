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

A site model is generated from basic site information: a kml boundary, start date (nullable), end date (nullable), and label. The script also has options for the user to specify an output directory and version number, as well as the option to overwrite an existing geojson.

The resulting name of the site model file (and therefore the official site ID) is determined by the region code which should prepend the kml file name. The user may then supply their own 4-digit ID to append to this region code, or a default 0000 is used. This is intended to support batch-processing, where each site kml is located within some region (and tagged as such), and supplied an ID that the user may increment themselves or pull from the kml filename if they keep the same site ID format. The simplest way to do this is to keep all site kmls formatted the same as their eventual site ID, and to extract out that "starting_id" from the filename.

The example below shows the site model generation process for an example site (AE_R001_0014), which would produce the site model found in `../annotations/primary_dataset/site_models/AE_R001_0014.geojson`. This example site has been previously updated and no longer has the default version value (2.0.0), so the optional version_number argument is included.

```bash
# gets command line argument descriptions
python site_model_generator.py --help

# evaluates AE_R001_0014
python site_model_generator.py --kml_path sample_kmls/AE_R001_0014.kml --starting_id 0014 --label positive_pending --start_date 2021-02-01 --end_date 2022-08-26 --version_number 2.0.1
```

#### Region Model

A collection of site models typically resides within a defined larger area; region models are used to give boundaries for these larger areas. While region models generally include the region information and the full collection of site models within the defined area, they can also provide region information alone ("empty" region models). Region models are the main files used in broad area search processing and evaluation, as they contain all of the basic site information (e.g. start/end dates, status, geometry) without the observations.

All region model generation requires a region_id and a region kml. For the primary mode of region model generation (site information included), a path to a directory with site models for that region must also be provided (geojson_dir argument). Note that a site's association with a region is determined by matching region_id in the site model filename, not by spatial intersection between site and region bounds. For the "empty" mode of region model generation (region information only), the -e flag should be used and no site model geojson directory is needed. In either mode, the script also has options for the user to specify an originator, output directory, and region version number.

In the following example, the user creates a new copy of the AE_R001 region model by pointing to the site models in this repository. Default start and end dates and version number are used, as specified in the help documentation.

```bash
# gets command line argument descriptions
python region_model_generator.py --help

# evaluates AE_R001
python region_model_generator.py --region_id AE_R001 --region_kml sample_kmls/AE_R001.kml --geojson_dir ../annotations/primary_dataset/site_models
```

### STAC Query Example

While not intended to be a standalone utility, `stac_query_example.py` provides documentation and guidelines on collecting publicly-available imagery from the Sentinel-2 and Landsat-8 collections.

The script runs without any command line arguments, and is supplied with an example boundary file, hard-coded into the script. Functions exist within the script to handle either geojson or kml bounding boxes on which to query STAC. Each of these functions is commented extensively with a working example in addition to a generalized description of relevant fields and query returns.

### Site and Region Validation Example

A user can validate the format, structure, and some contents of site and region models with `validate_site_and_region_models.py`. Model geojsons are checked against the rules in smart.schema.json, unless a path to a different schema is passed as an argument. The contents of the `sample_models_for_validation` folder are available for testing, with one site model example and one region model example that pass the validator, as well as a site model example that will not pass the validator (its site feature date fields have been removed). The following example demonstrates how to run the validator on the contents of the `sample_models_for_validation` folder.

```bash
# gets command line argument descriptions
python validate_site_and_region_models.py --help

python validate_site_and_region_models.py --path sample_models_for_validation --schema_file smart.schema.json
```

