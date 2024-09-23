# IARPA SMART Overview
The [IARPA Space-Based Machine Automated Recognition Technique (SMART) program](https://www.iarpa.gov/research-programs/smart) aims to automate global-scale detection, classficiation, and monitoring of large-scale anthropogenic activites on the Earth's surface using satellite imagery. 

For more information on the problem formulation and the dataset, please see our [publication](https://doi.org/10.1117/12.2663071). A video recording of the presentation of this paper can be found [here](https://doi.org/10.1117/12.2663071) as well. 


# About this repository

The Johns Hopkins University Applied Physics Laboratory (JHU/APL) led the development of a large Computer Vision/Machine Learning (CV/ML) dataset containing spatio-temporal annotations of large scale heavy construction activity for the purposes of algorithm development and evaluation. 

This repository contains the annotation dataset (found in `annotations/`) along with [instructions for how to obtain some of the imagery](documentation/obtain_imagery.md) in which these activities can be observed. Also included here are useful utilities (found in `utilities/`) to help get started and make use of the dataset.

A Python-based implementation of custom performance evaluation metrics (tailored specifically to the data formats and application introduced here) can be found in `src/`. A publication describing the evaluation metrics is available here (COMING SOON).

NOTE: At the time of the initial release, some annotations in the dataset remain sequestered to support independent test and evaluation for the IARPA SMART program and potential follow-on activities. These will remain sequestered (and unreleased here) until they are no longer needed for sequestered testing. 

## Terminology

- **Observation**:
  - A single image capturing the actitivy of interest on a specific day. A day is the most granular time-scale considered by SMART

- **Region**: 
  -  An area of interest defining spatial bounds for processing and annotation

- **Region Model**:
  - A data format (GeoJSON) that represents a region's spatial and temporal bounds along with a list of all sites contained within those region bounds. Region models defined in the SMART dataset can be found [here](annotations/region_models/). 

  ***Empty Region Model***: 
  - We also define the concept of an _empty region model_, which defines only the spatial and temporal bounds of the region without the list of sites contained within those regions bounds. These files (also in GeoJSON format) are meant to serve as an input to an algorithm for the sole purpose of defining the spatial and temporal extents over which the algorithm is expected to process (search for activity). 

- **Site / Site Boundary**: 
  - A geographical area defining the spatial boundaries of large-scale change (anthropogenic or not). 
  - This is the fundamental unit of activity that SMART is focused on; it is what human annotators will be labeling and what algorithms are expected to detect and classify. 
  - For SMART, sites of interest must be larger than 8000 m². (Note that this size is in reference to the entire site area, not the objects within the site.). 
  - There can be any number of sites within a `region` (including none)

- **Sub-site / Sub-site Boundary**: 
  - Used to indicate that an area within the site boundary is in a different activity phase as the surrounding or neighboring plots of land
  - Sub-site boundaries are only required _**if and only if**_ the site is exhibiting multiple activity phases in a single time slice

- **"Cleared" regions**: 
  - A region is said to be "cleared" when all activity (positive, negative, ignore) has been labeled and site models for each activity have been generated. Clearing regions is necessary for evaluation purposes. Not all regions in the SMART dataset are cleared. For a list of cleared regions, see <COMING SOON: Add list of cleared regions>

<div style="text-align: center;">
  <figure>
    <img src="resources/example_region.png" alt="Description" style="width: 750px;">
    <figcaption>Illustration of an annotated region in the vicinity of Rio de Janeiro, Brazil. The region boundaries are indicated by the yellow rectangle. Annotated heavy construction sites from the SMART dataset are indicated by the green polygons.</figcaption>
  </figure>
</div>


## Heavy Construction Annotation Dataset

For the purposes of the IARPA SMART problem formulation, heavy construction activity is defined as any activity related to the construction of large scale buildings and associated infrastructure. 

Note that for this application, we are interested in spatially and temporally localizing the bounds of _all_ construction related activity. This means that we are not simply interested in the footprints of the buildings alone (as many remote sensing applications and existing benchmark datasets are). Instead, we consider all activity associated with the construction to be part of the activity including, but not limited to, preparation of the entire plot of land undergoing change and being used to support the construction activity or facilities and infrastructure that support the use of the final facility/buildings (e.g. parking lots associated with the buildings). 

Therefore, for our problem, we have defined the concept of a `site` which is meant to spatially and temporally bound all construction-related activity, not simply the building footprints of the buildings being constructed. Given the above, note that the spatial boundaries of SMART 'sites' are almost always larger than the building footprints themselves. The SMART Heavy Construction dataset does not include the explicit labeling of individual buildings themselves. See below for examples of site boundaries of positive examples (heavy construction activity which we intend algorithms to detect) and negative examples (heavy construction or large scale change which we intend algorithms **_not_** detect). 

(NOTE: The assignment of specific activity types to the positive and negative classes were explicitly defined to meet the needs of expected end-users at the time of problem definition. Other applications may require slightly different assignments and users of this dataset are encouraged to re-define the breakdown in other ways if desired. A list of the activity type of each site can be found here <TODO: Add a link to this list>.)

### Positive activity types

For the purposes of the IARPA SMART Heavy Construction Dataset, the following activity types are considered to be in the 'positive' set. That is, we expect algorithms to detect these types of heavy construction activity. 

- Medium Residential (Low-rise apartments/condos, townhouse/row homes with 5 stories or below, Does not matter how many of these buildings there are)
- Heavy Residential (Large apartment or condo high rise building that is over 5 stories tall)
- Commercial (e.g. malls, grocery stores, strip malls, gas stations, hospitals, stadiums, office buildings, hotels, storage units)
- Industrial (e.g. factories, power plants, manufacturing facility, warehouses, distribution center, shipping infrastructure (shipping ports) etc.)
- Other: A known type that doesn't fall into any of the above categories. (e.g. schools, parking garages, religious buildings, power substations, fire stations, etc.)

Other considerations for 'Positive' activity types, or activity that should be included within site boundaries:

- Sports fields if also associated with large-scale construction buildings (i.e., a school with new sports fields)
- Roads/driveways/Parking lots that are associated with construction of a build (i.e., a parking lot that is part of a new store, a new access road that leads to a new factory)
- The creation of artificial islands/land if associated with the construction of a man-made structure on that land

| ![Image 1](resources/pos_activity_industrial_1.png) | ![Image 2](resources/pos_activity_heavyres_2.png) | ![Image 3](resources/pos_activity_commercial_1.png) | ![Image 4](resources/pos_activity_commercial_2.png) |
|:----------------------:|:----------------------:|:----------------------:|:----------------------:|
| Industrial              | Industrial              | Commercial              | Commercial              |

| ![Image 5](resources/pos_activity_heavyres_1.png) | ![Image 6](resources/pos_activity_heavyres_2.png) | ![Image 7](resources/pos_activity_medres_1.png) | ![Image 8](resources/pos_activity_medres_2.png) |
|:----------------------:|:----------------------:|:----------------------:|:----------------------:|
| Heavy Residential              | Heavy Residential              | Medium Residential              | Medium Residential               |

#### _Examples of site progressions over time_

<div style="text-align: center;">
  <div style="display: flex; justify-content: center; align-items: center; gap: 20px">
      <video width="400" height="400" controls>
        <source src="resources/pos_site_US.mp4" type="video/mp4">
        Your browser does not support the video tag.
      </video>
      <video width="400" height="400" controls>
        <source src="resources/pos_site_BR.mp4" type="video/mp4">
        Your browser does not support the video tag.
      </video>
      <video width="400" height="400" controls>
        <source src="resources/pos_site_AE.mp4" type="video/mp4">
        Your browser does not support the video tag.
      </video>
  </div>

  <p style="margin-top: 10px; font-size: 16px;">Examples of time-lapsed progression of heavy construction activity. Imagery shown is Sentinel 2 imagery from Copernicus Sentinel Hub EO Browser
  </p>
</div>

### Negative activity types

For the purposes of the IARPA SMART Heavy Construction Dataset, the following activity types are considered to be in the 'negative' set. That is, we expect algorithms to detect these types of heavy construction activity. 

- Light residential (A collection of one or more detached single family homes)
- Sports fields not associated with the construction of large building or facility
- Golf courses (even with the presence of a clubhouse)
- Standalone surface parking lots not associated with the construction of at least one other 'Positive' example (e.g. a park and ride, an airport parking lot)
- Standalone roads infrastructure (not directly associated with the construction of buildings) including interchanges, bridges, tunnels
- Change that is a result of a natural disaster (e.g. tornado, hurricane, flood, etc.)
- The general clearing of land or destruction of a building/structure without the explicit or immediate purpose of continued construction (e.g. the destruction of a stadium or factory on land that is then abandoned)
- The creation of water retention ponds, unless directly associated with the construction of a 'Positive' example
- Solar panel "fields"

TODO: Add pictures

### Ignore

For the purposes of the IARPA SMART Heavy Construction Dataset, activiy types that are either ambiguous or otherwise unknown at the time of annotation are  categorized as 'ignore'. These sites should not be counted or considered in the evaluation of algorithm performance. 

- Define what heavy construction is and isn't (size, activity types, etc.)
- Chart showing how many sites are annotated in each region
- Distinction between different annotation types 

## File Format Specifications

The IARPA SMART Heavy Construction Annotation Dataset is provided in a custom, yet simple human- and machine-readable format ([geoJSON](https://geojson.org/)). More details can on the format can be found in our documentation (found in `documentation/specifications/`). 

## Obtaining the Satellite Imagery

See [here](documentation/obtain_imagery.md) for more information on obtaining the satellite imagery corresponding to this dataset. 

# Terms and Conditions
The contents of this public dataset are provided under the <____________> license. 

Any publication using the dataset or any contents herein in any way shall refer to the following paper: 

```
@inproceedings{goldberg2023spie,
	author={Hirsh R. Goldberg and Christopher R. Ratto and Amit Banerjee and Michael T. Kelbaugh and Mark Giglio and Eric F. Vermote},
	booktitle={Geospatial Informatics XIII},
    volume={12525}, 
	title={Automated global-scale detection and characterization of anthropogenic activity using multi-source satellite-based remote sensing imagery}, 
	year={2023}, 
    doi={10.1117/12.2663071},
    URL={https://doi.org/10.1117/12.2663071}
}
```

# Acknowledgments
This work was supported by the Office of the Director of National Intelligence (ODNI), Intelligence Advanced Research Projects Activity (IARPA) under contract numbers 2017-17032700004 and 2020-20081800401. The views and conclusions contained herein are those of the authors and should not be interpreted as necessarily representing the official policies, either expressed or implied, of ODNI, IARPA, or the U.S. Government. 

Development of the dataset was also supported by: 
- CrowdAI
- iMERIT

# Contact the authors
Please reach out to pubgeo@jhuapl.edu with any questions or comments. 



