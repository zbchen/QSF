# vim: set sw=4 ts=4 softtabstop=4 expandtab:
import logging
import os
from . RunnerBase import RunnerBaseClass

_logger = logging.getLogger(__name__)


class JFSException(Exception):

    def __init__(self, msg):
        # pylint: disable=super-init-not-called
        self.msg = msg


class JFS(RunnerBaseClass):
    def __init__(self, invocationInfo, workingDirectory, rc, ctx):
        # pylint: disable=too-many-branches
        _logger.debug('Initialising {}'.format(invocationInfo['benchmark']))
        super(JFS, self).__init__(invocationInfo, workingDirectory, rc, ctx)

    @property
    def name(self):
        return "JFS"

    def getResults(self):
        r = super(JFS, self).getResults()
        # wd = r['working_directory']
        # jfs_output_dir = os.path.join(wd, 'jfs-wd')
        # jfs_stats_file = os.path.join(wd, 'jfs-stats.yml')
        # r['jfs_working_directory'] = jfs_output_dir
        # r['jfs_stats_file'] = jfs_stats_file
        return r

    def run(self):
        # Build the command line
        cmdLine = [self.toolPath] + self.additionalArgs
        # TODO: Make configurable from runner
        # cmdLine.append('-output-dir=jfs-wd')
        # cmdLine.append('-keep-output-dir')
        # cmdLine.append('-stats-file=jfs-stats.yml')

        # Add the benchmark
        cmdLine.append(self.programPathArgument)

        backendResult = self.runTool(cmdLine)
        if backendResult.outOfTime:
            _logger.warning('Hard timeout hit')
def get():
    return JFS
