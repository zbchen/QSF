#!/bin/bash
set -e
set -o pipefail

SCRIPT_DIR="$( cd ${BASH_SOURCE[0]%/*} ; echo $PWD )"
source "${SCRIPT_DIR}/common.sh"

EVENT_COUNT_TOOL="${SMT_RUNNER_ROOT}/tools/result-info-event-count.py"
EVENT_COUNT_DEBUG=${EVENT_COUNT_DEBUG:-0}
EVENT_COUNT_EXTRA_ARGS=()

if [ "${EVENT_COUNT_DEBUG}" -ne 0 ]; then
  echo "Passing debug args"
  EVENT_COUNT_EXTRA_ARGS+=(-l debug)
fi

if [ $# -lt 1 ]; then
  echo "require just one arg"
  exit 1
fi

OUTPUT_DIR="$1"
shift

if [ ! -d "${OUTPUT_DIR}" ]; then
  echo "\"${OUTPUT_DIR}\" is not a directory"
  exit 1
fi

python3 "${EVENT_COUNT_TOOL}" \
  "${OUTPUT_DIR}/output_with_sat.yml" \
  --wd-base "${OUTPUT_DIR}/wd" "${EVENT_COUNT_EXTRA_ARGS[@]}" "${@}"
