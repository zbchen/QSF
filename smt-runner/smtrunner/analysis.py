# vim: set sw=4 ts=4 softtabstop=4 expandtab:
import copy
import logging
import math
import pprint
import statistics

_logger = logging.getLogger(__name__)

def is_merged_result_info(r):
    return isinstance(r['sat'], list)

def get_expected_sat_from_result_info(r):
    return _get_sat_from_result_info(r, 'expected_sat')

def get_sat_from_result_info(r):
    return _get_sat_from_result_info(r, 'sat')

def _get_sat_from_result_info(r, key):
    foundConflict = False
    v = r[key]
    benchmark_name = r['benchmark']
    if isinstance(v, str):
        # Single result
        return (v, foundConflict)
    # Must be a merged result
    assert is_merged_result_info(r)
    assert isinstance(v, list)
    # If at least one result reports sat/unsat and there are no conflicts use that
    # result. Otherwise report unknown
    satisfiability = None
    for sat_result in v:
        if sat_result == 'sat':
            if satisfiability is not None and satisfiability == 'unsat':
                # Conflict
                _logger.warning('Found conflict for {}'.format(benchmark_name))
                satisfiability = None
                foundConflict = True
                break
            else:
                satisfiability = sat_result
        elif sat_result == 'unsat':
            if satisfiability is not None and satisfiability == 'sat':
                # Conflict
                _logger.warning('Found conflict for {}'.format(benchmark_name))
                satisfiability = None
                foundConflict = True
                break
            else:
                satisfiability = sat_result
        else:
            assert sat_result == 'unknown'
            # Don't do anything here
    if satisfiability is None:
        return ('unknown', foundConflict)
    return (satisfiability, foundConflict)

def get_arithmetic_mean_and_confidence_intervals(values, confidence_interval_factor):
    assert isinstance(values, list)
    assert confidence_interval_factor > 0
    n = len(values)
    assert n > 1
    mean = statistics.mean(values)
    variance_of_sample = statistics.variance(values)
    standard_error_in_mean_squared = variance_of_sample / n
    standard_error_in_mean = math.sqrt(standard_error_in_mean_squared)
    lower_bound = mean - (standard_error_in_mean * confidence_interval_factor)
    upper_bound = mean + (standard_error_in_mean * confidence_interval_factor)
    return (lower_bound, mean , upper_bound)   # comp time info   add by yx

def get_arithmetic_mean_and_95_confidence_intervals(values):
    # 95 % confidence
    return get_arithmetic_mean_and_confidence_intervals(values, 1.96)

def get_arithmetic_mean_and_99_confidence_intervals(values):
    # 99.9 % confidence
    return get_arithmetic_mean_and_confidence_intervals(values, 3.27)

def is_valid_bound(bounds):
    lower, mid, upper = bounds
    if lower > mid:
        return False
    if mid > upper:
        return False
    return True

def bound_contains_value(bounds, value):
    assert is_valid_bound(bounds)
    lower, _, upper = bounds
    if value >= lower and value <= upper:
        return True
    return False

def bound_contains_or_exceeds_value(bounds, value):
    assert is_valid_bound(bounds)
    if bound_contains_value(bounds, value):
        return True
    lower, _, upper = bounds
    if lower >= value or upper >= value:
        return True
    return False

def bounds_overlap(first_bound, second_bound):
    assert is_valid_bound(first_bound)
    assert is_valid_bound(second_bound)
    f_l, _, f_u = first_bound
    s_l, _, s_u = second_bound
    _logger.debug('Checking with fb:{} sb:{}'.format(first_bound, second_bound))
    if bound_contains_value(second_bound, f_l) or bound_contains_value(second_bound, f_u):
        # First bound overlaps second
        _logger.debug('Do overlap')
        return True
    # Redundant?
    if bound_contains_value(first_bound, s_l) or bound_contains_value(first_bound, s_u):
        _logger.debug('Do overlap')
        return True
    _logger.debug('Do not overlap')
    return False

