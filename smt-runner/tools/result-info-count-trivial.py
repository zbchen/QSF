#!/usr/bin/env python
# Copyright (c) 2017, Daniel Liew
# This file is covered by the license in LICENSE.txt
# vim: set sw=4 ts=4 softtabstop=4 expandtab:
"""
Read a result info files and count the counts for the `is_trivial` key
"""
from load_smtrunner import add_smtrunner_to_module_search_path
add_smtrunner_to_module_search_path()
from smtrunner import ResultInfo, DriverUtil, analysis

import argparse
import logging
import os
import pprint
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
                        nargs='?',
                        default=sys.stdin)

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

    trivial_count = {
        'trivial': 0,
        'non_trivial': 0,
        'unknown': 0,
        'total': 0,
    }

    numMergeConflicts = 0
    isMergedResult = False
    for r in result_infos['results']:
        trivial_count['total'] += 1
        if 'is_trivial' not in r:
            trivial_count['unknown'] += 1
            continue
        is_trivial = r['is_trivial']
        assert isinstance(is_trivial, bool)
        if is_trivial:
            trivial_count['trivial'] += 1
        else:
            trivial_count['non_trivial'] += 1

    print(trivial_count)
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
