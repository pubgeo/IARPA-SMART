# Miscellaneous annotation information

<a name="annotations-status-type-categories"></a>

## Annotation Status Type Categories

The list of labels below describes the possible values of the 'status' field in the site_model specification. This information applies to site models included in the SMART Heavy Construction Dataset. It is recommended that system outputs also conform to these guidelines. See [here](https://github.com/pubgeo/IARPA-SMART/edit/main/README.md#annotation-types) for a description of annotation types 1-4.

* Positive Type: true positive (TP) if detected, false negative (FN) if missed
  * positive_annotated (Type 1) [+] 
  * positive_annotated_static (Type 1) [+]
  * positive_partial (Type 2) [+]
  * positive_pending (Type 4)

* Negative Type: false positive (FP) if detected, true negative (TN) if missed
  * negative (Type 3)
  * positive_excluded (Type 3)

* Ignore Type: no impact on evaluation score regardless of whether it is successfully detected or missed
  * ignore (Type 3)
  * positive_unbounded

* [+] Denotes a positive type that includes activity phase labels


<a name="Activity Phase Labels"></a>
