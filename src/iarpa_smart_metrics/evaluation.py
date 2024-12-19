# © 2024 The Johns Hopkins University Applied Physics Laboratory LLC.  This material was sponsored by the U.S. Government under contract number 2020-20081800401.
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the “Software”), to deal in
# the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# built-in modules
import os
from collections import defaultdict
from datetime import datetime
import multiprocessing as mp
from threading import Lock
import re
import warnings
import sys
import logging
from copy import deepcopy
import git
from glob import glob
from itertools import product
import psutil

import functools
import time
import uuid

# data packages
import numpy as np
import pandas as pd

import sklearn.metrics
from tqdm import tqdm

# geometry packages
import geojson
import geopandas as gpd
from shapely.geometry.polygon import Polygon
from shapely.geometry.multipolygon import MultiPolygon
from shapely.ops import unary_union

# visualization packages
import rasterio.warp
from rasterio import plot  # NOQA
import matplotlib.pyplot as plt

import fiona
from packaging.version import parse as Version
from iarpa_smart_metrics.commons import DEV

# database functionality is currently only supported in developer mode
if DEV:
    from iarpa_smart_metrics.smart_database.models import (
        Region,
        Site,
        Observation,
        ObservationComparison,
        EvaluationRun,
        EvaluationBroadAreaSearchMetric,
        EvaluationBroadAreaSearchDetection,
        EvaluationBroadAreaSearchProposal,
        EvaluationBroadAreaSearchFailedAssociation,
        EvaluationActivityClassificationMatrix,
        EvaluationActivityClassificationF1,
        EvaluationActivityClassificationPhase,
        EvaluationActivityClassificationTemporalError,
        EvaluationActivityClassificationTemporalIOU,
        EvaluationActivityPredictionTemporalError,
    )

FIONA_GE_1_9_0 = Version(fiona.__version__) >= Version("1.9.0")

# Global Status type lists
# these are the categories of annotation status types for the ground truth sites, grouped by how they are scored when they are associated
NEGATIVE_STATUS_TYPES = [
    "positive_excluded",
    "negative",
    "negative_unbounded",
    "transient_negative",
    "transient_excluded",
]
POSITIVE_STATUS_TYPES = [
    "positive",
    "positive_annotated",
    "positive_annotated_static",
    "positive_partial",
    "positive_partial_static",
    "positive_pending",
    "transient_positive",
    "transient_pending",
]
IGNORE_STATUS_TYPES = ["ignore", "positive_unbounded", "transient_ignore"]
POSITIVE_ACTIVITY_STATUS_TYPES = [
    "positive_annotated",
    "positive_partial",
    "positive_annotated_static",
    "positive_partial_static",
]
POSITIVE_UNBOUNDED_STATUS_TYPES = ["positive_unbounded"]
ANNOTATED_IGNORE_STATUS_TYPES = ["ignore", "transient_ignore"]
ANNOTATED_NEGATIVE_STATUS_TYPES = ["negative", "negative_unbounded", "transient_negative"]
POSITIVE_PARTIAL_STATUS_TYPES = ["positive_partial"]
POSITIVE_COMPLETE_STATUS_TYPES = [
    "positive",
    "positive_annotated",
    "positive_annotated_static",
    "positive_pending",
    "transient_positive",
    "transient_pending",
]  # POSITIVE_STATUS_TYPES - ["positive_partial", "positive_partial_static"]


def timer(func):
    """This is a function decorator that logs the time spent executing the decorated function."""
    @functools.wraps(func)
    def wrapper_timer(*args, **kwargs):
        start_time = time.perf_counter()
        value = func(*args, **kwargs)
        end_time = time.perf_counter()
        run_time = end_time - start_time
        if run_time >= 5:
            logging.debug(f"finished {func.__module__}.{func.__name__!r} {kwargs} in {run_time:.2f} sec, total = {timer.total}")
        else:
            logging.debug(f"finished {func.__name__!r} {kwargs} in {run_time:.4f} sec, total = {timer.total}")
        return value

    return wrapper_timer


timer.total = 0


def _evaluation_global_preferences(output_dir, log_level="INFO", log_file="debug.log", oldval=None, newval=None):
    """
    Previously these were global side effects.  They now live in a function so
    they can be explicitly called by a main script that uses this module.

    This function primarily configures the settings for the logging.
    Importantly, it removes sequestered region IDs from the log messages.
    """
    if isinstance(log_level, str):
        log_level = getattr(logging, log_level.upper())

    if os.path.dirname(log_file) == "":
        log_file = os.path.abspath(f"{output_dir}/{log_file}")

    log_name = log_file.split("/")[-1]
    log_name_datetime = log_name.split(".")[0] + "-" + datetime.now().strftime("%Y_%m_%d-%H_%M_%S") + ".log"
    log_file = log_file.replace(log_name, log_name_datetime)

    logger = logging.getLogger()
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(filename)s:%(funcName)s:%(lineno)d - %(message)s")
    logger.setLevel(logging.DEBUG)

    file_handler = logging.FileHandler(log_file)
    stream_handler = logging.StreamHandler(sys.stdout)

    file_handler.setFormatter(formatter)

    class NoSeqInfoFilter(logging.Filter):
        def filter(self, record):
            return oldval not in str(record) or oldval == newval

    logger.addFilter(NoSeqInfoFilter())
    stream_handler.setFormatter(formatter)

    file_handler.setLevel(logging.DEBUG)
    stream_handler.setLevel(log_level)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

    warnings.filterwarnings("ignore", message="Geometry is in a geographic CRS")

    try:
        pd.set_option("precision", 4)
    except pd.errors.OptionError:
        # More recent pandas
        pd.options.styler.format.precision = 4


class StackSlice:
    """Class definition for a slice (aka an observation) in a site model

    Attributes:
        df: a geopandas dataframe representing the observation, derived from the site model's geojson annotation file
        polygon: a shapely geometry representing the observation's spatial boundary or boundaries
        area: the area of the polygon in sq km
        boundary_flags: boolean flags that indicate whether the polygon geometry or geometries represent the site boundary (True) or subsites (False)
        date: the observation's calendar date (yyyy-mm-dd)
        source: the observation's image source
        score: the observation's confidence score, a float ranging from 0.0 (least confident) to 1.0 (most confident)
        phase: the observation's activity phase label, indicating the phase of activity of the site model on this particular observation's date
        id: the human-readable ID for the observation
        uuid: a unique ID for the observation
    """

    def __init__(self, df):
        """
        Create a slice (aka an observation) for a SiteStack
        :param df: a single-row GeoDataFrame
        """
        self.df = df.copy(deep=True)
        if not df.crs:
            self.df.set_crs(4326, inplace=True)
        row = self.df.iloc[0]
        self.polygon = row["geometry"]
        self.area = GeometryUtil.compute_region_area(self.polygon)
        self.boundary_flags = str(row["is_site_boundary"]).replace(" ", "").split(",")
        self.date = pd.to_datetime(row["observation_date"], format="%Y-%m-%d")
        self.source = row["source"] if row["source"] else None
        # default confidence score is 1
        self.score = row.get("score", 1)
        if np.isnan(self.score):
            self.score = 1
        self.phase = row["current_phase"]
        self.set_id()
        self.uuid = uuid.uuid4()

    def set_id(self):
        """
        Create an identifier for the slice,
        currently using the combination of date and image source
        """
        self.id = f"{self.date}_{self.source}"


class SiteStack:
    """Class definition for a site stack (aka a site model), that is, a sequence of related observations that capture the progression of activity in a particular location over a period of time

    Attributes:
        df: a geopandas dataframe representing the site model, derived from the geojson annotation file
        annotation_id: the original ID provided in the site model's geojson annotation file
        originator: the ID of the site model's annotator
        mgrs: the military grid reference system code that indicates where the site model is geographically located
        id: the human-readable ID for the site model
        uuid: a unique ID for the site model
        sites: the list of oversegmented site IDs that constitute this site model, if any (by default, this is simply a list of one element that is the site model's own ID)
        annotated_status: the site model's original status, as it appears in the annotation file
        annotated_null_start: boolean flag that indicates whether the annotation file has an unspecified (null) start date
        annotated_null_end: boolean flag that indicates whether the annotation file has an unspecified (null) end date
        status: the site model's effective status for the purposes of association and scoring, which depends on the subset of ground truth activity that is being assessed
        score: the site model's confidence score, a float ranging from 0.0 (least confident) to 1.0 (most confident)
        predicted_phase: the next activity phase that the site will transition to in the future, beyond its end date
        predicted_date: the date in the future when the site will transition to the next activity phase
        unbounded: an integer code to indicate the temporal bounds of the site model relative to the given region model
        association_status: indicates how the site model's association was scored (e.g. true positive "tp", false positive "fp", false negative "fn", no impact "0")
        associated: a Boolean flag to indicate whether the site model was associated with another site model
        color: an integer code to indicate how the site model should be displayed in a visualization tool
        start_date: the site-level start date, as annotated in the geojson file (yyyy-mm-dd)
        end_date: the site-level end date, as annotated in the geojson file (yyyy-mm-dd)
        bounded_slices: a list of the site's observations that are within the region model's temporal bounds
        unbounded_slices: a list of the site's observations that are outside the region model's temporal bounds
        first_obs: the site's earliest observation date
        last_obs: the site's latest observation date
        first_post_obs: the site's earliest Post Construction observation date, if any
        len_first_post_obs: the number of calendar days between the latest start of activity and the first Post Construction observation, inclusive
        start_activity: the start of the site's period of activity (used for temporal comparison and association)
        earliest_start_activity: the earliest possible start date of the site's activity, given the phase transition ambiguity in the annotation
        latest_start_activity: the latest possible start date of the site's activity, given the phase transition ambiguity in the annotation
        end_activity: the end of the site's period of activity (used for temporal comparison and association)
        activity_dates: the full list of calendar dates between the start and the end of activity
        len_activity: the length of the activity_dates list
        min_activity_dates: the full list of calendar dates between the latest start and the end of activity
        len_min_activity: the length of the min_activity_dates list
        max_activity_dates: the full list of calendar dates between the earliest start and the end of activity
        len_max_activity: the length of the max_activity_dates list
        polygons: a list of the site model's temporally bounded polygon geometries
        polygon_areas: a list of the areas of the site model's temporally bounded polygon geometries
        max_polygon_area: the area of the site model's largest polygon observation
        polygon_union: the geometric union of the site model's temporally bounded observations
        area: the area of the site model's polygon union in sq km
    """

    @timer
    def __init__(self, input_path, region_model, crs=None):
        """
        Create a site stack from a geojson file
        :param input_path: path to a geojson file (str)
        :param region_model: a RegionModel object
        :param crs: the target coordinate reference system (int)
        """

        # check for valid path
        if not os.path.isfile(input_path):
            logging.error(f"Could not load site stack, {input_path} not found.")

        # load stack as a GeoDataFrame
        self.df = gpd.read_file(input_path)

        # version 2 of the SMART geojson annotation format (current version)
        if "type" in self.df:
            site = self.df[self.df["type"] == "site"].iloc[0]
            self.annotation_id = site["site_id"]
            self.originator = site["originator"]

        # version 1 of the annotation format (legacy version)
        else:
            with open(input_path) as f:
                site = geojson.load(f)
            self.annotation_id = site["id"]
            self.originator = None

        # set the site model attributes
        self.mgrs = site.get("mgrs", "")
        self.version = site.get("version", "")
        self.set_id()
        self.uuid = uuid.uuid4()
        self.sites = [self.id]
        self.annotated_status = site["status"]  # the original status, as appears in the annotation file
        self.annotated_null_start = False
        self.annotated_null_end = False
        self.status = site["status"]  # the current effective status, depending on the type of activity metric
        self.score = site.get("score", 1)
        if np.isnan(self.score):
            self.score = 1
        self.predicted_phase = site.get("predicted_phase_transition")
        self.predicted_date = site.get("predicted_phase_transition_date")
        self.unbounded = 0
        self.association_status = None
        self.associated = None
        self.color = None

        # get the site-level start date and end date in the annotation
        self.start_date = site["start_date"]
        self.end_date = site["end_date"]
        if self.start_date:
            self.start_date = pd.to_datetime(str(site["start_date"]), format="%Y-%m-%d")
        if self.end_date:
            self.end_date = pd.to_datetime(str(site["end_date"]), format="%Y-%m-%d")

        # clip site start and end dates to region model
        # and "ignore" sites that do not have an annotated start date or end date
        if self.start_date:
            if not self.end_date or (self.end_date and self.end_date >= region_model.start_date):
                self.start_date = max(self.start_date, region_model.start_date)
        else:
            self.start_date = region_model.start_date
            self.status = "ignore"
            self.annotated_null_start = True
        if self.end_date:
            if not self.start_date or (self.start_date and self.start_date <= region_model.end_date):
                self.end_date = min(self.end_date, region_model.end_date)
        else:
            self.end_date = region_model.end_date
            self.status = "ignore"
            self.annotated_null_end = True

        # set the coordinate reference system (currently, only EPSG:4326 is supported)
        if crs:
            self.df = self.df.to_crs(epsg=crs)
        self.crs = self.df.crs.srs

        self.df["stack"] = self.id
        self.df = self.df[self.df["type"] != "site"].reset_index()

        # change first and last observation dates to match the start_date and end_date
        if len(self.df) >= 2:
            if not self.df.loc[0, "observation_date"]:
                self.df.loc[0, "observation_date"] = str(self.start_date.date())
            if not self.df.loc[len(self.df) - 1, "observation_date"]:
                self.df.loc[len(self.df) - 1, "observation_date"] = str(self.end_date.date())

        # remove observations without dates
        self.df.dropna(subset=["observation_date"], inplace=True)

        # create stack slices
        slices = [StackSlice(gpd.GeoDataFrame([row.to_dict()], geometry=[row["geometry"]], crs=self.df.crs)) for i, row in self.df.iterrows() if row.get("type") != "site"]
        slices.sort(key=lambda x: (x.date, x.id))

        if FIONA_GE_1_9_0:
            # Replace nans with the string "None" in the current_phase column
            # to work around a change in fiona 1.9.x
            self.df = self.df.replace(float("nan"), None)

        # remove polygons from the multipolygon geometry that are not site boundaries (for BAS only)
        for slice in slices:
            # do nothing for the base case (a single site boundary polygon)
            if len(slice.boundary_flags) == 1 and slice.boundary_flags[0] == "True":
                continue
            elif type(slice.polygon) != MultiPolygon:
                continue
            # remove polygon boundaries for subsites
            else:
                new_multipolygon = MultiPolygon([p for p, flag in zip(slice.polygon.geoms, slice.boundary_flags) if flag != "False"])
                slice.polygon = new_multipolygon
                slice.area = GeometryUtil.compute_region_area(slice.polygon)

        # determine the site model's bounded status, relative to the region model's temporal bounds
        bounded_slices = sorted(
            list(
                filter(
                    lambda x: region_model.start_date <= x.date <= region_model.end_date,
                    slices,
                )
            ),
            key=lambda x: (x.date, x.id),
        )
        bounded_phases = [slice.phase for slice in bounded_slices if slice.phase]
        pre_slices = sorted(
            list(filter(lambda x: x.date < region_model.start_date, slices)),
            key=lambda x: (x.date, x.id),
        )
        pre_phases = [slice.phase for slice in pre_slices if slice.phase]
        post_slices = sorted(
            list(filter(lambda x: x.date > region_model.end_date, slices)),
            key=lambda x: (x.date, x.id),
        )
        post_phases = [slice.phase for slice in post_slices if slice.phase]
        unbounded_slices = pre_slices + post_slices

        # an observation has activity if it is in the Site Preparation or the Active Construction phases
        def has_activity(phases):
            return "Site Preparation" in "".join(phases) or "Active Construction" in "".join(phases)

        # a ground truth site is unbounded if one or more of its observations are outside the region model's temporal bounds
        if self.status in POSITIVE_ACTIVITY_STATUS_TYPES:
            if has_activity(pre_phases) and not has_activity(bounded_phases):
                self.unbounded = -2
            elif has_activity(pre_phases) and has_activity(bounded_phases):
                self.unbounded = -1
            elif has_activity(bounded_phases) and not has_activity(pre_phases) and not has_activity(post_phases):
                self.unbounded = 0
            elif has_activity(post_phases) and has_activity(bounded_phases):
                self.unbounded = 1
            elif has_activity(post_phases) and not has_activity(bounded_phases):
                self.unbounded = 2
        else:
            if pre_slices and not bounded_slices:
                self.unbounded = -2
            elif pre_slices and bounded_slices:
                self.unbounded = -1
            elif bounded_slices and not pre_slices and not post_slices:
                self.unbounded = 0
            elif post_slices and bounded_slices:
                self.unbounded = 1
            elif post_slices and not bounded_slices:
                self.unbounded = 2

        # A site remains bounded if all unbounded observations are additional (extra) post construction and as long as one post construction observation is bounded
        if not has_activity(pre_phases) and "Post Construction" in bounded_phases and set(post_phases) == set(["Post Construction"]):
            self.unbounded = 0
        if not has_activity(pre_phases) and "Post Construction" not in bounded_phases and "Post Construction" in post_phases:
            if "Active Construction" in bounded_phases:
                self.partial_type = "A"
            elif "Site Preparation" in bounded_phases:
                self.partial_type = "B"

        if not bounded_slices:
            logging.debug(f"{self.annotation_id} has no bounded slices")

        # filter the observations
        self.bounded_slices = bounded_slices
        self.unbounded_slices = unbounded_slices
        if self.status not in POSITIVE_ACTIVITY_STATUS_TYPES:
            self.slices = slices
        else:
            self.slices = bounded_slices  # drop unbounded slices (but not for site types 3 and 4)

        # initialize other dates of interest
        self.first_obs = self.slices[0].date if self.slices else None
        self.last_obs = self.slices[-1].date if self.slices else None
        self.first_post_obs = None
        self.len_first_post_obs = None
        self.start_activity = None
        self.earliest_start_activity = None
        self.latest_start_activity = None
        self.end_activity = None

        # get activity dates for truth sites types 1 and 2
        if self.status in POSITIVE_ACTIVITY_STATUS_TYPES:
            # compute the latest start of activity
            if has_activity(pre_phases) and (has_activity(bounded_phases) or "Post Construction" in "".join(bounded_phases)):
                self.latest_start_activity = region_model.start_date
            else:
                for bounded_slice in bounded_slices:
                    if bounded_slice.phase and has_activity([bounded_slice.phase]):
                        self.latest_start_activity = bounded_slice.date
                        break
            self.start_activity = self.latest_start_activity

            # compute the earliest start of activity
            if self.latest_start_activity:
                for obs in sorted(
                    list(
                        filter(
                            lambda obs: obs.date <= self.latest_start_activity,
                            pre_slices + bounded_slices,
                        )
                    ),
                    key=lambda obs: obs.date,
                    reverse=True,
                ):
                    if "No Activity" in obs.phase:
                        self.earliest_start_activity = max(
                            min(obs.date, self.latest_start_activity),
                            region_model.start_date,
                        )
                        break
                else:
                    self.earliest_start_activity = self.latest_start_activity

                # compute the end of activity
                for bounded_slice in bounded_slices:
                    if bounded_slice.phase:
                        segment_phases = set(re.split(", |_", bounded_slice.phase))
                        # all of the observation's phase labels must be Post Construction
                        if segment_phases == {"Post Construction"}:
                            self.first_post_obs = max(self.latest_start_activity, bounded_slice.date)
                            self.end_activity = min(region_model.end_date, self.first_post_obs)
                            self.len_first_post_obs = len(
                                set(
                                    pd.date_range(
                                        start=self.latest_start_activity,
                                        end=self.first_post_obs,
                                    )
                                )
                            )
                            break
                else:
                    self.end_activity = region_model.end_date

        # for other truth site types, the start and end of activity are the same as the site-level start and end dates
        else:
            self.start_activity = self.start_date
            self.end_activity = self.end_date

        # compute the activity duration
        self.activity_dates = set()
        self.len_activity = None
        if self.start_activity and self.end_activity:
            self.activity_dates = set(pd.date_range(start=self.start_activity, end=self.end_activity))
            self.len_activity = len(self.activity_dates)
        # a positive truth site is unbounded if it does not have a start or end activity date
        elif self.status in POSITIVE_ACTIVITY_STATUS_TYPES:
            self.status = "positive_unbounded"

        # compute the minimum activity duration
        self.min_activity_dates = set()
        self.len_min_activity = None
        if self.latest_start_activity and self.end_activity:
            self.min_activity_dates = set(pd.date_range(start=self.latest_start_activity, end=self.end_activity))
            self.len_min_activity = len(self.min_activity_dates)

        # compute the maximum activity duration
        self.max_activity_dates = set()
        self.len_max_activity = None
        if self.earliest_start_activity and self.end_activity:
            self.max_activity_dates = set(pd.date_range(start=self.earliest_start_activity, end=self.end_activity))
            self.len_max_activity = len(self.max_activity_dates)

        # compute the site model's spatial representations and area
        self.polygons = [slice.polygon for slice in self.slices]
        self.polygon_areas = [GeometryUtil.compute_region_area(polygon) for polygon in self.polygons]
        self.max_polygon_area = max(self.polygon_areas) if self.polygon_areas else None
        if self.polygons:
            try:
                self.polygon_union = unary_union(self.polygons)
                self.area = GeometryUtil.compute_region_area(self.polygon_union)
            except Exception:
                logging.warning(f"Failed to calculate area of polygon union for {self.id}")
                self.polygon_union = self.polygons[self.polygon_areas.index(max(self.polygon_areas))]
                self.area = self.max_polygon_area
        else:
            logging.warning(f"No bounded polygons for {self.id}")
            self.polygon_union = Polygon()
            try:
                self.area = GeometryUtil.compute_region_area(unary_union([slice.polygon for slice in unbounded_slices]))
            except Exception:
                logging.warning("Failed to calculate area of polygon union for unbounded slices")
                self.area = GeometryUtil.compute_region_area(unbounded_slices[0].polygon)

        logging.debug(f"Created site stack {self.id} with {len(self.slices)} slices")

    def set_id(self):
        """
        Create a unique ID for the site stack
        """
        self.id = self.annotation_id
        if "contour" in self.id:
            self.id = self.id[self.id.find("contour") :]
        if self.mgrs:
            # self.id = f"{self.mgrs}_{self.id}"
            pass
        if self.originator:
            self.id = f"{self.id}_{self.originator}"
        if self.version:
            self.id = f"{self.id}_{self.version}"
        logging.debug(f"Set id to {self.id}")

    def get_slice(self, date, exact=False):
        """
        Fetch a slice from the site stack based on the observation date
        The retrieved slice should be equal to or older than the date
        Returns the first slice to match the date
        :param date: date in yyyy-mm-dd format (str)
        :param exact: only return an observation if it has the exact same calendar date as the date parameter (bool)
        :return: the corresponding stack slice object if one exists, otherwise None
        """
        # get the most recent site model observation that isn't newer than the specified date
        prev_slices = sorted(
            list(filter(lambda x: x.date <= pd.to_datetime(date), self.slices)),
            key=lambda x: (x.date, x.id),
        )
        if prev_slices:
            if prev_slices[-1].date == date or not exact:
                return prev_slices[-1]
            else:
                # there is no site model observation on the specified date
                return None
        # all of the site model observations are newer than the ground truth
        else:
            logging.debug("Returning no slices")
            return None

    @timer
    def combine_stacks(self, stacks):
        """
        Merge the (site model) stacks into self (a ground truth stack)
        :param stacks: a list of SiteStack objects that will be combined together
        :return: the union of the site model stacks
        """

        # create a duplicate of the ground truth stack, to be converted to the combined site stack
        combined_stack = deepcopy(self)
        combined_stack.len_activity = len(combined_stack.activity_dates)

        sorted_stacks = sorted(stacks, key=lambda stack: stack.id)
        # set new attributes
        combined_stack.mgrs = "_".join([str(stack.mgrs) for stack in sorted_stacks])
        combined_stack.crs = "_".join([str(stack.crs) for stack in sorted_stacks])
        combined_stack.sites = [str(stack.id) for stack in sorted_stacks]
        combined_stack.id = Evaluation.get_sm_stack_id(stacks)
        combined_stack.version = "_".join([str(stack.version) for stack in sorted_stacks])
        combined_stack.df = None

        combined_stack.uuid = uuid.uuid4()

        combined_stack.originator = "_".join([str(stack.originator) for stack in sorted_stacks])
        combined_stack.annotated_status = "_".join([str(stack.annotated_status) for stack in sorted_stacks])
        combined_stack.start_date = min([stack.start_date for stack in sorted_stacks if stack.start_date])
        combined_stack.end_date = max([stack.end_date for stack in sorted_stacks if stack.end_date])
        combined_stack.start_activity = min([stack.start_activity for stack in sorted_stacks if stack.start_activity])
        combined_stack.end_activity = max([stack.end_activity for stack in sorted_stacks if stack.end_activity])
        combined_stack.activity_dates = set.union(*[stack.activity_dates for stack in sorted_stacks])
        combined_stack.len_activity = len(combined_stack.activity_dates)
        combined_stack.predicted_phase = None
        combined_stack.predicted_date = None
        combined_stack.score = min([stack.score for stack in sorted_stacks if stack.score])
        combined_stack.slices = []

        # create new slices
        # for each truth site timestep t, define the slice Z_t = (A_t U B_t U C_t ...)
        # even if the slice Z_t would have a higher intersection with G_t if Z_t = A_t or Z_t = B_t at that particular time t
        observation_dates = set()

        # truth site dates
        for slice in self.slices:
            observation_dates.add(slice.date)

        # proposed dates
        for stack in stacks:
            for slice in stack.slices:
                observation_dates.add(slice.date)

        # create new, combined observations
        for date in observation_dates:
            slices = list(filter(None, [stack.get_slice(date) for stack in sorted_stacks]))
            if not slices:
                continue
            combined_slice = deepcopy(slices[0])
            combined_slice.polygon = unary_union([slice.polygon for slice in slices])
            combined_slice.area = GeometryUtil.compute_region_area(combined_slice.polygon)
            combined_slice.df.set_geometry([combined_slice.polygon], inplace=True)
            combined_slice.date = date
            combined_slice.source = "_".join([str(slice.source) for slice in slices])
            combined_slice.phase = "_".join([str(slice.phase) for slice in slices])
            combined_slice.boundary_flags = []
            combined_slice.set_id()
            combined_slice.uuid = uuid.uuid4()
            combined_stack.slices.append(combined_slice)
        combined_stack.slices.sort(key=lambda x: (x.date, x.id))

        combined_stack.polygons = [slice.polygon for slice in combined_stack.slices]
        try:
            combined_stack.polygon_union = unary_union(combined_stack.polygons)
            combined_stack.area = GeometryUtil.compute_region_area(combined_stack.polygon_union)
        except Exception:
            logging.warning(f"Failed to calculate area of polygon union for {combined_stack.id}")
            combined_stack.polygon_union = combined_stack.polygons[0]
            combined_stack.area = GeometryUtil.compute_region_area(combined_stack.polygons[0])

        return combined_stack

    @timer
    def check_unary_union(self, stack):
        """
        Check if there is any intersection between the unary unions of the polygons of 2 stacks.
        If not, then there is definitely no intersection between any of their corresponding slices.
        Can be used an alternative to, or in combination with, a spatial index
        in order to filter out stack pairs with no intersection.
        :param stack: a SiteStack object that will be compared to self
        :return: the intersection geometry if stack and self intersect, otherwise an empty polygon
        """

        # get the corresponding slice from the site model stack
        sm_slices = [stack.get_slice(gt_slice.date) for gt_slice in self.slices]
        sm_polygons = [sm_slice.polygon for sm_slice in sm_slices if sm_slice]

        # get the union of all site model slices
        sm_polygon_union = unary_union(sm_polygons)

        # is there any intersection between the 2 stacks?
        try:
            intersection = self.polygon_union.intersection(sm_polygon_union)
        except Exception as e:
            logging.error(e)
            intersection = Polygon()

        return intersection


