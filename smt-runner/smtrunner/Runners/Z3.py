# vim: set sw=4 ts=4 softtabstop=4 expandtab:
import logging
import os
from . RunnerBase import RunnerBaseClass

_logger = logging.getLogger(__name__)


class Z3RunnerException(Exception):

    def __init__(self, msg):
        # pylint: disable=super-init-not-called
        self.msg = msg


class Z3Runner(RunnerBaseClass):
    def __init__(self, invocationInfo, workingDirectory, rc, ctx):
        # pylint: disable=too-many-branches
        _logger.debug('Initialising {}'.format(invocationInfo['benchmark']))
        super(Z3Runner, self).__init__(invocationInfo, workingDirectory, rc, ctx)

    @property
    def name(self):
        return "Z3"

    def getResults(self):
        r = super(Z3Runner, self).getResults()
        return r

    def run(self):
        # Build the command line
        cmdLine = [self.toolPath] + self.additionalArgs

        # Add the benchmark
        # This `--` is so that Z3 knows that option
        # parsing should finish and that the remaining
        # arguments are literal file names. We need this
        # for strangely named files (e.g. file with `=`
        # in its name).
        cmdLine.append('--')
        cmdLine.append(self.programPathArgument)

        backendResult = self.runTool(cmdLine)
        if backendResult.outOfTime:
            _logger.warning('Hard timeout hit')
def get():
    return Z3Runner
