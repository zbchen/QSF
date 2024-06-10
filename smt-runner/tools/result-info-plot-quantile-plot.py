#!/usr/bin/env python
# Copyright (c) 2017, Daniel Liew
# This file is covered by the license in LICENSE.txt
# vim: set sw=4 ts=4 softtabstop=4 expandtab:
"""
Generate quantile plot from one of more result infos
"""
from load_smtrunner import add_smtrunner_to_module_search_path
add_smtrunner_to_module_search_path()
from smtrunner import ResultInfo, DriverUtil, ResultInfoUtil, analysis, event_analysis
import smtrunner.util
import matplotlib.pyplot as plt

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

def round_away_from_zero_to_multiple_of(mult, value):
    assert mult > 0
    if value >= 0:
        temp = ( value + (mult -1)) / mult
        temp = math.floor(temp)
    else:
        temp = ( value - (mult -1)) / mult
        temp = math.ceil(temp)
    return int(temp) * mult


def strip(prefix, path):
    if prefix == "":
        return path
    if path.startswith(prefix):
        return path[len(prefix):]

class ResultInfoGenericScore:
    def __init__(self, *nargs, **kwargs):
        self._positive_results = []
        self._negative_results = []
        self._zero_results = []
        self.x_points = None
        self.y_points = None
        self.y_errors = None

    def addResults(self, ris):
        assert isinstance(ris, list)
        add_count = 0
        for ri in ris:
            score = self._compute_score(ri)
            if score == 0:
                self._zero_results.append(ri)
            elif score == 1:
                self._positive_results.append(ri)
            elif score == -1:
                self._negative_results.append(ri)
            else:
                raise Exception('Unsupport score {}'.format(score))
            add_count += 1
        _logger.info('Added {} benchmarks'.format(add_count))
        _logger.info('# {} positive benchmarks'.format(len(self._positive_results)))
        _logger.info('# {} negative benchmarks'.format(len(self._negative_results)))
        _logger.info('# {} zero score benchmarks'.format(len(self._zero_results)))

    @property
    def num_positive(self):
        return len(self._positive_results)

    @property
    def positive_results(self):
        return self._positive_results.copy()

    @property
    def num_negative(self):
        return len(self._negative_results)

    @property
    def negative_results(self):
        return self._negative_results.copy()

    @property
    def num_zero(self):
        return len(self._zero_results)

    @property
    def zero_results(self):
        return self._zero_results.copy()

    @property
    def x_label(self):
        return None

    @property
    def y_label(self):
        return None

    def _compute_score(self, ri):
        return None

    def _compute_points(self):
        return None
    
    def compute_points(self, **kwargs):
        """
            Compute points and store in
            .x_points
            .y_points
            .y_errors
            .point_index_to_benchmark_name_map
        """
        self.x_points = None
        self.y_points = None
        self.y_errors = None
        self.point_index_to_benchmark_name_map = None
        self.x_points, self.y_points, self.y_errors, self.point_index_to_benchmark_name_map = self._compute_points(**kwargs)

    @classmethod
    def do_global_compute_points(cls, index_to_ri_scores, **kwargs):
        assert isinstance(index_to_ri_scores, list)
        for ri_score in index_to_ri_scores:
            assert isinstance(ri_score, ResultInfoGenericScore)
        cls._do_global_compute_points(index_to_ri_scores, **kwargs)

    @classmethod
    def _do_global_compute_points(cls, index_to_ri_scores, **kwargs):
        """
            Perform compute points over a list of instances of
            ResultInfoGenericScore.
        """
        # This implementation doesn't do anything global.
        # Sub classes should override this if they need different
        # behaviour.
        for ri_scores in index_to_ri_scores:
            ri_scores.compute_points()

    def get_y_mean_bounds(self):
        """
            Return a tuple for the bounds of the arithmetic mean
            of the y-points, excluding the dummy point.
            (min_mean_y, mean_y, max_min_y)
        """
        assert isinstance(self.x_points, list)
        assert isinstance(self.y_points, list)
        assert isinstance(self.y_errors, list)
        y_values = self.y_points[1:]
        y_errors = [ self.y_errors[0][1:], self.y_errors[1][1:] ]
        num_values = len(y_values)
        assert num_values > 1
        assert len(y_values) == len(y_errors[0])
        assert len(y_values) == len(y_errors[1])
        assert all([ isinstance(y_point, float) for y_point in y_values])
        assert all([ y_point >= 0.0 for y_point in y_values])
        accum_mean_min = 0.0
        accum_mean = 0.0
        accum_mean_max = 0.0
        for index, y_point in enumerate(y_values):
            y_minus = y_errors[0][index]
            assert y_minus >= 0.0
            y_plus = y_errors[1][index]
            assert y_plus >= 0.0
            accum_mean += y_point/num_values
            accum_mean_min += (y_point - y_minus)/num_values
            accum_mean_max += (y_point + y_plus)/num_values
        return (accum_mean_min, accum_mean, accum_mean_max)

