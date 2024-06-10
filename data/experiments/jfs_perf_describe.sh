#!/bin/bash
set -e
set -x
set -o pipefail


SCRIPT_DIR="$( cd ${BASH_SOURCE[0]%/*} ; echo $PWD )"

source ${SCRIPT_DIR}/common.sh

TOOL_NAME="result-info-merged-event-count.py"

function usage() {
  set +x
  echo "$0 <bset> [OPTIONS]"
  echo ""
  echo "OPTIONS are the options to ${TOOL_NAME}"
  set -x
}

TOOL="${SMT_RUNNER_ROOT}/tools/${TOOL_NAME}"

TOOL_OPTS=( \
  --index-for-compute-sets 0
)


if [ $# -eq 0 ]; then
  usage
  exit 1
fi
bset="${1}"
bset_upper=$(echo "${bset}" | awk ' { print toupper($0) }')
shift
TOOL_OPTS+=("$@")

DIR_PREFIX="${MERGED_DIR}/${bset}"

EXTRA_CONFIGS=()

if [ "${bset}" = "qf_fp" ]; then
  #EXTRA_CONFIGS+=("${DIR_PREFIX}/jfs_lf_try_all/output_merged.yml")
  #EXTRA_CONFIGS+=("${DIR_PREFIX}/jfs_lf_try_all_smart_seeds/output_merged.yml")
  echo "Not adding extra"
else
  echo "Nothing to add"
fi

python3 "${TOOL}" \
  "${TOOL_OPTS[@]}" \
  "${DIR_PREFIX}/jfs_lf_fail_fast_smart_seeds/output_merged.yml" \
  "${DIR_PREFIX}/jfs_pf_fail_fast/output_merged.yml" \
  "${DIR_PREFIX}/jfs_lf_fail_fast/output_merged.yml" "${EXTRA_CONFIGS[@]}"
