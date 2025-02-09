#!/usr/bin/env python
# Copyright (c) 2017, Daniel Liew
# This file is covered by the license in LICENSE.txt
# vim: set sw=4 ts=4 softtabstop=4 expandtab:
"""
Read a result info files and filter based on a predicate
"""
from load_smtrunner import add_smtrunner_to_module_search_path
add_smtrunner_to_module_search_path()
from smtrunner import ResultInfo, DriverUtil
import smtrunner.util

import argparse
import logging
import os
import pprint
import re
import sys

_logger = None

def strip(prefix, path):
    if prefix == "":
        return path
    if path.startswith(prefix):
        return path[len(prefix):]

_RE_SMT2_STATUS = re.compile(r'^\s*\(set-info\s*:status\s*(sat|unsat|unknown)')
_RE_SMT2_DECL_FUN = re.compile(r'^\s*\(declare-fun')

def get_expected_sat(path):
    _logger.debug('Opening "{}"'.format(path))
    status = "unknown"
    with open(path, 'r') as f:
        for line in f:
            m = _RE_SMT2_DECL_FUN.match(line)
            if m:
                _logger.warning('Failed to find status decl in "{}"'.format(path))
                break
            m = _RE_SMT2_STATUS.match(line)
            if m:
                status = m.group(1)
                break
    _logger.debug('Status of "{}" is {}'.format(path, status))
    return status

def main(args):
    global _logger
    parser = argparse.ArgumentParser(description=__doc__)
    DriverUtil.parserAddLoggerArg(parser)
    parser.add_argument('directory',
                        help='Directory to scan',
                        type=str)
    parser.add_argument('--strip', type=str, default="")
    parser.add_argument('-o', '--output',
                        type=argparse.FileType('w'),
                        default=sys.stdout,
                        help='Output location (default stdout)')

    pargs = parser.parse_args(args)
    DriverUtil.handleLoggerArgs(pargs, parser)
    _logger = logging.getLogger(__name__)

    if not os.path.isdir(pargs.directory):
        _logger.error('"{}" is not a directory'.format(pargs.directory))
        return 1

    results = [ ]
    result_infos = {
        'schema_version': 0,
        'results': results,
    }
    for dirpath, _, filenames in os.walk(pargs.directory):
        for filename in filenames:
            if not filename.endswith('.smt2'):
                continue
            result_info = {
                'benchmark': os.path.join(strip(pargs.strip, dirpath), filename),
                'expected_sat': get_expected_sat(os.path.join(dirpath, filename)),
            }
            _logger.debug('Generated:\n{}'.format(pprint.pformat(result_info)))
            results.append(result_info)
    pargs.output.write('# Automatically generated result info\n')
    smtrunner.util.writeYaml(pargs.output, result_infos)
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
