#!/bin/bash
# This script annotates each solver result with
# an "event tag" (a string that describes the event).
set -e
set -x
set -o pipefail


SCRIPT_DIR="$( cd ${BASH_SOURCE[0]%/*} ; echo $PWD )"

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
        python3 ${SMT_RUNNER_ROOT}/tools/result-info-annotate-with-event.py  \
          ${RESULT_DIR}/output_with_sat_dsoes.yml \
          --timeout 60 \
          --use-dsoes-wallclock-time \
          --wd-base "${RESULT_DIR}/wd" \
          --output ${RESULT_DIR}/output_with_sat_dsoes_tag.yml 2>&1 | \
            tee -i ${RESULT_DIR}/console_annotate_with_event_tag.log
        #git add output_with_sat_dsoes.yml console_extract_dsoes.log
    done
  done
done
