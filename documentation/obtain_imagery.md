# Obtaining satellite imagery 

The IARPA SMART Heavy Construction annotation dataset uses imagery from three satellite-based imaging sources:
- [Landsat 8 (L8 or LS)](https://www.usgs.gov/landsat-missions/landsat-8)
- [Sentinel 2 (S2)](https://dataspace.copernicus.eu/explore-data/data-collections/sentinel-data/sentinel-2)
- [MAXAR WorldView 1, 2, and 3 (WV)](https://www.maxar.com/maxar-intelligence/constellation)

A fourth data source - [Planet Labs Imagery (PL)](https://www.planet.com/) - was also used for the program, but only for algorithm development and system inference. No Planet Labs imagery is included in the Heavy Construction Annotation Dataset.

## Inference vs Evaluation
The IARPA SMART problem formulation does not restrict the use of alternate image sources when performing algorithm development or inference. Specifically, any of the above sources OR any additional imagery sources may be used.  

However, for the purposes of algorithm performance evaluation, only observations associated with the specific images indicated in the annotated site models will be used. 

## Publicly available data (Landsat and Sentinel)
The Landsat 8 (L8 or LS) and Sentinel 2 (S2) imagery are publicly available. There are a number of ways to obtain these images. We recommend one of the following

### Landsat 8
Landsat 8 data can be obtained via one of the following links: 

### Sentinel 2
Sentinel 2 data can be obtained via one of the following links: 

- [ESA Copernicus Data Space Ecosystem](https://dataspace.copernicus.eu/)
- [Sentinel Hub EO Browser](https://apps.sentinel-hub.com/eo-browser/)
- [USGS Earth Explorer](https://earthexplorer.usgs.gov/)

### Using STAC
The use of [SpatioTemporal Asset Catalogs (STAC)](https://stacspec.org/en) facilitates the search, discovery, and acquisition of geospatial imagery. For faster, automated imagery retrieval, we recommend obtaining imagery in this fashion. Both Landsat 8 and Sentinel 2 imagery are available via STAC endpoints hosted on Amazon Web Services (AWS). See the table below for more information: 

| Satellite Sensor<br>Source   | STAC API Endpoint | Format | AWS Location | 
|----|----|----|----|
| Landsat 8<br>Collection 2 Level 1 | https://landsatlook.usgs.gov/stac-server/collections/landsat-c2l1/items | <div align="center">COG*</div> | <div align="center">us-west-2</div> |
| Landsat 8<br>Collection 2 Level 2 | https://landsatlook.usgs.gov/stac-server/collections/landsat-c2l2-sr/items | <div align="center">COG*</div> | <div align="center">us-west-2</div> |
| Sentinel 2<br>Level 1C | https://earth-search.aws.element84.com/v1/collections/sentinel-2-l1c/items, <br> https://earth-search.aws.element84.com/v0/collections/sentinel-s2-l1c/items** | <div align="center">JPEG 2000</div> | <div align="center">eu-central-1</div> |
| Sentinel 2<br>Level 2A | https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items, <br> https://earth-search.aws.element84.com/v0/collections/sentinel-s2-l2a/items** | <div align="center">JPEG 2000</div> | <div align="center">eu-central-1</div> |

- *[COG: Cloud Optimizied GeoTIFF Format Description](https://www.usgs.gov/media/files/landsat-cloud-optimized-geotiff-data-format-control-book)
- **The Sentinel 2 v0 STAC catalog is retired now, but was used for most annotations, and may occasionally have images that v1 does not

Examples demonstrating querying calls to the STAC endpoints can be found in IARPA-SMART/utilities/stac_query_example.py. We have also included requirements for the environment at IARPA-SMART/utilities/requirements.txt to run the examples. For downloading imagery, see the [USGS Landsat Commercial Cloud Access Guide](https://www.usgs.gov/landsat-missions/landsat-commercial-cloud-data-access) and the [Copernicus Sentinel-2 API Guide](https://dataspace.copernicus.eu/news/2023-9-28-accessing-sentinel-mission-data-new-copernicus-data-space-ecosystem-apis).

We recommend using some or all of the images listed in these files:
- obtain_imagery_supplemental/suggested_LS_images_with_annotated_sites.csv
- obtain_imagery_supplemental/suggested_S2_images_with_annotated_sites.csv

There may be additional images beyond those listed that can also be used but this set represents a sufficient baseline. 

## Non-publicly available data (WorldView and Planet Labs)
Due to licensing restrictions, we are not able to disseminate the WorldView or Planet imagery. While not technically required, having these imagery sources for algorithm development is beneficial.  

For access to these imagery sources, we recommend reaching out to the source vendors directly:
- [MAXAR](deftechsupport@maxar.com)
- [Planet Labs](https://www.planet.com/contact-sales/)

We recommend obtaining some or all of the images listed in these files: 
- obtain_imagery_supplemental/suggested_WV_images_with_annotated_sites.csv
- obtain_imagery_supplemental/suggested_PL_images_with_annotated_sites.csv

There may be additional images beyond those listed that can also be used but this set represents a sufficient baseline. 

## Obtaining imagery for early annotations
The first 50 annotations produced for this effort were created before we used STACs as part of our workflow, and as a result, these annotations include references to some Sentinel and Landsat imagery that we’ve had difficulty locating in the public Sentinel and Landsat STACs. Some of this is related to inconsistency in how image source IDs were annotated for these early sites, with some observations receiving non-standard ID values from other whole or partial image metadata ID fields. Other observations include the standard ID format, but that ID simply isn’t present when we query the STACs. We are continuing to work to track down the affected images, and will update the site models and imagery lists when we resolve this disparity.

Sites with affected observations:
-	BH_R001 sites 0000-0005
-	BR_R001 sites 0000-0004
-	BR_R002 sites 0000-0001
-	KR_R001 sites 0000-0005
-	KR_R002 sites 0000-0005
-	LT_R001 sites 0000-0008
-	NZ_R001 sites 0000-0003
-	US_R001 sites 0000-0011

