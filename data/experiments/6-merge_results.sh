#!/bin/bash
# This script merges multiple repeat runs of a solver into
# a single file.
set -e
set -x
set -o pipefail


SCRIPT_DIR="$( cd ${BASH_SOURCE[0]%/*} ; echo $PWD )"

source ${SCRIPT_DIR}/common.sh

TEST=""

mkdir -p "${BASE_DIR}"

: ${MERGED_DIR?"Expected MERGED_DIR to be set"}
mkdir -p "${MERGED_DIR}"

TOOL_OPTS=()

for bset in ${bsets[@]}; do
  for solver in ${solvers[@]}; do
    solver_config=$(get_solver_config "${solver}" "${bset}")
    if [ "${solver_config}" = "SKIP" ]; then
      echo "##### SKIPPING #####"
      continue
    fi
    yaml_output_files=()
    wd_base_dirs=()
    # Check result info files exist
    for n in ${ns[@]}; do
      echo "processing ${solver} run ${n}"
      wd_base_dir="${BASE_DIR}/${bset}/${solver}/${n}/wd"
      OUTPUT_YML_FILE="${BASE_DIR}/${bset}/${solver}/${n}/output_with_sat_dsoes_tag_throughtput.yml"
      if [ ! -f "${OUTPUT_YML_FILE}" ]; then
        echo "\"${OUTPUT_YML_FILE}\" does not exist"
        exit 1
      fi
      yaml_output_files+=("${OUTPUT_YML_FILE}")
      wd_base_dirs+=("${wd_base_dir}")
    done
    MERGE_OUTPUT_DIR="${MERGED_DIR}/${bset}/${solver}"
    mkdir -p "${MERGE_OUTPUT_DIR}"
    python3 ${SMT_RUNNER_ROOT}/tools/result-info-merge.py \
      "${yaml_output_files[@]}" \
      -o "${MERGE_OUTPUT_DIR}/output_merged.yml" \
      --wd-bases "${wd_base_dirs[@]}" \
      "${TOOL_OPTS[@]}" 2>&1 | \
        tee -i "${MERGE_OUTPUT_DIR}/console_merge_results.log"
  done
done
