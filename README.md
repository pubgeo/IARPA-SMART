# IARPA SMART Overview
The [IARPA Space-Based Machine Automated Recognition Technique (SMART) program](https://www.iarpa.gov/research-programs/smart) aims to automate global-scale detection, classficiation, and monitoring of large-scale anthropogenic activites on the Earth's surface using satellite imagery. 

For more information on the problem formulation and the dataset, please see our [publication](https://doi.org/10.1117/12.2663071). A video recording of the presentation of this paper can be found [here](https://doi.org/10.1117/12.2663071) as well. 


# About this repository

The Johns Hopkins University Applied Physics Laboratory (JHU/APL) led the development of a large Computer Vision/Machine Learning (CV/ML) dataset containing spatio-temporal annotations of large scale heavy construction activity for the purposes of algorithm development and evaluation. 

This repository contains the annotation dataset (found in `annotations/`) along with [instructions for how to obtain some of the imagery](documentation/obtain_imagery.md) in which these activities can be observed. Also included here are useful utilities (found in `utilities/`) to help get started and make use of the dataset. 

NOTE: At the time of the initial release, some annotations in the dataset remain sequestered to support independent test and evaluation for the IARPA SMART program and potential follow-on activities. These will remain sequestered (and unreleased here) until they are no longer needed for sequestered testing. 

## Terminology

- **Observation**:
  - A single image capturing the actitivy of interest on a specific day. A day is the most granular time-scale considered by SMART

- **Region**: 
  -  An area of interest defining spatial bounds for processing and annotation

- **Region Model**:
  - A data format that represents a region's spatial and temporal bounds

- **Site / Site Boundary**: 
  - A geographical area defining the spatial boundaries of large-scale change (anthropogenic or not). 
  - This is the fundamental unit of activity that SMART is focused on; it is what human annotators will be labeling and what algorithms are expected to detect and classify. 
  - For SMART, sites of interest must be larger than 8000 m². (Note that this size is in reference to the entire site area, not the objects within the site.). 
  - There can be any number of sites within a `region` (including none)

- **Sub-site / Sub-site Boundary**: 
  - Used to indicate that an area within the site boundary is in a different activity phase as the surrounding or neighboring plots of land
  - Sub-site boundaries are only required _**if and only if**_ the site is exhibiting multiple activity phases in a single time slice

- **"Cleared" regions**: 
  - A region is said to be "cleared" when all activity (positive, negative, ignore) has been labeled and site models for each activity have been generated. Clearing regions is necessary for evaluation purposes.

TODO: Add an image of a region with sites

## Heavy Construction Annotation Dataset

For the purposes of the IARPA SMART problem formulation, heavy construction activity is defined as any activity related to the construction of large scale buildings and associated infrastructure. 

Note that for this application, we are interested in spatially and temporally localizing the bounds of _all_ construction related activity. This means that we are not simply interested in the footprints of the buildings alone (as many remote sensing applications and existing benchmark datasets are). Instead, we consider all activity associated with the construction to be part of the activity including, but not limited to, preparation of the entire plot of land undergoing change and being used to support the construction activity or facilities and infrastructure that support the use of the final facility/buildings (e.g. parking lots associated with the buildings). 

Therefore, for our problem, we have defined the concept of a `site` which is meant to spatially and temporally bound all construction-related activity. Given the above, note that the spatial boundaries of SMART 'sites' are almost always larger than the building footprints themselves. The SMART Heavy Construction dataset does not include the explicit labeling of individual buildings themselves. See below for examples of site boundaries of positive examples (Heavy Construction for which we intend algorithms to detect) and negative examples (heavy construction or large scale change for which we intend algorithms **_not_** detect). 

(NOTE: The assignment of specific activity types to the positive and negative classes were explicitly defined to meet the needs of expected end-users at the time of problem definition. Other applications may require slightly different assignments and users of this dataset are encouraged to re-define the breakdown in other ways if desired. A list of how each site 

### Positive activity types

TODO: Add the list here


### Negative activity types

TODO: Add the list here


- Define what heavy construction is and isn't (size, activity types, etc.)
- Pictures of heavy construction
- Chart showing how many sites are annotated in each region
- Map with locations of regions
- Distinction between different annotation types 

### File Format Specifications

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



