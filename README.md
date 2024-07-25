# IARPA SMART Overview
The [IARPA Space-Based Machine Automated Recognition Technique (SMART) program](https://www.iarpa.gov/research-programs/smart) aims to automate global-scale detection, classficiation, and monitoring of large-scale anthropogenic activites on the Earth's surface using satellite imagery. 

For more information on the problem formulation and the dataset, please see our [publication](https://doi.org/10.1117/12.2663071). A video recording of the presentation of this paper can be found [here](https://doi.org/10.1117/12.2663071) as well. 


# About this repository

The Johns Hopkins University Applied Physics Laboratory (JHU/APL) led the development of a large Computer Vision/Machine Learning (CV/ML) dataset containing spatio-temporal annotations of large scale heavy construction activity for the purposes of algorithm development and evaluation. 

This repository contains the annotation dataset (found in `annotations/`) along with [instructions for how to obtain some of the imagery](documentation/obtain_imagery.md) in which these activities can be observed. Also included here are useful utilities (found in `utilities/`) to help get started and make use of the dataset. 

## Terminology

- **Observation**:
  - A single image capturing the actitivy of interest on a specific day. A day is the most granular time-scale considered by SMART
- **Region**: 
  -  An area of interest defining spatial bounds for processing and annotation
- **Region Model**:
  - A data format that represents a region's spatial and temporal bounds
- Site / Site Boundary: 
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

For the purposes of the IARPA SMART problem formulation, heavy construction activity is defined as activity related to the construction of 

Note that for this problem, we are interested in spatially and temporally localizing the bounds of all construction related activity. This means that we are 

Therefore, for our problem, we have defined the concept of a `site` which is meant to spatially and temporally bound all construction-related activity. 

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



