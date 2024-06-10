# vim: set sw=4 ts=4 softtabstop=4 expandtab:
from collections import namedtuple
from . analysis import is_merged_result_info
from . import util
from . import ResultInfoUtil
import logging
import os
import re

_logger = logging.getLogger(__name__)

GETInfo = namedtuple('GETInfo',
    ['ri', 'wd_base', 'benchmark_base', 'backend'])

def get_event_analyser_from_runner_name(name, *nargs, **kwargs):
    if name == 'Z3':
        return Z3RunnerEventAnalyser(*nargs, **kwargs)
    if name == 'MathSat5':
        return MathSat5RunnerEventAnalyser(*nargs, **kwargs)
    if name == 'Colibri':
         return ColibriRunnerEventAnalyser(*nargs, **kwargs)
    if name == 'goSAT':
        return goSATRunnerEventAnalyser(*nargs, **kwargs)
    if name == 'optSAT':
        return optSATRunnerEventAnalyser(*nargs, **kwargs)
    if name == 'OL1V3R':
        return OL1V3RRunnerEventAnalyser(*nargs, **kwargs)
    if name == 'XSat':
        return XSatRunnerEventAnalyser(*nargs, **kwargs)
    if name == 'Coral':
        return CoralRunnerEventAnalyser(*nargs, **kwargs)
    if name == 'JFS':
        return JFSRunnerEventAnalyser(*nargs, **kwargs)
    if name == 'CVC5':
        return CVC5RunnerEventAnalyser(*nargs, **kwargs)
    if name == 'Bitwuzla':
        return BitwuzlaRunnerEventAnalyser(*nargs, **kwargs)
    if name == 'optSATBitwuzla':
        return optSATBitwuzlaRunnerEventAnalyser(*nargs, **kwargs)
    
    raise Exception('not implemented')

class MergeEventFailure(Exception):
    pass

def get_event_tag(ri):
    """
    Returns (<tag>, <had_event_tag_conflicts>)

    Handles merging event tags if necessary.
    """
    tag = None
    try:
        tag = ri['event_tag']
    except KeyError:
        pass
    if tag is None:
        return (None, False)
    if not is_merged_result_info(ri):
        return (tag, False)
    # Merged result info
    return merge_aggregate_events(tag)

def merge_aggregate_events(events):
    """
        Returns tuple (<event>, <tags_were_mixed>)
    """
    assert isinstance(events, list)
    assert all([ isinstance(e, str) for e in events])
    all_same = set(events)
    if len(all_same) == 1:
        # All events are the same
        return (events[0], False)
    # FIXME: Figure out how to handle mismatched events

    # Handle mix of sat and unsat_but_expected_sat
    sat_count = len(list(filter(lambda tag: tag == 'sat', events)))
    unsat_but_expected_sat_count = len(list(filter(lambda tag: tag == 'unsat_but_expected_sat', events)))

    if sat_count > 0 and unsat_but_expected_sat_count > 0 and (sat_count + unsat_but_expected_sat_count) == len(events):
        # This is bad behaviour and is for XSat. Penalise heavily by saying
        # unsat_but_expected_sat
        return ('unsat_but_expected_sat', True)

    # Handle mix of sat and timeout
    timeout_count = len(list(filter(lambda tag: tag == 'timeout', events)))
    if (timeout_count + sat_count) == len(events):
        return ('sat', True)

    # Handle mix of sat and gosat_unknown
    gosat_unknown_count = len(list(filter(lambda tag: tag == 'gosat_unknown', events)))
    if (gosat_unknown_count + sat_count) == len(events):
        return ('sat', True)
    if (timeout_count + gosat_unknown_count) == len(events): # add by yx
        if timeout_count >= gosat_unknown_count:
            return ('timeout', True)
        else:
            return ('gosat_unknown_count', True)

    optsat_unknown_count = len(list(filter(lambda tag: tag == 'optsat_unknown', events)))
    if (optsat_unknown_count + sat_count) == len(events):
        return ('sat', True)

    # Handle mix of timeout and soft_timeout
    soft_timeout_count = len(list(filter(lambda tag: tag == 'soft_timeout', events)))
    if (timeout_count + soft_timeout_count) == len(events):
        return ('timeout', True)

    # FIXME: This is a hack. Can we do better?
    # Try to Handle 'colibri_generic_unknown', 'timeout'
    # There isn't an obvious way to handle this so just pick the more frequent tag
    colibri_generic_unknown_count = len(list(filter(lambda tag: tag == 'colibri_generic_unknown', events)))
    if (timeout_count + colibri_generic_unknown_count) == len(events):
        if timeout_count >= colibri_generic_unknown_count:
            return ('timeout', True)
        else:
            return ('colibri_generic_unknown', True)

    # add by yx
    colibri_unsat_expected_sat_count = len(list(filter(lambda tag: tag == 'unsat_but_expected_sat', events)))
    if (timeout_count + colibri_unsat_expected_sat_count) == len(events):
        if timeout_count >= colibri_generic_unknown_count:
            return ('timeout', True)
        else:
            return ('colibri_unsat_but_expected_sat_count', True)

    # add by yx
    if sat_count > 0:
        return ('sat', True)
    else:
        return ('unknown', True)
    unknown_count = len(list(filter(lambda tag: tag == 'unknown', events)))
    if (sat_count + unknown_count) == len(events):
        if sat_count > 0:
            return ('sat', True)
    if (timeout_count + unknown_count) == len(events):
        if timeout_count >= unknown_count:
            return ('timeout', True)
        else:
            return ('unknown', True)

    raise MergeEventFailure('Could not merge {}'.format(events))

