# Spatial Boundaries 

Site spatial boundaries delineate the outer extents of the observed change over the entire duration of the actvitiy. They should be distinguishable using visible features in the imagery and should include supporting infrastructure (i.e. parking lots, pavement, etc.). Examples of features that define site boundaries include the following:
- Major roads and above (using [OSM definitions](https://wiki.openstreetmap.org/wiki/United_States/Road_classification))
- Uninhabited areas
- Bodies of water (rivers, oceans, etc.)
- Large areas of vegetation (e.g. forests)
- Inhabited/completed areas that don’t undergo construction in any of the views (including “natural” areas such as open green space).
- A clear, delineated patch or strip of land that does not undergo change in any of the observable views during the temporal span of the activity

Site spatial boundaries may grow over time but will never shrink. They represent all change pertaining to the activity at all times up to the current observation. 

There is also a temporal aspect when considering site spatial boundaries. If activity on one site completely finishes prior to the start of the activity of an adjacent site, a site boundary should be drawn, thereby splitting two adjacent plots of land into two separate sites. If the activity on an adjacent plot of land starts prior to the completion of the original activity AND if no site boundary is present (as indicated above), then the new plot of land should be incorporated into the existing site boundary.  

## Sub-sites

### Boundaries

These are features that may be used to further split a site into smaller sections when multiple activity phases are present _within the same time slice and within the bounds of a single site polygon_. Sub-site boundaries are necessary _**if and only if**_ they separate areas within the same site boundary that are in different construction phases at a given observation. They are only required **if and only if** the two separate areas both represent heavy construction activities on their own. For example, subsites should not be drawn to separate open green space or parking lots by themselves since those are not positive examples of heavy construction. Examples of suitable subsite boundaries: 
- Roads that are completed within the site boundary during the construction activity
- “Natural” areas (e.g., open green space) that are completed during the activity
- Clear, visible delineations between two plots of land, even if not completed. This is only necessary if the boundary separates areas that are in different phases within that image. If the areas on either side of the boundary are in the same phase, sub-site boundaries are not required. Examples: 
  - Parking lot to dirt transition 
  - Dirt roads separating plots of land or city blocks on which activity is occurring

### Site/sub-site rules

These rules define the required spatial relationships between and within sites and subsites for a single observation/image (Note: Small amounts of spatial jitter from one image to another may slightly invalidate one or more of these rules between two observations/images.)
- Site boundaries will never overlap or even touch other site boundaries in the same image.
- Subsite boundaries will never overlap other subsite boundaries in the same image (but they can touch). 
- Subsites must always exist fully within site boundaries. Subsites cannot exist on their own and must not extend outside the site boundary of which they are a part.
  - Caveat: Subsites can share boundaries with the site polygon(s) in which they exist. 

# Temporal Bounds

The timespan of a site may be referred to differently depending on the completeness of the annotation (i.e. inclusion of phase classifications).

**Start and end dates** may have either been identified with Google Earth or Sentinel imagery, and will not be tied to a specific image. These are sort-of "default" dates, which appear on all negative and ignore sites, in addition to delivered `positive_pending` and iMerit-annotated ("coarse annotation") sites.
- start_date refers to the last timestamp on which no activity was seen, i.e. the time right before construction began.
- end_date refers to the first timestamp after all construction is verified to be completed, typically when the site is visibly in-use.

**Activity dates** may be referenced for sites which have at least partial phase classification annotations. Because it is tied to an annotated image, these dates will also correspond to a specific source and image tag.
- `activity start` refers to the first annotated instance of visible change for a site. This will ideally be indicated by the first instance of `site preparation`, though not necessarily depending on the completeness of the annotation or the availability of imagery
- `activity end` refers to the last annotated instance of construction-related change, before a site is completed. This will ideally be the first instance of `post construction`, though not necessarily depending on the completeness of the annotation or the availability of imagery