class ResultInfoFuzzingThroughputScores(ResultInfoGenericScore):
    def __init__(self):
        super(ResultInfoFuzzingThroughputScores, self).__init__()
        self._benchmark_name_to_ri_map = {}

    def addResults(self, ris):
        # Get parent class to do most of the work
        super(ResultInfoFuzzingThroughputScores, self).addResults(ris)

        # Now compute mapping
        for ri in ris:
            benchmark_name = ri['benchmark']
            assert benchmark_name != self._dummy_point_name
            assert benchmark_name not in self._benchmark_name_to_ri_map
            self._benchmark_name_to_ri_map[benchmark_name] = ri

    @property
    def x_label(self):
        return 'Accumulated score'

    @property
    def y_label(self):
        return 'Fuzzing throughput (num inputs/s)'

    @classmethod
    def _do_global_compute_points(cls, index_to_ri_scores, **kwargs):
        # Valid values: independent, max_score, max_throughput, max_mean_throughput
        point_ordering_mode = 'independent'
        try:
            point_ordering_mode = kwargs['point_ordering']
        except KeyError:
            pass

        # Compute each ri independently so we can figure out
        # which one we should use as the ordering guide.
        for ri_scores in index_to_ri_scores:
            ri_scores.compute_points(order_by=None)

        _logger.info('Using {} point ordering mode'.format(point_ordering_mode))
        if point_ordering_mode == 'independent':
            # Nothing left to do
            return
        benchmark_ordering = None
        if point_ordering_mode == 'max_score':
            index_with_max_score = None
            max_observed_score = None
            for index, ri_scores in enumerate(index_to_ri_scores):
                score = ri_scores.num_positive - ri_scores.num_negative
                if max_observed_score is None or score > max_observed_score:
                    index_with_max_score = index
                    max_observed_score = score
            _logger.info('Determined that index {} has max score of {}'.format(
                index_with_max_score,
                max_observed_score)
            )
            benchmark_ordering = index_to_ri_scores[index_with_max_score].point_index_to_benchmark_name_map.copy()
        elif point_ordering_mode == 'max_throughput':
            index_with_max_throughput = None
            max_observed_throughput = None
            for index, ri_scores in enumerate(index_to_ri_scores):
                assert ri_scores.num_negative == 0
                # Only positive score results will have throughput values
                for ri in ri_scores.positive_results:
                    _, _, t_ub = ri_scores.get_fuzzing_throughtput_from(ri)
                    if index_with_max_throughput is None:
                        index_with_max_throughput = index
                        max_observed_throughput = t_ub
                        continue
                    if t_ub > max_observed_throughput:
                        index_with_max_throughput = index
                        max_mean_throughput = t_ub
            benchmark_ordering = index_to_ri_scores[index_with_max_throughput].point_index_to_benchmark_name_map.copy()
        elif point_ordering_mode == 'max_mean_throughput':
            raise Exception('Not implemented')
        else:
            raise Exception('Unknown point_ordering: {}'.format(point_ordering_mode))
        assert isinstance(benchmark_ordering, list)

        # Now compute points again but using the specific benchmark ordering.
        for ri_scores in index_to_ri_scores:
            ri_scores.compute_points(order_by=benchmark_ordering)

    def _compute_score(self, ri):
        """
            Look result and give positive score
            if a throughput amount is available.
            Otherwise give a zero score.

            Should we have a mode where we treat
            getting the answer right in the first
            guess is a zero?
        """
        # FIXME: support merged throughput
        jfs_stat_fuzzing_wallclock_time = ri['jfs_stat_fuzzing_wallclock_time']
        jfs_stat_num_inputs = ri['jfs_stat_num_inputs']
        jfs_stat_num_wrong_sized_inputs = ri['jfs_stat_num_wrong_sized_inputs']
        values = [
            jfs_stat_fuzzing_wallclock_time,
            jfs_stat_num_inputs,
            jfs_stat_num_wrong_sized_inputs,
        ]
        if all(map(lambda x: x is not None, values)):
            return 1
        return 0

    # NOTE: No benchmark should have this name because
    # we use it to represent the dummy point.
    _dummy_point_name = '__DUMMY_POINT__'

    def get_fuzzing_throughtput_from(self, ri, no_throughtput_as_none=True):
        """
            Returns (<lower_bound>, <avg>, <upper_bound>)
        """
        assert isinstance(ri, dict)
        if self._compute_score(ri) == 0:
            # Throughput not available
            if no_throughtput_as_none:
                return (None, None, None)
            return (0.0, 0.0, 0.0)
        # FIXME: Support merged throughput
        jfs_stat_fuzzing_wallclock_time = ri['jfs_stat_fuzzing_wallclock_time']
        jfs_stat_num_inputs = ri['jfs_stat_num_inputs']
        jfs_stat_num_wrong_sized_inputs = ri['jfs_stat_num_wrong_sized_inputs']
        assert jfs_stat_fuzzing_wallclock_time > 0.0
        throughput = (
            (jfs_stat_num_inputs + jfs_stat_num_wrong_sized_inputs) / 
            jfs_stat_fuzzing_wallclock_time
        )
        return (throughput, throughput, throughput)

    def _compute_points(self, **kwargs):
        """
        Return tuple
        ( <x points>, <y points>, <y errors>, <point index to benchmark name map>)
        """
        if 'order_by' not in kwargs:
            raise Exception('order_by not specified')
        order_by = kwargs['order_by']

        x_points = []
        y_points = []
        y_errors = [[], []]
        point_index_to_benchmark_name_map = []

        positive_ris = self._positive_results.copy()
        negative_ris = self._negative_results.copy()
        _logger.info('# {} positive benchmarks'.format(len(positive_ris)))
        _logger.info('# {} negative benchmarks'.format(len(negative_ris)))
        ris_to_plot = []

        # Sort the positive points as specified by `order_by`.
        if order_by is None:
            # Order by fuzzing throughput, ignoring bounds.
            ris_to_plot.extend(positive_ris)
            ris_to_plot.sort(key=lambda ri: self.get_fuzzing_throughtput_from(ri)[1])
        else:
            assert isinstance(order_by, list)
            ris_handled = set()
            for benchmark_name in order_by:
                assert isinstance(benchmark_name, str)
                if benchmark_name == self._dummy_point_name:
                    # Skip dummy point because it's not something that
                    # has a throughput.
                    continue
                ri = self._benchmark_name_to_ri_map[benchmark_name]
                ris_handled.add(benchmark_name)
                ris_to_plot.append(ri)
            # FIXME: There might be some RIs left that didn't appear in the ordering.
            # We could try to find them and actually plot them

        x_starting_point = 0 -len(negative_ris)
        x_accumulating_score = x_starting_point

        # First point to handle is the "dummy point" which summarises the
        # number of negative scores. This doesn't actually make sense when
        # `order_by` is not None because there could be negative stores being
        # plotted elsewhere (`ris_to_plot` includes negative points). However
        # by construction the number of negative scores should always be zero
        # so just assert it here.
        assert len(negative_ris) == 0
        index = 0
        dummy_point_y_value = 0.0
        if len(positive_ris) == 0:
            _logger.warning('Using {} as dummy point time'.format(dummy_y_value))
        else:
            # Use the throughput of the point with the lowest throughput.
            # This avoids any big discontinuities at the beginning
            # (left most region) of the curve
            dummy_point_y_value = self.get_fuzzing_throughtput_from(ris_to_plot[0])[1]
        x_points.append(x_accumulating_score)
        y_points.append(dummy_point_y_value)
        y_errors[0].append(0.0)
        y_errors[1].append(0.0)
        # Doesn't correspond to any one single benchmark so give it a fake name
        point_index_to_benchmark_name_map.append(self._dummy_point_name)
        x_accumulating_score += 1

        # Now plot other points. When `order_by` is None this just all the positively
        # scoring benchmarks.
        for ri in ris_to_plot:
            lower_throughtput_bound, avg_throughput, upper_throughput_bound = self.get_fuzzing_throughtput_from(ri)
            print("x = {}, y = {}".format(x_accumulating_score, avg_throughput))
            x_points.append(x_accumulating_score)
            y_points.append(avg_throughput)
            upper_y_error = abs(upper_throughput_bound - avg_throughput)
            lower_y_error = abs(avg_throughput - lower_throughtput_bound)
            y_errors[0].append(lower_y_error)
            y_errors[1].append(upper_y_error)
            point_index_to_benchmark_name_map.append(ri['benchmark'])
            x_accumulating_score += 1

        return (x_points, y_points, y_errors, point_index_to_benchmark_name_map)


