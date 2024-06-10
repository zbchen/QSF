#!/usr/bin/env python
# Copyright (c) 2017, Daniel Liew
# This file is covered by the license in LICENSE.txt
# vim: set sw=4 ts=4 softtabstop=4 expandtab:
"""
Read a result info files and perform selection using a histogram.
"""
from load_smtrunner import add_smtrunner_to_module_search_path
add_smtrunner_to_module_search_path()
from smtrunner import ResultInfo, DriverUtil, ResultInfoUtil
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

class HistogramBin:
    def __init__(self, minValue, maxValue):
        self._used_keys = set()
        # We use a list to get deterministic selection
        self.keys = []
        # Range in [minValue, maxValue)
        self.minValue = minValue
        self.maxValue = maxValue
        _logger.debug('Creating {}'.format(self.getID()))

    def getID(self):
        return "HistogramBin[{},{})".format(self.minValue, self.maxValue)

    def insertKey(self, key):
        _logger.debug('{} inserting {}'.format(self.getID(), key))
        assert key not in self._used_keys
        self.keys.append(key)
        self._used_keys.add(key)

    def getSize(self):
        return len(self.keys)

    def getKeys(self):
        return self._used_keys.copy()

    def getBounds(self):
        return (self.minValue, self.maxValue)

    def getRandomKey(self, remove_item=True):
        key = random.sample(self.keys, 1)[0]
        if remove_item is True:
            _logger.debug('Removing {}'.format(key))
            self.keys.remove(key)
        return key

class HistogramStateMachine:
    def __init__(self, result_infos, bin_width, max_time, key_fn=None):
        self.bin_width = bin_width
        self.max_time = max_time
        # Maps tuple (minValue, maxValue) to HistogramBin
        self.range_to_bin = {}
        for r in sorted(result_infos, key=key_fn):
            t = r['wallclock_time']
            bin_tup = self.time_to_bin_tuple(t)
            bin = None
            if bin_tup not in self.range_to_bin:
                # Create bin if it doesn't already exist
                bin = HistogramBin(bin_tup[0], bin_tup[1])
                self.range_to_bin[bin_tup] = bin
            else:
                bin = self.range_to_bin[bin_tup]
            bin.insertKey(key_fn(r))
        # Create ordered bins
        self.bins = [ x for x in self.range_to_bin.values() ]
        self.bins.sort(key=lambda x: x.minValue)
        assert len(self.bins) == len(self.range_to_bin)
        _logger.info('Created {} bins'.format(len(self.bins)))

    def time_to_bin_tuple(self, time):
        lower_bound = min(math.floor(time), self.max_time)
        lower_bound = lower_bound // self.bin_width
        lower_bound *= self.bin_width
        upper_bound = lower_bound + self.bin_width
        _logger.debug('{} => [{},{})'.format(time, lower_bound, upper_bound))
        return (lower_bound, upper_bound)

    def getNextRandBin(self, remove_item=True):
        """
            Get next element from available bin.
            The bin is picked at random and then an item
            from the bin is picked at random.
        """
        if len(self.bins) == 0:
            return None

        # Pick random bin
        bin_index = random.randrange(len(self.bins))
        _logger.debug('Picked random bin index {} in range [0,{})'.format(
            bin_index,
            len(self.bins)))

        selected_bin = self.bins[bin_index]
        # Pick random key
        selected_key = selected_bin.getRandomKey(remove_item=remove_item)
        _logger.debug('Picked "{}"'.format(selected_key))
        if selected_bin.getSize() == 0:
            # Bin is now empty so remove it from list of available bins
            _logger.debug('Bin {} now empty. Removing'.format(selected_bin.getID()))
            self.bins.pop(bin_index)
        return selected_key

    def getNext(self, remove_item=True):
        """
            Get next element from available bin.
            The element is picked at random but is
            weighted such that small bins are much more likely
            to be picked than large bins
        """
        if len(self.bins) == 0:
            return None

        bin_counts = []
        max_size = 0 # The largest bin
        for bin in self.bins:
            count = bin.getSize()
            assert count > 0
            bin_counts.append(count)
            if count > max_size:
                max_size = count
        _logger.debug('Bin counts:\n{}'.format(pprint.pformat(bin_counts)))

        # Compute scaled probabilities. The probability is proportional to
        # 1/(size of bin). `max_size` is used as a scaling factor to try to
        # avoid small values
        scaled_probabilities = list(map(lambda x: float(max_size)/x, bin_counts))
        _logger.debug('Scaled probs:\n{}'.format(pprint.pformat(scaled_probabilities)))
        sum_of_probabilities = sum(scaled_probabilities)

        # Compute random (uniform) number in range [0, sum_of_probabilities]
        num = random.uniform(0.0, sum_of_probabilities)
        _logger.debug('Generating random number ({}) in range [0, {}]'.format(num, sum_of_probabilities))

        # FIXME: This is really naive. Just walk through
        lower_b = 0.0
        found_index = -1
        for index, scaled_prob in enumerate(scaled_probabilities):
            upper_b = lower_b + scaled_prob
            if lower_b <= num and num < upper_b:
                found_index = index
                break
            lower_b = upper_b
        if found_index == -1 and num == scaled_probabilities:
            # Handle edge case
            found_index = len(self.bins) - 1
        assert found_index != -1
        selected_bin = self.bins[found_index]
        _logger.debug('Picked bin with index {} with size {}'.format(found_index, selected_bin.getSize()))
        selected_key = selected_bin.getRandomKey(remove_item=remove_item)
        _logger.debug('Picked "{}"'.format(selected_key))
        if selected_bin.getSize() == 0:
            # Bin is now empty so remove it from list of available bins
            _logger.debug('Bin {} now empty. Removing'.format(selected_bin.getID()))
            self.bins.pop(found_index)
        return selected_key