class RegionModel:
    """Class definition for a region model, which defines the spatial and temporal boundaries of an evaluation"""

    @timer
    def __init__(self, roi_path, crs=None):
        """
        Load a region model
        :param roi_path: path to a ground truth region model geojson file (str)
        :param crs: the target coordinate reference system (int)
        """
        self.df = gpd.read_file(roi_path)
        self.df = self.df.loc[self.df["type"] == "region"]
        if crs:
            self.df = self.df.to_crs(epsg=crs)
        row = self.df.iloc[0]
        self.polygon = row.geometry
        self.area = GeometryUtil.compute_region_area(row.geometry)
        self.start_date = pd.to_datetime(str(row["start_date"]), format="%Y-%m-%d")
        self.end_date = pd.to_datetime(str(row["end_date"]), format="%Y-%m-%d")
        self.dates = len(pd.date_range(start=self.start_date, end=self.end_date)) - 1
        self.id = str(row["region_id"])


class GeometryUtil:
    "Utility class for various geometric computations"

    @classmethod
    def scale_area(cls, lat):
        """
        Find square meters per degree for a given latitude based on EPSG:4326
        :param lat: average latitude
            note that both latitude and longitude scales are dependent on latitude only
            https://en.wikipedia.org/wiki/Geographic_coordinate_system#Length_of_a_degree
        :return: square meters per degree for latitude coordinate
        """

        lat *= np.pi / 180.0  # convert to radians
        lat_scale = 111132.92 - (559.82 * np.cos(2 * lat)) + (1.175 * np.cos(4 * lat)) - (0.0023 * np.cos(6 * lat))
        lon_scale = (111412.84 * np.cos(lat)) - (93.5 * np.cos(3 * lat)) + (0.118 * np.cos(5 * lat))

        return lat_scale * lon_scale

    @classmethod
    @timer
    def compute_region_area(cls, region_poly, epsg=4326):
        """
        Compute area of the region based on EPSG:4326 CRS
        Custom method for computing accurate areas anywhere on the globe (the shapely geometry.area property is not accurate for EPSG:4326)
        :param region_poly: shapely polygon that defines the region boundary
        :return: area of polygon in square kilometers
        """

        # ignore area warnings on Mac OS...
        # The warning is from geopandas (documentation here). Essentially, it is alerting us that 
        # area isn't constant in a geographic CRS -> it varies with latitude. However, for us, this 
        # isn't a problem because Phil's custom area function accounts for this and scales by lat afterwards.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            poly_area = region_poly.area

        if epsg == 4326:
            # get average latitude
            try:
                avg_lat = (region_poly.bounds[1] + region_poly.bounds[3]) / 2.0
            except KeyError:
                avg_lat = (region_poly.bounds["miny"] + region_poly.bounds["maxy"]) / 2.0
            except IndexError:
                logging.warning("Failed to compute region area for empty polygon")
                return 0

            # scale the area by the scale factor
            poly_area *= GeometryUtil.scale_area(avg_lat)
        # convert from square meters to square kilometers
        if type(poly_area) == pd.Series:
            poly_area = float(poly_area.iloc[0])

        # return area in units of square kilometers and round to the nearest square centimeter
        return round(poly_area / 1e6, 10)

    @classmethod
    @timer
    def intersection(cls, df1, df2):
        """
        Get the intersection of 2 geometries
        :param df1: a GeoDataFrame
        :param df2: a GeoDataFrame
        :return: the area of the intersection of the 2 polygons
            and the intersection geometry
            (float, MultiPolygon)
        """
        shape = gpd.overlay(df1, df2, how="intersection")
        if shape.empty:
            area = 0
        else:
            area = GeometryUtil.compute_region_area(shape)

        return area, shape

    @classmethod
    @timer
    def union(cls, df1, df2):
        """
        Get the union of 2 geometries
        :param df1: a GeoDataFrame
        :param df2: a GeoDataFrame
        :return: the area of the union of the 2 polygons
            and the union geometry
            (float, MultiPolygon)
        """
        overlaid = gpd.overlay(df1, df2, how="union")
        AVOID_SEGFAULT = 1
        if AVOID_SEGFAULT:
            # There is a strange segfault that has happened here.
            # This might be due to a mismatch in geopandas / shapely versions
            # This can be mitigated via:
            shape = unary_union(overlaid["geometry"].values.tolist())
        else:
            shape = unary_union(overlaid["geometry"])
        if type(shape) == Polygon:
            shape = MultiPolygon([shape])

        area = GeometryUtil.compute_region_area(shape)

        return area, shape

    @classmethod
    @timer
    def convex_hull(cls, df1, df2, area=True):
        """
        Get the convex hull of 2 geometries
        :param df1: a GeoDataFrame
        :param df2: a GeoDataFrame
        :param area: whether to return the resulting shape or the shape's area (bool)
        :return: the (area of the) convex hull of the 2 polygons
            (float if area=True else MultiPolygon)
        """

        list_of_polygons = []

        for df in [df1, df2]:
            for geometry in list(df["geometry"]):
                if type(geometry) == MultiPolygon:
                    list_of_polygons.extend(list(geometry))
                elif type(geometry) == Polygon:
                    list_of_polygons.append(geometry)
                else:
                    logging.error(f"{df.id} has an invalid geometry type {type(geometry)}")

        shape = MultiPolygon(list_of_polygons).convex_hull
        return GeometryUtil.compute_region_area(shape) if area else shape


class Metric:
    """Utility class for computing various similarity and performance metrics"""

    @classmethod
    def calc_iou(cls, df1, df2):
        """
        Get the intersection over union of 2 geometries
        :param df1: a GeoDataFrame
        :param df2: a GeoDataFrame
        :return: the IoU ratio, the area of the intersection,
            the intersection geometry, the area of the union, the union geometry
            (float, float, MultiPolygon, float, MultiPolygon)
        """
        intersection_area, intersection = GeometryUtil.intersection(df1, df2)
        union_area, union = GeometryUtil.union(df1, df2)
        if intersection_area:
            iou = float(intersection_area / union_area)
        else:
            return 0, 0, None, 0, None
        return iou, intersection_area, intersection, union_area, union

    @classmethod
    def calc_iot(cls, df1, df2, intersection=None):
        """
        Get the intersection over truth of 2 geometries
        :param df1: the truth GeoDataFrame
        :param df2: a GeoDataFrame
        :param intersection: the intersection of the 2 geometries, if already calculated
        :return: the IoT ratio and the area of the intersection (float, float)
        """
        numerator = intersection
        if not numerator:
            numerator, _ = GeometryUtil.intersection(df1, df2)
        if numerator:
            isect = float(numerator)
            iot = float(numerator / GeometryUtil.compute_region_area(df1))
        else:
            iot, isect = 0, 0
        return iot, isect

    @classmethod
    def calc_giou(cls, df1, df2):
        """
        Get the generalized intersection over union of 2 geometries
        An implementation of the metric by Rezatofighi et. al. (arXiv:1902.09630v2)
        Only a valid metric for convex polygons
        :param df1: a GeoDataFrame
        :param df2: a GeoDataFrame
        :return: the GIoU metric, the IoU ratio, the intersection area,
            the intersection geometry, the area of the union, the union geometry
            (float, float, float, MultiPolygon, float, MultiPolygon)
            Since IoU and intersection are prerequisite inputs to calculating GIoU,
            this function returns them all for convenience, and to avoid a separate,
            redundant call to calc_iou()
        """
        iou, intersection_area, intersection, union_area, union = Metric.calc_iou(df1, df2)
        hull = GeometryUtil.convex_hull(df1, df2)
        penalty = (hull - union_area) / hull
        return float(iou - penalty), iou, intersection_area, intersection, union_area, union

    @classmethod
    def calc_precision(cls, tp, fp):
        """
        Get the precision score
        :param tp: number of true positives (int)
        :param fp: number of false positives (int)
        :return: precision value (float)
        """
        return tp / (tp + fp) if tp else 0

    @classmethod
    def calc_recall(cls, tp, fn):
        """
        Get the recall score
        :param tp: number of true positives (int)
        :param fn: number of false negatives (int)
        :return: recall value (float)
        """
        return tp / (tp + fn) if tp else 0

    @classmethod
    def calc_F1(cls, tp, fp, fn):
        """
        Get the F1 score
        :param tp: number of true positives (int)
        :param fp: number of false positives (int)
        :param fn: number of false negatives (int)
        :return: F1 value (float)
        """
        return tp / (tp + 0.5 * (fp + fn)) if tp else 0


