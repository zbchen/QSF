#!/usr/bin/env python
# vim: set sw=4 ts=4 softtabstop=4 expandtab:
"""
    Script to run a Runner over a set of programs.
"""
import argparse
import datetime
import logging
import os
import traceback
import signal
import sys
from smtrunner import RunnerFactory
from smtrunner import DriverUtil
from smtrunner import ResultInfo
from smtrunner import RunnerContext

_logger = None
futureToRunners = None


def handleInterrupt(signum, _):
    logging.info('Received signal {}'.format(signum))
    if futureToRunners != None:
        cancel(futureToRunners)


def cancel(futureToRunnersMap):
    _logger.warning('Cancelling futures')
    # Cancel all futures first. If we tried
    # to kill the runner at the same time then
    # other futures would start which we don't want
    for future in futureToRunnersMap.keys():
        future.cancel()

    # Then we can kill the runners if required
    _logger.warning('Killing runners')
    for runner_list in futureToRunnersMap.values():
        if isinstance(runner_list, list):
            for runner in runner_list:
                runner.kill()
        else:
            assert isinstance(runner_list, SequentialRunnerHolder)
            runner_list.kill()

def check_paths(invocation_infos, benchmark_base_path):
    if len(invocation_infos['results']) < 1:
        logging.error('List of jobs cannot be empty')
        return False

    # Check the benchmarks can be found
    for r in invocation_infos['results']:
        benchmark = r['benchmark']
        benchmark_full_path = os.path.join(benchmark_base_path, benchmark)
        if not os.path.exists(benchmark_full_path):
            _logger.error('Cannot find benchmark "{}"'.format(benchmark_full_path))
            return False
    return True

