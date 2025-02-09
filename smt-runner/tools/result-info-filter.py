#!/usr/bin/env python
# Copyright (c) 2017, Daniel Liew
# This file is covered by the license in LICENSE.txt
# vim: set sw=4 ts=4 softtabstop=4 expandtab:
"""
Read a result info files and filter based on a predicate
"""
from load_smtrunner import add_smtrunner_to_module_search_path
add_smtrunner_to_module_search_path()
from smtrunner import ResultInfo, ResultInfoUtil, DriverUtil
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

_RE_SMT2_STATUS = re.compile(r'^\s*\(set-info\s*:status\s*(sat|unsat|unknown)')
_RE_SMT2_DECL_FUN = re.compile(r'^\s*\(declare-fun')

def get_expected_sat(path):
    _logger.debug('Opening "{}"'.format(path))
    status = "unknown"
    with open(path, 'r') as f:
        for line in f:
            m = _RE_SMT2_DECL_FUN.match(line)
            if m:
                _logger.warning('Failed to find status decl in "{}"'.format(path))
                break
            m = _RE_SMT2_STATUS.match(line)
            if m:
                status = m.group(1)
                break
    _logger.debug('Status of "{}" is {}'.format(path, status))
    return status

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

def filter_out_expected_sat_types_impl(key, results, sat_types):
    assert isinstance(sat_types, list)
    report_initial(results)
    new_results = [ ]
    for r in results:
        sat = r[key]
        if any(map(lambda x: x == sat, sat_types)):
            continue
        new_results.append(r)
    report_after(new_results, results)
    return new_results

def filter_out_sat_types(results, sat_types, base):
    assert isinstance(sat_types, list)
    _logger.info('Filtering out sat types: {}'.format(sat_types))
    return filter_out_expected_sat_types_impl('sat', results, sat_types)

def filter_out_expected_sat_types(results, sat_types, base):
    assert isinstance(sat_types, list)
    _logger.info('Filtering out expected sat types: {}'.format(sat_types))
    return filter_out_expected_sat_types_impl('expected_sat', results, sat_types)

def filter_random_sample(results, n):
    assert isinstance(n, int)
    assert n >= 0
    report_initial(results)
    new_results = random.sample(results, n)
    report_after(new_results, results)
    return new_results

def filter_random_percentange(results, percen):
    assert isinstance(percen, float)
    assert percen >= 0.0
    assert percen <= 1.0
    num_results = len(results)
    num_sample = math.ceil(num_results * percen)
    _logger.info('Filter keeping {}% of results'.format(percen*100))
    _logger.info('Keeping {} out of {}'.format(num_sample, num_results))
    return filter_random_sample(results, num_sample)

def filter_keep_benchmarks_matching_regex(results, regex):
    benchmark_re = re.compile(regex)
    report_initial(results)
    new_results = []
    _logger.info('Filter keeping benchmarks matching regex "{}"'.format(regex))
    for r in results:
        benchmark_name = r['benchmark']
        m = benchmark_re.match(benchmark_name)
        if m:
            new_results.append(r)
    report_after(new_results, results)
    return new_results

def filter_out_benchmarks_matching_regex(results, regex):
    benchmark_re = re.compile(regex)
    report_initial(results)
    new_results = []
    _logger.info('Filter removing benchmarks matching regex "{}"'.format(regex))
    for r in results:
        benchmark_name = r['benchmark']
        m = benchmark_re.match(benchmark_name)
        if m is None:
            new_results.append(r)
    report_after(new_results, results)
    return new_results

def filter_keep_benchmarks_matching_exit_code(results, exit_code):
    assert isinstance(exit_code, int)
    report_initial(results)
    new_results = []
    _logger.info('Filter keeping benchmarks with exit_code "{}"'.format(exit_code))
    for r in results:
        if 'exit_code' not in r:
            continue
        r_exit_code = r['exit_code']
        if r_exit_code == exit_code:
            new_results.append(r)
    report_after(new_results, results)
    return new_results

def _filter_keep_has_trivial_value(results, value):
    assert isinstance(value, bool) or value is None
    report_initial(results)
    new_results = []
    _logger.info('Filter keeping benchmarks with `is_trival: {}`'.format(value))
    for r in results:
        if 'is_trivial' not in r:
            if value is None:
                new_results.append(r)
            continue
        is_trivial = r['is_trivial']
        if is_trivial == value:
            new_results.append(r)

    report_after(new_results, results)
    return new_results

def filter_keep_non_trivial_benchmarks(results):
    return _filter_keep_has_trivial_value(results, value=False)

def filter_keep_trivial_benchmarks(results):
    return _filter_keep_has_trivial_value(results, value=True)

def _filter_benchmarks_from_file_imp(results, f, mode):
    assert mode == 'keep' or mode == 'out'
    rri_for_filter = ResultInfo.loadRawResultInfos(f)
    # Collect the keys present in the file
    keys = set()
    for ri in rri_for_filter['results']:
        key = ResultInfoUtil.get_result_info_key(ri)
        keys.add(key)
    report_initial(results)
    new_results = []
    if mode == 'keep':
        should_keep = lambda ri: ResultInfoUtil.get_result_info_key(ri) in keys
    elif mode == 'out':
        should_keep = lambda ri: ResultInfoUtil.get_result_info_key(ri) not in keys
    else:
        assert False

    for ri in results:
        if should_keep(ri):
            new_results.append(ri)
            _logger.debug('Keeping benchmark {}'.format(
                ResultInfoUtil.get_result_info_key(ri))
            )
        else:
            _logger.debug('Removing benchmark {}'.format(
                ResultInfoUtil.get_result_info_key(ri))
            )

    report_after(new_results, results)
    return new_results