class ResultInfoTimeScores(ResultInfoGenericScore):
    def __init__(self, result_info_to_time_bounds_fn):
        super(ResultInfoTimeScores, self).__init__()
        self._result_info_to_time_bounds_fn = result_info_to_time_bounds_fn

    @property
    def x_label(self):
        return 'Accumulated score'

    @property
    def y_label(self):
        return 'Runtime (s)'

    def _compute_score(self, ri):
        # Look at the event tag
        # Merge tags if a merge resutl and
        # then compute a score.
        event_tag, conflicts = event_analysis.get_event_tag(ri)
        _logger.debug('Got "{}" tag for ri {}'.format(event_tag, ri['benchmark']))
        if conflicts:
            _logger.warning('Conflicts found when processing {}'.format(ri))
        if event_tag == 'sat':
            return 1
        elif event_tag == 'unsat':
            return 1
        elif event_tag == 'sat_but_expected_unsat':
            return -1
        elif event_tag == 'unsat_but_expected_sat':
            return -1
        elif event_tag is None:
            raise Exception("Event tag can't be None")
        else:
            # Any other event
            return 0

    def _compute_points(self, **kwargs):
        """
        Return tuple
        ( <x points>, <y points>, <y errors>, <point index to benchmark name map>)
        """
        if len(kwargs) > 0:
            raise Exception('Keyword arguments not accepted')
        x_points = []
        y_points = []
        y_errors = [ [], [] ]
        point_index_to_benchmark_name_map = []

        positive_ris = self._positive_results.copy()
        negative_ris = self._negative_results.copy()
        _logger.info('# {} positive benchmarks'.format(len(positive_ris)))
        _logger.info('# {} negative benchmarks'.format(len(negative_ris)))

        # Sort the positive points by execution time
        # Ignoring bounds.
        positive_ris.sort(key=lambda ri: self._result_info_to_time_bounds_fn(ri)[1])

        x_starting_point = 0 -len(negative_ris)
        x_accumulating_score = x_starting_point

        # First point to handle is the "dummy point" which summarises the number
        # of negative scores
        index = 0
        dummy_point_time = 0.0
        if len(positive_ris) == 0:
            _logger.warning('Using {} as dummy point time'.format(dummy_point_time))
        else:
            # Use the time of the point of the shortest executing positive score
            # benchmark. This avoids any big discontinuities at the beginning
            # (left most region) of the curve
            dummy_point_time = self._result_info_to_time_bounds_fn(positive_ris[0])[1]
        x_points.append(x_accumulating_score)
        y_points.append(dummy_point_time)
        y_errors[0].append(0.0)
        y_errors[1].append(0.0)
        # Doesn't correspond to any one single benchmark so give it a fake name
        point_index_to_benchmark_name_map.append("dummy_point")
        x_accumulating_score += 1

        # Now add the other points corresponding to positively scoring benchmarks
        for ri in positive_ris:
            lower_exec_time_bound, avg_exec_time, upper_exec_time_bound = self._result_info_to_time_bounds_fn(ri)
            x_points.append(x_accumulating_score)
            y_points.append(avg_exec_time)
            upper_y_error = abs(upper_exec_time_bound - avg_exec_time)
            lower_y_error = abs(avg_exec_time - lower_exec_time_bound)
            y_errors[0].append(lower_y_error)
            y_errors[1].append(upper_y_error)
            point_index_to_benchmark_name_map.append(ri['benchmark'])
            x_accumulating_score += 1

        return (x_points, y_points, y_errors, point_index_to_benchmark_name_map)

