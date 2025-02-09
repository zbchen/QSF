# vim: set sw=4 ts=4 softtabstop=4 expandtab:
import logging
import os
import pprint
import traceback
import yaml


class ConfigLoaderException(Exception):

    def __init__(self, msg):
        # pylint: disable=super-init-not-called
        self.msg = msg

_logger = logging.getLogger(__name__)


def load(configFileName):
    _logger.debug('Loading config file from "{}"'.format(configFileName))

    if not os.path.exists(configFileName):
        raise ConfigLoaderException(
            'Config file "{}" does not exist'.format(configFileName))

    config = None
    with open(configFileName, 'r') as f:
        try:
            config = yaml.load(f)
        except Exception:
            raise ConfigLoaderException(
                'Caught exception whilst loading config:\n' +
                traceback.format_exc())

    # A few sanity checks
    required_top_level_keys = ['runner', 'runner_config']
    for key in required_top_level_keys:
        if not key in config:
            raise ConfigLoaderException(
                '"{}" key missing from config file "{}"'.format(
                    key,
                    configFileName))

    if not isinstance(config['runner'], str):
        raise ConfigLoaderException('Key "runner" must be a string')
    if not isinstance(config['runner_config'], dict):
        raise ConfigLoaderException(
            'Key "runner_config" must map to a dictionary')

    _logger.info('Loaded config:\n{}'.format(pprint.pformat(config)))
    return config
