#!/usr/bin/env python
# © 2025 The Johns Hopkins University Applied Physics Laboratory LLC.  This material was sponsored by the U.S. Government under contract number 2020-20081800401.
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the “Software”), to deal in
# the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.


# custom JHU/APL module for SMART metric evaluation
from iarpa_smart_metrics.commons import as_local_path
from iarpa_smart_metrics.evaluation import Evaluation, _evaluation_global_preferences

# public packages
from glob import glob
import boto3
import click
from typing import List
import os
import logging
import warnings

# connect to AWS (only necessary if saving files to S3)
CLIENT = boto3.client("s3")


# command line arguments
@click.command()
# Region of interest
@click.option("--roi", default="", help="the ID of the region of interest")
@click.option(
    "--sequestered_id",
    required=True,
    help="an alias for the ID of the region, if the region is sequestered",
)
@click.option("--rm_path", required=True, help="path to a region model geojson annotation file")
# Ground truth annotations
@click.option(
    "--gt_dir",
    default="",
    help="path to a directory of ground truth site stack geojson annotation files",
)
@click.option(
    "--gt_points_file",
    default=None,
    help="path to a geojson annotation file of ground truth points",
)
@click.option(
    "--gt_whitelist",
    multiple=True,
    default=[],
    help="list of allowed ground truth site types (other site types will not be evaluated)",
)
@click.option(
    "--gt_blacklist",
    multiple=True,
    default=[],
    help="list of forbidden ground truth site types (these site types will not be evaluated)",
)
# Proposed site models
@click.option(
    "--sm_dir",
    required=True,
    help="path to a directory of proposed site model geojson annotation files",
)
@click.option(
    "--sm_whitelist",
    multiple=True,
    default=["system_confirmed"],
    help="list of allowed proposed site types (other site types will not be evaluated)",
)
@click.option(
    "--sm_blacklist",
    multiple=True,
    default=[],
    help="list of forbidden proposed site types (these site types will not be evaluated)",
)
@click.option(
    "--min_proposal_area",
    multiple=True,
    default=[0.0],
    type=click.FloatRange(min=0, clamp=True),
    help="minimum area of a proposed site model in square meters",
)
@click.option(
    "--confidence",
    "-c",
    multiple=True,
    default=[0.0],
    type=click.FloatRange(0, 1, clamp=True),
    help="minimum confidence score of a proposed site model",
)
@click.option(
    "--proposal_bounded_filter",
    default=None,
    help="subselects proposed site models according to their temporal bounds relative to the region model (e.g., ABCDE, CD, C)",
)
# Polygon-based evaluation
@click.option(
    "--activity",
    default=None,
    help="subselects the ground truth sites based on their activity duration relative to the region model (completed, partial, overall)",
)
@click.option(
    "--tau",
    multiple=True,
    default=[0.2],
    type=click.FloatRange(0, 1, clamp=True),
    help="association threshold (minimum similarity score for matching polygons)",
)
@click.option(
    "--rho",
    multiple=True,
    default=[0.5],
    type=click.FloatRange(0, 1, clamp=True),
    help="site detection threshold (minimum proportion of matching polygons that is necessary to match 2 site stacks)",
)
@click.option(
    "--temporal_iop",
    "--tiop",
    multiple=True,
    default=[0.1],
    type=click.FloatRange(0, 1, clamp=True),
    help="intersection over proposal detection threshold for temporal range association",
)
@click.option(
    "--temporal_iot",
    "--tiot",
    multiple=True,
    default=[0.2],
    type=click.FloatRange(0, 1, clamp=True),
    help="intersection over truth detection threshold for temporal range association",
)
@click.option(
    "--transient_temporal_iop",
    "--ttiop",
    multiple=True,
    default=[0.1],
    type=click.FloatRange(0, 1, clamp=True),
    help="intersection over proposal detection threshold for transient event temporal range association",
)
@click.option(
    "--transient_temporal_iot",
    "--ttiot",
    multiple=True,
    default=[0.2],
    type=click.FloatRange(0, 1, clamp=True),
    help="intersection over truth detection threshold for transient event temporal range association",
)
@click.option(
    "--small_site_threshold",
    default=9000,
    type=click.IntRange(min=0, clamp=True),
    help="minimum area of a truth site in square meters",
)
@click.option(
    "--parallel/--serial",
    default=True,
    help="spawns multiple processes to speed up geospatial calculations for site stack comparisons",
)
# Point-based evaluation
@click.option(
    "--min_spatial_distance",
    "--minsd",
    multiple=True,
    default=[100],
    type=int,
    help="geometric distance (meters) from the ground truth point to the nearest point in the geometric union of the proposed site model's temporally bounded polygon observations",
)
@click.option(
    "--central_spatial_distance",
    "--censd",
    "--midsd",
    multiple=True,
    default=[None],
    type=int,
    help="geometric distance (meters) from the ground truth point to the center of mass (centroid) of the geometric union of the proposed site model's temporally bounded polygon observations",
)
@click.option(
    "--max_spatial_distance",
    "--maxsd",
    multiple=True,
    default=[None],
    type=int,
    help="geometric distance (meters) from the ground truth point to the furthest point on the polygon boundary of the geometric union of the proposed site model's temporally bounded polygon observations",
)
@click.option(
    "--min_temporal_distance",
    "--mintd",
    multiple=True,
    default=[None],
    type=int,
    help="number of calendar days between the ground truth point date and the nearest date in the proposal's temporal date range",
)
@click.option(
    "--central_temporal_distance",
    "--centd",
    "--midtd",
    multiple=True,
    default=[None],
    type=int,
    help="number of calendar days between the ground truth point date and the middle date in the proposal's temporal date range",
)
@click.option(
    "--max_temporal_distance",
    "--maxtd",
    multiple=True,
    default=[None],
    type=int,
    help="number of calendar days between the ground truth point date and the furthest date in the proposal's temporal date range",
)
# Outputs
@click.option(
    "--output_dir",
    required=True,
    help="path to a directory where output files will be saved",
)
@click.option(
    "--s3_output_dir",
    default=None,
    help="path to an S3 directory where the output files will be uploaded (must start with s3://)",
)
@click.option("--viz/--no_viz", default=True, help="enable/disable region visualizations")
@click.option(
    "--background_img",
    default=None,
    help="path to a background image to plot region visualizations on",
)
@click.option("--logfile", default="debug.log", help="path to the output log file")
@click.option("--loglevel", default="INFO", help="logging level")
def main(
    roi: str = "",
    sequestered_id: str = "",
    rm_path: str = "",
    gt_dir: str = "",
    gt_points_file: str = None,
    gt_whitelist: List[str] = [],
    gt_blacklist: List[str] = [],
    sm_dir: str = "",
    sm_whitelist: List[str] = ["system_confirmed"],
    sm_blacklist: List[str] = [],
    min_proposal_area: List[float] = [0.0],
    confidence: List[float] = [0.0],
    proposal_bounded_filter: str = None,
    activity: str = None,
    tau: List[float] = [0.2],
    rho: List[float] = [0.5],
    temporal_iop: List[float] = [0.1],
    temporal_iot: List[float] = [0.2],
    transient_temporal_iop: List[float] = [0.1],
    transient_temporal_iot: List[float] = [0.2],
    small_site_threshold: int = 9000,
    parallel: bool = True,
    min_spatial_distance: List[int] = [100],
    central_spatial_distance: List[int] = [None],
    max_spatial_distance: List[int] = [None],
    min_temporal_distance: List[int] = [None],
    central_temporal_distance: List[int] = [None],
    max_temporal_distance: List[int] = [None],
    output_dir: str = "output",
    s3_output_dir: str = None,
    viz: bool = True,
    background_img: str = None,
    logfile: str = "debug.log",
    loglevel: str = "INFO",
):
    """
    Runs an evaluation of the proposed site models against the ground truth annotations for a specific region of interest.

    Step 1. Computes the similarity scores for each possible association of the ground truth sites and the proposed sites
    Step 2. Computes BAS and AC/AP metrics for the specified type of ground truth activity, based on the optimal site associations

    Parameters:

        # Region of interest
        roi (str): The region of interest ID.
        sequestered_id (str): The alias for a sequestered region ID.
        rm_path (str): The path to a region model geojson annotation file.

        # Ground truth annotations
        gt_dir (str): The path to a directory of ground truth site stack geojson annotation files.
        gt_points_file (str): The path to a geojson annotation file of ground truth points.
        gt_whitelist (List[str]): The list of permissible ground truth site types (other site types will not be evaluated).
        gt_blacklist (List[str]): The list of forbidden ground truth site types (these site types will not be evaluated).

        # Proposed site models
        sm_dir (str): The path to a directory of proposed site model geojson annotation files.
        sm_whitelist (List[str]): The list of permissible proposed site types (other site types will not be evaluated).
        sm_blacklist (List[str]): The list of forbidden proposed site types (these site types will not be evaluated).
        min_proposal_area (List[float]): The minimum area of a proposal in square meters.
        confidence (List[float]): The minimum confidence score of a proposal.
        proposal_bounded_filter (str): Subselects proposed site models according to their temporal bounds relative to the region model (e.g., ABCDE, CD, C).

        # Polygon-based evaluation
        activity (str): The type of activity metric to use for temporal unbounded sites.
        tau (List[float]): The association threshold (minimum similarity score for matching polygons).
        rho (List[float]): The site detection threshold (minimum proportion of matching polygons that is necessary to match 2 site stacks).
        temporal_iop (List[float]): The intersection over proposal detection threshold for temporal range association.
        temporal_iot (List[float]): The intersection over truth detection threshold for temporal range association.
        transient_temporal_iop (List[float]): The intersection over proposal detection threshold for transient event temporal range association.
        transient_temporal_iot (List[float]): The intersection over truth detection threshold for transient event temporal range association.
        small_site_threshold (int): The minimum area of a truth site in square meters.
        parallel (bool): Spawn multiple processes to speed up geospatial calculations for site stack comparisons.

        # Point-based evaluation
        min_spatial_distance (List[int]): The geometric distance (meters) from the ground truth point to the nearest point in the geometric union of the proposed site model's temporally bounded polygon observations.
        central_spatial_distance (List[int]): The geometric distance (meters) from the ground truth point to the center of mass (centroid) of the geometric union of the proposed site model's temporally bounded polygon observations.
        max_spatial_distance (List[int]): The geometric distance (meters) from the ground truth point to the furthest point on the polygon boundary of the geometric union of the proposed site model's temporally bounded polygon observations.
        min_temporal_distance (List[int]): The number of calendar days between the ground truth point date and the nearest date in the proposal's temporal date range.
        central_temporal_distance (List[int]): The number of calendar days between the ground truth point date and the middle date in the proposal's temporal date range.
        max_temporal_distance (List[int]): The number of calendar days between the ground truth point date and the furthest date in the proposal's temporal date range.

        # Outputs
        output_dir (str): The path to a directory where output files will be saved.
        s3_output_dir (str): The path to an S3 directory where the output files will be uploaded (must start with s3://).
        viz (bool): Enable/disable region visualizations.
        background_img (str): The path to a background image to plot region visualizations on.
        logfile (str): The path to the log file.
        loglevel (str): The logging level.

    Returns:
        None
    """

    # initialize outputs
    os.makedirs(output_dir, exist_ok=True)
    _evaluation_global_preferences(
        output_dir=output_dir,
        log_level=loglevel,
        log_file=logfile,
        oldval=roi,
        newval=sequestered_id,
    )

    # ground truth polygon annotations
    if gt_dir:
        gt_dir = as_local_path(gt_dir, "annotations/truth/", reg_exp=f".*{roi}.*_[0-9]+.*\.geojson")
        gt_files = glob(f"{gt_dir}/*{roi}*.geojson")
    # ground truth point annotations
    elif gt_points_file:
        gt_files = []
        local_path = as_local_path(gt_points_file, "annotations/points/")
        if os.path.isdir(local_path):
            gt_points_file = os.path.join(local_path, os.path.basename(gt_points_file))
        elif os.path.isfile(local_path):
            gt_points_file = local_path
    else:
        raise FileNotFoundError(
            f"Ground truth directory --gt_dir {gt_dir} not found and ground truth points file --gt_points_file {gt_points_file} not found. Specify one or the other."
        )

    # site model polygon annotations
    sm_files = []
    try:
        sm_dir = as_local_path(sm_dir, "annotations/proposals/", reg_exp=f".*{roi}.*_[0-9]+.*\.geojson")
        sm_files = glob(f"{sm_dir}/*{roi}*.geojson")
    except Exception:
        logging.critical("Failed to locate site models directory")
    if len(sm_files) == 0:
        logging.critical(f"No geojson annotations were found at {sm_dir}. Check the path.")

    # instantiate the Evaluation object
    evaluation = Evaluation(
        gt_files,
        gt_whitelist,
        gt_blacklist,
        sm_files,
        sm_whitelist,
        sm_blacklist,
        rm_path,
        roi,
        tau,
        rho,
        confidence,
        min_spatial_distance,
        central_spatial_distance,
        max_spatial_distance,
        min_temporal_distance,
        central_temporal_distance,
        max_temporal_distance,
        temporal_iop,
        temporal_iot,
        transient_temporal_iop,
        transient_temporal_iot,
        small_site_threshold,
        4326,
        min_proposal_area,
        output_dir,
        parallel=parallel,
        num_processes=None,
        sequestered_id=sequestered_id,
        gt_points_file=gt_points_file,
        proposal_bounded_filter=proposal_bounded_filter,
    )

    # 1. get the similarity scores for each possible association of the ground truth sites and the proposed sites
    if gt_points_file:
        # point-based evaluation
        evaluation.compare_points()
    else:
        if not gt_files:
            logging.warning(f"No geojson annotations were found at {gt_dir}. Check the path.")
        # polygon-based evaluation
        evaluation.compare_stacks()

    # 2. compute metrics for the specified subset of ground truth activity
    if gt_points_file:
        activities = ["overall"]
    elif activity:
        activities = [activity]
    else:
        activities = ["overall", "completed", "partial"]
    for activity_type in activities:
        # 2a. adjust the effective status of each truth site based on the subset of activity
        evaluation.update_gt_statuses(activity_type, small_site_threshold)

        # create the broad area search output directory
        evaluation.bas_dir = f"{output_dir}/{activity_type}/bas"
        os.makedirs(evaluation.bas_dir, exist_ok=True)

        # 2b. compute broad area search metrics
        evaluation.associate_sites(
            activity_type,
        )

        # 2c. compute phase activity classification and prediction metrics
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", "Mean of empty slice")
            warnings.filterwarnings("ignore", "invalid value encountered in divide")
            warnings.filterwarnings("ignore", "invalid value encountered in scalar divide")
            warnings.filterwarnings("ignore", "Degrees of freedom <= 0 for slice")
            if gt_files:
                evaluation.calc_activity_metrics(activity_type)

        # 2d. plot the annotations based on the broad area search scores
        if viz:
            evaluation.visualize_region(background_img=background_img)
            evaluation.visualize_region(background_img=background_img, simple=False)

    # save output files to S3
    if s3_output_dir is not None and s3_output_dir.startswith("s3://"):
        bucket = s3_output_dir.split("/")[2]
        prefix = "/".join(s3_output_dir.split("/")[3:])
        for root, _, files in os.walk(output_dir):
            for filename in files:
                local_path = os.path.join(root, filename)
                relative_path = os.path.relpath(local_path, output_dir)
                s3_path = os.path.join(prefix, relative_path)
                CLIENT.upload_file(local_path, bucket, s3_path)

    logging.info("All done.")


if __name__ == "__main__":
    main()
