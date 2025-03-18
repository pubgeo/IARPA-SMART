# SMART TA-2 Evaluation Metrics

Copyright 2025

The Johns Hopkins University Applied Physics Laboratory and BlackSky Inc.

## Contents
* [Contact](#contact)
* [Requirements](#requirements)
* [Installation](#installation)
* [Usage Examples](#usage-examples)
* [Example Input and Output Files](#example-input-and-output-files)
* [Command Line Arguments](#command-line-arguments)

## Contact

Send email to: iarpa.smart@jhuapl.edu

## Requirements

Requires Python 3.11

Supported operating systems: Unix and macOS

## Installation

Install the `iarpa_smart_metrics` module using pip:

```pip3 install -e .```

See the [Installation](INSTALLATION.md) guide for more details.

## Usage Examples

The testing script utilizes the Python [click](https://pypi.org/project/click/) package. Arguments are specified using two dashed lines `--` before the variable. See examples below:

```bash
# gets command line argument descriptions
python -m iarpa_smart_metrics.run_evaluation --help

# evaluates the region BR_R002 using ground truth polygon annotations
python -m iarpa_smart_metrics.run_evaluation --roi BR_R002 --sequestered_id BR_R002 --gt_dir example/input/truth/site_models/ --sm_dir example/input/proposals/ --rm_path example/input/truth/region_models/BR_R002.geojson --output_dir example/output/poly/

# evaluates the region BR_R002 using ground truth point annotations
python -m iarpa_smart_metrics.run_evaluation --roi BR_R002 --sequestered_id BR_R002 --gt_points_file example/input/truth/point_based_annotations.geojson --sm_dir example/input/proposals/ --rm_path example/input/truth/region_models/BR_R002.geojson --output_dir example/output/point/

# evaluates the region BR_R002 using ground truth polygon annotations and "sweeping" the tau threshold across several values
python -m iarpa_smart_metrics.run_evaluation --roi BR_R002 --sequestered_id BR_R002 --gt_dir example/input/truth/site_models/ --sm_dir example/input/proposals/ --rm_path example/input/truth/region_models/BR_R002.geojson --output_dir example/output/poly/ --tau 0.01 --tau 0.1 --tau 0.2 --tau 0.3 --tau 0.4 --tau 0.5
# 0.01 is the user-determined "default" value for the tau threshold, because it is supplied first (and not because it is the smallest value)
```

### Sweeping Thresholds

Some of the [command line arguments](#command-line-arguments) represent configurable thresholds that are used to determine the associations between the proposals and the ground truth annotations. Such arguments can be specified multiple times, in order to "sweep" the threshold and compute the output metrics across a range of threshold values.

* A threshold is considered to be "swept" if 2 or more values are specified for that threshold. A threshold with only 1 specified value, or no specified values (in which case a hardcoded default value is substituted), are not considered to be "swept."

* If only 1 threshold is swept, the test harness will compute metrics at every value that is specified for that threshold.

* If 2 thresholds are swept, the test harness will compute metrics for every combination of the values that are specified for those 2 thresholds.

* If more than 2 thresholds are swept, the test harness will not compute metrics for every combination of values, in order to avoid a combinatorial explosion. Instead, the test harness will consider every possible 2-element pairing of the thresholds and sweep every combination of their specified values, while holding every other threshold constant at its user-determined "default" value, which is whichever of the multiple values for that threshold is specified first in the user's command line arguments. (This is not necessarily the same value as the threshold's hardcoded default value in the test harness code.)

* If 2 or more thresholds are swept, the number of unique threshold combinations that the test harness will consider can be computed with the following script, in which the variable-length command line arguments are the numbers of user-specified values being swept for each threshold:
```
from itertools import combinations
import sys

"""Usage:
# Input: the number of values being swept for each threshold
# Output: the total number of unique combinations of the values that the test harness will consider

# Sweep 5 thresholds, each with the following number of values:
$ python script.py 3 5 6 6 3
144

# Sweep 4 thresholds, each with the following number of values:
$ python script.py 3 5 6 6
110
"""

def main():

    vals = [int(arg) for arg in sys.argv[1:]]
    if len(vals) > 1:
        pairs = combinations(vals, 2)

        # the formula for computing the output:
        count = sum([pair[0]*pair[1] for pair in pairs]) - (len(vals) - 2)*(sum(vals) - len(vals)) - len(vals)*(len(vals) - 1)/2 + 1
        print(int(count))

    else:
        print("At least 2 values in the list are required")

main()
```

#### Thresholds for [proposals](#proposed-site-models) that can be swept:
* min_proposal_area
* confidence

#### Thresholds for [polygon-based evaluation](#polygon-based-evaluation) that can be swept:
* tau
* rho
* temporal_iop
* temporal_iot
* transient_temporal_iop
* transient_temporal_iot

#### Thresholds for [point-based evaluation](#point-based-evaluation) that can be swept:
* min_spatial_distance
* central_spatial_distance
* max_spatial_distance
* min_temporal_distance
* central_temporal_distance
* max_temporal_distance

## Example Input and Output Files

See the descriptions for the [example](example/), which includes example input and output files.

## Command Line Arguments

### Region of Interest
| Field                          | Description    | Type                                                     | Required                                                      | Default                                                                                                                 |
|-------------------------------|------------|--------------------------------------------------------------|----------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------|
| roi|The ID of the region of interest that will be used for the evaluation. For polygon-based evaluation, this value is used to find and filter annotation files in the input directories `gt_dir` and `sm_dir`, by searching for annotations with the `roi` argument in the filename. For point-based evaluation, this value is used to filter point annotations in the `gt_points_file` that have the `roi` argument in their site ID. <br><br> If evaluating a region that contains ground truth sites that share the same 2-letter country code but not the full region ID, use the country code as the `roi`, so that these truth sites are not filtered out. <br><br> If the `roi` is not specified, then every annotation in `gt_dir`, `gt_points_file`, and `sm_dir` will be loaded into memory before it is compared to the region model boundary, which may be inefficient.    | String | No | `""` (empty string)
| sequestered_id | An alias for the `roi`, if a sequestered region is being evaluated. Used to sanitize the test harness outputs by replacing all mentions of the `roi` value in them with the `sequestered_id`. If sanitization is not necessary, simply specify the same value for `sequestered_id` as for `roi`.| String | Yes |
| rm_path |The path to the region model geojson annotation file. The test harness will only evaluate the proposals against ground truth sites that are spatially located within the bounds of the region model polygon. In addition, the region model annotation may or may not contain site summaries (a "full" or "empty" region model, respectively). If the region model annotation contains site summaries, the test harness will only evaluate the proposals against ground truth sites specified by `gt_dir` or `gt_points_file` that are also listed in the region model site summaries. | String |Yes|

### Ground Truth Annotations
| Field                          | Description    | Type                                                     | Required                                                      | Default                                                                                                                 |
|-------------------------------|------------|--------------------------------------------------------------|----------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------|
| gt_dir |Ground truth directory: the path to an S3 directory or a local directory containing ground truth geojson annotations named `*{roi}*.geojson` <br><br> Used for polygon-based evaluation.| String |`gt_dir` or `gt_points_file` is required | `""` (empty string)
| gt_points_file | The path to a geojson of point annotations. <br><br> Used for point-based evaluation.| String | `gt_dir` or `gt_points_file` is required | `None`
| gt_whitelist | Only evaluate ground truth sites that are of the specified whitelist status types. Ground truth sites that are filtered out will still appear in `gt_sites.csv` but will not be evaluated. <br><br>Multiple values can be specified by using the argument multiple times. | String | No | `[]` (empty list) |
| gt_blacklist | Do not evaluate any ground truth sites that are of the specified blacklist status types. Ground truth sites that are filtered out will still appear in `gt_sites.csv` but will not be evaluated.<br><br>Multiple values can be specified by using the argument multiple times. | String | No | `[]` (empty list) |

### Proposed Site Models
| Field                          | Description    | Type                                                     | Required                                                      | Default                                                                                                                 |
|-------------------------------|------------|--------------------------------------------------------------|----------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------|
| sm_dir |Site model directory: the path to an S3 directory or a local directory containing proposed site model geojson annotations named `*{roi}*.geojson`| String | Yes |
| sm_whitelist | Only evaluate proposed site models that are of the specified whitelist status types. Proposed site models that are filtered out will still appear in `sm_sites.csv` but will not be evaluated. <br><br>Multiple values can be specified by using the argument multiple times. | String | No | `["system_confirmed"]` <br><br> To specify an empty list (for example, if using ground truth annotations as proposals), pass the empty string `""` to this parameter. |
| sm_blacklist | Do not evaluate any proposed site models that are of the specified blacklist status types. Proposed site models that are filtered out will still appear in `sm_sites.csv` but will not be evaluated. <br><br>Multiple values can be specified by using the argument multiple times.| String | No | `[]` (empty list) |
| min_proposal_area | The minimum area of a proposed site model (square meters). Proposals smaller than this threshold will be ignored. <br><br>Multiple values can be specified by using the argument multiple times.| Float | No | `0.0`
| confidence | Minimum confidence score required for a proposal to be considered for association with the truth sites. Proposals with a score less than this threshold will be ignored. Used to filter out low-confidence proposals and increase precision. <br><br>Multiple values can be specified by using the argument multiple times.| Float | No | `0.0`
| proposal_bounded_filter | Subselects proposed site models according to their [temporal bounds relative to the region model](./example/README.md#performance-metric-subsets) (e.g., ABCDE, CD, C). If not specified, all proposals will be included in the evaluation by default. | String | No | `None`

### Polygon-based Evaluation
| Field                          | Description    | Type                                                     | Required                                                      | Default                                                                                                                 |
|-------------------------------|------------|--------------------------------------------------------------|----------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------|
| activity | Subselects ground truth site stacks according to their [activity duration relative to the region model](./example/README.md#performance-metric-subsets).<br><br>`completed` computes metrics only on the subset of site stacks that have reached `Post Construction`. <br><br>`partial` computes metrics only on the subset of site stacks that have begun their activity but have not reached `Post Construction`. <br><br>`overall` computes metrics on all of the ground truth site stacks. | String | No | `None` (metrics will be computed for all 3 categories)
| tau | The association threshold (the minimum Intersection over Union score that is necessary for 2 polygons to match spatially). <br><br>Multiple values can be specified by using the argument multiple times.| Float | No | `0.2`
| rho | The site stack detection threshold (the minimum proportion of a ground truth site stack's polygons that must be spatially matched with a proposed site model in order for the truth site to be detected). A truth polygon can only be spatially matched with a proposed polygon that has the same observation date or an older observation date. Note that if a ground truth site stack's observations are distributed unevenly across its temporal duration, the site's temporal intersection with a proposal might be dissimilar to its detection score with that proposal, which is the proportion that is compared to the rho threshold. Also note that some truth sites only have 2 observations, so a rho threshold > 0.5 would require that a proposal has at least one observation that occurs on or before the oldest truth observation in order for it to detect such a truth site. <br><br>Multiple values can be specified by using the argument multiple times.|Float | No | `0.5`
| temporal_iop | Temporal Intersection over Proposal (IoP) threshold, used for measuring temporal overlap for site association. <br><br>Multiple values can be specified by using the argument multiple times.| Float | No | `0.1`
| temporal_iot | Temporal Intersection over Truth threshold (IoT), used for measuring temporal overlap for site association. <br><br>Multiple values can be specified by using the argument multiple times.| Float | No | `0.2`
| transient_temporal_iop | The temporal IoP threshold used for transient event association. <br><br>Multiple values can be specified by using the argument multiple times.| Float | No | `0.1`
| transient_temporal_iot | The temporal IoT threshold used for transient event association. <br><br>Multiple values can be specified by using the argument multiple times.| Float | No | `0.2`
| small_site_threshold | All truth sites with an area (square meters) less than this threshold will have their status changed to `ignore`.| Integer | No | `9000`
| parallel/serial |Spawn multiple processes to speed up the geospatial calculations and site stack comparisons in `compare_stacks()`. Multiprocessing will be used by default, if no flag is specified. If encountering unexpected outputs, try running the test harness in `--serial` mode in order to reveal error messages hidden in the subprocesses and aid with debugging.| optional flag |No | `--parallel`

### Point-based Evaluation
| Field                          | Description    | Type                                                     | Required                                                      | Default                                                                                                                 |
|-------------------------------|------------|--------------------------------------------------------------|----------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------|
| min_spatial_distance | The maximimum distance (meters) between a truth point and the closest point in the proposal polygon in order for them to be associated. <br><br>Multiple values can be specified by using the argument multiple times. | Integer | Yes | `100`
| central_spatial_distance | The maximimum distance (meters) between a truth point and the centroid of the proposal polygon in order for them to be associated. <br><br>Multiple values can be specified by using the argument multiple times. <br><br>To disable the threshold, simply do not specify an argument.| Integer | No | `None`
| max_spatial_distance | The maximimum (meters) distance between a truth point and the furthest point in the proposal polygon in order for them to be associated. <br><br>Multiple values can be specified by using the argument multiple times.  <br><br>To disable the threshold, simply do not specify an argument.| Integer | No | `None`
| min_temporal_distance | The maximimum distance (m) between a truth point date and the closest point in the proposal polygon date range in order for them to be associated. <br><br>Multiple values can be specified by using the argument multiple times.  <br><br>To disable the threshold, simply do not specify an argument.| Integer | No | `None`
| central_temporal_distance | The maximimum distance (m) between a truth point date and the centroid of the proposal polygon date range in order for them to be associated. <br><br>Multiple values can be specified by using the argument multiple times.  <br><br>To disable the threshold, simply do not specify an argument.| Integer | No | `None`
| max_temporal_distance | The maximimum distance (m) between a truth point date and the furthest point in the proposal polygon date range in order for them to be associated. <br><br>Multiple values can be specified by using the argument multiple times.  <br><br>To disable the threshold, simply do not specify an argument.| Integer | No | `None`

### Outputs
| Field                          | Description    | Type                                                     | Required                                                      | Default                                                                                                                 |
|-------------------------------|------------|--------------------------------------------------------------|----------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------|
| output_dir |The path to a local directory where output files will be saved.| String | Yes|
| s3_output_dir |The path to an S3 directory where output files will be uploaded.| String | No| `None`
| viz/no_viz | Generate the region visualization when calculating metrics. | optional flag |No | `--viz`
| background_img | The path to a georeferenced image to display the region visualization on. | String | No | `None`
| logfile | The path to the output log file, used for debugging. | String | No | `debug.log`
| loglevel | The threshold used for the [Python logger](https://docs.python.org/3/library/logging.html#logging-levels). | String or Integer | No | `INFO`
