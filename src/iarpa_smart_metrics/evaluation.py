# © 2025 The Johns Hopkins University Applied Physics Laboratory LLC.  This material was sponsored by the U.S. Government under contract number 2020-20081800401.
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

from itertools import combinations
import psutil
from typing import Union, Iterable, Tuple

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
from shapely import intersection
from shapely.geometry.polygon import Polygon
from shapely.geometry.multipolygon import MultiPolygon
from shapely.geometry.point import Point
from shapely.ops import unary_union

# visualization packages
import rasterio
import rasterio.warp
import matplotlib.pyplot as plt

import fiona
from packaging.version import parse as Version
import simplekml

FIONA_GE_1_9_0 = Version(fiona.__version__) >= Version("1.9.0")

# Status type lists: these are the categories of annotation status types for the ground truth sites, grouped by how they are scored when they are detected by proposals
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
ANNOTATED_NEGATIVE_STATUS_TYPES = [
    "negative",
    "negative_unbounded",
    "transient_negative",
]
POSITIVE_PARTIAL_STATUS_TYPES = ["positive_partial"]
POSITIVE_COMPLETE_STATUS_TYPES = [
    "positive",
    "positive_annotated",
    "positive_annotated_static",
    "positive_pending",
    "transient_positive",
    "transient_pending",
]


def reorder_str(raw_string):
    """
    Reorders the characters in a string by splitting it on underscores, sorting the resulting list of words, and then joining them back together with underscores.

    Parameters:
        raw_string (str): The string to be reordered.

    Returns:
        str: The reordered string.
    """
    sort_list = re.split("_", raw_string)
    sort_list.sort()
    return "_".join(sort_list)


def timer(func):
    """
    Decorator that logs the time spent executing the decorated function.

    This decorator can be used to measure the execution time of any function. It logs the time taken to execute the function, along with the function name and any keyword arguments passed to it. The log messages include the total execution time and the average execution time per call, if applicable.

    Parameters:
        func (callable): The function to be decorated.

    Returns:
        callable: The decorated function.
    """

    @functools.wraps(func)
    def wrapper_timer(*args, **kwargs):
        start_time = time.perf_counter()
        value = func(*args, **kwargs)
        end_time = time.perf_counter()
        run_time = end_time - start_time
        if run_time >= 1:
            logging.debug(f"finished {func.__module__}.{func.__name__!r} {kwargs} in {run_time:.2f} sec")
        return value

    return wrapper_timer


def _evaluation_global_preferences(output_dir, log_level="INFO", log_file="debug.log", oldval=None, newval=None):
    """
    Configures the global preferences for the evaluation by setting up the logging.
    Previously these were global side effects. They now live in a function so
    they can be explicitly called by a main script that uses this module.

    This function sets up the logging configuration for the evaluation process.
    Importantly, it removes sequestered region IDs from the log messages.

    Parameters:
        output_dir (str): The directory where the output files will be saved.
        log_level (str, optional): The log level for the logger. Defaults to "INFO".
        log_file (str, optional): The name of the log file. Defaults to "debug.log".
        oldval (str, optional): The value to filter out from the log records. Defaults to None.
        newval (str, optional): The value to replace the oldval in the log records. Defaults to None.

    Returns:
        None
    """

    # Convert log level to the corresponding log level constant
    if isinstance(log_level, str):
        log_level = getattr(logging, log_level.upper())

    # Set the log file path if it is an empty string
    if os.path.dirname(log_file) == "":
        log_file = os.path.abspath(f"{output_dir}/{log_file}")

    # Generate a new log file name with a timestamp
    log_name = log_file.split("/")[-1]
    log_name_datetime = log_name.split(".")[0] + "-" + datetime.now().strftime("%Y_%m_%d-%H_%M_%S") + ".log"
    log_file = log_file.replace(log_name, log_name_datetime)

    # Set up the logger with the specified log level and log file
    logger = logging.getLogger()
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(filename)s:%(funcName)s:%(lineno)d - %(message)s")
    logger.setLevel(logging.DEBUG)

    # Set up a file handler and a stream handler for the logger
    file_handler = logging.FileHandler(log_file)
    stream_handler = logging.StreamHandler(sys.stdout)

    # Set the formatter for the file handler and the stream handler
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)

    # Create a custom filter class to filter out log records containing the old value
    class NoSeqInfoFilter(logging.Filter):
        def filter(self, record):
            return oldval not in str(record) or oldval == newval

    # Add the file handler and the stream handler to the logger
    file_handler.setLevel(logging.DEBUG)
    stream_handler.setLevel(log_level)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

    # Ignore warnings related to geometry being in a geographic CRS
    warnings.filterwarnings("ignore", message="Geometry is in a geographic CRS")

    # Set the precision for pandas data frames to 4 decimal places
    try:
        pd.set_option("precision", 4)
    except pd.errors.OptionError:
        # More recent pandas
        pd.options.styler.format.precision = 4


class SiteModel:
    def __init__(
        self,
        df,
        region_model,
        mgrs,
        crs,
        version,
        annotation_id,
        originator,
        annotated_status,
        status,
        score,
    ):
        """
        Initializes a new instance of the SiteModel class.

        Parameters:
            df (pandas.DataFrame): The DataFrame containing the site model data.
            region_model (str): The path to the region model file.
            mgrs (str): The MGRS (Military Grid Reference System) code of the site model.
            crs (int): The coordinate reference system (CRS) of the site model. Currently, only EPSG:4326 is supported.
            version (str): The version number of the site model.
            annotation_id (str): The annotation ID of the site model.
            originator (str): The creator of the site model annotation file.
            annotated_status (str): The original annotated status of the site model (is not updated).
            status (str): The effective status of the site model (can be updated by the scoring logic).
            score (float): The confidence score of the site model. Defaults to 1.

        Attributes:
            df (pandas.DataFrame): The DataFrame containing the site model data.
            region_model (str): The path to the region model file.
            mgrs (str): The MGRS code of the site model.
            crs (int): The coordinate reference system of the site model.
            version (str): The version number of the site model.
            annotation_id (str): The annotation ID of the site model.
            originator (str): The originator of the site model.
            annotated_status (str): The original annotated status of the site model (is not updated).
            status (str): The effective status of the site model (can be updated by the scoring logic).
            score (float): The confidence score of the site model. Defaults to 1.
            association_status (None or str): The association status of the site model.
            associated (None or bool): Indicates whether the site model is associated with another site model.
            color (None or int): The color code of the site model.
            uuid (uuid.UUID): The unique identifier of the site model.
        """

        self.df = df
        self.region_model = region_model
        self.mgrs = mgrs
        self.crs = crs
        self.version = version
        self.annotation_id = annotation_id
        self.originator = originator
        self.annotated_status = annotated_status
        self.status = status
        self.score = score

        # Default confidence score is 1
        if np.isnan(self.score):
            self.score = 1

        self.association_status = None
        self.associated = None
        self.color = None
        self.set_id()
        self.uuid = uuid.uuid4()

    def set_id(self):
        """
        Set the readable ID of the site model.

        This function sets the ID of the site model based on the annotation ID,
        originator, and version of the site model.

        Parameters:
            None

        Returns:
            None
        """
        # Set the initial ID to the annotation ID
        self.id = self.annotation_id

        # Check if an originator is provided
        if self.originator:
            # Append the originator to the ID with an underscore
            self.id = f"{self.id}_{self.originator}"

        # Check if a version is provided
        if self.version:
            # Append the version to the ID with an underscore
            self.id = f"{self.id}_{self.version}"

        # Log the resulting ID as a debug message
        logging.debug(f"Set id to {self.id}")


class SitePoint(SiteModel):
    def __init__(
        self,
        region_model,
        point_date,
        start_date,
        end_date,
        annotation_id,
        annotated_status,
        site_version,
        point_version,
        point_date_version,
        crs=None,
        score=1,
        coordinates: Point = None,
        df=None,
    ):
        """
        Initializes a new instance of the SitePoint class.

        Parameters:
            region_model (RegionModel): The region model used for the evaluation.
            point_date (str): The date of the site point in the format "YYYY-MM-DD".
            start_date (str): The start date of the site point's corresponding site stack in the format "YYYY-MM-DD".
            end_date (str): The end date of the site point's corresponding site stack in the format "YYYY-MM-DD".
            annotation_id (str): The ID of the site point annotation.
            annotated_status (str): The annotated status of the site point.
            site_version (str): The version of the site point.
            point_version (str): The version of the point.
            point_date_version (str): The version of the point date.
            crs (None or str): The coordinate reference system of the site point.
            score (float, optional): The confidence score of the site point. Defaults to 1.
            coordinates (Point, optional): The coordinates of the site point.
            df (None or pd.DataFrame, optional): The dataframe containing the site model data.

        Returns:
            None
        """
        # Convert the dates to datetime objects
        self.point_date = pd.to_datetime(point_date, format="%Y-%m-%d")
        self.start_date = pd.to_datetime(start_date, format="%Y-%m-%d")
        self.end_date = pd.to_datetime(end_date, format="%Y-%m-%d")

        # Set the start and end of activity to the point_date
        self.start_activity = self.point_date
        self.end_activity = self.point_date

        self.coordinates = coordinates
        self.area = 0  # a point does not have an area
        self.point_version = point_version
        self.point_date_version = point_date_version

        # Call the superclass's __init__ method (SiteModel)
        super().__init__(
            df,
            region_model,
            None,
            crs,
            site_version,
            annotation_id,
            "te",
            annotated_status,
            annotated_status,
            score,
        )

        # Check the relationship between the start_date and the point_date vs. the region_model's start_date and end_date
        # to determine the value of the unbounded variable (-2, -1, 0, +1, +2 corresponds to types A, B, C, D, E)
        if (not self.start_date or self.start_date < region_model.start_date) and (
            self.point_date < region_model.start_date
        ):
            self.unbounded = -2
        elif (not self.start_date or self.start_date < region_model.start_date) and (
            self.point_date >= region_model.start_date
        ):
            self.unbounded = -1
        elif (not self.start_date or self.start_date >= region_model.start_date) and (
            self.point_date <= region_model.end_date
        ):
            self.unbounded = 0
        elif (not self.start_date or (region_model.start_date <= self.start_date <= region_model.end_date)) and (
            self.point_date > region_model.end_date
        ):
            self.unbounded = 1
        elif (not self.start_date or self.start_date > region_model.end_date) and (
            self.point_date > region_model.end_date
        ):
            self.unbounded = 2

        # a positive point that is unbounded is a positive_unbounded type
        if self.status == "positive" and self.unbounded:
            self.status = "positive_unbounded"


class StackSlice:
    """Class definition for a slice (aka an observation) in a site stack

    Attributes:
        df: a geopandas dataframe representing the observation, derived from the site model's geojson annotation file
        polygon: a shapely geometry representing the observation's spatial boundary or boundaries
        area: the area of the polygon in square kilometers
        boundary_flags: boolean flags that indicate whether the polygon geometry or geometries represent the site boundary (True) or subsites (False)
        date: the observation's calendar date (yyyy-mm-dd format)
        source: the observation's image source
        score: the observation's confidence score, a float ranging from 0.0 (least confident) to 1.0 (most confident)
        phase: the observation's activity phase label, indicating the phase of activity of the site model on this particular observation's date
        id: the readable ID for the observation
        uuid: a unique ID for the observation
    """

    def __init__(self, df):
        """
        Creates a StackSlice object for a SiteStack.

        Parameters:
            df (GeoDataFrame): A single-row GeoDataFrame containing information about a stack slice.

        Attributes:
            df (GeoDataFrame): A copy of the single-row input GeoDataFrame.
            polygon (Geometry): The geometry of the stack slice.
            area (float): The area of the stack slice in square kilometers.
            boundary_flags (List[str]): A list of boolean flags indicating whether the polygon geometry represents the site boundary (True) or subsites (False).
            date (datetime): The date of the stack slice.
            source (str or None): The sensor source of the stack slice.
            score (float): The confidence score of the stack slice.
            phase (str): The current phase of the stack slice.
            id (str): The ID of the stack slice.
            uuid (UUID): The UUID of the stack slice.
        """
        self.df = df.copy(deep=True)

        # Default to EPSG:4326 if no CRS is specified
        if not df.crs:
            self.df.set_crs(4326, inplace=True)

        # Retrieve the first row of the GeoDataFrame and assign it to the row variable
        row = self.df.iloc[0]

        # Extract the geometry from the first row and assign it to the self.polygon attribute
        self.polygon = row["geometry"]

        # Compute the area of the polygon in square kilometers based on EPSG:4326
        self.area = GeometryUtil.compute_region_area(self.polygon)

        # Extract the boundary flags from the first row, convert them to a list of boolean flags, and assign them to the self.boundary_flags attribute
        self.boundary_flags = str(row["is_site_boundary"]).replace(" ", "").split(",")

        self.date = pd.to_datetime(row["observation_date"], format="%Y-%m-%d")

        self.source = row["source"] if row["source"] else None

        # Default score is 1
        self.score = row.get("score", 1)
        if np.isnan(self.score):
            self.score = 1

        self.phase = row["current_phase"]

        self.set_id()
        self.uuid = uuid.uuid4()

    def set_id(self):
        """
        Set the ID of the StackSlice based on the date and source attributes.

        This method concatenates the date and image source attributes to form the ID of the object.

        Returns:
            None
        """
        self.id = f"{self.date}_{self.source}"