class GenericRunnerEventAnalyser:
    def __init__(self, name, soft_timeout= None, use_dsoes_wallclock_time=False):
        self.name = name
        self._soft_timeout = soft_timeout
        assert isinstance(self._soft_timeout, float) or self._soft_timeout is None
        self.use_dsoes_wallclock_time = use_dsoes_wallclock_time
        assert isinstance(self.use_dsoes_wallclock_time, bool)

        if self._soft_timeout:
            _logger.info('Runner {} will check for softimeout'.format(name))
            if self.use_dsoes_wallclock_time:
                _logger.info('Runner {} will use dsoes_wallclock_time'.format(name))
            else:
                _logger.info('Runner {} will NOT use dsoes_wallclock_time'.format(name))
        else:
            _logger.info('Runner {} will NOT check for softtimeout'.format(name))

    @property
    def soft_timeout(self):
        return self._soft_timeout

    def get_solver_end_state_checker_fns(self):
        # Child classes should override this
        return []

    def get_event_tag(self, geti):
        ri = geti.ri
        assert isinstance(ri, dict)
        # if ri['exit_code'] == 0:
        #     if ri['sat'] == 'sat':
        #         if ri['expected_sat'] == 'unsat':
        #             return 'sat_but_expected_unsat'
        #         return 'sat'
        #     if ri['sat'] == 'unsat':
        #         if ri['expected_sat'] == 'sat':
        #             return 'unsat_but_expected_sat'
        #         return 'unsat'

        if ri['sat'] == 'sat':
            if ri['expected_sat'] == 'unsat':
                return 'sat_but_expected_unsat'
            return 'sat'
        if ri['sat'] == 'unsat':
            if ri['expected_sat'] == 'sat':
                return 'unsat_but_expected_sat'
            return 'unsat'
        if ri['sat'] == 'unknown':
            if ri['out_of_memory'] is True:
                return 'out_of_memory'
            elif ri['backend_timeout'] is True:
                return 'timeout'
            else:
                return 'unknown'

        # Go through solver specific functions
        fns = self.get_solver_end_state_checker_fns()
        for fn in fns:
            event_tag = fn(geti)
            if event_tag is not None:
                return event_tag

        # Only if that fails consider checking for a soft timeout
        if self.soft_timeout is not None:
            # FIXME: Use right clock
            ri_time = None
            if self.use_dsoes_wallclock_time:
                ri_time = ri['dsoes_wallclock_time']
            else:
                ri_time = ri['wallclock_time']
            if ri_time >= self.soft_timeout:
                return 'soft_timeout'
        did_timeout = self.did_timeout(geti)
        if did_timeout is not None:
            return did_timeout
        return None

    def did_timeout(self, geti):
        ri = geti.ri
        if ri['backend_timeout'] is True:
            return 'timeout'
        if self.soft_timeout is not None:
            # FIXME: Use right clock
            ri_time = None
            if self.use_dsoes_wallclock_time:
                ri_time = ri['dsoes_wallclock_time']
            else:
                ri_time = ri['wallclock_time']
            if ri_time >= self.soft_timeout:
                return 'soft_timeout'
        return None

    def join_path(self, prefix, suffix):
        if suffix.startswith('/'):
            mod_suffix = suffix[1:]
        else:
            mod_suffix = suffix
        return os.path.join(prefix, mod_suffix)

    def get_stdout_log_path(self, ri, wd_base):
        log_file = self.join_path(wd_base, ri['stdout_log_file'])
        return log_file

    def get_stderr_log_path(self, ri, wd_base):
        log_file = self.join_path(wd_base, ri['stderr_log_file'])
        return log_file

    def _open_log_file(self, log_file_path):
        if not os.path.exists(log_file_path):
            msg= 'File "{}" does not exist'.format(log_file_path)
            _logger.error(msg)
            raise Exception(msg)
        return open(log_file_path, 'r')

    def open_stdout_log(self, ri, wd_base):
        return self._open_log_file(self.get_stdout_log_path(ri, wd_base))

    def open_stderr_log(self, ri, wd_base):
        return self._open_log_file(self.get_stderr_log_path(ri, wd_base))

    def _exit_and_search_stderr_regex(self, geti, regex, match_tag, search=True, exit_code_neq=0):
        assert isinstance(search, bool)
        ri = geti.ri
        wd_base = geti.wd_base
        if ri['exit_code'] == exit_code_neq:
            return None
        with self.open_stderr_log(ri, wd_base) as f:
            for l in f.readlines():
                _logger.debug('Matching against line "{}"'.format(l))
                if search:
                    m = regex.search(l)
                else:
                    m = regex.match(l)
                if m:
                    return match_tag
        return None

    def _exit_and_search_stdout_regex(self, geti, regex, match_tag, search=True, exit_code_neq=0):
        assert isinstance(search, bool)
        ri = geti.ri
        wd_base = geti.wd_base
        if ri['exit_code'] == exit_code_neq:
            return None
        with self.open_stdout_log(ri, wd_base) as f:
            for l in f.readlines():
                _logger.debug('Matching against line "{}"'.format(l))
                if search:
                    m = regex.search(l)
                else:
                    m = regex.match(l)
                if m:
                    return match_tag
        return None

