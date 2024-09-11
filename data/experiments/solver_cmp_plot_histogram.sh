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
#shift
solverX="${3}"
#shift
solverY="${4}"
#shift

TOOL_NAME="result-info-plot-execution-time-histogram.py"

function usage() {
  set +x
  echo "$0 <bset> <solverX> <solverY> [OPTIONS]"
  echo ""
  echo "OPTIONS are the options to ${TOOL_NAME}"
  set -x
}

TOOL="${SMT_RUNNER_ROOT}/tools/${TOOL_NAME}"

#TOOL_OPTS+=("$@")
#bset_upper=$(echo "${bset}" | awk ' { print toupper($0) }')
#TOOL_OPTS+=(--title "JFS configuration comparison on ${bset_upper}")
TOOL_OPTS=( \
  --max-exec-time ${timeout} \
  --force-title "QSF on ${bset}" \
#  --annotate \
  --true-type-fonts \
#  --annotate-use-legacy-values \
#  --annotate-timeout-point \
#  --output "result/${bset}/${solverX}_${solverY}_${bset}.pdf"
)

DIR_PREFIX="${MERGED_DIR}/${bset}"

#solverXName="$(get_solver_name "${solverX}")"
#solverYName="$(get_solver_name "${solverY}")"

#TOOL_OPTS+=(--xlabel "${solverXName}")
#TOOL_OPTS+=(--ylabel "${solverYName}")

python3 "${TOOL}" \
  "${TOOL_OPTS[@]}" \
  "${DIR_PREFIX}/${solverX}/output_merged.yml" \
#  "${DIR_PREFIX}/${solverY}/output_merged.yml" \
