###############################################################################
# Common functions and data
#
# These are need by various scripts
###############################################################################

# List of solvers to use.
# Look at `get_solver_config()` for the valid solver names.
solvers=( \
#  z3 \
#  cvc5 \
#  mathsat5 \
#  bitwuzla \
#  colibri \
#  jfs \
#  ol1v3r \
#  coral \
#  xsat \
#  gosat \
#  optsat \
  optsat_soeacov \
#  optsat_soeadis \
#  optsat_nsga2 \
#  optsat_no_preprocess \
#  optsatBitwuzla
)

# Benchmark sets to use.
# See `get_invocation_info()` for valid benchmark sets.
bsets=(smtlib_qf_fp program_qf_fp smtlib_qf_fp_600 program_qf_fp_600)

# List of runs to perform.
# It is assumed that the list is a list of integers.
#ns=(0 1 2 3 4)
ns=(0 1 2 3 4 5 6 7 8 9)
#ns=(0 1)

SCRIPT_DIR="$( cd ${BASH_SOURCE[0]%/*} ; echo $PWD )"
INVOCATIONS_DIR="${SCRIPT_DIR}/../benchmarks"

# NOTE: We use more generic configurations for experiment reproduction.
# The commented out path points to the solver configurations actually used for experiments.
CONFIG_ROOT="${SCRIPT_DIR}/solver_configs/generic"

RUNS_DIR_SUFFIX=""
BASE_DIR="${SCRIPT_DIR}/runs${RUNS_DIR_SUFFIX}"
SMT_RUNNER_ROOT="${SMT_RUNNER_ROOT:-${SCRIPT_DIR}/../../smt-runner}"
USE_VIRTUAL_ENV="${USE_VIRTUAL_ENV:-0}"
VIRTUALENV_SCRIPT="${SMT_RUNNER_ROOT}/venv/bin/activate"

if [ "${USE_VIRTUAL_ENV}" -eq 1 ]; then
  if [ -f "${VIRTUALENV_SCRIPT}" ]; then
    source "${VIRTUALENV_SCRIPT}"
  fi
fi

MERGED_DIR="${SCRIPT_DIR}/merged${RUNS_DIR_SUFFIX}"

function get_benchmark_base() {
  bset="$1"
   base_dir="${SCRIPT_DIR}/../benchmarks"
   case "${bset}" in
     program_qf_fp*)
       echo "${base_dir}/program_qf_fp"
     ;;
     smtlib_qf_fp*)
       echo "${base_dir}/smtlib_qf_fp"
     ;;
     *)
     echo "Unrecognised bset \"${bset}\""
     exit 1
   esac
}


function get_invocation_info() {
  : ${INVOCATIONS_DIR?"INVOCATIONS_DIR must be specified"}
  bset="$1"
  case "${bset}" in
    smtlib_qf_fp*)
        echo "${INVOCATIONS_DIR}/smtlib_qf_fp/smtlib_qf_fp.yml"
      ;;
    program_qf_fp*)
      echo "${INVOCATIONS_DIR}/program_qf_fp/program_qf_fp.yml"
    ;;
    *)
      echo "Unrecognised bset \"${bset}\""
      exit 1
  esac
}

function is_jfs_solver() {
 solver="$1"
 case ${solver} in
   jfs_*)
     echo 1
   ;;
   *)
     echo 0
   ;;
  esac
}

