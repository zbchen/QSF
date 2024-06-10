#!/bin/bash
set -e
set -x
set -o pipefail


SCRIPT_DIR="$( cd ${BASH_SOURCE[0]%/*} ; echo $PWD )"

source ${SCRIPT_DIR}/common.sh

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
  --max-exec-time 900 \
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

SKIP_TRY_ALL=1
if [ "${1}" = "--skip-try-all" ]; then
  SKIP_TRY_ALL=1
  shift
fi

TOOL_OPTS+=("$@")

#TOOL_OPTS+=(--title "JFS configuration comparison on ${bset_upper}")

DIR_PREFIX="${MERGED_DIR}/${bset}"

EXTRA_CONFIGS=()

if [ "${bset}" = "qf_fp" -a "${SKIP_TRY_ALL}" -eq 0 ]; then
  EXTRA_CONFIGS+=("${DIR_PREFIX}/jfs_lf_try_all/output_merged.yml")
  LEGEND_NAMES='["JFS-NR", "JFS-LF-NS", "JFS-LF-SS", "JFS-LF-NS-TA"]'
else
  LEGEND_NAMES='["JFS-NR", "JFS-LF-NS", "JFS-LF-SS"]'
fi

python3 "${TOOL}" \
  "${TOOL_OPTS[@]}" \
  --legend-name-map <( echo "${LEGEND_NAMES}" ) \
  "${DIR_PREFIX}/jfs_pf_fail_fast/output_merged.yml" \
  "${DIR_PREFIX}/jfs_lf_fail_fast/output_merged.yml" \
  "${DIR_PREFIX}/jfs_lf_fail_fast_smart_seeds/output_merged.yml" "${EXTRA_CONFIGS[@]}"
