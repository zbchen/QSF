#!/bin/bash
set -e
set -x
set -o pipefail


SCRIPT_DIR="$( cd ${BASH_SOURCE[0]%/*} ; echo $PWD )"

source ${SCRIPT_DIR}/common.sh

if [ $# -eq 0 ]; then
  usage
  exit 1
fi
bset="${1}"
timeout="${2}"
#solverX="${3}"
#solverY="${4}"

TOOL_NAME="result-info-plot-scatter-exec-time.py"

function usage() {
  set +x
  echo "$0 <bset> <timeout> [OPTIONS]"
  echo ""
  echo "OPTIONS are the options to ${TOOL_NAME}"
  set -x
}

TOOL="${SMT_RUNNER_ROOT}/tools/${TOOL_NAME}"

solverX="optsat"

if [ "${bset}" = "smtlib_qf_fp" ] || [ "${bset}" = "smtlib_qf_fp_600" ]; then
  OTHER_NAMES=( \
      z3 \
      cvc5 \
      mathsat5 \
      bitwuzla \
      colibri \
      jfs \
      coral \
      xsat \
      gosat \
#      optsat_no_preprocess \
#      optsat_nsga2 \
#      optsat_soea
    )
  LEGEND_NAMES='["Z3", "CVC5", "MathSAT5", "Bitwuzla", "COLIBRI", "JFS", "CORAL", "XSat", "goSAT"]'
#  LEGEND_NAMES='["QSF_NoPre", "QSF_NSGA-II", "QSF_SOEA"]'
elif [ "${bset}" = "program_qf_fp" ] || [ "${bset}" = "program_qf_fp_600" ]; then
  OTHER_NAMES=( \
      z3 \
      cvc5 \
      mathsat5 \
      bitwuzla \
      colibri \
      jfs \
      gosat \
#      optsat_no_preprocess \
#      optsat_nsga2 \
#      optsat_soea
    )
  LEGEND_NAMES='["Z3", "CVC5", "MathSAT5", "Bitwuzla", "COLIBRI", "JFS", "goSAT"]'
#  LEGEND_NAMES='["QSF_NoPre", "QSF_NSGA-II", "QSF_SOEA"]'
fi

DIR_PREFIX="${MERGED_DIR}/${bset}"

solverXName="$(get_solver_name "${solverX}")"

for solverY in ${OTHER_NAMES[@]}; do
    solverYName="$(get_solver_name "${solverY}")"
    TOOL_OPTS=( \
    --max-exec-time ${timeout} \
    --annotate \
    --true-type-fonts \
  #  --annotate-use-legacy-values \
    --title-switch \
    --annotate-timeout-point \
    --output "result/${bset}/scatter_${solverXName}_${solverYName}_${timeout}.pdf"
  )

  TOOL_OPTS+=(--xlabel "${solverXName}")
  TOOL_OPTS+=(--ylabel "${solverYName}")

  python3 "${TOOL}" \
    "${TOOL_OPTS[@]}" \
    "${DIR_PREFIX}/${solverX}/output_merged.yml" \
    "${DIR_PREFIX}/${solverY}/output_merged.yml"

done