#!/bin/bash
# This script synthesizes the JFS+MathSAT5 portfolio solver
# results.
set -e
set -x
set -o pipefail

SCRIPT_DIR="$( cd ${BASH_SOURCE[0]%/*} ; echo $PWD )"

source ${SCRIPT_DIR}/common_1.sh

TEST=""

mkdir -p "${BASE_DIR}"

: ${MERGED_DIR?"Expected MERGED_DIR to be set"}
mkdir -p "${MERGED_DIR}"

TOOL="${SMT_RUNNER_ROOT}/tools/result-info-synthesize-portfolio.py"
TOOL_OPTS=( \
  --max-exec-time 60
)

#OTHER_SOLVERS=(mathsat5)
OTHER_SOLVERS=(bitwuzla)
JFS_SOLVER="optsat"
bset="QF_FP_final"
solver_config=$(get_solver_config "${JFS_SOLVER}" "${bset}")
if [ "${solver_config}" = "SKIP" ]; then
  echo "ERROR"
  exit 1
fi

for other_solver in ${OTHER_SOLVERS[@]}; do
  for bset in ${bsets[@]}; do
      solver_config=$(get_solver_config "${other_solver}" "${bset}")
      if [ "${solver_config}" = "SKIP" ]; then
        echo "ERROR"
        exit 1
      fi

      OTHER_SOLVER_INPUT="${MERGED_DIR}/${bset}/${other_solver}/output_merged.yml"
      if [ ! -e "${OTHER_SOLVER_INPUT}" ]; then
        echo "${OTHER_SOLVER_INPUT} does not exist"
        exit 1
      fi
      JFS_SOLVER_INPUT="${MERGED_DIR}/${bset}/${JFS_SOLVER}/output_merged.yml"
      if [ ! -e "${JFS_SOLVER_INPUT}" ]; then
        echo "${JFS_SOLVER_INPUT} does not exist"
        exit 1
      fi
      output_dir="${MERGED_DIR}/${bset}/portfolio_optsat_${other_solver}"
      mkdir -p "${output_dir}"
      output_file="${output_dir}/output_merged.yml"
      python3 "${TOOL}" \
        "${TOOL_OPTS[@]}" \
        --log-file "${output_dir}/console.log" \
        ${JFS_SOLVER_INPUT} \
        ${OTHER_SOLVER_INPUT} \
        --names \
        optsat \
        ${other_solver} \
        --output ${output_file} 2> /dev/null
  done
done