def entryPoint(args):
    # pylint: disable=global-statement,too-many-branches,too-many-statements
    # pylint: disable=too-many-return-statements
    global _logger, futureToRunners
    parser = argparse.ArgumentParser(description=__doc__)
    DriverUtil.parserAddLoggerArg(parser)
    parser.add_argument("--benchmark-base",
        dest='benchmark_base_path',
        type=str,
        default="",
        help="Prefix path for benchmarks")
    parser.add_argument("--dry", action='store_true',
                        help="Stop after initialising runners")
    parser.add_argument(
        "-j",
        "--jobs",
        type=int,
        default="1",
        help="Number of jobs to run in parallel (Default %(default)s)")
    parser.add_argument("config_file", help="YAML configuration file")
    parser.add_argument("invocation_info", help="Invocation info file")
    parser.add_argument("working_dirs_root",
                        help="Directory to create working directories inside")
    parser.add_argument("yaml_output", help="path to write YAML output to")

    pargs = parser.parse_args(args)

    DriverUtil.handleLoggerArgs(pargs, parser)
    _logger = logging.getLogger(__name__)

    if pargs.jobs <= 0:
        _logger.error('jobs must be <= 0')
        return 1

    # Check benchmark base path
    if not os.path.isabs(pargs.benchmark_base_path):
        pargs.benchmark_base_path = os.path.abspath(pargs.benchmark_base_path)
    if not os.path.isdir(pargs.benchmark_base_path):
        _logger.error('Benchmark base path "{}" must be a directory'.format(pargs.benchmark_base_path))
        return 1
    if not os.path.isabs(pargs.benchmark_base_path):
        _logger.error('Benchmark base path "{}" must be absolute'.format(pargs.benchmark_base_path))
        return 1

    # Load runner configuration
    config, success = DriverUtil.loadRunnerConfig(pargs.config_file)
    if not success:
        return 1

    # Load invocation info
    try:
        with open(pargs.invocation_info, 'r') as f:
            # FIXME: Do name clean up invocation info and result info are now the same thing
            invocation_infos = ResultInfo.loadRawResultInfos(f)
    except Exception as e: # pylint: disable=broad-except
        _logger.error(e)
        _logger.debug(traceback.format_exc())
        return 1

    if not check_paths(invocation_infos, pargs.benchmark_base_path):
        _logger.error('Problems with invocation infos')
        return 1

    # Misc data we will put into output result info file.
    output_misc_data = {
        'runner': config['runner'],
        'backend': config['runner_config']['backend']['name'],
        'jobs_in_parallel': pargs.jobs,
    }
    if 'misc' not in invocation_infos:
        invocation_infos['misc'] = {}
    invocation_infos['misc'].update(output_misc_data)
    output_misc_data = invocation_infos['misc']


    yamlOutputFile = os.path.abspath(pargs.yaml_output)

    if os.path.exists(yamlOutputFile):
        _logger.error(
            'yaml_output file ("{}") already exists'.format(yamlOutputFile))
        return 1

    # Setup the directory to hold working directories
    workDirsRoot = os.path.abspath(pargs.working_dirs_root)
    if os.path.exists(workDirsRoot):
        # Check its a directory and its empty
        if not os.path.isdir(workDirsRoot):
            _logger.error(
                '"{}" exists but is not a directory'.format(workDirsRoot))
            return 1

        workDirsRootContents = next(os.walk(workDirsRoot, topdown=True))
        if len(workDirsRootContents[1]) > 0 or len(workDirsRootContents[2]) > 0:
            _logger.error('"{}" is not empty ({},{})'.format(
                workDirsRoot,
                workDirsRootContents[1],
                workDirsRootContents[2]))
            return 1
    else:
        # Try to create the working directory
        try:
            os.mkdir(workDirsRoot)
        except Exception as e: # pylint: disable=broad-except
            _logger.error(
                'Failed to create working_dirs_root "{}"'.format(workDirsRoot))
            _logger.error(e)
            _logger.debug(traceback.format_exc())
            return 1

    # Get Runner class to use
    RunnerClass = RunnerFactory.getRunnerClass(config['runner'])
    runner_ctx = RunnerContext.RunnerContext(num_parallel_jobs=pargs.jobs)

    if not 'runner_config' in config:
        _logger.error('"runner_config" missing from config')
        return 1

    if not isinstance(config['runner_config'], dict):
        _logger.error('"runner_config" should map to a dictionary')
        return 1

    rc = config['runner_config']

    # Create the runners
    runners = []
    for index, invocationInfo in enumerate(invocation_infos['results']):
        _logger.info('Creating runner {} out of {} ({:.1f}%)'.format(
            index + 1,
            len(invocation_infos['results']),
            100 * float(index + 1) / len(invocation_infos['results'])))
        # Create working directory for this runner
        # FIXME: This should be moved into the runner itself
        workDir = os.path.join(workDirsRoot, 'workdir-{}'.format(index))
        assert not os.path.exists(workDir)
        try:
            os.mkdir(workDir)
        except Exception as e: # pylint: disable=broad-except
            _logger.error(
                'Failed to create working directory "{}"'.format(workDir))
            _logger.error(e)
            _logger.debug(traceback.format_exc())
            return 1
        # Pass in a copy of rc so that if a runner accidently modifies
        # a config it won't affect other runners.
        rc_copy=rc.copy()
        rc_copy['benchmark_base_path'] = pargs.benchmark_base_path
        rc_copy['output_base_path'] = workDirsRoot
        runners.append(RunnerClass(invocationInfo, workDir, rc_copy, runner_ctx))

    # Run the runners and build the report
    reports = []
    exitCode = 0

    if pargs.dry:
        _logger.info('Not running runners')
        return exitCode

    startTime = datetime.datetime.now()
    _logger.info('Starting {}'.format(startTime.isoformat(' ')))
    output_misc_data['start_time'] = str(startTime.isoformat(' '))

    if pargs.jobs == 1:
        _logger.info('Running jobs sequentially')
        for r in runners:
            try:
                r.run()
                reports.append(r.getResults())
            except KeyboardInterrupt:
                _logger.error('Keyboard interrupt')
                # This is slightly redundant because the runner
                # currently kills itself if KeyboardInterrupt is thrown
                r.kill()
                break
            except Exception: # pylint: disable=broad-except
                _logger.error("Error handling:{}".format(r.program))
                _logger.error(traceback.format_exc())

                # Attempt to add the error to the reports
                errorLog = r.InvocationInfo.copy()
                errorLog['error'] = traceback.format_exc()
                reports.append(errorLog)
                exitCode = 1
    else:
        # FIXME: Make windows compatible
        # Catch signals so we can clean up
        signal.signal(signal.SIGINT, handleInterrupt)
        signal.signal(signal.SIGTERM, handleInterrupt)

        _logger.info('Running jobs in parallel')
        completedFutureCounter = 0
        import concurrent.futures
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=pargs.jobs) as executor:
                # Simple: One runner to one future mapping.
                futureToRunners = {executor.submit(r.run): [r] for r in runners}
                for future in concurrent.futures.as_completed(futureToRunners):
                    completed_runner_list = None
                    if isinstance(futureToRunners[future], list):
                        completed_runner_list = futureToRunners[future]
                    else:
                        assert isinstance(futureToRunners[future], SequentialRunnerHolder)
                        completed_runner_list = futureToRunners[future].completed_runs()
                    for r in completed_runner_list:
                        _logger.debug('{} runner finished'.format(
                            r.programPathArgument))

                        if future.done() and not future.cancelled():
                            completedFutureCounter += 1
                            _logger.info('Completed {}/{} ({:.1f}%)'.format(
                                completedFutureCounter,
                                len(runners),
                                100 * (float(completedFutureCounter) / len(runners))
                                ))

                        excep = None
                        try:
                            if future.exception():
                                excep = future.exception()
                        except concurrent.futures.CancelledError as e:
                            excep = e

                        if excep != None:
                            # Attempt to log the error reports
                            errorLog = r.InvocationInfo.copy()
                            r_work_dir = None
                            try:
                                r_work_dir = r.workingDirectoryWithoutPrefix
                            except Exception:
                                pass
                            errorLog['working_directory'] = r_work_dir
                            errorLog['error'] = "\n".join(
                                traceback.format_exception(
                                    type(excep),
                                    excep,
                                    None))
                            # Only emit messages about exceptions that aren't to do
                            # with cancellation
                            if not isinstance(excep, concurrent.futures.CancelledError):
                                _logger.error('{} runner hit exception:\n{}'.format(
                                    r.programPathArgument, errorLog['error']))
                            reports.append(errorLog)
                            exitCode = 1
                        else:
                            reports.append(r.getResults())
        except KeyboardInterrupt:
            # The executor should of been cleaned terminated.
            # We'll then write what we can to the output YAML file
            _logger.error('Keyboard interrupt')
        finally:
            # Stop catching signals and just use default handlers
            signal.signal(signal.SIGINT, signal.SIG_DFL)
            signal.signal(signal.SIGTERM, signal.SIG_DFL)

    endTime = datetime.datetime.now()
    output_misc_data['end_time'] = str(endTime.isoformat(' '))
    output_misc_data['run_time'] = str(endTime- startTime)

    # Write result to YAML file
    invocation_infos['results'] = reports
    DriverUtil.writeYAMLOutputFile(yamlOutputFile, invocation_infos)

    _logger.info('Finished {}'.format(endTime.isoformat(' ')))
    _logger.info('Total run time: {}'.format(endTime - startTime))
    return exitCode

if __name__ == '__main__':
    sys.exit(entryPoint(sys.argv[1:]))