def main(args):
    global _logger
    parser = argparse.ArgumentParser(description=__doc__)
    DriverUtil.parserAddLoggerArg(parser)
    parser.add_argument('result_infos',
                        type=argparse.FileType('r'),
                        nargs='+')
    parser.add_argument('--bin-width',
        type=int,
        default=5,
        dest='bin_width',
        help='Histogram bin width in seconds (default %(default)s)',
    )
    parser.add_argument('--use-result-with-index',
        dest='use_result_with_index',
        default=-1,
        help='When outputting result info pick the result info for the benchmark from specified index. If -1 then pick from the relevant result info',
    )
    parser.add_argument('--max-time',
        type=int,
        default=120,
        dest='max_time',
        help='Assumed max time is seconds (default %(default)s)',
    )
    parser.add_argument('--random-seed',
                        type=int,
                        default=0,
                        dest='random_seed')
    parser.add_argument('--bound',
        type=int,
        default=100,
        help='Maximum number of benchmarks to gather (default %(default)s)',
    )
    parser.add_argument('--keep-on-pick',
        dest='keep_on_pick',
        help='When selecting benchmark keep it in histogram',
        default=False,
        action='store_true',
    )
    parser.add_argument('--selection-mode',
        dest='selection_mode',
        default='inv_height_probability',
        choices=['inv_height_probability', 'rand_bin'],
    )
    parser.add_argument('--seed-selection-from',
        dest='seed_selection_from',
        default=None,
        help='Seed selected benchmarks from supplied invocation info file'
    )
    parser.add_argument('-o', '--output',
                        type=argparse.FileType('w'),
                        default=sys.stdout,
                        help='Output location (default stdout)')
    parser.add_argument('--hack-check-bins-included-with-count-lt',
        type=int,
        dest='hack_check_bins_included_with_count_less_than',
        default=None
    )

    pargs = parser.parse_args(args)
    DriverUtil.handleLoggerArgs(pargs, parser)
    _logger = logging.getLogger(__name__)

    result_infos_list = []
    for of in pargs.result_infos:
        try:
            _logger.info('Loading "{}"'.format(of.name))
            result_infos = ResultInfo.loadRawResultInfos(of)
            result_infos_list.append(result_infos)
        except ResultInfo.ResultInfoValidationError as e:
            _logger.error('Validation error:\n{}'.format(e))
            return 1
    _logger.info('Loading done. Loaded {} result info files'.format(
        len(result_infos_list)))

    # Set random seed
    random.seed(pargs.random_seed)

    key_fn = ResultInfoUtil.get_result_info_key

    # Benchmarks to keep, this is used for checking if a HSM
    # has given us a benchmark we have already selected
    btk = set()
    btk_to_result_info_index = dict()

    if pargs.seed_selection_from:
        if not os.path.exists(pargs.seed_selection_from):
            _logger.error('{} does not exist'.format(
                pargs.seed_selection_from))
            return 1
        with open(pargs.seed_selection_from, 'r') as f:
            _logger.info('Seeding selection from {}'.format(
                f.name)
            )
            ris_for_seeding = ResultInfo.loadRawResultInfos(f)
            # Now pull keys from the the result info file
            for ri in ris_for_seeding['results']:
                if len(btk) >= pargs.bound:
                    _logger.info('Bound reached')
                    break
                key_for_ri = key_fn(ri)
                btk.add(key_for_ri)
                # HACK: Lie about the source
                btk_to_result_info_index[key_for_ri] = 0
            _logger.info('Seeded selection with {} benchmarks'.format(
                len(btk)))
            assert len(btk) == len(btk_to_result_info_index.keys())


    # Group
    key_to_result_infos, rejected_result_infos = ResultInfoUtil.group_result_infos_by(result_infos_list, key_fn=key_fn)
    if len(rejected_result_infos):
        for index, l in enumerate(rejected_result_infos):
            if len(l) > 0:
                _logger.error('Found rejected result infos:\n{}'.format(
                    pprint.pformat(rejected_result_infos)))
                return 1

    histogram_sms = []
    for result_infos in result_infos_list:
        histogram_sms.append(HistogramStateMachine(result_infos['results'], pargs.bin_width, pargs.max_time, key_fn))
    original_sms = histogram_sms.copy() # Shallow copy

    # HACK: Do check
    desirable_keys = set()
    if pargs.hack_check_bins_included_with_count_less_than:
        _logger.info('Doing hack - check bins with count less than {} are included'.format(pargs.hack_check_bins_included_with_count_less_than))
        assert pargs.hack_check_bins_included_with_count_less_than > 0
        # Walk through the bins and collect all keys where
        # bin count is less than the specified value.
        for hsm in histogram_sms:
            for bin in hsm.bins:
                if bin.getSize() < pargs.hack_check_bins_included_with_count_less_than:
                    _logger.info('Adding keys from bin {} to desirable keys'.format(
                        bin.getBounds()))
                    _logger.debug('Adding keys:\n{}'.format(pprint.pformat(bin.getKeys())))
                    desirable_keys.update(bin.getKeys())
        _logger.info('{} keys in set of desirable benchmarks'.format(
            len(desirable_keys)))


    # Keep picking round robin between the state machines until
    # a bound is reached.
    _logger.info('Beginning {} selection with bound of {} and seed of {} benchmarks'.format(
        pargs.selection_mode,
        pargs.bound,
        len(btk)))
    initialBtkSize = len(btk)
    while len(btk) < pargs.bound:
        if len(histogram_sms) == 0:
            _logger.warning('Exhausted all histogram SMs')
            break
        hsms_to_remove = set()
        # Go through sms in round robin order.
        for index, hsm in enumerate(histogram_sms):
            if len(btk) >= pargs.bound:
                # Don't allow bound to be exceeded.
                break
            benchmark_key = None
            while benchmark_key is None:
                # Based on selection mode pick a benchmark
                if pargs.selection_mode == 'inv_height_probability':
                    benchmark_key = hsm.getNext(remove_item=not pargs.keep_on_pick)
                elif pargs.selection_mode == 'rand_bin':
                    benchmark_key = hsm.getNextRandBin(remove_item=not pargs.keep_on_pick)
                else:
                    raise Exception('Unsupported selection mode')
                _logger.debug('Got key {}'.format(benchmark_key))
                if benchmark_key is None:
                    # hsm exhausted
                    _logger.debug('HSM index {} exhausted'.format(
                        index))
                    hsms_to_remove.add(index)
                    break
                if benchmark_key in btk:
                    _logger.debug('Already have key {}'.format(
                        benchmark_key))
                    # We already have this benchmark
                    # Try picking another.
                    benchmark_key = None
                    continue
            if benchmark_key is not None:
                _logger.debug('Adding key {}'.format(benchmark_key))
                assert benchmark_key not in btk_to_result_info_index
                assert benchmark_key not in btk
                btk_to_result_info_index[benchmark_key] = index
                btk.add(benchmark_key)
        if len(hsms_to_remove) > 0:
            new_hsms = []
            for index, hsm in enumerate(histogram_sms):
                if index not in hsms_to_remove:
                    _logger.debug('keeping HSM {}'.format(index))
                    new_hsms.append(hsm)
                else:
                    _logger.debug('dropping HSM {}'.format(index))
            histogram_sms = new_hsms
    _logger.info('Selected {} benchmarks'.format(
        len(btk) - initialBtkSize))
    _logger.info('Final selection has {} benchmarks'.format(
        len(btk)))
    assert len(btk) == len(btk_to_result_info_index)

    new_result_infos = {
        'results':[],
        'schema_version': 0,
    }
    new_results_list = new_result_infos['results']

    used_programs = set()
    # Grab the result info by key
    for key, result_info_index in sorted(btk_to_result_info_index.items(), key=lambda tup: tup[0]):
        # Just pick the first
        index_to_use = pargs.use_result_with_index
        if index_to_use == -1:
            # Use result info corresponding to the result info we took it from
            index_to_use = result_info_index
        _logger.debug('Selected key {} from result_info_index {}'.format(key, index_to_use))
        ri = key_to_result_infos[key][index_to_use]
        _logger.debug('Grabbed {}'.format(key_to_result_infos[key]))
        _logger.debug('Grabbed {}'.format(ri))
        new_results_list.append(ri)
        if key in used_programs:
            # Sanity check
            _logger.error(
                'Selected key ({}) that has already been used'.format(key))
            return 1
        used_programs.add(key)

    # HACK:
    if pargs.hack_check_bins_included_with_count_less_than:
        missing_desirable_benchmarks = desirable_keys.difference(
            set(btk_to_result_info_index.keys()))
        _logger.warning('{} desirable benchmarks missing from selection'.format(
            len(missing_desirable_benchmarks)
            ))
        if len(missing_desirable_benchmarks) > 0:
            _logger.error('Desirable {} benchmarks missing from selection:\n{}'.format(
                len(missing_desirable_benchmarks),
                pprint.pformat(missing_desirable_benchmarks))
                )
            return 1

    # Validate against schema
    try:
        _logger.info('Validating new_result_infos')
        ResultInfo.validateResultInfos(new_result_infos)
    except ResultInfo.ResultInfoValidationError as e:
        _logger.error('Validation error:\n{}'.format(e))
        return 1
    _logger.info('Validation complete')
    smtrunner.util.writeYaml(pargs.output, new_result_infos)
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