class JFSRunnerEventAnalyser(GenericRunnerEventAnalyser):
    def __init__(self, *nargs, **kwargs):
        # Normally we don't want this on because we want to manually
        # debug what happened. However if we use the DummySolver backend
        # we'll likely get unknown so we should handle this.
        self.handle_unknown = False
        new_kwargs = kwargs.copy()
        if 'jfs.handle_unknown' in kwargs:
            self.handle_unknown = kwargs['jfs.handle_unknown']
            assert isinstance(self.handle_unknown, bool)
            new_kwargs.pop('jfs.handle_unknown')
        super().__init__("JFS", *nargs, **new_kwargs)

    def get_jfs_stats(self, geti):
        wd_base = geti.wd_base
        ri = geti.ri
        stats_path = self.join_path(wd_base, ResultInfoUtil.get_result_info_wd(ri))
        stats_path = self.join_path(stats_path, 'jfs-stats.yml')
        try:
            with open(stats_path, 'r') as f:
                stats = util.loadYaml(f)
                return stats
        except FileNotFoundError:
            _logger.warning('"{}" does not exist'.format(stats_path))
            return None

    def get_fuzzer_stderr_path(self, geti):
        wd_base = geti.wd_base
        ri = geti.ri
        fuzzer_output_path = self.join_path(wd_base, ResultInfoUtil.get_result_info_wd(ri))
        fuzzer_output_path = self.join_path(fuzzer_output_path, 'jfs-wd/libfuzzer.stderr.txt')
        return fuzzer_output_path

    _RE_LIBFUZZER_AVG_EXEC = re.compile(r'stat::average_exec_per_sec:\s*(\d+)')
    def get_libfuzzer_stat_average_exec_per_sec(self, geti):
        fuzzer_stderr_path = self.get_fuzzer_stderr_path(geti)
        if not os.path.exists(fuzzer_stderr_path):
            return None
        # Look for something like
        # stat::average_exec_per_sec:     287127
        try:
            with open(fuzzer_stderr_path, 'r', errors='ignore') as f:
                for line in f.readlines():
                    m = self._RE_LIBFUZZER_AVG_EXEC.search(line)
                    if m:
                        value = m.group(1)
                        return int(value)
        except UnicodeDecodeError as e:
            _logger.error('Failed to read {}'.format(fuzzer_stderr_path))
            raise e
        return None

    def get_fuzzing_throughput_fields(self, geti):
        """
            returns the tuple (<num_inputs>, <num_wrong_sized_inputs>, <fuzzing_wallclock_time>)
        """
        stats_yml = self.get_jfs_stats(geti)
        if stats_yml is None:
            key = ResultInfoUtil.get_result_info_key(geti.ri)
            _logger.debug('Failed to open stats for {}'.format(key))
            return (None, None, None)

        stats = stats_yml['stats']
        assert isinstance(stats, list)
        # Walk list backwards because the fields we want are usually
        # near the end
        fuzzing_wallclock_time = None
        num_inputs = None
        num_wrong_sized_inputs = None
        for stat_entry in reversed(stats):
            assert isinstance(stat_entry, dict)
            if stat_entry['name'] == 'fuzz':
                fuzzing_wallclock_time = stat_entry['wall_time']
                assert isinstance(fuzzing_wallclock_time, float)
                continue
            if stat_entry['name'] == 'runtime_fuzzing_stats':
                num_inputs = stat_entry['jfs_num_inputs']
                num_wrong_sized_inputs = stat_entry['jfs_num_wrong_size_inputs']
                assert isinstance(num_inputs, int)
                assert isinstance(num_wrong_sized_inputs, int)
            if all(map(lambda x: x is not None, [fuzzing_wallclock_time, num_inputs, num_wrong_sized_inputs])):
                break
        assert num_inputs is None or isinstance(num_inputs, int)
        assert num_wrong_sized_inputs is None or isinstance(num_wrong_sized_inputs, int)
        assert fuzzing_wallclock_time is None or isinstance(fuzzing_wallclock_time, float)
        return (num_inputs, num_wrong_sized_inputs, fuzzing_wallclock_time)

    def _error_unimplement_fp_literals(self, geti):
        ri = geti.ri
        wd_base = geti.wd_base
        if ri['exit_code'] == 0:
            if ri['sat'] == 'sat':
                if ri['expected_sat'] == 'unsat':
                    return 'sat_but_expected_unsat'
                return 'sat'
            if ri['sat'] == 'unsat':
                if ri['expected_sat'] == 'sat':
                    return 'unsat_but_expected_sat'
                return 'unsat'
        if ri['exit_code'] == 255 or ri['exit_code'] == 1:
            return "unknown"
        if ri['exit_code'] == 'null':
            return "time_out"
        if ri['exit_code'] == 20 and ri['sat'] == 'unsat':
            return "unsat"

    def get_solver_end_state_checker_fns(self):
        c = [
            self._unsupported_bv_sort,
            self._unsupported_fp_sort,
            self._unsupported_general_sort,
            self._dropped_stdout,
            self._libfuzzer_timeout,
            self._error_unimplement_fp_literals,
        ]
        if self.handle_unknown:
            c.append(self._handle_unknown_no_timeout)
        return c

    def _handle_unknown_no_timeout(self, geti):
        if self.did_timeout(geti):
            return None
        ri = geti.ri
        if ri['exit_code'] != 0:
            return None
        if ri['sat'] != 'unknown':
            return None
        # Verify that JFS actually printed out `unknown`
        with self.open_stdout_log(ri, geti.wd_base) as f:
            first_line = f.readline().strip()
            if first_line == 'unknown':
                return 'jfs_generic_unknown'
        return None

    _RE_JFS_DEBUG_SOLVER_OUTPUT = re.compile(r'Solver responded with (sat|unsat|unknown)\)$')
    _RE_JFS_DEBUG_MODEL_VALIDATION = re.compile(r'\(model validation succeeded\)')
    def _dropped_stdout(self, geti):
        # Untriaged bug where stdout gets dropped by solution was found.
        ri = geti.ri
        wd_base = geti.wd_base
        if ri['exit_code'] != 0:
            return None
        stdout_path = self.get_stdout_log_path(ri, wd_base)
        # Stdout is empty
        if os.path.getsize(stdout_path) != 0:
            return None
        # Stderr output when verbosity is on indicates the solver
        # response.
        # NOTE: This only works with 64f89d6bed53f43e1d3e2b3b21f097164a8bf4c4
        # and newer.
        with self.open_stderr_log(ri, wd_base) as f:
            for l in f.readlines():
                m = self._RE_JFS_DEBUG_SOLVER_OUTPUT.search(l)
                m_model_validation = None
                sat = None
                if m:
                    sat = m.group(1)
                else:
                    # Heuristic for older JFS versions where the satisfiability wasn't
                    # recorded in debug output. This relies on model valiation being on.
                    # If model validation is performed that implies the result was sat.
                    m_model_validation = self._RE_JFS_DEBUG_MODEL_VALIDATION.search(l)
                    if m_model_validation:
                        sat = 'sat'
                if sat is not None:
                    assert sat == 'sat' or sat == 'unsat' or sat == 'unknown'
                    _logger.warning('jfs_dropped_stdout_bug_{}: {} ({})'.format(
                        sat,
                        ri['benchmark'],
                        ri['working_directory']))
                    return 'jfs_dropped_stdout_bug_{}'.format(sat)

        return None

    _RE_LIBFUZZER_TIMEOUT=re.compile(r'\(error Unexpected exit code from LibFuzzer 88\)')
    def _libfuzzer_timeout(self, geti):
        ri = geti.ri
        wd_base = geti.wd_base
        if ri['exit_code'] != 0:
            return None
        if ri['sat'] != 'unknown':
            return None
        # LibFuzzer hit single unit run titme out
        with self.open_stderr_log(ri, wd_base) as f:
            for l in f.readlines():
                m = self._RE_LIBFUZZER_TIMEOUT.match(l)
                if m:
                   return 'jfs_libfuzzer_unit_timeout'
        return None

    def _zero_exit_and_search_regex(self, geti, regex, match_tag, search=True):
        assert isinstance(search, bool)
        ri = geti.ri
        wd_base = geti.wd_base
        if ri['exit_code'] != 0:
            return None
        with self.open_stderr_log(ri, wd_base) as f:
            for l in f.readlines():
                _logger.debug('Matching against line "{}"'.format(l))
                if search:
                    m = regex.search(l)
                else:
                    m = regex.match(l)
                if m:
                    return match_tag
        return None

    _RE_UNSUPPORTED_BV_SORT = re.compile(r'\(BitVector width \d+ not supported\)')
    def _unsupported_bv_sort(self, geti):
        return self._zero_exit_and_search_regex(
            geti,
            self._RE_UNSUPPORTED_BV_SORT,
            'unsupported_bv_sort',
            True
        )

    _RE_UNSUPPORTED_FP_SORT=re.compile(r'\(FloatingPoint sort .+ not supported\)')
    def _unsupported_fp_sort(self, geti):
        # NOTE: This function relies on functionaility in very new JFS versions
        # (c47861db3c3f15488ec65d8184f3cb23132e2f88 onwards) and will fail to match
        # in older versions.
        return self._zero_exit_and_search_regex(
            geti,
            self._RE_UNSUPPORTED_FP_SORT,
            'unsupported_fp_sort',
            True
        )

    _RE_UNSUPPORTED_SORT=re.compile(r'\(unsupported sorts\)')
    def _unsupported_general_sort(self, geti):
        return self._zero_exit_and_search_regex(
            geti,
            self._RE_UNSUPPORTED_SORT,
            'unsupported_sort',
            True
        )

