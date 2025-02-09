#!/usr/bin/env python
# Copyright (c) 2017, Daniel Liew
# This file is covered by the license in LICENSE.txt
# vim: set sw=4 ts=4 softtabstop=4 expandtab:
"""
Read a result info files and strip the relevant fields to
turn it into an invocation info file
"""
from load_smtrunner import add_smtrunner_to_module_search_path
add_smtrunner_to_module_search_path()
from smtrunner import ResultInfo, DriverUtil, analysis
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

def main(args):
    global _logger
    parser = argparse.ArgumentParser(description=__doc__)
    DriverUtil.parserAddLoggerArg(parser)
    parser.add_argument('result_infos',
                        type=argparse.FileType('r'))
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

    keys_to_strip = [
        'sat',
        'wallclock_time',
        'working_directory',
        'exit_code',
        'out_of_memory',
        'stdout_log_file',
        'stderr_log_file',
        'user_cpu_time',
        'sys_cpu_time',
        'backend_timeout',
        'merged_result',
        'error',
        'dsoes_wallclock_time',
        'event_tag',
    ]

    for r in result_infos['results']:
        if 'expected_sat' in r and 'sat' in r:
            # Result might be merged so use `get_sat_from_result_info
            expected_sat, es_conflict = analysis.get_expected_sat_from_result_info(r)
            sat, s_conflict = analysis.get_sat_from_result_info(r)
            if es_conflict or s_conflict:
                _logger.warning('Found conflict for {}'.format(
                    r['benchmark']))
            # If the result is merged this will flatten the result
            if expected_sat == 'unknown' and sat != 'unknown':
                _logger.info('Copying over sat for {}'.format(r['benchmark']))
                r['expected_sat'] = sat
            else:
                _logger.debug('Preserving expected_sat')
                r['expected_sat'] = expected_sat
        # strip keys
        for key in keys_to_strip:
            if key in r:
                r.pop(key, None)

    if 'misc' in result_infos:
        result_infos.pop('misc')

    # Validate against schema
    try:
        _logger.info('Validating result_infos')
        ResultInfo.validateResultInfos(result_infos)
    except ResultInfo.ResultInfoValidationError as e:
        _logger.error('Validation error:\n{}'.format(e))
        return 1
    _logger.info('Validation complete')

    smtrunner.util.writeYaml(pargs.output, result_infos)
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
