#!/bin/bash
set -e
set -x
set -o pipefail


SCRIPT_DIR="$( cd ${BASH_SOURCE[0]%/*} ; echo $PWD )"

source ${SCRIPT_DIR}/common_1.sh

TOOL_NAME="result-info-plot-quantile-plot.py"

function usage() {
  set +x
  echo "$0 <bset> [OPTIONS]"
  echo ""
  echo "OPTIONS are the options to ${TOOL_NAME}"
  set -x
}

TOOL="${SMT_RUNNER_ROOT}/tools/${TOOL_NAME}"

TOOL_OPTS=( \
  --max-exec-time 60 \
  --mode time \
  --true-type-fonts \
)


if [ $# -eq 0 ]; then
  usage
  exit 1
fi
bset="${1}"
bset_upper=$(echo "${bset}" | awk ' { print toupper($0) }')
shift
TOOL_OPTS+=("$@")

#TOOL_OPTS+=(--title "JFS configuration comparison on ${bset_upper}")

DIR_PREFIX="${MERGED_DIR}/${bset}"

if [ "${bset}" = "qf_fp" ] || [ "${bset}" = "smtlib_qf_fp" ]; then
  SOLVER_NAMES=( \
    z3 \
    cvc5 \
    mathsat5 \
    bitwuzla \
    colibri \
  #  jfs_lf_fail_fast \
    jfs_lf_fail_fast_smart_seeds \
    ol1v3r \
    coral_pso \
  #  coral_avm \
    xsat \
    gosat \
    optsat \
    optsatBitwuzla \
#    portfolio_optsat_bitwuzla \
  )
#  LEGEND_NAMES='["Z3", "CVC5", "MathSAT5", "Bitwuzla", "COLIBRI", "JFS", "OL1V3R", "CORAL", "XSat", "goSAT", "QSat", "QSat_Bitwuzla", "QSat+Bitwuzla"]'
  LEGEND_NAMES='["Z3", "CVC5", "MathSAT5", "Bitwuzla", "COLIBRI", "JFS", "OL1V3R", "CORAL", "XSat", "goSAT", "QSF", "QSat+Bitwuzla"]'
elif [ "${bset}" = "program_qf_fp" ]; then
  SOLVER_NAMES=( \
    z3 \
    cvc5 \
    mathsat5 \
    bitwuzla \
    colibri \
    jfs_lf_fail_fast_smart_seeds \
    ol1v3r \
    gosat \
    optsat \
#    optsatBitwuzla \
  )
  LEGEND_NAMES='["Z3", "CVC5", "MathSAT5", "Bitwuzla", "COLIBRI", "JFS", "OL1V3R", "goSAT", "QSF"]'
else
  SOLVER_NAMES=( \
    colibri \
    cvc5 \
    bitwuzla \
    jfs_lf_fail_fast_smart_seeds \
    mathsat5 \
    z3 \
    portfolio_jfs_mathsat5 \
  )
  LEGEND_NAMES='["COLIBRI", "CVC5", "Bitwuzla", "JFS", "MathSAT5",  "Z3", "JFS+MathSAT5"]'
fi

SOLVER_FILES=()
for f in ${SOLVER_NAMES[@]}; do
  SOLVER_FILES+=("${DIR_PREFIX}/${f}/output_merged.yml")
done

python3 "${TOOL}" \
  "${TOOL_OPTS[@]}" \
  --legend-name-map <( echo "${LEGEND_NAMES}" ) \
  "${SOLVER_FILES[@]}"
