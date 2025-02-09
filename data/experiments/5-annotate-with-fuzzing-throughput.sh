#!/bin/bash
# This script annotates the solver results with information
# on the fuzzer throughput (if available). For non-JFS solvers
# this just copies the file across.
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
      RESULT_DIR="${BASE_DIR}/${bset}/${solver}/${n}"
      INPUT_FILE="${RESULT_DIR}/output_with_sat_dsoes_tag.yml"
      OUTPUT_FILE="${RESULT_DIR}/output_with_sat_dsoes_tag_throughtput.yml"
      if [ "$(is_jfs_solver ${solver})" -eq 0 ]; then
        # For non JFS solvers just copy across so we get uniform file naming
        cp "${INPUT_FILE}" "${OUTPUT_FILE}"
        echo "Just copying for solver ${solver}"
        continue
      fi
      echo "Processing ${solver} run ${n} for ${bset}"
      python3 ${SMT_RUNNER_ROOT}/tools/result-info-annotate-with-fuzzing-throughput.py  \
        ${INPUT_FILE} \
        --wd-base "${RESULT_DIR}/wd" \
        --timeout 60 \
        --use-dsoes-wallclock-time \
        --output ${OUTPUT_FILE}  2>&1 | \
          tee -i ${RESULT_DIR}/console_annotate_with_fuzzing_throughtput.log
    done
  done
done
