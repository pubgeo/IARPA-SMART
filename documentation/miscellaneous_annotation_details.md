# Miscellaneous annotation information

<a name="annotations-status-type-categories"></a>

## Annotation Status Type Categories

The list of labels below describes the possible values of the 'status' field in the site_model specification. This information applies to site models included in the SMART Heavy Construction Dataset. It is recommended that system outputs also conform to these guidelines.

* Positive Type: true positive (TP) if detected, false negative (FN) if missed
  * positive_annotated (+)
  * positive_annotated_static (+)
  * positive_partial (+)
  * positive_partial_static (+)
  * positive_pending

* Negative Type: false positive (FP) if detected, true negative (TN) if missed
  * negative
  * positive_excluded

* Ignore Type: no impact on evaluation score regardless of whether it is successfully detected or missed
  * ignore
  * positive_unbounded

* (+) Denotes a positive type that includes activity phase labels


<a name="Activity Phase Labels"></a>
