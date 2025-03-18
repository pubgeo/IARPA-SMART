#!/bin/bash

# REPO must point to root directory of METRICS-AND-TEST-FRAMEWORK
REPO="$HOME"
alias python3=python
python3 -V

if ! [ -z "$1" ]; then
    parentdir="$(dirname "$1")"
    REPO=$parentdir
fi
echo "Using $REPO home directory"

TH_COMMIT=$(git log | head -n 1 | cut -d' ' -f2 | head -c 8)

# list of regions to evaluate
REGIONS=("BR_R002" "KR_R002")

# directory with performer site models
INPUT_DIR="$REPO/metrics-and-test-framework/example/input/proposals/"

# run the test harness for each region
for REGION in ${REGIONS[@]}; do

    OUTPUT_DIR="$REPO/metrics-and-test-framework/example/output/$REGION"
    mkdir -p $OUTPUT_DIR

    echo "started evaluation for" $REGION
    date

    OUTPUT_DIR_POLY=$OUTPUT_DIR"/poly"
    mkdir -p $OUTPUT_DIR_POLY
    python3 "$REPO/metrics-and-test-framework/iarpa_smart_metrics/run_evaluation.py" \
        --roi $REGION \
        --gt_dir "$REPO/metrics-and-test-framework/example/input/truth/site_models/" \
        --rm_path "$REPO/metrics-and-test-framework/example/input/truth/region_models/$REGION.geojson" \
        --sm_dir $INPUT_DIR \
        --output_dir $OUTPUT_DIR_POLY \
        --tau 0.2 \
        --rho 0.5 \
        --rho 0.1 \
        --temporal_iop 0.1 \
        --temporal_iop 0.05 \
        --temporal_iop 0.2 \
        --temporal_iop 0.3 \
        --temporal_iop 0.4 \
        --temporal_iop 0.5 \
        --temporal_iot 0.2 \
        --temporal_iot 0.05 \
        --temporal_iot 0.1 \
        --temporal_iot 0.3 \
        --temporal_iot 0.4 \
        --temporal_iot 0.5 \
        --sequestered_id $REGION \

    OUTPUT_DIR_POINT=$OUTPUT_DIR"/point"
    mkdir -p $OUTPUT_DIR_POINT
    python3 "$REPO/metrics-and-test-framework/iarpa_smart_metrics/run_evaluation.py" \
        --roi $REGION \
        --gt_points_file "$REPO/metrics-and-test-framework/example/input/truth/point_based_annotations.geojson" \
        --rm_path "$REPO/metrics-and-test-framework/example/input/truth/region_models/$REGION.geojson" \
        --sm_dir $INPUT_DIR \
        --output_dir $OUTPUT_DIR_POINT \
        --minsd 100 \
        --minsd 0 \
        --minsd 500 \
        --midsd 500 \
        --midsd 1000 \
        --maxsd 1000 \
        --maxsd 1500 \
        --mintd 730 \
        --mintd 365 \
        --mintd 1095 \
        --sequestered_id $REGION \

    echo "finished evaluation for" $REGION
    date
done

