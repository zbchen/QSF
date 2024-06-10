#!/usr/bin/env python
# This file is covered by the license in LICENSE.txt
# vim: set sw=4 ts=4 softtabstop=4 expandtab:
"""
Read a result info file and annotate with fuzzing throughput
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
    if not isinstance(event_analyser, event_analysis.JFSRunnerEventAnalyser):
        _logger.error('Must be a JFS run')
        return 1
    new_results = result_infos.copy()
    new_results['results'] = []
    for ri in result_infos['results']:
        key = ResultInfoUtil.get_result_info_key(ri)
        wd = ResultInfoUtil.get_result_info_wd(ri)
        geti = event_analysis.GETInfo(
            ri=ri,
            wd_base=pargs.wd_base,
            benchmark_base=pargs.benchmark_base,
            backend=backend
        )

        new_ri = ri.copy()

        num_inputs, num_wrong_sized_inputs, fuzzing_wallclock_time = event_analyser.get_fuzzing_throughput_fields(geti)
        assert num_inputs is None or isinstance(num_inputs, int)
        assert num_wrong_sized_inputs is None or isinstance(num_wrong_sized_inputs, int)
        assert fuzzing_wallclock_time is None or isinstance(fuzzing_wallclock_time, float)
        _logger.info('num_inputs = {} for {}'.format(num_inputs, key))
        _logger.info('num_wrong_sized_inputs = {} for {}'.format(num_wrong_sized_inputs, key))
        _logger.info('fuzzing_wallclock_time = {} for {}'.format(
            fuzzing_wallclock_time,
            key))

        # Get LibFuzzer stats
        libfuzzer_avg_exec = event_analyser.get_libfuzzer_stat_average_exec_per_sec(geti)
        new_ri['libfuzzer_average_exec_per_sec'] = libfuzzer_avg_exec
        _logger.info('libfuzzer_average_exec_per_sec = {} for {}'.format(
            libfuzzer_avg_exec,
            key))

        # Get event tag so we can determine when the through put information
        # should be available.
        tag = event_analyser.get_event_tag(geti)
        if tag is None:
            _logger.error('Unhandled event for "{}"'.format(key))
            _logger.error(pprint.pformat(ri))
            return 1
        if tag in {'sat', 'unsat', 'sat_but_expected_unsat', 'unsat_but_expected_sat'}:
            # num_inputs = 1
            if num_inputs is None:
                num_inputs = 1
                # _logger.error('num_inputs should not be None for {} ({})'.format(key, wd))
                _logger.info('num_inputs should not be None for {} ({})'.format(key, wd))
                # return 1
            if num_wrong_sized_inputs is None:
                # _logger.error('num_wrong_sized_inputs should not be None for {} ({})'.format(key, wd))
                _logger.info('num_wrong_sized_inputs should not be None for {} ({})'.format(key, wd))
                num_wrong_sized_inputs = 1
                # return 1
            if fuzzing_wallclock_time is None:
                # _logger.error('fuzzing_wallclock_time should not be None for {} ({})'.format(key, wd))
                _logger.info('fuzzing_wallclock_time should not be None for {} ({})'.format(key, wd))
                fuzzing_wallclock_time = 0
                # return 1


        new_ri['jfs_stat_num_inputs'] = num_inputs
        new_ri['jfs_stat_num_wrong_sized_inputs'] = num_wrong_sized_inputs
        new_ri['jfs_stat_fuzzing_wallclock_time'] = fuzzing_wallclock_time
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
