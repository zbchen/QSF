#!/bin/bash
set -e
set -x
set -o pipefail


SCRIPT_DIR="$( cd ${BASH_SOURCE[0]%/*} ; echo $PWD )"

source ${SCRIPT_DIR}/common.sh

TOOL_NAME="result-info-plot-scatter-exec-time.py"

function usage() {
  set +x
  echo "$0 <bset> <solverX> <solverY> [OPTIONS]"
  echo ""
  echo "OPTIONS are the options to ${TOOL_NAME}"
  set -x
}

TOOL="${SMT_RUNNER_ROOT}/tools/${TOOL_NAME}"



if [ $# -eq 0 ]; then
  usage
  exit 1
fi
bset="${1}"
bset_upper=$(echo "${bset}" | awk ' { print toupper($0) }')
shift
solverX="${1}"
shift
solverY="${1}"
shift

TOOL_OPTS=( \
  --max-exec-time 600 \
  --annotate \
  --true-type-fonts \
#  --annotate-use-legacy-values \
  --annotate-timeout-point \
  --output "/home/aaa/PlatQSF/data/experiments/result/${bset}/qsf_${solverY}_program_600.pdf" \
)
TOOL_OPTS+=("$@")

#TOOL_OPTS+=(--title "JFS configuration comparison on ${bset_upper}")

DIR_PREFIX="${MERGED_DIR}/${bset}"

solverXName="$(get_solver_name "${solverX}")"
solverYName="$(get_solver_name "${solverY}")"

TOOL_OPTS+=(--xlabel "${solverXName}")
TOOL_OPTS+=(--ylabel "${solverYName}")

python3 "${TOOL}" \
  "${TOOL_OPTS[@]}" \
  "${DIR_PREFIX}/${solverX}/output_merged.yml" \
  "${DIR_PREFIX}/${solverY}/output_merged.yml" \
