#!/usr/bin/env python
# Copyright (c) 2017, Daniel Liew
# This file is covered by the license in LICENSE.txt
# vim: set sw=4 ts=4 softtabstop=4 expandtab:
"""
Read a result info file and try to count event types.
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
        use_dsoes_wallclock_time=pargs.use_dsoes_wallclock_time,
        **extra_kwargs)
    tag_to_keys = dict()
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
        # Record tag
        try:
            cur_set = tag_to_keys[tag]
            cur_set.add(key)
        except KeyError:
            tag_to_keys[tag] = { key }

    # Dump tags
    print("")
    print("TAG COUNTS")
    for tag_name, keys in sorted(tag_to_keys.items(), key= lambda k: k[0]):
        print("{}: {}".format(tag_name, len(keys)))
    # Dump requested tags
    for tag_name in pargs.dump_tags:
        if tag_name in tag_to_keys:
            print("{}: \n{}".format(tag_name, pprint.pformat(tag_to_keys[tag_name])))
        else:
            _logger.error('Tag "{}" not present'.format(tag_name))
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
