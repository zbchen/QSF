#!/bin/bash
# This script performs post-processing of solver results
# to extract satisfiability and label the results with
# this information.
set -x
set -e
set -o pipefail

SCRIPT_DIR="$( cd ${BASH_SOURCE[0]%/*} ; echo $PWD )"

. ${SCRIPT_DIR}/common.sh
EXTRACT_TOOL="${SMT_RUNNER_ROOT}/tools/result-info-extract-satisfiability-result.py"

#TEST="echo"
TEST=""

mkdir -p "${BASE_DIR}"

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

        RESULT_DIR="${BASE_DIR}/${bset}/${solver}/${n}"
        mkdir -p "${RESULT_DIR}"

        ${TEST} python3 "${EXTRACT_TOOL}" \
          -o "${RESULT_DIR}/output_with_sat.yml" \
          --base "${RESULT_DIR}/wd" \
          "${RESULT_DIR}/output.yml" 2>&1 | tee -i "${RESULT_DIR}/extract_sat.console.log"

      done
  done
done
