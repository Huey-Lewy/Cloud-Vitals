  GNU nano 7.2                                 cloud_vitals_stress.sh
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
  swap)
    TOTAL_MEM=$(grep MemTotal /proc/meminfo | awk '{print $2*1024}')
    ARGS=(--vm 1 --vm-bytes "${TOTAL_MEM}b" --mmap 1 --mmap-bytes 512M --page-in) ;;
  net)
    ARGS=(--udp 2 --udp-port 50000) ;;
  *)
    echo "Unknown class: $CLASS"
    exit 1 ;;
esac