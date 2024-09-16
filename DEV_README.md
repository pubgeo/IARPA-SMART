# SMART TA-2 Evaluation Metrics

Copyright 2024

The Johns Hopkins University Applied Physics Laboratory and BlackSky Inc.

## Contact

Send email to: iarpa.smart@jhuapl.edu

## Requirements

Requires Python 3.11

Supported operating systems: Unix and macOS

## Installation

Install the `iarpa_smart_metrics` module using pip:
```cd src```
```pip3 install -e .```


## Usage Examples

The testing script utilizes the Python [click](https://pypi.org/project/click/) package. Arguments are specified using two dashed lines `--` before the variable. See examples below:

```bash
# gets command line argument descriptions
python -m iarpa_smart_metrics.run_evaluation --help

# evaluates BR_R002
python -m iarpa_smart_metrics.run_evaluation --roi BR_R002 --sequestered_id BR_R002 --gt_dir example/input/truth/site_models/ --sm_dir example/input/proposals/ --rm_dir example/input/truth/region_models/ --output_dir example/output/ --tau 0.2 --rho 0.5 --temporal_iot 0.2 --temporal_iop 0.1
```

## Arguments

| Field                          | Description    | Type                                                     | Required                                                      | Default                                                                                                                 |
|-------------------------------|------------|--------------------------------------------------------------|----------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------|
| roi| Name of the region of interest that will be evaluated. This value is used to find the annotation files for the corresponding region in the input directories.    | String | Yes | None
| tau | An association threshold (minimum similarity score that is necessary to match 2 polygons). | Float | No | 0.2
| rho | A site detection threshold (minimum proportion of matching polygons that is necessary to match 2 site stacks). |Float | No | 0.5
| confidence | Minimum confidence score required for a proposal to be considered for association with the truth sites. Used to filter out low-confidence proposals and increase precision. | Float | No | 0.0
| temporal_iop | Temporal Intersection over Proposal (IoP) threshold - used for measuring temporal overlap for site association. | Float | No | 0.1
| temporal_iot | Temporal Intersection over Truth threshold (IoT) - used for measuring temporal overlap for site association. | Float | No | 0.2
| transient_temporal_iop | The temporal IoP threshold used for transient event association. | Float | No | 0.1
| transient_temporal_iot | The temporal IoT threshold used for transient event association. | Float | No | 0.2
| small_site_threshold | All truth sites with an area (sq m) less than this threshold will have their status changed to `ignore`. | Integer | No | 9000
| activity | The category of truth sites for which metrics are computed. <br><br>`completed` computes metrics only on the subset of sites that have reached `Post Construction`. <br><br>`partial` computes metrics only on the subset of truth sites that have begun their activity but have not reached `Post Construction`. <br><br>`overall` computes metrics on all truth sites. | String | No | None
| sequestered_id | An alias for the `roi`, if a sequestered region is being evaluated. Used to replace all mentions of the `roi` value in the test harness outputs. If a `sequestered_id`, is not given, the original `roi` will be used in the output files. | String | No | None
| gt_dir |Ground truth directory: existing path to an S3 path or local directory containing ground truth geojson annotations named `*{roi}*.geojson`. | String |Yes |
| rm_dir |Region model directory: existing path to an S3 path or local directory containing region model geojson files named `*{roi}*.geojson`. | String |Yes|
| sm_dir |Site model directory: Existing path to an S3 path or local directory containing proposed site model geojson annotations named `*{roi}*.geojson`.| String | Yes |
| output_dir |Output directory: Path to an S3 path or local directory where output files will be saved.| String | No| ```output/{roi}```
|  parallel/serial |Spawn multiple processes to speed up the geospatial calculations and site stack comparisons in `compare_stacks()`. Multiprocessing will be used by default, if no flag is specified.| optional flag |No |  --parallel
| logfile | Path to the output log file, used for debugging. | String | No | debug.log
| loglevel | Threshold used for the [Python logger](https://docs.python.org/3/library/logging.html#logging-levels). | String or Integer | No | INFO

## Output

See the descriptions for the [example outputs](example/output.compare/).