class SiteStack(SiteModel):
    """Class definition for a site stack, a sequence of related polygon observations that capture the progression of activity in a particular location over a period of time

    Attributes:
        df: a geopandas dataframe representing the site stack, derived from the geojson annotation file
        annotation_id: the original ID provided in the site model's geojson annotation file
        originator: the ID of the site model's annotator
        mgrs: the military grid reference system code that indicates where the site model is geographically located
        id: the readable ID for the site model
        uuid: a unique ID for the site model
        sites: the list of site IDs of oversegmented site models that constitute this site model, if any (by default, this is simply a list of one element that is the site model's own ID)
        annotated_status: the site model's original status, as it appears in the annotation file
        annotated_null_start: boolean flag that indicates whether the annotation file has an unspecified (null) start date
        annotated_null_end: boolean flag that indicates whether the annotation file has an unspecified (null) end date
        status: the site model's effective status for the purposes of association and scoring, which depends on the kind of ground truth activity that is being assessed (partial, completed, overall)
        score: the site model's confidence score, a float ranging from 0.0 (least confident) to 1.0 (most confident)
        predicted_phase: the next activity phase that the site will transition to in the future, beyond its end date
        predicted_date: the date in the future when the site will transition to the next activity phase
        unbounded: an integer code to indicate the temporal bounds of the site model relative to the given region model
        association_status: indicates how the site model's association was scored (e.g. true positive "tp", false positive "fp", false negative "fn", no impact "0")
        associated: a Boolean flag to indicate whether the site model was associated with another site model
        color: an integer code to indicate how the site model should be displayed in the visualization tool
        start_date: the site-level start date, as annotated in the geojson file (yyyy-mm-dd format)
        end_date: the site-level end date, as annotated in the geojson file (yyyy-mm-dd format)
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
        area: the area of the site model's polygon union in square kilometers
    """

    @timer
    def __init__(self, df, region_model, site, annotation_id, originator, crs=None):
        """
        Initializes a SiteStack object with the provided data.

        Parameters:
            df (GeoDataFrame): The GeoDataFrame containing the data for the site stack.
            region_model (RegionModel): The RegionModel object representing the region model.
            site (dict): The site information as a dictionary.
            annotation_id (str): The ID of the annotation.
            originator (str): The originator of the site stack.
            crs (int or str, optional): The coordinate reference system (CRS) of the site stack. Defaults to None.
        """

        # Initialize the attributes
        self.annotated_null_start = False
        self.annotated_null_end = False
        annotated_status = site["status"]  # the original status, as it appears in the annotation file
        status = site["status"]  # the current effective status, depending on the type of activity metric

        # Set the predicted phase and date
        self.predicted_phase = site.get("predicted_phase_transition")
        self.predicted_date = site.get("predicted_phase_transition_date")

        # Set the unbounded status
        self.unbounded = 0

        # Initialize the association-related attributes
        self.association_status = None
        self.associated = None
        self.color = None

        # Get the site-level start date and end date in the annotation
        self.start_date = site["start_date"]
        self.end_date = site["end_date"]

        # Call the parent class's constructor (SiteModel)
        super().__init__(
            df,
            region_model,
            site.get("mgrs", ""),
            crs,
            site.get("version", ""),
            annotation_id,
            originator,
            annotated_status,
            status,
            site.get("score", 1),
        )

        # The list of oversegmented sites is the site itself, by default
        self.sites = [self.id]

        # Convert the start and end dates to datetime objects
        if self.start_date:
            self.start_date = pd.to_datetime(str(site["start_date"]), format="%Y-%m-%d")
        if self.end_date:
            self.end_date = pd.to_datetime(str(site["end_date"]), format="%Y-%m-%d")

        # Clip site start and end dates to the region model's start and end dates
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

        # Set the coordinate reference system (currently, only EPSG:4326 is supported)
        if crs:
            self.df = self.df.to_crs(epsg=crs)
        self.crs = self.df.crs.srs

        # Add the stack ID to the GeoDataFrame
        self.df["stack"] = self.id
        self.df = self.df[self.df["type"] != "site"].reset_index()

        # Change the site's first and last observation dates to match the site-level start_date and end_date
        if len(self.df) >= 2:
            if not self.df.loc[0, "observation_date"]:
                self.df.loc[0, "observation_date"] = str(self.start_date.date())
            if not self.df.loc[len(self.df) - 1, "observation_date"]:
                self.df.loc[len(self.df) - 1, "observation_date"] = str(self.end_date.date())

        # Remove observations without dates
        self.df.dropna(subset=["observation_date"], inplace=True)

        # Create site slices (observations)
        slices = []
        for i, row in self.df.iterrows():
            if row.get("type") != "site":
                new_slice = StackSlice(gpd.GeoDataFrame([row.to_dict()], geometry=[row["geometry"]], crs=self.df.crs))
                # Check validity of polygon
                if not new_slice.polygon.is_valid:
                    # Note that some of the ground truth observations with subsites (the is_site_boundary list has multiple elements) have "invalid" overlapping polygons
                    # However, the test harness metrics are still computed accurately
                    logging.debug(f"Invalid slice polygon in {self.id} with slice ID {new_slice.id}")
                slices.append(new_slice)

        # Sort the slices based on date and ID
        slices.sort(key=lambda x: (x.date, x.id))

        # Replace nans with the string "None" in the current_phase column
        # to work around a change in fiona 1.9.x
        if FIONA_GE_1_9_0:
            self.df = self.df.replace(float("nan"), None)

        # Remove polygons from the multipolygon geometry that are not site boundaries (for broad area search only)
        for slice in slices:
            # Do nothing for the base case (a single site boundary polygon)
            if len(slice.boundary_flags) == 1 and slice.boundary_flags[0] == "True":
                continue
            elif type(slice.polygon) != MultiPolygon:
                continue
            # Remove non-site boundary polygons
            else:
                new_multipolygon = MultiPolygon(
                    [p for p, flag in zip(slice.polygon.geoms, slice.boundary_flags) if flag != "False"]
                )
                # Check validity of multi-polygon
                if not new_multipolygon.is_valid:
                    logging.warning(f"Invalid multi-polygon created for {self.id} {slice.id}")
                slice.polygon = new_multipolygon
                slice.area = GeometryUtil.compute_region_area(slice.polygon)

        # Determine the site model's bounded status, relative to the region model's temporal bounds
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

        def has_activity(phases):
            """
            Check if the given list of phases contains the "Site Preparation" or "Active Construction" phase.
            A site stack has heavy construction activity if it contains at least one observation with one of these phases.

            Parameters:
                phases (list of str): A list of phase names.

            Returns:
                bool: True if the list contains either "Site Preparation" or "Active Construction", False otherwise.
            """
            return "Site Preparation" in "".join(phases) or "Active Construction" in "".join(phases)

        # A ground truth site is unbounded if one or more of its observations are outside the region model's temporal bounds
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

        # A site remains bounded if all unbounded observations are additional (extra) Post Constructions and as long as one Post Construction observation is bounded
        if (
            not has_activity(pre_phases)
            and "Post Construction" in bounded_phases
            and set(post_phases) == set(["Post Construction"])
        ):
            self.unbounded = 0
        if (
            not has_activity(pre_phases)
            and "Post Construction" not in bounded_phases
            and "Post Construction" in post_phases
        ):
            if "Active Construction" in bounded_phases:
                self.partial_type = "A"
            elif "Site Preparation" in bounded_phases:
                self.partial_type = "B"

        if not bounded_slices:
            logging.debug(f"{self.annotation_id} has no bounded slices")

        # Filter the observations
        self.bounded_slices = bounded_slices
        self.unbounded_slices = unbounded_slices
        if self.status not in POSITIVE_ACTIVITY_STATUS_TYPES:
            self.slices = slices
        else:
            self.slices = bounded_slices  # drop unbounded slices (but not for site types 3 and 4)

        # Initialize other dates of interest
        self.first_obs = self.slices[0].date if self.slices else None
        self.last_obs = self.slices[-1].date if self.slices else None
        self.first_post_obs = None
        self.len_first_post_obs = None

        self.start_activity = None
        self.earliest_start_activity = None
        self.latest_start_activity = None
        self.end_activity = None

        # Get activity dates for truth sites types 1 and 2
        if self.status in POSITIVE_ACTIVITY_STATUS_TYPES:
            # Latest start of activity
            if has_activity(pre_phases) and (
                has_activity(bounded_phases) or "Post Construction" in "".join(bounded_phases)
            ):
                self.latest_start_activity = region_model.start_date
            else:
                for bounded_slice in bounded_slices:
                    if bounded_slice.phase and has_activity([bounded_slice.phase]):
                        self.latest_start_activity = bounded_slice.date
                        break
            self.start_activity = self.latest_start_activity

            # Compute the earliest start of activity
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

                # Compute the end of activity
                for bounded_slice in bounded_slices:
                    if bounded_slice.phase:
                        segment_phases = set(re.split(", |_", bounded_slice.phase))
                        # All of the observation's phase labels must be Post Construction
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

        # For other truth site types, the start and end of activity are the same as the site-level start and end dates
        else:
            self.start_activity = self.start_date
            self.end_activity = self.end_date

        # Compute the activity duration
        self.activity_dates = set()
        self.len_activity = None
        if self.start_activity and self.end_activity:
            self.activity_dates = set(pd.date_range(start=self.start_activity, end=self.end_activity))
            self.len_activity = len(self.activity_dates)
        # A positive truth site is unbounded if it does not have a start or end activity date
        elif self.status in POSITIVE_ACTIVITY_STATUS_TYPES:
            self.status = "positive_unbounded"

        # Compute the minimum activity duration
        self.min_activity_dates = set()
        self.len_min_activity = None
        if self.latest_start_activity and self.end_activity:
            self.min_activity_dates = set(pd.date_range(start=self.latest_start_activity, end=self.end_activity))
            self.len_min_activity = len(self.min_activity_dates)

        # Compute the maximum activity duration
        self.max_activity_dates = set()
        self.len_max_activity = None
        if self.earliest_start_activity and self.end_activity:
            self.max_activity_dates = set(pd.date_range(start=self.earliest_start_activity, end=self.end_activity))
            self.len_max_activity = len(self.max_activity_dates)

        # Compute the site model's spatial representations and area
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
            self.base_polygon_union = self.polygon_union
        else:
            logging.warning(f"No bounded polygons for {self.id}")
            self.polygon_union = Polygon()
            try:
                self.base_polygon_union = unary_union([slice.polygon for slice in unbounded_slices])
                self.area = GeometryUtil.compute_region_area(self.base_polygon_union)
            except Exception:
                logging.warning("Failed to calculate area of polygon union for unbounded slices")
                self.base_polygon_union = unbounded_slices[0].polygon
                self.area = GeometryUtil.compute_region_area(self.base_polygon_union)

        logging.debug(f"Created site stack {self.id} with {len(self.slices)} slices")

    def get_slice(self, date, exact=False):
        """
        Retrieves the most recent site model observation that is not newer than the specified date.

        Parameters:
            date (str, yyyy-mm-dd format): The date to compare with the site model observations.
            exact (bool, optional): If True, only return an observation if it has the exact same calendar date as the date parameter. Defaults to False.

        Returns:
            SiteSlice or None: The most recent site model observation that is not newer than the specified date, or None if there is no such observation.
        """
        # Get the most recent site model observation that isn't newer than the specified date
        prev_slices = sorted(
            list(filter(lambda x: x.date <= pd.to_datetime(date), self.slices)),
            key=lambda x: (x.date, x.id),
        )
        if prev_slices:
            if prev_slices[-1].date == date or not exact:
                return prev_slices[-1]
            else:
                # There is no site model observation on the specified date
                return None
        # All of the site model timesteps are newer than the ground truth
        else:
            logging.debug("Returning no slices")
            return None

    @timer
    def combine_stacks(self, stacks):
        """
        Merge the given site model stacks into a single combined site stack
        (self, which should be a ground truth stack).

        Parameters:
            stacks (List[SiteStack]): A list of SiteStack objects to be merged.

        Returns:
            SiteStack: The combined site stack with the merged attributes and slices.

        """

        # Create a duplicate of the ground truth stack, to be converted to the combined site stack
        combined_stack = deepcopy(self)
        combined_stack.len_activity = len(combined_stack.activity_dates)

        # sort the site stacks for deterministic results
        sorted_stacks = sorted(stacks, key=lambda stack: stack.id)

        # Set new attributes
        combined_stack.mgrs = "_".join([str(stack.mgrs) for stack in sorted_stacks])
        combined_stack.crs = "_".join([str(stack.crs) for stack in sorted_stacks])
        combined_stack.sites = [str(stack.id) for stack in sorted_stacks]
        combined_stack.id = Evaluation.get_sm_stack_id(stacks)
        combined_stack.version = "_".join([str(stack.version) for stack in sorted_stacks])
        combined_stack.df = (
            None  # technically, this should be a combination of the dataframes, but this is not needed for scoring
        )

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

        observation_dates = set()

        # Truth site dates
        for slice in self.slices:
            observation_dates.add(slice.date)

        # Proposed dates
        for stack in stacks:
            for slice in stack.slices:
                observation_dates.add(slice.date)

        # Create new, combined observations
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
        Check if there is any intersection between the unary union of the polygons of another stack and the polygons of the current object.
        If not, then there is definitely no intersection between any of their corresponding observations.
        Can be used an alternative to, or in combination with, a spatial index in order to filter out stack pairs with no intersection.

        Parameters:
            stack (SiteStack): The SiteStack object representing the site model stack.

        Returns:
            shapely.geometry.Polygon: The intersection geometry between the two stacks. If there is no intersection, an empty Polygon is returned.
        """

        # Get the corresponding slice from the site model stack
        sm_slices = [stack.get_slice(gt_slice.date) for gt_slice in self.slices]
        sm_polygons = [sm_slice.polygon for sm_slice in sm_slices if sm_slice]

        # Get the union of all site model slices
        sm_polygon_union = unary_union(sm_polygons)

        # Check if there is any intersection between the 2 stacks
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
        Initializes a RegionModel object.

        Parameters:
            roi_path (str): path to a ground truth region model geojson file (str)
            crs (int, optional): The target coordinate reference system (EPSG code). Defaults to None.

        Attributes:
            df (geopandas.GeoDataFrame): The GeoDataFrame containing the region model.
            sites_in_rm_file (list): The list of IDs of truth sites present in the region model file.
            polygon (shapely.geometry.Polygon): The region model polygon geometry.
            area (float): The area of the region model polygon in square meters.
            start_date (datetime.datetime): The start date of the region model.
            end_date (datetime.datetime): The end date of the region model.
            dates (int): The number of dates between the start and end dates.
            id (str): The ID of the region model.
        """
        self.df = gpd.read_file(roi_path)
        # A full region model has site summaries in it
        try:
            self.sites_in_rm_file = self.df[self.df["type"] == "site_summary"]["site_id"].tolist()
        # An empty region model does not have site summaries
        except KeyError:
            self.sites_in_rm_file = []
        self.df = self.df.loc[self.df["type"] == "region"]
        if crs:
            self.df = self.df.to_crs(epsg=crs)

        # Create the region model from the first row
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
        Find square meters per degree for a given latitude based on EPSG:4326.
        Note that both latitude and longitude scales are dependent on latitude only.
        https://en.wikipedia.org/wiki/Geographic_coordinate_system#Length_of_a_degree

        Parameters:
            lat (float): The average latitude in degrees.

        Returns:
            float: The square meters per degree for latitude coordinate.
        """

        lat *= np.pi / 180.0  # convert to radians
        lat_scale = 111132.92 - (559.82 * np.cos(2 * lat)) + (1.175 * np.cos(4 * lat)) - (0.0023 * np.cos(6 * lat))
        lon_scale = (111412.84 * np.cos(lat)) - (93.5 * np.cos(3 * lat)) + (0.118 * np.cos(5 * lat))

        return lat_scale * lon_scale

    @classmethod
    @timer
    def compute_region_area(cls, region_poly, epsg=4326):
        """
        Compute the area of a region defined by a polygon based on EPSG:4326.

        Parameters:
            region_poly (shapely.geometry.Polygon or shapely.geometry.MultiPolygon): The polygon(s) that define the region boundary.
            epsg (int, optional): The coordinate reference system (CRS) identifier. Defaults to EPSG:4326 (WGS84).

        Returns:
            float: The area of the region in square kilometers, rounded to the nearest square centimeter.

        Note:
            The function ignores area warnings related to geographic CRS on Mac OS.
            The area calculation is scaled by the scale factor based on the average latitude of the region.
            The input polygon can be a single polygon or a multi-polygon.
        """

        # ignore area warnings on Mac OS...
        # The warning is from geopandas. Essentially, it is alerting us that
        # area isn't constant in a geographic CRS -> it varies with latitude. However, this
        # isn't a problem because the custom area function accounts for this and scales by lat afterwards.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            poly_area = region_poly.area

        if epsg == 4326:
            # Get average latitude
            try:
                avg_lat = (region_poly.bounds[1] + region_poly.bounds[3]) / 2.0
            except KeyError:
                avg_lat = (region_poly.bounds["miny"] + region_poly.bounds["maxy"]) / 2.0
            except IndexError:
                logging.warning("Failed to compute region area for empty polygon")
                return 0

            # Scale the area by the scale factor
            poly_area *= GeometryUtil.scale_area(avg_lat)
        # Convert from square meters to square kilometers
        if type(poly_area) == pd.Series:
            poly_area = float(poly_area.iloc[0])

        # Return area in units of square kilometers and round to the nearest square centimeter
        return round(poly_area / 1e6, 10)

    @classmethod
    @timer
    def intersection(cls, df1, df2):
        """
        Calculates the intersection between two geometries.

        Parameters:
            df1 (GeoDataFrame): The first GeoDataFrame containing polygons.
            df2 (GeoDataFrame): The second GeoDataFrame containing polygons.

        Returns:
            tuple: A tuple containing the intersection area (float) and the intersection shape (GeoDataFrame).
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
        Calculates the union of two geometries.

        Parameters:
            df1 (GeoDataFrame): The first GeoDataFrame containing polygons.
            df2 (GeoDataFrame): The second GeoDataFrame containing polygons.

        Returns:
            tuple: A tuple containing the area of the union (float) and the union shape (MultiPolygon).
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
        Calculates the convex hull of two geometries and returns the area of the resulting polygon.

        Parameters:
            df1 (GeoDataFrame): The first GeoDataFrame containing polygons.
            df2 (GeoDataFrame): The second GeoDataFrame containing polygons.
            area (bool, optional): If True, return the area of the convex hull. If False, return the convex hull polygon.
                Defaults to True.

        Returns:
            float or shapely.geometry.multipolygon.MultiPolygon: The area of the convex hull if area is True,
            otherwise the convex hull polygon.
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
    def project_geometry(cls, g: Union[Point, Polygon]):
        """
        Projects a given geometry onto a new coordinate system.

        Parameters:
            g (Union[Point, Polygon]): The geometry object to be projected. It can be either a Point or a Polygon.

        Returns:
            Union[shapely.geometry.polygon.Polygon, shapely.geometry.point.Point]: The projected geometry object.
                If the input geometry is a Polygon or MultiPolygon, the resulting object will be a Polygon.
                If the input geometry is a Point, the resulting object will be a Point.

                If the projected geometry is invalid, a warning is logged and the original geometry is returned.
        """
        if isinstance(g, Polygon):
            coords = g.exterior.coords
        elif isinstance(g, MultiPolygon):
            coords = g.convex_hull.exterior.coords
        else:
            coords = g.coords

        new_coords = []
        for c in coords:
            lon, lat = c
            lat_rads = lat * (np.pi / 180.0)  # convert to radians
            lat_scale = (
                111132.92
                - (559.82 * np.cos(2 * lat_rads))
                + (1.175 * np.cos(4 * lat_rads))
                - (0.0023 * np.cos(6 * lat_rads))
            )
            lon_scale = (111412.84 * np.cos(lat_rads)) - (93.5 * np.cos(3 * lat_rads)) + (0.118 * np.cos(5 * lat_rads))

            new_c = (lon_scale * lon, lat_scale * lat)
            new_coords.append(new_c)

        if isinstance(g, Polygon) or isinstance(g, MultiPolygon):
            g_rescaled = Polygon(new_coords)
            # Check validity of rescaled polygon
            if not g_rescaled.is_valid:
                logging.warning("Invalid polygon created")
            return g_rescaled
        else:
            return Point(new_coords)

    @classmethod
    def calc_spatial_point_metrics(cls, site_polygon: Polygon, site_point: Point):
        """
        Calculates various spatial point metrics between a given polygon and a point.

        Parameters:
            site_polygon (shapely.geometry.polygon.Polygon): The polygon to calculate metrics against.
            site_point (shapely.geometry.point.Point): The point to calculate metrics from.

        Returns:
            tuple[float, float, float]: A tuple containing the minimum distance, centroid distance, and maximum distance.
        """

        def calc_dist_to_boundary(site_poly_projection: Polygon, query_pt_projection: Point):
            """
            Calculates the distance between a point projection and the nearest boundary point of a polygon projection.
            The distance is zero if the point is located inside the polygon.

            Parameters:
                site_poly_projection (shapely.geometry.polygon.Polygon): The polygon projection to calculate the distance against.
                query_pt_projection (shapely.geometry.point.Point): The point projection to calculate the distance from.

            Returns:
                shapely.geometry.distance.Distance: The distance between the point projection and the boundary of the polygon projection.
            """
            return query_pt_projection.distance(site_poly_projection.boundary)

        def calc_dist_to_centroid(site_poly_projection: Polygon, query_pt_projection: Point):
            """
            Calculates the distance between a point projection and the centroid of a given polygon.

            Parameters:
                site_poly_projection (shapely.geometry.polygon.Polygon): The polygon whose centroid is used for the calculation.
                query_pt_projection (shapely.geometry.point.Point): The point from which the distance is calculated.

            Returns:
                shapely.geometry.distance.Distance: The distance between the point projection and the centroid of the polygon.
            """
            return query_pt_projection.distance(site_poly_projection.centroid)

        def calc_haussdorff_dist(site_poly_projection: Polygon, query_pt_projection: Point):
            """
            Calculates the Hausdorff distance between a point projection and the furthest boundary point of a polygon projection.

            Parameters:
                site_poly_projection (shapely.geometry.polygon.Polygon): The polygon projection to calculate the Hausdorff distance against.
                query_pt_projection (shapely.geometry.point.Point): The point projection to calculate the Hausdorff distance from.

            Returns:
                float: The Hausdorff distance between the point projection and the boundary of the polygon projection.
            """
            return query_pt_projection.hausdorff_distance(site_poly_projection.boundary)

        site_poly_proj = cls.project_geometry(site_polygon)
        query_pt_proj = cls.project_geometry(site_point)

        boundary_distance = calc_dist_to_boundary(site_poly_proj, query_pt_proj)
        # the minimum distance is zero if the point is located inside the polygon
        min_distance = 0 if site_poly_proj.contains(query_pt_proj) else boundary_distance
        centroid_distance = calc_dist_to_centroid(site_poly_proj, query_pt_proj)
        max_distance = calc_haussdorff_dist(site_poly_proj, query_pt_proj)
        return min_distance, centroid_distance, max_distance

    @classmethod
    def calc_temporal_point_metrics(cls, site_dates: Iterable[datetime.date], point_date: datetime.date):
        """
        Calculate the temporal point metrics for a given set of site dates and a point date.

        Parameters:
            site_dates (Iterable[datetime.date]): An iterable of site dates.
            point_date (datetime.date): The point date for which to calculate the temporal metrics.

        Returns:
            Tuple[int]: A tuple containing the minimum temporal distance, the central temporal distance, and the maximum temporal distance.

        """

        def calc_min_temporal_dist(site_dates: Iterable[datetime], query_date: datetime) -> int:
            """
            Calculates the minimum temporal distance between a query date and a set of site dates.

            Parameters:
                site_dates (Iterable[datetime]): An iterable of site dates.
                query_date (datetime): The query date for which to calculate the minimum temporal distance.

            Returns:
                int: The number of calendar days between the query date and the closest site date.
            """
            dt = [(query_date - d).days for d in site_dates]
            return min(dt, key=np.abs)

        def calc_central_temporal_dist(
            site_start: datetime.date,
            site_end: datetime.date,
            query_date: datetime.date,
        ) -> int:
            """
            Calculates the central temporal distance between a query date and a range of dates.

            Parameters:
                site_start (datetime.date): The start date of the range.
                site_end (datetime.date): The end date of the range.
                query_date (datetime.date): The query date for which to calculate the central temporal distance.

            Returns:
                int: The number of calendar days between the query date and the middle date in the range.
            """
            site_midpoint = site_start + ((site_end - site_start) / 2)
            return (query_date - site_midpoint).days

        def calc_max_temporal_dist(
            site_start: datetime.date,
            site_end: datetime.date,
            query_date: datetime.date,
        ) -> Tuple[int]:
            """
            Calculates the maximum temporal distance between a query date and a range of dates.

            Parameters:
                site_start (datetime.date): The start date of the range.
                site_end (datetime.date): The end date of the range.
                query_date (datetime.date): The query date for which to calculate the maximum temporal distance.

            Returns:
                Tuple[int]: A tuple containing the number of calendar days between the query date and the start date,
                and the number of calendar days between the query date and the end date.
            """
            return (query_date - site_start).days, (query_date - site_end).days

        site_start, site_end = min(site_dates), max(site_dates)
        min_temporal_distance = calc_min_temporal_dist(site_dates, point_date)
        central_temporal_distance = calc_central_temporal_dist(site_start, site_end, point_date)
        max_temporal_distance = max(calc_max_temporal_dist(site_start, site_end, point_date), key=abs)
        return min_temporal_distance, central_temporal_distance, max_temporal_distance

    @classmethod
    def calc_iou(cls, df1, df2):
        """
        Calculates the Intersection over Union (IoU) between two geometries.

        Parameters:
            df1 (GeoDataFrame): The first GeoDataFrame
            df2 (GeoDataFrame): The second GeoDataFrame

        Returns:
            Tuple[float, float, GeoSeries, float, GeoSeries]: A tuple containing the following:
                - The IoU ratio, a float between 0 and 1.
                - The area of the intersection, a float.
                - The intersection geometry, a GeoSeries.
                - The area of the union, a float.
                - The union geometry, a GeoSeries.
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
        Calculates the Intersection over Truth (IoT) between two geometries.

        Parameters:
            df1 (GeoDataFrame): The first GeoDataFrame (represents the "truth" geometry)
            df2 (GeoDataFrame): The second GeoDataFrame
            intersection (GeoSeries, optional): The intersection geometry. Defaults to None.

        Returns:
            Tuple[float, float]: A tuple containing the following:
                - The IOT ratio, a float between 0 and 1.
                - The intersection area, a float.
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
    def calc_precision(cls, tp, fp):
        """
        Calculates the precision score.

        Parameters:
            tp (int): The number of true positives.
            fp (int): The number of false positives.

        Returns:
            float: The precision score. If the number of true positives is 0, returns 0.
        """
        return tp / (tp + fp) if tp else 0

    @classmethod
    def calc_recall(cls, tp, fn):
        """
        Calculates the recall score.

        Parameters:
            tp (int): The number of true positives.
            fn (int): The number of false negatives.

        Returns:
            float: The recall score. If the number of true positives is 0, returns 0.
        """
        return tp / (tp + fn) if tp else 0

    @classmethod
    def calc_F1(cls, tp, fp, fn):
        """
        Calculates the F1 score.

        Parameters:
            tp (int): The number of true positives.
            fp (int): The number of false positives.
            fn (int): The number of false negatives.

        Returns:
            float: The F1 score. If the number of true positives is 0, returns 0.
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
        gt_whitelist,
        gt_blacklist,
        sm_files,
        sm_whitelist,
        sm_blacklist,
        rm_path,
        roi,
        taus=[0.2],
        rhos=[0.5],
        confidence_score_thresholds=[0.0],
        min_spatial_distances=[100],
        central_spatial_distances=[None],
        max_spatial_distances=[None],
        min_temporal_distances=[None],
        central_temporal_distances=[None],
        max_temporal_distances=[None],
        temporal_iops=[0.1],
        temporal_iots=[0.2],
        transient_temporal_iops=[0.1],
        transient_temporal_iots=[0.2],
        small_site_threshold=9000,
        crs=4326,
        min_proposal_areas=[0.0],
        output_dir=None,
        parallel=True,
        num_processes=None,
        sequestered_id=None,
        gt_points_file=None,
        proposal_bounded_filter=None,
    ):
        """
        This function initializes the Evaluation class instance with the provided parameters.
        It sets up variables to store the optimal threshold values, checks which parameters have multiple input values and need to be swept across,
        and initializes other instance attributes.

        Parameters:
            gt_files (List[str]): A list of ground truth site stack filepaths.
            gt_whitelist (List[str]): The list of ground truth site whitelist types.
            gt_blacklist (List[str]): The list of ground truth site blacklist types.
            sm_files (List[str]): A list of proposed site stack filepaths.
            sm_whitelist (List[str]): The list of proposed site model whitelist types.
            sm_blacklist (List[str]): The list of proposed site model blacklist types.
            rm_path (str): The path to the region model geojson file.
            roi (str): The region of interest.
            taus (list, optional): A list of association threshold values to sweep. Defaults to [0.2].
            rhos (list, optional): A list of detection threshold values to sweep. Defaults to [0.5].
            confidence_score_thresholds (list, optional): A list of confidence score thresholds to sweep. Defaults to [0.0].
            min_spatial_distances (list, optional): A list of minimum spatial distances to sweep. Defaults to [100].
            central_spatial_distances (list, optional): A list of central spatial distances to sweep. Defaults to [-1].
            max_spatial_distances (list, optional): A list of maximum spatial distances to sweep. Defaults to [-1].
            min_temporal_distances (list, optional): A list of minimum temporal distances to sweep. Defaults to [-1].
            central_temporal_distances (list, optional): A list of central temporal distances to sweep. Defaults to [-1].
            max_temporal_distances (list, optional): A list of maximum temporal distances to sweep. Defaults to [-1].
            temporal_iops (list, optional): A list of temporal intersection over proposal site duration thresholds to sweep. Defaults to [0.1].
            temporal_iots (list, optional): A list of temporal intersection over truth site duration thresholds to sweep. Defaults to [0.2].
            transient_temporal_iops (list, optional): A list of transient temporal intersection over proposal site duration thresholds to sweep. Defaults to [0.1].
            transient_temporal_iots (list, optional): A list of transient temporal intersection over truth site duration thresholds to sweep. Defaults to [0.2].
            small_site_threshold (int, optional): The threshold for the minimum size of a ground truth site. Defaults to 9000 meters.
            crs (int, optional): The coordinate reference system. Defaults to 4326.
            min_proposal_areas (list, optional): A list of minimum proposal areas to sweep. Defaults to [0.0].
            output_dir (str, optional): The output directory. Defaults to None.
            parallel (bool, optional): Whether to run in parallel processing mode. Defaults to True.
            num_processes (int, optional): The number of processes. Defaults to None.
            sequestered_id (str, optional): The sequestered ID. Defaults to None.
            gt_points_file (str, optional): The path to the ground truth points file. Defaults to None.
            proposal_bounded_filter (str, optional): The proposal bounded filter. Defaults to None.

        Returns:
            None
        """
        logging.info("Starting evaluation...")

        # inputs
        self.crs = crs
        self.gt_files = gt_files
        self.sm_files = sm_files

        # initialize variables that will store the threshold values that yield the optimal performance scores (to be updated later during the evaluation)
        self.best_tau = None
        self.best_rho = None
        self.best_min_proposal_area = None
        self.best_min_score = None
        self.best_tiop = None
        self.best_tiot = None
        self.best_ttiop = None
        self.best_ttiot = None
        self.best_min_spatial_distance = None
        self.best_central_spatial_distance = None
        self.best_max_spatial_distance = None
        self.best_min_temporal_distance = None
        self.best_central_temporal_distance = None
        self.best_max_temporal_distance = None

        # set thresholds as instance attributes (click already handles type casting)
        self.taus = taus
        self.rhos = rhos
        self.min_proposal_areas = min_proposal_areas
        self.temporal_iops = temporal_iops
        self.temporal_iots = temporal_iots
        self.transient_temporal_iops = transient_temporal_iops
        self.transient_temporal_iots = transient_temporal_iots
        self.small_site_threshold = small_site_threshold
        self.confidence_score_thresholds = confidence_score_thresholds
        self.min_spatial_distances = min_spatial_distances
        self.central_spatial_distances = central_spatial_distances
        self.max_spatial_distances = max_spatial_distances
        self.min_temporal_distances = min_temporal_distances
        self.central_temporal_distances = central_temporal_distances
        self.max_temporal_distances = max_temporal_distances

        # check which thresholds have multiple input values and need to be swept across
        self.sweep_tau = len(self.taus) > 1
        self.sweep_rho = len(self.rhos) > 1
        self.sweep_min_proposal_area = len(self.min_proposal_areas) > 1
        self.sweep_confidence = len(self.confidence_score_thresholds) > 1
        self.sweep_temporal_iop = len(temporal_iops) > 1
        self.sweep_temporal_iot = len(temporal_iots) > 1
        self.sweep_transient_temporal_iop = len(transient_temporal_iops) > 1
        self.sweep_transient_temporal_iot = len(transient_temporal_iots) > 1
        self.sweep_min_spatial_distance = len(self.min_spatial_distances) > 1
        self.sweep_central_spatial_distance = len(self.central_spatial_distances) > 1
        self.sweep_max_spatial_distance = len(self.max_spatial_distances) > 1
        self.sweep_min_temporal_distance = len(self.min_temporal_distances) > 1
        self.sweep_central_temporal_distance = len(self.central_temporal_distances) > 1
        self.sweep_max_temporal_distance = len(self.max_temporal_distances) > 1

        self.best = None  # the best row from the metric scoreboard (the row with the highest F1 score and the strictest thresholds)
        self.detections = (
            {}
        )  # a dict mapping a ground truth site ID to a list of the proposed site model(s) that it associates with
        self.proposals = (
            {}
        )  # a dict mapping a proposed site model ID to a list of the ground truth site(s) that it associates with
        self.matched_pairs = (
            []
        )  # a list of tuples of associated pairs with the format: (ground truth site, proposed site model)

        # multiprocessing
        self.parallel = parallel
        self.num_processes = num_processes

        # output directories
        os.makedirs(output_dir, exist_ok=True)
        self.output_dir = output_dir
        self.bas_dir = f"{output_dir}/bas"

        # region of interest
        self.roi = roi
        self.sequestered_id = sequestered_id

        # convert the types from letters to integers
        if proposal_bounded_filter:
            filter_map = {"a": -2, "b": -1, "c": 0, "d": 1, "e": 2}
            proposal_bounded_filter = list(set(proposal_bounded_filter.lower()))
            proposal_bounded_filter = [filter_map[item] for item in proposal_bounded_filter if item in filter_map]

        # multiprocessing
        self.counter = 0  # an approximate counter, not thread safe
        self.lock = Lock()
        self.queue = mp.Queue()  # a thread and process safe Queue

        # load the site stacks from a list of geojson files
        logging.debug("Loading site stacks")

        # load the region model
        if rm_path:
            logging.debug("Loading the region model")
            self.region_model = RegionModel(roi_path=rm_path, crs=crs)
            logging.info(
                f"Region model {rm_path} starts {self.region_model.start_date} and ends {self.region_model.end_date}"
            )
        else:
            logging.warning("No region model was specified")
            self.region_model = None

        # load the sites from a list of geojson files
        self.gt_points, self.gt_points_gdf, all_gt_points = self.load_points(
            gt_points_file, crs, self.region_model, gt_whitelist, gt_blacklist
        )
        (
            self.gt_stacks,
            self.gt_stack_gdf,
            all_gt_stacks,
            self.fully_contained_gt,
            self.partially_contained_gt,
        ) = self.load_stacks(gt_files, crs, self.region_model, gt_whitelist, gt_blacklist, rm_filter=True)
        (
            self.sm_stacks,
            self.sm_stack_gdf,
            all_sm_stacks,
            self.fully_contained_sm,
            self.partially_contained_sm,
        ) = self.load_stacks(
            sm_files,
            crs,
            self.region_model,
            sm_whitelist,
            sm_blacklist,
            bounded_filter=proposal_bounded_filter,
        )

        # save the site metadata to the local filesystem
        self.write_sites_csv(all_gt_stacks, all_gt_points, "gt_sites.csv")
        self.write_sites_csv(all_sm_stacks, {}, "sm_sites.csv")

        # a nested dict mapping every intersecting pair of ground truth site and proposed site to a dataframe of their slice-by-slice comparisons
        self.stack_comparisons = {gt_id: {} for gt_id in self.gt_stacks}
        self.point_comparisons = {gt_id: {} for gt_id in self.gt_points}

        # initialize the highest F1 score
        self.best_metric_score = -1

    @timer
    def write_sites_csv(self, stacks, points, filename):
        """
        Write the given sites (stacks and points) to a CSV file.

        Parameters:
            stacks (dict): A dictionary mapping site IDs to SiteStack objects.
            points (dict): A dictionary mapping site IDs to SitePoint objects.
            filename (str): The name of the output CSV file.

        Returns:
            None
        """
        df = pd.DataFrame()
        data = [
            (
                site_id,
                getattr(site, "status", None),
                getattr(site, "area", 0.0),
                getattr(site, "max_polygon_area", None),
                getattr(site, "score", None),
                getattr(site, "first_obs", None),
                getattr(site, "start_date", None),
                getattr(site, "earliest_start_activity", None),
                getattr(site, "latest_start_activity", None),
                getattr(site, "start_activity", None),
                getattr(site, "end_activity", None),
                getattr(site, "end_date", None),
                getattr(site, "last_obs", None),
                "point" if type(site) == SitePoint else "stack",
            )
            for site_id, site in {**stacks, **points}.items()
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
                "model type",
            ],
        )

        # remove the region model ID from the dataframe and replace it with the sequestered ID
        df = Evaluation.sanitize_dataframe(df, self.region_model.id, self.sequestered_id)
        df.sort_values("id", inplace=True, ignore_index=True)
        df.to_csv(f"{self.output_dir}/{filename}", index=False)

    @classmethod
    def sanitize_dataframe(cls, df, oldval, newval):
        """
        Sanitizes a pandas DataFrame by replacing occurrences of a specified value with a new value.

        Parameters:
            df (GeoDataFrame or DataFrame): The DataFrame to be sanitized.
            oldval (str): The value to be replaced.
            newval (str): The new value to replace the old value with.

        Returns:
            GeoDataFrame or DataFrame: The sanitized DataFrame with the replaced values.
        """
        if newval is None:
            # Nothing to sanitize, return original dataframe
            return df

        for row_idx, row in df.iterrows():
            for col_idx, _ in row.items():
                before = str(df.at[row_idx, col_idx])
                if oldval in before:
                    df.at[row_idx, col_idx] = before.replace(oldval, newval)
                elif f"{oldval[:2]}_" in before:
                    df.at[row_idx, col_idx] = before.replace(oldval[:3], f"{newval}_")
        return df

    def load_points(self, input_path, crs=None, region_model=None, whitelist=None, blacklist=None):
        """
        Load points from a file and create a dictionary of SitePoint objects and a GeoDataFrame of all points.

        Parameters:
            input_path (str): The path to the geojson file of point annotations.
            crs (str, optional): The coordinate reference system (CRS) of the points. Defaults to None.
            region_model (RegionModel, optional): The region model object used to filter the points. Defaults to None.
            whitelist (list, optional): The list of allowed status types for the points. Defaults to None.
            blacklist (list, optional): The list of forbidden status types for the points. Defaults to None.

        Returns:
            tuple: A tuple containing the following:
                - points (dict): A dictionary of SitePoint objects, respecting the whitelist and the blacklist, where the keys are the site IDs and the values are the corresponding SitePoint objects.
                - points_df (GeoDataFrame): A GeoDataFrame containing the points data.
                - all_points (dict): A dictionary of all the SitePoint objects, ignoring the whitelist and the blacklist, where the keys are the site IDs and the values are the corresponding SitePoint objects.
        """

        # load the points file
        points, all_points = {}, {}
        if input_path is None:
            return points, gpd.GeoDataFrame(), all_points
        df = gpd.read_file(input_path)
        points_df, all_points_df = [], []

        for row_idx, row in df.iterrows():
            # Check that the site ID (row["site_id"]) contains the region of interest ID (self.roi)
            if self.roi and self.roi not in row["site_id"]:
                continue

            # Check that the site ID (row["site_id"]) is listed in the region model
            if region_model and region_model.sites_in_rm_file and row["site_id"] not in region_model.sites_in_rm_file:
                continue

            # Create the point
            point_site = SitePoint(
                region_model,
                row["date"],
                row.get("site_start_date", row["date"]),
                row.get("site_end_date", row["date"]),
                row["site_id"],
                row["status"],
                row["base_version"],
                row["point_version"],
                row["date_version"],
                crs=crs,
                score=1,
                coordinates=row["geometry"],
            )
            all_points_df.append(row)
            all_points[row["site_id"]] = point_site

            # Include the point if its type is in the whitelist and not in the blacklist
            if (not whitelist or row["status"] in whitelist) and (not blacklist or row["status"] not in blacklist):
                points_df.append(row)
                points[row["site_id"]] = point_site

        # Create the GeoDataFrames for the point
        all_points_df = (
            gpd.GeoDataFrame(all_points_df, geometry="geometry").reset_index(drop=True)
            if all_points_df
            else gpd.GeoDataFrame(
                columns=[
                    "site_id",
                    "base_version",
                    "status",
                    "date",
                    "type",
                    "point_version",
                    "date_version",
                    "geometry",
                ],
                geometry="geometry",
            )
        )
        points_df = (
            gpd.GeoDataFrame(points_df, geometry="geometry").reset_index(drop=True)
            if points_df
            else gpd.GeoDataFrame(
                columns=[
                    "site_id",
                    "base_version",
                    "status",
                    "date",
                    "type",
                    "point_version",
                    "date_version",
                    "geometry",
                ],
                geometry="geometry",
            )
        )

        # Set the CRS
        if crs:
            all_points_df = all_points_df.set_crs(epsg=crs)
            points_df = points_df.set_crs(epsg=crs)

        # Make sure that all of the points are spatially located within the region bounds
        if region_model:
            points_within_region = gpd.sjoin(
                all_points_df,
                region_model.df[["geometry"]],
                how="inner",
                predicate="intersects",
            )
            points_df = points_df[points_df["site_id"].isin(points_within_region["site_id"])].reset_index(drop=True)
            points = {
                point_id: points[point_id]
                for point_id in points.keys()
                if point_id in points_within_region["site_id"].tolist()
            }
            all_points = {
                point_id: all_points[point_id]
                for point_id in all_points.keys()
                if point_id in points_within_region["site_id"].tolist()
            }

        return points, points_df, all_points

    @timer
    def load_stacks(
        self,
        input_paths,
        crs=None,
        region_model=None,
        whitelist=None,
        blacklist=None,
        bounded_filter=None,
        rm_filter=False,
    ):
        """
        Load site stacks from the given input paths and filter them based on the provided criteria.

        Parameters:
            input_paths (List[str]): The paths to the site stack geojson annotation files.
            crs (str, optional): The coordinate reference system (CRS) of the site stacks. Defaults to None.
            region_model (RegionModel, optional): The region model used to filter the site stacks. Defaults to None.
            whitelist (List[str], optional): The list of allowed site status types. Defaults to None.
            blacklist (List[str], optional): The list of forbidden site status types. Defaults to None.
            bounded_filter (List[int], optional): The list of temporally bounded site types to evaluate. Defaults to None.
            rm_filter (bool, optional): Whether to only evaluate site stacks that are listed in the non-empty (full) region model. Defaults to False.

        Returns:
            Tuple[Dict[str, SiteStack], GeoDataFrame, Dict[str, SiteStack], List[str], List[str]]:
                - stacks (Dict[str, SiteStack]): The filtered site stacks, respecting the whitelist and blacklist.
                - stack_index (GeoDataFrame): The concatenated stack index, based on the stacks.
                - all_stacks (Dict[str, SiteStack]): All the site stacks, ignoring the whitelist and blacklist.
                - fully_contained_sites (List[str]): The list of IDs of sites that are fully contained within the region boundary.
                - partially_contained_sites (List[str]): The list of IDs of sites that are intersect with the region boundary.
        """

        stacks, all_stacks = {}, {}
        fully_contained_sites = []
        partially_contained_sites = []
        dataframes = []

        # remove empty strings from the lists
        whitelist = list(filter(bool, whitelist))
        blacklist = list(filter(bool, blacklist))

        for input_path in tqdm(input_paths, desc="load stacks"):
            # check for valid path
            if not os.path.isfile(input_path):
                logging.error(f"Could not load site stack, {input_path} not found.")

            # load stack as a GeoDataFrame
            df = gpd.read_file(input_path)

            # ground truth site identifiers must be listed in the non-empty region model
            if (
                rm_filter
                and region_model
                and region_model.sites_in_rm_file
                and df[df["type"] == "site"].site_id.values[0] not in region_model.sites_in_rm_file
            ):
                continue

            # version 2 of the SMART geojson annotation format (current version)
            if "type" in df:
                site = df[df["type"] == "site"].iloc[0]
                annotation_id = site["site_id"]
                originator = site["originator"]

            # version 1 of the annotation format (legacy version)
            else:
                with open(input_path) as f:
                    site = geojson.load(f)
                annotation_id = site["id"]
                originator = None

            if type(df["geometry"].iloc[0]) == Polygon or type(df["geometry"].iloc[0]) == MultiPolygon:
                stack = SiteStack(
                    df=df,
                    region_model=region_model,
                    site=site,
                    crs=crs,
                    annotation_id=annotation_id,
                    originator=originator,
                )

                # apply the temporally bounded filter
                if bounded_filter and stack.unbounded not in bounded_filter:
                    continue

                # filter the SiteStacks based on their status
                if (not whitelist or stack.status in whitelist) and (not blacklist or stack.status not in blacklist):
                    stacks[stack.id] = stack
                    dataframes.extend([slice.df for slice in stack.slices])

                all_stacks[stack.id] = stack

        # Combine the stacks
        stack_index = pd.concat(dataframes).reset_index(drop=True) if dataframes else gpd.GeoDataFrame()

        # None of the sites were in the whitelist
        if input_paths and not dataframes:
            logging.info(f"None of the stacks were in the whitelist: {whitelist}")
            return (
                stacks,
                stack_index,
                all_stacks,
                fully_contained_sites,
                partially_contained_sites,
            )

        if region_model and all_stacks:
            # Get the geometries of the stacks
            stack_union_gdf = gpd.GeoDataFrame(
                [(key, stack.base_polygon_union) for key, stack in all_stacks.items()],
                columns=["id", "geometry"],
                geometry="geometry",
            )

            # Set the CRS
            if crs:
                stack_union_gdf.set_crs(crs, inplace=True)

            # Find the stacks that intersect with the region
            stacks_within_region = gpd.sjoin(stack_union_gdf, region_model.df, how="inner", predicate="intersects")
            for i, row in stacks_within_region.iterrows():
                intersection_area = intersection(region_model.polygon, row.geometry).area
                site_area = row.geometry.area
                intersection_over_site = intersection_area / site_area

                # Stacks that are fully contained within the region
                if intersection_over_site >= 0.9999:
                    fully_contained_sites.append(row.id)
                # Stacks that overlap with the region boundary
                else:
                    partially_contained_sites.append(row.id)

            # Filter the stacks to only include the stacks that intersect with the region polygon
            stack_index = stack_index.loc[stack_index["stack"].isin(stacks_within_region["id"])].reset_index(drop=True)
            stacks = {
                stack_id: stacks[stack_id]
                for stack_id in stacks.keys()
                if stack_id in stacks_within_region["id"].tolist()
            }
            all_stacks = {
                stack_id: all_stacks[stack_id]
                for stack_id in all_stacks.keys()
                if stack_id in stacks_within_region["id"].tolist()
            }

        return (
            stacks,
            stack_index,
            all_stacks,
            fully_contained_sites,
            partially_contained_sites,
        )

    def update_gt_statuses(self, activity_type, small_site_threshold):
        """
        Updates the status of ground truth sites to ignore-type based on the given activity type, the temporal bounds compared to the region model (self.unbounded), and the small site threshold.

        Parameters:
            activity_type (str): The type of activity to consider when updating the status of the ground truth sites.
                It can be one of the following:
                - "completed": Update the status of completed sites.
                - "partialA": Update the status of partially completed sites with partial type "B" (not a typo).
                - "partialB": Update the status of partially completed sites with partial type "A" (not a typo).

            small_site_threshold (float): The threshold value to determine if a ground truth site is small and should be ignored in the evaluation.
                The value is converted from square meters to square kilometers.

        Returns:
            None
        """
        for gt_id, gt_stack in self.gt_stacks.items():
            # ignore small sites (convert small_site_threshold from square meters to square kilometers)
            if (
                gt_stack.status not in ANNOTATED_NEGATIVE_STATUS_TYPES
                and gt_stack.max_polygon_area
                and gt_stack.max_polygon_area <= small_site_threshold / 1e6
            ):
                self.gt_stacks[gt_id].status = "ignore" if "transient" not in gt_stack.status else "transient_ignore"

            # ignore partially spatially bounded sites
            # fmt: off
            elif gt_id in self.partially_contained_gt:
                self.gt_stacks[gt_id].status = "ignore" if "transient" not in gt_stack.status else "transient_ignore"
            else:
                if not gt_stack.annotated_null_start and not gt_stack.annotated_null_end:
                    self.gt_stacks[gt_id].status = (
                        gt_stack.annotated_status
                    )  # reset the effective status to the original annotated status
                if gt_stack.status in POSITIVE_COMPLETE_STATUS_TYPES:
                    if not gt_stack.unbounded:
                        if "partial" in activity_type:
                            self.gt_stacks[gt_id].status = (
                                "ignore" if "transient" not in gt_stack.status else "transient_ignore"
                            )
                    elif gt_stack.unbounded == -2:
                        self.gt_stacks[gt_id].status = (
                            "positive_unbounded" if "transient" not in gt_stack.status else "transient_ignore"
                        )
                    elif gt_stack.unbounded == -1:
                        self.gt_stacks[gt_id].status = (
                            "positive_unbounded" if "transient" not in gt_stack.status else "transient_ignore"
                        )
                    elif gt_stack.unbounded == 1:
                        if activity_type == "completed":
                            self.gt_stacks[gt_id].status = (
                                "positive_unbounded" if "transient" not in gt_stack.status else "transient_ignore"
                            )
                        elif activity_type == "partialA" and gt_stack.partial_type == "B":
                            self.gt_stacks[gt_id].status = (
                                "positive_unbounded" if "transient" not in gt_stack.status else "transient_ignore"
                            )
                        elif activity_type == "partialB" and gt_stack.partial_type == "A":
                            self.gt_stacks[gt_id].status = (
                                "ignore" if "transient" not in gt_stack.status else "transient_ignore"
                            )
                    elif gt_stack.unbounded == 2:
                        self.gt_stacks[gt_id].status = (
                            "positive_unbounded" if "transient" not in gt_stack.status else "transient_ignore"
                        )
                elif gt_stack.status in POSITIVE_PARTIAL_STATUS_TYPES:
                    if not gt_stack.unbounded:
                        if activity_type == "completed":
                            self.gt_stacks[gt_id].status = (
                                "ignore" if "transient" not in gt_stack.status else "transient_ignore"
                            )
                        elif activity_type == "partialA" and gt_stack.partial_type == "B":
                            self.gt_stacks[gt_id].status = (
                                "positive_unbounded" if "transient" not in gt_stack.status else "transient_ignore"
                            )
                        elif activity_type == "partialB" and gt_stack.partial_type == "A":
                            self.gt_stacks[gt_id].status = (
                                "ignore" if "transient" not in gt_stack.status else "transient_ignore"
                            )
                    elif gt_stack.unbounded == -2:
                        self.gt_stacks[gt_id].status = (
                            "positive_unbounded" if "transient" not in gt_stack.status else "transient_ignore"
                        )
                    elif gt_stack.unbounded == -1:
                        self.gt_stacks[gt_id].status = (
                            "positive_unbounded" if "transient" not in gt_stack.status else "transient_ignore"
                        )
                    elif gt_stack.unbounded == 1:
                        if activity_type == "completed":
                            self.gt_stacks[gt_id].status = (
                                "positive_unbounded" if "transient" not in gt_stack.status else "transient_ignore"
                            )
                        elif activity_type == "partialA" and gt_stack.partial_type == "B":
                            self.gt_stacks[gt_id].status = (
                                "positive_unbounded" if "transient" not in gt_stack.status else "transient_ignore"
                            )
                        elif activity_type == "partialB" and gt_stack.partial_type == "A":
                            self.gt_stacks[gt_id].status = (
                                "ignore" if "transient" not in gt_stack.status else "transient_ignore"
                            )
                    elif gt_stack.unbounded == 2:
                        self.gt_stacks[gt_id].status = (
                            "positive_unbounded" if "transient" not in gt_stack.status else "transient_ignore"
                        )
            # fmt: on

            # if the new status of the ground truth site is ignore, then adjust the site's activity dates accordingly
            if self.gt_stacks[gt_id].status in IGNORE_STATUS_TYPES:
                self.gt_stacks[gt_id].start_activity = gt_stack.start_date
                self.gt_stacks[gt_id].end_activity = gt_stack.end_date
                if gt_stack.start_activity and gt_stack.end_activity:
                    self.gt_stacks[gt_id].activity_dates = set(
                        pd.date_range(start=gt_stack.start_activity, end=gt_stack.end_activity)
                    )
                    self.gt_stacks[gt_id].len_activity = len(gt_stack.activity_dates)
                else:
                    self.gt_stacks[gt_id].activity_dates = set()
                    self.gt_stacks[gt_id].len_activity = None

    @classmethod
    def get_site_stack_id(cls, input_path):
        """
        Get the site stack ID from the filepath of a site stack geojson annotation file.

        This function takes an input path to a GeoJSON file and returns the site stack ID.
        The site stack ID is generated by concatenating the site ID, originator, and version
        from the properties of the first feature in the GeoJSON file.

        Parameters:
            input_path (str): The path to the input GeoJSON file.

        Returns:
            str: The site stack ID.
        """
        with open(input_path) as f:
            site_feature = geojson.load(f)["features"][0]["properties"]
        site_id = f"{site_feature['site_id']}_{site_feature['originator']}_{site_feature['version']}"

        return site_id

    @classmethod
    @timer
    def point_comparison(cls, gt_point, sm_stack):
        """
        Compares a ground truth point with a site model stack using spatial and temporal metrics.

        Parameters:
            gt_point (Point): The ground truth point to compare.
            sm_stack (SiteStack): The site model stack to compare against.

        Returns:
            dict: A dictionary containing the similarity scores for the point-polygon comparison. The keys are:
                - "min_spatial_distance": The minimum spatial distance between the point and the polygon.
                - "central_spatial_distance": The central spatial distance between the point and the polygon.
                - "max_spatial_distance": The maximum spatial distance between the point and the polygon.
                - "min_temporal_distance": The minimum temporal distance between the point and the polygon.
                - "central_temporal_distance": The central temporal distance between the point and the polygon.
                - "max_temporal_distance": The maximum temporal distance between the point and the polygon.

        """
        scores = {}
        try:
            with warnings.catch_warnings():
                (
                    scores["min_spatial_distance"],
                    scores["central_spatial_distance"],
                    scores["max_spatial_distance"],
                ) = Metric.calc_spatial_point_metrics(sm_stack.polygon_union, gt_point.coordinates)
                (
                    scores["min_temporal_distance"],
                    scores["central_temporal_distance"],
                    scores["max_temporal_distance"],
                ) = Metric.calc_temporal_point_metrics(sm_stack.activity_dates, gt_point.point_date)
        except Exception as e:
            logging.error(f"Exception comparing point {gt_point.id} with polygon {sm_stack.id}: {e}")
            # default to very high distances so that the polygon will not associate with the proposal
            (
                scores["min_spatial_distance"],
                scores["central_spatial_distance"],
                scores["max_spatial_distance"],
            ) = (1e4, 1e4, 1e4)
            (
                scores["min_temporal_distance"],
                scores["central_temporal_distance"],
                scores["max_temporal_distance"],
            ) = (1e4, 1e4, 1e4)

        return scores

    @classmethod
    @timer
    def stack_comparison(cls, gt_stack, sm_stack, check_unary_union=False):
        """
        Compares a ground truth stack with a site model stack by iterating through each slice of the ground truth stack and calculating the intersection over union (IoU) similarity score.

        Parameters:
            gt_stack (SiteStack): The ground truth stack to compare against.
            sm_stack (SiteStack): The site model stack to compare.
            check_unary_union (bool, optional): Flag to indicate whether to check if there is any intersection between the unary unions of the gt_stack and the sm_stack. Defaults to False.

        Returns:
            pandas.DataFrame: A DataFrame containing the comparison results, including the ground truth and site model slice UUIDs, dates, phases, sources, IoU scores, intersection geometries, union geometries, and intersection and union areas.
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

        # quick check for zero intersection
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
                            (
                                score,
                                intersection_area,
                                intersection,
                                union_area,
                                union,
                            ) = Metric.calc_iou(gt_slice.df, sm_slice.df)
                    except Exception as e:
                        logging.error(f"Exception comparing {gt_slice.id} vs. {sm_slice.id}")
                        logging.error(e)
                        score, intersection_area, intersection, union_area, union = (
                            0,
                            0,
                            None,
                            0,
                            None,
                        )

                # no corresponding slice from the site model stack was found
                else:
                    score, intersection_area, intersection, union_area, union = (
                        0,
                        0,
                        None,
                        0,
                        None,
                    )

                # save results
                gt_uuids.append(gt_slice.uuid)
                sm_uuids.append(sm_slice.uuid if sm_slice else None)
                scores.append(score)
                intersection_areas.append(intersection_area)
                intersections.append(intersection)
                union_areas.append(union_area)
                unions.append(union)
                iot_scores.append(
                    0 if not intersection_area else Metric.calc_iot(gt_slice.df, sm_slice.df, intersection_area)[0]
                )
                iop_scores.append(
                    0 if not intersection_area else Metric.calc_iot(sm_slice.df, gt_slice.df, intersection_area)[0]
                )

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
        df["proposal date"] = [
            date if type(date) != pd._libs.tslibs.nattype.NaTType else "n/a" for date in df["proposal date"].dt.date
        ]
        df["proposal source"] = [sm_slice.source if sm_slice else "n/a" for sm_slice in matched_sm_slices]
        df["iou"] = scores
        df["iot"] = iot_scores
        df["iop"] = iop_scores
        df["intersection_geometry"] = [
            (intersection.iloc[0].geometry.wkt if intersection is not None and not intersection.empty else None)
            for intersection in intersections
        ]
        df["intersection_area"] = intersection_areas
        df["union_geometry"] = [union.wkt if union else None for union in unions]
        df["union_area"] = union_areas

        # choose the best slice if there are multiple ground truth observations on the same date
        df = df.sort_values(by=["date", "iou", "source"])
        df = df.drop_duplicates(subset=["date"], keep="last")

        # a comparison table aligning the stack slices by date, with similarity scores for each pair of slices
        return df

    @classmethod
    @timer
    def score_point(cls, gt_point, sm_stack):
        """
        Retrieves / calculates the metric results for a point vs. stack comparison pair

        Parameters:
            gt_point (Point): The ground truth point to compare against.
            sm_stack (SiteModelStack): The site model stack to compare.

        Returns:
            Tuple[str, str, dict]: A tuple containing the IDs of the ground truth point and the site model stack,
            and a dictionary of metric scores.
        """
        logging.debug(
            f"Calculating metrics for {gt_point.id} vs. {sm_stack.id} - RAM Used: {psutil.virtual_memory().percent}"
        )
        scores = Evaluation.point_comparison(gt_point, sm_stack)

        return gt_point.id, sm_stack.id, scores

    @classmethod
    @timer
    def score_stack(cls, gt_stack, sm_stack):
        """
        Retrieves / calculates the comparison table for a pair of stacks

        Parameters:
            gt_stack (SiteStack): The ground truth stack to compare.
            sm_stack (SiteStack): The site model stack to compare against.

        Returns:
            tuple: A tuple containing the IDs of the ground truth stack and the site model stack, and a DataFrame with the comparison results.
        """
        logging.debug(
            f"Calculating metrics for {gt_stack.id} vs. {sm_stack.id} - RAM Used: {psutil.virtual_memory().percent}"
        )
        df = Evaluation.stack_comparison(gt_stack, sm_stack)

        return (gt_stack.id, sm_stack.id, df)

    @timer
    def save_mp_results(self, args):
        """
        Saves the multiprocessing queue results by putting the given arguments into the queue. The arguments are the tuple returned by the segment_sites() function.

        Parameters:
            args (tuple): A tuple returned by the segment_sites() function, containing the ground truth ID, a list of the intersecting site model proposals, and a list of the corresponding dataframes.

        Returns:
            None
        """
        self.queue.put(args)
        gt_id, _, dataframes = args
        with self.lock:
            self.counter += 1
            print(f"\t{self.counter}/{Evaluation.total_truth_sites} site comparisons completed")

    @classmethod
    def get_sm_stack_id(cls, sm_stacks):
        """
        Generate a unique identifier for a set of site model stacks.

        Parameters:
            sm_stacks (List[SiteStack]): A list of site model stacks.

        Returns:
            str: A string representing the unique identifier for the set of site model stacks (the combination of their individual site IDs).
        """
        return "_".join(sorted([str(stack.id) for stack in sm_stacks]))

    @classmethod
    @timer
    def segment_sites(cls, gt_stack, all_sm_stacks, tau, rho, confidence_score_thresholds):
        """
        Segments a list of proposed site models based on an intersecting ground truth site, a set of confidence score thresholds to filter the site models, an association threshold (tau), and a detection threshold (rho).
        Compares each ground truth site to each of the individual intersecting site model proposals and the various combinations of those oversegmented site models.

        Parameters:
            gt_stack (SiteStack): The ground truth site stack object.
            all_sm_stacks (List[SiteStack]): A list of intersecting site model site stack objects.
            tau (float): The association threshold.
            rho (float): The detection threshold.
            confidence_score_thresholds (List[float]): The list of confidence score thresholds to filter the proposed site models.

        Returns:
            tuple: A tuple containing the ground truth site ID (str), a list of site model stack objects (List[SiteStack]), and a list of comparison tables (List[DataFrame]).
        """

        # initialize the return tuple
        results = (gt_stack.id, [], [])

        proposal_cache = {}

        # filter the proposed site models based on the confidence score threshold
        for confidence_score_threshold in confidence_score_thresholds:
            sm_stacks = [sm_stack for sm_stack in all_sm_stacks if sm_stack.score >= confidence_score_threshold]

            # the truth site has no intersecting site models
            if len(sm_stacks) == 0:
                logging.debug(
                    f"No intersecting site models for {gt_stack.id} at confidence >= {confidence_score_threshold}"
                )
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
                _, _, df = Evaluation.score_stack(gt_stack, sm_stack)
                # save the comparison
                results[1].append(sm_stack)
                results[2].append(df)
                proposal_cache[sm_stack.id] = df
            scores = df["iou"]
            # the proportion of truth site observations that are above the association threshold
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
                    _, _, df = Evaluation.score_stack(gt_stack, sm_stack)
                    results[1].append(sm_stack)
                    results[2].append(df)
                    proposal_cache[sm_stack.id] = df
                scores = df["iou"]
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
                    _, _, df = Evaluation.score_stack(gt_stack, sm_stack)
                    # save the results
                    results[1].append(sm_stack)
                    results[2].append(df)
                    proposal_cache[sm_stack.id] = df
                scores = df["iou"]
                detection_score = len(list(filter(lambda x: x >= tau, scores))) / len(scores) if len(scores) > 0 else 0
                detection_scores.append((sm_stack, detection_score))

                # remove the site model with the lowest score in case another iteration is necessary
                remaining_stacks.pop(0)

        return results

    @timer
    def compare_points(self):
        """
        Compares site stacks with site points
        1. Prefilters on the maximimum min_spatial_distance threshold.
        2. Computes point-stack comparison metrics.
        3. Updates the nested dictionary (self.point_comparisons) with a dictionary of metrics for each gt -> sm prefiltered pair.
            {ground truth site name: {site model name: {spatial/temporal distance metric name: value}}}
        """
        logging.info("Comparing site points...")

        # Calculates the maximum buffer distance from the minimum spatial distances for prefiltering.
        buffer_distance = max(self.min_spatial_distances)

        # Creates a GeoDataFrame from the site models' polygon union and sets the CRS.
        sm_stack_union_gdf = gpd.GeoDataFrame(
            [(key, stack.polygon_union) for key, stack in self.sm_stacks.items()],
            columns=["id", "geometry"],
            geometry="geometry",
        ).set_crs(self.gt_points_gdf.crs)

        # Projects the geometry of the proposals to a new coordinate system.
        sm_stack_union_gdf["geometry_projected"] = sm_stack_union_gdf.geometry.apply(Metric.project_geometry)

        # Projects the geometry of the ground truth points to the same coordinate system.
        self.gt_points_gdf["geometry_projected"] = self.gt_points_gdf.geometry.apply(Metric.project_geometry)

        # Sets the new projected geometry as the main geometry for both the GeoDataFrame and the ground truth points.
        sm_stack_union_gdf = sm_stack_union_gdf.set_geometry("geometry_projected")
        self.gt_points_gdf = self.gt_points_gdf.set_geometry("geometry_projected")

        # Buffers the ground truth points by the calculated buffer distance and sets the buffer as the main geometry.
        self.gt_points_gdf["buffered"] = self.gt_points_gdf.geometry.buffer(buffer_distance)
        self.gt_points_gdf.set_geometry("buffered", inplace=True)

        # Performs a spatial join between the GeoDataFrame and the buffered ground truth points, keeping only the intersecting points.
        points_within_polygon = (
            gpd.sjoin(
                sm_stack_union_gdf,
                self.gt_points_gdf,
                how="inner",
                predicate="intersects",
            )
            .drop(columns=["index_right"])
            .reset_index(drop=True)
            .rename(columns={"id": "sm_id", "site_id": "gt_id"})
        )

        # Iterates over each row in the resulting DataFrame
        for index, row in points_within_polygon.iterrows():
            gt_id = row["gt_id"]
            sm_id = row["sm_id"]
            gt_point = self.gt_points[gt_id]
            sm_stack = self.sm_stacks[sm_id]
            # Scores the point-site model pair and stores the scores in the point_comparisons dictionary.
            _, _, scores = self.score_point(gt_point, sm_stack)
            self.point_comparisons[gt_id][sm_id] = scores

    @timer
    def compare_stacks(self):
        """

        1. Compares each truth site stack with its intersecting site model(s), if any
        2. If a truth site intersects with multiple site models, attempts to match all of them by combining them into a single stack
        3. If the comparison score between the truth site and the site model union fails to exceed the detection threshold,
            removes the site model with the lowest score from the union and retries the matching
        4. Updates the nested dictionary of comparison tables for each pair of site stacks (self.stack_comparisons)
            {ground truth site name: {site model name: comparison table}}

        Parameters:
            None

        Returns:
            None
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

        # initial filtering to remove pairs in the format (ground truth, proposal) that have no spatial intersection
        if True:
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
                    pair_dict[self.gt_stack_gdf.iloc[gt_idx]["stack"]].update(
                        [
                            sm_id
                            for sm_id in sm_ids
                            if self.sm_stacks[sm_id].start_date <= self.gt_stacks[gt_id].end_activity
                            and self.sm_stacks[sm_id].end_date >= self.gt_stacks[gt_id].start_activity
                        ]
                    )
                else:
                    pair_dict[self.gt_stack_gdf.iloc[gt_idx]["stack"]].update(
                        [
                            sm_id
                            for sm_id in sm_ids
                            if self.sm_stacks[sm_id].start_date <= self.gt_stacks[gt_id].end_date
                            and self.sm_stacks[sm_id].end_date >= self.gt_stacks[gt_id].start_date
                        ]
                    )
        else:
            for gt_id in self.gt_stacks:
                pair_dict[gt_id] = set(
                    [
                        sm_id
                        for sm_id in self.sm_stacks
                        if self.sm_stacks[sm_id].start_date <= self.gt_stacks[gt_id].end_activity
                        and self.sm_stacks[sm_id].end_date >= self.gt_stacks[gt_id].start_activity
                    ]
                )
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
                args = (
                    gt_stack,
                    stacks_to_segment,
                    1,
                    1,
                    self.confidence_score_thresholds,
                )
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
                gt_id, sm_stacks, dataframes = Evaluation.segment_sites(
                    gt_stack, stacks_to_segment, 1, 1, self.confidence_score_thresholds
                )
                for sm_stack, df in zip(sm_stacks, dataframes):
                    self.stack_comparisons[gt_id][sm_stack.id] = df
                    if sm_stack.id not in self.sm_stacks:
                        self.sm_stacks[sm_stack.id] = sm_stack
                    if sm_stack.id not in sm_ids:
                        combined_stacks.append(sm_stack)
                if dataframes:
                    serial_counter += 1
                    print(f"\t{serial_counter}/{Evaluation.comparable_truth_sites} site comparisons completed")

    def get_gt_color(self, gt_site_name, simple):
        """
        Get the color associated with a ground truth site, based on its status and whether it was detected by a proposal.

        Parameters:
            gt_site_name (str): The ID of the ground truth site.
            simple (bool): If True, returns the main color associated with the site's status.

        Returns:
            str: The color associated with the ground truth site.

        """
        gt_color = None
        gt_stack = self.gt_sites[gt_site_name]

        # a detected truth site
        if self.detections.get(gt_site_name):
            if gt_stack.status in POSITIVE_STATUS_TYPES:
                gt_color = "lime"
            elif gt_stack.status in NEGATIVE_STATUS_TYPES:
                gt_color = "red"
        # a missed truth site
        else:
            if gt_stack.status in POSITIVE_STATUS_TYPES:
                gt_color = "black"

        if simple:
            return gt_color

        if gt_stack.status in POSITIVE_UNBOUNDED_STATUS_TYPES:
            gt_color = "thistle"
        elif gt_stack.status in ANNOTATED_IGNORE_STATUS_TYPES:
            gt_color = "salmon"
        elif gt_stack.status in ["seen", "train"]:
            gt_color = "gray"

        return gt_color

    def get_sm_color(self, matches, simple):
        """
        Get the color associated with a proposed site model, based on its status and whether it detected a truth site.

        Parameters:
            matches (list): A list of strings representing the IDs of the ground truth sites that were matched with the proposed site model.
            simple (bool): If True, returns the main color associated with proposed site model.

        Returns:
            str: The color associated with the proposed site model.

        """
        sm_color = None

        # no matches
        if not matches:
            sm_color = "magenta"

        if simple:
            return sm_color

        # the list of statuses of the detected truth sites
        match_statuses = [self.gt_sites[match].status for match in matches]
        # at least 1 positive detection
        if set(match_statuses) & set(POSITIVE_STATUS_TYPES):
            # and at least 1 negative detection (partially wrong)
            if set(match_statuses) & set(NEGATIVE_STATUS_TYPES):
                sm_color = "orange"
            else:
                sm_color = "aquamarine"
        # only negative detections (completely wrong)
        elif set(match_statuses) & set(NEGATIVE_STATUS_TYPES):
            sm_color = "magenta"
        elif set(match_statuses) & set(IGNORE_STATUS_TYPES) or set(match_statuses) & set(
            POSITIVE_UNBOUNDED_STATUS_TYPES
        ):
            sm_color = "darkened_coral"

        return sm_color

    @timer
    def visualize_region(self, alpha=0.8, dst_crs=None, simple=True, background_img=None):
        """
        Visualizes a region by plotting the region model and the site models on a map.

        Parameters:
            alpha (float): The transparency of the region model and associated geometries on the map.
            dst_crs (str): The coordinate reference system (CRS) of the map.
            simple (bool): If True, only plots the main color associated with each site.
            background_img (str): The path to the background image.

        Returns:
            None
        """
        if not self.region_model:
            logging.warning("Specify a region model file in order to visualize the region.")
            return
        logging.info("Visualizing region...")

        region_name = self.region_model.id if self.region_model else "Region"

        fig, ax = plt.subplots(ncols=1, nrows=1, figsize=(25, 25))

        if background_img:
            # create the CRS
            with rasterio.open(background_img) as f:
                dst_crs = str(f.crs).lower() if f.crs else None
        else:
            dst_crs = None

        if not dst_crs:  # don't plot the background image if it doesn't have a CRS
            dst_crs = (
                str(self.region_model.df.crs).lower() if self.region_model else "epsg:4326"
            )  # fix CRS to that of region
            background_img = None  # null it out for plotting

        if background_img:  # plot the image if it exists with a useful CRS
            with rasterio.open(background_img) as f:
                rasterio.plot.show(f, ax=ax, alpha=alpha)
        else:
            logging.info(
                "Plotting without a background image (it was either unspecified or didn't have an associated CRS)"
            )

        # Create KML object
        kml = simplekml.Kml(
            name=f'{"Simple" if simple else "Detailed"} Region Visualization for {region_name}',
            open=1,
        )
        gt_true_pos_folder = kml.newfolder(name="(Annotation) True Positive")
        gt_false_neg_folder = kml.newfolder(name="(Annotation) False Negative")
        gt_false_pos_neg_gt_folder = kml.newfolder(name="(Annotation) False Positive Negative GT Association")
        gt_unbounded_folder = kml.newfolder(name="(Annotation) Unbounded GT Site (counted as 'Ignore GT Site')")
        gt_ignore_folder = kml.newfolder(name="(Annotation) Ignore")
        prop_false_pos_no_gt_folder = kml.newfolder(name="(Proposal) False Positive No GT Association")
        prop_true_pos_folder = kml.newfolder(name="(Proposal) True Positive")
        prop_partial_folder = kml.newfolder(name="(Proposal) Partial Positive")
        prop_assoc_ignore_folder = kml.newfolder(name="(Proposal) Association with Ignore or Unbounded GT Site")

        kml_colormap = {
            "lime": {
                "color_rgb": (42, 255, 0),  # (Annotation) True Positive
                "kml_folder": gt_true_pos_folder,
            },
            "black": {
                "color_rgb": (0, 0, 0),  # (Annotation) False Negative
                "kml_folder": gt_false_neg_folder,
            },
            "red": {
                "color_rgb": (
                    255,
                    0,
                    0,
                ),  # (Annotation) False Positive Negative GT Association
                "kml_folder": gt_false_pos_neg_gt_folder,
            },
            "thistle": {
                "color_rgb": (202, 167, 255),  # (Annotation) Unbounded
                "kml_folder": gt_unbounded_folder,
            },
            "salmon": {
                "color_rgb": (255, 134, 134),  # (Annotation) Ignore
                "kml_folder": gt_ignore_folder,
            },
            "magenta": {
                "color_rgb": (
                    213,
                    63,
                    255,
                ),  # (Proposal) False Positive No GT Association,
                "kml_folder": prop_false_pos_no_gt_folder,
            },
            "orange": {
                "color_rgb": (255, 144, 51),  # (Proposal) Partial
                "kml_folder": prop_partial_folder,
            },
            "aquamarine": {
                "color_rgb": (51, 255, 239),  # (Proposal) True Positive
                "kml_folder": prop_true_pos_folder,
            },
            "darkened_coral": {
                "color_rgb": (
                    190,
                    93,
                    57,
                ),  # (Proposal) Association with Ignore or Unbounded GT Site
                "kml_folder": prop_assoc_ignore_folder,
            },
        }

        # Add region model bounds
        region_folder = kml.newfolder(name="Region Bounds")
        region_bound_pol = region_folder.newpolygon(
            name=region_name, outerboundaryis=self.region_model.df.boundary[0].coords
        )
        region_bound_pol.style.linestyle.color = simplekml.Color.yellow
        region_bound_pol.linestyle.width = 4
        region_bound_pol.style.polystyle.fill = 0

        # Plot ground truth geometries
        gt_geoms = self.gt_points if len(self.gt_stacks) == 0 else self.gt_stacks
        for gt_geom_name, gt_geom in tqdm(gt_geoms.items()):
            gt_color = self.get_gt_color(gt_geom_name, simple)
            if gt_color in kml_colormap.keys():
                if isinstance(gt_geom, SitePoint):
                    ax.scatter(
                        *gt_geom.coordinates.xy,
                        c=[[c / 255 for c in kml_colormap[gt_color]["color_rgb"]]],
                        alpha=1,
                    )
                else:
                    crs_gt_stack = gt_geom.df.to_crs(dst_crs)
                    gt_stack_polys = crs_gt_stack.geometry
                    bound_poly = unary_union(gt_stack_polys)
                    ax.fill(
                        *bound_poly.exterior.xy,
                        alpha=1,
                        fc="none",
                        ec=[c / 255 for c in kml_colormap[gt_color]["color_rgb"]],
                    )

                folder = kml_colormap[gt_color]["kml_folder"]
                if isinstance(gt_geom, SitePoint):
                    kml_geom = folder.newpoint(name=gt_geom_name, coords=gt_geom.coordinates.coords)
                    # Styling
                    kml_geom.style.iconstyle.color = simplekml.Color.rgb(*kml_colormap[gt_color]["color_rgb"])
                    kml_geom.style.labelstyle.color = simplekml.Color.rgb(*kml_colormap[gt_color]["color_rgb"])
                else:
                    kml_geom = folder.newpolygon(
                        name=gt_geom_name,
                        outerboundaryis=unary_union(gt_geom.df.geometry).exterior.coords,
                    )
                    # Styling
                    kml_geom.style.linestyle.color = simplekml.Color.rgb(*kml_colormap[gt_color]["color_rgb"])
                    kml_geom.linestyle.width = 4
                    kml_geom.style.polystyle.fill = 0

                # Auxiliary info
                conf_score = gt_geom.score
                start_date = gt_geom.start_date
                end_date = gt_geom.end_date
                start_activity = gt_geom.start_activity
                end_activity = gt_geom.end_activity
                desc_str = (
                    f"<div style='width:250px;'>"
                    f"<h4>{gt_geom_name}</h4>"
                    f"<b>Site Type</b>: {folder.name}<br>"
                    f"<b>Start Date</b>: {start_date}<br>"
                    f"<b>End Date</b>: {end_date}<br>"
                    f"<b>Start Activity</b>: {start_activity}<br>"
                    f"<b>End Activity</b>: {end_activity}<br>"
                )
                if isinstance(gt_geom, SiteStack):
                    first_obs = gt_geom.first_obs
                    last_obs = gt_geom.last_obs
                    union_area = GeometryUtil.compute_region_area(bound_poly)
                    max_poly_area = gt_geom.max_polygon_area
                    desc_str += (
                        f"<b>Union Area (m<sup>2</sup>)</b>: {union_area}<br>"
                        f"<b>Max Area (m<sup>2</sup>)</b>: {max_poly_area}<br>"
                        f"<b>Confidence Score</b>: {conf_score}<br>"
                        f"</div>"
                    )
                else:
                    desc_str += f"<b>Confidence Score</b>: {conf_score}<br>" "</div>"
                kml_geom.description = desc_str

        # Plot proposal geometries
        for sm_id, matches in tqdm(self.proposals.items()):
            sm_stack = self.sm_stacks[sm_id]
            sm_color = self.get_sm_color(matches, simple)
            if sm_color in kml_colormap.keys():
                if sm_stack.df is not None:
                    crs_sm_stack = sm_stack.df.to_crs(dst_crs)
                    sm_stack_polys = crs_sm_stack.geometry
                    bound_poly = unary_union(sm_stack_polys)

                    ax.fill(
                        *bound_poly.exterior.xy,
                        alpha=1,
                        fc="none",
                        ec=[c / 255 for c in kml_colormap[sm_color]["color_rgb"]],
                    )

                    folder = kml_colormap[sm_color]["kml_folder"]
                    kml_geom = folder.newpolygon(
                        name=sm_id,
                        outerboundaryis=unary_union(sm_stack.df.geometry).exterior.coords,
                    )

                    # Auxiliary info
                    union_area = GeometryUtil.compute_region_area(bound_poly)
                    max_poly_area = sm_stack.max_polygon_area
                    conf_score = sm_stack.score
                    start_date = sm_stack.start_date
                    end_date = sm_stack.end_date
                    start_activity = sm_stack.start_activity
                    end_activity = sm_stack.end_activity
                    first_obs = sm_stack.first_obs
                    last_obs = sm_stack.last_obs
                    kml_geom.description = (
                        f"<div style='width:250px;'>"
                        f"<h4>{sm_id}</h4>"
                        f"<b>Site Type</b>: {folder.name}<br>"
                        f"<b>Start Date</b>: {start_date}<br>"
                        f"<b>End Date</b>: {end_date}<br>"
                        f"<b>Start Activity</b>: {start_activity}<br>"
                        f"<b>End Activity</b>: {end_activity}<br>"
                        f"<b>First Obs Date</b>: {first_obs}<br>"
                        f"<b>Last Obs Date</b>: {last_obs}<br>"
                        f"<b>Union Area (m<sup>2</sup>)</b>: {union_area}<br>"
                        f"<b>Max Area (m<sup>2</sup>)</b>: {max_poly_area}<br>"
                        f"<b>Confidence Score</b>: {conf_score}<br>"
                        f"</div>"
                    )

                    # Styling
                    kml_geom.style.linestyle.color = simplekml.Color.rgb(*kml_colormap[sm_color]["color_rgb"])
                    kml_geom.linestyle.width = 4
                    kml_geom.style.polystyle.fill = 0

        # zoom to region model
        if self.region_model:
            xlim = (
                self.region_model.df.to_crs(dst_crs).total_bounds[0],
                self.region_model.df.to_crs(dst_crs).total_bounds[2],
            )
            ylim = (
                self.region_model.df.to_crs(dst_crs).total_bounds[1],
                self.region_model.df.to_crs(dst_crs).total_bounds[3],
            )
            self.region_model.df.to_crs(dst_crs).boundary.plot(
                ax=ax, color="yellow", linewidth=7, ls="dashed", aspect=1
            )

        # zoom to polygons
        else:
            xlim = (
                min(
                    self.gt_stack_gdf.to_crs(dst_crs).total_bounds[0],
                    self.sm_stack_gdf.to_crs(dst_crs).total_bounds[0],
                ),
                max(
                    self.gt_stack_gdf.to_crs(dst_crs).total_bounds[2],
                    self.sm_stack_gdf.to_crs(dst_crs).total_bounds[2],
                ),
            )
            ylim = (
                min(
                    self.gt_stack_gdf.to_crs(dst_crs).total_bounds[1],
                    self.sm_stack_gdf.to_crs(dst_crs).total_bounds[1],
                ),
                max(
                    self.gt_stack_gdf.to_crs(dst_crs).total_bounds[3],
                    self.sm_stack_gdf.to_crs(dst_crs).total_bounds[3],
                ),
            )
            xbuffer = 0  # (xlim[1] - xlim[0]) * 0.05
            ybuffer = 0  # (ylim[1] - ylim[0]) * 0.05
            xlim = (xlim[0] - xbuffer, xlim[1] + xbuffer)
            ylim = (ylim[0] - ybuffer, ylim[1] + ybuffer)

        # zoom to limits
        xbuffer = (xlim[1] - xlim[0]) * 0.05
        ybuffer = (ylim[1] - ylim[0]) * 0.05
        xlim = (xlim[0] - xbuffer, xlim[1] + xbuffer)
        ylim = (ylim[0] - ybuffer, ylim[1] + ybuffer)
        ax.set_xlim(xlim)
        ax.set_ylim(ylim)
        ax.xaxis.set_visible(False)
        ax.yaxis.set_visible(False)

        # save to file
        title = f"{region_name}"
        if not simple:
            title += "_detailed"
        ax.set_title(f"{title}")
        if self.bas_dir:
            os.makedirs(f"{self.bas_dir}/region", exist_ok=True)
            filename = f"{self.bas_dir}/region/{title}"
            fig.savefig(f"{filename}.png", bbox_inches="tight", dpi=60)
            kml.save(f"{filename}.kml")

        plt.close()

    @timer
    def create_failed_associations_table(
        self,
        failed_associations,
        proposals,
        tau,
        rho,
        tiop,
        tiot,
        ttiop,
        ttiot,
        min_proposal_area,
        min_score,
        min_spatial_distance,
        central_spatial_distance,
        max_spatial_distance,
        min_temporal_distance,
        central_temporal_distance,
        max_temporal_distance,
        site_types,
        comparing_points,
        save_output=True,
    ):
        """
        Creates a table of the "failed associations" between the ground truth sites and the proposals, for the given threshold parameters. Failed associations have nonzero spatial and temporal overlap, but do not meet the association thresholds, or are suboptimal.

        Returns:
            - failed_associations_df (pandas.DataFrame): a table of the failed associations
        """

        # create failed associations table
        failed_associations_df = pd.DataFrame()
        failed_associations_df["site type"] = [
            self.gt_sites[failed_association_dict["gt_id"]].status for failed_association_dict in failed_associations
        ]
        failed_associations_df["truth site"] = [
            failed_association_dict["gt_id"] for failed_association_dict in failed_associations
        ]
        failed_associations_df["proposal site"] = [
            failed_association_dict["sm_id"] for failed_association_dict in failed_associations
        ]
        failed_associations_df["spatial overlap"] = [
            failed_association_dict.get("spatial_overlap", None) for failed_association_dict in failed_associations
        ]
        failed_associations_df["temporal iot"] = [
            failed_association_dict.get("tiot", None) for failed_association_dict in failed_associations
        ]
        failed_associations_df["temporal iop"] = [
            failed_association_dict.get("tiop", None) for failed_association_dict in failed_associations
        ]
        failed_associations_df["min spatial distance"] = [
            failed_association_dict.get("min_spatial_distance", None) for failed_association_dict in failed_associations
        ]
        failed_associations_df["central spatial distance"] = [
            failed_association_dict.get("central_spatial_distance", None)
            for failed_association_dict in failed_associations
        ]
        failed_associations_df["max spatial distance"] = [
            failed_association_dict.get("max_spatial_distance", None) for failed_association_dict in failed_associations
        ]
        failed_associations_df["min temporal distance"] = [
            failed_association_dict.get("min_temporal_distance", None)
            for failed_association_dict in failed_associations
        ]
        failed_associations_df["central temporal distance"] = [
            failed_association_dict.get("central_temporal_distance", None)
            for failed_association_dict in failed_associations
        ]
        failed_associations_df["max temporal distance"] = [
            failed_association_dict.get("max_temporal_distance", None)
            for failed_association_dict in failed_associations
        ]
        failed_associations_df["truth activity start date"] = [
            self.gt_sites[failed_association_dict["gt_id"]].start_activity
            for failed_association_dict in failed_associations
        ]
        failed_associations_df["truth activity end date"] = [
            self.gt_sites[failed_association_dict["gt_id"]].end_activity
            for failed_association_dict in failed_associations
        ]
        failed_associations_df["proposal activity start date"] = [
            self.sm_stacks[failed_association_dict["sm_id"]].start_activity
            for failed_association_dict in failed_associations
        ]
        failed_associations_df["proposal activity end date"] = [
            self.sm_stacks[failed_association_dict["sm_id"]].end_activity
            for failed_association_dict in failed_associations
        ]
        failed_associations_df["model type"] = [
            "point" if comparing_points else "stack" for failed_association_dict in failed_associations
        ]
        failed_associations_df.sort_values("site type", inplace=True, ignore_index=True)

        # add thresholds to the table
        failed_associations_df_raw = failed_associations_df.copy(deep=True)
        failed_associations_df_raw["rho"] = rho
        failed_associations_df_raw["tau"] = tau
        failed_associations_df_raw["min area"] = min_proposal_area
        failed_associations_df_raw["min score"] = min_score
        failed_associations_df_raw["temporal iop"] = tiop
        failed_associations_df_raw["temporal iot"] = tiot
        failed_associations_df_raw["transient temporal iop"] = ttiop
        failed_associations_df_raw["transient temporal iot"] = ttiot
        failed_associations_df_raw["min spatial distance threshold"] = min_spatial_distance
        failed_associations_df_raw["central spatial distance threshold"] = central_spatial_distance
        failed_associations_df_raw["max spatial distance threshold"] = max_spatial_distance
        failed_associations_df_raw["min temporal distance threshold"] = min_temporal_distance
        failed_associations_df_raw["central temporal distance threshold"] = central_temporal_distance
        failed_associations_df_raw["max temporal distance threshold"] = max_temporal_distance

        # save to file
        if self.bas_dir and save_output:
            # point-based evaluation
            if self.gt_points:
                threshold_str = f"minArea={min_proposal_area}_minScore={min_score}_minSp={min_spatial_distance}_cenSp={central_spatial_distance}_maxSp={max_spatial_distance}_minTem={min_temporal_distance}_cenTem={central_temporal_distance}_maxTem={max_temporal_distance}"
            # polygon-based evaluation
            else:
                threshold_str = f"minArea={min_proposal_area}_minScore={min_score}_tau={tau}_rho={rho}_tiop={tiop}_tiot={tiot}_ttiop={ttiop}_ttiot={ttiot}"

            failed_associations_df = Evaluation.sanitize_dataframe(
                failed_associations_df, self.region_model.id, self.sequestered_id
            )
            failed_associations_df = (
                failed_associations_df.sort_values(by=["truth site", "proposal site"])
                if "truth site" in failed_associations_df.columns and "proposal site" in failed_associations_df.columns
                else failed_associations_df
            )
            failed_associations_df.to_csv(f"{self.bas_dir}/failAssoc_{threshold_str}.csv", index=False)

        return failed_associations_df_raw

    @timer
    def create_detections_table(
        self,
        detections,
        proposals,
        tau,
        rho,
        tiop,
        tiot,
        ttiop,
        ttiot,
        min_proposal_area,
        min_score,
        min_spatial_distance,
        central_spatial_distance,
        max_spatial_distance,
        min_temporal_distance,
        central_temporal_distance,
        max_temporal_distance,
        site_types,
        comparing_points,
        save_output=True,
    ):
        """
        Creates a detections table, a proposals table, and a site types table.
        The detections table lists each of the ground truth sites and any proposal(s) that detected them, for the given threshold parameters.
        Inversely, The proposal table lists each of the proposals and any ground truth site(s) that they detected, for the given threshold parameters.
        The site types table lists each of the site types and the number of sites of that type that were detected for the given threshold parameters.

        Returns:
            - a pandas DataFrame of the detections table
            - a pandas DataFrame of the proposals table
            - a pandas DataFrame of the site types table
        """

        # create detections table
        detections_df = pd.DataFrame()
        detections_df["site type"] = [self.gt_sites[gt_id].status for gt_id in detections]
        detections_df["truth site"] = detections.keys()
        detections_df["site area"] = [self.gt_sites[gt_id].area for gt_id in detections]
        (
            matched_site_models_list,
            detection_score_list,
            spatial_overlap_list,
            tiot_list,
            tiop_list,
            min_spatial_distance_list,
            central_spatial_distance_list,
            max_spatial_distance_list,
            min_temporal_distance_list,
            central_temporal_distance_list,
            max_temporal_distance_list,
            model_type_list,
        ) = ([], [], [], [], [], [], [], [], [], [], [], [])

        # find optimal associations
        for dictionaries in detections.values():
            if comparing_points:
                best_dictionary = (
                    min(
                        dictionaries,
                        key=lambda x: (
                            x["min_spatial_distance"],
                            x["max_spatial_distance"],
                        ),
                    )
                    if len(dictionaries) > 0
                    else {}
                )
                matched_site_models_list.append(
                    [
                        site
                        for sites in [
                            self.sm_stacks[dictionary["sm_id"]].sites
                            for dictionary in sorted(
                                dictionaries,
                                key=lambda x: (
                                    x["min_spatial_distance"],
                                    x["max_spatial_distance"],
                                ),
                            )
                        ]
                        for site in sites
                    ]
                )
            else:
                best_dictionary = (
                    max(
                        dictionaries,
                        key=lambda x: (
                            len(self.sm_stacks[x["sm_id"]].sites),
                            x["spatial_overlap"],
                            x["sm_id"],
                        ),
                    )
                    if len(dictionaries) > 0
                    else {}
                )
                matched_site_models_list.append(
                    self.sm_stacks[best_dictionary["sm_id"]].sites if len(best_dictionary) else []
                )
            detection_score_list.append(
                best_dictionary.get("detection_score", None)
            )  # detection_score is deprecated, and has been replaced with spatial_overlap
            spatial_overlap_list.append(best_dictionary.get("spatial_overlap", None))
            tiot_list.append(best_dictionary.get("tiot", None))
            tiop_list.append(best_dictionary.get("tiop", None))
            min_spatial_distance_list.append(best_dictionary.get("min_spatial_distance", None))
            central_spatial_distance_list.append(best_dictionary.get("central_spatial_distance", None))
            max_spatial_distance_list.append(best_dictionary.get("max_spatial_distance", None))
            min_temporal_distance_list.append(best_dictionary.get("min_temporal_distance", None))
            central_temporal_distance_list.append(best_dictionary.get("central_temporal_distance", None))
            max_temporal_distance_list.append(best_dictionary.get("max_temporal_distance", None))
            model_type_list.append("point" if comparing_points else "stack")

        detections_df["matched site models"] = matched_site_models_list
        detections_df["spatial overlap"] = spatial_overlap_list
        detections_df["temporal iot"] = tiot_list
        detections_df["temporal iop"] = tiop_list
        detections_df["min spatial distance"] = min_spatial_distance_list
        detections_df["central spatial distance"] = central_spatial_distance_list
        detections_df["max spatial distance"] = max_spatial_distance_list
        detections_df["min temporal distance"] = min_temporal_distance_list
        detections_df["central temporal distance"] = central_temporal_distance_list
        detections_df["max temporal distance"] = max_temporal_distance_list
        detections_df["site count"] = [len(sm) for sm in detections_df["matched site models"]]
        detections_df["matched site models"] = [", ".join(sm) for sm in detections_df["matched site models"]]
        detections_df["association status"] = [
            self.gt_sites[gt_id].association_status for gt_id in detections_df["truth site"]
        ]
        detections_df["associated"] = [self.gt_sites[gt_id].associated for gt_id in detections_df["truth site"]]
        detections_df["color code"] = [self.gt_sites[gt_id].color for gt_id in detections_df["truth site"]]
        detections_df["model type"] = model_type_list
        detections_df.sort_values("site type", inplace=True, ignore_index=True)

        # create proposals table
        proposals_df = pd.DataFrame()
        if self.sm_stacks and proposals:
            (
                proposals_df["site model"],
                proposals_df["site area"],
                proposals_df["matched truth sites"],
            ) = zip(
                *[
                    (
                        (sm_id, self.sm_stacks[sm_id].area, sorted(gt_ids))
                        if gt_ids
                        else (sm_id, self.sm_stacks[sm_id].area, "")
                    )
                    for sm_id, gt_ids in proposals.items()
                    if len(self.sm_stacks[sm_id].sites) == 1
                ]
            )
            proposals_df["site count"] = [len(gt) for gt in proposals_df["matched truth sites"]]
            proposals_df["matched truth sites"] = [", ".join(gt) for gt in proposals_df["matched truth sites"]]
            proposals_df["association status"] = [
                self.sm_stacks[sm_id].association_status for sm_id in proposals_df["site model"]
            ]
            proposals_df["associated"] = [self.sm_stacks[sm_id].associated for sm_id in proposals_df["site model"]]
            proposals_df["color code"] = [self.sm_stacks[sm_id].color for sm_id in proposals_df["site model"]]

        # site type table
        site_types_df = pd.DataFrame()
        site_types_df["site type"] = site_types.keys()
        site_types_df["proposed site count"] = [len(sm_ids) for sm_ids in site_types.values()]

        # add thresholds to the detections dataframe
        detections_df_raw = detections_df.copy(deep=True)
        detections_df_raw["rho"] = rho
        detections_df_raw["tau"] = tau
        detections_df_raw["min area"] = min_proposal_area
        detections_df_raw["min score"] = min_score
        detections_df_raw["temporal iop"] = tiop
        detections_df_raw["temporal iot"] = tiot
        detections_df_raw["transient temporal iop"] = ttiop
        detections_df_raw["transient temporal iot"] = ttiot
        detections_df_raw["min spatial distance threshold"] = min_spatial_distance
        detections_df_raw["central spatial distance threshold"] = central_spatial_distance
        detections_df_raw["max spatial distance threshold"] = max_spatial_distance
        detections_df_raw["min temporal distance threshold"] = min_temporal_distance
        detections_df_raw["central temporal distance threshold"] = central_temporal_distance
        detections_df_raw["max temporal distance threshold"] = max_temporal_distance

        # add thresholds to the proposals dataframe
        proposals_df_raw = proposals_df.copy(deep=True)
        proposals_df_raw["rho"] = rho
        proposals_df_raw["tau"] = tau
        proposals_df_raw["min area"] = min_proposal_area
        proposals_df_raw["min score"] = min_score
        proposals_df_raw["temporal iop"] = tiop
        proposals_df_raw["temporal iot"] = tiot
        proposals_df_raw["transient temporal iop"] = ttiop
        proposals_df_raw["transient temporal iot"] = ttiot
        proposals_df_raw["min spatial distance threshold"] = min_spatial_distance
        proposals_df_raw["central spatial distance threshold"] = central_spatial_distance
        proposals_df_raw["max spatial distance threshold"] = max_spatial_distance
        proposals_df_raw["min temporal distance threshold"] = min_temporal_distance
        proposals_df_raw["central temporal distance threshold"] = central_temporal_distance
        proposals_df_raw["max temporal distance threshold"] = max_temporal_distance

        # save to file
        if self.bas_dir and save_output:
            detections_df = Evaluation.sanitize_dataframe(detections_df, self.region_model.id, self.sequestered_id)
            detections_df = (
                detections_df.sort_values(by="truth site") if "truth site" in detections_df.columns else detections_df
            )
            proposals_df = Evaluation.sanitize_dataframe(proposals_df, self.region_model.id, self.sequestered_id)
            proposals_df = (
                proposals_df.sort_values(by="site model") if "site model" in proposals_df.columns else proposals_df
            )

            # point-based evaluation
            if self.gt_points:
                threshold_str = f"minArea={min_proposal_area}_minScore={min_score}_minSp={min_spatial_distance}_cenSp={central_spatial_distance}_maxSp={max_spatial_distance}_minTem={min_temporal_distance}_cenTem={central_temporal_distance}_maxTem={max_temporal_distance}"
            # polygon-based evaluation
            else:
                threshold_str = f"minArea={min_proposal_area}_minScore={min_score}_tau={tau}_rho={rho}_tiop={tiop}_tiot={tiot}_ttiop={ttiop}_ttiot={ttiot}"

            detections_df.to_csv(f"{self.bas_dir}/detections_{threshold_str}.csv", index=False)
            proposals_df.to_csv(f"{self.bas_dir}/proposals_{threshold_str}.csv", index=False)
            site_types_df.to_csv(f"{self.bas_dir}/siteType_{threshold_str}.csv", index=False)

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
        Builds an F-score table based on the given scoreboard, table threshold name, table threshold, and row threshold name.

        Parameters:
            scoreboard (pandas.DataFrame): The scoreboard of performance metric results, containing precision and recall values for each row.
            table_threshold_name (str): The name of the table threshold that is held constant for the entire scoreboard
            table_threshold (float): The value of the table threshold that is held constant for the entire scoreboard
            row_threshold_name (str): The name of the row threshold that is varied across the rows of the scoreboard.
            save_output (bool, optional): Whether to save the F-score table to a CSV file. Defaults to True.
            betas (list, optional): The list of beta values to calculate the F-beta scores. Defaults to [1/3, 0.5, 1, 2, 3].

        Returns:
            pandas.DataFrame: The F-score table with metrics for each value of the row threshold.
        """

        f_score_table_rows = []

        for index, row in scoreboard.iterrows():
            # get values for f_score_table
            precision = row["precision"]
            recall = row["recall (PD)"]

            # build f_score table
            f_row = {}
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

            # add thresholds
            f_row["tau"] = row["tau"]
            f_row["rho"] = row["rho"]
            f_row["min proposal area"] = row["min proposal area"]
            f_row["min proposal confidence score"] = row["min proposal confidence score"]
            f_row["temporal iop"] = row["temporal iop"]
            f_row["temporal iot"] = row["temporal iot"]
            f_row["transient temporal iop"] = row["transient temporal iop"]
            f_row["transient temporal iot"] = row["transient temporal iot"]
            f_row["min spatial distance threshold"] = row["min spatial distance threshold"]
            f_row["central spatial distance threshold"] = row["central spatial distance threshold"]
            f_row["max spatial distance threshold"] = row["max spatial distance threshold"]
            f_row["min temporal distance threshold"] = row["min temporal distance threshold"]
            f_row["central temporal distance threshold"] = row["central temporal distance threshold"]
            f_row["max temporal distance threshold"] = row["max temporal distance threshold"]
            f_row["region"] = self.sequestered_id if self.sequestered_id else self.region_model.id

            # add row to f_score_table (metrics per value of detection threshold rho)
            f_score_table_rows.append(f_row)

        # Convert list of dictionaries into a data frame
        f_score_table = pd.DataFrame(f_score_table_rows)

        # return statement to allow for future expansion of functionality if desired
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
        save_output=True,
    ):
        """
        Builds a scoreboard table with performance metrics calculated at varying parameter threshold levels, including precision, recall, and F1 score.

        Makes updates to:
            self.best_metric_score (float): the highest metric score (currently using F1) achieved using
                the optimal thresholds, used to save the corresponding optimal results:
            self.detections: a dict mapping each truth site to its matched site model(s) (0 or more)
            self.proposals: a dict mapping each site model to its matched truth site(s) (0 or more)
            self.site_types: a dict mapping each truth site type to its matched site model(s)
            self.matched_pairs: a list of the matched pairs [ (gt_id, sm_id), ... ]

        Parameters:
            table_threshold_name (str): The name of the threshold held constant for the entire scoreboard.
            table_threshold (float): The value of the threshold held constant for the entire scoreboard.
            row_threshold_name (str): The name of the threshold varied across the rows of the scoreboard.
            row_thresholds (list): The values of the threshold varied across the rows of the scoreboard.
            min_score (float, optional): The minimum confidence score of all the sites involved in building this scoreboard. Defaults to 0.
            use_iot (bool, optional): If sites fail to meet the IoU threshold, attempt to match them using IoT. Defaults to True.
            save_output (bool, optional): Write the table to a CSV file. Defaults to True.

        Returns:
            tuple: A tuple containing the following:
                - scoreboard (DataFrame): The scoreboard table with performance metrics.
                - scoreboard_df_raw (DataFrame): The scoreboard table with raw threshold values.
                - all_detections_df_concat (DataFrame): The concatenated table of detected sites.
                - all_proposals_df_concat (DataFrame): The concatenated table of proposed sites.
                - all_failed_assoc_df_concat (DataFrame): The concatenated table of failed associations.
        """

        # initialize scoreboard
        scoreboard_rows = []
        scoreboard_rows_raw = []
        detections_df_raw_list = []
        proposals_df_raw_list = []
        failed_assoc_df_raw_list = []

        # build up 1 row at a time
        for row_threshold in sorted(row_thresholds):
            thresholds = [
                (table_threshold_name, table_threshold),
                (row_threshold_name, row_threshold),
            ]

            # thresholds for polygon-based evaluation
            tau = next(iter([tup[1] for tup in thresholds if tup[0] == "tau"]), self.taus[0])
            rho = next(iter([tup[1] for tup in thresholds if tup[0] == "rho"]), self.rhos[0])
            temporal_iot = next(
                iter([tup[1] for tup in thresholds if tup[0] == "temporal iot"]),
                self.temporal_iots[0],
            )
            temporal_iop = next(
                iter([tup[1] for tup in thresholds if tup[0] == "temporal iop"]),
                self.temporal_iops[0],
            )
            transient_temporal_iot = next(
                iter([tup[1] for tup in thresholds if tup[0] == "transient temporal iot"]),
                self.transient_temporal_iots[0],
            )
            transient_temporal_iop = next(
                iter([tup[1] for tup in thresholds if tup[0] == "transient temporal iop"]),
                self.transient_temporal_iops[0],
            )

            # thresholds for proposals
            min_proposal_area = next(
                iter([tup[1] for tup in thresholds if tup[0] == "min proposal area"]),
                self.min_proposal_areas[0],
            )
            min_score = next(
                iter([tup[1] for tup in thresholds if tup[0] == "min proposal confidence score"]),
                self.confidence_score_thresholds[0],
            )

            # thresholds for point-based evaluation
            min_spatial_distance = next(
                iter([tup[1] for tup in thresholds if tup[0] == "min spatial distance threshold"]),
                self.min_spatial_distances[0],
            )
            central_spatial_distance = next(
                iter([tup[1] for tup in thresholds if tup[0] == "central spatial distance threshold"]),
                self.central_spatial_distances[0],
            )
            max_spatial_distance = next(
                iter([tup[1] for tup in thresholds if tup[0] == "max spatial distance threshold"]),
                self.max_spatial_distances[0],
            )
            min_temporal_distance = next(
                iter([tup[1] for tup in thresholds if tup[0] == "min temporal distance threshold"]),
                self.min_temporal_distances[0],
            )
            central_temporal_distance = next(
                iter([tup[1] for tup in thresholds if tup[0] == "central temporal distance threshold"]),
                self.central_temporal_distances[0],
            )
            max_temporal_distance = next(
                iter([tup[1] for tup in thresholds if tup[0] == "max temporal distance threshold"]),
                self.max_temporal_distances[0],
            )

            # save the best results for each row threshold
            detections = defaultdict(list)
            failed_associations = []
            attempted_iot = []  # a list of truth sites not initially detected by IoU, but potentially detected by IoT

            # filter proposals by minimum area
            sm_ids_to_keep = set()
            for sm_id in self.sm_stacks:
                for site in self.sm_stacks[sm_id].sites:
                    # Check area
                    if self.sm_stacks[site].area * 1e6 < min_proposal_area:
                        logging.debug(f"{site} < {min_proposal_area} square meters")
                        break

                    # Check the minimum confidence score of the proposal
                    site_score = self.sm_stacks[site].score
                    if site_score < min_score:
                        logging.debug(f"{site} < {min_score} confidence score")
                        break
                else:
                    sm_ids_to_keep.add(sm_id)
            logging.debug(
                f"{len(sm_ids_to_keep)} site models > {min_proposal_area} square meters and >= {min_score} confidence score)"
            )

            proposals = {sm_id: [] for sm_id in sm_ids_to_keep}
            valid_point_proposals = defaultdict(
                list
            )  # proposals that meet the association thresholds and should not be counted as false positives
            proposed_slices = 0

            site_types = defaultdict(set)
            matched_pairs = []
            tp, tp_exact, tp_over, tp_under, tp_under_iou, tp_under_iot, fp, fn, tn = (
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
            )

            # get the comparisons between the truth sites and the proposals, which were already computed
            comparing_points = False if self.gt_stacks else True
            if comparing_points:
                comparisons = self.point_comparisons
                self.gt_sites = self.gt_points
            else:
                comparisons = self.stack_comparisons
                self.gt_sites = self.gt_stacks

            # score each (ground truth, proposal) comparison
            for gt_id, sm_ids in comparisons.items():
                gt_site = self.gt_sites[gt_id]
                self.gt_sites[gt_id].association_status = None
                self.gt_sites[gt_id].associated = None
                self.gt_sites[gt_id].color = None

                # make sure that the detections dict includes every truth site
                detections[gt_id] = []

                # sort the valid proposals by the number of sites they are composed of (prioritize combined site stacks)
                for sm_id in sorted(
                    list(set(sm_ids) & sm_ids_to_keep),
                    key=lambda sm_id: len(self.sm_stacks[sm_id].sites),
                    reverse=True,
                ):
                    sm_stack = self.sm_stacks[sm_id]
                    self.sm_stacks[sm_id].association_status = None
                    self.sm_stacks[sm_id].associated = None
                    self.sm_stacks[sm_id].color = None

                    # the ground truth site must have some temporal duration in order to be associated
                    if not comparing_points and not gt_site.len_activity or not sm_stack.len_activity:
                        continue

                    # point-based evaluation
                    if comparing_points:
                        point_scores = self.point_comparisons[gt_id][sm_id]
                        if not point_scores:
                            continue
                        # a point is detected if the spatial and temporal distances are within the thresholds, or if the thresholds are negative (turned off)
                        detected = (
                            (
                                min_spatial_distance is None
                                or point_scores["min_spatial_distance"] <= min_spatial_distance
                            )
                            and (
                                central_spatial_distance is None
                                or point_scores["central_spatial_distance"] <= central_spatial_distance
                            )
                            and (
                                max_spatial_distance is None
                                or point_scores["max_spatial_distance"] <= max_spatial_distance
                            )
                            and (
                                min_temporal_distance is None
                                or abs(point_scores["min_temporal_distance"]) <= min_temporal_distance
                            )
                            and (
                                central_temporal_distance is None
                                or abs(point_scores["central_temporal_distance"]) <= central_temporal_distance
                            )
                            and (
                                max_temporal_distance is None
                                or abs(point_scores["max_temporal_distance"]) <= max_temporal_distance
                            )
                        )
                        if detected:
                            detections[gt_id].append(
                                {
                                    "sm_id": sm_id,
                                    "min_spatial_distance": point_scores["min_spatial_distance"],
                                    "central_spatial_distance": point_scores["central_spatial_distance"],
                                    "max_spatial_distance": point_scores["max_spatial_distance"],
                                    "min_temporal_distance": point_scores["min_temporal_distance"],
                                    "central_temporal_distance": point_scores["central_temporal_distance"],
                                    "max_temporal_distance": point_scores["max_temporal_distance"],
                                }
                            )
                        else:
                            failed_associations.append(
                                {
                                    "gt_id": gt_id,
                                    "sm_id": sm_id,
                                    "min_spatial_distance": point_scores["min_spatial_distance"],
                                    "central_spatial_distance": point_scores["central_spatial_distance"],
                                    "max_spatial_distance": point_scores["max_spatial_distance"],
                                    "min_temporal_distance": point_scores["min_temporal_distance"],
                                    "central_temporal_distance": point_scores["central_temporal_distance"],
                                    "max_temporal_distance": point_scores["max_temporal_distance"],
                                }
                            )

                    # polygon-based evaluation
                    else:
                        # for each dataframe, calculate the % of its observations that were detected
                        df = comparisons[gt_id][sm_id]
                        if df.empty:
                            continue

                        # spatial overlap
                        # use spatial IoP for ignore-type sites
                        if gt_site.status in IGNORE_STATUS_TYPES:
                            # only use the first and the last truth observations of an ignore-type truth site for BAS association
                            first_and_last = pd.concat([df.head(1), df.tail(1)])
                            iop_score = len(list(filter(lambda x: x >= tau, first_and_last["iop"]))) / len(
                                first_and_last["iop"]
                            )
                            spatial_overlap = iop_score
                        # use spatial IoU and IoT for other sites
                        else:
                            iou_score = len(list(filter(lambda x: x >= tau, df["iou"]))) / len(df["iou"])
                            spatial_overlap = iou_score
                            if iou_score < rho and use_iot:
                                logging.debug(f"No detections of {gt_id} with IoU, now trying with IoT")
                                iot_score = len(list(filter(lambda x: x >= tau, df["iot"]))) / len(df["iot"])
                                attempted_iot.append(gt_id)
                                spatial_overlap = iot_score

                        # temporal overlap
                        # use temporal IoT and IoP for all sites
                        if not gt_site.len_activity:
                            tiot = 0
                            tiop = 0
                        elif gt_site.status in POSITIVE_ACTIVITY_STATUS_TYPES:
                            tiot = (
                                len(gt_site.min_activity_dates.intersection(sm_stack.activity_dates))
                                / gt_site.len_min_activity
                            )
                            tiop = (
                                len(gt_site.max_activity_dates.intersection(sm_stack.activity_dates))
                                / sm_stack.len_activity
                            )
                        else:
                            tiot = (
                                len(gt_site.activity_dates.intersection(sm_stack.activity_dates)) / gt_site.len_activity
                            )
                            tiop = (
                                len(gt_site.activity_dates.intersection(sm_stack.activity_dates))
                                / sm_stack.len_activity
                            )

                        # determine whether the thresholds were met for the truth site to be detected
                        if gt_site.status in IGNORE_STATUS_TYPES:
                            if "transient" in gt_site.status:
                                detected = spatial_overlap >= rho and tiop >= transient_temporal_iop
                            else:
                                detected = spatial_overlap >= rho and tiop >= temporal_iop
                        else:
                            if "transient" in gt_site.status:
                                detected = (
                                    spatial_overlap >= rho
                                    and tiop >= transient_temporal_iop
                                    and tiot >= transient_temporal_iot
                                )
                            else:
                                detected = spatial_overlap >= rho and tiop >= temporal_iop and tiot >= temporal_iot

                        # each truth site from the stack_comparisons dict is detected (thresholds were met) or
                        # failed to associate (the truth site had some spatial and temporal overlap with a proposal, but the thresholds were not met)
                        if detected:
                            # add every proposal that meets the thresholds for the truth site
                            # (there can be more than 1 valid candidate proposal for association)
                            detections[gt_id].append(
                                {
                                    "sm_id": sm_id,
                                    "spatial_overlap": spatial_overlap,
                                    "tiot": tiot,
                                    "tiop": tiop,
                                }
                            )
                        else:
                            # add every proposal that has non-zero overlap with the truth site but fails to meet the thresholds
                            failed_associations.append(
                                {
                                    "gt_id": gt_id,
                                    "sm_id": sm_id,
                                    "spatial_overlap": spatial_overlap,
                                    "tiot": tiot,
                                    "tiop": tiop,
                                }
                            )

            # point-based evaluation
            closest_point = {}
            if comparing_points:
                pairs = []
                for gt_id in detections:
                    if detections[gt_id]:
                        for sm in detections[gt_id]:
                            valid_point_proposals[sm["sm_id"]].append(gt_id)
                        best_sm = min(
                            detections[gt_id],
                            key=lambda x: (
                                x["min_spatial_distance"],
                                x["max_spatial_distance"],
                            ),
                        )
                        # for each truth point, choose the eligible proposal closest to it
                        pairs.append((gt_id, best_sm["sm_id"], best_sm["min_spatial_distance"]))
                if pairs:
                    df = pd.DataFrame(pairs, columns=["gt_id", "sm_id", "distance"])
                    # can't use a proposal that is already matched to another truth point
                    # but need to permit ties (e.g. distance=0)
                    smallest_distances = df.groupby("sm_id").min("distances")
                    df = df.merge(smallest_distances)
                    for pair in list(df[["gt_id", "sm_id"]].itertuples(index=False, name=None)):
                        closest_point[pair[0]] = pair[1]

            # score the associations
            for gt_id in comparisons:
                gt_site = self.gt_sites[gt_id]
                if comparing_points:
                    best_sm_id = closest_point.get(gt_id)
                else:
                    # the truth site was detected by 1 or more candidate site model proposals
                    # choose the proposal with the most over-segmented sites, in order to minimize false positives
                    # the next tie-breaker between candidate proposals is the spatial overlap score
                    # the next tie-breaker between candidate proposals is the site name
                    best_sm_id = (
                        max(
                            detections[gt_id],
                            key=lambda x: (
                                len(self.sm_stacks[x["sm_id"]].sites),
                                x["spatial_overlap"],
                                x["sm_id"],
                            ),
                        )["sm_id"]
                        if detections[gt_id]
                        else None
                    )

                if best_sm_id:
                    logging.debug(f"Detected gt {gt_id} with sm {best_sm_id}")
                    proposed_slices += len(self.sm_stacks[best_sm_id].slices)

                    matched_pairs.append((gt_id, best_sm_id))
                    sm_match_stack = self.sm_stacks[best_sm_id]
                    # over-segmented proposals
                    for sub_sm_id in sm_match_stack.sites:
                        proposals[sub_sm_id].append(gt_id)
                        site_types[gt_site.status].add(sub_sm_id)

                    # score the detected truth site based on its effective status
                    if gt_site.status in POSITIVE_STATUS_TYPES:
                        self.gt_sites[gt_id].association_status = "tp"
                        self.gt_sites[gt_id].associated = True
                        self.gt_sites[gt_id].color = 2
                        tp += 1
                    elif gt_site.status in NEGATIVE_STATUS_TYPES:
                        self.gt_sites[gt_id].association_status = "fp"
                        self.gt_sites[gt_id].associated = True
                        self.gt_sites[gt_id].color = 5
                        fp += 1
                    elif gt_site.status in POSITIVE_UNBOUNDED_STATUS_TYPES:
                        self.gt_sites[gt_id].association_status = "0"
                        self.gt_sites[gt_id].associated = True
                        self.gt_sites[gt_id].color = 8
                    elif gt_site.status in ANNOTATED_IGNORE_STATUS_TYPES:
                        self.gt_sites[gt_id].association_status = "0"
                        self.gt_sites[gt_id].associated = True
                        self.gt_sites[gt_id].color = 11

                # the truth site was not detected
                else:
                    logging.debug(f"Missed gt {gt_id}")

                    # score the missed truth site based on its effective status
                    if gt_site.status in POSITIVE_STATUS_TYPES:
                        self.gt_sites[gt_id].association_status = "fn"
                        self.gt_sites[gt_id].associated = False
                        self.gt_sites[gt_id].color = 3
                        fn += 1
                    elif gt_site.status in NEGATIVE_STATUS_TYPES:
                        self.gt_sites[gt_id].association_status = "tn"
                        self.gt_sites[gt_id].associated = False
                        self.gt_sites[gt_id].color = 6
                        tn += 1
                    elif gt_site.status in POSITIVE_UNBOUNDED_STATUS_TYPES:
                        self.gt_sites[gt_id].association_status = "0"
                        self.gt_sites[gt_id].associated = False
                        self.gt_sites[gt_id].color = 9
                    elif gt_site.status in ANNOTATED_IGNORE_STATUS_TYPES:
                        self.gt_sites[gt_id].association_status = "0"
                        self.gt_sites[gt_id].associated = False
                        self.gt_sites[gt_id].color = 12

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
                    if not comparing_points:
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
                match_statuses = [self.gt_sites[gt_id].status for gt_id in gt_ids]
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
                    proposed_slices += len(self.sm_stacks[sm_id].slices)
                    if sm_id in valid_point_proposals:
                        self.sm_stacks[sm_id].association_status = "0"
                        self.sm_stacks[sm_id].associated = False
                        self.sm_stacks[sm_id].color = 27
                        site_types["already detected point"].add(sm_id)
                    else:
                        self.sm_stacks[sm_id].association_status = "fp"
                        self.sm_stacks[sm_id].associated = False
                        self.sm_stacks[sm_id].color = 22
                        fp += 1
                        site_types["false alarm"].add(sm_id)

            # add point proposals
            for sm_id in valid_point_proposals:
                if not proposals[sm_id]:
                    proposals[sm_id] = valid_point_proposals[sm_id]

            # count the over/under/exact segmentations
            for gt_id, sm_id in matched_pairs:
                if self.gt_sites[gt_id].status in POSITIVE_STATUS_TYPES:
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
                        logging.debug(
                            f"{gt_id} was detected with {len(matched_site_models)} over-segmented proposals {sm_id}"
                        )
                        tp_over += 1

            # normalize the false positive area
            fpa = round(proposal_area / self.region_model.area, 4)
            ffpa = round(
                fp_area / GeometryUtil.compute_region_area(self.region_model.polygon.difference(union_nonneg_area)),
                4,
            )

            # calculate metrics
            precision = Metric.calc_precision(tp, fp)
            recall = Metric.calc_recall(tp, fn)
            f1 = Metric.calc_F1(tp, fp, fn)

            # build scoreboard table
            row = {}
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
            row["confident proposals"] = len(
                [
                    sm_id
                    for sm_id in self.sm_stacks
                    if self.sm_stacks[sm_id].score >= min_score and len(self.sm_stacks[sm_id].sites) == 1
                ]
            )
            row["proposed sites"] = tp + fp
            row["total sites"] = tp + fp + fn
            row["truth slices"] = sum([len(self.gt_stacks[gt_id].slices) for gt_id in self.gt_stacks])
            row["proposed slices"] = proposed_slices
            row["precision"] = precision
            row["recall (PD)"] = recall
            row["F1"] = f1
            row["tau"] = tau
            row["rho"] = rho
            row["temporal iop"] = temporal_iop
            row["temporal iot"] = temporal_iot
            row["transient temporal iop"] = transient_temporal_iop
            row["transient temporal iot"] = transient_temporal_iot
            row["min proposal area"] = min_proposal_area
            row["min proposal confidence score"] = min_score
            row["min spatial distance threshold"] = min_spatial_distance
            row["central spatial distance threshold"] = central_spatial_distance
            row["max spatial distance threshold"] = max_spatial_distance
            row["min temporal distance threshold"] = min_temporal_distance
            row["central temporal distance threshold"] = central_temporal_distance
            row["max temporal distance threshold"] = max_temporal_distance
            row["region"] = self.sequestered_id if self.sequestered_id else self.region_model.id

            # calculate FAR metrics
            if self.region_model is not None:
                spatial_far = round(float(fp / self.region_model.area), 4)
                temporal_far = round(float(fp / self.region_model.dates), 4)
                row["spatial FAR"] = spatial_far
                row["temporal FAR"] = temporal_far

            # count the number of images (slices) in the site model stacks, for the FAR metric
            images_far = round(float(fp / proposed_slices), 4) if proposed_slices else 0
            row["images FAR"] = images_far

            # add row to scoreboard (metrics per value of detection threshold rho)
            scoreboard_rows.append(row)

            # add threshold values to the scoreboard table
            row_raw = deepcopy(row)
            row_raw["tau"] = tau
            row_raw["rho"] = rho
            row_raw["min area"] = min_proposal_area
            row_raw["min score"] = min_score
            row_raw["temporal iop"] = temporal_iop
            row_raw["temporal iot"] = temporal_iot
            row_raw["transient temporal iop"] = transient_temporal_iop
            row_raw["transient temporal iot"] = transient_temporal_iot
            row_raw["min spatial distance threshold"] = min_spatial_distance
            row_raw["central spatial distance threshold"] = central_spatial_distance
            row_raw["max spatial distance threshold"] = max_spatial_distance
            row_raw["min temporal distance threshold"] = min_temporal_distance
            row_raw["central temporal distance threshold"] = central_temporal_distance
            row_raw["max temporal distance threshold"] = max_temporal_distance
            scoreboard_rows_raw.append(row_raw)

            # save the best results, using the F1 score
            # if f1 >= self.best_metric_score:
            # OR
            # save the results at a fixed set of thresholds, for standard comparisons between performers
            if f1 >= self.best_metric_score:
                self.best_metric_score = f1
                self.best = pd.DataFrame([row])
                self.detections = detections
                self.proposals = proposals
                self.matched_pairs = matched_pairs
                self.best_tau = tau
                self.best_rho = rho
                self.best_min_proposal_area = min_proposal_area
                self.best_min_score = min_score
                self.best_tiop = temporal_iop
                self.best_tiot = temporal_iot
                self.best_ttiop = transient_temporal_iop
                self.best_ttiot = transient_temporal_iot
                self.best_min_spatial_distance = min_spatial_distance
                self.best_central_spatial_distance = central_spatial_distance
                self.best_max_spatial_distance = max_spatial_distance
                self.best_min_temporal_distance = min_temporal_distance
                self.best_central_temporal_distance = central_temporal_distance
                self.best_max_temporal_distance = max_temporal_distance

            # create the output tables for the given thresholds
            detections_df_raw, proposals_df_raw = self.create_detections_table(
                detections,
                proposals,
                tau,
                rho,
                temporal_iop,
                temporal_iot,
                transient_temporal_iop,
                transient_temporal_iot,
                min_proposal_area,
                min_score,
                min_spatial_distance,
                central_spatial_distance,
                max_spatial_distance,
                min_temporal_distance,
                central_temporal_distance,
                max_temporal_distance,
                site_types,
                comparing_points,
                save_output=save_output,
            )
            failed_assoc_raw = self.create_failed_associations_table(
                failed_associations,
                proposals,
                tau,
                rho,
                temporal_iop,
                temporal_iot,
                transient_temporal_iop,
                transient_temporal_iot,
                min_proposal_area,
                min_score,
                min_spatial_distance,
                central_spatial_distance,
                max_spatial_distance,
                min_temporal_distance,
                central_temporal_distance,
                max_temporal_distance,
                site_types,
                comparing_points,
                save_output=save_output,
            )

            detections_df_raw_list.append(detections_df_raw)
            proposals_df_raw_list.append(proposals_df_raw)
            failed_assoc_df_raw_list.append(failed_assoc_raw)

        # Convert list of dictionaries into a data frame
        scoreboard = pd.DataFrame(scoreboard_rows)
        scoreboard = scoreboard.sort_values(row_threshold_name).drop_duplicates(subset=row_threshold_name)
        scoreboard_df_raw = pd.DataFrame(scoreboard_rows_raw)
        logging.debug("Built scoreboard with shape: {}".format(scoreboard.shape))

        # concatenate tables
        with warnings.catch_warnings():
            # FutureWarning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated
            warnings.filterwarnings("ignore", category=FutureWarning)
            all_detections_df_concat = pd.concat(detections_df_raw_list)
            all_proposals_df_concat = pd.concat(proposals_df_raw_list)
            all_failed_assoc_df_concat = pd.concat(failed_assoc_df_raw_list)

        return (
            scoreboard,
            scoreboard_df_raw,
            all_detections_df_concat,
            all_proposals_df_concat,
            all_failed_assoc_df_concat,
        )

    @timer
    def associate_sites(self, activity_type):
        """
        Finds optimal site associations between ground truth sites and proposed site models,
        using varying threshold values, while allowing for over/under segmentation (for polygon-based evaluation).

        Parameters:
            activity_type (str): The type of activity for which site stacks are being associated (partial, completed, overall).

        Returns:
            None
        """
        logging.info(f"Associating {activity_type} sites...")

        # reset optimal score
        self.best_metric_score = 0

        # calculate rollup metrics for varying levels of the detection threshold
        threshold_map = {
            "tau": sorted(list(set(self.taus))),
            "rho": sorted(list(set(self.rhos))),
            "min_confidence": sorted(list(set(self.confidence_score_thresholds))),
            "min_proposal_area": sorted(list(set(self.min_proposal_areas))),
            "tiop": sorted(list(set(self.temporal_iops))),
            "tiot": sorted(list(set(self.temporal_iots))),
            "ttiop": sorted(list(set(self.transient_temporal_iops))),
            "ttiot": sorted(list(set(self.transient_temporal_iots))),
            "minSp": sorted(list(set(self.min_spatial_distances))),
            "midSp": sorted(list(set(self.central_spatial_distances))),
            "maxSp": sorted(list(set(self.max_spatial_distances))),
            "minTem": sorted(list(set(self.min_temporal_distances))),
            "midTem": sorted(list(set(self.central_temporal_distances))),
            "maxTem": sorted(list(set(self.max_temporal_distances))),
        }
        thresholds = []

        # sweep the thresholds
        if self.sweep_tau:
            thresholds.append(("tau", threshold_map["tau"]))
        if self.sweep_rho:
            thresholds.append(("rho", threshold_map["rho"]))
        if self.sweep_min_proposal_area:
            thresholds.append(("min proposal area", threshold_map["min_proposal_area"]))
        if self.sweep_confidence:
            thresholds.append(("min proposal confidence score", threshold_map["min_confidence"]))
        if self.sweep_temporal_iop:
            thresholds.append(("temporal iop", threshold_map["tiop"]))
        if self.sweep_temporal_iot:
            thresholds.append(("temporal iot", threshold_map["tiot"]))
        if self.sweep_transient_temporal_iop:
            thresholds.append(("transient temporal iop", threshold_map["ttiop"]))
        if self.sweep_transient_temporal_iot:
            thresholds.append(("transient temporal iot", threshold_map["ttiot"]))
        if self.sweep_central_spatial_distance:
            thresholds.append(("central spatial distance threshold", threshold_map["midSp"]))
        if self.sweep_max_spatial_distance:
            thresholds.append(("max spatial distance threshold", threshold_map["maxSp"]))
        if self.sweep_min_temporal_distance:
            thresholds.append(("min temporal distance threshold", threshold_map["minTem"]))
        if self.sweep_max_temporal_distance:
            thresholds.append(("max temporal distance threshold", threshold_map["maxTem"]))
        if self.sweep_min_spatial_distance:
            thresholds.append(("min spatial distance threshold", threshold_map["minSp"]))
        if self.sweep_central_temporal_distance:
            thresholds.append(("central temporal distance threshold", threshold_map["midTem"]))
        if len(thresholds) == 0:
            thresholds.append(("min proposal area", threshold_map["min_proposal_area"]))
            thresholds.append(("min proposal confidence score", threshold_map["min_confidence"]))
        if len(thresholds) == 1:
            if thresholds[0][0] == "min proposal confidence score":
                thresholds.append(("min proposal area", threshold_map["min_proposal_area"]))
            else:
                thresholds.append(("min proposal confidence score", threshold_map["min_confidence"]))

        # tables for all of the thresholds
        scoreboards = []
        f_score_tables = []

        # get every pair of thresholds to create the 2-dimensional tables
        for threshold_pair in sorted(list(combinations(thresholds, 2))):
            threshold_pair = sorted(list(threshold_pair))

            # use the threshold with fewer values to create the individual scoreboard tables
            table_threshold_name, table_thresholds = threshold_pair.pop(
                threshold_pair.index(min(threshold_pair, key=lambda x: len(x[1])))
            )

            # use the other threshold with more values to create the individual rows in each scoreboard
            row_threshold_name, row_thresholds = threshold_pair[0]

            # build each scoreboard
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
                )

                f_score_table = self.build_f_score_table(
                    scoreboard,
                    table_threshold_name,
                    table_threshold,
                    row_threshold_name,
                )
                f_score_tables.append(f_score_table)
                scoreboards.append(scoreboard)

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

        # save the f score tables and scoreboards
        if self.bas_dir:
            f_score_tables_concat = (
                pd.concat(f_score_tables).sort_values("f_1", ascending=False).drop_duplicates().round(4)
            )
            f_score_tables_concat.to_csv(f"{self.bas_dir}/f_scores.csv", index=False)
            scoreboards_concat = pd.concat(scoreboards).sort_values("F1", ascending=False).drop_duplicates().round(4)
            scoreboards_concat.to_csv(f"{self.bas_dir}/scoreboard.csv", index=False)

        # save the optimal row from the scoreboard to its own file
        if isinstance(self.best, pd.DataFrame):
            self.best["tau"] = self.best_tau
            self.best["rho"] = self.best_rho
            self.best["temporal iop"] = self.best_tiop
            self.best["temporal iot"] = self.best_tiot
            self.best["transient temporal iop"] = self.best_ttiop
            self.best["transient temporal iot"] = self.best_ttiot
            self.best["min proposal area"] = self.best_min_proposal_area
            self.best["min proposal confidence score"] = self.best_min_score
            self.best["min spatial distance threshold"] = self.best_min_spatial_distance
            self.best["central spatial distance threshold"] = self.best_central_spatial_distance
            self.best["max spatial distance threshold"] = self.best_max_spatial_distance
            self.best["min temporal distance threshold"] = self.best_min_temporal_distance
            self.best["central temporal distance threshold"] = self.best_central_temporal_distance
            self.best["max temporal distance threshold"] = self.best_max_temporal_distance
            self.best["region"] = self.sequestered_id if self.sequestered_id else self.region_model.id
            self.best = self.best.round(4)

            # point-based evaluation
            if self.gt_points:
                threshold_str = f"minArea={self.best_min_proposal_area}_minScore={self.best_min_score}_minSp={self.best_min_spatial_distance}_cenSp={self.best_central_spatial_distance}_maxSp={self.best_max_spatial_distance}_minTem={self.best_min_temporal_distance}_cenTem={self.best_central_temporal_distance}_maxTem={self.best_max_temporal_distance}"
            # polygon-based evaluation
            else:
                threshold_str = f"minArea={self.best_min_proposal_area}_minScore={self.best_min_score}_tau={self.best_tau}_rho={self.best_rho}_tiop={self.best_tiop}_tiot={self.best_tiot}_ttiop={self.best_ttiop}_ttiot={self.best_ttiot}"

            self.best.to_csv(f"{self.bas_dir}/bestScore_{threshold_str}.csv", index=False)
        else:
            logging.warning("self.best not set. Did not write a best score scoreboard.")

    @timer
    def calc_activity_metrics(self, activity_type):
        """
        Calculate activity classification and prediction metrics for a given activity type (partial, completed, overall).
        AC and AP metrics are only for polygon-based evaluation.

        Parameters:
            activity_type (str): The type of ground truth activity for which to evaluate metrics (partial, completed, overall).

        Returns:
            tuple: A tuple containing the following:
                - phase_table (DataFrame): A table of the observation dates and the ground truth and proposed activity phase labels on those dates, for each observation of each pair of associated stacks.
                - tiou_table (DataFrame): A table of the temporal intersection over union (TIoU) metric for each pair of associated stacks, for each activity phase.
                - ac_te_table (DataFrame): A temporal error table that shows the average onset-of-activity classification errors across all sites, used for activity classification metrics.
                - ap_te_table (DataFrame): A temporal error table that shows the average activity prediction errors across all sites, used for activity prediction metrics.
                - cm (DataFrame): A confusion matrix built from the phases in the activity classification phase table.
        """

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

        def get_phase_dates(stack):
            """
            Retrieves or infers the phase activity for each observation date within a site.
            Don't infer phase activity for dates that occur during the transition from one type of activity to a different type.
            Used for TIoU calculations only.

            Parameters:
                stack (SiteStack): The site stack containing the observation dates and corresponding phases.

            Returns:
                dict: A dictionary mapping a phase label to the calendar dates in the site's temporal duration that are in that phase.
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
            Builds a temporal error table based on the given temporal error, missing ground truth sites, and missing proposed sites.

            Parameters:
                temporal_error (dict): A dictionary mapping a phase label to a list of temporal errors. Each temporal error is a tuple containing the worst, proposed, and best temporal error values.
                missing_gt (dict): A dictionary mapping a phase label to a list of missing ground truth site IDs.
                missing_sm (dict): A dictionary mapping a phase label to a list of missing proposed site model IDs.

            Returns:
                pandas.DataFrame: A DataFrame containing the temporal error metrics for each phase label.
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

        phase_dataframes = []  # list of per-site phase activity tables
        tiou_dataframes = []  # list of per-site TIoU tables

        # equal-length lists of the ground truth phase labels and the corresponding proposed phase labels (including subsites)
        phase_true_all_sites, phase_pred_all_sites = [], []
        f1_score_per_site = {}  # a dict mapping a ground truth site ID to its F1 score table

        ac_temporal_error = defaultdict(
            list
        )  # a dict mapping a phase label to the list of activity classification temporal errors for that activity phase
        ap_temporal_error = defaultdict(
            list
        )  # a dict mapping a phase label to the list of activity prediction temporal errors for that activity phase
        missing_gt = defaultdict(
            list
        )  # a dict mapping a phase label to a list of ground truth IDs that do not have that activity phase
        ac_missing_sm = defaultdict(
            list
        )  # a dict mapping a phase label to a list of proposed site model IDs that do not have that activity phase in their observational phase activity labels
        ap_missing_sm = defaultdict(
            list
        )  # a dict mapping a phase label to a list of proposed site model IDs that do not have that activity phase in their activity prediction labels

        # only iterate through stacks that got matched
        positive_detection_pairs = sorted(
            [pair for pair in self.matched_pairs if self.gt_stacks[pair[0]].status in POSITIVE_ACTIVITY_STATUS_TYPES]
        )
        if not positive_detection_pairs:
            logging.info(
                f"Phase activity metrics cannot be calculated for {activity_type!r}, because there were no positive site detections of this type."
            )
            return None
        else:
            logging.debug(
                f"Calculate phase activity metrics for {activity_type!r} with {len(positive_detection_pairs)}/{len(self.matched_pairs)} pairs."
            )

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
            gt_times = defaultdict(
                list
            )  # a dict mapping a phase label to a list of observation dates in the ground truth site that are in that activity phase
            sm_times = defaultdict(
                list
            )  # a dict mapping a phase label to a list of observation dates in the proposed site model that are in that activity phase
            tiou = (
                {}
            )  # a dict mapping a phase label to the temporal intersection over union ratio metric for that activity phase
            phase_dict = (
                {}
            )  # a dict mapping each observation date to the phase labels of the ground truth observation and the associated site model observation

            ac_temporal_error_site = defaultdict(
                list
            )  # a dict mapping a phase label to the list of activity classification temporal errors for that activity phase
            ap_temporal_error_site = defaultdict(
                list
            )  # a dict mapping a phase label to the list of activity prediction temporal errors for that activity phase
            missing_gt_site = defaultdict(
                list
            )  # a dict mapping a phase label to a list of ground truth IDs that do not have that activity phase
            ac_missing_sm_site = defaultdict(
                list
            )  # a dict mapping a phase label to a list of proposed site model IDs that do not have that activity phase in their observational phase activity labels
            ap_missing_sm_site = defaultdict(
                list
            )  # a dict mapping a phase label to a list of proposed site model IDs that do not have that activity phase in their activity prediction labels

            # get activity phases for each stack slice
            gt_has_subsites = False
            for gt_slice in gt_stack.slices:
                # map each ground truth observation date to the ground truth phase
                gt_segment_phases = set(re.split(", |_", gt_slice.phase))
                phase_dict[gt_slice.date] = reorder_str(gt_slice.phase)

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
                            phase_true.append(gt_segment_phase)
                            phase_pred.append(sm_segment_phase)

                # explicitly add the proposed phase label if it is different than the actual ground truth label
                if gt_segment_phases != sm_segment_phases:
                    if sm_slice:
                        phase_dict[gt_slice.date] += f" vs. {reorder_str(sm_slice.phase)}"
                    else:
                        phase_dict[gt_slice.date] += " vs. n/a"

            for sm_slice in sm_stack.slices:
                # add the observation dates from the proposed site model
                if sm_slice.date not in phase_dict:
                    phase_dict[sm_slice.date] = f"n/a vs. {reorder_str(sm_slice.phase)}"
                # map the activity phase labels to the proposed site model observation dates
                sm_segment_phases = set(re.split(", |_", sm_slice.phase))
                for sm_segment_phase in sm_segment_phases:
                    # the proposed site model is only in Post Construction when all of its phase labels are Post Construction and all of the sites have started
                    if len(sm_segment_phases) == 1:
                        if sm_segment_phase != "Post Construction":
                            sm_times[sm_segment_phase].append(sm_slice.date)
                        elif sm_segment_phase == "Post Construction" and np.all(
                            [sm_slice.date >= self.sm_stacks[stack_id].start_date for stack_id in sm_stack.sites]
                        ):
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

            # compute the phase activity classification F1 scores, using the lists of ground truth phase labels and proposed phase labels
            selected_phases = list(
                set(["Site Preparation", "Active Construction"]) & (set(phase_true) | set(phase_pred))
            )
            selected_phases.sort(reverse=True)
            f1_score_df = pd.DataFrame(
                sklearn.metrics.f1_score(phase_true, phase_pred, labels=selected_phases, average=None),
                index=selected_phases,
            ).T
            f1_score_df = f1_score_df.rename_axis("Activity Classification", axis="columns")
            f1_score_df = f1_score_df.rename(index={0: "F1 score"}).round(4)
            f1_score_per_site[gt_id] = f1_score_df
            f1_score_df.to_csv(f"{output_dir}/ac_f1_{display_gt_id}.csv")

            # add the lists of ground truth phase labels and proposed phase labels to the aggregated lists for all detected positive truth sites and their associated proposals
            phase_true_all_sites.extend(phase_true)
            phase_pred_all_sites.extend(phase_pred)

            # get the calendar dates for each phase activity
            gt_ranges = get_phase_dates(gt_stack)
            sm_ranges = get_phase_dates(sm_stack)

            # compute the temporal errors for each phase
            activity_phases = [
                "No Activity",
                "Site Preparation",
                "Active Construction",
                "Post Construction",
            ]
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
                            prev_gt_times = [
                                gt_time for gt_time in gt_times[activity_phases[i - j]] if gt_time <= truth_onset
                            ]
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
                                worst_te = max(
                                    [
                                        te,
                                        len(pd.date_range(start=prev_finish, end=pred_onset)) - 1,
                                    ],
                                    key=abs,
                                )  # choose the greater magnitude of these 2 and keep the sign
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
                        onset = (
                            min(gt_times[phase]),
                            pd.to_datetime(sm_stack.predicted_date),
                        )
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
                    tiou[phase] = len(set(gt_ranges[phase]).intersection(set(sm_ranges[phase]))) / len(
                        set(gt_ranges[phase]).union(set(sm_ranges[phase]))
                    )

            # for each site, create tables of the observation dates and the ground truth and proposed activity phase labels
            phase_df = pd.DataFrame(phase_dict, index=[0]).T
            phase_df.columns = [f"site truth {display_gt_id} vs. site model {display_sm_id}"]
            phase_dataframes.append(phase_df)

            # add raw site model ids; however, need to make sure to remove before saving output
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

        # compute the aggregated phase activity classification F1 scores, using the lists of ground truth phase labels and proposed phase labels
        f1_score_macro = {}
        for phase in ["Site Preparation", "Active Construction"]:
            scores = [site_df[phase].iloc[0] for site_df in f1_score_per_site.values() if phase in site_df.columns]
            f1_score_macro[phase] = [np.mean(scores)]
        selected_phases = list(
            set(["Site Preparation", "Active Construction"]) & (set(phase_true_all_sites) | set(phase_pred_all_sites))
        )
        selected_phases.sort(reverse=True)
        f1_df = pd.concat(
            [
                pd.DataFrame(
                    sklearn.metrics.f1_score(
                        phase_true_all_sites,
                        phase_pred_all_sites,
                        labels=selected_phases,
                        average=None,
                    ),
                    index=selected_phases,
                ).T,
                pd.DataFrame(f1_score_macro, index=["F1 macro average"]),
            ]
        )
        f1_df = (
            f1_df.rename(index={0: "F1 micro average"})
            .rename_axis(
                f"Activity Classification ({len(f1_score_per_site)} sites)",
                axis="columns",
            )
            .round(4)
        )
        f1_df.to_csv(f"{output_dir}/ac_f1_all_sites.csv")

        ac_te_table.to_csv(f"{output_dir}/ac_temporal_error.csv")

        ap_te_table.to_csv(f"{output_dir}/ap_temporal_error.csv")

        phase_table.to_csv(f"{output_dir}/ac_phase_table.csv")

        # make sure to remove site model ids before saving output
        tiou_table.drop(columns=["gt_id", "sm_id"]).to_csv(f"{output_dir}/ac_tiou.csv")

        return phase_table, tiou_table, ac_te_table, ap_te_table, cm