function get_solver_config() {
  : ${CONFIG_ROOT?"CONFIG_ROOT must be specified"}
  solver="$1"
  bset="$2"
  case "${solver}" in
    z3)
      case "${bset}" in
        program_qf_fp|smtlib_qf_fp)
          echo "${CONFIG_ROOT}/z3_docker_generic.yml"
        ;;
        program_qf_fp_600|smtlib_qf_fp_600)
          echo "${CONFIG_ROOT}/z3_docker_generic_600.yml"
        ;;
        *)
          echo "Unrecognised bset \"${bset}\""
          exit 1
      esac
    ;;
    mathsat5)
      case "${bset}" in
        program_qf_fp|smtlib_qf_fp)
          echo "${CONFIG_ROOT}/mathsat5_qf_fp_qf_bvfp_docker_generic.yml"
        ;;
        program_qf_fp_600|smtlib_qf_fp_600)
          echo "${CONFIG_ROOT}/mathsat5_qf_fp_qf_bvfp_docker_generic_600.yml"
        ;;
        *)
          echo "Unrecognised bset \"${bset}\""
          exit 1
      esac
    ;;
    cvc5)
      case "${bset}" in
        program_qf_fp|smtlib_qf_fp)
          echo "${CONFIG_ROOT}/cvc5_docker_generic.yml"
        ;;
        program_qf_fp_600|smtlib_qf_fp_600)
          echo "${CONFIG_ROOT}/cvc5_docker_generic_600.yml"
        ;;
        *)
          echo "Unrecognised bset \"${bset}\""
          exit 1
      esac
    ;;
    bitwuzla)
      case "${bset}" in
        program_qf_fp|smtlib_qf_fp)
          echo "${CONFIG_ROOT}/bitwuzla_docker_generic.yml"
        ;;
        program_qf_fp_600|smtlib_qf_fp_600)
          echo "${CONFIG_ROOT}/bitwuzla_docker_generic_600.yml"
        ;;
        *)
          echo "Unrecognised bset \"${bset}\""
          exit 1
      esac
    ;;
    colibri)
      case "${bset}" in
        program_qf_fp|smtlib_qf_fp)
          echo "${CONFIG_ROOT}/colibri_docker_generic.yml"
        ;;
        program_qf_fp_600|smtlib_qf_fp_600)
          echo "${CONFIG_ROOT}/colibri_docker_generic_600.yml"
        ;;
        *)
          echo "Unrecognised bset \"${bset}\""
          exit 1
      esac
    ;;
    jfs)
      case "${bset}" in
        program_qf_fp|smtlib_qf_fp)
          echo "${CONFIG_ROOT}/jfs_lf_fail_fast_smart_seeds_docker_generic.yml"
        ;;
        program_qf_fp_600|smtlib_qf_fp_600)
          echo "${CONFIG_ROOT}/jfs_lf_fail_fast_smart_seeds_docker_generic_600.yml"
        ;;
        *)
          echo "Unrecognised bset \"${bset}\""
          exit 1
      esac
    ;;
    xsat)
      case "${bset}" in
        program_qf_fp*)
          # Not supported by XSat.
          echo "SKIP"
        ;;
        smtlib_qf_fp_600)
          echo "${CONFIG_ROOT}/xsat_docker_generic_600.yml"
        ;;
        smtlib_qf_fp)
          echo "${CONFIG_ROOT}/xsat_docker_generic.yml"
        ;;
        *)
          echo "Unrecognised bset \"${bset}\""
          exit 1
      esac
    ;;
    gosat)
      case "${bset}" in
        program_qf_fp|smtlib_qf_fp)
          echo "${CONFIG_ROOT}/gosat_docker_generic.yml"
        ;;
        program_qf_fp_600|smtlib_qf_fp_600)
          echo "${CONFIG_ROOT}/gosat_docker_generic_600.yml"
        ;;
        *)
          echo "Unrecognised bset \"${bset}\""
          exit 1
      esac
    ;;
    optsat)
      case "${bset}" in
        program_qf_fp|smtlib_qf_fp)
          echo "${CONFIG_ROOT}/optsat_docker_generic.yml"
        ;;
        program_qf_fp_600|smtlib_qf_fp_600)
          echo "${CONFIG_ROOT}/optsat_docker_generic_600.yml"
        ;;
        *)
          echo "Unrecognised bset \"${bset}\""
          exit 1
      esac
    ;;
    optsat_nsga2)
      case "${bset}" in
        program_qf_fp|smtlib_qf_fp)
          echo "${CONFIG_ROOT}/optsat_nsga2_docker_generic.yml"
        ;;
        program_qf_fp_600|smtlib_qf_fp_600)
          echo "${CONFIG_ROOT}/optsat_nsga2_docker_generic_600.yml"
        ;;
        *)
          echo "Unrecognised bset \"${bset}\""
          exit 1
      esac
    ;;
    optsat_soeacov)
      case "${bset}" in
        program_qf_fp|smtlib_qf_fp)
          echo "${CONFIG_ROOT}/optsat_soeacov_docker_generic.yml"
        ;;
        program_qf_fp_600|smtlib_qf_fp_600)
          echo "${CONFIG_ROOT}/optsat_soeacov_docker_generic_600.yml"
        ;;
        *)
          echo "Unrecognised bset \"${bset}\""
          exit 1
      esac
    ;;
    optsat_soeadis)
      case "${bset}" in
        program_qf_fp|smtlib_qf_fp)
          echo "${CONFIG_ROOT}/optsat_soeadis_docker_generic.yml"
        ;;
        program_qf_fp_600|smtlib_qf_fp_600)
          echo "${CONFIG_ROOT}/optsat_soeadis_docker_generic_600.yml"
        ;;
        *)
          echo "Unrecognised bset \"${bset}\""
          exit 1
      esac
    ;;
    optsat_no_preprocess)
      case "${bset}" in
        program_qf_fp|smtlib_qf_fp)
          echo "${CONFIG_ROOT}/optsat_no_preprocess_docker_generic.yml"
        ;;
        program_qf_fp_600|smtlib_qf_fp_600)
          echo "${CONFIG_ROOT}/optsat_no_preprocess_docker_generic_600.yml"
        ;;
        *)
          echo "Unrecognised bset \"${bset}\""
          exit 1
      esac
    ;;
    ol1v3r)
      case "${bset}" in
        program_qf_fp*)
          # Not supported by XSat.
          echo "SKIP"
        ;;
        smtlib_qf_fp)
          echo "${CONFIG_ROOT}/ol1v3r_docker_generic.yml"
        ;;
        smtlib_qf_fp_600)
          echo "${CONFIG_ROOT}/ol1v3r_docker_generic_600.yml"
        ;;
        *)
          echo "Unrecognised bset \"${bset}\""
          exit 1
      esac
    ;;
    optsatBitwuzla)
      case "${bset}" in
        program_qf_fp|smtlib_qf_fp)
          echo "${CONFIG_ROOT}/optsatBitwuzla_docker_generic.yml"
        ;;
        program_qf_fp_600|smtlib_qf_fp_600)
          echo "${CONFIG_ROOT}/optsatBitwuzla_docker_generic_600.yml"
        ;;
        *)
          echo "Unrecognised bset \"${bset}\""
          exit 1
      esac
    ;;
    coral)
      case "${bset}" in
        program_qf_fp*)
          # Not supported by XSat.
          echo "SKIP"
        ;;
        smtlib_qf_fp)
          echo "${CONFIG_ROOT}/coral_pso_docker_generic.yml"
        ;;
        smtlib_qf_fp_600)
          echo "${CONFIG_ROOT}/coral_pso_docker_generic_600.yml"
        ;;
        *)
          echo "Unrecognised bset \"${bset}\""
          exit 1
      esac
    ;;
    *)
      echo "Unrecognised solver \"${1}\""
      exit 1
  esac
}