class CoralRunnerEventAnalyser(GenericRunnerEventAnalyser):
    def __init__(self, *nargs, **kwargs):
        super().__init__("Coral", *nargs, **kwargs)

    def _non_zero_exit_and_search_regex(self, geti, regex, match_tag, search=True):
        assert isinstance(search, bool)
        ri = geti.ri
        wd_base = geti.wd_base
        if ri['exit_code'] == 0:
            return None
        with self.open_stderr_log(ri, wd_base) as f:
            for l in f.readlines():
                _logger.debug('Matching against line "{}"'.format(l))
                if search:
                    m = regex.search(l)
                else:
                    m = regex.match(l)
                if m:
                    return match_tag
        return None

    _RE_JAVA_UNEXPECTED_TYPE_SYM_BOOL = re.compile(r'java.lang.RuntimeException: Unexpected type: class symlib.SymBoolLiteral')
    def error_unexpected_sym_bool(self, geti):
        tag = self._non_zero_exit_and_search_regex(geti, self._RE_JAVA_UNEXPECTED_TYPE_SYM_BOOL, 'coral_unexpected_sym_bool', search=False)
        if not tag is None:
            return tag
        return None

    _RE_UNSUPPORTED_OP_ITE = re.compile(r'CoralPrinterUnsupportedOperation: ite')
    def error_unsupported_op_ite(self, geti):
        tag = self._non_zero_exit_and_search_regex(geti, self._RE_UNSUPPORTED_OP_ITE, 'coral_unsupported_op_ite')
        if not tag is None:
            return tag
        return None

    _RE_UNSUPPORTED_OP_FABS = re.compile(r'CoralPrinterUnsupportedOperation: fp.abs')
    def error_unsupported_op_fabs(self, geti):
        tag = self._non_zero_exit_and_search_regex(geti, self._RE_UNSUPPORTED_OP_FABS, 'coral_unsupported_op_fp_abs')
        if not tag is None:
            return tag
        return None

    _RE_UNSUPPORTED_OP_FMA = re.compile(r'CoralPrinterUnsupportedOperation: fp.fma')
    def error_unsupported_op_fma(self, geti):
        tag = self._non_zero_exit_and_search_regex(geti, self._RE_UNSUPPORTED_OP_FMA, 'coral_unsupported_op_fp_fma')
        if not tag is None:
            return tag
        return None

    _RE_UNSUPPORTED_OP_FP_MAX = re.compile(r'CoralPrinterUnsupportedOperation: fp.max')
    def error_unsupported_op_fp_max(self, geti):
        tag = self._non_zero_exit_and_search_regex(geti, self._RE_UNSUPPORTED_OP_FP_MAX, 'coral_unsupported_op_fp_max')
        if not tag is None:
            return tag
        return None

    _RE_UNSUPPORTED_OP_FP_MIN = re.compile(r'CoralPrinterUnsupportedOperation: fp.min')
    def error_unsupported_op_fp_min(self, geti):
        tag = self._non_zero_exit_and_search_regex(geti, self._RE_UNSUPPORTED_OP_FP_MIN, 'coral_unsupported_op_fp_min')
        if not tag is None:
            return tag
        return None

    _RE_UNSUPPORTED_OP_FP_ROUND_TO_INTEGRAL = re.compile(r'CoralPrinterUnsupportedOperation: fp.roundToIntegral')
    def error_unsupported_op_fp_round_to_integral(self, geti):
        tag = self._non_zero_exit_and_search_regex(geti, self._RE_UNSUPPORTED_OP_FP_ROUND_TO_INTEGRAL, 'coral_unsupported_op_fp_round_to_integral')
        if not tag is None:
            return tag
        return None

    _RE_UNSUPPORTED_ROUNDING_MODE = re.compile(r'CoralPrinterUnsupportedRoundingMode:')
    def error_unsupported_rounding_mode(self, geti):
        tag = self._non_zero_exit_and_search_regex(geti, self._RE_UNSUPPORTED_ROUNDING_MODE, 'coral_unsupported_rounding_mode')
        if not tag is None:
            return tag
        return None

    _RE_UNSUPPORTED_OP_CONV = re.compile(r'CoralPrinterUnsupportedOperation: Converting \w+(\([0-9 ,]+\))? to \w+(\([0-9 ,]+\))?')
    def error_unsupported_op_sort_conversion(self, geti):
        ri = geti.ri
        wd_base = geti.wd_base
        if ri['exit_code'] == 0:
            return None
        with self.open_stderr_log(ri, wd_base) as f:
            for l in f.readlines():
                _logger.debug('Matching against line "{}"'.format(l))
                m = self._RE_UNSUPPORTED_OP_CONV.search(l)
                if m:
                    return 'coral_unsupported_op_sort_conversion'
        return None

    _RE_NO_IMPL_BV_EQ = re.compile(r'NotImplementedError: BitVector equal')
    def error_unsupported_bv_eq(self, geti):
        tag = self._non_zero_exit_and_search_regex(geti, self._RE_NO_IMPL_BV_EQ, 'coral_unsupported_bv_eq')
        if not tag is None:
            return tag
        return None

    _RE_JAVA_NULL_PTR = re.compile(r'java.lang.NullPointerException')
    def error_nullptr_exception(self, geti):
        ri = geti.ri
        wd_base = geti.wd_base
        if ri['exit_code'] == 0:
            return None
        with self.open_stderr_log(ri, wd_base) as f:
            for l in f.readlines():
                _logger.debug('Matching against line "{}"'.format(l))
                m = self._RE_JAVA_NULL_PTR.search(l)
                if m:
                    return 'coral_nullptr_exception'
        return None

    _RE_PYTHON_OS_ERROR_ARG_LIST_TOO_LONG = re.compile(r'OSError: \[Errno 7\] Argument list too long')
    def error_argument_list_too_long(self, geti):
        ri = geti.ri
        wd_base = geti.wd_base
        if ri['exit_code'] == 0:
            return None
        with self.open_stderr_log(ri, wd_base) as f:
            for l in f.readlines():
                _logger.debug('Matching against line "{}"'.format(l))
                m = self._RE_PYTHON_OS_ERROR_ARG_LIST_TOO_LONG.search(l)
                if m:
                    return 'coral_argument_list_too_long'
        return None

    _RE_DISTINCT_NOT_IMP = re.compile(r'NotImplementedError: Handler for 259 is missing from dispatch dictionary')
    def error_distinct_support_not_implemented(self, geti):
        return self._exit_and_search_stderr_regex(
            geti,
            self._RE_DISTINCT_NOT_IMP,
            'coral_distinct_not_implemented',
            search=True,
            exit_code_neq=0
        )

    def get_solver_end_state_checker_fns(self):
        return [
            self.error_unsupported_op_sort_conversion,
            self.error_nullptr_exception,
            self.error_argument_list_too_long,
            self.error_unsupported_op_ite,
            self.error_unsupported_op_fabs,
            self.error_unsupported_rounding_mode,
            self.error_unsupported_op_fma,
            self.error_unsupported_op_fp_max,
            self.error_unsupported_op_fp_min,
            self.error_unsupported_op_fp_round_to_integral,
            self.error_unexpected_sym_bool,
            self.error_unsupported_bv_eq,
            self.error_distinct_support_not_implemented,
        ]


