#!/usr/bin/env python
# Copyright (c) 2017, Daniel Liew
# This file is covered by the license in LICENSE.txt
# vim: set sw=4 ts=4 softtabstop=4 expandtab:
"""
Read several result info files and filter based on a predicate
that applies globally over all result info files.
"""
from load_smtrunner import add_smtrunner_to_module_search_path
add_smtrunner_to_module_search_path()
from smtrunner import ResultInfo, DriverUtil, ResultInfoUtil, analysis
import smtrunner.util

import argparse
import logging
import math
import os
import pprint
import random
import re
import sys
import yaml

_logger = None

def strip(prefix, path):
    if prefix == "":
        return path
    if path.startswith(prefix):
        return path[len(prefix):]

# START filters

def report_initial(results):
    _logger.info('{} results initially'.format(len(results)))

def report_after(new_results, results):
    lnr = len(new_results)
    lr = len(results)
    if lnr != lr:
        _logger.info('Results changed {} results after. {} removed'.format(
            lnr, lr - lnr))
    else:
        _logger.info('Results not changed')

def all_elements_are_same(s):
    assert len(s) > 0
    return len(set(s)) == 1

def filter_out_global_sat_types_impl(results, sat_types, merged_key_to_result_info):
    global_sat_types_conflicts = set()
    assert isinstance(sat_types, list)
    assert isinstance(results, list)
    report_initial(results)
    global_sat_help_count = 0
    new_results = [ ]
    for r in results:
        # Get key for result
        result_key = ResultInfoUtil.get_result_info_key(r)
        # Get corresponding global result
        global_r = merged_key_to_result_info[result_key]
        # Now get merged satisfiability result
        merged_sat, foundConflict = analysis.get_sat_from_result_info(global_r)
        if foundConflict:
            global_sat_types_conflicts.add(result_key)
            _logger.warning('Found conflict for sat result for key "{}"'.format(result_key))
        if any(map(lambda x: x == merged_sat, sat_types)):
            _logger.debug('Filtering out "{}" with global sat "{}"'.format(
                result_key,
                merged_sat))
            if not all_elements_are_same(global_r['sat']):
                global_sat_help_count += 1
                _logger.info('Global only view allowed filtering for "{}"'.format(
                    result_key))
            continue
        new_results.append(r)
    report_after(new_results, results)
    _logger.info('Global only view filtered {} benchmarks'.format(global_sat_help_count))
    return (new_results, global_sat_types_conflicts)

def filter_out_global_sat_types(results, sat_types, merged_key_to_result_info):
    assert isinstance(sat_types, list)
    _logger.info('Filtering out global_sat types: {}'.format(sat_types))
    return filter_out_global_sat_types_impl(
        results,
        sat_types,
        merged_key_to_result_info)

# END filters

def get_merged_sat(key_to_result_info):
    merged_sat_set = set()
    merged_unsat_set = set()
    merged_unknown_set = set()
    for key, ri in key_to_result_info.items():
        # Get corresponding global result
        assert isinstance(ri['sat'], list)
        merged_sat, foundConflict = analysis.get_sat_from_result_info(ri)
        if foundConflict:
            raise Exception('Merge conflict')
        if merged_sat == 'sat':
            merged_sat_set.add(key)
        elif merged_sat == 'unsat':
            merged_unsat_set.add(key)
        elif merged_sat == 'unknown':
            merged_unknown_set.add(key)
        else:
            raise Exception('Unhandled merge sat result')
    return (merged_sat_set, merged_unsat_set, merged_unknown_set)

