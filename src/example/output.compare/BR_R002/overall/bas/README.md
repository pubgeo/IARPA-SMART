# Broad Area Search Metrics

This folder contains the Broad Area Search metrics that
measure activity localization and tracking.

## best\_score\*.csv

-   This table contains the set of performance metrics that
    were calculated using the default values for the similarity thresholds.
    ~~the optimal similarity thresholds
    that maximize the F1 score. Thus, this table is the “best”
    row copied from the scoreboard table. If more than 1 row
    in the scoreboard table has the highest F1 score, the
    row with the more restrictive thresholds is considered
    to be the “best.” Area-based thresholds for
    polygon-to-polygon association are more restrictive at
    higher values.~~

-   The filename contains the parameter threshold values
    (tau, rho, etc.) that were used to determine the
    associations.

-   The columns in this table are the same as the columns in
    the [scoreboard](#scoreboardcsv) table. See the description of the
    scoreboard columns for more details.

## detections\*.csv

-   This table lists each of the ground truth sites, along
    with the [proposed](#proposalscsv) site model(s) that were associated
    with each truth site.

-   The filename contains the parameter threshold values
    (tau, rho, etc.) that were used to determine the
    associations.

- Many of the parameters in this table are also in the [failed associations](#failed_associationscsv) table.
    
| Columns              | Description          |
|-----------------------------|---------------|
| site type | The effective status type of the truth site, after the test harness makes adjustments to effectively “ignore” spatially small sites and sites that are not temporally bounded.
| truth site | The unique identifier of the truth site.
| site area | The area of the truth site (sq km), that is, the area of the geometric union of the truth site’s temporally bounded observations. This field should match the corresponding “polygon union area” in the [gt\_sites.csv](../../gt_sites.csv) file.
| matched site models | The proposed site model that is associated with the truth site. If multiple site models are listed, then they are over-segmented proposals, and the truth site is associated with their combination. If no site models are listed, the truth site is not associated with any proposals.
| detection score | This metric is deprecated and has been replaced by the spatial overlap metric.
| spatial overlap | The proportion of the truth site’s observations that have sufficient spatial similarity with the associated proposal. A truth observation must have a spatial similarity greater than or equal to the tau threshold in order to count toward this proportion. The proportion must be greater than or equal to the rho threshold in order for the truth site to meet the spatial requirements for association with the proposal. Note that the spatial overlap metric represents the *proportion* of the truth observations that have sufficient spatial similarity (e.g., sufficient IoU), not the IoU itself, nor an average IoU across all the observations.
| temporal IoT | Temporal Intersection over Truth: the ratio of the intersection of the truth site’s temporal date range and the proposal’s temporal range, to the truth’s site temporal range. Temporal date ranges are measured in calendar days, including both the start date and the end date of the range.
| temporal IoP | Temporal Intersection over Proposal: the ratio of the intersection of the truth site’s temporal date range and the proposal’s temporal range, to the proposal’s temporal range.
| site count | The number of proposal(s) that were associated with the truth site.
| association status | The impact of the truth site’s association (or lack thereof) on the F1 score (F1 = tp / (tp + ½fp + ½ fn)). The possible association statuses are shown below: <br><br>  tp: the truth site is detected and is a positive-type, so it counts as 1 true positive. <br> fp: the truth site is detected and is a negative-type, so it counts as 1 false positive. <br> fn: the truth site is not detected and is a positive-type, so it counts as 1 false negative. <br> 0: the truth site is not detected but is not a positive-type, or was detected and is an ignore-type, so it has no impact on the F1 score.
| associated | A Boolean that indicates whether or not the truth site was associated with any proposal(s).
| color code | An integer that is a function of the site’s site type and its association status, which indicates how the site’s polygon should be colored in a separate visualization application.

## f\_score\_table\*.csv

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

## failed\_associations\*.csv

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
| site type | Same as the corresponding column in the [detections](#detectionscsv) table.
| truth site | Same as the corresponding column in the [detections](#detectionscsv) table.
| proposal site | The proposed site model(s) that were compared against the truth site because they had some non-zero spatial and temporal overlap.
| spatial overlap | Same as the corresponding column in the [detections](#detectionscsv) table.
| temporal IoT | Same as the corresponding column in the [detections](#detectionscsv) table.
| temporal IoP | Same as the corresponding column in the [detections](#detectionscsv) table.
| truth activity start date | The date on which the truth site effectively begins activity. The effective date ranges are used to compute the temporal intersection between truth sites and proposed sites. A failed association due to insufficient temporal intersection can be assessed more precisely by comparing the start and the end activity dates of the sites.
| truth activity end date | The date on which the truth site effectively ends activity.
| proposal activity start date | The date on which the proposed site effectively begins activity.
| proposal activity end date | The date on which the proposed site effectively ends activity.

## scoreboard\*.csv

-   This table contains the aggregate performance metrics
    calculated at varying parameter threshold levels,
    including the precision, recall, and F1 score. 
    
-   Each column of the scoreboard represents a specific
    performance metric. The individual columns of the
    scoreboard are also duplicated and saved in separate CSV
    files for convenience.

-   The filename contains the parameter threshold values
    (tau, rho, etc.) that were used to determine the
    associations.

| Columns              | Description          |
|----------------------|----------------------|
| tau | The minimum similarity score that is necessary to spatially match a single proposed polygon with a single ground truth polygon. Also known as the “association threshold”. Defaults to 0.2. Spatial similarity metrics include IoU (Intersection area over polygon Union area) and IoT (Intersection area over Truth polygon area).
| rho | The minimum proportion of polygons in a ground truth site that need to be associated with the polygon(s) in a proposed site in order for the ground truth site to be detected by that proposed site. Also known as the “detection threshold.” <br> Defaults to 0.5.
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
| proposed sites | The effective number of proposed site models (might be less than the number of proposed annotations because of over-segmentation, which combines annotations into a single site model).
| total sites | The total number of sites. total sites = truth sites + proposed sites.
| truth slices | The total number of observations in the truth sites.
| proposed slices | The total number of observations in the proposed site models (might be less than the number of observations in the proposed annotations because of over-segmentation, which combines observations into a single observation).
| precision | precision = tp sites / (tp sites + fp sites).
| recall (PD) | Also known as the probability of detection. recall = tp sites / (tp sites + fn sites).
| F1 score | F1 = tp sites / (tp sites + ½ fp sites + ½ fn sites).
|spatial FAR | Spatial false alarm rate = fp sites / region model area.
| temporal FAR | Temporal false alarm rate = fp sites / the length of the region model’s temporal range, measured in calendar days.
| images FAR | Image-based false alarm rate = fp sites / the number of observations in the proposed site models.

## site\_types\*.csv

-   This table contains the numerical count of proposed site
    models that are associated with each type of truth site.
    A proposed site model that does not associate with any
    of the truth sites is categorized in this table as a
    “false alarm.”

-   The filename contains the parameter threshold values
    (tau, rho, etc.) that were used to determine the
    associations.

## proposals\*.csv

-   This table lists each of the proposed site models, along
    with the truth site(s) that were associated with each
    proposal.

-   The filename contains the parameter threshold values
    (tau, rho, etc.) that were used to determine the
    associations.

| Columns              | Description          |
|----------------------|----------------------|
| site model | The unique identifier of the proposal.
| site area | The area (sq km) of the proposal, that is, the area of the geometric union of the proposal’s temporally bounded observations.
| matched truth sites | The truth site(s), if any, that the proposal associated with and detected. If multiple truth sites are listed, the proposal is considered to be “under-segmented” and it detected each of the listed truth sites. If empty, the proposal did not detect any truth sites and is counted as a false alarm.
| site count | The number of truth sites that the proposal detected.
| association status | The impact of the proposal’s association (or lack thereof) on the F1 score (F1 = tp / (tp + ½fp + ½fn)). <br><br>  tp: the proposal detected a positive-type truth site. <br>  fp: the proposal did not detect a positive-type, nor an ignore-type truth site. <br>  0: the proposal detected an ignore-type truth site.
| associated | A Boolean that indicates whether or not the proposal was associated with any truth site(s).
| color code | An integer that is a function of the site’s site type and its association status, which indicates how the site’s polygon should be colored in a separate visualization application.