class goSATRunnerEventAnalyser(GenericRunnerEventAnalyser):
    def __init__(self, *nargs, **kwargs):
        super().__init__("goSAT", *nargs, **kwargs)

    def error_generic_crash(self, geti):
        ri = geti.ri
        wd_base = geti.wd_base
        # FIXME: The exit code is different depending on the backend
        if ri['exit_code'] != 255 and geti.backend != 'Docker':
            return None
        if os.path.getsize(self.get_stdout_log_path(ri, wd_base)) == 0:
            if os.path.getsize(self.get_stderr_log_path(ri, wd_base)) == 0:
                return 'gosat_generic_crash'
        return None

    _RE_ASSERT_FAIL = re.compile(r'Assertion.+failed')

    def error_assert_failed(self, geti):
        ri = geti.ri
        wd_base = geti.wd_base
        if ri['exit_code'] == 0:
            return None
        with self.open_stderr_log(ri, wd_base) as f:
            for l in f.readlines():
                _logger.debug('Matching against line "{}"'.format(l))
                m = self._RE_ASSERT_FAIL.search(l)
                if m:
                    return 'gosat_assert_fail'
        return None

    _RE_UNCAUGHT_EXCEPTION = re.compile(r"terminate called after throwing an instance of")

    def error_uncaught_exception(self, geti):
        ri = geti.ri
        wd_base = geti.wd_base
        if ri['exit_code'] == 0:
            return None
        with self.open_stderr_log(ri, wd_base) as f:
            for l in f.readlines():
                _logger.debug('Matching against line "{}"'.format(l))
                m = self._RE_UNCAUGHT_EXCEPTION.search(l)
                if m:
                    return 'gosat_uncaught_exception'
        return None

    def result_unknown(self, geti):
        ri = geti.ri
        wd_base = geti.wd_base
        if ri['exit_code'] != 0:
            return None
        # Check stderr is empty
        stderr_path = self.get_stderr_log_path(ri, wd_base)
        if os.path.getsize(stderr_path) != 0:
            return None
        if ri['sat'] == 'unknown':
            return 'gosat_unknown'

    _RE_UNSUPPORTED_EXPR = re.compile(r'^Unsupported expression')
    def error_unsupported_expression(self, geti):
        ri = geti.ri
        wd_base = geti.wd_base
        if ri['exit_code'] == 0:
            return None
        with self.open_stderr_log(ri, wd_base) as f:
            for l in f.readlines():
                _logger.debug('Matching against line "{}"'.format(l))
                m = self._RE_UNSUPPORTED_EXPR.match(l)
                if m:
                    return 'gosat_unsupported_expr'
        return None

    def _error_unimplement_fp_literals(self, geti):
        ri = geti.ri
        wd_base = geti.wd_base
        if ri['exit_code'] == 0:
            if ri['sat'] == 'sat':
                if ri['expected_sat'] == 'unsat':
                    return 'sat_but_expected_unsat'
                return 'sat'
            if ri['sat'] == 'unsat':
                if ri['expected_sat'] == 'sat':
                    return 'unsat_but_expected_sat'
                return 'unsat'
        if ri['exit_code'] == 3:
            return "unknown"
        if ri['exit_code'] == 'null':
            return "time_out"
        if ri['exit_code'] == 20 and ri['sat'] == 'unsat':
            return "unsat"

    def get_solver_end_state_checker_fns(self):
        # Child classes should override this
        return [
            self.error_generic_crash,
            self.error_assert_failed,
            self.error_uncaught_exception,
            self.result_unknown,
            self.error_unsupported_expression,
            self._error_unimplement_fp_literals,
        ]

