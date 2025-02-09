# vim: set sw=4 ts=4 softtabstop=4 expandtab:
import abc
import os
import logging

_logger = logging.getLogger(__name__)


class BackendException(Exception):
    pass


class BackendResult:

    def __init__(self, exitCode, runTime, oot, oom, userCpuTime=None, sysCpuTime=None):
        self.exitCode = exitCode
        self.runTime = runTime
        self.outOfTime = oot
        self.outOfMemory = oom
        self.userCpuTime = userCpuTime
        self.sysCpuTime = sysCpuTime

        if not (isinstance(self.exitCode, int) or self.exitCode == None):
            msg = 'exitCode was expected to be an int or None but was a {}'.format(
                self.exitCode)
            _logger.error(msg)
            raise BackendException(msg)
        if not (isinstance(self.runTime, float) and self.runTime > 0.0):
            msg = 'runTime was expected be a float greater than zero but was "{}"'.format(
                self.runTime)
            _logger.error(msg)
            raise BackendException(msg)
        if not isinstance(self.outOfTime, bool):
            msg = 'outOfTime was expected to be a bool but was "{}"'.format(
                self.outOfTime)
            _logger.error(msg)
            raise BackendException(msg)
        if not isinstance(self.outOfMemory, bool):
            msg = 'outOfMemory was expected to be a bool but was "{}"'.format(
                self.outOfMemory)
            _logger.error(msg)
            raise BackendException(msg)
        if not (isinstance(self.userCpuTime, float) or self.userCpuTime == None):
            msg = ('userCpuTime was expected to be a float or None but was'
                   ' {}'.format(self.userCpuTime))
            _logger.error(msg)
            raise BackendException(msg)
        if not (isinstance(self.sysCpuTime, float) or self.sysCpuTime == None):
            msg = ('sysCpuTime was expected to be a float or None but was'
                   ' {}'.format(self.sysCpuTime))
            _logger.error(msg)
            raise BackendException(msg)


class BackendBaseClass(metaclass=abc.ABCMeta):

    def __init__(self, hostProgramPath, workingDirectory, timeLimit, memoryLimit, stackLimit, ctx, **kwargs):
        """
          hostProgramPath: Absolute path to program on host
          workingDirectory: Absolute path to the working directory on the host which must exist
          timeLimit: max time allowed in seconds. Zero implies unlimited
          memoryLimit: max memory allowed in MiB. Zero implies unlimited
          stackLimit: max stack size in KiB. Zero implies unlimited, None implies do not set
          ctx: RunnerContext
        """
        # Rely on setters for error checking
        self.hostProgramPath = hostProgramPath
        self.workingDirectory = workingDirectory
        self.timeLimit = timeLimit
        self.memoryLimit = memoryLimit
        self.stackLimit = stackLimit
        self._ctx = ctx

    @property
    def ctx(self):
        return self._ctx

    @property
    def hostProgramPath(self):
        return self._hostProgramPath

    @hostProgramPath.setter
    def hostProgramPath(self, value):
        if not (isinstance(value, str) and os.path.isabs(value)):
            raise BackendException('hostProgramPath should be an absolute path was instead "{}"'.format(
                value))
        self._hostProgramPath = value

    @property
    def workingDirectory(self):
        return self._workingDirectory

    @workingDirectory.setter
    def workingDirectory(self, value):
        if not os.path.isdir(value):
            raise BackendException(
                'workingDirectory should be an existing directory but was instead "{}"'.format(value))
        self._workingDirectory = value

    @property
    def timeLimit(self):
        return self._timeLimit

    @timeLimit.setter
    def timeLimit(self, value):
        if not (isinstance(value, int) and value >= 0):
            raise BackendException('timeLimit should be an integer >= 0. But instead was {}'.format(
                value))
        self._timeLimit = value

    @property
    def memoryLimit(self):
        return self._memoryLimit

    @memoryLimit.setter
    def memoryLimit(self, value):
        if not (isinstance(value, int) and value >= 0):
            raise BackendException('memoryLimit should be an integer >= 0. But instead was {}'.format(
                value))
        self._memoryLimit = value

    @property
    def stackLimit(self):
        return self._stackLimit

    @stackLimit.setter
    def stackLimit(self, value):
        if not ((isinstance(value, int) and value >= 0) or value == None):
            raise BackendException(
                'stackLimit should be an integer >=0 or None. But instead was {}'.format(value))
        self._stackLimit = value

    @abc.abstractproperty
    def name(self):
        pass

    @abc.abstractmethod
    def run(self, cmdLine, stdoutLogFilePath, stderrLogFilePath, envVars):
        """
          cmdLine: List of command line arguments (strings)
          stdoutLogFilePath: Absolute path to where tool standard output should be logged
          stderrLogFilePath: Absolute path to where tool standard error should be logged
          envVars: A dictionary of environment variables to set

          Returns an instance of BackendResult
        """
        pass

    @abc.abstractmethod
    def kill(self):
        """
          Kill the backend if it is running.
        """
        pass

    @abc.abstractmethod
    def programPath(self):
        """
          Returns the absolute directory path where the program
          will be located when run() is invoked.
        """
        pass

    @abc.abstractproperty
    def workingDirectoryInternal(self):
        """
          Returns the absolute path to the working directory used internally
          by the backend.
        """
        pass

    @abc.abstractmethod
    def checkToolExists(self, toolPath):
        """
        Checks that the ``toolPath`` exists in the environment that this
        backend will use. Throws an exception if the tool cannot be found
        """
        pass

    @abc.abstractmethod
    def addFileToBackend(self, path, read_only=True):
        """
          Make a file on the host available inside the backend.
          This should only be called before `run()`.
        """
        pass

    @abc.abstractmethod
    def getFilePathInBackend(self, hostPath):
        """
          Given a file with path `hostPath` that was added to
          the backend using `addFileToBackend()`.

          Return the path to file inside the backend.
        """
        pass
