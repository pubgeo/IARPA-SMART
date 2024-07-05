# Obtaining satellite imagery 

The IARPA SMART Heavy Construction annotation dataset uses imagery from three satellite-based imaging sources:
- [Landsat 8 (L8)](https://www.usgs.gov/landsat-missions/landsat-8)
- [Sentinel 2 (S2)](https://dataspace.copernicus.eu/explore-data/data-collections/sentinel-data/sentinel-2)
- [MAXAR WorldView 1, 2, and 3 (WV)](https://www.maxar.com/maxar-intelligence/constellation)

A fourth data source - [Planet Labs Imagery (PL)](https://www.planet.com/) - was used for the program but only for algorithm development and system inference. No Planet Labs imagery is included in the Heavy Construction Annotation Dataset.

## Inference vs Evaluation
The IARPA SMART problem formulation does not restrict the use of alternate image sources when performing algorithm development or inference. Specifically, any of the above sources OR any additional imagery sources may be used.  

However, for the purposes of algorithm performance evaluation, only observations associated with the specific images indicated in the annotated site models will be used. 

## Publicly available data (Landsat and Sentinel)
The Landsat 8 (L8) and Sentinel 2 (S2) imagery are publicly available. There are a number of ways to obtain these images. We recommend one of the following

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
| Sentinel 2<br>Level 1C | https://earth-search.aws.element84.com/v1/collections/sentinel-2-l1c/items | <div align="center">JPEG 2000</div> | <div align="center">eu-central-1</div> |
| Sentinel 2<br>Level 2A | https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items | <div align="center">JPEG 2000</div> | <div align="center">eu-central-1</div> |

*[COG: Cloud Optimizied GeoTIFF Format Description](https://www.usgs.gov/media/files/landsat-cloud-optimized-geotiff-data-format-control-book)
```
TODO: Isolde to check and finalize
```

Examples demonstrating proper calls to the STAC endpoints can be found (TODO: HERE)

## Non-publicly available data (WorldView and Planet Labs)
Due to licensing restrictions, we are not able to dissemninate the WorldView or Planet imagery. While not technically required, having these imagery sources for algorithm development is beneficial.  

For access to these imagery sources, we recommend reaching out to the source vendors directly:
- [MAXAR](deftechsupport@maxar.com)
- [Planet Labs](https://www.planet.com/contact-sales/)

We recommend obtaining some or all of the images listed below: 
- TODO: Make a WV imagery list
- TODO: Make a Planet imagery list

There may be additional images beyond those listed that can also be used but this set represents a sufficient baseline. 