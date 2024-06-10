# vim: set sw=4 ts=4 softtabstop=4 expandtab:
import abc
import copy
import logging
import os
import pprint
import psutil
import re
import shutil
import sys
import time
import traceback
import threading
from .. import BackendFactory
from .. import RunnerContext

_logger = logging.getLogger(__name__)


class RunnerBaseException(Exception):

    def __init__(self, msg):
        self.msg = msg


class RunnerBaseClass(metaclass=abc.ABCMeta):
    staticCounter = 0

    def _checkProgramPath(self):
        if not os.path.isabs(self.program):
            raise RunnerBaseException(
                'Program ("{}") must be absolute path'.format(self.program))

        if not os.path.exists(self.program):
            raise RunnerBaseException(
                'Program ("{}") does not exist'.format(self.program))

    def _setupWorkingDirectory(self, workingDirectory):
        self.workingDirectory = workingDirectory
        if not os.path.isabs(self.workingDirectory):
            raise RunnerBaseException(
                'working directory "{}" must be an absolute path'.format(self.workingDirectory))

        if not os.path.exists(self.workingDirectory):
            raise RunnerBaseException(
                'working directory "{}" does not exist'.format(self.workingDirectory))

        if not os.path.isdir(self.workingDirectory):
            raise RunnerBaseException(
                'Specified working directory ("{}") is not a directory'.format(self.workingDirectory))

        # Check the directory is empty
        firstLevel = next(os.walk(self.workingDirectory, topdown=True))
        if len(firstLevel[1]) > 0 or len(firstLevel[2]) > 0:
            raise RunnerBaseException(
                'working directory "{}" is not empty'.format(self.workingDirectory))

    def _setupMaxMemory(self, rc):
        try:
            self.maxMemoryInMiB = rc['max_memory']
        except KeyError:
            _logger.info(
                '"max_memory" not specified, assuming no tool memory limit')
            self.maxMemoryInMiB = 0

        if self.maxMemoryInMiB < 0:
            raise RunnerBaseException('"max_memory" must be > 0')

    def _setupMaxTime(self, rc):
        try:
            self.maxTimeInSeconds = rc['max_time']
        except KeyError:
            _logger.info('"max_time" not specified, assuming no tool timeout')
            self.maxTimeInSeconds = 0

        if self.maxTimeInSeconds < 0:
            raise RunnerBaseException('"max_time" must be > 0')

    def _setupAdditionalArgs(self, rc):
        self.additionalArgs = []
        if 'additional_args' in rc:
            if not isinstance(rc['additional_args'], list):
                raise RunnerBaseException('"additional_args" should be a list')

            for arg in rc['additional_args']:
                if not isinstance(arg, str):
                    raise RunnerBaseException(
                        'Found additional argument that is not a string')

                self.additionalArgs.append(arg)

    def _setupEnvironmentVariables(self, rc):
        # Set environment variables
        self.toolEnvironmentVariables = {}
        if 'env' in rc:
            if not isinstance(rc['env'], dict):
                raise RunnerBaseException('"env" must map to a dictionary')

            # Go through each key, value pair making sure they are the right
            # type
            for key, value in rc['env'].items():
                if not isinstance(key, str):
                    raise RunnerBaseException(
                        'key "{}" must be a string'.format(key))

                if not isinstance(value, str):
                    raise RunnerBaseException(
                        'Value for key "{}" must be a string'.format(key))

                self.toolEnvironmentVariables[key] = value

    def _setupStackSize(self, rc):
        try:
            self._stackSize = rc['stack_size']
            if isinstance(self._stackSize, str):
                if self._stackSize != 'unlimited':
                    raise RunnerBaseException(
                        'If "stack_size" maps to a string it must be set to "unlimited"')
            elif isinstance(self._stackSize, int):
                if self._stackSize <= 0:
                    raise RunnerBaseException(
                        '"stack_size" must be greater than 0')
            else:
                raise RunnerBaseException('"stack_size" has unexpected type')
        except KeyError:
            self._stackSize = None

    def _setupToolPath(self, rc):
        if not 'tool_path' in rc:
            raise RunnerBaseException(
                '"tool_path" missing from "runner_config"')

        self.toolPath = os.path.expanduser(rc['tool_path'])
        if not os.path.isabs(self.toolPath):
            raise RunnerBaseException('"tool_path" must be an absolute path')

    def _setupBackend(self, rc):
        default = "PythonPsUtil"
        if not 'backend' in rc:
            backendName = default
            _logger.warning(
                'Backend not specified, using default backend "{}"'.format(default))
            backendSpecificOptions = {}
        else:
            backendDict = rc['backend']
            if not isinstance(backendDict, dict):
                raise RunnerBaseException(
                    '"backend" key must map to a dictionary')
            try:
                backendName = backendDict['name']
                if not isinstance(backendName, str):
                    raise RunnerBaseException(
                        'backend "name" must be a string')
            except KeyError:
                raise RunnerBaseException(
                    '"name" key missing inside "backend"')

            # Backend specific options are optional
            backendSpecificOptions = backendDict.get('config', {})

        if not isinstance(backendSpecificOptions, dict):
            raise RunnerBaseException('"config" must map to a dictionary')

        # Check the keys of the backendSpecificOptions are strings
        for key in backendSpecificOptions.keys():
            if not isinstance(key, str):
                raise RunnerBaseException(
                    'The keys in "config" must be strings')

        self._backend = None
        backendClass = BackendFactory.getBackendClass(backendName)
        self._backend = backendClass(hostProgramPath=self._programPathOnHostToUse,
                                     workingDirectory=self.workingDirectory,
                                     timeLimit=self.maxTimeInSeconds,
                                     memoryLimit=self.maxMemoryInMiB,
                                     stackLimit=0 if self._stackSize == 'unlimited' else self._stackSize,
                                     ctx=self._ctx,
                                     **backendSpecificOptions)
        self._checkToolExistsInBackend()

    def _checkToolExistsInBackend(self):
        # Check the tool exists in the backend.
        # This is provided as a method so sub-classes can override this
        # behaviour.
        self._backend.checkToolExists(self.toolPath)

    def _readConfig(self, rc):
        if not isinstance(rc, dict):
            raise RunnerBaseException(
                'Config passed to runner must be a dictionary')

        self._setupToolPath(rc)
        self._setupMaxMemory(rc)
        self._setupMaxTime(rc)
        self._setupAdditionalArgs(rc)
        self._setupEnvironmentVariables(rc)
        self._setupStackSize(rc)

    @property
    def _programPathOnHostToUse(self):
        return self.program

    @property
    def InvocationInfo(self):
        return self._invocationInfo

    # FIXME: Rename to benchmark
    @property
    def program(self):
        return os.path.join(self._benchmark_base_path, self._invocationInfo['benchmark'])

    def _setupBasePaths(self, rc):
        if 'benchmark_base_path' not in rc:
            raise Z3RunnerException('"benchmark_base_path" not in rc')
        self._benchmark_base_path = rc['benchmark_base_path']
        if 'output_base_path' not in rc:
            raise Z3RunnerException('"output_base_path" not in rc')
        self._output_base_path = rc['output_base_path']

    _initLock = threading.Lock()

    def __init__(self, invocationInfo, workingDirectory, rc, ctx):
        with RunnerBaseClass._initLock:
            _logger.debug('Initialising {}'.format(invocationInfo['benchmark']))

            # Unique ID (we assume this constructor is never called in
            # parallel)
            self.uid = RunnerBaseClass.staticCounter
            RunnerBaseClass.staticCounter += 1

            self._backendResult = None
            self._invocationInfo = invocationInfo

            self._setupBasePaths(rc)
            self._checkProgramPath()
            self._setupWorkingDirectory(workingDirectory)

            self._readConfig(rc)
            self._ctx = ctx
            assert isinstance(self._ctx, RunnerContext.RunnerContext)
            self._setupBackend(rc)

    @property
    def stdoutLogFile(self):
        return os.path.join(self.workingDirectory, 'stdout.log.txt')

    @property
    def stderrLogFile(self):
        return os.path.join(self.workingDirectory, 'stderr.log.txt')

    @abc.abstractmethod
    def run(self):
        pass

    @property
    def ranOutOfMemory(self):
        """
          Return True if the tool ran out of memory
          Return False if the tool did not run out of memory
          Return None if this could not be determined
        """
        return self._backendResult.outOfMemory

    @property
    def exitCode(self):
        return self._backendResult.exitCode

    @property
    def runTime(self):
        # Wallclock time
        return self._backendResult.runTime
    
    def stripBasePath(self, path):
        assert path.startswith(self._output_base_path)
        return path[len(self._output_base_path):]

    def getResults(self):
        results = self.InvocationInfo.copy()
        assert isinstance(results, dict)
        results['wallclock_time'] = self.runTime
        results['working_directory'] = self.stripBasePath(self.workingDirectory)
        results['exit_code'] = self.exitCode
        results['out_of_memory'] = self.ranOutOfMemory
        results['stdout_log_file'] = self.stripBasePath(self.stdoutLogFile)
        results['stderr_log_file'] = self.stripBasePath(self.stderrLogFile)
        results['user_cpu_time'] = self._backendResult.userCpuTime
        results['sys_cpu_time'] = self._backendResult.sysCpuTime
        results['backend_timeout'] = self._backendResult.outOfTime
        # TODO: Set sat field and copy other fields over
        return results

    @abc.abstractproperty
    def name(self):
        pass

    @property
    def programPathArgument(self):
        """
          This the argument to pass to the tool when running.
          This should be used instead of ``self.program`` because
          this property takes into account the backend being used.
        """
        return self._backend.programPath()

    @property
    def workingDirectoryInBackend(self):
        """
          This should be used if it is necessary to know the working
          directory path inside the environment of the backend
        """
        return self._backend.workingDirectoryInternal

    @property
    def workingDirectoryWithoutPrefix(self):
        return self.stripBasePath(selft.workingDirectory)

    def kill(self, pause=0.0):
        """
        Subclasses need to override this if their
        run() method doesn't use runTool()
        """
        _logger.debug('Trying to kill {}'.format(self.name))
        self._backend.kill()

    def runTool(self, cmdLine, envExtra={}):
        env = {}
        env.update(self.toolEnvironmentVariables)
        env.update(envExtra)  # These take precendence

        _logger.info('Running:\n{}\nwith env:{}'.format(
            pprint.pformat(cmdLine),
            pprint.pformat(env)))

        # Run the tool
        self._backendResult = self._backend.run(
            cmdLine,
            self.stdoutLogFile,
            self.stderrLogFile,
            env)
        return self._backendResult

    @property
    def ctx(self):
        return self._ctx
