# vim: set sw=4 ts=4 softtabstop=4 expandtab:
import logging
import os
from . RunnerBase import RunnerBaseClass

_logger = logging.getLogger(__name__)


class BitwuzlaRunnerException(Exception):

    def __init__(self, msg):
        # pylint: disable=super-init-not-called
        self.msg = msg


class BitwuzlaRunner(RunnerBaseClass):
    def __init__(self, invocationInfo, workingDirectory, rc, ctx):
        # pylint: disable=too-many-branches
        _logger.debug('Initialising {}'.format(invocationInfo['benchmark']))
        super(BitwuzlaRunner, self).__init__(invocationInfo, workingDirectory, rc, ctx)

    @property
    def name(self):
        return "Bitwuzla"

    def getResults(self):
        r = super(BitwuzlaRunner, self).getResults()
        return r

    def run(self):
        # Build the command line
        cmdLine = [self.toolPath] + self.additionalArgs

        cmdLine.append(self.programPathArgument)

        backendResult = self.runTool(cmdLine)
        if backendResult.outOfTime:
            _logger.warning('Hard timeout hit')
def get():
    return BitwuzlaRunner