def get_index_to_execution_time_bounds(index_to_result_info, indices_to_use, max_time, bound_fn, time_prefs=['usr_sys_sum', 'dsoes_wallclock', 'wallclock']):
    # FIXME: This is a hack just so we can make progress.
    # We should instead ensure that the bounds we use are for
    # all the same measurement. We also need to ignore handling indicies
    # that we aren't using
    assert isinstance(index_to_result_info, list)
    index_to_execution_time_bounds = []
    for index, ri in enumerate(index_to_result_info):
        assert isinstance(ri, dict)
        if index not in indices_to_use:
            _logger.warning('Giving index {}, dummy values')
            index_to_execution_time_bounds.append((-1.0, -1.0, -1.0))
            continue
        _logger.info('Getting execution time for index {}'.format(index))
        index_to_execution_time_bounds.append(
                get_exec_time_with_bounds(
                    ri,
                    max_time,
                    bound_fn,
                    time_prefs)
        )
    return index_to_execution_time_bounds

def compute_user_sys_cpu_times(r, bound_fn):
    # Try doing user+sys time
    computed_bounds = None
    sys_cpu_time = r['sys_cpu_time']
    user_cpu_time = r['user_cpu_time']
    sys_any_none = any(map(lambda e: e is None, sys_cpu_time))
    user_any_none = any(map(lambda e: e is None, user_cpu_time))
    if (not user_any_none) and (not sys_any_none):
        summed_times = list(map(lambda vs: vs[0]+vs[1], zip(user_cpu_time, sys_cpu_time)))
        computed_bounds = bound_fn(summed_times)
        _logger.debug('Computed bounds using user+sys: {}'.format(computed_bounds))
    return computed_bounds

def compute_dsoes_wallclock_time(r, bound_fn):
    computed_bounds = None
    # Try dsoes_wallclock_time
    dsoes_wallclock_time = r['dsoes_wallclock_time']
    any_none = any(map(lambda e: e is None, dsoes_wallclock_time))
    if not any_none:
        # Have all values
        computed_bounds = bound_fn(dsoes_wallclock_time)
        _logger.debug('Computed bounds using dsoes_wallclock_time: {}'.format(computed_bounds))
    return computed_bounds

def compute_wallclock_time(r, bound_fn):
    computed_bounds = None
    if computed_bounds is None:
        wallclock_time = r['wallclock_time']
        computed_bounds = bound_fn(wallclock_time)
        _logger.warning('Computed bounds using wallclock_time: {}'.format(computed_bounds))
    return computed_bounds

def get_exec_time_with_bounds(r, max_time, bound_fn, time_prefs=['usr_sys_sum', 'dsoes_wallclock', 'wallclock']):
    r_copy = r
    if not is_merged_result_info(r):
        # HACK: If this not a merged result pretend that it is
        # by turning the timing fields into lists with duplicate
        # times.
        r_copy = r.copy()
        fields_to_listify = ['wallclock_time', 'dsoes_wallclock_time', 'user_cpu_time', 'sys_cpu_time', 'sat']
        for field in fields_to_listify:
            if field not in r_copy:
                continue
            field_value = r_copy[field]
            assert not isinstance(field_value, list)
            r_copy[field] = [ field_value, field_value ] # Two values is enough
    assert is_merged_result_info(r_copy)
    computed_bounds = None

    assert len(time_prefs) > 0
    assert all([isinstance(p, str) for p in time_prefs])
    for clock_type in time_prefs:
        if clock_type == 'usr_sys_sum':
            computed_bounds = compute_user_sys_cpu_times(r_copy, bound_fn)
        elif clock_type == 'dsoes_wallclock':
            computed_bounds = compute_dsoes_wallclock_time(r_copy, bound_fn)
        elif clock_type == 'wallclock':
            computed_bounds = compute_wallclock_time(r_copy, bound_fn)
        else:
            raise Exception('Unsupported clock type: {}'.format(clock_type))
        if computed_bounds is not None:
            break

    if computed_bounds is None:
        msg = 'Failed to compute bounds with:\n{}'.format(pprint.pformat(r_copy))
        _logger.error(msg)
        raise Exception(msg)

    # Bound by max time if specified
    # FIXME: This is broken. In the case that a merged is a mix of timeouts
    # and a useful result we will change it to max-time as if it failed.
    if max_time is not None:
        _logger.info('Using max_time to bound: {}'.format(max_time))
        assert isinstance(max_time, float)
        assert max_time > 0.0
        if bound_contains_or_exceeds_value(computed_bounds, max_time):
            _logger.info('Computed bounds {} contain max time {}'.format(
                computed_bounds,
                max_time))
            computed_bounds = (max_time, max_time, max_time)

    _logger.info('Returning computed_bounds {}'.format(computed_bounds))
    return computed_bounds