def make_result_info_score_generator(pargs):
    if pargs.mode == 'time':
        # For each result info compute the corresponding scores.
        def result_info_to_time_bounds_fn(ri):
            return analysis.get_exec_time_with_bounds(
                ri,
                max_time=pargs.max_exec_time,
                bound_fn=analysis.get_arithmetic_mean_and_99_confidence_intervals,
                time_prefs=['dsoes_wallclock', 'wallclock']
            )
        return ResultInfoTimeScores(result_info_to_time_bounds_fn)
    elif pargs.mode == 'fuzzing_throughput':
        return ResultInfoFuzzingThroughputScores()
    else:
        raise Exception("{} is an unsupported mode".format(pargs.mode))

def main(args):
    global _logger
    global _fail_count
    parser = argparse.ArgumentParser(description=__doc__)
    DriverUtil.parserAddLoggerArg(parser)
    parser.add_argument('--true-type-fonts',
        default=False,
        action='store_true'
    )
    parser.add_argument('result_infos', nargs='+', help='Input YAML files')
    parser.add_argument('--title', default="", type=str)
    parser.add_argument('--legend-name-map',dest='legend_name_map', default=None, type=str)
    parser.add_argument('--legend-position',dest='legend_position', default='outside_bottom', choices=['outside_bottom', 'outside_right', 'inner', 'none'])
    parser.add_argument('--report-negative-results',dest='report_negative_results', default=False, action='store_true')
    parser.add_argument('--legend-font-size', dest='legend_font_size', default=None, type=int)
    parser.add_argument('--draw-style', dest='drawstyle', choices=['steps','default'], default='default', help='Line draw style')
    parser.add_argument('--legend-num-columns', dest='legend_num_columns',
            default=3,
            type=int
    )
    actionGroup = parser.add_mutually_exclusive_group()
    actionGroup.add_argument('--ipython', action='store_true')
    actionGroup.add_argument('--pdf', help='Write graph to PDF')
    actionGroup.add_argument('--svg', help='Write graph to svg')

    plotGroup = parser.add_mutually_exclusive_group()
    plotGroup.add_argument("--points", action='store_true')
    plotGroup.add_argument("--error-bars", action='store_true', dest='error_bars')
    parser.add_argument('--point-size', type=float, default=3.0, dest='point_size')
    parser.add_argument('--allow-merge-failures',
        dest='allow_merge_failures',
        default=False,
        action='store_true',
    )
    parser.add_argument('--max-exec-time',
        default=None,
        type=float,
        dest='max_exec_time',
    )
    parser.add_argument('--mode',
        choices=['time', 'fuzzing_throughput'],
        default='time',
    )
    parser.add_argument('--fuzzing-point-ordering',
        choices=['independent', 'max_score', 'max_throughput', 'max_mean_throughput'],
        dest='fuzzing_point_ordering',
        default=None,
    )

    pargs = parser.parse_args(args)
    DriverUtil.handleLoggerArgs(pargs, parser)
    _logger = logging.getLogger(__name__)

    if pargs.mode == 'time' and pargs.max_exec_time is None:
        _logger.error('--max-exec-time must be specified')
        return 1
    if pargs.max_exec_time is not None and pargs.mode == 'fuzzing_throughput':
        _logger.warning('Ignoring --max-time')
        pargs.max_exec_time = None

    if pargs.pdf != None:
      if not pargs.pdf.endswith('.pdf'):
        logging.error('--pdf argument must end with .pdf')
        return 1
      if os.path.exists(pargs.pdf):
        logging.error('Refusing to overwrite {}'.format(pargs.pdf))
        return 1

    if pargs.svg != None:
      if not pargs.svg.endswith('.svg'):
        logging.error('--pdf argument must end with .svg')
        return 1
      if os.path.exists(pargs.svg):
        logging.error('Refusing to overwrite {}'.format(pargs.svg))
        return 1

    if pargs.true_type_fonts:
        smtrunner.util.set_true_type_font()

    index_to_raw_result_infos = []
    index_to_file_name = []
    index_to_abs_file_path = []
    index_to_truncated_file_path = []
    index_to_ris = []
    index_to_legend_name = []
    if pargs.legend_name_map:
        # Naming is bad here. We actually expect
        # to receive a list of names to use the corresponds
        # to the ordering of RI files on the command line.
        with open(pargs.legend_name_map, 'r') as f:
            legend_list = smtrunner.util.loadYaml(f)
            if not isinstance(legend_list, list):
                _logger.error('Legend mapping file must be a list')
                return 1
            if len(legend_list) != len(pargs.result_infos):
                _logger.error('Legend mapping file list must contain {}'.format(len(pargs.result_infos)))
                return 1
            index_to_legend_name = legend_list

    for index, result_infos_file_path in enumerate(pargs.result_infos):
        try:
          with open(result_infos_file_path, 'r') as f:
            _logger.info('Loading "{}"'.format(f.name))
            ris = ResultInfo.loadRawResultInfos(f)
            index_to_raw_result_infos.append(ris)
            index_to_file_name.append(f.name)
            index_to_abs_file_path.append(os.path.abspath(f.name))
            index_to_ris.append(ris['results'])
        except ResultInfo.ResultInfoValidationError as e:
            _logger.error('Validation error:\n{}'.format(e))
            return 1
        _logger.info('Loading done')
    result_infos = None

    longest_path_prefix = ResultInfoUtil.compute_longest_common_path_prefix(index_to_abs_file_path)
    index_to_prefix_truncated_path = []
    for index, _ in enumerate(pargs.result_infos):
        path = index_to_abs_file_path[index]
        index_to_prefix_truncated_path.append(path[len(longest_path_prefix):])
    # Now truncated suffixes
    longest_path_suffix = ResultInfoUtil.compute_longest_common_path_suffix(index_to_prefix_truncated_path)
    for index, _ in enumerate(pargs.result_infos):
        truncated_path = index_to_prefix_truncated_path[index]
        truncated_path = truncated_path[:-(len(longest_path_suffix))]
        index_to_truncated_file_path.append(truncated_path)
        assert index_to_truncated_file_path[index] == truncated_path

    # Perform grouping by benchmark name
    # Technically not necessary but this can be used as a safety check to make sure
    # all result info files are talking about the same benchmarks
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

    _logger.info('Computing points')
    index_to_ri_scores = []
    index_to_x_points = []
    index_to_y_points = []
    index_to_y_error_points = []
    index_to_point_index_to_benchmark_name_map = []
    max_observed_y_value = 0.0
    max_observed_x_value = 0.0
    min_observed_x_value = 0.0
    for index, ris in enumerate(index_to_raw_result_infos):
        ri_scores = make_result_info_score_generator(pargs)
        index_to_ri_scores.append(ri_scores)
        ri_scores.addResults(ris['results'])
    # Do point computations
    do_global_compute_points_kwargs = {}
    if pargs.fuzzing_point_ordering:
        do_global_compute_points_kwargs['point_ordering'] = pargs.fuzzing_point_ordering
    index_to_ri_scores[0].do_global_compute_points(
        index_to_ri_scores,
        **do_global_compute_points_kwargs
    )

    for index, ri_scores in enumerate(index_to_ri_scores):
        index_to_x_points.append(ri_scores.x_points)
        index_to_y_points.append(ri_scores.y_points)
        index_to_y_error_points.append(ri_scores.y_errors)
        index_to_point_index_to_benchmark_name_map.append(
            ri_scores.point_index_to_benchmark_name_map)

        # See if we've found a larger time.
        for y_point in ri_scores.y_points:
            if y_point is not None and y_point > max_observed_y_value:
                max_observed_y_value = y_point
        for x_point in ri_scores.x_points:
            if x_point > max_observed_x_value:
                max_observed_x_value = x_point
            if x_point < min_observed_x_value:
                min_observed_x_value = x_point
    _logger.info('Computing points done')
    _logger.info('min observed x value: {}'.format(min_observed_x_value))
    _logger.info('max observed x value: {}'.format(max_observed_x_value))
    _logger.info('max observed y value: {}'.format(max_observed_y_value))
    ri_scores = None

    # Report means
    for index, ri_score in enumerate(index_to_ri_scores):
        name = index_to_truncated_file_path[index]
        means = ri_score.get_y_mean_bounds()
        _logger.info('Means (<min>, <mean>, <max>) for {} is {}'.format(
            name, means)
        )

    # Now try to plot
    fig, ax = plt.subplots()

    if len(pargs.title) > 0:
        ax.set_title(pargs.title)
    ax.set_xlabel(index_to_ri_scores[0].x_label)
    ax.set_ylabel(index_to_ri_scores[0].y_label)

    # Add curves
    curves = [ ]
    legend_names = [ ]
    for index, _ in enumerate(index_to_ris):
        _logger.info('"{}" # of benchmarks with {} +ve score, {} -ve score, {} zero score'.format(
            index_to_truncated_file_path[index],
            index_to_ri_scores[index].num_positive,
            index_to_ri_scores[index].num_negative,
            index_to_ri_scores[index].num_zero)
        )
        x_points = index_to_x_points[index]
        y_points = index_to_y_points[index]
        y_errors = index_to_y_error_points[index]
        point_index_to_benchmark_name_map = index_to_point_index_to_benchmark_name_map[index]
        name_for_legend = None
        result_info_file_name = index_to_file_name[index]
        if pargs.legend_name_map:
            name_for_legend = index_to_legend_name[index]
        else:
            #name_for_legend = result_info_file_name
            name_for_legend = index_to_truncated_file_path[index]
        pickTolerance=4
        if pargs.error_bars:
            p = ax.errorbar(
                x_points,
                y_points,
                yerr=y_errors,
                #picker=pickTolerance,
                drawstyle=pargs.drawstyle,
                markersize=pargs.point_size)
        else:
            p = ax.plot(
                x_points,
                y_points,
                '-o' if pargs.points else '-',
                #picker=pickTolerance,
                drawstyle=pargs.drawstyle,
                markersize=pargs.point_size)
        curves.append(p[0])

        legend_names.append(name_for_legend)
    # Add legend
    assert len(legend_names) == len(curves)
    if pargs.legend_position == 'none':
        fig.tight_layout()
    elif pargs.legend_position == 'inner':
        legend = ax.legend(
            tuple(curves),
            tuple(legend_names),
            ncol=pargs.legend_num_columns,
            loc='upper left',
            fontsize=pargs.legend_font_size
        )
        fig.tight_layout()
    elif pargs.legend_position == 'outside_right':
        # HACK: move the legend outside
        # Shrink current axis by 20%
        box = ax.get_position()
        print(box)
        legend = ax.legend(tuple(curves), tuple(legend_names),
            loc='upper left',
            bbox_to_anchor=(1.01, 1.0),
            borderaxespad=0, # No padding so that corners line up
            fontsize=pargs.legend_font_size,
            ncol=pargs.legend_num_columns
        )

        # Work out how wide the legend is in terms of axes co-ordinates
        fig.canvas.draw() # Needed say that legend size computation is correct
        legendWidth, _ = ax.transAxes.inverted().transform((legend.get_frame().get_width(), legend.get_frame().get_height()))
        assert legendWidth > 0.0

        # FIXME: Why do I have to use 0.95??
        ax.set_position([box.x0, box.y0, box.width * (0.95 - legendWidth), box.height])
    elif pargs.legend_position == 'outside_bottom':
        box = ax.get_position()
        legend = ax.legend(
            tuple(curves),
            tuple(legend_names),
            ncol=pargs.legend_num_columns,
            bbox_to_anchor=(0.5, -0.13),
            loc='upper center',
            fontsize=pargs.legend_font_size
        )
        # Work out how wide the legend is in terms of axes co-ordinates
        fig.canvas.draw() # Needed say that legend size computation is correct
        legendWidth, legendHeight = ax.transAxes.inverted().transform((legend.get_frame().get_width(), legend.get_frame().get_height()))
        hack_y_axis_offset=0.15
        ax.set_position([
            box.x0,
            box.y0 + legendHeight + hack_y_axis_offset,
            box.width,
            box.height - legendHeight - 0.6*hack_y_axis_offset]
        )
    else:
        assert False

    if pargs.legend_position != 'none':
      if 'set_draggable' in dir(legend):
        legend.set_draggable(True) # Make it so we can move the legend with the mouse
      else:
          legend.draggable(True)

    # Adjust y-axis so it is a log plot everywhere except [-1,1] which is linear
    ax.set_yscale('symlog', linthreshy=1.0, linscaley=0.1)

    #set minor ticks on y-axis
    from matplotlib.ticker import LogLocator
    import numpy
    yAxisLocator = LogLocator(subs=numpy.arange(1.0,10.0))
    ax.yaxis.set_minor_locator(yAxisLocator)
    ax.yaxis.set_tick_params(which='minor', length=4)
    ax.yaxis.set_tick_params(which='major', length=6)
    #ax.grid()

    # Y-axis bounds
    if pargs.max_exec_time:
        assert pargs.max_exec_time > 0.0
        ax.set_ybound(lower=0.0, upper=pargs.max_exec_time)
    else:
        ax.set_ybound(lower=0.0, upper=round_away_from_zero_to_multiple_of(100, max_observed_y_value))

    # X-axis bounds
    # Round up to nearest multiple of 10
    assert max_observed_x_value >= 0.0
    x_axis_upper_bound = round_away_from_zero_to_multiple_of(10, max_observed_x_value)
    x_axis_lower_bound = round_away_from_zero_to_multiple_of(10, min_observed_x_value)
    ax.set_xbound(lower=x_axis_lower_bound, upper=x_axis_upper_bound)
    _logger.info('X axis bounds [{}, {}]'.format(x_axis_lower_bound, x_axis_upper_bound))


    if pargs.ipython:
        # Useful interfactive console
        header="""Useful commands:
        fig.show() - Shows figure
        fig.canvas.draw() - Redraws figure (useful if you changed something)
        fig.savefig('something.pdf') - Save the figure
        """
        from IPython import embed
        embed(header=header)
    elif pargs.pdf != None:
        fig.show()
        logging.info('Writing PDF to {}'.format(pargs.pdf))
        fig.savefig(pargs.pdf)
    elif pargs.svg != None:
        fig.show()
        logging.info('Writing svg to {}'.format(pargs.svg))
        fig.savefig(pargs.svg)
    else:
        plt.show()
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
