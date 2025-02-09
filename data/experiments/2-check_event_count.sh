#!/bin/bash
# This script computes the "event tag" for each solver
# result and produces an error if we don't recognise the
# event. This is only a sanity check and can be skipped
# if required.
set -x
set -e
set -o pipefail

SCRIPT_DIR="$( cd ${BASH_SOURCE[0]%/*} ; echo $PWD )"
BASE_DIR="${SCRIPT_DIR}/runs"
CONFIG_ROOT="${SCRIPT_DIR}/configs"

. ${SCRIPT_DIR}/common.sh

FAILS=()

for bset in ${bsets[@]}; do
  for n in ${ns[@]}; do
    for solver in ${solvers[@]}; do
      echo "###############################################################################"
      echo "# Running ${solver} run ${n} on ${bset}"
      echo "###############################################################################"
        # Find solver config
        solver_config=$(get_solver_config "${solver}" "${bset}")
        if [ "${solver_config}" = "SKIP" ]; then
          echo "##### SKIPPING #####"
          continue
        fi

        set +e
        RESULT_DIR="${BASE_DIR}/${bset}/${solver}/${n}"
        RESULT_NAME="${bset}/${solver}/${n}"
        ${SCRIPT_DIR}/event_count.sh "${RESULT_DIR}" --timeout 60
        if [ $? -ne 0 ]; then
          FAILS+=("${RESULT_NAME}")
        fi
      done
  done
done

set +x
for f in "${FAILS[@]}"; do
  echo "FAIL: $f"
done
