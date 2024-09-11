#!/bin/bash
set -e
set -x
set -o pipefail


SCRIPT_DIR="$( cd ${BASH_SOURCE[0]%/*} ; echo $PWD )"

source ${SCRIPT_DIR}/common_1.sh

if [ $# -eq 0 ]; then
  usage
  exit 1
fi
bset="${1}"
timeout="${2}"
#bset_upper=$(echo "${bset}" | awk ' { print toupper($0) }')
#shift
#TOOL_OPTS+=("$@")

#TOOL_OPTS+=(--title "JFS configuration comparison on ${bset_upper}")

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
  --max-exec-time ${timeout} \
  --mode time \
  --true-type-fonts \
#  --error-bars \
#  --points \
  --title "${timeout}s timeout" \
#  --title-font-size 14 \
#  --label-font-size 12 \
#  --legend-font-size 10 \
#  --tick-font-size 10 \
  --pdf "result/${bset}/portfolio_${bset}.pdf"
#  --pdf "result/${bset}/ablation_${bset}.pdf"
)



DIR_PREFIX="${MERGED_DIR}/${bset}"

if [ "${bset}" = "smtlib_qf_fp" ] || [ "${bset}" = "smtlib_qf_fp_600" ]; then
  SOLVER_NAMES=( \
    bitwuzla \
    portfolio_bitwuzla_colibri \
    portfolio_bitwuzla_jfs_lf_fail_fast_smart_seeds \
    portfolio_bitwuzla_coral_pso \
    portfolio_bitwuzla_xsat \
    portfolio_bitwuzla_gosat \
    portfolio_bitwuzla_optsat
  )
#  LEGEND_NAMES='["Z3", "CVC5", "MathSAT5", "Bitwuzla", "COLIBRI", "JFS", "CORAL", "XSat", "goSAT", "QSF", "COLIBRI+Bitwuzla", "JFS+Bitwuzla", "CORAL+Bitwuzla", "goSAT+Bitwuzla", "QSF+Bitwuzla"]'
#  LEGEND_NAMES='["Z3", "CVC5", "MathSAT5", "Bitwuzla", "COLIBRI", "JFS", "OL1V3R", "CORAL", "XSat", "goSAT", "QSF"]'
  LEGEND_NAMES='["Bitwuzla", "COLIBRI+Bitwuzla", "JFS+Bitwuzla", "CORAL+Bitwuzla", "XSat+Bitwuzla", "goSAT+Bitwuzla", "QSF+Bitwuzla"]'
#  SOLVER_NAMES=( \
#      z3 \
#      cvc5 \
#      mathsat5 \
#      bitwuzla \
#      colibri \
#      jfs_lf_fail_fast_smart_seeds \
#      coral_pso \
#      xsat \
#      gosat \
#      optsat \
#      optsat_soea \
#      optsat_nsga2 \
#      optsat_no_preprocess \
##      optsat
#  )
#  LEGEND_NAMES='["Z3", "CVC5", "MathSAT5", "Bitwuzla", "COLIBRI", "JFS", "CORAL", "XSat", "goSAT", "QSF", "QSF_SOEA", "QSF_NSGA-II", "QSF_NOPreprocess"]'
elif [ "${bset}" = "program_qf_fp" ] || [ "${bset}" = "program_qf_fp_600" ]; then
  SOLVER_NAMES=( \
    optsat \
    portfolio_optsat_z3 \
    portfolio_optsat_cvc5 \
    portfolio_optsat_mathsat5 \
    portfolio_optsat_bitwuzla \
    portfolio_optsat_colibri \
    portfolio_optsat_jfs_lf_fail_fast_smart_seeds \
#    portfolio_optsat_gosat
  )
#  LEGEND_NAMES='["Z3", "CVC5", "MathSAT5", "Bitwuzla", "COLIBRI", "JFS", "OL1V3R", "goSAT", "QSF"]'
  LEGEND_NAMES='["QSF", "Z3+QSF", "CVC5+QSF", "MathSAT5+QSF", "Bitwuzla+QSF", "COLIBRI+QSF", "JFS+QSF"]'
#  SOLVER_NAMES=( \
#      optsat_soea \
#      optsat_nsga2 \
#      optsat_no_preprocess \
#      optsat
#  )
#  LEGEND_NAMES='["QSF_SOEA", "QSF_NSGA-II", "QSF_NOPreprocess", "QSF"]'
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
