#!/usr/bin/env python
# © 2024 The Johns Hopkins University Applied Physics Laboratory LLC.  This material was sponsored by the U.S. Government under contract number 2020-20081800401.
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the “Software”), to deal in
# the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.


# custom JHU/APL module for SMART metric evaluation
from iarpa_smart_metrics.commons import DEV, as_local_path
from iarpa_smart_metrics.evaluation import Evaluation, _evaluation_global_preferences

# database functionality is currently only supported in developer mode
if DEV:
    from iarpa_smart_metrics.smart_database.api import SmartDatabaseApi

# public packages
from glob import glob
import boto3
import click
from datetime import datetime
import os
import logging
import warnings

# connect to AWS (only necessary if downloading files from S3)
CLIENT = boto3.client("s3")

# command line arguments
@click.command()
@click.option("--roi", required=True, help="name of the region of interest")
@click.option("--tau", default=None, type=float, help="association threshold (minimum similarity score for matching polygons), in the interval [0.0, 1.0]")
@click.option("--rho", default=None, type=float, help="site detection threshold (minimum proportion of matching polygons that is necessary to match 2 site stacks), in the interval [0.0, 1.0]")
@click.option("--confidence", "-c", multiple=True, default=None, help="threshold for the minimum confidence score of a proposal, in the interval [0.0, 1.0]")
@click.option("--temporal_iop", default=0.1, type=float, help="intersection over proposal detection threshold for temporal range association, in the interval [0.0, 1.0]")
@click.option("--temporal_iot", default=0.2, type=float, help="intersection over truth detection threshold for temporal range association, in the interval [0.0, 1.0]")
@click.option("--transient_temporal_iop", default=0.1, type=float, help="intersection over proposal detection threshold for transient event temporal range association, in the interval [0.0, 1.0]")
@click.option("--transient_temporal_iot", default=0.2, type=float, help="intersection over truth detection threshold for transient event temporal range association, in the interval [0.0, 1.0]")
@click.option("--small_site_threshold", default=9000, type=int, help="set minimum small site threshold, in square meters")
@click.option("--gt_dir", required=True, help="path to a directory of ground truth site geojson annotations")
@click.option("--rm_dir", required=True, help="path to a directory of ground truth region model geojson annotations")
@click.option("--sm_dir", required=True, help="path to a directory of proposed site model geojson annotations")
@click.option("--output_dir", help="path to a directory where output files will be saved")
@click.option("--parallel/--serial", default=True, help="spawn multiple processes to speed up geospatial calculations")
@click.option("--activity", default=None, help="the type of ground truth activity to use to compute metrics (e.g. completed, partial, overall)")
@click.option("--sequestered_id", required=True, help="an alias for a sequestered region")
@click.option("--loglevel", default="INFO", help="Logging level (e.g. info, debug)")
@click.option("--logfile", default="debug.log", help="Output log file path")

