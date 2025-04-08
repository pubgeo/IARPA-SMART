# Site Model Specification

This is the [schema specification](../../utilities/smart.schema.json) for a _Site Model_. Site model files can be validated by running the [validate_site_and_region_models.py](../../utilities/validate_site_and_region_models.py) utility. 

_Site models_ describe all observed activity in a given site/activity, both spatially and temporally. One _site model_ is produced for each activity/site.

A _Site Model_ is also a FeatureCollection, which means at the top level it must define the keys type and features. Unlike the Region Model, a Site Model’s two features are 'site' and 'observation'.

## 'Site' Feature

As mentioned in the common model documentation, a Site feature is expected to define its type and geometry. A Site's geometry, as with a Site Summary's geometry, **must be** 'Polygon'. The following are defined properties - unless explicitly noted, all of these are mandatory.

### `type` (string)

For _site models_, this must be set to "site".

This is specific to the site feature and is used to differentiate sites from observation features.

### `region_id` (string or null)

This must be a string of the format `<2-digit country code>_{R|C|S}###`, or `null`.

This is the ID of the region that this site is associated to. If this ID is defined, it is implicit that a Region Model exists with this same ID associated to its Region feature.

### `site_id` (string)

This must be a string of the format `<region_id>_####`.

If this site is associated to a specific region, then the region's ID should form the prefix of this ID, and a four-digit suffix added for uniqueness.

The _site_id_ is a unique index that serves as the primary link between sites that exist within region bounds and the site model annotation itself. 

Unique IDs of sites do not need to be contiguous, e.g. the existence of site XX_R000_0000 and XX_R000_0002 does not imply the existence of site XX_R000_0001.

If a site has not been associated to a region, the reserved region ID `<two-letter country code>_Rxxx` may be used. That is, the site declares the country that it belongs to (with the location of the centroid determining country ownership in the case of a border ambiguity), and it uses the literal string `Rxxx` rather than `R` followed by three digits.

### `version` (string)

This must be a string of the format `#.#.#`.

Site models will be given version numbers to enable tracking of changes **to the model** which occur over time.

Versioning will use a Semantic Versioning construct (MAJOR.MINOR.PATCH). Updates to the version numbers will follow this format:

* **MAJOR increment**
  * This corresponds to the MAJOR version of the site model spec that is being used. An increment of this type indicates that metadata fields have been added or removed, or that their type has been modified.
* **MINOR increment**
  * This is incremented to indicate that observations have been added to, or removed from, the site model.
* **PATCH increment.**
  * This is incremented to indicate that the content of existing features has been modified (e.g. geometries have been updated, or properties have been modified).

Incrementation indicates a single operation has taken place, not that a single modification has taken place. For example, a task that added three observations to a file versioned 1.0.0 would change the semantic version to 1.1.0, not to 1.3.0.

### `mgrs` (string)

