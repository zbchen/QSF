# Copyright (c) 2017, Daniel Liew
# This file is covered by the license in LICENSE.txt
# vim: set sw=4 ts=4 softtabstop=4 expandtab:
import collections
import copy
import os
import logging
import jsonschema
from . import util

_logger = logging.getLogger(__name__)

class ResultInfo:
    def __init__(self, data):
        assert isinstance(data, dict)
        self._data = data

    def isError(self):
        return 'error' in self._data

    def GetInternalRepr(self):
        return self._data

    @property
    def benchmark(self):
        return self._data['benchmark']
    # TODO: Implement property getters


class ResultInfoValidationError(Exception):
    def __init__(self, message, absoluteSchemaPath=None):
        # pylint: disable=super-init-not-called
        assert isinstance(message, str)
        if absoluteSchemaPath != None:
            assert isinstance(absoluteSchemaPath, collections.deque)
        self.message = message
        self.absoluteSchemaPath = absoluteSchemaPath
    def __str__(self):
        return self.message


def loadResultInfos(openFile, auto_upgrade=True):
    resultInfos = loadRawResultInfos(openFile, auto_upgrade)
    miscData = None
    resultInfoObjects = []
    for r in resultInfos['results']:
        resultInfoObjects.append(ResultInfo(r))
    if 'misc' in resultInfos:
        miscData = resultInfos['misc']
    return (resultInfoObjects, miscData)


def loadRawResultInfos(openFile, auto_upgrade=True):
    resultInfos = util.loadYaml(openFile)
    if auto_upgrade:
        resultInfos = upgradeResultInfosToSchema(resultInfos)
    validateResultInfos(resultInfos)
    return resultInfos


def getSchema():
    """
      Return the Schema for ResultInfo files.
    """
    yamlFile = os.path.join(os.path.dirname(__file__), 'ResultInfoSchema.yml')
    schema = None
    with open(yamlFile, 'r') as f:
        schema = util.loadYaml(f)
    assert isinstance(schema, dict)
    assert '__version__' in schema
    return schema


def validateResultInfos(resultInfos, schema=None):
    """
      Validate a ``resultInfo`` file.
      Will throw a ``ResultInfoValidationError`` exception if
      something is wrong
    """
    assert isinstance(resultInfos, dict)
    if schema is None:
        schema = getSchema()
    assert isinstance(schema, dict)
    assert '__version__' in schema

    # Even though the schema validates this field in the resultInfo we need to
    # check them ourselves first because if the schema version we have doesn't
    # match then we can't validate using it.
    if 'schema_version' not in resultInfos:
        raise ResultInfoValidationError(
            "'schema_version' is missing")
    if not isinstance(resultInfos['schema_version'], int):
        raise ResultInfoValidationError(
            "'schema_version' should map to an integer")
    if not resultInfos['schema_version'] >= 0:
        raise ResultInfoValidationError(
            "'schema_version' should map to an integer >= 0")
    if resultInfos['schema_version'] != schema['__version__']:
        # pylint: disable=bad-continuation
        raise ResultInfoValidationError(
            ('Schema version used by benchmark ({}) does not match' +
             ' the currently support schema ({})').format(
                resultInfos['schema_version'],
                schema['__version__']))

    # Validate against the schema
    try:
        jsonschema.validate(resultInfos, schema)
    except jsonschema.exceptions.ValidationError as e:
        raise ResultInfoValidationError(
            str(e),
            e.absolute_schema_path)
    return


def upgradeResultInfosToVersion(resultInfos, schemaVersion):
    """
      Upgrade invocation info to a particular schemaVersion. This
      does not validate it against the schema.
    """
    assert isinstance(resultInfos, dict)
    assert isinstance(schemaVersion, int)
    schemaVersionUsedByInstance = resultInfos['schema_version']
    assert isinstance(schemaVersionUsedByInstance, int)
    assert schemaVersionUsedByInstance >= 0
    assert schemaVersion >= 0
    newResultInfo = copy.deepcopy(resultInfos)

    if schemaVersionUsedByInstance == schemaVersion:
        # Nothing todo
        return newResultInfo
    elif schemaVersionUsedByInstance > schemaVersion:
        raise Exception(
            'Cannot downgrade benchmark specification to older schema')

    # TODO: Add more upgrade steps
    if schemaVersionUsedByInstance == schemaVersion:
        # Done
        return newResultInfo

    raise NotImplementedError("Schema upgrade not implemented. Want {} but have {}".format(
        schemaVersion,
        schemaVersionUsedByInstance))

def upgradeResultInfosToSchema(resultInfos, schema=None):
    """
      Upgrade a ``resultInfo`` to the specified ``schema``.
    """
    if schema is None:
        schema = getSchema()
    assert '__version__' in schema
    assert 'schema_version' in resultInfos

    newResultInfos = upgradeResultInfosToVersion(
        resultInfos,
        schema['__version__']
    )
    return newResultInfos