class optSATRunnerEventAnalyser(GenericRunnerEventAnalyser):
    def __init__(self, *nargs, **kwargs):
        super().__init__("optSAT", *nargs, **kwargs)

    def error_generic_crash(self, geti):
        ri = geti.ri
        wd_base = geti.wd_base
        # FIXME: The exit code is different depending on the backend
        if ri['exit_code'] != 255 and geti.backend != 'Docker':
            return None
        if os.path.getsize(self.get_stdout_log_path(ri, wd_base)) == 0:
            if os.path.getsize(self.get_stderr_log_path(ri, wd_base)) == 0:
                return 'optsat_generic_crash'
        return None

    _RE_ASSERT_FAIL = re.compile(r'Assertion.+failed')

    def error_assert_failed(self, geti):
        ri = geti.ri
        wd_base = geti.wd_base
        if ri['exit_code'] == 0:
            return None
        with self.open_stderr_log(ri, wd_base) as f:
            for l in f.readlines():
                _logger.debug('Matching against line "{}"'.format(l))
                m = self._RE_ASSERT_FAIL.search(l)
                if m:
                    return 'optsat_assert_fail'
        return None

    _RE_UNCAUGHT_EXCEPTION = re.compile(r"terminate called after throwing an instance of")

    def error_uncaught_exception(self, geti):
        ri = geti.ri
        wd_base = geti.wd_base
        if ri['exit_code'] == 0:
            return None
        with self.open_stderr_log(ri, wd_base) as f:
            for l in f.readlines():
                _logger.debug('Matching against line "{}"'.format(l))
                m = self._RE_UNCAUGHT_EXCEPTION.search(l)
                if m:
                    return 'optsat_uncaught_exception'
        return None

    def result_unknown(self, geti):
        ri = geti.ri
        wd_base = geti.wd_base
        if ri['exit_code'] != 0:
            return None
        # Check stderr is empty
        stderr_path = self.get_stderr_log_path(ri, wd_base)
        if os.path.getsize(stderr_path) != 0:
            return None
        if ri['sat'] == 'unknown':
            return 'optsat_unknown'

    _RE_UNSUPPORTED_EXPR = re.compile(r'^(Unsupported expression|unsupported:)')
    def error_unsupported_expression(self, geti):
        ri = geti.ri
        wd_base = geti.wd_base
        if ri['exit_code'] == 0:
            return None
        if ri['exit_code'] == 1:
            return 'optsat_unknown_error'
        with self.open_stderr_log(ri, wd_base) as f:
            for l in f.readlines():
                _logger.debug('Matching against line "{}"'.format(l))
                m = self._RE_UNSUPPORTED_EXPR.match(l)
                if m:
                    return 'optsat_unsupported_expr'
        return None


    def get_solver_end_state_checker_fns(self):
        # Child classes should override this
        return [
            self.error_generic_crash,
            self.error_assert_failed,
            self.error_uncaught_exception,
            self.result_unknown,
            self.error_unsupported_expression,
        ]

class optSATBitwuzlaRunnerEventAnalyser(GenericRunnerEventAnalyser):
    def __init__(self, *nargs, **kwargs):
        super().__init__("optSATBitwuzla", *nargs, **kwargs)

    def error_generic_crash(self, geti):
        ri = geti.ri
        wd_base = geti.wd_base
        # FIXME: The exit code is different depending on the backend
        if ri['exit_code'] != 255 and geti.backend != 'Docker':
            return None
        if os.path.getsize(self.get_stdout_log_path(ri, wd_base)) == 0:
            if os.path.getsize(self.get_stderr_log_path(ri, wd_base)) == 0:
                return 'optsat_generic_crash'
        return None

    _RE_ASSERT_FAIL = re.compile(r'Assertion.+failed')

    def error_assert_failed(self, geti):
        ri = geti.ri
        wd_base = geti.wd_base
        if ri['exit_code'] == 0:
            return None
        with self.open_stderr_log(ri, wd_base) as f:
            for l in f.readlines():
                _logger.debug('Matching against line "{}"'.format(l))
                m = self._RE_ASSERT_FAIL.search(l)
                if m:
                    return 'optsat_assert_fail'
        return None

    _RE_UNCAUGHT_EXCEPTION = re.compile(r"terminate called after throwing an instance of")

    def error_uncaught_exception(self, geti):
        ri = geti.ri
        wd_base = geti.wd_base
        if ri['exit_code'] == 0:
            return None
        with self.open_stderr_log(ri, wd_base) as f:
            for l in f.readlines():
                _logger.debug('Matching against line "{}"'.format(l))
                m = self._RE_UNCAUGHT_EXCEPTION.search(l)
                if m:
                    return 'optsat_uncaught_exception'
        return None

    def result_unknown(self, geti):
        ri = geti.ri
        wd_base = geti.wd_base
        if ri['exit_code'] != 0:
            return None
        # Check stderr is empty
        stderr_path = self.get_stderr_log_path(ri, wd_base)
        if os.path.getsize(stderr_path) != 0:
            return None
        if ri['sat'] == 'unknown':
            return 'optsat_unknown'

    _RE_UNSUPPORTED_EXPR = re.compile(r'^(Unsupported expression|unsupported:)')
    def error_unsupported_expression(self, geti):
        ri = geti.ri
        wd_base = geti.wd_base
        if ri['exit_code'] == 0:
            return None
        with self.open_stderr_log(ri, wd_base) as f:
            for l in f.readlines():
                _logger.debug('Matching against line "{}"'.format(l))
                m = self._RE_UNSUPPORTED_EXPR.match(l)
                if m:
                    return 'optsat_unsupported_expr'
        return None

    _RE_UNIMP_FP_LIT = re.compile(r'Floating-point literals not yet implemented')

    def _error_unimplement_fp_literals(self, geti):
        ri = geti.ri
        wd_base = geti.wd_base
        if ri['exit_code'] == 10:
            if ri['sat'] == 'sat':
                if ri['expected_sat'] == 'unsat':
                    return 'sat_but_expected_unsat'
                return 'sat'
            if ri['sat'] == 'unsat':
                if ri['expected_sat'] == 'sat':
                    return 'unsat_but_expected_sat'
                return 'unsat'
        if ri['exit_code'] == 1:
            return "unknown"
        if ri['exit_code'] == 'null':
            return "time_out"
        if ri['exit_code'] == 20 and ri['sat'] == 'unsat':
            return "unsat"

    def get_solver_end_state_checker_fns(self):
        # Child classes should override this
        return [
            self.error_generic_crash,
            self.error_assert_failed,
            self.error_uncaught_exception,
            self.result_unknown,
            self.error_unsupported_expression,
            self._error_unimplement_fp_literals,
        ]

