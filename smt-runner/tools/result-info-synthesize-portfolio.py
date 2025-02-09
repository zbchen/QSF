#!/usr/bin/env python
# Copyright (c) 2017, Daniel Liew
# This file is covered by the license in LICENSE.txt
# vim: set sw=4 ts=4 softtabstop=4 expandtab:
"""
Read multiple result info files and synthesize a theoretical
portfolio solver
"""
from load_smtrunner import add_smtrunner_to_module_search_path
add_smtrunner_to_module_search_path()
from smtrunner import ResultInfo, DriverUtil, ResultInfoUtil, analysis
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
import copy

_logger = None

def strip(prefix, path):
    if prefix == "":
        return path
    if path.startswith(prefix):
        return path[len(prefix):]


def main(args):
    global _logger
    global _fail_count
    parser = argparse.ArgumentParser(description=__doc__)
    DriverUtil.parserAddLoggerArg(parser)
    parser.add_argument('result_infos',
                        type=argparse.FileType('r'),
                        nargs='+')
    parser.add_argument('--names', nargs='+')
    parser.add_argument('--base', type=str, default="")
    parser.add_argument('--allow-merge-failures',
        dest='allow_merge_failures',
        default=False,
        action='store_true',
    )
    parser.add_argument('--no-rank-unknown',
        dest='no_rank_unknown',
        default=False,
        action='store_true',
    )
    parser.add_argument('--dump-wins',
        dest='dump_wins',
        default=False,
        action='store_true',
    )
    parser.add_argument('--max-exec-time',
        default=None,
        type=float,
        dest='max_exec_time',
    )
    parser.add_argument('-o', '--output',
                        type=argparse.FileType('w'),
                        default=sys.stdout,
                        help='Output location (default stdout)')

    pargs = parser.parse_args(args)
    DriverUtil.handleLoggerArgs(pargs, parser)
    _logger = logging.getLogger(__name__)

    if not pargs.no_rank_unknown and pargs.max_exec_time is None:
        _logger.error('Max time must be specified')
        return 1

    if pargs.names is None:
        _logger.error('--names must be specified')
        return 1
    if len(pargs.names) != len(pargs.result_infos):
        _logger.error('Number of names must match number of result info files')
        return 1

    index_to_name = pargs.names

    index_to_raw_result_infos = []
    index_to_file_name = []
    index_to_wins = []
    for index, result_infos_file in enumerate(pargs.result_infos):
        try:
            _logger.info('Loading "{}"'.format(result_infos_file.name))
            result_infos = ResultInfo.loadRawResultInfos(result_infos_file)
            index_to_raw_result_infos.append(result_infos)
            index_to_file_name.append(result_infos_file.name)
            index_to_wins.append(set())
        except ResultInfo.ResultInfoValidationError as e:
            _logger.error('Validation error:\n{}'.format(e))
            return 1
        _logger.info('Loading done')
    result_infos = None

    # Perform grouping by benchmark name
    key_to_results_infos, rejected_result_infos = ResultInfoUtil.group_result_infos_by(
            index_to_raw_result_infos)
    if len(rejected_result_infos) > 0:
        _logger.warning('There were rejected result infos')
        num_merge_failures = 0
        for index, l in enumerate(rejected_result_infos):
            _logger.warning('Index {} had {} rejections'.format(index, len(l)))
            num_merge_failures += len(l)
        if num_merge_failures > 0:
            if pargs.allow_merge_failures:
                _logger.warning('Merge failures being allowed')
            else:
                _logger.error('Merge failures are not allowed')
                return 1

    # HACK: Do something smarter here
    merged = {
        'misc' : {
            'runner': index_to_raw_result_infos[0]['misc']['runner'],
            'synthesized_from': index_to_name,
        },
        'results': [ ],
        'schema_version': index_to_raw_result_infos[0]['schema_version'],
    }


    failed_to_rank=set()
    for key, raw_result_info_list in sorted(key_to_results_infos.items(), key=lambda kv:kv[0]):
        _logger.info('Ranking on "{}" : '.format(key))
        indices_to_use = []
        # Compute indices to use
        modified_raw_result_info_list = [ ]

        # Handle "unknown"
        # Only compare results that gave sat/unsat
        for index, ri in enumerate(raw_result_info_list):
            sat, _ = analysis.get_sat_from_result_info(ri)
            _logger.info('index {} {}'.format(index, sat))
            if sat != 'unknown':
                indices_to_use.append(index)
                modified_raw_result_info_list.append(ri)
            else:
                if pargs.no_rank_unknown:
                    # Legacy
                    modified_raw_result_info_list.append(ri)
                    _logger.debug('Not using index {} for {} due to unknown'.format(
                        index,
                        key))
                else:
                    modified_ri = analysis.get_result_with_modified_time(
                        ri,
                        pargs.max_exec_time)
                    _logger.debug('modified_ri: {}'.format(pprint.pformat(modified_ri)))
                    _logger.debug('Treating index {} for {} due to unknown as having max-time'.format(
                        index,
                        key))
                    indices_to_use.append(index)
                    modified_raw_result_info_list.append(modified_ri)
        _logger.debug('used indices_to_use: {}'.format(indices_to_use))

        def append_result(winner_index):
            rank_failure = False
            if winner_index is None:
                # Failure
                rank_failure = True
                # Just use firtst
                winner_index = 0
            copied_result = copy.deepcopy(raw_result_info_list[winner_index])
            copied_result['rank_failure'] = rank_failure
            copied_result['rank_winner'] = index_to_name[winner_index]
            merged['results'].append(copied_result)

        if len(indices_to_use) == 0:
            # Can't rank
            failed_to_rank.add(key)
            append_result(None)
            continue

        ranked_indices, ordered_bounds = analysis.rank_by_execution_time(
            modified_raw_result_info_list,
            indices_to_use,
            pargs.max_exec_time,
            analysis.get_arithmetic_mean_and_99_confidence_intervals,
            ['dsoes_wallclock', 'wallclock'])
        _logger.info('Ranking on "{}" : {}'.format(key, ranked_indices))
        _logger.info('Ranking on "{}" : {}'.format(key, ordered_bounds))
        # Record win
        if len(ranked_indices[0]) == 1:
            # Winner
            winner_index = ranked_indices[0][0]
            _logger.info('Recorded win for {}'.format(
                index_to_file_name[winner_index]))
            index_to_wins[winner_index].add(key)
            append_result(winner_index)
        else:
            failed_to_rank.add(key)
            append_result(None)

    # Report wins
    for index, winner_key_set in enumerate(index_to_wins):
        name = index_to_file_name[index]
        print("# of wins for {}: {}".format(name, len(winner_key_set)))
        if pargs.dump_wins:
            print(pprint.pformat(sorted(list(winner_key_set))))
        win_key = 'rank_wins_for_{}'.format(index_to_name[index])
        merged['misc'][win_key] = len(winner_key_set)
    print("# failed to rank: {}".format(len(failed_to_rank)))
    merged['misc']['num_fail_to_rank'] = len(failed_to_rank)

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
