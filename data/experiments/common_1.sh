###############################################################################
# Common functions and data
#
# These are need by various scripts
###############################################################################

# List of solvers to use.
# Look at `get_solver_config()` for the valid solver names.
solvers=( \
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
)

JFS_ENABLE_VALIDATION_VARIANTS="${JFS_ENABLE_VALIDATION_VARIANTS:-0}"

if [ "${JFS_ENABLE_VALIDATION_VARIANTS}" -eq 1 ]; then
  # Add validation variants
  solvers+=( \
    jfs_validate_lf_fail_fast \
    jfs_validate_lf_fail_fast_smart_seeds \
    jfs_validate_pf_fail_fast \
  )
fi

# Benchmark sets to use.
# See `get_invocation_info()` for valid benchmark sets.
#bsets=(qf_fp qf_bvfp qf_bv)
#bsets=(qf_fp qf_bvfp program_qf_fp)
#bsets=(qf_fp)
#bsets=(qf_fp program_qf_fp)
#bsets=(qf_bvfp)
#bsets=(QF_FP_20170501-Heizmann-UltimateAutomizer \
#        QF_FP_20190429-UltimateAutomizerSvcomp2019 \
#        QF_FP_20210211-Vector \
#        QF_FP_20230321-UltimateAutomizerSvcomp2023 \
#        QF_FP_griggio \
#        QF_FP_ramalho \
#        QF_FP_schanda)
#bsets=(smtlib_qf_fp)
#bsets=(smtlib_qf_fp_600)
#bsets=(program_qf_fp)
bsets=(program_qf_fp_600)
#bsets=(gsl_elementary gsl_complex gsl_sf gsl_integration gsl_ploy gsl_odeiv gsl_fit gsl_cdf)
#bsets=(gsl_elementary_600 gsl_complex_600 gsl_sf gsl_integration_600 gsl_ploy_600 gsl_odeiv_600 gsl_fit_600 gsl_cdf_600)

# List of runs to perform.
# It is assumed that the list is a list of integers.
#ns=(0 1 2 3 4)
#ns=(0 1 2 3 4 5 6 7 8 9)

SCRIPT_DIR="$( cd ${BASH_SOURCE[0]%/*} ; echo $PWD )"
#INVOCATIONS_DIR="${SCRIPT_DIR}/../benchmarks/3-stratified-random-sampling"
#INVOCATIONS_DIR="${SCRIPT_DIR}/../benchmarks/smtlib_qf_fp"
INVOCATIONS_DIR="${SCRIPT_DIR}/../benchmarks"

