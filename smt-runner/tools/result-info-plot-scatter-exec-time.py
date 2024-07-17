#!/usr/bin/env python
# Copyright (c) 2017, Daniel Liew
# This file is covered by the license in LICENSE.txt
# vim: set sw=4 ts=4 softtabstop=4 expandtab:
"""
Read two result info files and generate a scatter plot of execution time
"""
from load_smtrunner import add_smtrunner_to_module_search_path
add_smtrunner_to_module_search_path()
from smtrunner import ResultInfo, DriverUtil, ResultInfoUtil, analysis, event_analysis
import smtrunner.util
import matplotlib.pyplot as plt
import numpy as np

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
    parser.add_argument('first_result_info',
        type=argparse.FileType('r'))
    parser.add_argument('second_result_info',
        type=argparse.FileType('r'))
    parser.add_argument('--base', type=str, default="")
    parser.add_argument('--point-size', type=float, default=25.0, dest='point_size')
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
    parser.add_argument('--title',
        default="{num_keys} benchmarks, {num_points} jointly SAT or timeout"
    )
    parser.add_argument("--xlabel",
        type=str,
        default=None,
    )
    parser.add_argument("--ylabel",
        type=str,
        default=None,
    )
    parser.add_argument("--axis-label-suffix",
        type=str,
        default=" execution time (s)",
        dest="axis_label_suffix",
    )
    parser.add_argument("--axis-label-colour",
        type=str,
        default="black",
        dest="axis_label_colour",
    )
    parser.add_argument("--annotate",
        default=False,
        action='store_true',
    )
    parser.add_argument("--annotate-use-legacy-values",
        default=False,
        action='store_true',
    )
    parser.add_argument("--output",
        default=None,
        type=argparse.FileType('wb'),
    )
    parser.add_argument("--error-bars",
        default=False,
        action='store_true',
    )
    parser.add_argument("--annotate-timeout-point",
        dest='annotate_timeout_point',
        default=False,
        action='store_true',
    )
    parser.add_argument("--require-time-abs-diff",
        dest="require_time_abs_diff",
        default=0.0,
        type=float
    )
    parser.add_argument('--true-type-fonts',
        default=False,
        action='store_true'
    )

    pargs = parser.parse_args(args)
    DriverUtil.handleLoggerArgs(pargs, parser)
    _logger = logging.getLogger(__name__)

    if pargs.max_exec_time is None:
        _logger.error('--max-exec-time must be specified')
        return 1

    if pargs.true_type_fonts:
        smtrunner.util.set_true_type_font()

    index_to_raw_result_infos = []
    index_to_file_name = []
    for index, result_infos_file in enumerate([pargs.first_result_info, pargs.second_result_info]):
        try:
            _logger.info('Loading "{}"'.format(result_infos_file.name))
            result_infos = ResultInfo.loadRawResultInfos(result_infos_file)
            index_to_raw_result_infos.append(result_infos)
            index_to_file_name.append(result_infos_file.name)
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


    # Generate scatter points
    x_scatter_points = []
    x_scatter_errors = [[], []]
    y_scatter_points = []
    y_scatter_errors = [[], []]
    count_dual_timeout = 0
    count_x_lt_y_not_dt = 0
    count_x_gt_y_not_dt = 0
    count_x_eq_y_not_dt = 0

    # New counting vars
    bounds_incomparable_keys = set()
    x_gt_y_keys = set()
    x_lt_y_keys = set()
    x_eq_y_keys = set()
    x_eq_y_and_is_timeout_keys = set()
    cnt = 0
    for key, raw_result_info_list in sorted(key_to_results_infos.items(), key=lambda kv:kv[0]):
        _logger.info('Ranking on "{}" : '.format(key))
        indices_to_use = []
        # Compute indices to use
        modified_raw_result_info_list = [ ]
        # Handle "unknown"
        # Only compare results that gave sat/unsat
        for index, ri in enumerate(raw_result_info_list):
            if isinstance(ri['event_tag'], str):
                # single result
                event_tag = ri['event_tag']
            else:
                assert isinstance(ri['event_tag'], list)
                event_tag, _ = event_analysis.merge_aggregate_events(
                    ri['event_tag'])

            # Event must be sat or timeout
            _logger.info('index {} is {}'.format(index, event_tag))
            if event_tag not in { 'sat', 'timeout', 'soft_timeout'}:
                # Skip this. We can't do a meaningful comparison here
                continue
            indices_to_use.append(index)
            # Normalise timeouts to have fixed values for the time.
            if event_tag in {'timeout', 'soft_timeout'}:
                modified_ri = analysis.get_result_with_modified_time(
                    ri,
                    pargs.max_exec_time)
                _logger.debug('modified_ri: {}'.format(
                    pprint.pformat(modified_ri)))
                _logger.debug(
                    'Treating index {} for {} due to unknown as having max-time'.format(
                        index,
                        key))
                modified_raw_result_info_list.append(modified_ri)
            else:
                modified_raw_result_info_list.append(ri)
        _logger.debug('used indices_to_use: {}'.format(indices_to_use))

        if len(indices_to_use) != 2:
            # Skip this one. One of the result infos can't be compared
            # against.
            continue

        assert len(indices_to_use) == 2
        # Get execution times
        index_to_execution_time_bounds = analysis.get_index_to_execution_time_bounds(
            modified_raw_result_info_list,
            indices_to_use,
            pargs.max_exec_time,
            analysis.get_arithmetic_mean_and_99_confidence_intervals,
            ['dsoes_wallclock', 'wallclock'])
        assert isinstance(index_to_execution_time_bounds, list)
        # index_to_execution_time_bounds is a list of tuples  (lower_bound, mean, upper_bound)   99.9% confidence interval
        x_scatter_point_bounds = index_to_execution_time_bounds[0]
        y_scatter_point_bounds = index_to_execution_time_bounds[1]
        x_scatter_point = x_scatter_point_bounds[1] # mean
        y_scatter_point = y_scatter_point_bounds[1] # mean
        x_scatter_lower_error = x_scatter_point_bounds[1] - x_scatter_point_bounds[0]
        assert x_scatter_lower_error >= 0
        x_scatter_higher_error = x_scatter_point_bounds[2] - x_scatter_point_bounds[1]
        assert x_scatter_higher_error >= 0
        y_scatter_lower_error = y_scatter_point_bounds[1] - y_scatter_point_bounds[0]
        assert y_scatter_lower_error >= 0
        y_scatter_higher_error = y_scatter_point_bounds[2] - y_scatter_point_bounds[1]
        assert y_scatter_higher_error >= 0

        print(cnt)
        cnt += 1
        x_scatter_points.append(x_scatter_point)
        y_scatter_points.append(y_scatter_point)
        # Error bar points
        #x_scatter_errors.append((x_scatter_lower_error, x_scatter_higher_error))
        x_scatter_errors[0].append(x_scatter_lower_error)
        x_scatter_errors[1].append(x_scatter_higher_error)
        #y_scatter_errors.append((y_scatter_lower_error, y_scatter_higher_error))
        y_scatter_errors[0].append(y_scatter_lower_error)
        y_scatter_errors[1].append(y_scatter_higher_error)

        # LEGACY: Now do some counting
        if x_scatter_point == y_scatter_point:
            if x_scatter_point == pargs.max_exec_time:
                assert x_scatter_lower_error == 0
                assert x_scatter_higher_error == 0
                assert y_scatter_lower_error == 0
                assert y_scatter_higher_error == 0
                count_dual_timeout += 1
            else:
                _logger.info('Found count_x_eq_y_not_dt: x: {}, key: {}'.format(
                    x_scatter_point,
                    key))
                count_x_eq_y_not_dt += 1
        elif x_scatter_point > y_scatter_point:
            count_x_gt_y_not_dt += 1
        else:
            assert x_scatter_point < y_scatter_point
            count_x_lt_y_not_dt += 1

        # SMARTER counting: uses error bounds
        if analysis.bounds_overlap(x_scatter_point_bounds, y_scatter_point_bounds):
            # Bounds overlap, we can't compare the execution times in a meaningful way
            bounds_incomparable_keys.add(key)
            # However if both are timeouts we can note this
            if x_scatter_point == pargs.max_exec_time:
                x_eq_y_and_is_timeout_keys.add(key)
            # else:
            #     print(x_scatter_points, y_scatter_points)
        else:
            # Compare the means
            if x_scatter_point > y_scatter_point and abs(x_scatter_point - y_scatter_point) > pargs.require_time_abs_diff:
                x_gt_y_keys.add(key)
            elif x_scatter_point < y_scatter_point and abs(x_scatter_point - y_scatter_point) > pargs.require_time_abs_diff:
                x_lt_y_keys.add(key)
            else:
                if pargs.require_time_abs_diff == 0.0:
                    assert x_scatter_point == y_scatter_point
                x_eq_y_keys.add(key)

    # Report counts
    print("# of points : {}".format(len(x_scatter_points)))
    print("LEGACY: count_dual_timeout: {}".format(count_dual_timeout))
    print("LEGACY: count_x_eq_y_not_dt: {}".format(count_x_eq_y_not_dt))
    print("LEGACY: count_x_gt_y_not_dt: {}".format(count_x_gt_y_not_dt))
    print("LEGACY: count_x_lt_y_not_dt: {}".format(count_x_lt_y_not_dt))
    print("")
    print("# x > y and no bound overlap: {}".format(len(x_gt_y_keys)))
    print("# x < y and no bound overlap: {}".format(len(x_lt_y_keys)))
    print("# x = y and no bound overlap: {}".format(len(x_eq_y_keys)))
    print("# incomparable: {}".format(len(bounds_incomparable_keys)))
    print("# of x = y and is timeout: {}".format(len(x_eq_y_and_is_timeout_keys)))

    # print(x_scatter_points)
    # print(y_scatter_points)
    # print(len(x_scatter_points),len(y_scatter_points))
    x_time_mean = np.mean(x_scatter_points, 0)
    y_time_mean = np.mean(y_scatter_points, 0)
    print(x_time_mean, y_time_mean, y_time_mean/x_time_mean)
    x_a = 0
    y_a = 0
    cnt = 0;
    for i,v in enumerate(x_scatter_points):
        x_v = x_scatter_points[i]
        y_v = y_scatter_points[i]
        if x_v>=60:
            continue
        x_a += x_v
        y_a += y_v
        cnt += 1
    # xx_a = np.power(x_a, len(x_scatter_points))
    # yy_a = np.power(y_a, len(y_scatter_points))
    x_avg = x_a/cnt
    y_avg = y_a/cnt
    print(x_avg, y_avg, y_avg/x_avg)

    # Now plot
    # extend = 5  # modify yangxu
    # tickFreq = 5  # modify yangxu
    extend = 50 # modify yangxu
    tickFreq = 50 # modify yangxu
    assert len(x_scatter_points) == len(y_scatter_points)
    fig, ax = plt.subplots()
    fig.patch.set_alpha(0.0) # Transparent
    if pargs.error_bars:
        splot = ax.errorbar(
            x_scatter_points,
            y_scatter_points,
            xerr=x_scatter_errors,
            yerr=y_scatter_errors,
            fmt='o',
            picker=5,
            ms=pargs.point_size/2.0, # HACK
            ecolor='black',
            capsize=5,
            #capthick=10,
        )
    else:
        splot = ax.scatter(x_scatter_points, y_scatter_points, picker=5, s=pargs.point_size)
    xlabel = index_to_file_name[0] if pargs.xlabel is None else pargs.xlabel
    ylabel = index_to_file_name[1] if pargs.ylabel is None else pargs.ylabel
    xlabel += pargs.axis_label_suffix
    ylabel += pargs.axis_label_suffix
    ax.xaxis.label.set_color(pargs.axis_label_colour)
    ax.yaxis.label.set_color(pargs.axis_label_colour)
    ax.tick_params(axis='x', colors=pargs.axis_label_colour)
    ax.tick_params(axis='y', colors=pargs.axis_label_colour)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)

    ax.set_xlim(0,pargs.max_exec_time + extend)
    ax.set_ylim(0,pargs.max_exec_time + extend)
    # +1 is just so the pargs.max_exec_time is included because range()'s end is not inclusive
    ax.set_xticks(range(0, int(pargs.max_exec_time) + 1, tickFreq))
    ax.set_yticks(range(0, int(pargs.max_exec_time) + 1, tickFreq))

    # Construct title keyword args
    title_kwargs = {
        'num_points': len(x_scatter_points),
        'xlabel': xlabel,
        'ylabel': ylabel,
        'num_keys': len(key_to_results_infos.keys()),
    }
    ax.set_title(pargs.title.format(**title_kwargs))

    # Identity line
    ax.plot([ 0 , pargs.max_exec_time + extend], [0, pargs.max_exec_time + extend], linewidth=1.0, color='black', )

    if pargs.annotate:
        if pargs.annotate_use_legacy_values:
            _logger.warning('Displaying legacy values')
            x_lt_value_to_display = count_x_lt_y_not_dt
            x_gt_value_to_display = count_x_gt_y_not_dt
        else:
            _logger.info('Displaying new values')
            x_lt_value_to_display = len(x_lt_y_keys)
            x_gt_value_to_display = len(x_gt_y_keys)

        ax.annotate(
            '{}'.format(x_lt_value_to_display),
            # xy=(20, 40),  # modified yangxu
            xy=(200,400), # modified yangxu
            fontsize=40
        )
        ax.annotate(
            '{}'.format(x_gt_value_to_display),
            # xy=(20, 40),  # modified yangxu
            xy=(400,200), # modified yangxu
            fontsize=40
        )

    # timeout point annotation
    if pargs.annotate_timeout_point:
        num_dual_timeouts = len(x_eq_y_and_is_timeout_keys)
        dual_timeout_txt = None
        if num_dual_timeouts == 1:
            dual_timeout_txt = '{} dual timeout'.format(num_dual_timeouts)
        else:
            dual_timeout_txt = '{} dual timeouts'.format(num_dual_timeouts)

        ax.annotate(dual_timeout_txt,
            # HACK -5 is to offset arrow properly
            xy=(pargs.max_exec_time - 1.00, pargs.max_exec_time), xycoords='data',
            xytext=(-50, 0), textcoords='offset points',
            arrowprops=dict(facecolor='black', shrink=0.05, width=1.5, headwidth=7.0),
            horizontalalignment='right', verticalalignment='center',
            bbox=dict(boxstyle='round',fc='None'),
            fontsize=15)

    # Finally show
    if pargs.output is None:
        plt.show()
    else:
        # For command line usage
        fig.show()
        fig.savefig(pargs.output, format='pdf')
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
