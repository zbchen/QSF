#!/bin/bash
# This script synthesizes the JFS+MathSAT5 portfolio solver
# results.
set -e
set -x
set -o pipefail

SCRIPT_DIR="$( cd ${BASH_SOURCE[0]%/*} ; echo $PWD )"

source ${SCRIPT_DIR}/common.sh

TEST=""

mkdir -p "${BASE_DIR}"

: ${MERGED_DIR?"Expected MERGED_DIR to be set"}
mkdir -p "${MERGED_DIR}"

TOOL="${SMT_RUNNER_ROOT}/tools/result-info-synthesize-portfolio.py"
#TOOL_OPTS=( \
#  --max-exec-time 60
#)
#echo "111111111111111111111111"
#OTHER_SOLVERS=(mathsat5)
#OTHER_SOLVERS=(z3 cvc5 mathsat5 bitwuzla colibri jfs gosat)
#OTHER_SOLVERS=(colibri jfs coral xsat gosat optsat)
JFS_SOLVER="bitwuzla"
bsets=(smtlib_qf_fp smtlib_qf_fp_600)

#bset="smtlib_qf_fp_600"
#bset="program_qf_fp_600"
#bset="program_qf_fp_600"
for bset in ${bsets[@]}; do
  if [[ "${bset}" == "smtlib_qf_fp" ]]; then
    timeout=60
    OTHER_SOLVERS=(colibri jfs coral xsat gosat optsat)
  if [[ "${bset}" == "smtlib_qf_fp_600" ]]; then
    timeout=600
    OTHER_SOLVERS=(colibri jfs coral xsat gosat optsat)
  if [[ "${bset}" == "program_qf_fp" ]]; then
    timeout=60
    OTHER_SOLVERS=(colibri jfs gosat optsat)
  if [[ "${bset}" == "program_qf_fp_600" ]]; then
    timeout=600
    OTHER_SOLVERS=(colibri jfs gosat optsat)
  else
    echo "ERROR"
    exit 1
  fi

  solver_config=$(get_solver_config "${JFS_SOLVER}" "${bset}")
  echo ${solver_config}
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
        output_dir="${MERGED_DIR}/${bset}/portfolio_${JFS_SOLVER}_${other_solver}"
        mkdir -p "${output_dir}"
        output_file="${output_dir}/output_merged.yml"
        python3 "${TOOL}" \
          --max-exec-time ${timeout} \
          --log-file "${output_dir}/console.log" \
          ${JFS_SOLVER_INPUT} \
          ${OTHER_SOLVER_INPUT} \
          --names \
          ${JFS_SOLVER} \
          ${other_solver} \
          --output ${output_file} 2> /dev/null
    done
  done
done
