#!/usr/bin/env python
# Copyright (c) 2017, Daniel Liew
# This file is covered by the license in LICENSE.txt
# vim: set sw=4 ts=4 softtabstop=4 expandtab:
"""
Read a result info files and count the counts for the `sat` key
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

    sat_count = {
        'sat': 0,
        'unsat': 0,
        'unknown': 0,
        'total': 0,
    }

    numMergeConflicts = 0
    isMergedResult = False
    for r in result_infos['results']:
        sat, hasMergeConflict = analysis.get_sat_from_result_info(r)
        sat_count['total'] += 1
        sat_count[sat] += 1
        if not isMergedResult:
            isMergedResult = analysis.is_merged_result_info(r)
        # Warn if merge conflict
        if hasMergeConflict:
            _logger.warning('Merge conflict for "{}"'.format(r['benchmark']))
            numMergeConflicts += 1
        # Warn if mis match
        expected_sat = r['expected_sat']
        if (sat == 'sat' and expected_sat == 'unsat') or (sat == 'unsat' and expected_sat == 'sat'):
            _logger.warning('Expected sat and result mismatch for "{}"'.format(r['benchmark']))
    print("Sat:\n", pprint.pformat(sat_count))

    if isMergedResult:
        _logger.info('Is merged result')
        _logger.info('# of merge conflicts: {}'.format(numMergeConflicts))
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
