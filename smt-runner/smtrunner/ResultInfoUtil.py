#!/usr/bin/env python
# vim: set sw=4 ts=4 softtabstop=4 expandtab:
import logging
import os
import pprint

_logger = logging.getLogger(__name__)

def get_result_info_key(ri):
    return ri['benchmark']

def get_result_info_wd(ri):
    return ri['working_directory']

def group_result_infos_by(result_infos_list, key_fn=get_result_info_key):
    """
    Given a list of raw `ResultInfos` group them by `key_fn`. `key_fn` should be a
    function that takes a raw `ResultInfo` and returns a unique identifier.

    Returns a tuple (key_to_result_infos, rejected_result_infos)

    `key_to_result_infos` is a dictionary mapping the key to a list of raw `ResultInfo`s
    where the index of the `ResultInfo` corresponds to the index in which it was found
    in `result_infos_list`.

    `rejected_result_infos` is a list containing rejected raw `ResultInfo`s.
    It maps the index of the raw `ResultInfos` (in `result_infos_list`) to
    a list of rejected raw `ResultInfo`s.
    """
    rejected_result_infos = [ ]
    assert(len(result_infos_list) > 0)

    key_to_result_infos = dict()
    number_of_result_infos = len(result_infos_list)
    _logger.debug('number_of_result_infos: {}'.format(number_of_result_infos))

    defaultGroup = []
    for _ in range(0, number_of_result_infos):
        defaultGroup.append(None)
        rejected_result_infos.append([])
    assert(len(defaultGroup) == number_of_result_infos)
    assert(len(rejected_result_infos) == number_of_result_infos)

    for result_infos_index in range(0, number_of_result_infos):
        for r in result_infos_list[result_infos_index]['results']:
            key = key_fn(r)
            if key not in key_to_result_infos:
                key_to_result_infos[key] = defaultGroup.copy()
                _logger.debug('Added key "{}" = {}'.format(key, key_to_result_infos[key]))
            group_for_key = key_to_result_infos[key]
            if group_for_key[result_infos_index] is not None:
                _logger.error(
                    '"{}" cannot appear more than once in the same result infos (index {})'.format(
                    key, result_infos_index))
                _logger.debug('group_for_key: {}'.format(group_for_key))
                rejected_result_infos[result_infos_index].append(r)
                continue
            else:
                _logger.debug('Inserting at index {} for key "{}"'.format(result_infos_index, key))
                key_to_result_infos[key][result_infos_index] = r

    #_logger.debug('key_to_result_infos: {}'.format(pprint.pformat(key_to_result_infos)))
    return (key_to_result_infos, rejected_result_infos)


class MergeResultInfoException(Exception):
    def __init__(self, msg):
        # pylint: disable=super-init-not-called
        self.msg = msg

def compute_longest_common_path_prefix(paths):
    result = _compute_longest_common_path_prefix(paths)
    assert os.path.isdir(result)
    assert os.path.isabs(result)
    return result

def _compute_longest_common_path_prefix(paths):
    assert isinstance(paths, list)
    assert len(paths) > 1
    assert all([ isinstance(p, str) and os.path.isabs(p) for p in paths])
    split_by_path_sep = [  p.split(os.path.sep) for p in paths ]
    shortest_len = min([ len(sp) for sp in split_by_path_sep ])
    same_up_to = -1
    for index in range(0, shortest_len):
        path_element = split_by_path_sep[0][index]
        _logger.debug('Checking if "{}" is common'.format(path_element))
        if not all([ sp[index] == path_element for sp in split_by_path_sep]):
            break
        same_up_to += 1
    assert same_up_to >= 0
    slice = split_by_path_sep[0][0:(same_up_to +1)]
    result = os.path.sep.join(slice)
    return result

def compute_longest_common_path_suffix(paths):
    # Reverse all the paths
    assert len(paths) > 1
    reversed_paths = [ os.sep + ''.join(reversed(p)) for p in paths ]
    reversed_result = _compute_longest_common_path_prefix(reversed_paths)
    result = ''.join(reversed_result)
    assert result[0] == os.sep
    result = result[1:]
    return result

def merge_raw_result_infos(key_to_results_infos, allow_merge_errors=False, wd_bases=None):
    assert isinstance(key_to_results_infos, dict)
    new_key_to_results_info = dict()
    longest_common_wd_base = None
    if wd_bases is not None:
        longest_common_wd_base = compute_longest_common_path_prefix(wd_bases)
        _logger.info('Common wd base in "{}"'.format(longest_common_wd_base))
    errors = []
    for key, raw_result_info_list in key_to_results_infos.items():
        _logger.debug('Merging "{}"'.format(key))
        assert key not in new_key_to_results_info
        try:
            new_key_to_results_info[key] = merge_raw_results(
                raw_result_info_list,
                longest_common_wd_base,
                wd_bases
            )
        except MergeResultInfoException as e:
            _logger.error('Failed to merge "{}"'.format(key))
            if allow_merge_errors:
                errors.append(e)
            else:
                raise e
    return (new_key_to_results_info, errors)