class Evaluation:
    """Class definition for a SMART evaluation, which compares ground truth annotations with proposed site models and computes similarity and performance metrics"""

    # used to log the progress of the evaluation
    comparable_truth_sites = 0
    total_truth_sites = 0

    @timer
    def __init__(
        self,
        gt_files,
        sm_files,
        rm_path,
        roi,
        #eval_num,
        #eval_run_num,
        #eval_increment_num,
        #performer,
        # batch_mode=True,
        #increment_start_date=None,
        #increment_end_date=None,
        #dag_run_id=None,
        metric_name="iou",
        tau=0.2,
        rho=0.5,
        confidence_score_thresholds=None,
        temporal_iop=0.1,
        temporal_iot=0.2,
        transient_temporal_iop=0.1,
        transient_temporal_iot=0.2,
        small_site_threshold=9000,
        crs=None,
        #sweep_tau=False,
        #sweep_rho=False,
        #sweep_min_area=False,
        #sweep_confidence=False,
        #image_path=None,
        output_dir=None,
        smart_database_api=None,  # DEV only
        parallel=True,
        num_processes=None,
        sequestered_id=None,
    ):
        """
        :param gt_files: list of ground truth site stack filepaths ([str])
        :param sm_files: list of proposed site stack filepaths ([str])
        :param rm_path: path to a region model geojson file (str)
        :param roi: region of interest (str)
        :param metric_name: the name of the similarity metric to use for the comparison, such as "iou" or "giou" (str)
        :param tau: the association threshold (float)
        :param rho: the detection threshold (float)
        :param confidence_score_thresholds: a list of minimum confidence score thresholds to use to filter out proposals ([float])
        :temporal_iop: the temporal intersection over proposal site duration threshold (float)
        :temporal_iot: the temporal intersection over truth site duration threshold (float)
        :transient_temporal_iop: the temporal intersection over proposal site duration threshold for transient sites (float)
        :transient_temporal_iot: the temporal intersection over truth site duration threshold for transient sites (float)
        :small_site_threshold: the threshold for the minimum size of a ground truth site (sq m), in order to not be "ignored" (int)
        :param crs: the target coordinate reference system (int)
        :param output_dir: path to the directory where visualization outputs will be stored (str)
        :param smart_database_api: SMART database API instantiated with database connection infromation - DEV ONLY
        :param parallel: whether to use multiprocessing (bool)
        :param num_processes: the number of processes to spawn, if parallel is True (int)
        :param sequestered_id: the alias to use in place of the region model ID (str)
        """
        logging.info("Starting evaluation...")

        # inputs
        self.metric_name = metric_name
        self.crs = crs
        # self.image_path = image_path
        self.gt_files = gt_files
        self.sm_files = sm_files

        # initialize variables that will store the optimal threshold values (to be updated later during the evaluation)
        self.best = None # the best row from the metric scoreboard (the row with the highest F1 score and the strictest thresholds)
        self.best_metric_score = -1 # the highest F1 score
        self.tau = tau
        self.rho = rho
        self.temporal_iop = temporal_iop
        self.temporal_iot = temporal_iot
        self.transient_temporal_iop = transient_temporal_iop
        self.transient_temporal_iot = transient_temporal_iot
        self.min_area = 0  # square meters
        self.min_score = 0
        self.small_site_threshold = small_site_threshold
        if confidence_score_thresholds:
            self.confidence_score_thresholds = confidence_score_thresholds
        else:
            self.confidence_score_thresholds = list(map(lambda x: round(x, 2), np.linspace(0, 1, 11)))

        # deprecated
        self.sweep_tau = False # sweep_tau
        self.sweep_rho = False # sweep_rho
        self.sweep_min_area = False # sweep_min_area
        self.sweep_confidence = False # sweep_confidence

        self.detections = {} # a dict mapping a ground truth site ID to a list of the proposed site model(s) that it associates with
        self.proposals = {} # a dict mapping a proposed site model ID to a list of the ground truth site(s) that it associates with
        self.matched_pairs = [] # a list of tuples of associated (ground truth site, proposed site model) pairs

        # default threshold values to use if a range of values is not given
        self.default_tau = 0.2
        self.default_rho = 0.5
        self.default_min_confidence_score = 0
        self.default_min_area = 0  # square meters
        self.default_taus = [0.001, 0.005, 0.01, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5]
        self.default_rhos = [0.001, 0.01, 0.1, 0.5]

        # a range of threshold values, for a parameter sweep
        if tau:
            self.taus = [tau]
            if tau != self.default_tau:
                self.taus.append(self.default_tau)
        else:
            logging.warning(f"Tau not provided. Sweeping across a range of values: {self.default_taus}")
            self.taus = self.default_taus
        if rho:
            if rho > 0.5:
                logging.warning(f"Rho has been set to {rho}, but it should not be greater than 0.5")
            self.rhos = [rho]
            if rho != self.default_rho:
                self.rhos.append(self.default_rho)
        else:
            logging.warning(f"Rho not provided. Sweeping across a range of values: {self.default_rhos}")
            self.rhos = self.default_rhos
        self.min_areas = list(range(0, 50000, 10000))

        # multiprocessing
        self.parallel = parallel
        self.num_processes = num_processes

        # self.increment_start_date = increment_start_date if increment_start_date else None
        # self.increment_end_date = increment_end_date if increment_end_date else None
        #- REMOVE/turn off option - Database related

        # output directories
        os.makedirs(output_dir, exist_ok=True)
        self.output_dir = output_dir
        self.bas_dir = f"{output_dir}/bas"

        self.roi = roi
        self.evaluation_run_uuid = uuid.uuid4()

        # database functionality is currently only supported in developer mode
        if DEV:
            self.smart_database_api = smart_database_api
            if self.smart_database_api:
                self.register_evaluation()
        ###

        # multiprocessing
        self.counter = 0  # an approximate counter, not thread safe
        self.lock = Lock()
        self.queue = mp.Queue()  # a thread and process safe Queue

        # load the region model
        logging.debug("Loading the region model")
        self.region_model = RegionModel(roi_path=rm_path, crs=crs)

        # database functionality is currently only supported in developer mode
        if DEV:
            if self.smart_database_api:
                self.insert_if_not_exists_region()
        ###

        # load the site stacks from a list of geojson files
        logging.debug("Loading site stacks")
        self.sequestered_id = sequestered_id
        self.gt_stacks, self.gt_stack_gdf, all_gt_stacks = self.load_stacks(gt_files, crs, self.region_model)
        self.sm_stacks, self.sm_stack_gdf, all_sm_stacks = self.load_stacks(sm_files, crs, self.region_model, ["system_confirmed"])

        # a nested dict mapping every intersecting pair of ground truth site and proposed site to a dataframe of their slice-by-slice comparisons
        self.stack_comparisons = {gt_id: {} for gt_id in self.gt_stacks}

        # save the sites to the database
        if DEV:
            if self.smart_database_api:
                self.insert_sites(all_gt_stacks.values())
                self.insert_sites(all_sm_stacks.values())
        ###

        # save the site metadata to the local filesystem
        self.write_stacks_csv(all_gt_stacks, "gt_sites.csv")
        self.write_stacks_csv(all_sm_stacks, "sm_sites.csv")

    @timer
    def write_stacks_csv(self, stacks, filename):
        """Creates a CSV file that lists selected attributes of the site stacks
        :param stacks: a list of SiteStack objects
        :param filename: the name of the output CSV file (str)
        """
        df = pd.DataFrame()
        data = [
            (
                stack_id,
                stack.status,
                stack.area,
                stack.max_polygon_area,
                stack.score,
                stack.first_obs,
                stack.start_date,
                stack.earliest_start_activity,
                stack.latest_start_activity,
                stack.start_activity,
                stack.end_activity,
                stack.end_date,
                stack.last_obs,
            )
            for stack_id, stack in stacks.items()
        ]
        df = pd.DataFrame(
            data,
            columns=[
                "id",
                "status",
                "polygon union area",
                "max polygon area",
                "confidence score",
                "first observation",
                "start date",
                "earliest start",
                "latest start",
                "start activity",
                "end activity",
                "end date",
                "last observation",
            ],
        )
        # remove the region model ID from the dataframe and replace it with the sequestered ID
        df = Evaluation.sanitize_dataframe(df, self.region_model.id, self.sequestered_id)
        df.sort_values("id", inplace=True, ignore_index=True)
        df.to_csv(f"{self.output_dir}/{filename}", index=False)

    @timer
    def register_evaluation(self):
        """
        Database code - DEV Only
        """
        provenance_id = self.smart_database_api.get_provenance_id(
            test_harness_git_hash=git.Repo(search_parent_directories=True).head.object.hexsha,
            small_site_threshold=self.small_site_threshold,
        )

    @timer
    def complete_evaluation(self):
        """
        Database - DEV Only
        """
        self.smart_database_api.update_evaluation_run(self.evaluation_run_uuid, {"success": True})

    @timer
    def insert_if_not_exists_region(self):
        """
        Database code - DEV only
        """
        region = self.region_model.df.iloc[0].to_dict()
        region_id = region["region_id"]

        if not self.smart_database_api.get_region(region_id):
            self.smart_database_api.add(
                Region(
                    id=region_id,
                    start_date=region["start_date"],
                    end_date=region["end_date"],
                    crs=self.region_model.df.crs.srs,
                    mgrs=region["mgrs"],
                    geometry=region["geometry"].wkt,
                    area=self.region_model.area,
                )
            )

    @timer
    def insert_sites(self, sites):
        """
        DAtabase - DEV Only
        """
        for site in sites:
            add_list = []

            add_list.append(
                Site(
                    uuid=site.uuid,
                    site_id=site.id,
                    region_id=self.region_model.id,
                    crs=site.crs,
                    evaluation_run_uuid=self.evaluation_run_uuid,
                    originator=site.originator,
                    version=site.version,
                    mgrs=site.mgrs,
                    status_annotated=site.annotated_status,
                    predicted_phase=site.predicted_phase,
                    predicted_date=site.predicted_date,
                    union_geometry=site.polygon_union.wkt if hasattr(site, "polygon_union") else None,
                    union_area=site.area,
                    max_area=site.max_polygon_area,
                    sites=site.sites,
                    first_obs_date=site.first_obs,
                    last_obs_date=site.last_obs,
                    start_date=site.start_date,
                    end_date=site.end_date,
                    start_activity=site.start_activity,
                    end_activity=site.first_post_obs,
                    len_activity=site.len_first_post_obs,
                    end_observed_activity=site.end_activity,
                    len_observed_activity=site.len_activity,
                    earliest_start_activity=site.earliest_start_activity,
                    latest_start_activity=site.latest_start_activity,
                    len_min_activity=site.len_min_activity,
                    len_max_activity=site.len_max_activity,
                    annotated_null_start=site.annotated_null_start,
                    annotated_null_end=site.annotated_null_end,
                    confidence_score=site.score,
                )
            )

            for s in site.slices:
                add_list.append(
                    Observation(
                        uuid=s.uuid,
                        site_uuid=site.uuid,
                        date=s.date,
                        source=s.source,
                        phase=s.phase,
                        crs=s.df.crs.srs,
                        geometry=s.polygon.wkt,
                        area=s.area,
                        is_site_boundary=s.df.iloc[0]["is_site_boundary"],
                        confidence_score=s.score,
                    )
                )

            self.smart_database_api.add_all(add_list)

    @classmethod
    def sanitize_dataframe(cls, df, oldval, newval):
        """Removes instances of oldval from the dataframe (e.g. the ID of a sequestered region)
        and replaces them with newval (e.g. an alias for the sequestered region ID)

        :param df: pandas dataframe
        :paam oldval: a string in the dataframe that needs to be removed (str)
        :paam newval: the substitution string (str)
        """

        if newval is None:
            # Nothing to sanitize, return original dataframe
            return df

        for row_idx, row in df.iterrows():
            for col_idx, _ in row.items():
                before = str(df.at[row_idx, col_idx])
                if oldval in before:
                    df.at[row_idx, col_idx] = before.replace(oldval, newval)
        return df

    @timer
    def load_stacks(self, input_paths, crs=None, region_model=None, valid_statuses=None):
        """
        Load multiple SiteStack objects
        :param input_paths: list of paths to geojson files (list of strs)
        :param crs: the target coordinate reference system (int)
        :param region_model: the RegionModel used in the evaluation
        :param valid_statuses: a list of statuses, used to filter the site stacks
            If no list is provided, all of the site stacks will be loaded
        :return:
            stacks: a dict of site stacks {site stack name: site stack} that all have a valid status
            stack_index: a pandas DataFrame of the site stacks
            all_stacks: a dict of all of the site stacks, including those with an invalid status
        """

        stacks, all_stacks = {}, {}

        dataframes = []

        for input_path in tqdm(input_paths, desc="load stacks"):
            stack = SiteStack(input_path=input_path, region_model=region_model, crs=crs)

            # filter the SiteStacks based on their status
            if not valid_statuses or stack.status in valid_statuses:
                stacks[stack.id] = stack
                dataframes.extend([slice.df for slice in stack.slices])

            all_stacks[stack.id] = stack

        stack_index = pd.concat(dataframes).reset_index(drop=True) if dataframes else gpd.GeoDataFrame()

        return stacks, stack_index, all_stacks

    def update_gt_statuses(self, activity_type, small_site_threshold):
        """Adjusts the statuses of the ground truth site depending on the type of activity that is being evaluated
        Also ignores ground truth sites that are too small (below the small site threshold)
        """
        for gt_id, gt_stack in self.gt_stacks.items():
            # ignore small sites (convert small_site_threshold from sq m to sq km)
            if gt_stack.status not in ANNOTATED_NEGATIVE_STATUS_TYPES and gt_stack.max_polygon_area and gt_stack.max_polygon_area <= small_site_threshold / 1e6:
                self.gt_stacks[gt_id].status = "ignore" if "transient" not in gt_stack.status else "transient_ignore"

            else:
                if not gt_stack.annotated_null_start and not gt_stack.annotated_null_end:
                    self.gt_stacks[gt_id].status = gt_stack.annotated_status  # reset the effective status to the original annotated status
                if gt_stack.status in POSITIVE_COMPLETE_STATUS_TYPES:
                    if not gt_stack.unbounded:
                        if "partial" in activity_type:
                            self.gt_stacks[gt_id].status = "ignore" if "transient" not in gt_stack.status else "transient_ignore"
                    elif gt_stack.unbounded == -2:
                        self.gt_stacks[gt_id].status = "positive_unbounded" if "transient" not in gt_stack.status else "transient_ignore"
                    elif gt_stack.unbounded == -1:
                        self.gt_stacks[gt_id].status = "positive_unbounded" if "transient" not in gt_stack.status else "transient_ignore"
                    elif gt_stack.unbounded == 1:
                        if activity_type == "completed":
                            self.gt_stacks[gt_id].status = "positive_unbounded" if "transient" not in gt_stack.status else "transient_ignore"
                        elif activity_type == "partialA" and gt_stack.partial_type == "B":
                            self.gt_stacks[gt_id].status = "positive_unbounded" if "transient" not in gt_stack.status else "transient_ignore"
                        elif activity_type == "partialB" and gt_stack.partial_type == "A":
                            self.gt_stacks[gt_id].status = "ignore" if "transient" not in gt_stack.status else "transient_ignore"
                    elif gt_stack.unbounded == 2:
                        self.gt_stacks[gt_id].status = "positive_unbounded" if "transient" not in gt_stack.status else "transient_ignore"
                elif gt_stack.status in POSITIVE_PARTIAL_STATUS_TYPES:
                    if not gt_stack.unbounded:
                        if activity_type == "completed":
                            self.gt_stacks[gt_id].status = "ignore" if "transient" not in gt_stack.status else "transient_ignore"
                        elif activity_type == "partialA" and gt_stack.partial_type == "B":
                            self.gt_stacks[gt_id].status = "positive_unbounded" if "transient" not in gt_stack.status else "transient_ignore"
                        elif activity_type == "partialB" and gt_stack.partial_type == "A":
                            self.gt_stacks[gt_id].status = "ignore" if "transient" not in gt_stack.status else "transient_ignore"
                    elif gt_stack.unbounded == -2:
                        self.gt_stacks[gt_id].status = "positive_unbounded" if "transient" not in gt_stack.status else "transient_ignore"
                    elif gt_stack.unbounded == -1:
                        self.gt_stacks[gt_id].status = "positive_unbounded" if "transient" not in gt_stack.status else "transient_ignore"
                    elif gt_stack.unbounded == 1:
                        if activity_type == "completed":
                            self.gt_stacks[gt_id].status = "positive_unbounded" if "transient" not in gt_stack.status else "transient_ignore"
                        elif activity_type == "partialA" and gt_stack.partial_type == "B":
                            self.gt_stacks[gt_id].status = "positive_unbounded" if "transient" not in gt_stack.status else "transient_ignore"
                        elif activity_type == "partialB" and gt_stack.partial_type == "A":
                            self.gt_stacks[gt_id].status = "ignore" if "transient" not in gt_stack.status else "transient_ignore"
                    elif gt_stack.unbounded == 2:
                        self.gt_stacks[gt_id].status = "positive_unbounded" if "transient" not in gt_stack.status else "transient_ignore"

            # if the new status of the ground truth site is ignore, then adjust the site's activity dates accordingly
            if self.gt_stacks[gt_id].status in IGNORE_STATUS_TYPES:
                self.gt_stacks[gt_id].start_activity = gt_stack.start_date
                self.gt_stacks[gt_id].end_activity = gt_stack.end_date
                if gt_stack.start_activity and gt_stack.end_activity:
                    self.gt_stacks[gt_id].activity_dates = set(pd.date_range(start=gt_stack.start_activity, end=gt_stack.end_activity))
                    self.gt_stacks[gt_id].len_activity = len(gt_stack.activity_dates)
                else:
                    self.gt_stacks[gt_id].activity_dates = set()
                    self.gt_stacks[gt_id].len_activity = None

    @classmethod
    def get_site_stack_id(cls, input_path):
        """Create an identifier for a SiteStack (only for use with a database)"""
        with open(input_path) as f:
            site_feature = geojson.load(f)["features"][0]["properties"]
        site_id = f"{site_feature['site_id']}_{site_feature['originator']}_{site_feature['version']}"

        return site_id

    @classmethod
    @timer
    def stack_comparison(cls, gt_stack, sm_stack, metric_name, check_unary_union=False):
        """
        Compare a single pair of stacks by calculating geospatial similarity scores (IoU or GIoU) between their polygons
        :param gt_stack: a ground truth SiteStack object
        :param sm_stack: a site model SiteStack object
        :param metric_name: the name of the similarity metric to use for the comparison, such as "iou" or "giou" (str)
        :param check_unary_union: boolean flag to indicate whether the unary union of the gt_stack and the sm_stack should be compared, to quickly filter out stack comparisons that have no spatial overlap
        :return: a comparison table aligning the stack slices by date, with similarity scores for each pair of slices (DataFrame)
        """

        gt_uuids = []
        sm_uuids = []
        scores = []
        iot_scores = []
        iop_scores = []
        intersection_areas = []
        intersections = []
        union_areas = []
        unions = []
        valid_slices = []

        if check_unary_union and not gt_stack.check_unary_union(sm_stack):
            # none of the gt_stack polygons overlap with any of the sm_stack polygons
            gt_uuids = [0] * len(gt_stack.slices)
            sm_uuids = [0] * len(gt_stack.slices)
            scores = [0] * len(gt_stack.slices)
            iot_scores = [0] * len(gt_stack.slices)
            iop_scores = [0] * len(gt_stack.slices)
            intersection_areas = [0] * len(gt_stack.slices)
            intersections = [0] * len(gt_stack.slices)
            union_areas = [0] * len(gt_stack.slices)
            unions = [0] * len(gt_stack.slices)

        else:
            seen_post_construction = False

            # iterate through each slice of the ground truth stack
            for gt_slice in tqdm(gt_stack.slices, desc=f"compare truth site {gt_stack.id}"):
                # No Activity observations are not compared
                if gt_slice.phase == "No Activity":
                    continue
                # superfluous Post Construction observations (after the first Post Construction observation) are not compared
                elif gt_slice.phase == "Post Construction":
                    if seen_post_construction:
                        continue
                    else:
                        seen_post_construction = True
                valid_slices.append(gt_slice)

                # get the corresponding slice from the site model stack
                sm_slice = sm_stack.get_slice(gt_slice.date)

                if sm_slice:
                    # get similarity score
                    try:
                        with warnings.catch_warnings():
                            warnings.filterwarnings("ignore", "invalid value encountered in intersection")
                            warnings.filterwarnings("ignore", category=FutureWarning)
                            if metric_name == "iou":
                                score, intersection_area, intersection, union_area, union = Metric.calc_iou(gt_slice.df, sm_slice.df)
                            elif metric_name == "giou":
                                score, _, intersection_area, intersection, union_area, union = Metric.calc_giou(gt_slice.df, sm_slice.df)
                            else:
                                logging.error(f"Metric {metric_name} not recognized")
                                score, intersection_area, intersection, union_area, union = 0, 0, None, 0, None
                    except Exception as e:
                        logging.error(f"Exception comparing {gt_slice.id} vs. {sm_slice.id}")
                        logging.error(e)
                        score, intersection_area, intersection, union_area, union = 0, 0, None, 0, None

                # no corresponding slice from the site model stack was found
                else:
                    score, intersection_area, intersection, union_area, union = 0, 0, None, 0, None

                # save results
                gt_uuids.append(gt_slice.uuid)
                sm_uuids.append(sm_slice.uuid if sm_slice else None)
                scores.append(score)
                intersection_areas.append(intersection_area)
                intersections.append(intersection)
                union_areas.append(union_area)
                unions.append(union)
                iot_scores.append(0 if not intersection_area else Metric.calc_iot(gt_slice.df, sm_slice.df, intersection_area)[0])
                iop_scores.append(0 if not intersection_area else Metric.calc_iot(sm_slice.df, gt_slice.df, intersection_area)[0])

        # get the corresponding slices from the site model stack
        matched_sm_slices = [sm_stack.get_slice(gt_slice.date) for gt_slice in valid_slices]

        # build the DataFrame
        df = pd.DataFrame()
        df["gt_uuid"] = gt_uuids
        df["sm_uuid"] = sm_uuids
        df["date"] = pd.to_datetime([gt_slice.date for gt_slice in valid_slices])
        df["date"] = df["date"].dt.date
        df["truth phase"] = [gt_slice.phase for gt_slice in valid_slices]
        df["source"] = [gt_slice.source for gt_slice in valid_slices]
        df["proposal date"] = pd.to_datetime([sm_slice.date if sm_slice else None for sm_slice in matched_sm_slices])
        df["proposal date"] = [date if type(date) != pd._libs.tslibs.nattype.NaTType else "n/a" for date in df["proposal date"].dt.date]
        df["proposal source"] = [sm_slice.source if sm_slice else "n/a" for sm_slice in matched_sm_slices]
        df[metric_name] = scores
        df["iot"] = iot_scores
        df["iop"] = iop_scores
        df["intersection_geometry"] = [intersection.iloc[0].geometry.wkt if intersection is not None and not intersection.empty else None for intersection in intersections]
        df["intersection_area"] = intersection_areas
        df["union_geometry"] = [union.wkt if union else None for union in unions]
        df["union_area"] = union_areas

        # choose the best slice if there are multiple ground truth observations on the same date
        df = df.sort_values(by=["date", metric_name, "source"])
        df = df.drop_duplicates(subset=["date"], keep="last")

        return df

    @classmethod
    @timer
    def score_stack(cls, gt_stack, sm_stack, metric_name):
        """
        Retrieve / calculate the comparison table for a pair of stacks
        :param gt_stack: a ground truth site stack object
        :param sm_stack: a site model site stack object
        :param metric_name: the name of the similarity metric to use for the comparison, such as "iou" or "giou" (str)
        :return: a 3-tuple of (truth site id (str), site model id (str), stack comparison table (DataFrame))
        """
        # compare a new pair of stacks
        logging.debug(f"Calculating {metric_name} for {gt_stack.id} vs. {sm_stack.id} - RAM Used: {psutil.virtual_memory().percent}")
        df = Evaluation.stack_comparison(gt_stack, sm_stack, metric_name)

        return (gt_stack.id, sm_stack.id, df)

    @timer
    def save_mp_results(self, args):
        """
        Push results from segment_sites() to the multiprocessing queue
        :param args: the tuple argument returned by segment_sites()
        :return: no return value
        """
        self.queue.put(args)
        # gt_id, _, dataframes = args
        with self.lock:
            self.counter += 1
            print(f"\t{self.counter}/{Evaluation.total_truth_sites} site comparisons completed")

    @classmethod
    def get_sm_stack_id(cls, sm_stacks):
        """Generates the ID for a combined site stack
        :param sm_stacks: a list of SiteStacks that will be combined together
        :return: an ID for a stack that is the combination of the sm_stacks (str)"""
        return "_".join(sorted([str(stack.id) for stack in sm_stacks]))

    @classmethod
    @timer
    def segment_sites(cls, gt_stack, all_sm_stacks, metric_name, tau, rho, confidence_score_thresholds):
        """
        :param gt_stack: a ground truth SiteStack object
        :param all_sm_stacks: a list of SiteStack objects
        :param metric_name: the name of the similarity metric to use for the comparison, such as "iou" or "giou" (str)
        :param tau: the association threshold (float)
        :param rho: the detection threshold (float)
        :param confidence_score_thresholds: a list of confidence score thresholds to filter proposals from the list of all_sm_stacks
        :return: a 3-tuple of (truth site id (str), site model id (str), stack comparison table (DataFrame))
        """

        results = (gt_stack.id, [], [])

        proposal_cache = {}

        # filter the proposed site models based on the confidence score threshold
        for confidence_score_threshold in confidence_score_thresholds:
            sm_stacks = [sm_stack for sm_stack in all_sm_stacks if sm_stack.score >= confidence_score_threshold]

            # the truth site has no intersecting site models
            if len(sm_stacks) == 0:
                logging.debug(f"No intersecting site models for {gt_stack.id} at confidence >= {confidence_score_threshold}")
                continue

            # the truth site has exactly 1 intersecting site model, so get the site model stack
            elif len(sm_stacks) == 1:
                sm_stack = sm_stacks[0]
                sm_stack_id = sm_stack.id

            # if the truth site has multiple intersecting site models, construct the union of their stacks
            # (attempt to match the truth site with as many site models as possible)
            else:
                sm_stack_id = cls.get_sm_stack_id(sm_stacks)

            df = proposal_cache.get(sm_stack_id)
            if df is None:
                if len(sm_stacks) > 1:
                    sm_stack = gt_stack.combine_stacks(sm_stacks)
                # compare the truth stack with the proposed stack
                _, _, df = Evaluation.score_stack(gt_stack, sm_stack, metric_name)
                # save the comparison
                results[1].append(sm_stack)
                results[2].append(df)
                proposal_cache[sm_stack.id] = df
            scores = df[metric_name]
            detection_score = len(list(filter(lambda x: x >= tau, scores))) / len(scores) if len(scores) > 0 else 0

            # if the truth site only intersected with 1 site model, we're done
            if len(sm_stacks) == 1 or detection_score >= rho:
                continue

            # if the truth site fails to match with the proposal stack union,
            # remove individual site models from the stack union 1 at a time,
            # until the truth site matches

            # compare the truth site with each one of its site models individually
            detection_scores = []
            for sm_stack in sm_stacks:
                df = proposal_cache.get(sm_stack.id)
                if df is None:
                    _, _, df = Evaluation.score_stack(gt_stack, sm_stack, metric_name)
                    results[1].append(sm_stack)
                    results[2].append(df)
                    proposal_cache[sm_stack.id] = df
                scores = df[metric_name]
                detection_score = len(list(filter(lambda x: x >= tau, scores))) / len(scores) if len(scores) > 0 else 0
                detection_scores.append((sm_stack, detection_score))

            # sort the site models based on their comparison with the truth site
            # (ascending order, lowest-scoring site model first)
            detection_scores.sort(key=lambda x: (x[1], x[0].id))

            # construct a new union of proposal stacks, by removing the worst site model
            remaining_stacks = [tup[0] for tup in detection_scores][1:]

            # attempt to match the truth site with the remaining site models, if any
            detection_score = -1
            while detection_score <= rho and remaining_stacks:
                if len(remaining_stacks) == 1:
                    sm_stack = remaining_stacks[0]
                    sm_stack_id = sm_stack.id
                else:
                    sm_stack_id = cls.get_sm_stack_id(remaining_stacks)

                df = proposal_cache.get(sm_stack_id)
                if df is None:
                    if len(sm_stacks) > 1:
                        sm_stack = gt_stack.combine_stacks(remaining_stacks)
                    # score the stack union
                    _, _, df = Evaluation.score_stack(gt_stack, sm_stack, metric_name)
                    # save the results
                    results[1].append(sm_stack)
                    results[2].append(df)
                    proposal_cache[sm_stack.id] = df
                scores = df[metric_name]
                detection_score = len(list(filter(lambda x: x >= tau, scores))) / len(scores) if len(scores) > 0 else 0
                detection_scores.append((sm_stack, detection_score))

                # remove the site model with the lowest score in case another iteration is necessary
                remaining_stacks.pop(0)

        return results

    @timer
    def compare_stacks(self):
        """
        Compare multiple pairs of site stacks and get similarity scores
        Function call stack:
            stack_comparison()
            score_stack()
            segment_sites()
            compare_stacks()
        1. Compare each truth site with the intersecting site model(s), if any
        2. If a truth site intersects with multiple site models, attempt to match all of them by combining them into a single stack
        3. If the comparison score between the truth site and the site model union fails to exceed the detection threshold,
            remove the site model with the lowest score from the union and retry the match
        :return: updates the nested dictionary of comparison tables for each pair of site stacks (self.stack_comparisons)
            {ground truth site name: {site model name: comparison table}}
        """
        logging.info("Comparing site stacks...")

        if not self.sm_stacks:
            logging.critical("No proposed site models to compare")
            return
        elif self.sm_stack_gdf.empty:
            logging.critical("No bounded proposed site models to compare")
            return

        # map each truth site to its potentially matching site model(s)
        pair_dict = defaultdict(set)

        combined_stacks = []

        # initial filtering to remove (ground truth, proposal) pairs that have no spatial intersection
        if self.metric_name == "iou":
            # build the spatial index
            logging.debug("Building a spatial index")
            gt_idx_to_sm_idxs = {}
            sm_stack_index = self.sm_stack_gdf.sindex

            # map each truth site to its intersecting site model(s)
            for gt_idx, gt_row in tqdm(
                self.gt_stack_gdf.iterrows(),
                total=len(self.gt_stack_gdf),
                desc="compare stacks",
            ):
                sm_idxs = sm_stack_index.query(gt_row.geometry, predicate="intersects")
                gt_idx_to_sm_idxs[gt_idx] = sm_idxs

            for gt_idx, sm_idxs in gt_idx_to_sm_idxs.items():
                gt_id = self.gt_stack_gdf["stack"].iloc[gt_idx]
                sm_ids = self.sm_stack_gdf["stack"].iloc[sm_idxs].values.tolist()
                if self.gt_stacks[gt_id].start_activity and self.gt_stacks[gt_id].end_activity:
                    pair_dict[self.gt_stack_gdf.iloc[gt_idx]["stack"]].update([sm_id for sm_id in sm_ids if self.sm_stacks[sm_id].start_date <= self.gt_stacks[gt_id].end_activity and self.sm_stacks[sm_id].end_date >= self.gt_stacks[gt_id].start_activity])
                else:
                    pair_dict[self.gt_stack_gdf.iloc[gt_idx]["stack"]].update([sm_id for sm_id in sm_ids if self.sm_stacks[sm_id].start_date <= self.gt_stacks[gt_id].end_date and self.sm_stacks[sm_id].end_date >= self.gt_stacks[gt_id].start_date])

        else:
            for gt_id in self.gt_stacks:
                pair_dict[gt_id] = set([sm_id for sm_id in self.sm_stacks if self.sm_stacks[sm_id].start_date <= self.gt_stacks[gt_id].end_activity and self.sm_stacks[sm_id].end_date >= self.gt_stacks[gt_id].start_activity])
        logging.debug(f"Found {len(pair_dict)} stack pairs: {pair_dict}")
        Evaluation.comparable_truth_sites = len([v for v in pair_dict.values() if v])
        Evaluation.total_truth_sites = len(pair_dict)

        # get the necessary number of threads
        if not self.num_processes:
            self.num_processes = min(len(pair_dict), mp.cpu_count() - 1)

        # use multiprocessing
        if self.parallel and self.num_processes > 1:
            # create a multiprocessing pool
            logging.debug(f"Creating {self.num_processes} new parallel processes")
            pool = mp.Pool(self.num_processes)

            raw_sm_ids = set()

            # send stack comparison tasks to the processes
            logging.debug(f"Performing {len(pair_dict)} site stack comparisons")
            for gt_id, sm_ids in pair_dict.items():
                raw_sm_ids.update(sm_ids)
                gt_stack = self.gt_stacks[gt_id]
                stacks_to_segment = [self.sm_stacks[sm_id] for sm_id in sm_ids]
                args = (gt_stack, stacks_to_segment, self.metric_name, 1, 1, self.confidence_score_thresholds)
                pool.apply_async(Evaluation.segment_sites, args=args, callback=self.save_mp_results)

            # cleanup
            pool.close()
            pool.join()

            # retrieve the comparison tables from the queue
            while self.counter:
                gt_id, sm_stacks, dataframes = self.queue.get()
                self.counter -= 1
                logging.debug(f"Getting {gt_id} from the queue")
                for sm_stack, df in zip(sm_stacks, dataframes):
                    self.stack_comparisons[gt_id][sm_stack.id] = df
                    if sm_stack.id not in self.sm_stacks:
                        self.sm_stacks[sm_stack.id] = sm_stack
                    if sm_stack.id not in raw_sm_ids:
                        combined_stacks.append(sm_stack)

            self.queue.close()
            self.queue.join_thread()

        # use serial processing
        else:
            logging.info("Using serial processing")

            # iterate through each truth site and its intersecting site model(s)
            serial_counter = 0
            for gt_id, sm_ids in pair_dict.items():
                gt_stack = self.gt_stacks[gt_id]
                stacks_to_segment = [self.sm_stacks[sm_id] for sm_id in sm_ids]
                gt_id, sm_stacks, dataframes = Evaluation.segment_sites(gt_stack, stacks_to_segment, self.metric_name, 1, 1, self.confidence_score_thresholds)
                for sm_stack, df in zip(sm_stacks, dataframes):
                    self.stack_comparisons[gt_id][sm_stack.id] = df
                    if sm_stack.id not in self.sm_stacks:
                        self.sm_stacks[sm_stack.id] = sm_stack
                    if sm_stack.id not in sm_ids:
                        combined_stacks.append(sm_stack)
                if dataframes:
                    serial_counter += 1
                    print(f"\t{serial_counter}/{Evaluation.comparable_truth_sites} site comparisons completed")

        if DEV:
            if self.smart_database_api:
                self.insert_sites(combined_stacks)
                self.insert_site_comparisons()

    @timer
    def insert_site_comparisons(self):
        """
        Database - DEV Only
        """
        add_list = []
        for gt_site_id in self.stack_comparisons.keys():
            for sm_site_id in self.stack_comparisons[gt_site_id].keys():
                for index, row in self.stack_comparisons[gt_site_id][sm_site_id].iterrows():
                    row = row.copy(deep=True).replace({"n/a": None})

                    add_list.append(
                        ObservationComparison(
                            observation_truth_uuid=row["gt_uuid"],
                            observation_proposal_uuid=row["sm_uuid"],
                            intersection_geometry=row["intersection_geometry"],
                            union_geometry=row["union_geometry"],
                            intersection_area=row["intersection_area"],
                            union_area=row["union_area"],
                        )
                    )

        self.smart_database_api.add_all(add_list)


    @timer
    def visualize_failed_associations_table(
        self,
        failed_associations,
        tau,
        rho,
        min_area,
        min_score,
        save_output=True,
    ):
        """
        Creates a failed_associations table
        A failed_assocations table lists every combination of ground truth site and proposed site model(s) that have spatial and temporal overlap
        that are nonzero yet insufficient for association, based on the association parameter thresholds. A ground truth site can be listed in
        multiple rows in this table if there are multiple different combinations of proposals that have nonzero spatial and temporal overlap with it.
        A ground truth site can also be listed in both the detections table and in the failed associations table if there is a proposal,
        or a combination of proposals, that has overlap with the truth site sufficient to meet the association thresholds,
        as well as another proposal or combination of proposals that does not have overlap sufficient to meet the thresholds.

        :param failed_associations: a list of tuples (such as the one created in build_scoreboard()) of the form (gt_id, sm_id, spatial overlap score, tiot score, tiop score)
        :param tau: the association threshold (float)
        :param rho: the detection threshold (float)
        :parm min_area: the minimum area threshold (float)
        :parm min_score: the minimum confidence score threshold (float)
        :param save_output: write the tables to a CSV files (bool)
        :return: None
        """
        logging.debug("Visualizing Failed BAS associations...")

        # (gt_id, sm_id, spatial_overlap/matched_proportion, temporal_iot, temporal_iop)
        failed_associations_df = pd.DataFrame()
        failed_associations_df["site type"] = [self.gt_stacks[failed_association_tuple[0]].status for failed_association_tuple in failed_associations]
        failed_associations_df["truth site"] = [failed_association_tuple[0] for failed_association_tuple in failed_associations]
        failed_associations_df["proposal site"] = [failed_association_tuple[1] for failed_association_tuple in failed_associations]
        failed_associations_df["spatial overlap"] = [failed_association_tuple[2] for failed_association_tuple in failed_associations]
        failed_associations_df["temporal iot"] = [failed_association_tuple[3] for failed_association_tuple in failed_associations]
        failed_associations_df["temporal iop"] = [failed_association_tuple[4] for failed_association_tuple in failed_associations]
        failed_associations_df["truth activity start date"] = [self.gt_stacks[failed_association_tuple[0]].start_activity for failed_association_tuple in failed_associations]
        failed_associations_df["truth activity end date"] = [self.gt_stacks[failed_association_tuple[0]].end_activity for failed_association_tuple in failed_associations]
        failed_associations_df["proposal activity start date"] = [self.sm_stacks[failed_association_tuple[1]].start_activity for failed_association_tuple in failed_associations]
        failed_associations_df["proposal activity end date"] = [self.sm_stacks[failed_association_tuple[1]].end_activity for failed_association_tuple in failed_associations]
        failed_associations_df.sort_values("site type", inplace=True, ignore_index=True)

        failed_associations_df_raw = failed_associations_df.copy(deep=True)
        failed_associations_df_raw["rho"] = rho
        failed_associations_df_raw["tau"] = tau
        failed_associations_df_raw["min area"] = min_area
        failed_associations_df_raw["min score"] = min_score

        # save to file
        if self.bas_dir and save_output:
            failed_associations_df = Evaluation.sanitize_dataframe(failed_associations_df, self.region_model.id, self.sequestered_id)
            failed_associations_df = failed_associations_df.sort_values(by="truth site") if "truth site" in failed_associations_df.columns else failed_associations_df
            failed_associations_df.to_csv(
                f"{self.bas_dir}/failAssoc_tau={tau}_rho={rho}_minArea={min_area}_minScore={min_score}.csv",
                index=False,
            )

        return failed_associations_df_raw

    @timer
    def visualize_detection_table(
        self,
        detections,
        proposals,
        tau,
        rho,
        min_area,
        min_score,
        site_types,
        save_output=True,
    ):
        """
        Creates a detections table, a proposals table, and a site types table
        A detections table lists each of the ground truth sites, along with the proposed site model(s) that were associated with each truth site
        A proposals table lists each of the proposed site models, along with the truth site(s) that were associated with each proposal
        A site types table lists each type of ground truth site, along with the counts of the proposals that were associated with each type

        :param detections: a dict (such as Evaluation.detections) mapping each truth site to its matched site model(s) (0 or more)
        :param proposals: a dict (such as Evaluation.proposals) mapping each site model to its matched truth site(s) (0 or more)
        :param tau: the association threshold (float)
        :param rho: the detection threshold (float)
        :parm min_area: the minimum area threshold (float)
        :parm min_score: the minimum confidence score threshold (float)
        :parm site_types: a dict (such as the one created in buildd_scoreboard()) that maps a ground truth status type to a list of proposed site model IDs
        :param save_output: write the tables to a CSV files (bool)
        :return: None
        """
        logging.debug("Visualizing BAS detections...")

        #def highlight_table(df, highlight_col="site count"):
        #    # convert DataFrame cells to strings
        #    df_style = df.copy().astype(str)
        #    # Initialize all styles to None, and then conditionally
        #    df_style.loc[:, :] = None
        #    # highlight cells where % detected >= detection threshold
        #    for idx in df.index:
        #        if int(df.at[idx, "site count"]) == 0:
        #            if "site type" not in df:
        #                df_style.at[idx, "site count"] = "background-color: bisque"
        #            elif df.at[idx, "site type"] in POSITIVE_STATUS_TYPES:
        #                df_style.at[idx, highlight_col] = "background-color: bisque"
        #        elif int(df.at[idx, "site count"]) > 0:
        #            if "site type" in df:
        #                if df.at[idx, "site type"] in POSITIVE_STATUS_TYPES:
        #                    df_style.at[idx, highlight_col] = "background-color: lightblue"
        #                elif df.at[idx, "site type"] in NEGATIVE_STATUS_TYPES:
        #                    df_style.at[idx, highlight_col] = "background-color: coral"
        #    return df_style

        # detections table: highlight false negatives
        detections_df = pd.DataFrame()
        detections_df["site type"] = [self.gt_stacks[gt_id].status for gt_id in detections]
        detections_df["truth site"] = detections.keys()
        detections_df["site area"] = [self.gt_stacks[gt_id].area for gt_id in detections]
        highlight_col = f"detection score (tau = {tau}, rho = {rho}, min area = {min_area})"
        matched_site_models_list, detection_score_list, spatial_overlap_list, tiot_list, tiop_list = [], [], [], [], []
        for tuples in detections.values():
            best_tuple = max(tuples, key=lambda x: (len(self.sm_stacks[x[0]].sites), x[1], x[0])) if len(tuples) > 0 else ()
            matched_site_models_list.append(self.sm_stacks[best_tuple[0]].sites if len(best_tuple) else [])
            detection_score_list.append(best_tuple[1] if 0 < len(best_tuple) <= 2 else None)
            spatial_overlap_list.append(best_tuple[1] if len(best_tuple) > 2 else None)
            tiot_list.append(best_tuple[2] if len(best_tuple) > 2 else None)
            tiop_list.append(best_tuple[3] if len(best_tuple) > 2 else None)
        detections_df["matched site models"] = matched_site_models_list
        detections_df[highlight_col] = detection_score_list
        detections_df["spatial overlap"] = spatial_overlap_list
        detections_df["temporal iot"] = tiot_list
        detections_df["temporal iop"] = tiop_list
        detections_df["site count"] = [len(sm) for sm in detections_df["matched site models"]]
        detections_df["matched site models"] = [", ".join(sm) for sm in detections_df["matched site models"]]
        detections_df["association status"] = [self.gt_stacks[gt_id].association_status for gt_id in detections_df["truth site"]]
        detections_df["associated"] = [self.gt_stacks[gt_id].associated for gt_id in detections_df["truth site"]]
        detections_df["color code"] = [self.gt_stacks[gt_id].color for gt_id in detections_df["truth site"]]
        detections_df.sort_values("site type", inplace=True, ignore_index=True)

        # detections_df_styled = detections_df.style.apply(highlight_table, axis=None, highlight_col=highlight_col)
        # detections_df_styled = detections_df_styled.hide_columns(["site count"])  # Deprecated
        # detections_df_styled = detections_df_styled.hide(["site count"], axis="columns")

        # proposals table: highlight false positives
        proposals_df = pd.DataFrame()
        if self.sm_stacks and proposals:
            proposals_df["site model"], proposals_df["site area"], proposals_df["matched truth sites"] = zip(*[(sm_id, self.sm_stacks[sm_id].area, gt_ids) if gt_ids else (sm_id, self.sm_stacks[sm_id].area, "") for sm_id, gt_ids in proposals.items() if len(self.sm_stacks[sm_id].sites) == 1])
            proposals_df["site count"] = [len(gt) for gt in proposals_df["matched truth sites"]]
            proposals_df["matched truth sites"] = [", ".join(gt) for gt in proposals_df["matched truth sites"]]
            proposals_df["association status"] = [self.sm_stacks[sm_id].association_status for sm_id in proposals_df["site model"]]
            proposals_df["associated"] = [self.sm_stacks[sm_id].associated for sm_id in proposals_df["site model"]]
            proposals_df["color code"] = [self.sm_stacks[sm_id].color for sm_id in proposals_df["site model"]]
            # proposals_df_styled = proposals_df.style.apply(highlight_table, axis=None)

        # site types table
        site_types_df = pd.DataFrame()
        site_types_df["site type"] = site_types.keys()
        site_types_df["proposed site count"] = [len(sm_ids) for sm_ids in site_types.values()]

        # add threshold values to the tables
        detections_df_raw = detections_df.copy(deep=True)
        detections_df_raw["rho"] = rho
        detections_df_raw["tau"] = tau
        detections_df_raw["min area"] = min_area
        detections_df_raw["min score"] = min_score
        proposals_df_raw = proposals_df.copy(deep=True)
        proposals_df_raw["rho"] = rho
        proposals_df_raw["tau"] = tau
        proposals_df_raw["min area"] = min_area
        proposals_df_raw["min score"] = min_score

        # save to file
        if self.bas_dir and save_output:
            detections_df = Evaluation.sanitize_dataframe(detections_df, self.region_model.id, self.sequestered_id)
            detections_df = detections_df.sort_values(by="truth site") if "truth site" in detections_df.columns else detections_df
            proposals_df = Evaluation.sanitize_dataframe(proposals_df, self.region_model.id, self.sequestered_id)
            proposals_df = proposals_df.sort_values(by="site model") if "site model" in proposals_df.columns else proposals_df
            detections_df.to_csv(
                f"{self.bas_dir}/detections_tau={tau}_rho={rho}_minArea={min_area}_minScore={min_score}.csv",
                index=False,
            )
            proposals_df.to_csv(f"{self.bas_dir}/proposals_tau={tau}_rho={rho}_minArea={min_area}_minScore={min_score}.csv", index=False)
            site_types_df.to_csv(f"{self.bas_dir}/siteType_tau={tau}_rho={rho}_minArea={min_area}_minScore={min_score}.csv", index=False)
 
        return detections_df_raw, proposals_df_raw

    @timer
    def build_f_score_table(
        self,
        scoreboard,
        table_threshold_name,
        table_threshold,
        row_threshold_name,
        save_output=True,
        betas=[1 / 3, 0.5, 1, 2, 3],
    ):
        """
        :param scoreboard: DataFrame with rho, tau, precision, recall
        :param table_threshold_name: the name of the threshold held constant for the entire scoreboard
        :param table_threshold: the value of the threshold held constant for the entire scoreboard
        :param row_threshold_name: the name of the threshold varied across the rows of the scoreboard
        :param save_output: write the table to a CSV file (bool)
        :param betas: the beta values to use to compute the F scores (list of floats)
        :return: a dataframe of F scores (DataFrame)
        """

        f_score_table_rows = []

        for index, row in scoreboard.iterrows():
            # get values for f_score_table
            precision = row["precision"]
            recall = row["recall (PD)"]

            # build f_score table
            f_row = {}
            f_row[row_threshold_name] = index
            f_row["precision"] = precision
            f_row["recall (PD)"] = recall

            # calculate f_beta scores
            for beta in betas:
                if precision or recall:
                    f_score = (1 + beta**2) * ((precision * recall) / ((beta**2 * precision) + recall))
                else:
                    logging.debug(f"F_{beta} is zero because precision and recall are zero")
                    f_score = 0
                f_row[f"f_{round(beta, 2)}"] = f_score

            # add row to f_score_table (metrics per value of detection threshold rho)
            f_score_table_rows.append(f_row)

        # Convert list of dictionaries into a dataframe
        f_score_table = pd.DataFrame(f_score_table_rows)
        f_score_table = f_score_table.sort_values(row_threshold_name).drop_duplicates(subset=row_threshold_name).set_index(row_threshold_name)

        # save table to file
        if self.bas_dir and save_output:
            f_score_table_round = f_score_table.round(4)
            f_score_table_round.to_csv(f"{self.bas_dir}/f_score_table_{table_threshold_name}={table_threshold}.csv")

        return f_score_table

    @timer
    def build_scoreboard(
        self,
        table_threshold_name,
        table_threshold,
        row_threshold_name,
        row_thresholds,
        min_score=0,
        use_iot=True,
        viz_detection_table=True,
        save_output=True,
    ):
        """
        Creates a table of performance metrics, such as precision, recall, and F1 score
        :param table_threshold_name: the name of the threshold held constant for the entire scoreboard
        :param table_threshold: the value of the threshold held constant for the entire scoreboard
        :param row_threshold_name: the name of the threshold varied across the rows of the scoreboard
        :param row_thresholds: the values of the threshold varied across the rows of the scoreboard
        :param min_score: the minimum confidence score of all the sites involved in building this scoreboard (defaults to 0)
        :param use_iot: if sites fail to meet the IoU threshold, attempt to match them using IoT
        :param viz_detection_table: create a detection table using visualize_detection_table() (bool)
        :param save_output: write the table to a CSV file (bool)

        makes updates to:
            self.best_metric_score (float): the highest metric score (currently using F1) achieved using
                the optimal thresholds, used to save the corresponding optimal results:
            self.detections: a dict mapping each truth site to its matched site model(s) (0 or more)
            self.proposals: a dict mapping each site model to its matched truth site(s) (0 or more)
            self.site_types: a dict mapping each truth site type to its matched site model(s)
            self.matched_pairs: a list of the matched pairs [ (gt_id, sm_id), ... ]
        :return: scoreboard (DataFrame)
        """

        # initialize scoreboard
        scoreboard_rows = []
        scoreboard_rows_raw = []
        detections_df_raw_list = []
        proposals_df_raw_list = []
        failed_assoc_df_raw_list = []

        # build up 1 row at a time
        for row_threshold in sorted(row_thresholds):
            # get tau, rho, and the other threshold values
            thresholds = [
                (table_threshold_name, table_threshold),
                (row_threshold_name, row_threshold),
            ]
            tau = next(
                iter([tup[1] for tup in thresholds if tup[0] == "tau"]),
                self.default_tau,
            )
            rho = next(
                iter([tup[1] for tup in thresholds if tup[0] == "rho"]),
                self.default_rho,
            )
            min_area = next(
                iter([tup[1] for tup in thresholds if tup[0] == "Min Area"]),
                self.default_min_area,
            )
            min_score = next(iter([tup[1] for tup in thresholds if tup[0] == "Min Confidence"]), 0)

            # save the best results for each row threshold
            detections = defaultdict(list)
            failed_associations = []
            attempted_iot = []  # a list of truth sites not initially detected by IoU, but potentially detected by IoT

            # filter proposals by minimum area
            sm_ids_to_keep = set()
            for sm_id in self.sm_stacks:
                for site in self.sm_stacks[sm_id].sites:
                    # Check area
                    if self.sm_stacks[site].area * 1e6 < min_area:
                        logging.debug(f"{site} < {min_area} square meters")
                        break

                    # Check the minimum confidence score
                    site_score = self.sm_stacks[site].score
                    if site_score < min_score:
                        logging.debug(f"{site} < {min_score} confidence score")
                        break
                else:
                    sm_ids_to_keep.add(sm_id)
            logging.debug(f"{len(sm_ids_to_keep)} site models > {min_area} square meters and >= {min_score} confidence score)")

            proposals = {sm_id: [] for sm_id in sm_ids_to_keep}
            proposed_slices = 0

            site_types = defaultdict(set)
            matched_pairs = []
            tp, tp_exact, tp_over, tp_under, tp_under_iou, tp_under_iot, fp, fn, tn = 0, 0, 0, 0, 0, 0, 0, 0, 0

            # score each (ground truth, proposal) comparison
            for gt_id, sm_ids in self.stack_comparisons.items():
                gt_stack = self.gt_stacks[gt_id]
                self.gt_stacks[gt_id].association_status = None
                self.gt_stacks[gt_id].associated = None
                self.gt_stacks[gt_id].color = None

                # sort the valid proposals by the number of sites they are composed of (prioritize combined site stacks)
                for sm_id in sorted(list(set(sm_ids) & sm_ids_to_keep), key=lambda sm_id: len(self.sm_stacks[sm_id].sites), reverse=True):
                    sm_stack = self.sm_stacks[sm_id]
                    self.sm_stacks[sm_id].association_status = None
                    self.sm_stacks[sm_id].associated = None
                    self.sm_stacks[sm_id].color = None

                    # the ground truth site must have some temporal duration in order to be associated
                    if not gt_stack.len_activity or not sm_stack.len_activity:
                        continue

                    # for each dataframe, calculate the % of its observations that were detected
                    df = self.stack_comparisons[gt_id][sm_id]
                    if df.empty:
                        continue

                    # spatial overlap
                    # use spatial IoP for ignore-type sites
                    if gt_stack.status in IGNORE_STATUS_TYPES:
                        # only use the first and the last truth observations of an ignore-type truth site for BAS association
                        first_and_last = pd.concat([df.head(1), df.tail(1)])
                        iop_score = len(list(filter(lambda x: x >= tau, first_and_last["iop"]))) / len(first_and_last["iop"])
                        spatial_overlap = iop_score
                    # use spatial IoU and IoT for other sites
                    else:
                        iou_score = len(list(filter(lambda x: x >= tau, df[self.metric_name]))) / len(df[self.metric_name])
                        spatial_overlap = iou_score
                        if iou_score < rho and use_iot:
                            logging.debug(f"No detections of {gt_id} with {self.metric_name}, now trying with IoT")
                            iot_score = len(list(filter(lambda x: x >= tau, df["iot"]))) / len(df["iot"])
                            attempted_iot.append(gt_id)
                            spatial_overlap = iot_score

                    # temporal overlap
                    # use temporal IoT and IoP for all sites
                    if not gt_stack.len_activity:
                        tiot = 0
                        tiop = 0
                    elif gt_stack.status in POSITIVE_ACTIVITY_STATUS_TYPES:
                        tiot = len(gt_stack.min_activity_dates.intersection(sm_stack.activity_dates)) / gt_stack.len_min_activity
                        tiop = len(gt_stack.max_activity_dates.intersection(sm_stack.activity_dates)) / sm_stack.len_activity
                    else:
                        tiot = len(gt_stack.activity_dates.intersection(sm_stack.activity_dates)) / gt_stack.len_activity
                        tiop = len(gt_stack.activity_dates.intersection(sm_stack.activity_dates)) / sm_stack.len_activity

                    # determine whether the thresholds were met for the truth site to be detected
                    if gt_stack.status in IGNORE_STATUS_TYPES:
                        if "transient" in gt_stack.status:
                            detected = spatial_overlap >= rho and tiop >= self.transient_temporal_iop
                        else:
                            detected = spatial_overlap >= rho and tiop >= self.temporal_iop
                    else:
                        if "transient" in gt_stack.status:
                            detected = spatial_overlap >= rho and tiop >= self.transient_temporal_iop and tiot >= self.transient_temporal_iot
                        else:
                            detected = spatial_overlap >= rho and tiop >= self.temporal_iop and tiot >= self.temporal_iot

                    # each truth site from the stack_comparisons dict is detected (thresholds were met) or
                    # failed to associate (the truth site had some spatial and temporal overlap with a proposal, but the thresholds were not met)
                    if detected:
                        # add every proposal that meets the thresholds for the truth site
                        # (there can be more than 1 valid candidate proposal for association)
                        detections[gt_id].append((sm_id, spatial_overlap, tiot, tiop))
                    else:
                        # add every proposal that has non-zero overlap with the truth site but fails to meet the thresholds
                        failed_associations.append((gt_id, sm_id, spatial_overlap, tiot, tiop))

                # the truth site was detected by 1 or more candidate site model proposals
                if detections[gt_id]:
                    # choose the proposal with the most over-segmented sites, in order to minimize false positives
                    # the next tie-breaker between candidate proposals is the spatial overlap score
                    # the next tie-breaker between candidate proposals is the site name
                    sm_id, *_ = max(detections[gt_id], key=lambda x: (len(self.sm_stacks[x[0]].sites), x[1], x[0]))
                    logging.debug(f"Detected gt {gt_id} with sm {sm_id}")
                    proposed_slices += len(self.sm_stacks[sm_id].slices)
                    matched_pairs.append((gt_id, sm_id))
                    sm_match_stack = self.sm_stacks[sm_id]

                    # over-segmented proposals
                    for sub_sm_id in sm_match_stack.sites:
                        proposals[sub_sm_id].append(gt_id)
                        site_types[gt_stack.status].add(sub_sm_id)

                    # score the detected truth site based on its effective status
                    if gt_stack.status in POSITIVE_STATUS_TYPES:
                        self.gt_stacks[gt_id].association_status = "tp"
                        self.gt_stacks[gt_id].associated = True
                        self.gt_stacks[gt_id].color = 2
                        tp += 1
                    elif gt_stack.status in NEGATIVE_STATUS_TYPES:
                        self.gt_stacks[gt_id].association_status = "fp"
                        self.gt_stacks[gt_id].associated = True
                        self.gt_stacks[gt_id].color = 5
                        fp += 1
                    elif gt_stack.status in POSITIVE_UNBOUNDED_STATUS_TYPES:
                        self.gt_stacks[gt_id].association_status = "0"
                        self.gt_stacks[gt_id].associated = True
                        self.gt_stacks[gt_id].color = 8
                    elif gt_stack.status in ANNOTATED_IGNORE_STATUS_TYPES:
                        self.gt_stacks[gt_id].association_status = "0"
                        self.gt_stacks[gt_id].associated = True
                        self.gt_stacks[gt_id].color = 11

                # the truth site was not detected
                else:
                    logging.debug(f"Missed gt {gt_id}")

                    # score the missed truth site based on its effective status
                    if gt_stack.status in POSITIVE_STATUS_TYPES:
                        self.gt_stacks[gt_id].association_status = "fn"
                        self.gt_stacks[gt_id].associated = False
                        self.gt_stacks[gt_id].color = 3
                        fn += 1
                    elif gt_stack.status in NEGATIVE_STATUS_TYPES:
                        self.gt_stacks[gt_id].association_status = "tn"
                        self.gt_stacks[gt_id].associated = False
                        self.gt_stacks[gt_id].color = 6
                        tn += 1
                    elif gt_stack.status in POSITIVE_UNBOUNDED_STATUS_TYPES:
                        self.gt_stacks[gt_id].association_status = "0"
                        self.gt_stacks[gt_id].associated = False
                        self.gt_stacks[gt_id].color = 9
                    elif gt_stack.status in ANNOTATED_IGNORE_STATUS_TYPES:
                        self.gt_stacks[gt_id].association_status = "0"
                        self.gt_stacks[gt_id].associated = False
                        self.gt_stacks[gt_id].color = 12

            # compute area-based metrics
            proposal_area, fp_area = 0, 0
            proposal_areas, nonneg_areas = [], []
            union_nonneg_area = Polygon()

            for sm_id, gt_ids in proposals.items():
                # only include stacks with a single site model
                if len(self.sm_stacks[sm_id].sites) == 1:

                    # get proposal areas
                    try:
                        proposal_areas.append(self.sm_stacks[sm_id].polygon_union)
                    except Exception:
                        logging.warning(f"{sm_id} does not have a polygon union")
                        proposal_areas.append(self.sm_stacks[sm_id].polygons[0])

                    # get ground truth annotation areas
                    for gt_id in gt_ids:
                        gt_stack = self.gt_stacks[gt_id]
                        if gt_stack.status not in NEGATIVE_STATUS_TYPES:
                            nonneg_areas.append(gt_stack.check_unary_union(self.sm_stacks[sm_id]))

            if proposal_areas:
                union_proposal_area = unary_union(proposal_areas)
                if type(union_proposal_area) == Polygon:
                    union_proposal_area = MultiPolygon([union_proposal_area])
                # compute combined proposal area
                proposal_area = GeometryUtil.compute_region_area(union_proposal_area)
                if nonneg_areas:
                    union_nonneg_area = unary_union(nonneg_areas)
                    if type(union_nonneg_area) == Polygon:
                        union_nonneg_area = MultiPolygon([union_nonneg_area])
                    # compute area of proposal polygons that were false positive pixels
                    fp_area = GeometryUtil.compute_region_area(union_proposal_area.difference(union_nonneg_area))

            # score the proposals
            for sm_id, gt_ids in proposals.items():
                match_statuses = [self.gt_stacks[gt_id].status for gt_id in gt_ids]
                # at least 1 positive match
                if set(match_statuses) & set(POSITIVE_STATUS_TYPES):
                    # and at least 1 negative match (partially wrong)
                    if set(match_statuses) & set(NEGATIVE_STATUS_TYPES):
                        self.sm_stacks[sm_id].association_status = "tpfp"
                        self.sm_stacks[sm_id].associated = True
                        self.sm_stacks[sm_id].color = 23
                    else:
                        self.sm_stacks[sm_id].association_status = "tp"
                        self.sm_stacks[sm_id].associated = True
                        self.sm_stacks[sm_id].color = 24
                # only negative matches (completely wrong)
                elif set(match_statuses) & set(NEGATIVE_STATUS_TYPES):
                    self.sm_stacks[sm_id].association_status = "fp"
                    self.sm_stacks[sm_id].associated = True
                    self.sm_stacks[sm_id].color = 25
                # only ignore matches
                elif set(match_statuses) & set(IGNORE_STATUS_TYPES):
                    self.sm_stacks[sm_id].association_status = "0"
                    self.sm_stacks[sm_id].associated = True
                    self.sm_stacks[sm_id].color = 26

                # only include stacks with a single site model
                if not gt_ids and len(self.sm_stacks[sm_id].sites) == 1:
                    self.sm_stacks[sm_id].association_status = "fp"
                    self.sm_stacks[sm_id].associated = False
                    self.sm_stacks[sm_id].color = 22
                    fp += 1
                    proposed_slices += len(self.sm_stacks[sm_id].slices)
                    site_types["false alarm"].add(sm_id)

            # count the over/under/exact segmentations
            for gt_id, sm_id in matched_pairs:
                if self.gt_stacks[gt_id].status in POSITIVE_STATUS_TYPES:
                    matched_site_models = self.sm_stacks[sm_id].sites
                    if len(matched_site_models) == 1:
                        if len(proposals[sm_id]) == 1:
                            logging.debug(f"{gt_id} was detected with a single proposal {sm_id}")
                            tp_exact += 1
                        elif len(proposals[sm_id]) > 1:
                            logging.debug(f"{gt_id} was detected with an under-segmented proposal {sm_id}")
                            tp_under += 1
                            if gt_id in attempted_iot:
                                tp_under_iot += 1
                            else:
                                tp_under_iou += 1
                    elif len(matched_site_models) > 1:
                        logging.debug(f"{gt_id} was detected with {len(matched_site_models)} over-segmented proposals {sm_id}")
                        tp_over += 1

            # normalize the false positive area
            fpa = proposal_area / self.region_model.area
            ffpa = fp_area / GeometryUtil.compute_region_area(self.region_model.polygon.difference(union_nonneg_area))

            # calculate metrics
            precision = Metric.calc_precision(tp, fp)
            recall = Metric.calc_recall(tp, fn)
            f1 = Metric.calc_F1(tp, fp, fn)

            # build scoreboard table
            row = {}
            row[row_threshold_name] = row_threshold
            row["tp sites"] = tp
            row["tp exact"] = tp_exact
            row["tp under"] = tp_under
            row["tp under (IoU)"] = tp_under_iou
            row["tp under (IoT)"] = tp_under_iot
            row["tp over"] = tp_over
            row["fp sites"] = fp
            row["fp area"] = fp_area
            row["ffpa"] = ffpa
            row["proposal area"] = proposal_area
            row["fpa"] = fpa
            row["fn sites"] = fn
            row["truth annotations"] = len(self.gt_files)
            row["truth sites"] = tp + fn
            row["proposed annotations"] = len(self.sm_files)
            row["confident annotations"] = len([sm_id for sm_id in self.sm_stacks if self.sm_stacks[sm_id].score >= min_score and len(self.sm_stacks[sm_id].sites) == 1])
            row["proposed sites"] = tp + fp
            row["total sites"] = tp + fp + fn
            row["truth slices"] = sum([len(self.gt_stacks[gt_id].slices) for gt_id in self.gt_stacks])
            row["proposed slices"] = proposed_slices
            row["precision"] = precision
            row["recall (PD)"] = recall
            row["F1"] = f1

            # calculate FAR metrics
            if self.region_model is not None:
                spatial_far = float(fp / self.region_model.area)
                temporal_far = float(fp / self.region_model.dates)
                row["spatial FAR"] = spatial_far
                row["temporal FAR"] = temporal_far

            # count the number of images (slices) in the site model stacks, for the FAR metric
            images_far = float(fp / proposed_slices) if proposed_slices else 0
            row["images FAR"] = images_far

            # add row to scoreboard (metrics per value of detection threshold rho)
            scoreboard_rows.append(row)

            # add threshold values to the scoreboard table
            row_raw = deepcopy(row)
            row_raw["tau"] = tau
            row_raw["rho"] = rho
            row_raw["min area"] = min_area
            row_raw["min score"] = min_score
            scoreboard_rows_raw.append(row_raw)

            # save the best results, using the F1 score
            # if f1 >= self.best_metric_score:
            # OR
            # save the results at a fixed set of thresholds, for standard comparisons between performers
            if tau == self.default_tau and rho == self.default_rho and min_area == self.default_min_area and min_score == self.default_min_confidence_score:
                self.best_metric_score = f1
                self.best = pd.DataFrame([row])
                self.detections = detections
                self.proposals = proposals
                self.matched_pairs = matched_pairs
                self.tau = tau
                self.rho = rho
                self.min_area = min_area
                self.min_score = min_score

            # detections table
            detections_df_raw, proposals_df_raw = self.visualize_detection_table(
                detections,
                proposals,
                tau,
                rho,
                min_area,
                min_score,
                site_types,
                save_output=(viz_detection_table and save_output),
            )

            # failed associations table
            failed_assoc_raw = self.visualize_failed_associations_table(
                failed_associations,
                tau,
                rho,
                min_area,
                min_score,
                save_output=(viz_detection_table and save_output),
            )
            detections_df_raw_list.append(detections_df_raw)
            proposals_df_raw_list.append(proposals_df_raw)
            failed_assoc_df_raw_list.append(failed_assoc_raw)

        # Convert list of dictionaries into a data frame
        scoreboard = pd.DataFrame(scoreboard_rows)
        scoreboard = scoreboard.sort_values(row_threshold_name).drop_duplicates(subset=row_threshold_name).set_index(row_threshold_name)

        scoreboard_df_raw = pd.DataFrame(scoreboard_rows_raw)

        logging.debug("Built scoreboard with shape: {}".format(scoreboard.shape))
        # save to file
        if self.bas_dir and save_output:
            scoreboard_round = scoreboard.round(4)
            out_path = f"{self.bas_dir}/scoreboard_{table_threshold_name}={table_threshold}.csv"
            scoreboard_round.to_csv(out_path)


        return (
            scoreboard,
            scoreboard_df_raw,
            pd.concat(detections_df_raw_list),
            pd.concat(proposals_df_raw_list),
            pd.concat(failed_assoc_df_raw_list),
        )

    @timer
    def associate_stacks(self, activity_type, viz_associate_metrics=False, viz_detection_table=True):
        """
        Find optimal stack associations between ground truth and site model stacks,
        using varying threshold values for tau, rho, and the other association thresholds, while
        allowing for over/under segmentation. It is possible for a ground truth stack
        to match with 1 or more site model stacks (over-segmentation), and for a site model stack to match
        with 1 or more ground truth stacks (under-segmentation).
        """
        logging.info(f"Associating {activity_type} site stacks...")

        # reset optimal score
        self.best_metric_score = 0

        # calculate rollup metrics for varying levels of the detection threshold
        threshold_map = {
            "tau": self.taus,
            "rho": self.rhos,
            "Min Confidence": self.confidence_score_thresholds,
            "Min Area": self.min_areas,
        }

        # choose which thresholds will be swept (max is 2)
        thresholds = []
        if self.sweep_tau:
            thresholds.append(("tau", threshold_map["tau"]))
        if self.sweep_rho:
            thresholds.append(("rho", threshold_map["rho"]))
        if self.sweep_min_area:
            thresholds.append(("Min Area", threshold_map["Min Area"]))
        if self.sweep_confidence:
            thresholds.append(("Min Confidence", threshold_map["Min Confidence"]))
        if len(thresholds) == 0:
            thresholds.append(("rho", threshold_map["rho"]))
            thresholds.append(("Min Confidence", threshold_map["Min Confidence"]))
        if len(thresholds) == 1:
            if thresholds[0][0] == "Min Confidence":
                thresholds.append(("rho", threshold_map["rho"]))
            else:
                thresholds.append(("Min Confidence", threshold_map["Min Confidence"]))
        if len(thresholds) > 2:
            thresholds = thresholds[-2:]

        # use the threshold with fewer values to create the individual scoreboard tables
        table_threshold_name, table_thresholds = thresholds.pop(thresholds.index(min(thresholds, key=lambda x: len(x[1]))))

        # use the other threshold with more values to create the individual rows in each scoreboard
        row_threshold_name, row_thresholds = thresholds[0]

        # build each scoreboard
        scoreboards = []
        all_scoreboard_df_raw = []
        all_detections_df_raw = []
        all_proposals_df_raw = []
        all_failed_assoc_df_raw = []

        # for each individual table threshold, create a scoreboard table, a detections table, a failed associations table, and a proposals table
        for table_threshold in table_thresholds:
            (
                scoreboard,
                scoreboard_df_raw,
                detections_df_raw,
                proposals_df_raw,
                failed_assoc_df_raw,
            ) = self.build_scoreboard(
                table_threshold_name,
                table_threshold,
                row_threshold_name,
                row_thresholds,
                viz_detection_table=viz_detection_table,
            )

            # f_score_table = self.build_f_score_table(
            #     scoreboard, table_threshold_name, table_threshold, row_threshold_name    - UNUSED
            # )
            scoreboard_name = f"{table_threshold_name}={table_threshold}"
            scoreboards.append((scoreboard_name, scoreboard))

            all_scoreboard_df_raw.append(
                {
                    "df": scoreboard_df_raw,
                    "table_threshold_name": table_threshold_name,
                    "table_threshold": table_threshold,
                }
            )
            all_detections_df_raw.append(
                {
                    "df": detections_df_raw,
                    "table_threshold_name": table_threshold_name,
                    "table_threshold": table_threshold,
                }
            )
            all_proposals_df_raw.append(
                {
                    "df": proposals_df_raw,
                    "table_threshold_name": table_threshold_name,
                    "table_threshold": table_threshold,
                }
            )
            all_failed_assoc_df_raw.append(
                {
                    "df": failed_assoc_df_raw,
                    "table_threshold_name": table_threshold_name,
                    "table_threshold": table_threshold,
                }
            )

        if DEV:
            if self.smart_database_api:
                self.add_bas_data(
                    activity_type,
                    all_scoreboard_df_raw,
                    all_detections_df_raw,
                    all_proposals_df_raw,
                    all_failed_assoc_df_raw,
                )

        # plot metric vs. row threshold, per table threshold
        for metric in scoreboards[0][1].columns:
            if viz_associate_metrics:
                fig, ax = plt.subplots(ncols=1, nrows=1, figsize=(10, 6))
            df = pd.DataFrame({row_threshold_name: row_thresholds})
            for scoreboard_name, scoreboard in scoreboards:
                df[scoreboard_name] = scoreboard[metric].tolist()
                if viz_associate_metrics:
                    ax.plot(row_thresholds, df[scoreboard_name], label=scoreboard_name, alpha=0.5, linewidth=6)
                    ax.set_xlabel(row_threshold_name, fontsize=14)
                    ax.set_ylabel(metric, fontsize=14)
                    ax.set_title(f"{metric} vs. {row_threshold_name}, per {table_threshold_name}", fontsize=18)
            df.to_csv(f"{self.bas_dir}/{metric}.csv", index=False)
            if viz_associate_metrics:
                fig.legend()
                fig.savefig(f"{self.bas_dir}/{metric}.png", bbox_inches="tight", dpi=60)

        # plot metric1 vs. metric2, across varying row thresholds, per table threshold
        for y, x in product(
            ["precision", "recall (PD)", "F1"],
            ["precision", "recall (PD)", "spatial FAR", "temporal FAR", "images FAR"],
        ):
            if y == x:
                continue
            if viz_associate_metrics:
                fig, ax = plt.subplots(ncols=1, nrows=1, figsize=(10, 6))
            df = pd.DataFrame({row_threshold_name: row_thresholds})
            for scoreboard_name, scoreboard in scoreboards:
                y_col = scoreboard[y].tolist()
                x_col = scoreboard[x].tolist()
                df[f"{y}_{scoreboard_name}"] = y_col
                df[f"{x}_{scoreboard_name}"] = x_col
                if viz_associate_metrics:
                    ax.plot(x_col, y_col, label=scoreboard_name, alpha=0.5, linewidth=6)
                    ax.set_xlabel(x, fontsize=14)
                    ax.set_ylabel(y, fontsize=14)
                    ax.set_ylim(0, 1)
                    ax.set_title(f"{y} vs. {x} with threshold {row_threshold_name}, per {table_threshold_name}", fontsize=18)
            df.to_csv(f"{self.bas_dir}/{y}_vs_{x}.csv", index=False)
            if viz_associate_metrics:
                fig.legend()
                fig.savefig(f"{self.bas_dir}/{y}_vs_{x}.png", bbox_inches="tight", dpi=60)

        # save the optimal row from the scoreboard to its own file
        if isinstance(self.best, pd.DataFrame):
            self.best["tau"] = self.tau
            self.best["rho"] = self.rho
            self.best["min area"] = self.min_area
            self.best["min score"] = self.min_score
            self.best["region"] = self.sequestered_id if self.sequestered_id else self.region_model.id
            self.best.to_csv(f"{self.bas_dir}/bestScore_tau={self.tau}_rho={self.rho}_minArea={self.min_area}_minScore={self.min_score}.csv")
        else:
            logging.warning("self.best not set. Did not write a best score scoreboard.")

    def add_bas_data(self, activity_type, all_scoreboards, all_detections_df_raw, all_proposals_df_raw, all_failed_assoc_df_raw):
        """
        Database - DEV Only
        """
        add_list = []

        for scoreboard_dict in all_scoreboards:
            metrics = scoreboard_dict["df"].copy().reset_index(drop=False)
            metrics[scoreboard_dict["table_threshold_name"]] = scoreboard_dict["table_threshold"]

            for index, row in metrics.iterrows():
                add_list.append(
                    EvaluationBroadAreaSearchMetric(
                        evaluation_run_uuid=self.evaluation_run_uuid,
                        activity_type=activity_type,
                        rho=row["rho"],
                        tau=row["tau"],
                        min_area=row["min area"],
                        min_confidence_score=row["min score"],
                        tp_sites=row["tp sites"],
                        tp_exact=row["tp exact"],
                        tp_under=row["tp under"],
                        tp_under_iou=row["tp under (IoU)"],
                        tp_under_iot=row["tp under (IoT)"],
                        tp_over=row["tp over"],
                        fp_sites=row["fp sites"],
                        fp_area=row["fp area"],
                        ffpa=row["ffpa"],
                        proposal_area=row["proposal area"],
                        fpa=row["fpa"],
                        fn_sites=row["fn sites"],
                        truth_annotations=row["truth annotations"],
                        truth_sites=row["truth sites"],
                        proposed_annotations=row["proposed annotations"],
                        proposed_sites=row["proposed sites"],
                        confident_proposals=row["confident annotations"],
                        total_sites=row["total sites"],
                        truth_slices=row["truth slices"],
                        proposed_slices=row["proposed slices"],
                        precision=row["precision"],
                        recall_pd=row["recall (PD)"],
                        f1=row["F1"],
                        spatial_far=row["spatial FAR"],
                        temporal_far=row["temporal FAR"],
                        images_far=row["images FAR"],
                    )
                )

        for df_dict in all_detections_df_raw:
            df = df_dict["df"]
            detection_col = list(filter(lambda col: col.startswith("detection score"), df.columns))[0]

            for index, row in df.iterrows():
                matched = [sm.strip() for sm in row["matched site models"].split(",")]
                matched = [] if len(matched) == 1 and not matched[0] else matched

                add_list.append(
                    EvaluationBroadAreaSearchDetection(
                        evaluation_run_uuid=self.evaluation_run_uuid,
                        activity_type=activity_type,
                        rho=row["rho"],
                        tau=row["tau"],
                        min_area=row["min area"],
                        min_confidence_score=row["min score"],
                        site_truth=row["truth site"],
                        site_truth_type=row["site type"],
                        site_truth_area=row["site area"],
                        site_proposal_matched=matched,
                        site_proposal_matched_count=len(matched),
                        detection_score=row[detection_col] if row[detection_col] and not np.isnan(row[detection_col]) else None,
                        spatial_overlap=row["spatial overlap"] if not pd.isnull(row["spatial overlap"]) else None,
                        temporal_iot=row["temporal iot"] if not pd.isnull(row["temporal iot"]) else None,
                        temporal_iop=row["temporal iop"] if not pd.isnull(row["temporal iop"]) else None,
                        association_status=row["association status"],
                        associated=row["associated"],
                        color_code=int(row["color code"]) if not pd.isnull(row["color code"]) else None,
                    )
                )

        for df_dict in all_proposals_df_raw:
            df = df_dict["df"]

            for index, row in df.iterrows():
                matched = [gt.strip() for gt in row["matched truth sites"].split(",")]
                matched = [] if len(matched) == 1 and not matched[0] else matched

                add_list.append(
                    EvaluationBroadAreaSearchProposal(
                        evaluation_run_uuid=self.evaluation_run_uuid,
                        activity_type=activity_type,
                        rho=row["rho"],
                        tau=row["tau"],
                        min_area=row["min area"],
                        min_confidence_score=row["min score"],
                        site_proposal=row["site model"],
                        site_proposal_area=row["site area"],
                        site_truth_matched=matched,
                        site_truth_matched_count=len(matched),
                        association_status=row["association status"],
                        associated=row["associated"],
                        color_code=int(row["color code"]) if not pd.isnull(row["color code"]) else None,
                    )
                )

        for df_dict in all_failed_assoc_df_raw:
            df = df_dict["df"]

            for index, row in df.iterrows():
                add_list.append(
                    EvaluationBroadAreaSearchFailedAssociation(
                        evaluation_run_uuid=self.evaluation_run_uuid,
                        activity_type=activity_type,
                        rho=row["rho"],
                        tau=row["tau"],
                        min_area=row["min area"],
                        min_confidence_score=row["min score"],
                        site_truth=row["truth site"],
                        site_truth_type=row["site type"],
                        site_proposal=row["proposal site"],
                        spatial_overlap=row["spatial overlap"] if not pd.isnull(row["spatial overlap"]) else None,
                        temporal_iot=row["temporal iot"] if not pd.isnull(row["temporal iot"]) else None,
                        temporal_iop=row["temporal iop"] if not pd.isnull(row["temporal iop"]) else None,
                        site_truth_activity_start=row["truth activity start date"] if not pd.isnull(row["truth activity start date"]) else None,
                        site_truth_activity_end=row["truth activity end date"] if not pd.isnull(row["truth activity end date"]) else None,
                        site_proposal_activity_start=row["proposal activity start date"] if not pd.isnull(row["proposal activity start date"]) else None,
                        site_proposal_activity_end=row["proposal activity end date"] if not pd.isnull(row["proposal activity end date"]) else None,
                    )
                )

        self.smart_database_api.add_all(add_list)

    @timer
    def calc_activity_metrics(self, activity_type):
        """
        Calculate metrics for activity classification and prediction
        :param activity_type: the type of ground truth activity for which to evaluate metrics (e.g. completed, partial, overall)
        :return:
            phase_table: the activity phases for each slice of each pair of associated stacks (DataFrame)
            tiou_table: the temporal intersection over union (distinct from the BAS TIoU metric) table for each pair of associated stacks, per activity phase (DataFrame)
            ac_te_table: the temporal error table that shows the average onset-of-activity classification errors across all sites (DataFrame)
            ap_te_table: the temporal error table that shows the average activity prediction errors across all sites (DataFrame)
            cm: a confusion matrix built from the phase_table, highlighting the misclassified labels (DataFrame)
            Each dataframe is saved as a CSV file
        """
        add_list = []  # DEV Only

        # output directory where the tables will be saved
        output_dir = f"{self.output_dir}/{activity_type}/phase_activity" if self.output_dir else "phase_activity"
        os.makedirs(output_dir, exist_ok=True)

        # sequential phase activity categories
        phase_classifications = [
            "No Activity",
            "Site Preparation",
            "Active Construction",
            "Post Construction",
        ]

        # highlight nonzero, nondiagonal cells
        def highlight_activity_cm(df):
            df_style = df.copy().astype(str)
            df_style.loc[:, :] = None

            for r in range(df.shape[0]):
                if str(df.iloc[r][0]) != "0":
                    df_style.iat[r, 0] = "background-color: bisque"
                for c in range(df.shape[1] - 1):
                    if str(df.iloc[r][c + 1]) != "0" and r != c:
                        df_style.iat[r, c + 1] = "background-color: bisque"

            return df_style

        # highlight cells with misclassified phases
        def highlight_phase_table(df):
            df_style = df.copy().astype(str)
            df_style.loc[:, :] = None

            for r in range(df.shape[0]):
                for c in range(df.shape[1]):
                    cell = str(df.iloc[r][c])
                    gt = cell.split("vs")[0]
                    if "vs" in cell and "Unknown" not in gt and "No Activity" not in gt:
                        df_style.iat[r, c] = "background-color: bisque"

            return df_style

        def get_phase_dates(stack):
            """
            retrieve and infer the phase activity for each observation date within a site
            used to calculate the activity classification TIoU metric only
            don't infer phase activity for dates that occur during the transition from 1 type of activity to a different type

            :param stack: a SiteStack
            :return: a dict mapping a phase label to the calendar dates in the site's temporal duration that are in that phase
            """
            phase_dates = defaultdict(list)
            for i, slice in enumerate(stack.slices):
                # initialize
                if i == 0:
                    prev_date = stack.slices[i].date
                    prev_phase = stack.slices[i].phase
                elif slice.phase == prev_phase:
                    # the end of the observations
                    if i == len(stack.slices) - 1:
                        phase_dates[prev_phase].extend(pd.date_range(start=prev_date, end=stack.slices[i].date))
                # phase transition
                elif slice.phase != prev_phase:
                    phase_dates[prev_phase].extend(pd.date_range(start=prev_date, end=stack.slices[i - 1].date))
                    # reset
                    prev_date = slice.date
                    prev_phase = slice.phase
                    if stack.start_activity and stack.end_activity:
                        phase_dates["All Activity"] = pd.date_range(start=stack.start_activity, end=stack.end_activity)
            return phase_dates

        def build_te_table(temporal_error, missing_gt, missing_sm):
            """
            Construct the temporal error table

            :param temporal_error: a dict mapping a phase label to a list of temporal errors
            :param missing_gt: a dict mapping a phase label to a list of ground truth IDs that do not have that activity phase
            :param missing_sm: a dict mapping a phase label to a list of proposed site model IDs that do not have that activity phase
            :return: a DataFrame table of the temporal errors
            """

            temporal_error_dict = {}
            for phase, errors in temporal_error.items():
                if isinstance(errors[0], tuple):
                    worst_te = [e[0] for e in errors if e[0] is not None]
                    proposed_te = [e[1] for e in errors if e[1] is not None]
                    best_te = [e[2] for e in errors if e[2] is not None]
                    early = [e[1] for e in errors if e[1] is not None and e[1] < 0]
                    late = [e[1] for e in errors if e[1] is not None and e[1] > 0]
                    perfect = [e[1] for e in errors if e[1] is not None and e[1] == 0]
                else:
                    worst_te = proposed_te = best_te = errors
                    early = [e for e in errors if e < 0]
                    late = [e for e in errors if e > 0]
                    perfect = [e for e in errors if e == 0]
                temporal_error_dict[phase] = [
                    np.mean(worst_te),
                    np.std(worst_te),
                    np.mean(list(map(abs, worst_te))),
                    np.std(list(map(abs, worst_te))),
                    np.mean(proposed_te),
                    np.std(proposed_te),
                    np.mean(list(map(abs, proposed_te))),
                    np.std(list(map(abs, proposed_te))),
                    np.mean(best_te),
                    np.std(best_te),
                    np.mean(list(map(abs, best_te))),
                    np.std(list(map(abs, best_te))),
                    np.mean(early),
                    np.std(early),
                    np.mean(late),
                    np.std(late),
                    len(errors),
                    len(early),
                    len(late),
                    len(perfect),
                    len(missing_sm[phase]),
                    len(missing_gt[phase]),
                ]
            te_table = pd.DataFrame(temporal_error_dict).round(1)
            te_table = te_table.rename_axis("Temporal Error", axis="columns")
            row_names = [
                "worst mean days (all detections)",
                "worst std days (all)",
                "worst mean days (absolute value of all detections)",
                "worst std days (abs val of all)",
                "mean days (all detections)",
                "std days (all)",
                "mean days (absolute value of all detections)",
                "std days (abs val of all)",
                "best mean days (all detections)",
                "best std days (all)",
                "best mean days (absolute value of all detections)",
                "best std days (abs val of all)",
                "mean days (early detections)",
                "std days (early)",
                "mean days (late detections)",
                "std days (late)",
                "all detections",
                "early",
                "late",
                "perfect",
                "missing proposals",
                "missing truth sites",
            ]
            te_table = te_table.rename(index={i: name for i, name in zip(range(len(row_names)), row_names)})
            return te_table

        phase_dataframes = [] # list of per-site phase activity tables
        phase_raw = [] # to save to the database
        tiou_dataframes = [] # list of per-site TIoU tables

        # equal-length lists of the ground truth phase labels and the corresponding proposed phase labels (including subsites)
        phase_true_all_sites, phase_pred_all_sites = [], []

        f1_score_per_site = {} # a dict mapping a ground truth site ID to its F1 score table
        ac_temporal_error = defaultdict(list) # a dict mapping a phase label to the list of activity classification temporal errors for that activity phase
        ap_temporal_error = defaultdict(list) # a dict mapping a phase label to the list of activity prediction temporal errors for that activity phase
        missing_gt = defaultdict(list) # a dict mapping a phase label to a list of ground truth IDs that do not have that activity phase
        ac_missing_sm = defaultdict(list) # a dict mapping a phase label to a list of proposed site model IDs that do not have that activity phase in their observational phase activity labels
        ap_missing_sm = defaultdict(list) # a dict mapping a phase label to a list of proposed site model IDs that do not have that activity phase in their activity prediction labels

        # only iterate through stacks that got matched
        positive_detection_pairs = [pair for pair in self.matched_pairs if self.gt_stacks[pair[0]].status in POSITIVE_ACTIVITY_STATUS_TYPES]
        if not positive_detection_pairs:
            logging.warning(f"Phase activity metrics cannot be calculated for {activity_type!r}, because there were no positive site detections of this type.")
            return None
        else:
            logging.debug(f"Calculate phase activity metrics for {activity_type!r} with {len(positive_detection_pairs)}/{len(self.matched_pairs)} pairs.")

        # examine each detected positive truth site
        for gt_id, sm_id in positive_detection_pairs:

            # sanitize sequestered region ID
            display_gt_id = gt_id.replace(self.region_model.id, self.sequestered_id) if self.sequestered_id else gt_id
            display_sm_id = sm_id.replace(self.region_model.id, self.sequestered_id) if self.sequestered_id else sm_id

            # equal-length lists of the ground truth phase labels and the corresponding proposed phase labels (including subsites)
            phase_true, phase_pred = [], []

            # retrieve the positive ground truth site and the associated proposed site
            gt_stack = self.gt_stacks[gt_id]
            sm_stack = self.sm_stacks[sm_id]

            # initialize variables for metrics for this particular detected positive truth site
            gt_times = defaultdict(list) # a dict mapping a phase label to a list of observation dates in the ground truth site that are in that activity phase
            sm_times = defaultdict(list) # a dict mapping a phase label to a list of observation dates in the proposed site model that are in that activity phase
            tiou = {} # a dict mapping a phase label to the temporal intersection over union ratio metric for that activity phase
            phase_dict = {} # a dict mapping each observation date to the phase labels of the ground truth observation and the associated site model observation
            ac_temporal_error_site = defaultdict(list) # a dict mapping a phase label to the list of activity classification temporal errors for that activity phase
            ap_temporal_error_site = defaultdict(list) # a dict mapping a phase label to the list of activity prediction temporal errors for that activity phase
            missing_gt_site = defaultdict(list) # a dict mapping a phase label to a list of ground truth IDs that do not have that activity phase
            ac_missing_sm_site = defaultdict(list) # a dict mapping a phase label to a list of proposed site model IDs that do not have that activity phase in their observational phase activity labels
            ap_missing_sm_site = defaultdict(list) # a dict mapping a phase label to a list of proposed site model IDs that do not have that activity phase in their activity prediction labels

            # get activity phases for each stack slice
            gt_has_subsites = False
            for gt_slice in gt_stack.slices:

                # map each ground truth observation date to the ground truth phase
                gt_segment_phases = set(re.split(", |_", gt_slice.phase))
                phase_dict[gt_slice.date] = gt_slice.phase

                # get the phases from the observation of the associated proposal site
                sm_slice = sm_stack.get_slice(gt_slice.date)
                sm_segment_phases = set(re.split(", |_", sm_slice.phase)) if sm_slice else []

                for gt_segment_phase in gt_segment_phases:
                    # don't include phase activity labels for ground truth subsites in the temporal error computation
                    if len(gt_segment_phases) > 1:
                        gt_has_subsites = True
                    else:
                        # map each phase to a list of ground truth dates
                        gt_times[gt_segment_phase].append(gt_slice.date)

                    # filter out truth observations that are labeled Unknown
                    if gt_segment_phase not in ["Unknown", "No Activity"]:
                        for sm_segment_phase in sm_segment_phases:
                            # add to the sequential list of ground truth phases and proposal phases
                            phase_true.append(gt_segment_phase)
                            phase_pred.append(sm_segment_phase)

                # explicitly add the proposed phase label if it is different than the actual ground truth label
                if gt_segment_phases != sm_segment_phases:
                    if sm_slice:
                        phase_dict[gt_slice.date] += f" vs. {sm_slice.phase}"
                    else:
                        phase_dict[gt_slice.date] += " vs. n/a"

                phase_raw.append(
                    {
                        "date": gt_slice.date,
                        "site_truth": gt_id,
                        "site_proposal": sm_id,
                        "site_truth_phase": sorted(list(gt_segment_phases)),
                        "site_proposal_phase": sorted(list(sm_segment_phases)),
                    }
                )

            for sm_slice in sm_stack.slices:
                # add the observation dates from the proposed site model
                if sm_slice.date not in phase_dict:
                    phase_dict[sm_slice.date] = f"n/a vs. {sm_slice.phase}"

                # map the activity phase labels to the proposed site model observation dates
                sm_segment_phases = set(re.split(", |_", sm_slice.phase))
                for sm_segment_phase in sm_segment_phases:
                    # the proposed site model is only in Post Construction when all of its phase labels are Post Construction and all of the sites have started
                    if len(sm_segment_phases) == 1:
                        if sm_segment_phase != "Post Construction":
                            sm_times[sm_segment_phase].append(sm_slice.date)
                        elif sm_segment_phase == "Post Construction" and np.all([sm_slice.date >= self.sm_stacks[stack_id].start_date for stack_id in sm_stack.sites]):
                            sm_times[sm_segment_phase].append(sm_slice.date)
                    elif sm_segment_phase != "Post Construction":
                        sm_times[sm_segment_phase].append(sm_slice.date)

            # build the confusion matrix, using the lists of ground truth phase labels and proposed phase labels
            cm = pd.DataFrame(
                sklearn.metrics.confusion_matrix(phase_true, phase_pred, labels=phase_classifications),
                columns=phase_classifications,
                index=phase_classifications,
            )
            cm = cm.rename_axis("truth phase")
            cm = cm.rename_axis("predicted phase", axis="columns")
            cm = cm.drop("No Activity")
            cm.to_csv(f"{output_dir}/ac_confusion_matrix_{display_gt_id}.csv")

            if DEV:
                if self.smart_database_api:
                    for index, row in cm.iterrows():
                        add_list.append(
                            EvaluationActivityClassificationMatrix(
                                evaluation_run_uuid=self.evaluation_run_uuid,
                                activity_type=activity_type,
                                site=gt_id,
                                phase_truth=index,
                                phase_proposal_no_activity=int(row["No Activity"]),
                                phase_proposal_site_preparation=int(row["Site Preparation"]),
                                phase_proposal_active_construction=int(row["Active Construction"]),
                                phase_proposal_post_construction=int(row["Post Construction"]),
                            )
                        )


            # compute the phase activity classification F1 scores, using the lists of ground truth phase labels and proposed phase labels
            selected_phases = list(set(["Site Preparation", "Active Construction"]) & (set(phase_true) | set(phase_pred)))
            selected_phases.sort(reverse=True)
            f1_score_df = pd.DataFrame(
                sklearn.metrics.f1_score(phase_true, phase_pred, labels=selected_phases, average=None),
                index=selected_phases,
            ).T
            f1_score_df = f1_score_df.rename_axis("Activity Classification", axis="columns")
            f1_score_df = f1_score_df.rename(index={0: "F1 score"}).round(4)
            f1_score_per_site[gt_id] = f1_score_df
            f1_score_df.to_csv(f"{output_dir}/ac_f1_{display_gt_id}.csv")

            if DEV:
                if self.smart_database_api:
                    for index, row in f1_score_df.iterrows():
                        add_list.append(
                            EvaluationActivityClassificationF1(
                                evaluation_run_uuid=self.evaluation_run_uuid,
                                activity_type=activity_type,
                                site=gt_id,
                                metric=index,
                                site_preparation=float(row["Site Preparation"]) if "Site Preparation" in row else None,
                                active_construction=float(row["Active Construction"]) if "Active Construction" in row else None,
                                post_construction=float(row["Post Construction"]) if "Post Construction" in row else None,
                            )
                        )


            # add the lists of ground truth phase labels and proposed phase labels to the aggregated lists for all detected positive truth sites and their associated proposals
            phase_true_all_sites.extend(phase_true)
            phase_pred_all_sites.extend(phase_pred)

            # get the calendar dates for each phase activity
            gt_ranges = get_phase_dates(gt_stack)
            sm_ranges = get_phase_dates(sm_stack)

            # compute the temporal errors for each phase
            activity_phases = ["No Activity", "Site Preparation", "Active Construction", "Post Construction"]
            for i, phase in enumerate(activity_phases):
                # skip No Activity
                if phase == "No Activity":
                    continue

                # compute best-case and worst-case temporal errors, for activity classification metrics
                # the truth site has the phase activity within it
                if not gt_has_subsites and gt_times[phase]:

                    # the proposed site has the phase activity within it
                    if sm_times[phase]:
                        truth_onset = min(gt_times[phase])  # true onset of Active Construction
                        # get the date when the previous activity phase ended
                        for j in range(1, i + 1):
                            prev_gt_times = [gt_time for gt_time in gt_times[activity_phases[i - j]] if gt_time <= truth_onset]
                            if prev_gt_times:
                                prev_finish = max(prev_gt_times)
                                break
                        else:
                            prev_finish = None
                        pred_onset = min(sm_times[phase])  # proposed onset of Active Construction

                        # the activity began in the proposal before the previous activity ended in the ground truth site
                        if prev_finish and pred_onset <= prev_finish:
                            te = -(len(pd.date_range(start=pred_onset, end=truth_onset)) - 1)
                            best_te = -(len(pd.date_range(start=pred_onset, end=prev_finish)) - 1)
                            worst_te = te

                        # the activity began in the proposal before the activity began in the ground truth site, but after the previous activity ended
                        elif pred_onset <= truth_onset:
                            te = -(len(pd.date_range(start=pred_onset, end=truth_onset)) - 1)
                            if prev_finish:
                                best_te = 0
                                worst_te = max([te, len(pd.date_range(start=prev_finish, end=pred_onset)) - 1], key=abs)  # choose the greater magnitude of these 2 and keep the sign
                            else:
                                best_te = None
                                worst_te = None

                        # the activity began in the proposal after the activity began in the ground truth site
                        elif truth_onset < pred_onset:
                            te = len(pd.date_range(start=truth_onset, end=pred_onset)) - 1
                            if prev_finish:
                                best_te = te
                                worst_te = len(pd.date_range(start=prev_finish, end=pred_onset)) - 1
                            else:
                                best_te = None
                                worst_te = None

                        # add temporal errors
                        ac_temporal_error[phase].append((worst_te, te, best_te))
                        ac_temporal_error_site[phase].append((worst_te, te, best_te))

                    # the proposed site does not have the phase activity within it
                    else:
                        ac_missing_sm[phase].append(sm_id)
                        ac_missing_sm_site[phase].append(sm_id)

                    # compute temporal errors for activity prediction metrics
                    if sm_stack.predicted_date and sm_stack.predicted_phase == phase:
                        onset = (min(gt_times[phase]), pd.to_datetime(sm_stack.predicted_date))
                        te = len(pd.date_range(start=min(onset), end=max(onset))) - 1
                        # flip the sign if the site model is early
                        if onset[1] < onset[0]:
                            te = -te
                        # add temporal errors
                        ap_temporal_error[phase].append(te)
                        ap_temporal_error_site[phase].append(te)
                    else:
                        # the proposed site does not have the phase activity within it
                        ap_missing_sm[phase].append(sm_id)
                        ap_missing_sm_site[phase].append(sm_id)

                # the truth site does not have the phase activity within it
                else:
                    missing_gt[phase].append(gt_id)
                    missing_gt_site[phase].append(gt_id)

                # compute the activity classification TIoU (distinct from the broad area search TIoU) for each activity phase
                if gt_ranges.get(phase, None) or sm_ranges.get(phase, None):
                    tiou[phase] = len(set(gt_ranges[phase]).intersection(set(sm_ranges[phase]))) / len(set(gt_ranges[phase]).union(set(sm_ranges[phase])))

            # for each site, create tables of the observation dates and the ground truth and proposed activity phase labels
            phase_df = pd.DataFrame(phase_dict, index=[0]).T
            phase_df.columns = [f"site truth {display_gt_id} vs. site model {display_sm_id}"]
            phase_dataframes.append(phase_df)

            # add raw site model ids to store for database; however, need to make sure to remove before saving output
            tiou["gt_id"] = gt_id
            tiou["sm_id"] = sm_id
            tiou_df = pd.DataFrame(tiou, index=[0]).T
            tiou_df.columns = [f"site truth {display_gt_id} vs. site model {display_sm_id}"]
            tiou_dataframes.append(tiou_df)

            # create the temporal error tables for each site
            ac_te_table_site = build_te_table(ac_temporal_error_site, missing_gt_site, ac_missing_sm_site)
            ap_te_table_site = build_te_table(ap_temporal_error_site, missing_gt_site, ap_missing_sm_site)
            ac_te_table_site.to_csv(f"{output_dir}/ac_temporal_error_{display_gt_id}.csv")
            ap_te_table_site.to_csv(f"{output_dir}/ap_temporal_error_{display_gt_id}.csv")

            if DEV:
                if self.smart_database_api:
                    for index, row in ac_te_table_site.iterrows():
                        add_list.append(
                            EvaluationActivityClassificationTemporalError(
                                evaluation_run_uuid=self.evaluation_run_uuid,
                                activity_type=activity_type,
                                site=gt_id,
                                metric=index,
                                site_preparation=float(row["Site Preparation"]) if "Site Preparation" in row else None,
                                active_construction=float(row["Active Construction"]) if "Active Construction" in row else None,
                                post_construction=float(row["Post Construction"]) if "Post Construction" in row else None,
                            )
                        )

                    for index, row in ap_te_table_site.iterrows():
                        add_list.append(
                            EvaluationActivityPredictionTemporalError(
                                evaluation_run_uuid=self.evaluation_run_uuid,
                                activity_type=activity_type,
                                site=gt_id,
                                metric=index,
                                site_preparation=float(row["Site Preparation"]) if "Site Preparation" in row else None,
                                active_construction=float(row["Active Construction"]) if "Active Construction" in row else None,
                                post_construction=float(row["Post Construction"]) if "Post Construction" in row else None,
                            )
                        )


        # create the aggregated temporal error tables
        ac_te_table = build_te_table(ac_temporal_error, missing_gt, ac_missing_sm)
        ap_te_table = build_te_table(ap_temporal_error, missing_gt, ap_missing_sm)

        # create the aggregated table of observation dates and activity phase labels
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)
            phase_table = None
            for i, df in enumerate(phase_dataframes):
                merge_in = df.rename_axis("date")
                if i:
                    phase_table = phase_table.merge(merge_in, how="outer", on="date")
                else:
                    phase_table = merge_in
        if phase_table is None:
            logging.debug("phase_dataframes is empty")
            raise Exception("phase_dataframes is empty")
        phase_table_cols = deepcopy(phase_table.columns.tolist())
        phase_table_date_col = phase_table_cols.pop(0)
        # sort columns alphabetically
        phase_table = phase_table.reindex([phase_table_date_col] + sorted(phase_table_cols), axis=1)
        phase_table = phase_table.sort_values("date")

        # create the aggregated TIoU table
        tiou_table = pd.concat(tiou_dataframes, axis="columns")
        tiou_table = tiou_table.rename_axis("TIoU").T

        # create the aggregated confusion matrix
        cm = pd.DataFrame(
            sklearn.metrics.confusion_matrix(phase_true_all_sites, phase_pred_all_sites, labels=phase_classifications),
            columns=phase_classifications,
            index=phase_classifications,
        )
        cm = cm.rename_axis("truth phase")
        cm = cm.rename_axis("predicted phase", axis="columns")
        cm = cm.drop("No Activity")
        cm.to_csv(f"{output_dir}/ac_confusion_matrix_all_sites.csv")

        if DEV:
            if self.smart_database_api:
                for index, row in cm.iterrows():
                    add_list.append(
                        EvaluationActivityClassificationMatrix(
                            evaluation_run_uuid=self.evaluation_run_uuid,
                            activity_type=activity_type,
                            site="All",
                            phase_truth=index,
                            phase_proposal_no_activity=int(row["No Activity"]),
                            phase_proposal_site_preparation=int(row["Site Preparation"]),
                            phase_proposal_active_construction=int(row["Active Construction"]),
                            phase_proposal_post_construction=int(row["Post Construction"]),
                        )
                    )

        # compute the aggregated phase activity classification F1 scores, using the lists of ground truth phase labels and proposed phase labels
        f1_score_macro = {}
        for phase in ["Site Preparation", "Active Construction"]:
            scores = [site_df[phase].iloc[0] for site_df in f1_score_per_site.values() if phase in site_df.columns]
            f1_score_macro[phase] = [np.mean(scores)]
        selected_phases = list(set(["Site Preparation", "Active Construction"]) & (set(phase_true_all_sites) | set(phase_pred_all_sites)))
        selected_phases.sort(reverse=True)
        f1_df = pd.concat(
            [
                pd.DataFrame(
                    sklearn.metrics.f1_score(phase_true_all_sites, phase_pred_all_sites, labels=selected_phases, average=None),
                    index=selected_phases,
                ).T,
                pd.DataFrame(f1_score_macro, index=["F1 macro average"]),
            ]
        )
        f1_df = f1_df.rename(index={0: "F1 micro average"}).rename_axis(f"Activity Classification ({len(f1_score_per_site)} sites)", axis="columns").round(4)
        f1_df.to_csv(f"{output_dir}/ac_f1_all_sites.csv")

        if DEV:
            if self.smart_database_api:
                for index, row in f1_df.iterrows():
                    add_list.append(
                        EvaluationActivityClassificationF1(
                            evaluation_run_uuid=self.evaluation_run_uuid,
                            activity_type=activity_type,
                            site="All",
                            metric=index,
                            site_preparation=float(row["Site Preparation"]) if "Site Preparation" in row else None,
                            active_construction=float(row["Active Construction"]) if "Active Construction" in row else None,
                            post_construction=float(row["Post Construction"]) if "Post Construction" in row else None,
                        )
                    )



        ac_te_table.to_csv(f"{output_dir}/ac_temporal_error.csv")

        if DEV:
            if self.smart_database_api:
                for index, row in ac_te_table.iterrows():
                    add_list.append(
                        EvaluationActivityClassificationTemporalError(
                            evaluation_run_uuid=self.evaluation_run_uuid,
                            activity_type=activity_type,
                            site="All",
                            metric=index,
                            site_preparation=float(row["Site Preparation"]) if "Site Preparation" in row else None,
                            active_construction=float(row["Active Construction"]) if "Active Construction" in row else None,
                            post_construction=float(row["Post Construction"]) if "Post Construction" in row else None,
                        )
                    )


        ap_te_table.to_csv(f"{output_dir}/ap_temporal_error.csv")

        if DEV:
            if self.smart_database_api:
                for index, row in ap_te_table.iterrows():
                    add_list.append(
                        EvaluationActivityPredictionTemporalError(
                            evaluation_run_uuid=self.evaluation_run_uuid,
                            activity_type=activity_type,
                            site="All",
                            metric=index,
                            site_preparation=float(row["Site Preparation"]) if "Site Preparation" in row else None,
                            active_construction=float(row["Active Construction"]) if "Active Construction" in row else None,
                            post_construction=float(row["Post Construction"]) if "Post Construction" in row else None,
                        )
                    )



        phase_table.to_csv(f"{output_dir}/ac_phase_table.csv")

        if DEV:
            if self.smart_database_api:
                for i in phase_raw:
                    add_list.append(
                        EvaluationActivityClassificationPhase(
                            evaluation_run_uuid=self.evaluation_run_uuid,
                            activity_type=activity_type,
                            date=i["date"],
                            site_truth=i["site_truth"],
                            site_proposal=i["site_proposal"],
                            site_truth_phase=i["site_truth_phase"],
                            site_proposal_phase=i["site_proposal_phase"],
                        )
                    )

        # make sure to remove site model ids before saving output
        tiou_table.drop(columns=["gt_id", "sm_id"]).to_csv(f"{output_dir}/ac_tiou.csv")

        if DEV:
            if self.smart_database_api:
                for index, row in tiou_table.iterrows():
                    add_list.append(
                        EvaluationActivityClassificationTemporalIOU(
                            evaluation_run_uuid=self.evaluation_run_uuid,
                            activity_type=activity_type,
                            site_truth=row["gt_id"],
                            site_proposal=row["sm_id"],
                            site_preparation=float(row["Site Preparation"]) if "Site Preparation" in row else None,
                            active_construction=float(row["Active Construction"]) if "Active Construction" in row else None,
                            post_construction=float(row["Post Construction"]) if "Post Construction" in row else None,
                        )
                    )


        if DEV:
            if self.smart_database_api:
                self.smart_database_api.add_all(add_list)

        return phase_table, tiou_table, ac_te_table, cm
