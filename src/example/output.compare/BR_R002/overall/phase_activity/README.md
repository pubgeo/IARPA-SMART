# Phase Activity Metrics

This folder contains the Activity Classification and
Activity Prediction metrics. These metrics are computed on
the positive truth sites with phase labels (site types 1
and 2) that were successfully detected. These metrics cannot
be computed for sites that do not have phase labels, such as
positive pending sites and point sites. If none of the
proposals detect any positive sites with phase labels, then
this folder will be empty.

## ac\_phase\_table.csv

-   Each column of this table compares the activity
    classification phase label from each of the observations
    of the detected positive truth site with the
    corresponding observation phase label from the proposal
    that associated with the truth site. If the true label
    and the proposed label differ, then they will be listed
    as *true label vs. proposed label*. If the labels match,
    then the label will simply be listed once. If a phase
    label was not annotated or proposed on a particular
    observation date, then it will be listed as “n/a”.

## ac\_confusion\_matrix\*.csv

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

## ac\_f1\*.csv

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

## ac\_tiou.csv

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

## ac\_temporal\_error.csv

-   This file contains the “temporal error” for each
    activity phase that is annotated in each of the
    successfully detected positive ground truth sites. The
    temporal error of a phase is the difference in calendar
    days between the onset of the phase in the ground truth
    annotation and the onset of that phase in the proposed
    site model. In general, the “onset” of a phase in a site
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
| worst mean days (all detections) | The average of the signed temporal errors across all of the successfully detected positive truth sites, in the worst-case scenario that maximizes the temporal error. In the worst-case scenario, the effective onset of the given activity phase in the truth site is as distant as possible from the onset of that activity in the proposed site, while still between the annotated onset of activity and the previous annotated observation date in the truth site (also known as the “phase gap”).
| worst std days (all detections) | The standard deviation of the signed temporal errors across all of the successfully detected positive truth sites, in the worst-case scenario that maximizes the temporal error.
| worst mean days (absolute value of all detections) | The average of the magnitudes of the temporal errors across all of the successfully detected positive truth sites, in the worst-case scenario that maximizes the temporal error.
| worst std days (absolute value of all detections) | The standard deviation of the magnitude of the temporal errors across all of the successfully detected positive truth sites, in the worst-case scenario that maximizes the temporal error.
| mean days (all detections)| The average of the signed temporal errors across all of the successfully detected positive truth sites.
| std days (all detections) | The standard deviation of the signed temporal errors across all of the successfully detected positive truth sites.
| mean days (absolute value of all detections) | The average of the magnitude of the temporal errors across all of the successfully detected positive truth sites.
| std days (absolute value of all detections) | The standard deviation of the magnitude of the temporal errors across all of the successfully detected positive truth sites.
| best mean days (all detections) | The average of the signed temporal errors across all of the successfully detected positive truth sites, in the best-case scenario that minimizes the temporal error. In the best-case scenario, the effective onset of the given activity phase in the truth site is as close as possible to the onset of that activity in the proposed site, while still between the annotated onset of activity and the previous annotated observation date in the truth site (also known as the “phase gap”). If the proposed onset of activity is within the phase gap, the best-case temporal error is zero.
| best std days (all detections) | The standard deviation of the signed temporal errors across all of the successfully detected positive truth sites, in the best-case scenario that minimizes the temporal error.
| best mean days (absolute value of all detections) | The average of the magnitude of temporal errors across all of the successfully detected positive truth sites, in the best-case scenario that minimizes the temporal error.
| best std days (absolute value of all detections) | The standard deviation of the magnitude of temporal errors across all of the successfully detected positive truth sites, in the best-case scenario that minimizes the temporal error.
| mean days (early detections) | The average of the negative temporal errors, across the successfully detected positive sites in which the proposed onset of activity occurs before the annotated onset of activity.
| std days (early detections) | The standard deviation of the negative temporal errors, across the successfully detected positive sites in which the proposed onset of activity occurs before the annotated onset of activity.
| mean days (late detections) | The average of the positive temporal errors, across the successfully detected positive sites in which the proposed onset of activity occurs after the annotated onset of activity.
| std days (late detections) | The standard deviation of the positive temporal errors, across the successfully detected positive sites in which the proposed onset of activity occurs after the annotated onset of activity.
| all detections | The number of successfully detected positive truth sites in which the truth site and the proposal that detected it are both labeled with the column’s phase somewhere in their temporally bounded observations. This is the number of sites on which the temporal error for that phase can be computed. <br><br>  All detections = early + late + perfect. <br>  All detections + missing proposals + missing truth sites = the total number of successfully detected positive truth sites. 
| early | The number of successfully detected positive truth sites in which the onset of the activity phase is earlier in the proposal than it is in the truth site.
| late | The number of successfully detected positive truth sites in which the onset of the activity phase is later in the proposal than it is in the truth site.
| perfect | The number of successfully detected positive truth sites in which the onset of the activity phase is the exact same calendar date in the proposal as it is in the truth site.
| missing proposals | The number of successfully detected positive truth sites that were detected by a proposal not labeled with the given activity phase. The temporal error for this phase cannot be calculated for these truth sites.
| missing truth sites | The number of successfully detected positive truth sites that were not labeled with the given activity phase. The temporal error for this phase cannot be calculated for these truth sites.

## ap\_temporal\_error.csv

-   This file measures the temporal error between the
    successfully detected positive ground truth sites and
    their associated proposals using the site-level
    predicted phase transition label and predicted phase
    transition date, instead of the phase labels in the
    observations. In general, it has the same kind of
    content as the [ac\_temporal\_error](#ac_temporal_errorcsv) table.
