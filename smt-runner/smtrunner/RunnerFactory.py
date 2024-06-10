# vim: set sw=4 ts=4 softtabstop=4 expandtab:
import logging
import pkgutil
import importlib
import os

_logger = logging.getLogger(__name__)


def getRunnerClass(runnerString):
    _logger.info('Attempting to load runner "{}"'.format(runnerString))
    # pylint: disable=unused-variable
    from . import Runners

    module = None
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Runners')
    for _, name, _ in pkgutil.iter_modules([path]):
        if name == runnerString:
            # FIXME: I don't like that we have to specify "smtrunner"
            module = importlib.import_module('.' + name, 'smtrunner.Runners')

    try:
        return module.get()
    except AttributeError:
        raise Exception('Failed to load runner "{}"'.format(runnerString))
