#!/usr/bin/env python
# Copyright (c) 2017, Daniel Liew
# This file is covered by the license in LICENSE.txt
# vim: set sw=4 ts=4 softtabstop=4 expandtab:
"""
Read a result info file and annotate with event tag
"""
from load_smtrunner import add_smtrunner_to_module_search_path
add_smtrunner_to_module_search_path()
from smtrunner import ResultInfo, DriverUtil, ResultInfoUtil, event_analysis
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

#Get Event Tag info

_logger = None

def main(args):
    global _logger
    parser = argparse.ArgumentParser(description=__doc__)
    DriverUtil.parserAddLoggerArg(parser)
    parser.add_argument('result_infos',
                        type=argparse.FileType('r'))
    parser.add_argument('--benchmark-base',
        dest="benchmark_base",
        default="",
        type=str)
    parser.add_argument('--wd-base',
        dest="wd_base",
        default="",
        type=str)
    parser.add_argument('--timeout',
        type=float,
        default=None,
        help='Timeout to assume when creating tags',
    )
    parser.add_argument('--use-dsoes-wallclock-time',
        action='store_true',
        default=False,
    )
    parser.add_argument('--output',
        type=argparse.FileType('w'),
        default=sys.stdout,
    )
    pargs = parser.parse_args(args)
    DriverUtil.handleLoggerArgs(pargs, parser)
    _logger = logging.getLogger(__name__)
    _logger.info('Using benchmark base of "{}"'.format(pargs.benchmark_base))
    _logger.info('Using working directory base of "{}"'.format(pargs.wd_base))

    try:
        _logger.info('Loading "{}"'.format(pargs.result_infos.name))
        result_infos = ResultInfo.loadRawResultInfos(pargs.result_infos)
    except ResultInfo.ResultInfoValidationError as e:
        _logger.error('Validation error:\n{}'.format(e))
        return 1
    _logger.info('Loading done')

    runner = result_infos['misc']['runner']
    _logger.info('Found runner "{}"'.format(runner))
    backend = None
    if 'backend' in result_infos['misc']:
        backend = result_infos['misc']['backend']
    _logger.info('Backend was "{}"'.format(backend))

    event_analyser = event_analysis.get_event_analyser_from_runner_name(
        runner,
        soft_timeout=pargs.timeout,
        use_dsoes_wallclock_time=pargs.use_dsoes_wallclock_time)
    new_results = result_infos.copy()
    new_results['results'] = []
    for ri in result_infos['results']:
        key = ResultInfoUtil.get_result_info_key(ri)
        # Construct get event tag info
        geti = event_analysis.GETInfo(
            ri=ri,
            wd_base=pargs.wd_base,
            benchmark_base=pargs.benchmark_base,
            backend=backend
        )
        tag = event_analyser.get_event_tag(geti)
        if tag is None:
            _logger.error('Unhandled event for "{}"'.format(key))
            _logger.error(pprint.pformat(ri))
            return 1

        new_ri = ri.copy()
        new_ri['event_tag'] = tag
        new_results['results'].append(new_ri)

    # Validate against schema
    try:
        _logger.info('Validating result_infos')
        ResultInfo.validateResultInfos(new_results)
    except ResultInfo.ResultInfoValidationError as e:
        _logger.error('Validation error:\n{}'.format(e))
        return 1
    _logger.info('Validation complete')

    smtrunner.util.writeYaml(pargs.output, new_results)

    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