def update_expected_sat(results, merged_key_to_result_info):
    _logger.info('Updating expected_sat field')
    assert isinstance(results, list)
    conflicts = set()
    expected_sat_set = set()
    expected_unsat_set = set()
    expected_unknown_set = set()
    report_initial(results)
    new_results = [ ]
    num_updated_fields = 0
    for r in results:
        # Get key for result
        result_key = ResultInfoUtil.get_result_info_key(r)
        # Get corresponding global result
        global_r = merged_key_to_result_info[result_key]
        # Now get merged satisfiability result
        merged_sat, foundConflict = analysis.get_sat_from_result_info(global_r)
        r_copy = r.copy()
        if foundConflict:
            _logger.warning('Found conflict for sat result for key "{}"'.format(result_key))
            conflicts.add(result_key)
        else:
            current_expected_sat = r_copy['expected_sat']
            if current_expected_sat == "unknown" and merged_sat != "unknown":
                num_updated_fields += 1
                r_copy['old_expected_sat'] = current_expected_sat
                r_copy['expected_sat'] = merged_sat
                _logger.info('Updating expected sat for "{}" from {} to {}'.format(
                    result_key,
                    r_copy['old_expected_sat'],
                    r_copy['expected_sat']))
            elif current_expected_sat == "sat" and merged_sat == "unsat":
                msg = "conflict detected, expected sat is sat, but merged is unsat"
                _logger.error(msg)
                raise Exception(msg)
            elif current_expected_sat == "unsat" and merged_sat == "sat":
                msg = "conflict detected, expected sat is unsat, but merged is sat"
                _logger.error(msg)
                raise Exception(msg)
        
        if r_copy['expected_sat'] == 'sat':
            expected_sat_set.add(result_key)
        elif r_copy['expected_sat'] == 'unsat':
            expected_unsat_set.add(result_key)
        elif r_copy['expected_sat'] == 'unknown':
            expected_unknown_set.add(result_key)
        else:
            raise Exception('Unexpected sat type')
        new_results.append(r_copy)
    # Count won't change so don't report
    #report_after(new_results, results)

    _logger.info('Updated expected sat info: {}'.format(
        {
            'sat': len(expected_sat_set),
            'unsat': len(expected_unsat_set),
            'unknown': len(expected_unknown_set),
            'total': len(expected_sat_set) + len(expected_unsat_set) + len(expected_unknown_set)
        }))

    assert len(new_results) == len(results)
    _logger.info('Updated {} expected_sat fields'.format(num_updated_fields))
    return (new_results, conflicts)