# NOTE: We use more generic configurations for experiment reproduction.
# The commented out path points to the solver configurations actually used for experiments.
#CONFIG_ROOT="${SCRIPT_DIR}/solver_configs/mars"
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
#  base_dir="${SCRIPT_DIR}/../benchmarks/3-stratified-random-sampling/benchmarks/"
   base_dir="${SCRIPT_DIR}/../benchmarks"
   case "${bset}" in
     qf_fp|qf_bv)
       echo "${base_dir}"
     ;;
     program_qf_fp*|gsl_*)
       echo "${base_dir}/program_qf_fp"
     ;;
     smtlib_qf_fp|smtlib_qf_fp_600)
       echo "${base_dir}/smtlib_qf_fp"
     ;;
     qf_bvfp)
       # We used a patched set to workaround bugs in Colibri's SMT-LIB parser
       echo "${base_dir}/patched_qf_bvfp/"
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
    qf_fp)
      echo "${INVOCATIONS_DIR}/qf_fp_filtered_final_3.yml"
    ;;
    qf_bvfp)
      echo "${INVOCATIONS_DIR}/qf_bvfp_filtered_final_ii.yml"
    ;;
    qf_bv)
      echo "${INVOCATIONS_DIR}/qf_bv_filtered_final_ii.yml"
    ;;
    QF_FP_20170501-Heizmann-UltimateAutomizer)
        echo "${INVOCATIONS_DIR}/QF_FP_20170501-Heizmann-UltimateAutomizer.yml"
      ;;
    QF_FP_20190429-UltimateAutomizerSvcomp2019)
        echo "${INVOCATIONS_DIR}/QF_FP_20190429-UltimateAutomizerSvcomp2019.yml"
      ;;
    QF_FP_20210211-Vector)
        echo "${INVOCATIONS_DIR}/QF_FP_20210211-Vector.yml"
      ;;
    QF_FP_20230321-UltimateAutomizerSvcomp2023)
        echo "${INVOCATIONS_DIR}/QF_FP_20230321-UltimateAutomizerSvcomp2023.yml"
      ;;
    QF_FP_griggio)
        echo "${INVOCATIONS_DIR}/QF_FP_griggio.yml"
      ;;
    QF_FP_ramalho)
        echo "${INVOCATIONS_DIR}/QF_FP_ramalho.yml"
      ;;
    QF_FP_schanda)
        echo "${INVOCATIONS_DIR}/QF_FP_schanda.yml"
      ;;
    smtlib_qf_fp|smtlib_qf_fp_600)
        echo "${INVOCATIONS_DIR}/smtlib_qf_fp/smtlib_qf_fp.yml"
      ;;
    gsl_elementary*)
      echo "${INVOCATIONS_DIR}/program_qf_fp/output_files/gsl_elementary.yml"
    ;;
    gsl_complex*)
      echo "${INVOCATIONS_DIR}/program_qf_fp/output_files/gsl_complex.yml"
    ;;
    gsl_sf*)
      echo "${INVOCATIONS_DIR}/program_qf_fp/output_files/gsl_sf.yml"
    ;;
    gsl_integration*)
      echo "${INVOCATIONS_DIR}/program_qf_fp/output_files/gsl_integration_gsl_monte_gsl_deriv.yml"
    ;;
    gsl_ploy*)
      echo "${INVOCATIONS_DIR}/program_qf_fp/output_files/gsl_poly.yml"
    ;;
    gsl_odeiv*)
      echo "${INVOCATIONS_DIR}/program_qf_fp/output_files/gsl_odeiv2_gsl_root_gsl_multiroot.yml"
    ;;
    gsl_fit*)
      echo "${INVOCATIONS_DIR}/program_qf_fp/output_files/gsl_fit_gsl_multifit_gsl_interp_gsl_min_gsl_multimin_gsl_siman.yml"
    ;;
    gsl_cdf*)
      echo "${INVOCATIONS_DIR}/program_qf_fp/output_files/gsl_cdf.yml"
    ;;
    program_qf_fp*)
      echo "${INVOCATIONS_DIR}/program_qf_fp/program_filtered_final.yml"
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
      echo "${CONFIG_ROOT}/z3_docker_generic.yml"
    ;;
    mathsat5)
      case "${bset}" in
        qf_bv)
          echo "${CONFIG_ROOT}/mathsat5_qf_bv_docker_generic.yml"
        ;;
        qf_bvfp|qf_fp|program_qf_fp*|smtlib_qf_fp|smtlib_qf_fp_600|gsl_*)
          echo "${CONFIG_ROOT}/mathsat5_qf_fp_qf_bvfp_docker_generic.yml"
        ;;
        *)
          echo "Unknown bset \"${bset}\""
          exit 1
        ;;
      esac
    ;;
    cvc5)
      echo "${CONFIG_ROOT}/cvc5_docker_generic.yml"
    ;;
    bitwuzla)
      echo "${CONFIG_ROOT}/bitwuzla_docker_generic.yml"
    ;;
    jfs_validate_lf_fail_fast_smart_seeds)
      echo "${CONFIG_ROOT}/model_validate/jfs_lf_fail_fast_smart_seeds_validate_model_docker_generic.yml"
    ;;
    jfs_validate_lf_fail_fast)
      echo "${CONFIG_ROOT}/model_validate/jfs_lf_fail_fast_validate_model_docker_generic.yml"
    ;;
    jfs_validate_pf_fail_fast)
      echo "${CONFIG_ROOT}/model_validate/jfs_pf_fail_fast_validate_model_docker_generic.yml"
    ;;
    jfs_lf_fail_fast)
      echo "${CONFIG_ROOT}/jfs_lf_fail_fast_docker_generic.yml"
    ;;
    jfs_lf_fail_fast_smart_seeds)
      echo "${CONFIG_ROOT}/jfs_lf_fail_fast_smart_seeds_docker_generic.yml"
    ;;
    jfs_pf_fail_fast)
      echo "${CONFIG_ROOT}/jfs_pf_fail_fast_docker_generic.yml"
    ;;
    colibri)
      # We'll run on all benchmarks even though possibly not sound
      echo "${CONFIG_ROOT}/colibri_docker_generic.yml"
    ;;
    xsat)
      case "${bset}" in
        qf_bv|qf_bvfp|program_qf_fp*|gsl_*)
          # Not supported by XSat.
          echo "SKIP"
        ;;
        qf_fp|smtlib_qf_fp|smtlib_qf_fp_600)
          echo "${CONFIG_ROOT}/xsat_docker_generic.yml"
        ;;
        *)
          echo "Unrecognised bset \"${bset}\""
          exit 1
      esac
    ;;
    gosat)
      case "${bset}" in
        qf_bv)
          # Not supported by goSAT.
          echo "SKIP"
        ;;
        qf_fp|qf_bvfp|program_qf_fp*|smtlib_qf_fp|smtlib_qf_fp_600|gsl_*)
          echo "${CONFIG_ROOT}/gosat_docker_generic.yml"
        ;;
        *)
          echo "Unrecognised bset \"${bset}\""
          exit 1
      esac
    ;;
    optsat)
      case "${bset}" in
        qf_bv)
          # Not supported by goSAT.
          echo "SKIP"
        ;;
        qf_fp|qf_bvfp|program_qf_fp*|smtlib_qf_fp_600|gsl_*)
          echo "${CONFIG_ROOT}/optsat_docker_generic.yml"
        ;;
        *)
          echo "Unrecognised bset \"${bset}\""
          exit 1
      esac
    ;;
    ol1v3r)
      case "${bset}" in
        qf_bv)
          # Not supported by goSAT.
          echo "SKIP"
        ;;
        qf_fp|qf_bvfp|program_qf_fp*|smtlib_qf_fp|smtlib_qf_fp_600|gsl_*)
          echo "${CONFIG_ROOT}/ol1v3r_docker_generic.yml"
        ;;
        *)
          echo "Unrecognised bset \"${bset}\""
          exit 1
      esac
    ;;
    optsatBitwuzla)
      case "${bset}" in
        qf_bv)
          # Not supported by goSAT.
          echo "SKIP"
        ;;
        qf_fp|qf_bvfp|program_qf_fp*|smtlib_qf_fp|smtlib_qf_fp_600|gsl_*)
          echo "${CONFIG_ROOT}/optsatBitwuzla_docker_generic.yml"
        ;;
        *)
          echo "Unrecognised bset \"${bset}\""
          exit 1
      esac
    ;;
    coral_pso)
      case "${bset}" in
        qf_bv|qf_bvfp|program_qf_fp*|gsl_*)
          # Not supported by Coral.
          echo "SKIP"
        ;;
        qf_fp|smtlib_qf_fp|smtlib_qf_fp_600)
          echo "${CONFIG_ROOT}/coral_pso_docker_generic.yml"
        ;;
        *)
          echo "Unrecognised bset \"${bset}\""
          exit 1
      esac
    ;;
    coral_avm)
      case "${bset}" in
        qf_bv|qf_bvfp|program_qf_fp*|gsl_*)
          # Not supported by Coral.
          echo "SKIP"
        ;;
        qf_fp|smtlib_qf_fp|smtlib_qf_fp_600)
          echo "${CONFIG_ROOT}/coral_avm_docker_generic.yml"
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
    jfs*)
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
      echo "QSat"
    ;;
    coral_pso)
      echo "CORAL-PSO"
    ;;
    coral_avm)
      echo "CORAL-AVM"
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
    portfolio_optsat_bitwuzla)
      echo "QSat+Bitwuzla"
    ;;
    *)
      echo "Unrecognised solver \"${1}\""
      exit 1
  esac
}
