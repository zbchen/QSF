#!/bin/bash
# This script runs the experiments. See `common.sh`
# for the solvers and benchmark suites that will
# be used.
set -x
set -e
set -o pipefail

SCRIPT_DIR="$( cd ${BASH_SOURCE[0]%/*} ; echo $PWD )"

# For the `mars` machine we used the commented out values
# below. However for reproducing experiments we have provied
# more conservative values.
#
# JOBS="13"
# USE_SCRIPT_CPU_PIN=1
# USE_DISK_CACHE_FLUSH=1
JOBS="70"
USE_SCRIPT_CPU_PIN=0
USE_DISK_CACHE_FLUSH=0

. ${SCRIPT_DIR}/common.sh
BATCH_RUNNER="${SMT_RUNNER_ROOT}/batch-runner.py"


# FIXME: Remove the echo
#TEST="echo"
TEST=""
START_TIME="$(date +%s)"

TASK_SET_CMD=()
if [ "${USE_SCRIPT_CPU_PIN}" -eq 1 ]; then
  TASK_SET_CMD=(taskset --cpu-list 0-2)
fi

mkdir -p "${BASE_DIR}"

export PYTHONPATH=/usr/bin/python3.6/site-packages/yaml:$PYTHONPATH

for bset in ${bsets[@]}; do
  for n in ${ns[@]}; do
    for solver in ${solvers[@]}; do
      echo "###############################################################################"
      echo "# Running ${solver} run ${n} on ${bset}"
      echo "###############################################################################"

        # Find solver config
        solver_config=$(get_solver_config "${solver}" "${bset}")
        if [ "${solver_config}" = "SKIP" ]; then
          echo "##### SKIPPING #####"
          continue
        fi
        if [ ! -f "${solver_config}" ]; then
          echo "Cannot find solver config \"${solver_config}\""
          exit 1
        fi

        # Find invocation info
        invocation_info=$(get_invocation_info "${bset}")
        if [ ! -e "${invocation_info}" ]; then
          echo "invocation info \"${invocation_info}\" does not exist"
          exit 1
        fi

        # Find benchmark base
        BENCHMARK_BASE=$(get_benchmark_base "${bset}")
        if [ ! -d "${BENCHMARK_BASE}" ]; then
          echo "Benchmark base \"${BENCHMARK_BASE}\" doest not exist"
          exit 1
        fi

        RESULT_DIR="${BASE_DIR}/${bset}/${solver}/${n}"
        if [ -d "${RESULT_DIR}" ]; then
          # 如果结果目录存在，则检查输出文件是否存在
          if [ -f "${RESULT_DIR}/output.yml" ]; then
            echo "Output file already exists for ${solver} run ${n} on ${bset}, skipping..."
            continue
          fi
          # 删除结果目录中的所有内容
          rm -rf "${RESULT_DIR}"
        fi
        mkdir -p "${RESULT_DIR}"
        if [ "${USE_DISK_CACHE_FLUSH}" -eq 1 ]; then
          # To try to prevent disk cache from skewing execution times clear disk cache
          echo "$(date): Flushing disk cache..."
          # HACK: Needs passwordless sudo
          sudo sync && sudo sh -c 'echo 3 > /proc/sys/vm/drop_caches'
          echo "$(date): Flushing disk cache...done"
        fi

        # Give script access to CPUS 0,1,2
        # NOTE: For running on the mars machine we used
        # but that's removed for the artifact so that its
        # easier to reproduce experiments.
        # ${TEST} taskset --cpu-list 0-2 "${BATCH_RUNNER}" \
        ${TEST} python3 "${BATCH_RUNNER}" \
          -j${JOBS} \
          --benchmark-base "${BENCHMARK_BASE}" \
          --log-show-src-locs \
          "${solver_config}" \
          "${invocation_info}" \
          "${RESULT_DIR}/wd" \
          "${RESULT_DIR}/output.yml" 2>&1 | tee -i "${RESULT_DIR}/console.log"
      done
  done
done

END_TIME="$(date +%s)"
echo "Total time to run"
python3 -c "import datetime; print(datetime.timedelta(seconds=(${END_TIME} - ${START_TIME})))"
