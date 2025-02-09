# vim: set sw=4 ts=4 softtabstop=4 expandtab:
import logging
import os
from . RunnerBase import RunnerBaseClass

_logger = logging.getLogger(__name__)


class OL1V3RRunnerException(Exception):

    def __init__(self, msg):
        # pylint: disable=super-init-not-called
        self.msg = msg


class OL1V3RRunner(RunnerBaseClass):
    def __init__(self, invocationInfo, workingDirectory, rc, ctx):
        # pylint: disable=too-many-branches
        _logger.debug('Initialising {}'.format(invocationInfo['benchmark']))
        super(OL1V3RRunner, self).__init__(invocationInfo, workingDirectory, rc, ctx)

    @property
    def name(self):
        return "OL1V3R"

    def getResults(self):
        r = super(OL1V3RRunner, self).getResults()
        return r

    def run(self):
        # Build the command line
        cmdLine = [self.toolPath] + self.additionalArgs

        cmdLine.append(self.programPathArgument)

        backendResult = self.runTool(cmdLine)
        if backendResult.outOfTime:
            _logger.warning('Hard timeout hit')
def get():
    return OL1V3RRunner
