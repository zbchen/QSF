#!/usr/bin/env python
# Copyright (c) 2017, Daniel Liew
# This file is covered by the license in LICENSE.txt
# vim: set sw=4 ts=4 softtabstop=4 expandtab:
"""
Read multiple result info files and merge them
"""
from load_smtrunner import add_smtrunner_to_module_search_path
add_smtrunner_to_module_search_path()
from smtrunner import ResultInfo, DriverUtil, ResultInfoUtil
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



def main(args):
    global _logger
    parser = argparse.ArgumentParser(description=__doc__)
    DriverUtil.parserAddLoggerArg(parser)
    parser.add_argument('result_infos',
                        type=argparse.FileType('r'),
                        nargs='+')
    parser.add_argument('--wd-bases', type=str, default=[], nargs='+')
    parser.add_argument('--allow-merge-failures',
        dest='allow_merge_failures',
        default=False,
        action='store_true',
    )
    parser.add_argument('-o', '--output',
                        type=argparse.FileType('w'),
                        default=sys.stdout,
                        help='Output location (default stdout)')

    pargs = parser.parse_args(args)
    DriverUtil.handleLoggerArgs(pargs, parser)
    _logger = logging.getLogger(__name__)

    if len(pargs.wd_bases) > 0:
        if len(pargs.wd_bases) != len(pargs.result_infos):
            _logger.error(
                'Number of working directory bases must = number of result info files')
            return 1
        for wd_base in pargs.wd_bases:
            if not os.path.exists(wd_base):
                _logger.error('"{}" does not exist'.format(wd_base))
                return 1
            if not os.path.isdir(wd_base):
                _logger.error('"{}" is not a directory'.format(wd_base))
                return 1
            if not os.path.isabs(wd_base):
                _logger.error('"{}" must be an absolute path'.format(wd_base))
                return 1

    index_to_raw_result_infos = []

    for index, result_infos_file in enumerate(pargs.result_infos):
        try:
            _logger.info('Loading "{}"'.format(result_infos_file.name))
            result_infos = ResultInfo.loadRawResultInfos(result_infos_file)
            index_to_raw_result_infos.append(result_infos)
        except ResultInfo.ResultInfoValidationError as e:
            _logger.error('Validation error:\n{}'.format(e))
            return 1
        _logger.info('Loading done')
    result_infos = None

    # HACK: Do something smarter here
    merged = {
        'misc' : {
            'runner': index_to_raw_result_infos[0]['misc']['runner'],
        },
        'results': [ ],
        'schema_version': index_to_raw_result_infos[0]['schema_version'],
    }

    # Perform grouping by benchmark name
    key_to_results_infos, rejected_result_infos = ResultInfoUtil.group_result_infos_by(
            index_to_raw_result_infos)
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


    merged_key_result_info, merge_failures = ResultInfoUtil.merge_raw_result_infos(
        key_to_results_infos,
        allow_merge_errors=False,
        wd_bases=pargs.wd_bases if len(pargs.wd_bases) > 0 else None)
    if len(merge_failures) > 0:
        _logger.error('There were merge failures')
        return 1
    # TODO: sort by key
    for key, merged_result in sorted(merged_key_result_info.items()):
        merged['results'].append(merged_result)

    # Validate against schema
    try:
        _logger.info('Validating result_infos')
        ResultInfo.validateResultInfos(merged)
    except ResultInfo.ResultInfoValidationError as e:
        _logger.error('Validation error:\n{}'.format(e))
        return 1
    _logger.info('Validation complete')

    smtrunner.util.writeYaml(pargs.output, merged)
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
