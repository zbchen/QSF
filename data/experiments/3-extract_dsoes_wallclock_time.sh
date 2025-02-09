#!/bin/bash
# This script extracts the wallclock time of the solver
# run in the container and annotates the results with it.
set -e
set -x
set -o pipefail

SCRIPT_DIR="$( cd ${BASH_SOURCE[0]%/*} ; echo $PWD )"
BASE_DIR="${SCRIPT_DIR}/runs"
CONFIG_ROOT="${SCRIPT_DIR}/configs"

source ${SCRIPT_DIR}/common.sh

TEST=""

mkdir -p "${BASE_DIR}"

for bset in ${bsets[@]}; do
  for n in ${ns[@]}; do
    for solver in ${solvers[@]}; do
      solver_config=$(get_solver_config "${solver}" "${bset}")
      if [ "${solver_config}" = "SKIP" ]; then
        echo "##### SKIPPING #####"
        continue
      fi
      echo "Processing ${solver} run ${n} for ${bset}"
        RESULT_DIR="${BASE_DIR}/${bset}/${solver}/${n}"
        python3 ${SMT_RUNNER_ROOT}/tools/result-info-extract-stat-shim-wallclock.py \
          ${RESULT_DIR}/output_with_sat.yml \
          --base "${RESULT_DIR}/wd" \
          -o ${RESULT_DIR}/output_with_sat_dsoes.yml 2>&1 | \
            tee -i ${RESULT_DIR}/console_extract_dsoes.log
        #git add output_with_sat_dsoes.yml console_extract_dsoes.log
    done
  done
done
