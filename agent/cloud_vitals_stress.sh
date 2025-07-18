#!/usr/bin/env bash
# cloud_vitals_stress.sh
# Note: Make sure this is is executable with chmod +x
# Usage: cloud_vitals_stress.sh <class> <duration_in_seconds>

STRESS_CMD="/usr/bin/stress-ng"
CLASS="$1"
DURATION="${2:-60}"  # default to 60s if missing

case "$CLASS" in
  cpu)
    ARGS=(--cpu 2 --cpu-method matrixprod) ;;
  io)
    ARGS=(--iomix 4) ;;
  filesystem)
    ARGS=(--hdd 2 --hdd-bytes 1G) ;;
  *)
    echo "Unknown class: $CLASS"
    exit 1 ;;
esac

exec "$STRESS_CMD" "${ARGS[@]}" -t "${DURATION}s" --metrics-brief
