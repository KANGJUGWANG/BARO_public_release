#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCORER="${SCRIPT_DIR}/phase_14_1a_baseline_scoring.py"
AGGREGATOR="${SCRIPT_DIR}/phase_14_1a_aggregate_chunks.py"

OUTPUT_ROOT="/tmp/baro_phase14_1a_full"
WINDOW_DAYS=28
ROUNDTRIP_LIMIT=0
ONEWAY_LIMIT=0
ROUTES="ICN-NRT,NRT-ICN,ICN-HND,HND-ICN"
TRIPS="roundtrip,oneway"
CONTINUE_ON_ERROR=0
SKIP_EXISTING=0
RUN_AGGREGATE=0
LOG_FILE=""

usage() {
  cat <<'EOF'
Usage: phase_14_1a_run_chunks.sh [options]

Options:
  --output-root PATH       Output root directory.
  --window-days N          Baseline window days. Default: 28.
  --roundtrip-limit N      limit_rows for roundtrip chunks. 0 means full.
  --oneway-limit N         limit_rows for oneway chunks. 0 means full.
  --routes CSV             Route list. Default: ICN-NRT,NRT-ICN,ICN-HND,HND-ICN.
  --trips CSV              Trip list. Default: roundtrip,oneway.
  --continue-on-error      Continue after a failed chunk.
  --skip-existing          Skip chunk dirs that already contain summary.json.
  --aggregate              Run aggregate after chunks.
  --log-file PATH          Tee stdout/stderr to a log file.
  -h, --help               Show this help.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --output-root) OUTPUT_ROOT="$2"; shift 2 ;;
    --window-days) WINDOW_DAYS="$2"; shift 2 ;;
    --roundtrip-limit) ROUNDTRIP_LIMIT="$2"; shift 2 ;;
    --oneway-limit) ONEWAY_LIMIT="$2"; shift 2 ;;
    --routes) ROUTES="$2"; shift 2 ;;
    --trips) TRIPS="$2"; shift 2 ;;
    --continue-on-error) CONTINUE_ON_ERROR=1; shift ;;
    --skip-existing) SKIP_EXISTING=1; shift ;;
    --aggregate) RUN_AGGREGATE=1; shift ;;
    --log-file) LOG_FILE="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [ -n "$LOG_FILE" ]; then
  mkdir -p "$(dirname "$LOG_FILE")"
  exec > >(tee -a "$LOG_FILE") 2>&1
fi

RUN_ID="run_$(date +%Y%m%d_%H%M%S)"
OUT="${OUTPUT_ROOT}/${RUN_ID}"
mkdir -p "${OUT}/chunks" "${OUT}/aggregate"

IFS=',' read -r -a ROUTE_LIST <<< "$ROUTES"
IFS=',' read -r -a TRIP_LIST <<< "$TRIPS"

chunk_status_file="${OUT}/chunk_status.csv"
printf "trip_type,route,limit_rows,status,exit_code,started_at,finished_at,chunk_dir\n" > "$chunk_status_file"

echo "RUN_ID=${RUN_ID}"
echo "OUT=${OUT}"
echo "SCORER=${SCORER}"
echo "AGGREGATOR=${AGGREGATOR}"
echo "WINDOW_DAYS=${WINDOW_DAYS}"
echo "TRIPS=${TRIPS}"
echo "ROUTES=${ROUTES}"
echo "ROUNDTRIP_LIMIT=${ROUNDTRIP_LIMIT}"
echo "ONEWAY_LIMIT=${ONEWAY_LIMIT}"

for trip in "${TRIP_LIST[@]}"; do
  trip="$(echo "$trip" | xargs)"
  if [ "$trip" = "oneway" ]; then
    limit_rows="$ONEWAY_LIMIT"
  elif [ "$trip" = "roundtrip" ]; then
    limit_rows="$ROUNDTRIP_LIMIT"
  else
    echo "invalid trip: $trip" >&2
    exit 2
  fi

  for route in "${ROUTE_LIST[@]}"; do
    route="$(echo "$route" | xargs)"
    chunk_base="${OUT}/chunks/${trip}_${route}"
    started_at="$(date -Is)"
    if [ "$SKIP_EXISTING" = "1" ] && find "$chunk_base" -name summary.json -type f | grep -q . 2>/dev/null; then
      echo "===== SKIP ${trip} ${route} existing ====="
      printf "%s,%s,%s,skipped,0,%s,%s,%s\n" "$trip" "$route" "$limit_rows" "$started_at" "$(date -Is)" "$chunk_base" >> "$chunk_status_file"
      continue
    fi

    mkdir -p "$chunk_base"
    echo "===== START ${trip} ${route} $(date -Is) limit_rows=${limit_rows} ====="
    args=(
      python3 "$SCORER"
      --window-days "$WINDOW_DAYS"
      --trip "$trip"
      --routes "$route"
      --splits calibration,holdout
      --output-dir "$chunk_base"
      --write-compact-output
    )
    if [ "$limit_rows" != "0" ]; then
      args+=(--limit-rows "$limit_rows")
    fi
    "${args[@]}"
    exit_code=$?
    finished_at="$(date -Is)"
    if [ "$exit_code" = "0" ]; then
      status="success"
    else
      status="failed"
    fi
    printf "%s,%s,%s,%s,%s,%s,%s,%s\n" "$trip" "$route" "$limit_rows" "$status" "$exit_code" "$started_at" "$finished_at" "$chunk_base" >> "$chunk_status_file"
    echo "===== END ${trip} ${route} ${finished_at} status=${exit_code} ====="
    if [ "$exit_code" != "0" ] && [ "$CONTINUE_ON_ERROR" != "1" ]; then
      echo "stopping after failed chunk: ${trip} ${route}" >&2
      exit "$exit_code"
    fi
  done
done

if [ "$RUN_AGGREGATE" = "1" ]; then
  python3 "$AGGREGATOR" \
    --input-dir "${OUT}/chunks" \
    --output-dir "${OUT}/aggregate"
fi

latest_file="${OUTPUT_ROOT}_latest.txt"
echo "$OUT" > "$latest_file"
echo "$OUT" > /tmp/baro_phase14_1a_large_latest.txt
echo "DONE ${OUT}"
