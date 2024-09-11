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
  --pdf "result/${bset}/portfolio_${bset}_100.pdf"
#  --pdf "result/${bset}/ablation_${bset}.pdf"
)



DIR_PREFIX="${MERGED_DIR}/${bset}"

if [ "${bset}" = "smtlib_qf_fp" ] || [ "${bset}" = "smtlib_qf_fp_600" ]; then
  SOLVER_NAMES=( \
    bitwuzla \
    portfolio_bitwuzla_colibri \
    portfolio_bitwuzla_jfs \
    portfolio_bitwuzla_coral \
    portfolio_bitwuzla_xsat \
    portfolio_bitwuzla_gosat \
    portfolio_bitwuzla_optsat
  )
  LEGEND_NAMES='["Bitwuzla", "COLIBRI+Bitwuzla", "JFS+Bitwuzla", "CORAL+Bitwuzla", "XSat+Bitwuzla", "goSAT+Bitwuzla", "QSF+Bitwuzla"]'
elif [ "${bset}" = "program_qf_fp" ] || [ "${bset}" = "program_qf_fp_600" ]; then
  SOLVER_NAMES=( \
    bitwuzla \
    portfolio_bitwuzla_colibri \
    portfolio_bitwuzla_jfs \
    portfolio_bitwuzla_gosat \
    portfolio_bitwuzla_optsat
  )
  LEGEND_NAMES='["Bitwuzla", "COLIBRI+Bitwuzla", "JFS+Bitwuzla", "goSAT+Bitwuzla", "QSF+Bitwuzla"]'
fi

SOLVER_FILES=()
for f in ${SOLVER_NAMES[@]}; do
  SOLVER_FILES+=("${DIR_PREFIX}/${f}/output_merged.yml")
done

python3 "${TOOL}" \
  "${TOOL_OPTS[@]}" \
  --legend-name-map <( echo "${LEGEND_NAMES}" ) \
  "${SOLVER_FILES[@]}"