def bound_overlaps_with_group(group, bound):
    assert is_valid_bound(bound)
    for bound_in_group in group:
        assert is_valid_bound(bound_in_group)
        if bounds_overlap(bound, bound_in_group):
            return True
    return False

def _bound_group_indices_to_bound_group(index_to_execution_time_bounds, indices_group):
    assert isinstance(indices_group, list)
    bound_group = list(map(
        lambda i: index_to_execution_time_bounds[i], indices_group))
    return bound_group

def rank_by_execution_time(index_to_result_info, indices_to_use, max_time, bound_fn, time_prefs):
    assert isinstance(indices_to_use, list)
    assert len(indices_to_use) <= len(index_to_result_info)
    index_to_execution_time_bounds = get_index_to_execution_time_bounds(
        index_to_result_info,
        indices_to_use,
        max_time,
        bound_fn,
        time_prefs)

    # First create a sorted list of indices that computes the order of the means
    #indices_sorted_by_mean_exec_time = list(range(0, len(index_to_execution_time_bounds)))
    indices_sorted_by_mean_exec_time = indices_to_use.copy()
    indices_sorted_by_mean_exec_time = sorted(
        indices_sorted_by_mean_exec_time,
        key=lambda index: index_to_execution_time_bounds[index][1],
        reverse=False)
    _logger.debug('Computed ordered means: {}'.format(indices_sorted_by_mean_exec_time))

    # Now construct the groupings
    indices_sorted_and_grouped_by_exec_time = []
    for index in indices_sorted_by_mean_exec_time:
        if len(indices_sorted_and_grouped_by_exec_time) == 0:
            indices_sorted_and_grouped_by_exec_time.append([index])
            continue
        bounds_for_index = index_to_execution_time_bounds[index]
        current_indices_bound_group = indices_sorted_and_grouped_by_exec_time[-1]
        # FIXME: not optimal to keep doing this
        # Turn the bound_group_indices into a list of bounds
        current_bound_group = _bound_group_indices_to_bound_group(
            index_to_execution_time_bounds,
            current_indices_bound_group)
        if bound_overlaps_with_group(current_bound_group, bounds_for_index):
            # This bound overlaps so add it to exist group
            current_indices_bound_group.append(index)
        else:
            # Doesn't overlap so add to a new group
            indices_sorted_and_grouped_by_exec_time.append([index])

    # Construct bound groups
    bound_groups = []
    for list_of_indices in indices_sorted_and_grouped_by_exec_time:
        bound_groups.append(
            _bound_group_indices_to_bound_group(
                index_to_execution_time_bounds,
                list_of_indices)
        )

    return indices_sorted_and_grouped_by_exec_time, bound_groups

# Useful for unifying timeouts
def get_result_with_modified_time(r, time):
    assert isinstance(r, dict)
    assert isinstance(time, float)
    assert time >= 0.0
    fields_to_set_to_time= [
        'dsoes_wallclock_time',
        'user_cpu_time',
        'wallclock_time'
    ]
    fields_to_zero = [
        'sys_cpu_time'
    ]
    r_copy = copy.deepcopy(r)
    for list_to_it, value in ((fields_to_set_to_time, time), (fields_to_zero, 0.0)):
        for field in list_to_it:
            if field in r_copy:
                if isinstance(r_copy[field], list):
                    num_elms = len(r_copy[field])
                    assert num_elms > 0
                    r_copy[field] = [value] * num_elms
                else:
                    assert isinstance(r_copy[field], float) or r_copy[field] is None
                    r_copy[field] = value
    return r_copy

