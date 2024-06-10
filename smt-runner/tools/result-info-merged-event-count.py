#!/usr/bin/env python
# Copyright (c) 2017, Daniel Liew
# This file is covered by the license in LICENSE.txt
# vim: set sw=4 ts=4 softtabstop=4 expandtab:
"""
Read a result info files and report their merged `event_tag` field1
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

def get_indices_with_tag(tag, tag_list):
    indices = set()
    for index, t in enumerate(tag_list):
        if t == tag:
            indices.add(index)
    return indices

def find_conflicts(tags_for_key):
    assert isinstance(tags_for_key, list)
    assert all([ isinstance(tag, str) for tag in tags_for_key])
    sat_indices = get_indices_with_tag('sat', tags_for_key)
    unsat_indices = get_indices_with_tag('unsat', tags_for_key)
    unsat_but_expected_sat_indices = get_indices_with_tag(
        'unsat_but_expected_sat', tags_for_key)
    sat_but_expected_unsat_indices = get_indices_with_tag(
        'sat_but_expected_unsat', tags_for_key)
    conflicting_indices = set()
    if len(sat_indices) > 0:
        if len(unsat_indices) > 0 or len(unsat_but_expected_sat_indices) > 0:
            conflicting_indices.update(sat_indices)
            conflicting_indices.update(unsat_indices)
            conflicting_indices.update(unsat_but_expected_sat_indices)
    if len(unsat_indices) > 0:
        if len(sat_but_expected_unsat_indices) > 0 or len(sat_indices) > 0:
            conflicting_indices.update(unsat_indices)
            conflicting_indices.update(sat_indices)
            conflicting_indices.update(sat_but_expected_unsat_indices)
    return conflicting_indices

def main(args):
    global _logger
    parser = argparse.ArgumentParser(description=__doc__)
    DriverUtil.parserAddLoggerArg(parser)
    parser.add_argument('result_infos',
                        type=argparse.FileType('r'),
                        nargs='+')
    parser.add_argument('--dump-tags',
        dest="dump_tags",
        nargs='+',
        default=[],
    )
    parser.add_argument('--dump-corresponding-tags',
        dest="dump_corresponding_tags",
        action='store_true',
        default=False,
    )
    parser.add_argument('--allow-merge-failures',
        action='store_true',
        default=False,
    )
    parser.add_argument('--only-report-conflicts-for-expected-unknown',
        dest='only_report_conflicts_for_expected_unknown',
        action='store_true',
        default=False,
    )
    parser.add_argument('--no-rebase-paths',
        dest='no_rebase_paths',
        action='store_true',
        default=False,
    )
    parser.add_argument('--indices-to-use-for-conflict-check',
        dest='indices_to_use_for_conflict_check',
        type=int,
        nargs='+',
        default=[],
        help='By default all indices are used',
    )
    parser.add_argument('--index-for-compute-sets',
        dest='index_for_compute_sets',
        type=int,
        default=None,
    )

    pargs = parser.parse_args(args)
    DriverUtil.handleLoggerArgs(pargs, parser)
    _logger = logging.getLogger(__name__)

    if len(pargs.indices_to_use_for_conflict_check) == 0:
        indices_to_use_for_conflict_check = list(range(0, len(pargs.result_infos)))
    else:
        indices_to_use_for_conflict_check = pargs.indices_to_use_for_conflict_check
    for i in indices_to_use_for_conflict_check:
        if i >= len(pargs.result_infos):
            _logger.error('Index {} is invalid. Must be < {}'.format(i, len(pargs.result_infos)))
            return 1

    if pargs.index_for_compute_sets is not None:
        if pargs.index_for_compute_sets >= len(pargs.result_infos):
            _logger.error('Index {} for compute sets is invalid. Must be < {}'.format(
                pargs.index_for_compute_sets, len(pargs.result_infos)))
            return 1


    index_to_raw_result_infos = []
    index_to_file_name = []
    index_to_tag_to_key_map = []
    index_to_keys_with_mixed_tags = []
    for of in pargs.result_infos:
        try:
            _logger.info('Loading "{}"'.format(of.name))
            result_infos = ResultInfo.loadRawResultInfos(of)
            index_to_raw_result_infos.append(result_infos)
            index_to_file_name.append(of.name)
            index_to_tag_to_key_map.append(dict())
            index_to_keys_with_mixed_tags.append(set())
        except ResultInfo.ResultInfoValidationError as e:
            _logger.error('Validation error:\n{}'.format(e))
            return 1
    _logger.info('Loading done')

    if not pargs.no_rebase_paths:
        index_to_file_name = ResultInfoUtil.rebase_paths_infer(index_to_file_name)

    for value in indices_to_use_for_conflict_check:
        _logger.info('Using {} for conflict checks'.format(index_to_file_name[value]))

    # Group result infos by benchmark name
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

    # Now collect tags
    keys_to_indices_that_conflict = dict()
    _logger.info('Found {} benchmarks'.format(len(key_to_results_infos.keys())))
    for key, ris in key_to_results_infos.items():
        tags_for_key = [ ]
        for index, ri in enumerate(ris):
            tags = ri['event_tag']
            _logger.debug('For {} : {} got {}'.format(
                key,
                index_to_file_name[index],
                tags)
            )
            if isinstance(tags, list):
                # Merged result
                try:
                    merged_tag, tags_were_mixed = event_analysis.merge_aggregate_events(tags)
                    if tags_were_mixed:
                        index_to_keys_with_mixed_tags[index].add(key)
                except event_analysis.MergeEventFailure as e:
                    _logger.error('Failed to merge events {} for benchmark {} for {}'.format(
                        tags,
                        key,
                        index_to_file_name[index])
                    )
                    raise e
            else:
                # Single result
                assert isinstance(tags, str)
                merged_tag = tags
                tags_were_mixed = False
            # Record the tag
            if index in indices_to_use_for_conflict_check:
                tags_for_key.append(merged_tag)
            else:
                tags_for_key.append('')
            try:
                index_to_tag_to_key_map[index][merged_tag].add(key)
            except KeyError:
                index_to_tag_to_key_map[index][merged_tag] = { key }
        # Now look at the reported tags and check for conflicts
        conflicting_indices = find_conflicts(tags_for_key)
        if len(conflicting_indices) > 0:
            if ris[0]['expected_sat'] != 'unknown' and pargs.only_report_conflicts_for_expected_unknown:
                _logger.warning('Skipping found conflict for {}'.format(key))
                continue
            keys_to_indices_that_conflict[key] = conflicting_indices
            _logger.warning(
                    'Found conflict for benchmark {} with:\ntags:{}\nnames:\n{}\n'.format(
                    key,
                    [ tags_for_key[i] for i in conflicting_indices],
                    [ index_to_file_name[i] for i in conflicting_indices])
            )

    # Now report tags
    print("Found {} conflicting benchmarks".format(
        len(keys_to_indices_that_conflict.keys())))
    for index, tag_to_key_map in enumerate(index_to_tag_to_key_map):
        report(
            index,
            index_to_file_name,
            tag_to_key_map,
            index_to_keys_with_mixed_tags[index],
            key_to_results_infos,
            pargs.dump_corresponding_tags,
            pargs.dump_tags,
        )

    # Now reports sets
    if pargs.index_for_compute_sets is not None:
        report_sets_for_index(
            pargs.index_for_compute_sets,
            index_to_tag_to_key_map,
            index_to_file_name,
            set(key_to_results_infos.keys()))
    return 0

def gqtp(thing_set, universal_set):
    """
    Get quantity to print
    """
    assert isinstance(thing_set, set)
    assert isinstance(universal_set, set)
    return "{} / {} ({:.2%})".format(
        len(thing_set),
        len(universal_set),
        float(len(thing_set))/len(universal_set))

def report_sets_for_index(index, index_to_tag_to_key_map, index_to_file_name, all_benchmarks):
    assert isinstance(index, int)
    print("#"*80)
    print("#"*80)
    print("# Benchmark sets for {} ".format(index_to_file_name[index]))
    all_tags = { 'sat', 'unsat', 'unsat_but_expected_sat'}

    for tag in sorted(all_tags):
        # compute sets
        indexes_benchmarks = set(index_to_tag_to_key_map[index].get(tag, set()))
        print("Tag : {}".format(tag))
        print("# of benchmarks with tag {} for {}: {}".format(
            tag,
            index_to_file_name[index],
            gqtp(indexes_benchmarks, all_benchmarks)))
        global_intersection = None
        global_only_index = None
        global_only_in_others = None
        global_neither = None
        for other_index in filter(lambda i: i != index ,range(0, len(index_to_tag_to_key_map))):
            other_indexes_benchmarks = set(index_to_tag_to_key_map[other_index].get(tag, set()))
            print("  # of benchmarks with tag {} for {}: {}".format(
                tag,
                index_to_file_name[other_index],
                gqtp(other_indexes_benchmarks, all_benchmarks)))

            # Intersection
            benchmark_intersection = indexes_benchmarks.intersection(other_indexes_benchmarks)
            print("  # Intersection: {}".format(
                gqtp(benchmark_intersection, all_benchmarks)))
            if global_intersection is None:
                global_intersection = benchmark_intersection.copy()
            else:
                # The semantics are subtle here. What we do is a union of the 
                # intersections rather than an intersection of the intersections.
                # For the latter the values won't add up the number of benchmarks
                #global_intersection.intersection_update(benchmark_intersection)
                global_intersection.update(benchmark_intersection)

            # Set difference
            only_index = indexes_benchmarks.difference(other_indexes_benchmarks)
            if global_only_index is None:
                global_only_index = only_index.copy()
            else:
                global_only_index.difference_update(other_indexes_benchmarks)
            print("  # only in {}: {}".format(
                index_to_file_name[index],
                gqtp(only_index, all_benchmarks)))

            # Set difference
            only_other_index = other_indexes_benchmarks.difference(indexes_benchmarks)
            print("  # only in {}: {}".format(
                index_to_file_name[other_index],
                gqtp(only_other_index, all_benchmarks)))
            if global_only_in_others is None:
                global_only_in_others = only_other_index.copy()
            else:
                global_only_in_others.update(only_other_index)

            # Complement of union
            neither_indices = all_benchmarks.difference(indexes_benchmarks)
            neither_indices.difference_update(other_indexes_benchmarks)
            print("  # with neither: {}".format(
                gqtp(neither_indices, all_benchmarks)))
            if global_neither is None:
                global_neither = neither_indices.copy()
            else:
                global_neither.difference_update(other_indexes_benchmarks)

            # Sanity check
            assert len(benchmark_intersection) + len(only_index) + len(only_other_index) + len(neither_indices) == len(all_benchmarks)
            print()
        print("  Global intersection: {}".format(
            gqtp(global_intersection, all_benchmarks)))
        print("  Global only in {}: {}".format(
            index_to_file_name[index],
            gqtp(global_only_index, all_benchmarks)))
        print("  Global only in all others: {}".format(
            gqtp(global_only_in_others, all_benchmarks)))
        print("  Global neither: {}".format(
            gqtp(global_neither, all_benchmarks)))
        assert len(global_intersection.intersection(global_only_index)) == 0
        assert len(global_intersection.intersection(global_only_in_others)) == 0
        assert len(global_intersection.intersection(global_neither)) == 0
        assert len(global_only_index.intersection(global_only_in_others)) == 0
        assert len(global_only_index.intersection(global_neither)) == 0
        assert len(global_only_in_others.intersection(global_neither)) == 0
        assert len(global_intersection) + len(global_only_index) + len(global_only_in_others) + len(global_neither) == len(all_benchmarks)

def report(index, index_to_file_name, tag_to_key_map, keys_with_mixed_tags, key_to_results_infos, dump_corresponding_tags, dump_tags=[], width=80):
    ri_name = index_to_file_name[index]
    print("#"*width)
    print(ri_name)
    print("")
    # print all tag counts
    for tag, keys_with_same_tag in sorted(tag_to_key_map.items(), key= lambda p: p[0]):
        print(" # of {}: {}".format(tag, len(keys_with_same_tag)))
        if tag == 'sat':
            # Report number for each expected sat label
            for expected_sat_to_consider in {'sat', 'unsat', 'unknown'}:
                # count number with expected_sat_to_consider
                key_with_same_tag_and_expected_sat = set(filter(
                    lambda k: key_to_results_infos[k][index]['expected_sat'] == expected_sat_to_consider,
                    keys_with_same_tag))
                print("  # where expected sat is {}: {}".format(expected_sat_to_consider, len(key_with_same_tag_and_expected_sat)))
        if tag in dump_tags:
            keys_with_same_tag_sorted = sorted(list(keys_with_same_tag))
            print("TAG {}".format(tag))
            for key in keys_with_same_tag_sorted:
                print("{} : expected_sat: {}".format(pprint.pformat(key), key_to_results_infos[key][index]['expected_sat']))
                if dump_corresponding_tags:
                    for other_index, fname in enumerate(index_to_file_name):
                        if other_index == index:
                            continue
                        other_ri_name = index_to_file_name[other_index]
                        other_tags = key_to_results_infos[key][other_index]['event_tag']
                        merged_other_tags, _ = event_analysis.merge_aggregate_events(other_tags)
                        print("  {} => {}".format(other_ri_name, merged_other_tags))

    print()

    # For convenience report a general 'unknown' aggreate
    tags_used_for_unknown_agg = set()
    skip_tags = {'sat', 'unsat', 'unsat_but_expected_sat', 'sat_but_expected_unsat'}
    unknown_agg = set()
    for tag, keys_with_same_tag in tag_to_key_map.items():
        if tag in skip_tags:
            continue
        tags_used_for_unknown_agg.add(tag)
        unknown_agg.update(keys_with_same_tag)
    print(" # of aggreate unknowns: {}".format(len(unknown_agg)))
    print("")
    print("The aggreagate unknown uses the following tags: {}".format(
        tags_used_for_unknown_agg))

    if len(keys_with_mixed_tags) > 0:
        print("# of benchmark with mixed tags: {}".format(len(keys_with_mixed_tags)))
        print()

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
