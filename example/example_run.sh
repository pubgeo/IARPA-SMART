#!/bin/bash

# REPO must point to root directory of IARPA-SMART
REPO="$HOME"
alias python3=python
python3 -V
export PYTHONPATH=.

if ! [ -z "$1" ]; then
    parentdir="$(dirname "$1")"
    REPO=$parentdir
fi
echo "Using $REPO home directory"

TH_COMMIT=$(git log | head -n 1 | cut -d' ' -f2 | head -c 8)

# list of regions to evaluate
REGIONS=("BR_R002" "KR_R002")

# parameter threshold values
TAU="0.2"
RHO="0.5"
TEMPORAL_IOT="0.2"
TEMPORAL_IOP="0.1"

# directory with performer site models
INPUT_DIR="$REPO/IARPA-SMART/example/input/proposals/"

# run the test harness for each region
EVAL_NUM=0
for REGION in ${REGIONS[@]}; do
    ((EVAL_NUM++))

    OUTPUT_DIR="$REPO/IARPA-SMART/example/output/$REGION/"
    mkdir -p $OUTPUT_DIR

    echo "started evaluation for" $REGION
    date

    python3 "$REPO/IARPA-SMART/iarpa_smart_metrics/run_evaluation.py" \
        --roi $REGION \
        --gt_dir "$REPO/IARPA-SMART/example/input/truth/site_models/" \
        --rm_dir "$REPO/IARPA-SMART/example/input/truth/region_models/" \
        --sm_dir $INPUT_DIR \
        --output_dir $OUTPUT_DIR \
        --tau $TAU \
        --rho $RHO \
        --temporal_iot $TEMPORAL_IOT \
        --temporal_iop $TEMPORAL_IOP \
        --sequestered_id $REGION

    echo "finished evaluation for" $REGION
    date
done

