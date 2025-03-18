
# Example Inputs

Example inputs for the test harness are saved in the [input](./input) directory:
* Ground truth annotations are located in the [truth](./input/truth) directory.
* Site model proposals are located in the [proposals](./input/proposals/) directory.

# Example Test Harness Run

* Edit [example_run.sh](example_run.sh) and update the `REPO` variable to point to the parent directory of this code repository.
* Run [example_run.sh](example_run.sh) and verify correct output by comparing the generated output to the expected output in `output.compare`.
* This comparison can be done using the `diff` command: `diff -r example/output.compare/ example/output/`

# Example Outputs

The SMART test harness compares proposed site models against ground truth annotations, computes quantitative metrics to measure their similarity, and writes them to the local file system as CSV files. Example output files, generated using both polygon-based and point-based ground truth annotations, are saved in [output.compare](output.compare).

* Output files related to [annotations](#annotations), which are the primary inputs ingested by the test harness:
    * Ground truth annotations are logged in the [gt_sites.csv](#gt_sitescsv) file.
    * Proposed site models are logged in the [sm_sites.csv](#sm_sitescsv) file.
* Output files related to performance metrics:
    * [Metric subset directories](#performance-metric-subsets)
        * [Broad area search metrics](#broad-area-search-metrics)
        * [Activity classification and prediction metrics](#phase-activity-metrics)

## Troubleshooting the Outputs

Some suggestions for diagnosing unexpected results in the output files and avoiding common pitfalls:

* An empty [gt_sites.csv](#gt_sitescsv) file indicates that the test harness did not ingest any annotations to use as ground truth sites.
    * Check the paths specified by the `--gt_dir` (if running a polygon-based evaluation) or the `--gt_points file` (if running a point-based evaluation) [command line arguments](../README.md/#command-line-arguments).
    * Each truth site must have the `--roi` value as a substring somewhere in its annotation filename (if running a polygon-based evaluation) or in its `site_id` attribute (if running a point-based evaluation) in order to be ingested into the test harness. Consider specifying the `--roi` as the 2-letter country code (the prefix of the region ID) instead of the full region ID, or leaving it as an empty string (the default value) in order to ingest all geojson files in the directory or in the point annotation file.
    * Each site must be located within the region model's spatial bounds in order to be ingested, so verify the location of the sites relative to the boundary of the region model specified by `--rm_path`.
    * If `--rm_path` is pointing to a full region model that contains site summaries, each truth site ID must be listed somewhere in the site summaries in order to be included in the evaluation. (An empty region model will include all truth sites.)

* An empty [sm_sites.csv](#sm_sitescsv) file indicates that the test harness did not ingest any annotations to use as site model proposals.
    * Check the path specified by the `--sm_dir` [command line argument](../README.md/#command-line-arguments) to verify that the directory contains geojson annotation files.
    * Each proposal site must have the `--roi` value as a substring somewhere in its annotation filename in order to be ingested into the test harness. Consider specifying the `--roi` as the 2-letter country code (the prefix of the region ID) instead of the full region ID, or leaving it as an empty string (the default value) in order to ingest all geojson files in the directory.
    * Each site must be located within the region model's spatial bounds in order to be ingested, so verify the location of the sites relative to the boundary of the region model specified by `--rm_path`.
    * The `--proposal_bounded_filter` argument, if specified, will only include proposals with the specified [temporally bounded status type](#performance-metric-subsets), and will include all other proposals. Try removing this argument to include all proposals of any temporal duration relative to the region model.

* An empty [detections.csv](#detectionscsv) file indicates that the ingested proposals did not associate with any of the ingested truth sites.
    * Try relaxing the [thresholds](../README.md/#sweeping-thresholds) to make the association requirements less demanding (use smaller threshold values for area-based / polygon-based evaluation and larger threshold values for distance-based / point-based evaluation).
    * Compare the status types of the ground truth annotations with the status types that are listed in the `--gt_whitelist` and the `--gt_blacklist` to verify that they are not being filtered out inadvertently.

* An empty [proposals.csv](#proposalscsv) file indicates that none of the ingested proposals were eligible for association.
    * Compare the status types of the proposed geojson annotations with the status types that are listed in the `--sm_whitelist` and the `--sm_blacklist` to verify that they are not being filtered out inadvertently.

* Performance [metric scores](#scoreboardcsv) of zero (e.g., F1=0) indicate that there were no successful detections of positive-type sites (that is, no true positives).
    * Try relaxing the [thresholds](../README.md/#sweeping-thresholds) to make the association requirements less demanding (use smaller threshold values for area-based / polygon-based evaluation and larger threshold values for distance-based / point-based evaluation).

* An empty [phase_activity](#phase-activity-metrics) directory indicates that the proposals did not detect any positive-type truth site stacks.
    * Only positive-type site stacks are considered for activity classification and prediction metrics, so detections of other types of site stacks will not populate this directory. This is intended behavior.
    * Points do not have phase labels, so a point-based evaluation will leave this directory empty, even if positive-type points are detected. This is intended behavior.

* Missing output files for polygon-based evaluation may also indicate a test harness bug.
    * Try running the test harness in `--serial` mode instead of using the default `--parallel` processing [command line argument](../README.md/#command-line-arguments), in order to reveal error messages that could potentially be coming from one of the subprocesses. This additional information may aid with debugging.

## Annotations

### gt\_sites.csv

This table lists each of the ground truth site annotations that are ingested into the test harness via the `-–gt_dir` or the `--gt_points_file` [command line arguments](../README.md#command-line-arguments).

| Columns              | Description          |
|-----------------------------|---------------|
| id | The unique identifier of the truth site.
| status | The annotated status type of the truth site as specified in the annotation file. This is irrespective of the site's spatial size or its temporal range relative to the region model.
| polygon union area | The area (sq km) of the truth site stack. Specifically, the area of the geometric union of the truth site's temporally bounded polygon observations. (An observation date is temporally bounded if it occurs on or between the region model's start and end dates.) <br><br>This measurement is what the test harness generally uses for metrics involving a site's (approximate) area.
| maximum polygon area | The area (sq km) of the truth site stack's largest temporally bounded polygon. This measurement is used to determine whether a truth site is small enough to be "ignored" for the purposes of site association and scoring.
| confidence score | This defaults to 1.0 for a ground truth site.
| first observation | The site's first temporally bounded observation date.
| start date | The annotated site-level start date or the region model's start date, whichever occurs later.
| earliest start | For positive truth sites with phase labels (site types 1 and 2), this field is the earliest possible start date of the observed activity, that is, the latest 'No Activity' observation date that occurs before the first 'Site Preparation' or 'Active Construction' observation date, when activity definitely begins. <br><br>If this 'No Activity' observation date occurs before the start of the region model, then the earliest start date (of *observed* activity) is effectively the region model's start date. If there is no such 'No Activity' observation date, this field defaults to the "latest start" date. This field is not applicable for other types of truth sites and is left empty.
| latest start | For positive truth sites with phase labels (site types 1 and 2), this field is the latest possible start date of the observed activity, that is, the earliest 'Site Preparation' or 'Active Construction' observation date in the site. If this date occurs before the region model start date, then the latest start date (of *observed* activity) is effectively the region model's start date (and the test harness will also update this site's status to positive\_unbounded).
| start activity | Used to denote the start of a site's temporal range for the purposes of site association. Defaults to the date of the "latest start" for positive truth sites with phase labels, and to the site-level "start date" for all other site types.
|end activity | Used to denote the end of a site's temporal range for the purposes of site association. For positive truth sites with phase labels, this field is the end of the site's observed activity, and is set to the region model's end date or to the first 'Post Construction' observation date, whichever occurs first. For all other site types, this field defaults to the site-level "end date".
| end date | The annotated site-level end date or the region model's end date, whichever occurs earlier.
| last observation | The site's last temporally bounded observation date.
| model type | Indicates whether the annotation is a site point or a polygon site stack.

### sm\_sites.csv

This table lists each of the proposed site models that are ingested into the test harness via the `-–sm_dir` [command line argument](../README.md#command-line-arguments).

| Columns              | Description          |
|-------------------------------|-------------|
| id |The unique identifier of the proposed site.
| status | A label that indicates whether the proposal should be scored by the test harness or ignored. A proposal annotated as "system\_confirmed" will be compared to the ground truth sites; a proposal with any other label, such as "system\_rejected", will be effectively ignored.
| polygon union area | The area (sq km) of the proposed site, that is, the geometric union of the site's temporally bounded polygon observations. This measurement is what the test harness generally uses for metrics involving a site's (approximate) area.
| maximum polygon area | The area (sq km) of the proposed site's largest temporally bounded polygon.
| confidence score | The annotator's level of confidence in the site proposal, ranging from 0 (least confident) to 1 (most confident) that the proposal correctly captures actual activity of interest.
| first observation | The site's first temporally bounded observation date.
| start date | The annotated site-level start date or the region model's start date, whichever occurs later.
| earliest start | This field is not used for proposed sites and is left empty.
| latest start | This field is not used for proposed sites and is left empty.
| start activity | Used to denote the start of a site's temporal range for the purposes of site association. This field defaults to the same date as the "start date".
| end activity | Used to denote the start of a site's temporal range for the purposes of site association. This field defaults to the same date as the "end date".
| end date | The annotated site-level end date or the region model's end date, whichever occurs earlier.
| last observation | The site's last temporally bounded observation date.
| model type | Indicates whether the annotation is a site point or a polygon site stack.

## Performance Metric Subsets

The test harness can filter and select up to 3 different subsets of the ground truth sites before comparing them with the proposed site models and computing the [performance](#example-outputs) metrics.

The "overall" metrics are computed on the subset of truth sites that begin within the region
model's start date and end date (types C and D). <br>The "completed" metrics are computed on the subset of truth sites that begin *and end* within the region model's start date and end date (type C). <br>The "partial" metrics are computed on the subset of truth sites that begin but do
*not* end within the region model's start date and end date (type D).

<img src="./temporal_bounds.png" style="width:4.58354in;height:2.01117in" />

<br>The test harness computes the full set of metrics on each of these 3
subsets and writes them to their respective folders:

-   completed/

    -   This folder contains the full set of test harness metrics
        computed on the subset of truth sites that begin and complete
        their activity within the region model's temporal bounds. All
        other truth sites are effectively ignored.

    -   In general, this folder has the same kind of metrics content as
        the "overall" folder; however, some files might not appear if
        there were no associations with the "completed" subset of truth
        sites. For example, the `phase_activity` folder will be empty if there were no dections of the fully completed positive truth sites.

-   partial/

    -   This folder contains the full set of test harness metrics
        computed on the subset of truth sites that began but did *not*
        complete their activity within the region model's temporal
        bounds. All other truth sites are effectively ignored.

    -   In general, this folder has the same kind of metrics content as
        the "overall" folder; however, some files might not appear if
        there were no associations with the "partial" subset of truth
        sites. For example, the `phase_activity` folder will be empty if there were no dections of the partially completed positive truth sites.

-   overall/

    -   This folder contains the full set of test harness metrics
        computed on the subset of truth sites that began their activity
        within the region model's temporal bounds. All other truth sites
        are effectively ignored.

Note that proposals can also be filtered out from the evaluation based on their temporal duration relative to the region model's temporal bounds. The `--proposal_bounded_filter` command line argument can be specified as a string of letters (A, B, C, D, and/or E) corresponding to the site types above. A proposal will only be included in the evaluation if its type of temporal duration is listed in the `--proposal_bounded_filter` argument.

## Broad Area Search Metrics

Broad Area Search (BAS) metrics measure activity localization and tracking.

### best\_score\*.csv

-   This table contains the set of performance metrics that
    were calculated using the optimal similarity thresholds
    that maximize the F1 score. Thus, this table is the "best"
    row copied from the scoreboard table. If more than 1 row
    in the scoreboard table has the highest F1 score, the
    row with the more restrictive thresholds is considered
    to be the "best." Area-based thresholds for
    polygon-to-polygon association are more restrictive at
    higher values, whereas distance-based thresholds for
    point-to-polygon association are more restrictive at
    lower values.

-   The filename contains the parameter threshold values
    (tau, rho, etc.) that were used to determine the
    associations.

-   The columns in this table are the same as the columns in
    the [scoreboard](#scoreboardcsv) table. See the description of the
    scoreboard columns for more details.

### detections\*.csv

-   This table lists each of the ground truth sites, along
    with the proposed site model(s) that were associated
    with each truth site.

-   The filename contains the parameter threshold values
    (tau, rho, etc.) that were used to determine the
    associations.

| Columns              | Description          |
|-----------------------------|---------------|
| site type | The effective status type of the truth site, after the test harness makes adjustments to effectively "ignore" spatially small sites and sites that are not temporally bounded.
| truth site | The unique identifier of the truth site.
| site area | The area of the truth site (sq km), that is, the area of the geometric union of the truth site's temporally bounded observations. This field should match the corresponding "polygon union area" in the [gt_sites.csv](#gt_sitescsv) file.
| matched site models | The proposed site model that is associated with the truth site. If multiple site models are listed, then they are over-segmented proposals, and the truth site is associated with their combination. If no site models are listed, the truth site is not associated with any proposals.
| spatial overlap | The proportion of the truth site's observations that have sufficient spatial similarity with the associated proposal. A truth observation must have a spatial similarity greater than or equal to the tau threshold in order to count toward this proportion. The proportion must be greater than or equal to the rho threshold in order for the truth site to meet the spatial requirements for association with the proposal. Note that the spatial overlap metric represents the *proportion* of the truth observations that have sufficient spatial similarity (e.g., sufficient IoU), not the IoU itself, nor an average IoU across all the observations.
| temporal IoT | Temporal Intersection over Truth: the ratio of the intersection of the truth site's temporal date range and the proposal's temporal range, to the truth's site temporal range. Temporal date ranges are measured in calendar days, including both the start date and the end date of the range.
| temporal IoP | Temporal Intersection over Proposal: the ratio of the intersection of the truth site's temporal date range and the proposal's temporal range, to the proposal's temporal range.
| minimum spatial distance | The geometric distance (m) from the ground truth point to the nearest point in the geometric union of the proposed site model's temporally bounded polygon observations. If the proposal polygon contains the ground truth point, then the minimum spatial distance is zero. Only used for point-to-polygon comparisons and associations.
| central spatial distance | The geometric distance (m) from the ground truth point to the center of mass (centroid) of the geometric union of the proposed site model's temporally bounded polygon observations. Only used for point-to-polygon comparisons and associations.
| maximum spatial distance | The geometric distance (m) from the ground truth point to the furthest point on the polygon boundary of the geometric union of the proposed site model's temporally bounded polygon observations. Only used for point-to-polygon comparisons and associations.
| minimum temporal distance | The number of calendar days between the ground truth point date and the nearest date in the proposal's temporal date range. If the proposal's temporal range contains the ground truth point date, then the minimum temporal distance is zero. Only used for point-to-polygon comparisons and associations.
| central temporal distance | The number of calendar days between the ground truth point date and the middle date in the proposal's temporal date range. Only used for point-to-polygon comparisons and associations.
| maximum temporal distance | The number of calendar days between the ground truth point date and the furthest date in the proposal's temporal date range. Only used for point-to-polygon comparisons and associations.
| site count | The number of proposal(s) that were associated with the truth site.
| association status | The impact of the truth site's association (or lack thereof) on the F1 score (F1 = tp / (tp + ½fp + ½ fn)). The possible association statuses are shown below: <br><br>  tp: the truth site is detected and is a positive-type, so it counts as 1 true positive. <br> fp: the truth site is detected and is a negative-type, so it counts as 1 false positive. <br> fn: the truth site is not detected and is a positive-type, so it counts as 1 false negative. <br> 0: the truth site is not detected but is not a positive-type, or was detected and is an ignore-type, so it has no impact on the F1 score.
| associated | A Boolean that indicates whether or not the truth site was associated with any proposal(s).
| color code | An integer that is a function of the site's site type and its association status, which indicates how the site's polygon should be colored in a separate visualization application.
| model type | Indicates whether the annotation is a site point or a polygon site stack.

### f\_scores.csv

-   This table contains the F beta scores at varying
    thresholds of beta, to weight precision and recall
    unequally. The F1 score (beta=1) is the default
    performance metric, which weights precision and recall
    equally. A value of beta *b* &gt; 1 favors recall by a
    factor of *b*, whereas a value of *b* &lt; 1 favors
    precision by a factor of *b*. For example, beta = 2
    gives the recall twice as much weight as the precision
    when computing the F score, whereas beta = ½ gives the
    precision twice as much weight as the recall.

### failed\_associations\*.csv

-   This table lists every combination of ground truth site
    and proposed site model(s) that have spatial and
    temporal overlap that are nonzero yet insufficient for
    association, based on the association parameter
    thresholds.

-   A ground truth site can be listed in multiple rows in this
    table if there are multiple different combinations of
    proposals that have nonzero spatial and temporal overlap
    with it. A ground truth site can also be listed in both the
    detections table and in the failed associations table if
    there is a proposal, or a combination of proposals, that has
    overlap with the truth site sufficient to meet the association
    thresholds, as well as another proposal or combination
    of proposals that does not have overlap sufficient to
    meet the thresholds.

-   The filename contains the parameter threshold values
    that were used to determine the attempted yet failed
    associations. Each row of the table has one or more
    similarity or distance values that fails to meet the
    corresponding non-None threshold in the filename.

-   Many of the parameters in this table are also in the [detections](#detectionscsv) table, where their descriptions can be located.

| Columns              | Description          |
|----------------------|----------------------|
| Site type | Same as the corresponding column in the detections table.
| Truth site | Same as the corresponding column in the detections table.
| Proposal site | The proposed site model(s) that were compared against the truth site because they had some non-zero spatial and temporal overlap.
| Spatial overlap | Same as the corresponding column in the detections table.
| Temporal IoT | Same as the corresponding column in the detections table.
| Temporal IoP | Same as the corresponding column in the detections table.
| Minimum spatial distance | Same as the corresponding column in the detections table.
| Central spatial distance | Same as the corresponding column in the detections table.
| Maximum spatial distance | Same as the corresponding column in the detections table.
| Minimum temporal distance | Same as the corresponding column in the detections table.
| Central temporal distance | Same as the corresponding column in the detections table.
| Maximum temporal distance | Same as the corresponding column in the detections table.
| Truth activity start date | The date on which the truth site effectively begins activity. The effective date ranges are used to compute the temporal intersection between truth sites and proposed sites. A failed association due to insufficient temporal intersection can be assessed more precisely by comparing the start and the end activity dates of the sites.
| Truth activity end date | The date on which the truth site effectively ends activity.
| Proposal activity start date | The date on which the proposed site effectively begins activity.
| Proposal activity end date | The date on which the proposed site effectively ends activity.
| Model type | Same as the corresponding column in the detections table.

### scoreboard.csv

-   This table contains the aggregate performance metrics
    calculated at varying parameter threshold levels,
    including the precision, recall, and F1 score.

| Columns              | Description          |
|----------------------|----------------------|
| tp sites | The total number of positive ground truth sites that are detected. These positive detections are what get counted favorably toward the F1 score. tp sites = tp exact + tp under + tp over
| tp exact | The number of detections made by matching exactly 1 positive ground truth site with exactly 1 proposal (using neither over-segmentation nor under-segmentation).
| tp under | The number of detections made by using under-segmentation, in which a single proposal is associated with multiple ground truth sites. tp under = tp under IoU + tp under IoT
| tp under IoU | The number of detections made by using under-segmentation and the IoU similarity score.
| tp under IoT | The number of detections made by using under-segmentation and the IoT similarity score (used if the IoU similarity score is insufficient to meet the spatial association thresholds).
| tp over | The number of detections made by using over-segmentation, in which a single ground truth site is associated with multiple proposals combined together.
| fp sites | The number of proposed sites that did not detect a positive ground truth site.
| fp area (sq km) | The area of the geometric union of the false positive sites.
| ffpa (sq km) | The fractional (normalized) false positive area. ffpa = fp area / region model area.
| proposal area (sq km) | The area of the geometric union of the proposed sites.
| fpa (sq km) | The fractional (normalized) positive area. fpa = proposal area / region model area.
| fn sites | The number of positive ground truth sites that were not detected.
| truth annotations | The number of ground truth geojson annotation files.
| truth sites | The effective number of positive ground truth sites that should be detected. Truth sites = tp sites + fn sites.
| proposed annotations | The number of proposed geojson annotation files.
| confident proposals | The number of proposed geojson annotation files that meet the confidence score threshold.
| proposed sites | The effective number of proposed site models (might be less than the number of proposed annotations because of over-segmentation, which combines annotations into a single site model).
| total sites | The total number of sites. total sites = truth sites + proposed sites.
| truth slices | The total number of observations in the truth sites.
| proposed slices | The total number of observations in the proposed site models (might be less than the number of observations in the proposed annotations because of over-segmentation, which combines observations into a single observation).
| precision | precision = tp sites / (tp sites + fp sites).
| recall (PD) | Also known as the probability of detection. recall = tp sites / (tp sites + fn sites).
| F1 score | F1 = tp sites / (tp sites + ½ fp sites + ½ fn sites).
|spatial FAR | Spatial false alarm rate = fp sites / region model area.
| temporal FAR | Temporal false alarm rate = fp sites / the length of the region model's temporal range, measured in calendar days.
| images FAR | Image-based false alarm rate = fp sites / the number of observations in the proposed site models.

### site\_types\*.csv

-   This table contains the numerical count of proposed site
    models that are associated with each type of truth site.
    A proposed site model that does not associate with any
    of the truth sites is categorized in this table as a
    "false alarm."

-   The filename contains the parameter threshold values
    (tau, rho, etc.) that were used to determine the
    associations.

### proposals\*.csv

-   This table lists each of the proposed site models, along
    with the truth site(s) that were associated with each
    proposal.

-   The filename contains the parameter threshold values
    (tau, rho, etc.) that were used to determine the
    associations.

| Columns              | Description          |
|----------------------|----------------------|
| Site model | The unique identifier of the proposal.
| Site area | The area (sqm km) of the proposal, that is, the area of the geometric union of the proposal's temporally bounded observations.
| Matched truth sites | The truth site(s), if any, that the proposal associated with and detected. If multiple truth sites are listed, the proposal is considered to be "under-segmented" and it detected each of the listed truth sites. If empty, the proposal did not detect any truth sites and is counted as a false alarm.
| Site count | The number of truth sites that the proposal detected.
| Association status | The impact of the proposal's association (or lack thereof) on the F1 score (F1 = tp / (tp + ½fp + ½fn)). <br>  tp: the proposal detected a positive-type truth site. <br>  fp: the proposal did not detect a positive-type, nor an ignore-type truth site. <br>  0: the proposal detected an ignore-type truth site.
| associated | A Boolean that indicates whether or not the proposal was associated with any truth site(s).
| color code | An integer that is a function of the site's site type and its association status, which indicates how the site's polygon should be colored in a separate visualization application.


## Phase Activity Metrics

Activity Classification and Activity Prediction metrics are computed on the positive truth sites with phase labels (site types 1 and 2) that were successfully detected. These metrics cannot be computed for sites that do not have phase labels, such as positive pending sites and point sites. If none of the proposals detect any positive sites with phase labels, then this folder will be empty.

### ac\_phase\_table.csv

-   Each column of this table compares the activity
    classification phase label from each of the observations
    of the detected positive truth site with the
    corresponding observation phase label from the proposal
    that associated with the truth site. If the true label
    and the proposed label differ, then they will be listed
    as *true label vs. proposed label*. If the labels match,
    then the label will simply be listed once. If a phase
    label was not annotated or proposed on a particular
    observation date, then it will be listed as "n/a".

### ac\_confusion\_matrix\*.csv

-   This table constructs a confusion matrix from the phases
    in the activity classification phase table. Each row
    denotes a ground truth phase label, and each column
    denotes a predicted phase label.

-   There is an individual ac\_confusion\_matrix\*.csv file
    for each of the successfully detected positive truth
    sites, that is, for each column of the activity
    classification phase table. The
    ac\_confusion\_matrix\_all\_sites.csv file aggregates
    the individual matrices to compute the overall matrix
    for the entire region.

### ac\_f1\*.csv

-   This table computes the F1 scores for each phase label
    in the set of successfully detected positive ground
    truth sites, using the activity classification confusion
    matrices. There is an individual ac\_f1\*.csv file for
    each of the successfully detected positive truth sites.

-   The ac\_f1\_all\_sites.csv file aggregates the
    individual per-phase F1 scores to compute an average F1
    score for the entire region. To compute an overall F1
    score across all of the truth sites, both micro and
    macro averaging approaches are used. The macro average
    assigns an equal weight to the per-site F1 score from
    each of the truth sites, regardless of the number of its
    observations. The micro average computes the overall F1
    score by combining all of the observations from the
    truth sites, such that each individual observation is
    given equal weight toward the overall score.

### ac\_tiou.csv

-   This table measures the temporal intersection between a
    positive detected truth site and its associated proposal
    for each activity phase that is annotated in the truth
    site. Each row in this table is a truth site vs.
    proposed site pair that represents a column in the
    activity classification phase table. Note that it is the
    overall temporal intersection, regardless of phase
    label, that is used to perform the actual association
    between a truth site and a proposal. It is possible for
    the *per-phase* temporal intersections in this table to
    be very low, even though the overall temporal
    intersection were sufficient for association.

### ac\_temporal\_error.csv

-   This file contains the "temporal error" for each
    activity phase that is annotated in each of the
    successfully detected positive ground truth sites. The
    temporal error of a phase is the difference in calendar
    days between the onset of the phase in the ground truth
    annotation and the onset of that phase in the proposed
    site model. In general, the "onset" of a phase in a site
    model is the first occurrence of that phase label in the
    temporally bounded observations. For a site that has
    observations with multiple labels, the onset of the Post
    Construction phase is the first observation date in
    which *all* of its label(s) are Post Construction. The
    onset of any other phase is the first observation date
    in which *any* of its label(s) belong to that particular
    phase.

-   There is an individual ac\_temporal\_error\*.csv file
    for each of the successfully detected positive truth
    sites. The ac\_temporal\_error.csv file aggregates the
    individual temporal errors to compute the overall
    temporal errors for the entire region, on all of the
    successfully detected positive truth sets and on certain
    subsets of those sites.

| Rows              | Description          |
|-----------------------------|------------|
| worst mean days (all detections) | The average of the signed temporal errors across all of the successfully detected positive truth sites, in the worst-case scenario that maximizes the temporal error. In the worst-case scenario, the effective onset of the given activity phase in the truth site is as distant as possible from the onset of that activity in the proposed site, while still between the annotated onset of activity and the previous annotated observation date in the truth site (also known as the "phase gap").
| worst std days (all detections) | The standard deviation of the signed temporal errors across all of the successfully detected positive truth sites, in the worst-case scenario that maximizes the temporal error.
| worst mean days (absolute value of all detections) | The average of the magnitudes of the temporal errors across all of the successfully detected positive truth sites, in the worst-case scenario that maximizes the temporal error.
| worst std days (absolute value of all detections) | The standard deviation of the magnitude of the temporal errors across all of the successfully detected positive truth sites, in the worst-case scenario that maximizes the temporal error.
| mean days (all detections)| The average of the signed temporal errors across all of the successfully detected positive truth sites.
| std days (all detections) | The standard deviation of the signed temporal errors across all of the successfully detected positive truth sites.
| mean days (absolute value of all detections) | The average of the magnitude of the temporal errors across all of the successfully detected positive truth sites.
| std days (absolute value of all detections) | The standard deviation of the magnitude of the temporal errors across all of the successfully detected positive truth sites.
| best mean days (all detections) | The average of the signed temporal errors across all of the successfully detected positive truth sites, in the best-case scenario that minimizes the temporal error. In the best-case scenario, the effective onset of the given activity phase in the truth site is as close as possible to the onset of that activity in the proposed site, while still between the annotated onset of activity and the previous annotated observation date in the truth site (also known as the "phase gap"). If the proposed onset of activity is within the phase gap, the best-case temporal error is zero.
| best std days (all detections) | The standard deviation of the signed temporal errors across all of the successfully detected positive truth sites, in the best-case scenario that minimizes the temporal error.
| best mean days (absolute value of all detections) | The average of the magnitude of temporal errors across all of the successfully detected positive truth sites, in the best-case scenario that minimizes the temporal error.
| best std days (absolute value of all detections) | The standard deviation of the magnitude of temporal errors across all of the successfully detected positive truth sites, in the best-case scenario that minimizes the temporal error.
| mean days (early detections) | The average of the negative temporal errors, across the successfully detected positive sites in which the proposed onset of activity occurs before the annotated onset of activity.
| std days (early detections) | The standard deviation of the negative temporal errors, across the successfully detected positive sites in which the proposed onset of activity occurs before the annotated onset of activity.
| mean days (late detections) | The average of the positive temporal errors, across the successfully detected positive sites in which the proposed onset of activity occurs after the annotated onset of activity.
| std days (late detections) | The standard deviation of the positive temporal errors, across the successfully detected positive sites in which the proposed onset of activity occurs after the annotated onset of activity.
| all detections | The number of successfully detected positive truth sites in which the truth site and the proposal that detected it are both labeled with the column's phase somewhere in their temporally bounded observations. This is the number of sites on which the temporal error for that phase can be computed. <br>  All detections = early + late + perfect. <br>  All detections + missing proposals + missing truth sites = the total number of successfully detected positive truth sites.
| early | The number of successfully detected positive truth sites in which the onset of the activity phase is earlier in the proposal than it is in the truth site.
| late | The number of successfully detected positive truth sites in which the onset of the activity phase is later in the proposal than it is in the truth site.
| perfect | The number of successfully detected positive truth sites in which the onset of the activity phase is the exact same calendar date in the proposal as it is in the truth site.
| missing proposals | The number of successfully detected positive truth sites that were detected by a proposal not labeled with the given activity phase. The temporal error for this phase cannot be calculated for these truth sites.
| missing truth sites | The number of successfully detected positive truth sites that were not labeled with the given activity phase. The temporal error for this phase cannot be calculated for these truth sites.

### ap\_temporal\_error.csv

-   This file measures the temporal error between the
    successfully detected positive ground truth sites and
    their associated proposals using the site-level
    predicted phase transition label and predicted phase
    transition date, instead of the phase labels in the
    observations. In general, it has the same kind of
    content as the [ac\_temporal\_error](#ac_temporal_errorcsv) table.
