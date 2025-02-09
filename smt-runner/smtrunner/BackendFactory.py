# vim: set sw=4 ts=4 softtabstop=4 expandtab:
import logging
import pkgutil
import importlib
import os

_logger = logging.getLogger(__name__)


def getBackendClass(backendString):
    _logger.debug('Attempting to load backend "{}"'.format(backendString))
    # pylint: disable=unused-variable
    from . import Backends

    module = None
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Backends')
    for _, name, _ in pkgutil.iter_modules([path]):
        if name == backendString:
            # FIXME: I don't like that we have to specify "smtrunner"
            module = importlib.import_module('.' + name, 'smtrunner.Backends')

    return module.get()
