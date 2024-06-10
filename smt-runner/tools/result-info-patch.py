#!/usr/bin/env python
# Copyright (c) 2017, Daniel Liew
# This file is covered by the license in LICENSE.txt
# vim: set sw=4 ts=4 softtabstop=4 expandtab:
"""
Read two result info files, patch the first with data from
the second in memory, and then write out the result.
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

def strip(prefix, path):
    if prefix == "":
        return path
    if path.startswith(prefix):
        return path[len(prefix):]

def join_path(prefix, suffix):
    if suffix.startswith('/'):
        mod_suffix = suffix[1:]
    else:
        mod_suffix = suffix
    return os.path.join(prefix, mod_suffix)


def load_yaml(arg):
    try:
        _logger.info('Loading "{}"'.format(arg.name))
        result_infos = ResultInfo.loadRawResultInfos(arg)
    except ResultInfo.ResultInfoValidationError as e:
        _logger.error('Validation error:\n{}'.format(e))
        return None
    return result_infos

def check_dir_exists(path):
    if not os.path.exists(path):
        _logger.error('"{}" does not exist'.format(path))
        return False
    if not os.path.isdir(path):
        _logger.error('"{}" is not a directory'.format(path))
        return False
    return True

def patch_ri_paths(ri, wd_dest_name):
    # HACK: This is super fragile
    assert isinstance(ri, dict)
    new_wd_dest_name = '/{}'.format(wd_dest_name)
    if ri['working_directory'] == new_wd_dest_name:
        # No patching needed
        return ri
    # Need to patch
    new_ri = ri.copy()
    new_ri['working_directory'] = new_wd_dest_name
    # Also patch stdout/stderr log file paths
    stdout_file_name = os.path.basename(new_ri['stdout_log_file'])
    stderr_file_name = os.path.basename(new_ri['stderr_log_file'])
    new_ri['stdout_log_file'] = os.path.join(new_wd_dest_name, stdout_file_name)
    new_ri['stderr_log_file'] = os.path.join(new_wd_dest_name, stderr_file_name)
    return new_ri

def create_new_working_directories(output_result_infos_wd, workdirs_to_copy):
    assert isinstance(output_result_infos_wd, str)
    assert isinstance(workdirs_to_copy, dict)
    abs_output_result_infos_wd = os.path.abspath(output_result_infos_wd)
    os.mkdir(abs_output_result_infos_wd)
    for origin, dest_name in workdirs_to_copy.items():
        dest_path = os.path.join(abs_output_result_infos_wd, dest_name)
        _logger.info('Copying "{}" to "{}"'.format(origin, dest_path))
        shutil.copytree(origin, dest_path)

def main(args):
    global _logger
    parser = argparse.ArgumentParser(description=__doc__)
    DriverUtil.parserAddLoggerArg(parser)
    parser.add_argument('original_result_infos',
                        type=argparse.FileType('r'))
    parser.add_argument('original_result_infos_wd',
                        type=str)
    parser.add_argument('patch_result_infos',
                        type=argparse.FileType('r'))
    parser.add_argument('patch_result_infos_wd',
                        type=str)
    parser.add_argument('output_result_info',
                        type=argparse.FileType('w'),
                        default=sys.stdout,
                        help='Output location for result info YAML file')
    parser.add_argument('output_result_infos_wd',
                        type=str)
    pargs = parser.parse_args(args)
    DriverUtil.handleLoggerArgs(pargs, parser)
    _logger = logging.getLogger(__name__)

    # Validate paths
    if not check_dir_exists(pargs.original_result_infos_wd):
        return 1
    original_result_infos_wd = pargs.original_result_infos_wd
    if not check_dir_exists(pargs.patch_result_infos_wd):
        return 1
    patch_result_infos_wd = pargs.patch_result_infos_wd
    if os.path.exists(pargs.output_result_infos_wd):
        _logger.error('"{}" already exists'.format(pargs.output_result_infos_wd))
        return 1
    # Load YAML files
    original_raw_results_info = load_yaml(pargs.original_result_infos)
    if original_raw_results_info is None:
        return 1
    patch_raw_result_infos = load_yaml(pargs.patch_result_infos)
    if patch_raw_result_infos is None:
        return 1
    _logger.info('Loading done')

    # Group patch results by key for look-up
    key_to_patch_result = dict()
    for ri in patch_raw_result_infos['results']:
        key = ResultInfoUtil.get_result_info_key(ri)
        assert key not in key_to_patch_result
        key_to_patch_result[key] = ri

    # Construct new results info
    new_rri = original_raw_results_info.copy() # shallow copy
    new_results = []
    new_rri['results'] = new_results
     # Absolute paths to copy into new working directory map to destination name
    workdirs_to_copy = dict()

    used_keys = set()
    used_dest_names = set()
    patch_count = 0
    _logger.info('Constructing new results')
    for ri in original_raw_results_info['results']:
        key = ResultInfoUtil.get_result_info_key(ri)
        assert key not in used_keys
        ri_to_use = None
        wd_path_prefix = None
        wd_dest_name = None
        if key in key_to_patch_result:
            ri_to_use = key_to_patch_result[key]
            wd_path_prefix = patch_result_infos_wd
            # HACK: Good enough to avoid name collision
            wd_dest_name = os.path.basename(ri_to_use['working_directory']) + "_patched"
            patch_count += 1
        else:
            ri_to_use = ri
            wd_path_prefix = original_result_infos_wd
            wd_dest_name = os.path.basename(ri_to_use['working_directory'])
        wd_path = join_path(wd_path_prefix, ri_to_use['working_directory'])
        if not check_dir_exists(wd_path):
            return 1
        assert wd_path not in workdirs_to_copy
        # Patch paths if necessary
        ri_to_use = patch_ri_paths(ri_to_use, wd_dest_name)
        assert wd_dest_name not in used_dest_names
        workdirs_to_copy[wd_path] = wd_dest_name
        new_results.append(ri_to_use)
        used_keys.add(key)
        used_dest_names.add(wd_dest_name)

    # Compute new results to add
    _logger.info('Adding new results')
    add_count = 0
    new_keys = set(key_to_patch_result.keys()).difference(used_keys)
    for key in new_keys:
        add_count += 1
        new_results.append(key_to_patch_result[key])

    print("# of patched results: {}".format(patch_count))
    print("# of new results: {}".format(add_count))

    # Output the new results as YAML
    # Validate against schema
    try:
        _logger.info('Validating result_infos')
        ResultInfo.validateResultInfos(new_rri)
    except ResultInfo.ResultInfoValidationError as e:
        _logger.error('Validation error:\n{}'.format(e))
        return 1
    _logger.info('Validation complete')
    _logger.info('Writing to "{}"'.format(pargs.output_result_info.name))
    smtrunner.util.writeYaml(pargs.output_result_info, new_rri)
    _logger.info('Writing done')

    # Now create the new working directory by copying from other directories
    create_new_working_directories(pargs.output_result_infos_wd, workdirs_to_copy)
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