def main(args):
    global _logger
    parser = argparse.ArgumentParser(description=__doc__)
    DriverUtil.parserAddLoggerArg(parser)
    parser.add_argument('result_infos',
                        type=argparse.FileType('r'),
                        nargs='+')
    parser.add_argument('-o', '--outputs',
                        type=str,
                        default=[],
                        nargs='+',
                        required=True,
                        help='Output locations',)
    parser.add_argument('--allow-merge-failures',
        dest='allow_merge_failures',
        default=False,
        action='store_true',
    )
    parser.add_argument('--ignore-existing-outputs',
        default=False,
        action='store_true',
    )
    parser.add_argument('--dump-merged-sat',
        default=False,
        action='store_true',
    )
    # START filter arguments
    parser.add_argument('--filter-out-sat',
        dest='filter_out_sat',
        nargs='+', # gather into list
        choices=['sat', 'unsat', 'unknown'],
        default=[],
    )
    # END filter arguments
    parser.add_argument('--update-expected-sat',
        dest='update_expected_sat',
        default=False,
        action='store_true',
    )

    pargs = parser.parse_args(args)
    DriverUtil.handleLoggerArgs(pargs, parser)
    _logger = logging.getLogger(__name__)

    if len(pargs.result_infos) != len(pargs.outputs):
        _logger.error('Number of inputs must be the same as number of outputs')
        return 1

    # Check outputs don't already exist
    if not pargs.ignore_existing_outputs:
        for output_path in pargs.outputs:
            if os.path.exists(output_path):
                msg = '"{}" already exists. Giving up'.format(output_path)
                if pargs.ignore_existing_outputs:
                    _logger.warning(msg)
                else:
                    _logger.error(msg)
                    return 1

    index_to_raw_result_info = []
    index_to_file_name = []
    for rri in pargs.result_infos:
        try:
            _logger.info('Loading "{}"'.format(rri.name))
            result_infos = ResultInfo.loadRawResultInfos(rri)
        except ResultInfo.ResultInfoValidationError as e:
            _logger.error('Validation error:\n{}'.format(e))
            return 1
        index_to_raw_result_info.append(result_infos)
        index_to_file_name.append(rri.name)
    result_infos = None
    _logger.info('Loading done')

    # Perform grouping by benchmark name
    key_to_results_info, rejected_result_infos = ResultInfoUtil.group_result_infos_by(
            index_to_raw_result_info)
    if len(rejected_result_infos) > 0:
        l_was_empty = True
        for index, l in enumerate(rejected_result_infos):
            _logger.warning('Index {} had {} rejections'.format(index, len(l)))
            if len(l) > 0:
                _logger.warning('There were rejected result infos')
                l_was_empty = False
        if not l_was_empty:
            if pargs.allow_merge_failures:
                _logger.warning('Merge failures being allowed')
            else:
                _logger.error('Merge failures are not allowed')
                return 1

    # Merge results infos in memory for analysis
    _logger.info('Merging')
    merged_key_to_result_info, merge_failures = ResultInfoUtil.merge_raw_result_infos(
        key_to_results_info)
    _logger.info('Merge complete')
    if len(merge_failures) > 0:
        if pargs.allow_merge_failures:
            _logger.warning('Merge failures being allowed')
        else:
            _logger.error('Merge failures are not allowed')
            return 1

    # Dump merged sat info
    if pargs.dump_merged_sat:
        merged_sat_keys, merged_unsat_keys, merged_unknown_keys = get_merged_sat(merged_key_to_result_info)
        merged_sat_info = {
            'sat': len(merged_sat_keys),
            'unsat': len(merged_unsat_keys),
            'unknown': len(merged_unknown_keys),
            'total': len(merged_sat_keys) + len(merged_unsat_keys) + len(merged_unknown_keys),
        }
        print("Merged sat counts: {}".format(merged_sat_info))

    # Apply filters
    index_to_new_raw_result_info = []
    filter_out_global_sat_types_conflicts = []
    update_expected_sat_conflicts = []
    for index, rri in enumerate(index_to_raw_result_info):
        _logger.info('START Filtering "{}"'.format(index_to_file_name[index]))
        # Make a shallow copy
        new_rri = rri.copy()
        new_results = rri['results']

        # Do update first so that when it reports results, unsat is not removed.
        if pargs.update_expected_sat:
            new_results, update_expected_sat_conflicts = update_expected_sat(
                new_results,
                merged_key_to_result_info,
            )
        if len(update_expected_sat_conflicts) > 0:
            _logger.error('SAT conflicts detected')
            return 1

        if len(pargs.filter_out_sat) > 0:
            new_results, filter_out_global_sat_types_conflicts = filter_out_global_sat_types(
                new_results,
                pargs.filter_out_sat,
                merged_key_to_result_info,
            )
        if len(filter_out_global_sat_types_conflicts) > 0:
            _logger.error('SAT conflicts detected')
            return 1
        new_rri['results'] = new_results
        _logger.info('DONE Filtering "{}"'.format(index_to_file_name[index]))
        index_to_new_raw_result_info.append(new_rri)


    # Now write results out
    for index, output_file_name in enumerate(pargs.outputs):
        new_result_infos = index_to_new_raw_result_info[index]
        # Validate against schema
        try:
            _logger.info('Validating result_infos')
            ResultInfo.validateResultInfos(new_result_infos)
        except ResultInfo.ResultInfoValidationError as e:
            _logger.error('Validation error:\n{}'.format(e))
            return 1
        _logger.info('Validation complete')
        _logger.info('Writing filtered data from "{}" to "{}"'.format(
            index_to_file_name[index],
            output_file_name))
        with open(output_file_name, 'w') as f:
            smtrunner.util.writeYaml(f, new_result_infos)
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
