# vim: set sw=4 ts=4 softtabstop=4 expandtab:
import logging
import os
from . RunnerBase import RunnerBaseClass

_logger = logging.getLogger(__name__)


class qSATBitwuzlaException(Exception):

    def __init__(self, msg):
        # pylint: disable=super-init-not-called
        self.msg = msg


class qSATBitwuzla(RunnerBaseClass):
    def __init__(self, invocationInfo, workingDirectory, rc, ctx):
        # pylint: disable=too-many-branches
        _logger.debug('Initialising {}'.format(invocationInfo['benchmark']))
        super(qSATBitwuzla, self).__init__(invocationInfo, workingDirectory, rc, ctx)

    @property
    def name(self):
        return "goSATBitwuzla"

    def getResults(self):
        r = super(qSATBitwuzla, self).getResults()
        return r

    def run(self):
        # Build the command line
        cmdLine = [self.toolPath] + self.additionalArgs

        # Add the benchmark
        cmdLine.append(self.programPathArgument)

        backendResult = self.runTool(cmdLine)
        if backendResult.outOfTime:
            _logger.warning('Hard timeout hit')
def get():
    return qSATBitwuzla