class ColibriRunnerEventAnalyser(GenericRunnerEventAnalyser):
    def __init__(self, *nargs, **kwargs):
        super().__init__("Colibri", *nargs, **kwargs)

    def error_generic_unknown(self, geti):
        ri = geti.ri
        wd_base = geti.wd_base
        # Colibri has been observed emitting both exit codes
        if ri['sat'] != 'unknown' or (ri['exit_code'] != 2 and ri['exit_code'] != 3):
            return None
        # don't differ unknown type or cause reason
        # # Check stderr is empty
        # stderr_path = self.get_stderr_log_path(ri, wd_base)
        # if os.path.getsize(stderr_path) != 0:
        #     return None
        # I don't know what colibri is doing here
        return 'colibri_generic_unknown'

    # Fatal error: exception Stack overflow
    _RE_STACK_OVERFLOW = re.compile(r'^Fatal\s+error:\s+exception\s+Stack\s+overflow')
    def error_stack_overflow(self, geti):
        ri = geti.ri
        wd_base = geti.wd_base
        # Both exit codes have been observed with stackoverflow message
        if ri['sat'] != 'unknown' or (ri['exit_code'] != 2 and ri['exit_code'] != 3):
            return None
        # Check stderr
        with self.open_stderr_log(ri, wd_base) as f:
            first_line = f.readline()
            if self._RE_STACK_OVERFLOW.match(first_line):
                return 'colibri_stack_overflow'
        return None

    def error_parsing_unknown_char(self, geti):
        ri = geti.ri
        wd_base = geti.wd_base
        if ri['sat'] != 'unknown' or ri['exit_code'] != 2:
            return None
        # Check stderr
        with self.open_stderr_log(ri, wd_base) as f:
            # Check 2nd line
            first_line = f.readline()
            second_line = f.readline()
            if second_line.startswith('unknown character'):
                return 'colibri_parser_error_unknown_character'
        return None

    def error_seg_fault(self, geti):
        # 11 Segmentation fault
        ri = geti.ri
        wd_base = geti.wd_base
        # Both exit codes of 2 and 3 have been observed
        if ri['sat'] != 'unknown' or (ri['exit_code'] != 3 and ri['exit_code'] != 2):
            return None
        # Check stderr
        with self.open_stderr_log(ri, wd_base) as f:
            # Check 2nd line
            first_line = f.readline()
            if re.search(r'Segmentation fault', first_line):
                return 'colibri_segfault'
        return None

    def _error_colibri_unknown(self, geti):
        ri = geti.ri
        if ri['exit_code'] == 1:
            return 'colibri_unknown_error'
        return None

    def get_solver_end_state_checker_fns(self):
        # Child classes should override this
        return [
            self.error_parsing_unknown_char,
            self.error_stack_overflow,
            self.error_generic_unknown,
            self.error_seg_fault,
            self._error_colibri_unknown,
        ]

class Z3RunnerEventAnalyser(GenericRunnerEventAnalyser):
    def __init__(self, *nargs, **kwargs):
        super().__init__("Z3", *nargs, **kwargs)

    def old_z3_benchmark_name_bug(self, geti):
        ri = geti.ri
        wd_base = geti.wd_base
        # This was a bug where we forgot to tell Z3 to handle
        # strangely named files. This was fixed in
        # 4472534179087c3e854e0acd701b3f6f4bc846f4
        if ri['exit_code'] != 110:
            return None
        # Check the stderr file for the pattern we expect
        with self.open_stderr_log(ri, wd_base) as f:
            line = f.readline()
            if (line.startswith('ERROR: unknown parameter') or
                line.startswith('ERROR: invalid parameter')):
                return 'old_z3_benchmark_name_bug'
        return None

    def get_solver_end_state_checker_fns(self):
        # Child classes should override this
        return [
            self.old_z3_benchmark_name_bug,
        ]

class MathSat5RunnerEventAnalyser(GenericRunnerEventAnalyser):
    def __init__(self, *nargs, **kwargs):
        super().__init__("MathSat5", *nargs, **kwargs)

    def error_expected_sat_got_unsat(self, geti):
        """
            (error "expected status was sat, got unsat instead")
        """
        ri = geti.ri
        wd_base = geti.wd_base
        if ri['exit_code'] != 0 or ri['sat'] != 'unknown':
            return None
        with self.open_stdout_log(ri, wd_base) as f:
            line = f.readline()
            _logger.debug('Opened "{}" with line "{}"'.format(f.name, line))
            if line.startswith('(error "expected status was sat, got unsat instead")'):
                return 'mathsat5_error_expected_sat_got_unsat'
        return None

    def error_empty_name_for_symbol(self, geti):
        """
          (error "Empty name for symbol")
        """
        ri = geti.ri
        wd_base = geti.wd_base
        if ri['exit_code'] != 0 or ri['sat'] != 'unknown':
            return None
        with self.open_stdout_log(ri, wd_base) as f:
            line = f.readline()
            if line.startswith('(error "Empty name for symbol")'):
                return 'mathsat5_error_empty_symbol_name'
        return None

    def error_fp_rem_unsupported(self, geti):
        """
            This seems like a bug in MathSat5
        """
        ri = geti.ri
        wd_base = geti.wd_base
        if ri['exit_code'] != 0 or ri['sat'] != 'unknown':
            return None
        with self.open_stdout_log(ri, wd_base) as f:
            line = f.readline()
            if line.startswith('(error "unknown symbol: fp.rem'):
                return 'mathsat5_error_fp_rem_not_supported'
        return None

    def error_fp_lt_chainable_unsupported(self, geti):
        """
            This seems like a bug in MathSat5
            (error "ERROR: fp.lt takes exactly 2 arguments (3 given) (line: 15)")
        """
        ri = geti.ri
        wd_base = geti.wd_base
        if ri['exit_code'] != 0 or ri['sat'] != 'unknown':
            return None
        with self.open_stdout_log(ri, wd_base) as f:
            line = f.readline()
            if line.startswith('(error "ERROR: fp.lt takes exactly 2 arguments'):
                return 'mathsat5_error_fp_lt_chainable_not_supported'
        return None

    def error_fp_fma_unsupported(self, geti):
        """
            This seems like a bug in MathSat5
        """
        ri = geti.ri
        wd_base = geti.wd_base
        if ri['exit_code'] != 0 or ri['sat'] != 'unknown':
            return None
        with self.open_stdout_log(ri, wd_base) as f:
            line = f.readline()
            if line.startswith('(error "unknown symbol: fp.fma'):
                return 'mathsat5_error_fp_fma_not_supported'
        return None

    def mathsat5_error_unknown(self, geti):
        ri = geti.ri
        if ri['exit_code'] == 1:
            return 'mathsat5_unknown_error'
        return None

    def get_solver_end_state_checker_fns(self):
        # Child classes should override this
        return [
            self.error_expected_sat_got_unsat,
            self.error_empty_name_for_symbol,
            self.error_fp_rem_unsupported,
            self.error_fp_fma_unsupported,
            self.error_fp_lt_chainable_unsupported,
            self.mathsat5_error_unknown,
        ]

