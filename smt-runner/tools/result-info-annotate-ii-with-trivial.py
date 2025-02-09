#!/usr/bin/env python
# Copyright (c) 2017, Daniel Liew
# This file is covered by the license in LICENSE.txt
# vim: set sw=4 ts=4 softtabstop=4 expandtab:
"""
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
    parser.add_argument('ii_template', type=argparse.FileType('r'))
    parser.add_argument('--benchmark-base',
        dest="benchmark_base",
        default="",
        type=str)
    parser.add_argument('--wd-base',
        dest="wd_base",
        default="",
        type=str)
    parser.add_argument('--dump-tags',
        dest="dump_tags",
        nargs='+',
        default=[],
    )
    parser.add_argument('--timeout',
        type=float,
        default=None,
    )
    parser.add_argument('--use-dsoes-wallclock-time',
        action='store_true',
        default=False,
    )
    parser.add_argument('--bool-args',
        dest='bool_args',
        nargs='+',
        default=[],
    )
    parser.add_argument('--output',
        default=sys.stdout,
        type=argparse.FileType('w'),
    )
    pargs = parser.parse_args(args)
    DriverUtil.handleLoggerArgs(pargs, parser)
    _logger = logging.getLogger(__name__)
    _logger.info('Using benchmark base of "{}"'.format(pargs.benchmark_base))
    _logger.info('Using working directory base of "{}"'.format(pargs.wd_base))

    extra_kwargs = {}
    bool_arg_re = re.compile(r'^([a-zA-z.]+)=(true|false)')
    for b in pargs.bool_args:
        m = bool_arg_re.match(b)
        if m is None:
            _logger.error('"{}" is not valid bool assignment'.format(b))
            return 1
        var_name = m.group(1)
        assignment = m.group(2)
        _logger.info('Adding extra param "{}" = {}'.format(var_name, assignment))
        if assignment == 'true':
            assignment_as_bool = True
        else:
            assert assignment == 'false'
            assignment_as_bool = False
        extra_kwargs[var_name] = assignment_as_bool

    try:
        _logger.info('Loading "{}"'.format(pargs.result_infos.name))
        result_infos = ResultInfo.loadRawResultInfos(pargs.result_infos)
        _logger.info('Loading "{}"'.format(pargs.ii_template.name))
        ii_template = ResultInfo.loadRawResultInfos(pargs.ii_template)
    except ResultInfo.ResultInfoValidationError as e:
        _logger.error('Validation error:\n{}'.format(e))
        return 1
    _logger.info('Loading done')

    # Do grouping
    _logger.info('Performing merge')
    result_info_list = [ result_infos, ii_template ]
    key_to_result_infos, rejected_result_infos = ResultInfoUtil.group_result_infos_by(result_info_list)
    list_was_empty = True
    for index, reject_list in enumerate(rejected_result_infos):
        for reject in reject_list:
            list_was_empty = False
            key = ResultInfoUtil.get_result_info_key(reject)
            _logger.info('{} was rejected'.format(key))
    if not list_was_empty:
        return 1
    _logger.info('Merge complete')

    runner = result_infos['misc']['runner']
    _logger.info('Found runner "{}"'.format(runner))
    backend = None
    if 'backend' in result_infos['misc']:
        backend = result_infos['misc']['backend']
    _logger.info('Backend was "{}"'.format(backend))

    output_ri = {
        'results': [],
        'schema_version': result_info_list[0]['schema_version'],
    }

    event_analyser = event_analysis.get_event_analyser_from_runner_name(
        runner,
        soft_timeout=pargs.timeout,
        use_dsoes_wallclock_time=pargs.use_dsoes_wallclock_time,
        **extra_kwargs)
    tag_to_keys = dict()
    non_trivial_known_tags = {
        'jfs_generic_unknown',
        'timeout',
        'soft_timeout',
        'jfs_dropped_stdout_bug_unknown',
        'unsupported_bv_sort',
        'unsupported_fp_sort',
        'unsupported_sorts',
    }
    trivial_known_tags = {
        'sat',
        'jfs_dropped_stdout_bug_sat',
        'jfs_dropped_stdout_bug_unsat',
        'unsat',
    }
    trivial_keys = set()
    non_trivial_keys = set()
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
        # The assumption here is that we are using JFS is dummy solving
        # mode. Benchmarks that aren't sat are non-trivial and so we should
        # annotate as such.
        is_trivial = False
        if tag in trivial_known_tags:
            is_trivial = True
            trivial_keys.add(key)
        else:
            if tag not in non_trivial_known_tags:
                _logger.error('Unsupported tag {} for {}'.format(tag, key))
                return 1
            non_trivial_keys.add(key)
        corresponding_ri = key_to_result_infos[key][1].copy()
        corresponding_ri['is_trivial'] = is_trivial
        output_ri['results'].append(corresponding_ri)

    _logger.info('# of trivial benchmarks: {}'.format(len(trivial_keys)))
    _logger.info('# of non-trivial benchmarks: {}'.format(len(non_trivial_keys)))

    # Validate against schema
    try:
        _logger.info('Validating result_infos')
        ResultInfo.validateResultInfos(output_ri)
    except ResultInfo.ResultInfoValidationError as e:
        _logger.error('Validation error:\n{}'.format(e))
        return 1
    _logger.info('Validation complete')


    smtrunner.util.writeYaml(pargs.output, output_ri)

    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
