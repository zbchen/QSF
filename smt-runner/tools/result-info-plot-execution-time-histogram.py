#!/usr/bin/env python
# vim: set sw=4 ts=4 softtabstop=4 expandtab:
from load_smtrunner import add_smtrunner_to_module_search_path
add_smtrunner_to_module_search_path()
from smtrunner import ResultInfo, DriverUtil

import smtrunner.util
import argparse
import logging
import os
import sys

_logger = None


def main(args):
    global _logger
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plot-bins",
        type=int,
        dest='plot_number_of_bins',
        default=100,
        help='Number of bins for histogram plot'
    )
    parser.add_argument('result_infos',
                        type=argparse.FileType('r'))
    parser.add_argument('--base', type=str, default="")
    parser.add_argument('--report-num-under',
        dest='report_num_under',
        type=int,
        default=0,
        help='Report number of benchmarks in histogram <= this size',
    )
    parser.add_argument('--max-exec-time',
        dest='max_exec_time',
        type=int,
        default=-1,
        help="If non-negative give explicit max time"
    )
    parser.add_argument('--force-title',
        dest='force_title',
        type=str,
        default=None,
        help="Force plot use supplied title",
    )
    parser.add_argument('--true-type-fonts',
        default=False,
        action='store_true'
    )

    DriverUtil.parserAddLoggerArg(parser)
    pargs = parser.parse_args(args)
    DriverUtil.handleLoggerArgs(pargs, parser)
    _logger = logging.getLogger(__name__)

    if pargs.true_type_fonts:
        smtrunner.util.set_true_type_font()

    try:
        _logger.info('Loading "{}"'.format(pargs.result_infos.name))
        result_infos = ResultInfo.loadRawResultInfos(pargs.result_infos)
    except ResultInfo.ResultInfoValidationError as e:
        _logger.error('Validation error:\n{}'.format(e))
        return 1
    _logger.info('Loading done')

    if pargs.force_title is not None:
        title = pargs.force_title
    else:
        title = os.path.abspath(pargs.result_infos.name)

    max_time = None
    if pargs.max_exec_time > 0:
        max_time = pargs.max_exec_time

    report_num_under = None
    if pargs.report_num_under > 0:
        report_num_under = pargs.report_num_under

    plot_histogram(result_infos['results'], pargs.plot_number_of_bins, title, max_time, report_num_under)
    return 0

def plot_histogram(runs, nbins, title, max_time, report_num_under):
    assert isinstance(runs, list)
    import matplotlib.pyplot as plt
    def bound_time(t):
        if max_time is not None:
            return min(t, max_time)
        else:
            return t
    execution_times = [ bound_time(r['wallclock_time']) for r in runs ]

    if max_time is not None:
        # Use user provided value
        assert max_time > 0
        assert isinstance(max_time, int)
        max_exec = max_time
    else:
        # Guess max time
        max_exec = max(execution_times)

    bin_width = max_exec / nbins
    min_exec = min(execution_times)
    _logger.info('Bin width: {}'.format(bin_width))
    n, bins, patches = plt.hist(
        execution_times,
        bins=nbins,
        range=(0, max_exec),
    )
    _logger.info('n: {}'.format(n))
    _logger.info('bins: {}'.format(bins))

    if report_num_under is not None:
        accum_num_under = 0;
        for bin_count in n:
            if bin_count <= report_num_under:
                accum_num_under += bin_count
        _logger.info('Number of benchmarks in bins of size <= {}: {}'.format(
            report_num_under,
            accum_num_under))

    plt.grid(True)
    plt.xlabel('Execution Time (s)')
    plt.ylabel('Count')
    plt.yscale('log', nonposy='clip')
    plt.title(title)

    if max_time is not None:
        # Use range
        plt.xlim([0, max_time])
    plt.show()

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