def filter_keep_benchmarks_from_file(results, f):
    return _filter_benchmarks_from_file_imp(results, f, mode='keep')

def filter_out_benchmarks_from_file(results, f):
    return _filter_benchmarks_from_file_imp(results, f, mode='out')


# END filters

def main(args):
    global _logger
    parser = argparse.ArgumentParser(description=__doc__)
    DriverUtil.parserAddLoggerArg(parser)
    parser.add_argument('result_infos',
                        type=argparse.FileType('r'))
    parser.add_argument('--base', type=str, default="")
    parser.add_argument('--random-seed',
                        type=int,
                        default=0,
                        dest='random_seed')
    parser.add_argument('-o', '--output',
                        type=argparse.FileType('w'),
                        default=sys.stdout,
                        help='Output location (default stdout)')
    # START filter arguments
    parser.add_argument('--filter-out-expected-sat',
        dest='filter_out_expected_sat',
        nargs='+', # gather into list
        choices=['sat', 'unsat', 'unknown'],
        default=[],
    )
    parser.add_argument('--filter-out-sat',
        dest='filter_out_sat',
        nargs='+', # gather into list
        choices=['sat', 'unsat', 'unknown'],
        default=[],
    )
    parser.add_argument('--filter-random-percentage',
        dest='filter_random_percentange',
        type=float,
        default=None,
    )
    parser.add_argument('--filter-keep-benchmark-matching-regex',
        dest='filter_keep_benchmarks_matching_regex',
        type=str,
        default=None,
    )
    parser.add_argument('--filter-out-benchmark-matching-regex',
        dest='filter_out_benchmarks_matching_regex',
        type=str,
        default=None,
    )
    parser.add_argument('--filter-keep-benchmark-matching-exit-code',
        dest='filter_keep_benchmarks_matching_exit_code',
        type=int,
        default=None,
    )
    parser.add_argument('--filter-keep-non-trivial',
        default=False,
        action='store_true',
    )
    parser.add_argument('--filter-keep-trivial',
        default=False,
        action='store_true',
    )
    parser.add_argument('--filter-keep-benchmarks-from-file',
        dest='filter_keep_benchmarks_from_file',
        type=argparse.FileType('r'),
    )
    parser.add_argument('--filter-out-benchmarks-from-file',
        dest='filter_out_benchmarks_from_file',
        type=argparse.FileType('r'),
    )

    # END filter arguments

    pargs = parser.parse_args(args)
    DriverUtil.handleLoggerArgs(pargs, parser)
    _logger = logging.getLogger(__name__)

    try:
        _logger.info('Loading "{}"'.format(pargs.result_infos.name))
        result_infos = ResultInfo.loadRawResultInfos(pargs.result_infos)
    except ResultInfo.ResultInfoValidationError as e:
        _logger.error('Validation error:\n{}'.format(e))
        return 1
    _logger.info('Loading done')

    # Set random seed
    random.seed(pargs.random_seed)

    # START Apply filters
    new_results = result_infos['results']
    if len(pargs.filter_out_expected_sat) > 0:
        new_results = filter_out_expected_sat_types(
            new_results,
            pargs.filter_out_expected_sat,
            pargs.base)

    if len(pargs.filter_out_sat) > 0:
        new_results = filter_out_sat_types(
            new_results,
            pargs.filter_out_sat,
            pargs.base)

    if pargs.filter_random_percentange is not None:
        if not (pargs.filter_random_percentange >= 0.0 and pargs.filter_random_percentange <= 1.0):
            _logger.error('Filter percentage must be in range [0.0, 1.0]')
            return 1
        new_results = filter_random_percentange(
            new_results,
            pargs.filter_random_percentange
        )
    if pargs.filter_keep_benchmarks_matching_regex:
        new_results = filter_keep_benchmarks_matching_regex(
            new_results,
            pargs.filter_keep_benchmarks_matching_regex
        )
    if pargs.filter_out_benchmarks_matching_regex:
        new_results = filter_out_benchmarks_matching_regex(
            new_results,
            pargs.filter_out_benchmarks_matching_regex
        )

    if pargs.filter_keep_benchmarks_matching_exit_code is not None:
        new_results = filter_keep_benchmarks_matching_exit_code(
                new_results,
                pargs.filter_keep_benchmarks_matching_exit_code)

    if pargs.filter_keep_non_trivial:
        new_results = filter_keep_non_trivial_benchmarks(new_results)
    if pargs.filter_keep_trivial:
        new_results = filter_keep_trivial_benchmarks(new_results)

    if pargs.filter_out_benchmarks_from_file:
        new_results = filter_out_benchmarks_from_file(
            new_results,
            pargs.filter_out_benchmarks_from_file
        )
    if pargs.filter_keep_benchmarks_from_file:
        new_results = filter_keep_benchmarks_from_file(
            new_results,
            pargs.filter_keep_benchmarks_from_file
        )

    # END Apply filters
    new_result_infos = result_infos
    new_result_infos['results'] = new_results


    # Validate against schema
    try:
        _logger.info('Validating result_infos')
        ResultInfo.validateResultInfos(new_result_infos)
    except ResultInfo.ResultInfoValidationError as e:
        _logger.error('Validation error:\n{}'.format(e))
        return 1
    _logger.info('Validation complete')


    smtrunner.util.writeYaml(pargs.output, new_result_infos)
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