function get_solver_name() {
  solver="$1"
  case "${solver}" in
    z3)
      echo "Z3"
    ;;
    mathsat5)
      echo "MathSAT5"
    ;;
    jfs)
      echo "JFS"
    ;;
    colibri)
      echo "COLIBRI"
    ;;
    xsat)
      echo "XSat"
    ;;
    gosat)
      echo "goSAT"
    ;;
    optsat)
      echo "QSF"
    ;;
    optsat_nsga2)
      echo "QSF_NSGA-II"
    ;;
    optsat_soeacov)
      echo "QSF_SOEACov"
    ;;
    optsat_soeadis)
      echo "QSF_SOEADis"
    ;;
    optsat_no_preprocess)
      echo "QSF_NoPre"
    ;;
    coral)
      echo "CORAL"
    ;;
    cvc5)
      echo "CVC5"
    ;;
    bitwuzla)
      echo "Bitwuzla"
    ;;
    ol1v3r)
      echo "OL1V3R"
    ;;
    optsatBitwuzla)
      echo "QSF_Bitwuzla"
    ;;
#    portfolio_optsat_bitwuzla)
#      echo "QSF+Bitwuzla"
#    ;;
#    portfolio_colibri_bitwuzla)
#      echo "COLIBRI+Bitwuzla"
#    ;;
#    portfolio_jfs_bitwuzla)
#      echo "JFS+Bitwuzla"
#    ;;
#    portfolio_coral_bitwuzla)
#      echo "CORAL+Bitwuzla"
#    ;;
#    portfolio_xsat_bitwuzla)
#      echo "XSat+Bitwuzla"
#    ;;
#    portfolio_gosat_bitwuzla)
#      echo "goSAT+Bitwuzla"
#    ;;
#    portfolio_z3_optsat)
#      echo "Z3+QSF"
#    ;;
#    portfolio_cvc5_optsat)
#      echo "CVC5+QSF"
#    ;;
#    portfolio_mathsat5_optsat)
#      echo "MathSAT5+QSF"
#    ;;
#    portfolio_bitwuzla_optsat)
#      echo "Bitwuzla+QSF"
#    ;;
#    portfolio_colibri_optsat)
#      echo "COLIBRI+QSF"
#    ;;
#    portfolio_jfs_optsat)
#      echo "JFS+QSF"
#    ;;
#    portfolio_gosat_optsat)
#      echo "goSAT+QSF"
#    ;;
    *)
      echo "Unrecognised solver \"${1}\""
      exit 1
  esac
}
