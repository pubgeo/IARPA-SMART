# Primary Regions

The "Primary Regions" of the dataset are those which include a higher level of detail in their annotations (see [Annotation Types](https://github.com/pubgeo/IARPA-SMART/blob/main/README.md#annotation-types)). These regions are listed below, including whether they were included in the training/validation dataset ("Train") or the sequestered test set ("Test").

"Cleared" indicates whether a region underwent a detailed search by an annotator to identify all visible examples of heavy construction within the January 2014 through August 2021 timeframe.

All regions in the primary dataset are formatted like [country code]_R### (or _Rxxx, discussed below).

| Region ID | Train/Test | Cleared? | Site Count | Positive Sites | Negative Sites | Other Sites |
|-----------|------------|----------|------------|----------------|----------------|-------------|
| AE_R001 | Train | No | 637 | 531 | 18 | 88 |
| BH_R001 | Train | Yes | 70 | 38 | 11 | 21 |
| BR_R001 | Train | Yes | 99 | 67 | 19 | 13 |
| BR_R002 | Train | Yes | 12 | 5 | 4 | 3 |
| BR_R004 | Train | Yes | 51 | 31 | 16 | 4 |
| BR_R005 | Train | Yes | 220 | 161 | 9 | 50 |
| BR_R006 | Test | Yes | 402 | 150 | 119 | 133 |
| CH_R001 | Train | Yes | 214 | 155 | 6 | 53 |
| CH_R002 | Test | Yes | 91 | 53 | 12 | 26 |
| KR_R001 | Train | Yes | 28 | 11 | 4 | 13 |
| KR_R002 | Train | Yes | 118 | 42 | 18 | 58 |
| KR_R003 | Test | Yes | 155 | 62 | 57 | 36 |
| LT_R001 | Train | Yes | 136 | 67 | 32 | 37 |
| NZ_R001 | Train | Yes | 67 | 41 | 9 | 17 |
| NZ_R002 | Test | Yes | 171 | 65 | 61 | 45 |
| PE_R001 | Train | Yes | 37 | 18 | 7 | 12 |
| US_R001 | Train | Yes | 56 | 41 | 9 | 6 |
| US_R003 | Test | Yes | 149 | 71 | 50 | 28 |
| US_R004 | Train | Yes | 105 | 62 | 30 | 13 |
| US_R005 | Train | Yes | 33 | 26 | 3 | 4 |
| US_R006 | Train | No | 89 | 82 | 0 | 7 |
| US_R007 | Train | No | 58 | 52 | 2 | 4 |
| US_R012 | Test | Yes | 40 | 6 | 19 | 15 |
| ZA_R001 | Test | Yes | 190 | 54 | 98 | 38 |

In addition to the regions listed above, many countries include additional annotations which do not fall within the named region boundaries. These sites will have region codes with the same country code, followed by "Rxxx" (e.g. US_Rxxx). None of these "regions" are cleared, as they may fall anywhere else in the country, and are mostly negative sites found as part of a concerted effort to find more negative examples.

## Train Region Map
![train-regions](https://github.com/user-attachments/assets/c6a12a20-82f1-4bb4-83fa-ed23ad431610)
## Test Region Map
![test-regions](https://github.com/user-attachments/assets/5163b825-8dce-486a-a928-6f18c0a1b448)

# Secondary Dataset
The "secondary dataset" contains Type 4 (positive_pending) annotations, which do not have activity phase labels or imagery associations (they include a single polygon, a start date, and an end date only). While more numerous, none of these regions are cleared, and they do not include any negative examples of heavy construction. 

These sites are not annotated with the same fidelity as the primary dataset, so they may have small date or polygon inconsistencies and are significantly more likely to have null start or end dates. When sites with issues were identified and brought to the data curation team's attention, they were updated or changed to "ignore" status if they were too ambiguous to properly annotate.

All of these regions identifiers are formatted as [country code]_C###
- AE_C001
- AE_C002
- AE_C003
- BO_C001
- BO_C002
- BO_C003
- BR_C005
- BR_C006
- BR_C007
- BR_C008
- BR_C009
- BR_C010
- CL_C001
- CL_C002
- CL_C003
- CL_C004
- CL_C005
- CL_C006
- CN_C000
- CN_C001
- CO_C001
- CO_C002
- CO_C003
- CO_C004
- CO_C005
- CO_C006
- CO_C007
- CO_C008
- CO_C009
- CO_C010
- EC_C001
- EC_C002
- EC_C003
- EC_C004
- EC_C005
- ET_C000
- ID_C001
- IN_C000
- IN_C001
- KW_C001
- MY_C000
- NG_C000
- NG_C001
- PE_C001
- PE_C002
- PE_C003
- PE_C004
- PE_C005
- PE_C006
- PE_C007
- PH_C001
- PY_C001
- QA_C001
- RU_C000
- RU_C001
- SA_C001
- SA_C002
- SA_C003
- SA_C004
- SA_C005
- SN_C000
- TH_C001
- TR_C000
- US_C000
- US_C001
- US_C002
- US_C010
- US_C011
- US_C012
- US_C013
- US_C014
- US_C016
- UY_C001
- UY_C002
- VE_C000
- VE_C001
- VE_C002
- VE_C004
- VN_C001
- VN_C002

## Secondary Regions Map
![secondary-data](https://github.com/user-attachments/assets/43a2e613-ca01-4c39-a3f1-a705fef762dc)
