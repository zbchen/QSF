#!/usr/bin/env python
# Copyright (c) 2017, Daniel Liew
# This file is covered by the license in LICENSE.txt
# vim: set sw=4 ts=4 softtabstop=4 expandtab:
"""
Read a result info file and extract the wallclock time from
docker-stats-on-exit-shim (dsoes)
"""
from load_smtrunner import add_smtrunner_to_module_search_path
add_smtrunner_to_module_search_path()
from smtrunner import ResultInfo, DriverUtil
import smtrunner.util

import argparse
import json
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

_fail_count = 0

def get_satisfiability_result(r, base_path):
    global _fail_count
    stdout_path = r['stdout_log_file']
    if stdout_path.startswith('/'):
        stdout_path = stdout_path[1:]
    full_path = os.path.join(base_path, stdout_path)
    if not os.path.exists(full_path):
        _logger.error('"{}" does not exist'.format(full_path))
        raise Exception('missing file')
    sat = 'unknown'
    with open(full_path, 'r') as f_sat:
        first_line = f_sat.readline()
        _logger.debug('Got first line \"{}\"'.format(first_line))
        m = _RE_SAT_RESPONCE.match(first_line)
        if m:
            sat = m.group(1)
        else:
            _logger.warning('Failed to read sat result from "{}"'.format(f_sat.name))
            _fail_count += 1
    r_copy = r.copy()
    r_copy['sat'] = sat
    return r_copy

def get_dsoes_wallclock_time_result(r, base_path):
    global _fail_count
    r_copy = r.copy()
    r_copy['dsoes_wallclock_time'] = None
    workdir_path = r['working_directory']
    if workdir_path.startswith('/'):
        workdir_path = workdir_path[1:]
    workdir_path = os.path.join(base_path, workdir_path)
    exit_stats_file_path = os.path.join(workdir_path, 'exit_stats.json')
    if not os.path.exists(exit_stats_file_path):
        _logger.error('"{}" does not exist'.format(exit_stats_file_path))
        _fail_count += 1
        return r_copy
    try:
        with open(exit_stats_file_path, 'r') as f_time:
            stats = json.load(f_time)
            dsoes_wallclock_time = stats["wall_time"] / (10**9)
            r_copy['dsoes_wallclock_time'] = dsoes_wallclock_time
    except Exception as e:
        _logger.error('Failed to retrieve stats from "{}"'.format(exit_stats_file_path))
        _logger.error(e)
        _fail_count += 1
    return r_copy


def add_dsoes_wallclock_time(results, base_path):
    new_results=[]
    for r in results:
        _logger.debug('Processing "{}"'.format(r['benchmark']))
        new_r = get_dsoes_wallclock_time_result(r, base_path)
        new_results.append(new_r)
    return new_results

def main(args):
    global _logger
    global _fail_count
    parser = argparse.ArgumentParser(description=__doc__)
    DriverUtil.parserAddLoggerArg(parser)
    parser.add_argument('result_infos',
                        type=argparse.FileType('r'))
    parser.add_argument('--base', type=str, default="")
    parser.add_argument('-o', '--output',
                        type=argparse.FileType('w'),
                        default=sys.stdout,
                        help='Output location (default stdout)')

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

    # START Apply filters
    new_results = result_infos['results']
    new_results = add_dsoes_wallclock_time(new_results, pargs.base)

    # END Apply filters
    new_result_infos = result_infos
    new_result_infos['results'] = new_results

    if _fail_count > 0:
        _logger.warning('Failed to parse "{}" files'.format(_fail_count))


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
