# Site Boundaries

## Spatial Boundaries 

Site spatial boundaries delineate the outer extents of the observed change **over the entire duration of the activity**. They should be distinguishable using visible features in the imagery and should include supporting infrastructure (i.e. parking lots, pavement, greenery, areas used during the construction of the activity, etc.). Examples of features that can be used as site boundaries include the following:
- Major roads and above (using [OSM definitions](https://wiki.openstreetmap.org/wiki/United_States/Road_classification))
- Uninhabited areas
- Bodies of water (rivers, oceans, etc.)
- Large areas of vegetation (e.g. forests)
- Inhabited/completed areas that don’t undergo construction in any of the views (including “natural” areas such as open green space).
- A clear, delineated patch or strip of land that does not undergo change in any of the observable views during the temporal span of the activity

Site spatial boundaries may grow over time but will never shrink. They represent all change pertaining to the activity at all times up to the current observation. 

There is also a temporal aspect when considering site spatial boundaries. If activity in one area completely finishes prior to the start of the activity in an adjacent area, a site boundary should be drawn, thereby splitting two adjacent plots of land into two separate sites. If the activity on an adjacent plot of land starts prior to the completion of the original activity AND if no feature that can be used as a site boundary is present (as indicated above), then the new plot of land should be incorporated into the existing site boundary. If additional activity occurs on the same plot of land after several years where the site from the initial activity is clearly complete, unchanging, and in use, the same spatial bounds can be used for a second site separated by a later temporal bound.

### <ins>Sub-sites</ins>

#### Boundaries

These are features that may be used to further split a site into smaller sections when multiple activity phases are present _within the same time slice and within the bounds of a single site polygon_. Sub-site boundaries are necessary _**if and only if**_ they separate areas within the same site boundary that are in different construction phases at a given observation. They are only required **if and only if** the two separate areas both represent heavy construction activities on their own. For example, subsites should not be drawn to separate open green space or parking lots by themselves since those are not positive examples of heavy construction. Examples of suitable subsite boundaries: 
- Roads that are completed within the site boundary during the construction activity
- “Natural” areas (e.g., open green space) that are completed during the activity
- Clear, visible delineations between two plots of land, even if not completed. This is only necessary if the boundary separates areas that are in different phases within that image. If the areas on either side of the boundary are in the same phase, sub-site boundaries are not required. Examples: 
  - Parking lot to dirt transition 
  - Dirt roads separating plots of land or city blocks on which activity is occurring

#### Site/sub-site rules

These rules define the required spatial relationships between and within sites and subsites for a single observation/image (Note: Small amounts of spatial jitter from one image to another may slightly invalidate one or more of these rules between two observations/images.)
- Site boundaries will never overlap or even touch other site boundaries in the same image.
- Subsite boundaries will never overlap other subsite boundaries in the same image (but they can touch). 
- Subsites must always exist fully within site boundaries. Subsites cannot exist on their own and must not extend outside the site boundary of which they are a part.
  - Caveat: Subsites can share boundaries with the site polygon(s) in which they exist. 

Note that the use of subsites in the heavy construction dataset was supported in early development but ultimately phased out (and often ignored) in later development. They exist in some annotations but are only partially supported and/or included in the metrics evaluation code.  

## Temporal Boundaries

The timespan of a site may be referred to differently depending on the completeness of the annotation (i.e. inclusion of phase classifications).

**Start and end dates** have been identified with either Google Earth or Sentinel imagery, but will not be explicitly tied to a specific image. These are "default" dates, which will be present for all [Type 3 or Type 4](https://github.com/pubgeo/IARPA-SMART/blob/main/README.md#annotation-types) sites (sites without phase labels, including all `negative` (Type 3), `positive_excluded` (3), `ignore` (3), and `positive_pending` (4) sites). These dates will always appear in top-level site model feature as well as the site's entry in its corresponding region model.

- start_date refers to the last image timestamp on which no activity was seen, i.e. the time right before construction began. Sites may rarely have a null start_date, which can be used when a site is already under construction in the earliest available images or when there is a long gap after the last image without activity (e.g. Google Earth often has a gap between 1985 imagery and mid-2000s imagery). This is very uncommon (less than a dozen sites) in the [primary dataset](https://github.com/pubgeo/IARPA-SMART/blob/main/README.md#primary-and-supplemental-datasets), and it is more frequent but still under 10% of the [secondary dataset](https://github.com/pubgeo/IARPA-SMART/blob/main/README.md#primary-and-supplemental-datasets).
- end_date refers to the first image timestamp after all construction appears to be completed, often when the site is visibly in-use. If construction activity has not yet ended in the most recent images available at the time of annotation, end_date should be null.
- Note that the `start_date` and `end_date` fields in Type 1 or 2 site annotation files do not correspond to this "default" date range. They instead give the date of the earliest/latest images annotated with a phase label, which may be many images before/after any construction activity begins/ends. The equivalent to a Type 3 or 4 "default" start_date is the date of the last annotated instance of `no activity` before `site preparation` or `active construction` begins, while a Type 3 or 4 "default" end_date is the date of the first annotated instance of `post construction` (equivalent to `activity end`).

**Activity dates** may also be referenced for [Type 1 or Type 2](https://github.com/pubgeo/IARPA-SMART/blob/main/README.md#annotation-types) sites, which have at least partial phase classification annotations. Phase classification is tied to an annotated image, so these dates will also correspond to a specific source and image tag.
- `activity start` refers to the first annotated instance of visible change for a site. This will ideally be indicated by the first instance of `site preparation`, though not necessarily depending on the completeness of the annotation or the availability of imagery. This is part of the function of the `positive_partial` site status (Type 2): to indicate that there are incomplete phase labels annotated for that site.
- `activity end` refers to the last annotated instance of construction-related change, before a site is completed. This will ideally be the first instance of `post construction`, though not necessarily depending on the completeness of the annotation or the availability of imagery.

In addition to these considerations, if the activity start or end dates fall outside of the region temporal boundary (2014-01-01 to 2021-08-31), those region boundary dates will be used as default values, giving the site an "unbounded" status. For more details on activity dates, example regions ([BR_R002](https://github.com/pubgeo/IARPA-SMART/tree/main/src/example/output.compare/BR_R002) and [KR_R002](https://github.com/pubgeo/IARPA-SMART/tree/main/src/example/output.compare/KR_R002)) are included in the test harness source code documentation. The READMEs for these regions include descriptions of the calculated activity dates.