def main(
    roi,
    #crs,
    tau,
    rho,
    confidence,
    temporal_iop,
    temporal_iot,
    transient_temporal_iop,
    transient_temporal_iot,
    small_site_threshold,
    #sweep_tau,
    #sweep_rho,
    #sweep_min_area,
    #sweep_confidence,
    gt_dir,
    rm_dir,
    sm_dir,
    #image_dir,
    output_dir,
    #eval_num,
    #eval_run_num,
    # eval_increment_num,
    #performer,
    #batch_mode,
    #increment_start_date,
    #increment_end_date,
    #dag_run_id,
    #db_conn_str,
    parallel,
    activity,
    sequestered_id,
    #viz_region,
    #viz_slices,
    #viz_detection_table,
    #viz_comparison_table,
    #viz_associate_metrics,
    #viz_activity_metrics,
    #viz,
    loglevel,
    logfile,
):

    os.makedirs(output_dir, exist_ok=True)
    _evaluation_global_preferences(
        output_dir=output_dir,
        log_level=loglevel,
        log_file=logfile,
        oldval=roi,
        newval=sequestered_id,
    )


    # Check value range for parameters
    if tau and (0 > tau or tau > 1):
        raise ValueError("--tau must be a value between 0 & 1")
    if rho and (0 > rho or rho > 1):
        raise ValueError("--rho must be a value between 0 & 1")
    if confidence and (0 > confidence or confidence > 1):
        raise ValueError("--confidence must be a value between 0 & 1")
    if temporal_iop and (0 > temporal_iop or temporal_iop > 1):
        raise ValueError("--temporal_iop must be a value between 0 & 1")
    if temporal_iot and (0 > temporal_iot or temporal_iot > 1):
        raise ValueError("--temporal_iot must be a value between 0 & 1")
    if transient_temporal_iop and (0 > transient_temporal_iop or transient_temporal_iop > 1):
        raise ValueError("--transient_temporal_iop must be a value between 0 & 1")
    if transient_temporal_iot and (0 > transient_temporal_iot or transient_temporal_iot > 1):
        raise ValueError("--transient_temporal_iot must be a value between 0 & 1")

    # default path to ground truth annotations. get a list of filepaths
    gt_dir = as_local_path(gt_dir, "annotations/truth/", reg_exp=f".*{roi}_[0-9]+.*\.geojson")
    
    # look for geojson files within the directory
    gt_files = glob(f"{gt_dir}/*{roi}*.geojson")
    if len(gt_files) == 0:
        raise FileNotFoundError(f"No geojson annotations were found at {gt_dir}. Check the path.")

    # default path to site model annotations. get a list of filepaths
    # look for geojson files within the directory
    sm_files = []
    try:
        sm_dir = as_local_path(
            sm_dir,
            f"annotations/proposals/{roi}/",
            reg_exp=f".*{roi}_[0-9]+.*\.geojson",
        )
        sm_files = glob(f"{sm_dir}/*{roi}*.geojson")
    except Exception:
        logging.critical("Failed to locate site models directory")
    if len(sm_files) == 0:
        logging.critical(f"No geojson annotations were found at {sm_dir}. Check the path.")

    # default path to a region model. get a list of filepaths
    rm_dir = as_local_path(rm_dir, "annotations/region_models/", reg_exp=f".*{roi}.*.geojson")
    rm_files = glob(f"{rm_dir}/*{roi}*.geojson")
    if not rm_files:
        raise FileNotFoundError(f"No geojson annotations were found at {rm_dir}. Check the path.")

    # check directory paths
    if not os.path.exists(sm_dir):
        raise FileNotFoundError(f"No directory found --sm_dir {sm_dir}")
    if not os.path.exists(rm_dir):
        raise FileNotFoundError(f"No directory found --rm_dir {rm_dir}")
    if not os.path.exists(gt_dir):
        raise FileNotFoundError(f"No directory found --gt_dir {gt_dir}")

    # output paths
    output_dir = f"output/{roi}" if not output_dir else output_dir
    if output_dir is not None and output_dir.startswith("s3://"):
        s3_output_dir = output_dir
        output_dir = None
    else:
        s3_output_dir = None
    output_dir = f"output/{roi}" if not output_dir else output_dir

    # if DEV and db_conn_str:
    #     smart_database_api = SmartDatabaseApi(db_conn_str)
    # else:
    smart_database_api = None

    # instantiate the Evaluation object
    evaluation = Evaluation(
        gt_files,
        sm_files,
        rm_files[0],
        roi,
        #eval_num,
        #eval_run_num,
        #eval_increment_num,
        #performer,
        #batch_mode,
        #increment_start_date,
        #increment_end_date,
        #dag_run_id,
        "iou",
        tau,
        rho,
        confidence,
        temporal_iop,
        temporal_iot,
        transient_temporal_iop,
        transient_temporal_iot,
        small_site_threshold,
        4326, # default crs
        #sweep_tau,
        #sweep_rho,
        #sweep_min_area,
        #sweep_confidence,
        #image_dir,
        output_dir,
        smart_database_api=smart_database_api,
        parallel=parallel,
        num_processes=None,
        sequestered_id=sequestered_id,
    )

    # 1. get the similarity scores for each possible association of the site stacks
    evaluation.compare_stacks()

    # compute metrics for the specified subset of ground truth activity
    if activity:
        activities = [activity]
    else:
        activities = ["overall", "completed", "partial"]
    for activity_type in activities:
        # 2. adjust the effective status of each truth site based on the subset of activity
        evaluation.update_gt_statuses(activity_type, small_site_threshold)
        evaluation.bas_dir = f"{output_dir}/{activity_type}/bas"
        os.makedirs(evaluation.bas_dir, exist_ok=True)

        # 3. compute broad area search metrics
        evaluation.associate_stacks(activity_type)

        # 4. compute phase activity classification and prediction metrics
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", "Mean of empty slice")
            warnings.filterwarnings("ignore", "invalid value encountered in divide")
            warnings.filterwarnings("ignore", "invalid value encountered in scalar divide")
            warnings.filterwarnings("ignore", "Degrees of freedom <= 0 for slice")
            evaluation.calc_activity_metrics(activity_type)

    # save output files to S3
    if s3_output_dir is not None:
        bucket = s3_output_dir.split("/")[2]
        prefix = "/".join(s3_output_dir.split("/")[3:])
        for root, _, files in os.walk(output_dir):
            for filename in files:
                local_path = os.path.join(root, filename)
                relative_path = os.path.relpath(local_path, output_dir)
                s3_path = os.path.join(prefix, relative_path)
                CLIENT.upload_file(local_path, bucket, s3_path)

    #if smart_database_api:
    #    evaluation.complete_evaluation()
    #- REMOVE/turn off option - Database related

    logging.info("All done.")


if __name__ == "__main__":
    main()