def aggregate_field(name, list_of_raw_results, optional=False):
    assert isinstance(list_of_raw_results, list)
    assert len(list_of_raw_results) > 0
    aggregate_values = []
    for index, rr in enumerate(list_of_raw_results):
        if rr is None:
            # Missing result info
            msg = "Can't merge results where result is None at index {}".format(index)
            _logger.error(msg)
            raise MergeResultInfoException(msg)
        assert isinstance(rr, dict)
        if name not in rr:
            if optional:
                _logger.debug('Field "{}" is missing from raw result'.format(name))
                aggregate_values.append(None)
            else:
                msg = 'Field "{}" is missing'.format(name)
                _logger.error(msg)
                raise MergeResultInfoException(msg)
        else:
            aggregate_values.append(rr[name])
    return aggregate_values

def identical_field_or_error(name, list_of_raw_results):
    assert len(list_of_raw_results) > 0
    if name not in list_of_raw_results[0]:
        msg = 'Field "{}" is missing'.format(name)
        raise MergeResultInfoException(msg)
    field_value = list_of_raw_results[0][name]
    for index in range(1, len(list_of_raw_results)):
        field_value_at_index = list_of_raw_results[index][name]
        if field_value_at_index != field_value:
            msg = 'Mismatch at field "{}" with {} != {}'.format(
                name,
                field_value,
                field_value_at_index
                )
            _logger.error(msg)
            raise MergeResultInfoException(msg)
    return field_value

def rebase_paths_infer(paths):
    assert isinstance(paths, list)
    assert all([ isinstance(p, str) for p in paths])
    if len(paths) < 2:
        return paths
    abs_paths = [ os.path.abspath(p)  for p in paths ]
    lcpp = compute_longest_common_path_prefix(abs_paths)
    return [rebase_path(p, lcpp) for p in abs_paths]

def rebase_path(original, new_base):
    assert isinstance(original, str)
    assert os.path.isabs(original)
    assert isinstance(new_base, str)
    assert os.path.isabs(new_base)
    assert original.startswith(new_base)
    return original[len(new_base):]

def strip_ls(path):
    if path.startswith(os.path.sep):
        return path[1:]
    return path

def rebase_aggregate_path(agg, new_base, current_bases):
    if new_base is None:
        return agg
    assert isinstance(agg, list)
    assert isinstance(new_base, str)
    assert isinstance(current_bases, list)
    new_paths = []
    assert len(agg) == len(current_bases)
    for index, p in enumerate(agg):
        # Compute existing absolute path
        p_nls = strip_ls(p)
        p_base = current_bases[index]
        full_existing_path = os.path.join(p_base, p_nls)
        _logger.debug('Computed existing path to be "{}"'.format(full_existing_path))
        new_path = rebase_path(full_existing_path, new_base)
        assert os.path.exists(os.path.join(new_base, strip_ls(new_path)))
        new_paths.append(new_path)
    return new_paths

def aggregate_is_all_none(agg):
    return all(map(lambda x: x is None, agg))

def field_is_available(field_name, lorr):
    for rr in lorr:
        assert isinstance(rr, dict)
        if field_name in rr:
            return True
    return False
    
def merge_raw_results(lorr, new_wd_base, wd_bases):
    assert isinstance(lorr, list)
    _logger.debug('Merging:\n{}'.format(pprint.pformat(lorr)))
    new_r = {
        'backend_timeout': aggregate_field('backend_timeout', lorr),
        'benchmark': identical_field_or_error('benchmark', lorr),
        'dsoes_wallclock_time': aggregate_field('dsoes_wallclock_time', lorr, optional=True),
        'event_tag': aggregate_field('event_tag', lorr, optional=True),
        'exit_code': aggregate_field('exit_code', lorr),
        'expected_sat': identical_field_or_error('expected_sat', lorr),
        'out_of_memory': aggregate_field('out_of_memory', lorr),
        'sat': aggregate_field('sat', lorr),
        'stderr_log_file':
            rebase_aggregate_path(
                aggregate_field('stderr_log_file', lorr),
                new_wd_base,
                wd_bases
            ),
        'stdout_log_file':
            rebase_aggregate_path(
                aggregate_field('stdout_log_file', lorr),
                new_wd_base,
                wd_bases
            ),
        'sys_cpu_time': aggregate_field('sys_cpu_time', lorr),
        'user_cpu_time': aggregate_field('user_cpu_time', lorr),
        'wallclock_time': aggregate_field('wallclock_time', lorr),
        'working_directory':
            rebase_aggregate_path(
                aggregate_field('working_directory', lorr),
                new_wd_base,
                wd_bases
            ),
    }
    # FIXME: We really need to do merging on a per runner basis.
    jfs_working_directory = aggregate_field('jfs_working_directory', lorr, optional=True)
    if not aggregate_is_all_none(jfs_working_directory):
        jfs_working_directory = rebase_aggregate_path(jfs_working_directory,
            new_wd_base,
            wd_bases
        )
        new_r['jfs_working_directory'] = jfs_working_directory
    # Merge expected identical field if available.
    identical_field_to_add_if_available = {
        'is_trivial',
    }
    for field in identical_field_to_add_if_available:
        if not field_is_available(field, lorr):
            continue
        new_r[field] = identical_field_or_error(field, lorr)
    # Merge other fields if available.
    agg_fields_to_add_if_available = {
        'jfs_stat_fuzzing_wallclock_time',
        'jfs_stat_num_inputs',
        'jfs_stat_num_wrong_sized_inputs',
        'libfuzzer_average_exec_per_sec',
    }
    for field in agg_fields_to_add_if_available:
        if not field_is_available(field, lorr):
            continue
        new_r[field] = aggregate_field(field, lorr, optional=True)
    return new_r
