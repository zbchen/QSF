#!/usr/bin/env python
# Copyright (c) 2017, Daniel Liew
# This file is covered by the license in LICENSE.txt
# vim: set sw=4 ts=4 softtabstop=4 expandtab:
"""
Read an invocation info file and copy benchmarks that are
present.
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
import shutil
import sys
import yaml

_logger = None


def main(args):
    global _logger
    parser = argparse.ArgumentParser(description=__doc__)
    DriverUtil.parserAddLoggerArg(parser)
    parser.add_argument('result_infos',
                        type=argparse.FileType('r'))
    parser.add_argument('--benchmark-base', type=str, default=os.getcwd())
    parser.add_argument('dest_dir', type=str)

    pargs = parser.parse_args(args)
    DriverUtil.handleLoggerArgs(pargs, parser)
    _logger = logging.getLogger(__name__)

    # Make destination if it doesn't exist
    try:
        os.mkdir(pargs.dest_dir)
    except FileExistsError:
        pass
    
    try:
        _logger.info('Loading "{}"'.format(pargs.result_infos.name))
        result_infos = ResultInfo.loadRawResultInfos(pargs.result_infos)
    except ResultInfo.ResultInfoValidationError as e:
        _logger.error('Validation error:\n{}'.format(e))
        return 1
    _logger.info('Loading done')

    destination_root = os.path.abspath(pargs.dest_dir)
    assert os.path.exists(destination_root)

    for ri in result_infos['results']:
        key = ResultInfoUtil.get_result_info_key(ri)
        # Construct source path
        if key.startswith(os.path.sep):
            key = key[1:]
        src_path = os.path.join(pargs.benchmark_base, key)
        if not os.path.exists(src_path):
            _logger.error('{} does not exist'.format(src_path))
            return 1
        # Construct destination path
        dirs = os.path.dirname(key)
        filename = os.path.basename(key)

        dest_dir = os.path.join(destination_root, dirs)
        _logger.debug('Destination dir is {}'.format(dest_dir))
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, filename)
        _logger.info('Copying {} => {}'.format(src_path, dest_path))
        shutil.copy2(src_path, dest_path)
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