class XSatRunnerEventAnalyser(GenericRunnerEventAnalyser):
    def __init__(self, *nargs, **kwargs):
        super().__init__("XSat", *nargs, **kwargs)

    _RE_NOT_IMPLEMENTED_PY = re.compile(r"raise NotImplementedError")
    def error_not_implemented(self, geti):
        ri = geti.ri
        wd_base = geti.wd_base
        if ri['exit_code'] != 1:
            return None
        with self.open_stderr_log(ri, wd_base) as f:
            for l in f.readlines():
                m = self._RE_NOT_IMPLEMENTED_PY.search(l)
                if m:
                    return 'xsat_not_implemented_exception'
        return None

    _RE_UNICODE_ERROR_PY = re.compile(r"UnicodeDecodeError")
    def error_unicode_exception(self, geti):
        ri = geti.ri
        wd_base = geti.wd_base
        if ri['exit_code'] != 1:
            return None
        with self.open_stderr_log(ri, wd_base) as f:
            for l in f.readlines():
                m = self._RE_UNICODE_ERROR_PY.search(l)
                if m:
                    return 'xsat_unicode_exception'
        return None

    _RE_TYPE_ERROR_PY = re.compile(r'^TypeError:\s+')
    def error_type_error(self, geti):
        ri = geti.ri
        wd_base = geti.wd_base
        if ri['exit_code'] != 1:
            return None
        with self.open_stderr_log(ri, wd_base) as f:
            for l in f.readlines():
                m = self._RE_TYPE_ERROR_PY.match(l)
                if m:
                    return 'xsat_type_error'
        return None


    _RE_COMPILER_ERROR_MSG=re.compile(r'^build/foo.c:\d+:\d+:\s+error:')
    def error_compiler_error(self, geti):
        ri = geti.ri
        wd_base = geti.wd_base
        if ri['exit_code'] != 1:
            return None
        with self.open_stderr_log(ri, wd_base) as f:
            for l in f.readlines():
                m = self._RE_COMPILER_ERROR_MSG.match(l)
                if m:
                    return 'xsat_compiler_error'

    def get_solver_end_state_checker_fns(self):
        # Child classes should override this
        return [
            self.error_not_implemented,
            self.error_unicode_exception,
            self.error_compiler_error,
            self.error_type_error,
        ]


class CVC5RunnerEventAnalyser(GenericRunnerEventAnalyser):
    def __init__(self, *nargs, **kwargs):
        super().__init__("CVC5", *nargs, **kwargs)

    _RE_UNIMP_FP_LIT = re.compile(r'Floating-point literals not yet implemented')
    def _error_unimplement_fp_literals(self, geti):
        ri = geti.ri
        wd_base = geti.wd_base
        if ri['exit_code'] != 1:
            return None
        with self.open_stdout_log(ri, wd_base) as f:
            for l in f.readlines():
                m = self._RE_UNIMP_FP_LIT.search(l)
                if m:
                    return 'cvc5_not_implemented_fp_literal'

    _RE_FREE_SORT_SYM_NOT_ALLOWED = re.compile(r'Free sort symbols not allowed in QF_FP')

    def _error_free_sort_sym_not_allowed(self, geti):
        return self._exit_and_search_stdout_regex(
            geti,
            self._RE_FREE_SORT_SYM_NOT_ALLOWED,
            'cvc5_free_sort_sym_not_allowed_in_qf_fp',
            search=True,
            exit_code_neq=0
        )

    _RE_BACKSLASH_IN_QUOTED_SYM_NOT_ALLOWED = re.compile(r'backslash not permitted in \|quoted\| symbol')
    def _error_backlash_in_quoted_sym_not_allowed(self, geti):
        return self._exit_and_search_stdout_regex(
            geti,
            self._RE_BACKSLASH_IN_QUOTED_SYM_NOT_ALLOWED,
            'cvc5_backlash_in_quoted_symbol_not_allowed',
            search=True,
            exit_code_neq=0
        )

    _RE_CVC5_SEGFAULT_HANDLER = re.compile(r'CVC5 suffered a segfault')
    def _error_cvc5_segfault(self, geti):
        return self._exit_and_search_stderr_regex(
            geti,
            self._RE_CVC5_SEGFAULT_HANDLER,
            'cvc5_segfault',
            search=True,
            exit_code_neq=0
        )

    _RE_CVC5_SEGFAULT_HANDLER = re.compile(r'mountpoint for rdma not found')

    def _error_cvc5_unknown(self, geti):
        ri = geti.ri
        if ri['exit_code'] == 1:
            return 'cvc5_unknown_error'
        return None

    def get_solver_end_state_checker_fns(self):
        # Child classes should override this
        return [
            self._error_unimplement_fp_literals,
            self._error_free_sort_sym_not_allowed,
            self._error_backlash_in_quoted_sym_not_allowed,
            self._error_cvc5_segfault,
            self._error_cvc5_unknown,
        ]


class BitwuzlaRunnerEventAnalyser(GenericRunnerEventAnalyser):
    def __init__(self, *nargs, **kwargs):
        super().__init__("Bitwuzla", *nargs, **kwargs)

    _RE_UNIMP_FP_LIT = re.compile(r'Floating-point literals not yet implemented')
    def _error_unimplement_fp_literals(self, geti):
        ri = geti.ri
        wd_base = geti.wd_base
        if ri['exit_code'] == 10:
            if ri['sat'] == 'sat':
                # if ri['expected_sat'] == 'unsat':
                #     return 'sat_but_expected_unsat'
                return 'sat'
            if ri['sat'] == 'unsat':
                # if ri['expected_sat'] == 'sat':
                #     return 'unsat_but_expected_sat'
                return 'unsat'
        if ri['exit_code'] == 1:
            return "unknown"
        if ri['exit_code'] == 'null':
            return "time_out"
        if ri['exit_code'] == 20 and ri['sat'] == 'unsat':
            return "unsat"

    def get_solver_end_state_checker_fns(self):
        # Child classes should override this
        return [
            self._error_unimplement_fp_literals,
        ]


class OL1V3RRunnerEventAnalyser(GenericRunnerEventAnalyser):
    def __init__(self, *nargs, **kwargs):
        super().__init__("OL1V3R", *nargs, **kwargs)

    _RE_UNIMP_FP_LIT = re.compile(r'Floating-point literals not yet implemented')
    def _error_unimplement_fp_literals(self, geti):
        ri = geti.ri
        wd_base = geti.wd_base
        if ri['exit_code'] == 0:
            if ri['sat'] == 'sat':
                if ri['expected_sat'] == 'unsat':
                    return 'sat_but_expected_unsat'
                return 'sat'
            if ri['sat'] == 'unsat':
                if ri['expected_sat'] == 'sat':
                    return 'unsat_but_expected_sat'
                return 'unsat'
        if ri['exit_code'] == 1:
            return "unknown"
        if ri['exit_code'] == 'null':
            return "time_out"
        if ri['exit_code'] == 20 and ri['sat'] == 'unsat':
            return "unsat"

    def get_solver_end_state_checker_fns(self):
        # Child classes should override this
        return [
            self._error_unimplement_fp_literals,
        ]