This is the [MGRS](https://en.wikipedia.org/wiki/Military_Grid_Reference_System) grid ID at the 100km precision level for the region’s centroid. For non-polar regions, the grid zone designator should be zero-padded e.g. rather than `4QFJ` you would use `04QFJ`. Accordingly, non-polar regions should have a five-letter MGRS string, two numerics followed by three alphabetics. Polar regions should have only three alphabetics.

### `status` (string)

This must be one of the strings found on the list of [annotation status types](../miscellaneous_annotation_details.md#annotations-status-type-categories).

### `start_date` (string or null)

This value may be `null` ,or a datestring of the format `"YYYY-MM-DD"`.

If it is a datestring, it corresponds to the earliest date of all observation features in this site model. `null` has a special semantic meaning and is only permitted in certain statused sites, as detailed in the [annotation status types](../miscellaneous_annotation_details.md#annotations-status-type-categories).

NOTE: This date is not the same as the observed start of the activity described by the site model. It is simply the very first observation noted in the annotation (ground truth) file, which could be 'No Activity' (prior to activity starting). 

### `end_date` (string or null)

This value may be `null` ,or a datestring of the format `"YYYY-MM-DD"`.

If it is a datestring, it corresponds to the latest date of all observation features in this site model. `null` has a special semantic meaning and is only permitted in certain statused sites, as detailed in the [annotation status types](../miscellaneous_annotation_details.md#annotations-status-type-categories).

NOTE: This date is not the same as the observed end of the activity described by the site model. It is simply the very last observation noted in the annotation (ground truth) file, which could be the last of several 'Post Construction' activities. 

### `model_content` (string)

This must be one of two strings `["annotation", "proposed"]`

An "annotation" site is a new site defined by the program or a performer, and "proposed" sites are defined by performer algorithms. Unlike the similarly named property of a Region feature, a Site may not have the model_content "empty".

### `originator` (string)

This field indicates who produced the site model. In the SMART Heavy Construction Dataset, all annotation (ground truth) files will contain one of the strings `["te", "iMERIT"]`. 

## The following properties may also optionally be defined:

### `score` (float, optional)

This must be a value in the range \[0.0, 1.0\].

This is the "confidence score" of this site, with 1.0 being highest confidence and 0.0 being lowest confidence. If this property is not explicitly defined in the site model, it will be treated as though the score is 1.0.

### `validated` (string, optional)

This is either the string "True" or the string "False".

**Warning:** The use of JSON literal booleans in this field is malformed.

If the site has been validated by the annotation team, it may receive the string "True"; otherwise it is "False". If this property is not defined, it will be treated as though the string is "False".

### `predicted_phase_transition` (string, optional)

Not currently used. 

### `predicted_phase_transition_date` (string, optional)

Not currently used. 

### `cache` (object, optional)

This is an unstructured dictionary that provides miscellaneous information about the observation. If this property is not defined, it will be assumed that there is no additional information to provide.

NOTE: In early versions of the site model schema, a `misc_info` property was defined. As of schema version 0.7.0, this property replaces the use of the `misc_info` property. Currently, use of the old key is still supported, but migration to the new key is recommended for all future implementations.

# Observation Feature

An _Observation Feature_ corresponds to a specific observation made on a specific date associated with a specific site activity. Unlike all other defined features, the Observation Feature's geometry is of type **MultiPolygon**.

The following properties must all be defined for an _Observation Feature_.

### `type` (string)

This must be set to "observation".

This is specific to the observation feature, and is used to differentiate _observation_ features from _site_ features.

### `observation_date` (string or null)

This value may either be `null` or a datestring of the format `"YYYY-MM-DD"`.

`null` has a special semantic meaning and is only permitted in certain circumstances, as detailed in the `TODO: FIX THIS canonical site types`

### `source` (string or null)

This is the image name associated with this observation, without the file extension. For example, an observation from a file named "T17RMP_20150608T160359_TCI.TIF" would assign the value "T17RMP_20150608T160359_TCI" to the `source` field.

If this observation is not associated with a specific image, this value is to be set to `null`.

#### Note

The current practice of using `source` as a key to associate multiple observations to a single source is intended to be phased out and replaced by use of `source` to identify an explicit object.

A best practice for this property would be to use file link to the artifact in question. However, this is not mandatory at this time.

### `sensor_name` (string or null)

This value must be one of the strings `["Landsat 8", "Sentinel-2", "WorldView", "Planet"]`, or `null`.

Name of satellite sensor platform associated with this observation. If this observation is not associated with a particular sensor, then this value is to be set to `null`.

### Note

The following fields are all comma-space-separated formatted strings, owing to technology use decisions. A comma-space separated string does not contain quotes or other string delimiters, and indicates the break between adjacent values by use of the substring `", "`. For example, the command-space-separated form of the list `["one", "two", "three"]` would look like `"one, two, three"`, while the comma-space-separated form of the list `["one"]` would look like `"one"`.

As mentioned, the Observation feature is allowed to be a MultiPolygon, but a MultiPolygon can have different values for each subsidiary polygon. Therefore, each value in the following lists corresponds to the state of the polygon at that index of the geometry. For example, the first entry in the current_phase list would correspond to the first entry in the is_occluded list, which corresponds to the first whole polygon in the Observation's MultiPolygon, and so on. Therefore, the lengths of all of the lists of these properties should be identical, and identical to the length of the top-level list of the "coordinates" object in this feature's geometry.

### `current_phase` (string or null)

This string is a comma-space separated list of strings, which are from the list `["No Activity", "Site Preparation", "Active Construction", "Post Construction", "Unknown"]`.

These give the current phase of their corresponding polygon in the multipolygon.

If there are no phases (which can happen in certain annotation model types), this value may be explicitly set to `null`. The use of an empty string is not an acceptable substitute.

### `is_occluded` (string or null)

This string is a comma-space separated list of strings, which are from the list `["True", "False"]`.

**Warning:** The use of JSON literal booleans in this field is malformed.

This is a list that indicates if the observation in this polygon has been occluded in any way. This uses the string "True" if there is any occlusion of the feature, and the string "False" if there is none.

If there are no occlusion notes (which can happen in annotation models), this value may be explicitly set to `null`. The use of an empty string is not an acceptable substitute.

### `is_site_boundary` (string or null)

This string is a comma-space separated list of strings, which are from the list `["True", "False"]`.

**Warning:** The use of JSON literal booleans in this field is malformed.

This is a list that indicates if this observation in this polygon is the exterior perimeter of the site. This uses the string "True" if this is the case, and "False" otherwise.

If there are no site boundary notes (which can happen in certain annotation model types), this value may be explicitly set to `null`. The use of an empty string is not an acceptable substitute.

### Notes on the observation geometries

Polygon geometries should follow the [guidelines defined for site and subsite rules](../boundary_definitions.md).

### Optional Fields

### `score` (float, optional)

This must be a value in the range \[0.0, 1.0\].

This is the "confidence score" associated with this observation, with 1.0 being highest confidence and 0.0 being lowest confidence. If this property is not defined, it will be treated as though the score is 1.0.

### `cache` (object, optional)

This is an unstructured dictionary that provides miscellaneous information about the observation. If this property is not defined, it will be assumed that there is no additional information to provide.

NOTE: In early versions of the site model schema, a `misc_info` property was defined. As of schema version 0.7.0, this property replaces the use of the `misc_info` property. Currently, use of the old key is still supported, but migration to the new key is recommended for all future implementations.

# Site Model Example

```
{
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {
                "type": "site",
                "region_id": "AE_R001",
                "site_id": "AE_R001_0014",
                "version": "2.0.1",
                "status": "positive_pending",
                "mgrs": "40RCN",
                "score": 1.0,
                "start_date": "2021-02-01",
                "end_date": "2022-08-26",
                "model_content": "annotation",
                "originator": "te",
                "validated": "True",
                "misc_info": {
                    "commit_hash": "6bbb83463a734bf8db57673e2a9df144e23a1f1f"
                }
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [
                            55.049518,
                            24.865315
                        ],
                        [
                            55.04735,
                            24.86392
                        ],
                        [
                            55.046448,
                            24.86503
                        ],
                        [
                            55.048551,
                            24.86641
                        ],
                        [
                            55.049518,
                            24.865315
                        ]
                    ]
                ]
            }
        },
        {
            "type": "Feature",
            "properties": {
                "observation_date": "2021-02-01",
                "source": null,
                "sensor_name": null,
                "type": "observation",
                "current_phase": null,
                "is_occluded": null,
                "is_site_boundary": null,
                "score": 1.0
            },
            "geometry": {
                "type": "MultiPolygon",
                "coordinates": [
                    [
                        [
                            [
                                55.049518,
                                24.865315
                            ],
                            [
                                55.04735,
                                24.86392
                            ],
                            [
                                55.046448,
                                24.86503
                            ],
                            [
                                55.048551,
                                24.86641
                            ],
                            [
                                55.049518,
                                24.865315
                            ]
                        ]
                    ]
                ]
            }
        },
        {
            "type": "Feature",
            "properties": {
                "observation_date": "2022-08-26",
                "source": null,
                "sensor_name": null,
                "type": "observation",
                "current_phase": null,
                "is_occluded": null,
                "is_site_boundary": null,
                "score": 1.0
            },
            "geometry": {
                "type": "MultiPolygon",
                "coordinates": [
                    [
                        [
                            [
                                55.049518,
                                24.865315
                            ],
                            [
                                55.04735,
                                24.86392
                            ],
                            [
                                55.046448,
                                24.86503
                            ],
                            [
                                55.048551,
                                24.86641
                            ],
                            [
                                55.049518,
                                24.865315
                            ]
                        ]
                    ]
                ]
            }
        }
    ]
}
```
