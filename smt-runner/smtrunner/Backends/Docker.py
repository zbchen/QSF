# vim: set sw=4 ts=4 softtabstop=4 expandtab:
from . BackendBase import *
import functools
import logging
import os
import pprint
import time
import psutil
import threading
import traceback
import requests.exceptions
import json
_logger = logging.getLogger(__name__)


class DockerBackendException(BackendException):
    pass

try:
    import docker
except ImportError:
    raise DockerBackendException(
        'Could not import docker module from docker-py')

# Pool of resources.
# FIXME: Refactor docker stuff out of this so PythonPsUtilBackend can
# share this
# FIXME: We need a way to close all the clients when all runners
# finish.
class ResourcePool:
    """
        Resource pool for DockerBackend. It contains a set of resources
        that can be acquired and returned. These resources include

        * DockerClient
        * CPUs
    """
    def __init__(self, num_jobs, available_cpu_ids, cpus_per_job, use_memset_of_nearest_node, docker_api_timeout=120, docker_api_version='1.26'):
        assert isinstance(num_jobs, int)
        assert num_jobs > 0
        assert isinstance(available_cpu_ids, set) or available_cpu_ids is None
        assert isinstance(cpus_per_job, int) or cpus_per_job is None
        if cpus_per_job is not None:
            assert cpus_per_job > 0
        if available_cpu_ids is not None:
            assert len(available_cpu_ids) > 0
        assert isinstance(use_memset_of_nearest_node, bool) or use_memset_of_nearest_node is None
        self._num_jobs = num_jobs
        self._available_cpu_ids = available_cpu_ids
        self._cpus_per_job = cpus_per_job
        self._use_memset_of_nearest_node = use_memset_of_nearest_node

        # Docker client data structures
        self._docker_clients = dict() # All created clients
        self._docker_client_pool = set() # Available clients
        self._docker_api_timeout = docker_api_timeout
        self._docker_api_version = docker_api_version
        assert isinstance(self._docker_api_timeout, int)
        assert isinstance(self._docker_api_version, str)

        # CPU and memset data structures
        self._numa_nodes = dict() # Maps NUMA node to set of CPU ids
        self._numa_node_pool = dict() # Maps NUMa node to set of available CPU ids

        self._lock = threading.Lock()

        # Sanity check
        if cpus_per_job is not None and available_cpu_ids is not None:
            assert (num_jobs * cpus_per_job) <= len(available_cpu_ids)

    def _lazy_docker_client_init(self):
        # Implicitly assume lock is already held
        if len(self._docker_clients) != 0:
            # Init already happenend
            return
        # Create Docker clients
        _logger.info('Using Docker API timeout of {} seconds'.format(self._docker_api_timeout))
        _logger.info('Using Docker API version {}'.format(self._docker_api_version))
        for index in range(0, self._num_jobs):
            _logger.info('Creating DockerClient {}'.format(index))
            new_client = docker.APIClient(version=self._docker_api_version, timeout=self._docker_api_timeout)
            self._docker_clients[id(new_client)] = new_client
            # Add to pool
            self._docker_client_pool.add(id(new_client))

        assert len(self._docker_clients) == len(self._docker_client_pool)

    def get_docker_client(self):
        with self._lock:
            self._lazy_docker_client_init()
            try:
                docker_client_id = self._docker_client_pool.pop()
            except Exception as e:
                _logger.error('Failed to get client from pool')
                _logger.error(e)
                raise e
            return self._docker_clients[docker_client_id]

    def release_docker_client(self, docker_client):
        with self._lock:
            self._lazy_docker_client_init()
            if id(docker_client) not in self._docker_clients:
                raise DockerBackendException('Invalid client released back to pool')
            if id(docker_client) in self._docker_client_pool:
                raise DockerBackendException('Returned client is already in pool')
            # Put back in pool
            self._docker_client_pool.add(id(docker_client))

    def _lazy_cpu_and_mem_set_init(self):
        # Implicitly assume lock is already held
        if len(self._numa_nodes) != 0:
            # Init already happened
            return
        if (self._available_cpu_ids is None
            or self._cpus_per_job is None
            or self._use_memset_of_nearest_node is None):
            raise Exception('Cannot do init. One or more params were None')
        import numa
        if not numa.available():
            raise Exception('NUMA not available')
        numa_nodes = list(range(0, numa.get_max_node() + 1))
        cpu_count = 0
        for numa_node in numa_nodes:
            cpus = numa.node_to_cpus(numa_node)
            for cpu_id in cpus:
                if cpu_id in self._available_cpu_ids:
                    try:
                        self._numa_nodes[numa_node].add(cpu_id)
                    except KeyError:
                        self._numa_nodes[numa_node] = set()
                        self._numa_nodes[numa_node].add(cpu_id)
                    try:
                        self._numa_node_pool[numa_node].add(cpu_id)
                    except KeyError:
                        self._numa_node_pool[numa_node] = set()
                        self._numa_node_pool[numa_node].add(cpu_id)
                    _logger.info('Putting CPU {} in NUMA node {} in resource pool'.format(
                        cpu_id, numa_node))
                    cpu_count += 1
                else:
                    _logger.info('CPU {} in NUMA node {} is NOT IN resource pool'.format(
                        cpu_id, numa_node))

        if cpu_count == 0:
            raise Exception('Found no available CPUs')
        if cpu_count != len(self._available_cpu_ids):
            raise Exception(
                'Mismatch between provided available CPU ids and what was found on system')
        assert len(self._numa_node_pool) == len(self._numa_nodes)

    def get_cpus(self):
        """
            Returns a set of CPU ids for a single job
        """
        with self._lock:
            self._lazy_cpu_and_mem_set_init()
            cpu_memset_tuples_to_return = set()
            if self._use_memset_of_nearest_node:
                for numa_node, available_cpus in sorted(
                    self._numa_node_pool.items(), key=lambda x:x[0]):
                    if len(available_cpus) >= self._cpus_per_job:
                        for _ in range(0, self._cpus_per_job):
                            cpu = available_cpus.pop()
                            cpu_memset_tuples_to_return.add( (cpu, numa_node) )
                        break # We are done
            else:
                # Grab any available CPU
                available_cpus = set(functools.reduce(
                    lambda a,b: a.union(b),
                    self._numa_node_pool.values()))
                cpus_to_grab = set()
                if len(available_cpus) >= self._cpus_per_job:
                    for _ in range(0, self._cpus_per_job):
                        cpus_to_grab.add(available_cpus.pop())
                    # Now remove from pool
                    for numa_node, available_cpus_in_node in sorted(
                        self._numa_node_pool.items(), key=lambda x:x[0]):
                        for cpu_to_grab in cpus_to_grab:
                            if cpu_to_grab in available_cpus_in_node:
                                cpu_memset_tuples_to_return.add( (cpu_to_grab, numa_node) )
                                available_cpus_in_node.remove(cpu_to_grab)


            if len(cpu_memset_tuples_to_return) != self._cpus_per_job:
                _logger.error('Failed to retrieve CPU resources required for job')
                _logger.error('cpu_memset_tuples_to_return: {}'.format(cpu_memset_tuples_to_return))
                _logger.error('cpus_per_job: {}'.format(self._cpus_per_job))
                raise Exception('Failed to retrieve CPU resources required for job')
            return cpu_memset_tuples_to_return

    def release_cpus(self, cpu_ids):
        """
            Returns a set of CPU ids
        """
        with self._lock:
            self._lazy_cpu_and_mem_set_init()
            assert isinstance(cpu_ids, set)
            for item in cpu_ids:
                assert isinstance(item, int)
            for cpu_to_release in cpu_ids:
                released=False
                for numa_node, available_cpu_ids in self._numa_node_pool.items():
                    if cpu_to_release in self._numa_nodes[numa_node]:
                        available_cpu_ids.add(cpu_to_release)
                        released = True
                        break
                if not released:
                    raise Exception('Failed to return CPU {} to pool'.format(cpu_to_release))

class DockerBackend(BackendBaseClass):

    def __init__(self, hostProgramPath, workingDirectory, timeLimit, memoryLimit, stackLimit, ctx, **kwargs):
        super().__init__(hostProgramPath, workingDirectory,
                         timeLimit, memoryLimit, stackLimit, ctx, **kwargs)
        self._container = None
        self._workDirInsideContainer = '/mnt/'
        self._skipToolExistsCheck = False
        self._userToUseInsideContainer = None
        self._dockerStatsOnExitShimBinary = None
        self._killLock = threading.Lock()
        self._additionalHostContainerFileMaps = dict()
        self._usedFileMapNames = set()  # HACK
        self._extra_volume_mounts = dict()
        self._grabbed_cpus = None
        self._memory_swappiness = None
        self._stdout_and_stderr_bypass = False
        # handle required options
        if not 'image' in kwargs:
            raise DockerBackendException('"image" but be specified')
        self._dockerImageName = kwargs['image']
        if not (isinstance(self._dockerImageName, str) and len(self._dockerImageName) > 0):
            raise DockerBackendException('"image" must to a non empty string')

        # Pretend user default is $USER
        if not 'user' in kwargs:
            kwargs['user'] = '$HOST_USER'

        available_cpu_ids = None
        cpus_per_job = None
        self._use_memset_of_nearest_node = None
        self.resource_pinning = False # No resource pinning by default
        requiredOptions = ['image']
        # handle other options
        for key, value in kwargs.items():
            if key in requiredOptions:
                continue
            if key == 'stdout_and_stderr_bypass':
                if not isinstance(value, bool):
                    raise DockerBackendException(
                        '"stdout_and_stderr_bypass" must be bool')
                if value:
                    self._stdout_and_stderr_bypass = True
                continue
            if key == 'skip_tool_check':
                self._skipToolExistsCheck = value
                if not isinstance(self._skipToolExistsCheck, bool):
                    raise DockerBackendException(
                        '"skip_tool_check" must map to a bool')
                continue
            if key == 'image_work_dir':
                self._workDirInsideContainer = value
                if not (isinstance(self._workDirInsideContainer, str) and len(self._workDirInsideContainer) > 0):
                    raise DockerBackendException(
                        '"image_work_dir" must be a non empty string')
                if not os.path.isabs(value):
                    raise DockerBackendException(
                        '"image_work_dir" must be an absolute path')
                continue
            if key == 'user':
                if not (isinstance(value, str) or isinstance(value, int) or value == None):
                    raise DockerBackendException(
                        '"user" must be integer or a string')
                if value == None:
                    self._userToUseInsideContainer = None
                elif isinstance(value, int):
                    if value < 0:
                        raise DockerBackendException(
                            '"user" specified as an integer must be >= 0')
                    self._userToUseInsideContainer = value
                else:
                    # The choice of $ is deliberate because it is not a valid
                    # character in a username
                    if value == "$HOST_USER":
                        self._userToUseInsideContainer = "{}:{}".format(
                            os.getuid(), os.getgid())
                    else:
                        import re
                        if re.match(r'[a-z_][a-z0-9_-]*[$]?', value) == None:
                            raise DockerBackendException(
                                '"{}" is not a valid username'.format(value))
                        self._userToUseInsideContainer = value
                continue
            if key == 'docker_stats_on_exit_shim':
                if not isinstance(value, bool):
                    raise DockerBackendException(
                        '"docker_stats_on_exit_shim" should be a boolean')
                if value:
                    root = os.path.dirname(os.path.dirname(
                        os.path.dirname(os.path.abspath(__file__))))
                    self._dockerStatsOnExitShimBinary = os.path.join(
                        root, 'external_deps', 'docker-stats-on-exit-shim')
                    _logger.info("Looking for '{}'".format(
                        self._dockerStatsOnExitShimBinary))
                    if not os.path.exists(self._dockerStatsOnExitShimBinary):
                        raise DockerBackendException(
                            "Could not find docker-stats-on-exit-shim at '{}'".format(self._dockerStatsOnExitShimBinary))
                continue
            if key == 'extra_mounts':
                if not isinstance(value, dict):
                    raise DockerBackendException(
                        '"extra_mounts" should be a dictionary')
                for host_path, props in value.items():
                    if not isinstance(host_path, str):
                        raise DockerBackendException(
                            '"extra_mounts" keys should be a string')
                    if not os.path.isabs(host_path):
                        raise DockerBackendException(
                            '"host_path" ("{}") must be an absolute path'.format(
                                host_path))
                    if not isinstance(props, dict):
                        raise DockerBackendException(
                            '"{}" should map to a dictionary'.format(
                                in_container_path))
                    in_container_path = None
                    read_only = True
                    try:
                        in_container_path =  props['container_path']
                    except KeyError:
                        raise DockerBackendException('"container_path" key is missing from {}'.format(props))
                    if 'read_only' in props:
                        read_only = props['read_only']
                    if not isinstance(read_only, bool):
                        raise DockerBackendException('"read_only" must be a boolean')
                    if not os.path.isabs(in_container_path):
                        raise DockerBackendException(
                            'Container mount point "{}" should be absolute'.format(
                                in_container_path))
                    if in_container_path.startswith(self._workDirInsideContainer):
                        raise DockerBackendException(
                            'Container mount point "{}" cannot be based in "{}"'.format(
                                in_container_path,
                                self._workDirInsideContainer))
                    self._extra_volume_mounts[host_path] = {
                        'bind': in_container_path,
                        'ro': read_only,
                    }
                continue
            if key == 'memory_swappiness':
                if not isinstance(value, int):
                    raise DockerBackendException('memory_swappiness should be an int')
                if value <= 0 or value > 100:
                    raise DockerBackendException(
                        'memory_swappiness should in range [0,100]')
                self._memory_swappiness = value
                continue
            if key == 'resource_pinning':
                self.resource_pinning = True
                if not isinstance(value, dict):
                    raise DockerBackendException(
                    'resource_pinning should map to a dictionary')
                if 'cpu_ids' not in value:
                    raise DockerBackendException(
                    'cpu_ids key must be present in resource_pinning')
                available_cpu_ids = value['cpu_ids']
                if not isinstance(available_cpu_ids, list):
                    raise DockerBackendException(
                    'cpu_ids must be a list')
                # Turn into a set
                available_cpu_ids = set(available_cpu_ids)
                if len(available_cpu_ids) == 0:
                    raise DockerBackendException(
                    'cpu_ids must not be empty')
                if 'cpus_per_job' not in value:
                    raise DockerBackendException(
                    'cpus_per_job key must be present in resource_pinning')
                cpus_per_job = value['cpus_per_job']
                if not isinstance(cpus_per_job, int):
                    raise DockerBackendException(
                    'cpus_per_job must be an integer')
                if cpus_per_job < 1:
                    raise DockerBackendException(
                    'cpus_per_job >= 1')
                self._use_memset_of_nearest_node = False # Default
                if 'use_memset_of_nearest_node' in value:
                    self._use_memset_of_nearest_node = value['use_memset_of_nearest_node']
                    if not isinstance(self._use_memset_of_nearest_node, bool):
                        raise DockerBackendException(
                        'cpus_per_job >= 1')
                # Sanity check
                if (self.ctx.num_parallel_jobs * cpus_per_job) > len(available_cpu_ids):
                        raise DockerBackendException(
                        'Number of cpus required exceeds number of available CPUs')
                continue

            # Not recognised option
            raise DockerBackendException(
                '"{}" key is not a recognised option'.format(key))

        # HACK: Try to prevent program path name being used in calls to addFileToBackend()
        if self.programPath().startswith('/tmp') and os.path.dirname(self.programPath()) == '/tmp':
            self._usedFileMapNames.add(os.path.basename(self.programPath()))

        # Initialise global client pool. This is shared amoung all runners.
        self._resource_pool = None
        try:
            self._resource_pool, success = self.ctx.get_object('DockerBackend.ResourcePool')
            if not success:
                # There is no existing resource pool. Make one
                self._resource_pool = ResourcePool(
                    num_jobs=self.ctx.num_parallel_jobs,
                    available_cpu_ids=available_cpu_ids,
                    cpus_per_job=cpus_per_job,
                    use_memset_of_nearest_node=self._use_memset_of_nearest_node
                )
                success = self.ctx.add_object('DockerBackend.ResourcePool', self._resource_pool)
                # Handle race. If someone managed to make a resource pool before we did
                # use theirs instead
                if not success:
                    self._resource_pool, success = self.ctx.get_object('DockerBackend.ResourcePool')
                    if not success:
                        raise DockerBackendException('Failed to setup resource pool')
        except Exception as e:
            _logger.error('Failed to get resource pool')
            _logger.error(e)
            raise DockerBackendException(
                'Failed to get resource pool')

        # Initialise the docker client
        try:
            self._dc = self._resource_pool.get_docker_client()
            self._dc.ping()
        except Exception as e:
            _logger.error('Failed to connect to the Docker daemon')
            _logger.error(e)
            raise DockerBackendException(
                'Failed to connect to the Docker daemon')

        try:
            # FIXME: Move this check into the resource pool so we can cache
            # the result of this check amoung runners.
            # Check we can find the docker image
            images = self._dc.images()
            assert isinstance(images, list)
            images = list(
                filter(lambda i: (i['RepoTags'] is not None) and self._dockerImageName in i['RepoTags'], images))
            if len(images) == 0:
                msg = 'Could not find docker image with name "{}"'.format(
                    self._dockerImageName)
                raise DockerBackendException(msg)
            else:
                if len(images) > 1:
                    msg = 'Found multiple docker images:\n{}'.format(
                        pprint.pformat(images))
                    _logger.error(msg)
                    raise DockerBackendException(msg)
                self._dockerImage = images[0]
                _logger.debug('Found Docker image:\n{}'.format(
                    pprint.pformat(self._dockerImage)))
        finally:
            # HACK: To not exhaust the resource pool we need to
            # return the client now.
            self._resource_pool.release_docker_client(self._dc)
            self._dc = None

    @property
    def name(self):
        return "Docker"

    @property
    def dockerStatsOnExitShimPathInContainer(self):
        if self._dockerStatsOnExitShimBinary == None:
            return None
        return self.getFilePathInBackend(self._dockerStatsOnExitShimBinary)

    @property
    def dockerStatsLogFileName(self):
        return 'exit_stats.json'

    @property
    def dockerStatsLogFileHost(self):
        return os.path.join(self.workingDirectory, self.dockerStatsLogFileName)

    @property
    def dockerStatsLogFileInContainer(self):
        return os.path.join(self.workingDirectoryInternal, self.dockerStatsLogFileName)

    def run(self, cmdLine, stdoutLogFilePath, stderrLogFilePath, envVars):
        # Grab a docker client
        self._dc = self._resource_pool.get_docker_client()

        self._stdoutLogFilePath = stdoutLogFilePath
        self._stderrLogFilePath = stderrLogFilePath
        self._outOfMemory = False
        outOfTime = False
        ulimits = []
        if self.stackLimit != None:
            stackLimitInBytes = 0
            if self.stackLimit == 0:
                # Work out the maximum memory size, docker doesn't support
                # "unlimited" right now
                _logger.warning(
                    "Trying to emulate unlimited stack. Docker doesn't support setting it")
                if self.memoryLimit > 0:
                    # If a memory limit is set just set the stack size to the maximum we allow
                    # self.memoryLimit is in MiB, convert to bytes
                    stackLimitInBytes = self.memoryLimit * (2**20)
                else:
                    # No memory limit is set. Just use the amount of memory on system as an
                    # upper bound
                    stackLimitInBytes = psutil.virtual_memory().total + psutil.swap_memory().total
            elif self.stackLimit > 0:
                stackLimitInBytes = self.stackLimit * 1024
            # I'm assuming the stack limit is set in bytes here. I don't actually know if
            # this is the case.
            ulimits.append(docker.utils.Ulimit(name='stack',
                                               soft=stackLimitInBytes,
                                               hard=stackLimitInBytes))
            _logger.info(
                'Setting stack size limit to {} bytes'.format(stackLimitInBytes))

        # Handle stdout/stderr bypass. This avoids docker'ss logging system
        # completely. This is an attempt to hack around stdout accidently
        # being lost somewhere ocassionaly.
        stdoutLogFilePathInContainer = None
        stderrLogFilePathInContainer = None
        if self._stdout_and_stderr_bypass:
            _logger.info('Using stdout/stderr by-pass')
            # Create the files
            with open(stdoutLogFilePath, 'w') as f:
                pass
            with open(stderrLogFilePath, 'w') as f:
                pass
            # Add them to this back-end
            self.addFileToBackend(stdoutLogFilePath, read_only=False)
            self.addFileToBackend(stderrLogFilePath, read_only=False)
            stdoutLogFilePathInContainer = self.getFilePathInBackend(stdoutLogFilePath)
            stderrLogFilePathInContainer = self.getFilePathInBackend(stderrLogFilePath)

        extraHostCfgArgs = {}
        if len(ulimits) > 0:
            extraHostCfgArgs['ulimits'] = ulimits

        # Declare the volumes
        programPathInsideContainer = self.programPath()
        bindings = dict()

        if self._dockerStatsOnExitShimBinary:
            self.addFileToBackend(self._dockerStatsOnExitShimBinary, read_only=True)

        # Add aditional volumes
        for hostPath, (containerPath, read_only) in self._additionalHostContainerFileMaps.items():
            bindings[hostPath] = {'bind': containerPath, 'ro': read_only}

        # Try adding extra volumes
        for hostPath, props in self._extra_volume_mounts.items():
            bindings[hostPath] = props

        # Mandatory bindings
        bindings[self.workingDirectory] = {
            'bind': self.workingDirectoryInternal, 'ro': False}
        bindings[self.hostProgramPath] = {
            'bind': programPathInsideContainer, 'ro': True}

        _logger.debug('Declaring bindings:\n{}'.format(
            pprint.pformat(bindings)))

        extraContainerArgs = {}

        if self.memoryLimit > 0:
            # http://docs.docker.com/reference/run/#memory-constraints
            #
            # memory=L<inf, memory-swap=S<inf, L<=S
            # (specify both memory and memory-swap) The container is not allowed to use more than L bytes of memory, swap *plus* memory usage is limited by S.
            extraHostCfgArgs['mem_limit'] = '{}m'.format(self.memoryLimit)
            extraHostCfgArgs['memswap_limit'] = '{}m'.format(self.memoryLimit)
            _logger.info(
                'Setting memory limit to {} MiB'.format(self.memoryLimit))

        if self._userToUseInsideContainer != None:
            extraContainerArgs['user'] = self._userToUseInsideContainer
            _logger.info('Using user "{}" inside container'.format(
                self._userToUseInsideContainer))

        if self.resource_pinning:
            cpu_memset_tuples = self._resource_pool.get_cpus()
            self._grabbed_cpus = set(map(lambda t: t[0], cpu_memset_tuples))
            grabbed_cpu_strs = set(map(lambda c:str(c), self._grabbed_cpus))
            cpu_set_string=",".join(grabbed_cpu_strs)
            extraHostCfgArgs['cpuset_cpus']=cpu_set_string
            _logger.info('Using CPU pinning: {}'.format(cpu_set_string))
            if self._use_memset_of_nearest_node:
                mem_set_to_use = None
                for _, mem_set in cpu_memset_tuples:
                    mem_set_to_use = mem_set
                    break
                _logger.info('Using Memset pinning: {}'.format(mem_set_to_use))
                assert isinstance(mem_set_to_use, int)
                assert mem_set_to_use >= 0
                mem_set_to_use_str=str(mem_set_to_use)
                extraHostCfgArgs['cpuset_mems'] = mem_set_to_use_str

        if self._memory_swappiness is not None:
            _logger.info('Setting memory_swappiness to {}'.format(
                self._memory_swappiness))
            extraHostCfgArgs['mem_swappiness'] = self._memory_swappiness

        _logger.debug('Using host config:\n{}'.format(pprint.pformat(extraHostCfgArgs)))
        hostCfg = self._dc.create_host_config(
            binds=bindings,
            privileged=False,
            network_mode=None,
            **extraHostCfgArgs
        )

        # Modify the command line if necessary
        finalCmdLine = cmdLine
        if self._dockerStatsOnExitShimBinary:
            finalCmdLine = [self.dockerStatsOnExitShimPathInContainer,
                            self.dockerStatsLogFileInContainer] + finalCmdLine

        
        if self._stdout_and_stderr_bypass:
            # Need to modify the final command to use bash to redirect
            # stdout/stderr to files
            original_cmd_as_escaped_str = ''
            for c in finalCmdLine:
                original_cmd_as_escaped_str += " '{cmd}'".format(cmd=c)
            original_cmd_as_escaped_str += " >> '{stdout}' 2>> '{stderr}'".format(
                stdout = stdoutLogFilePathInContainer,
                stderr = stderrLogFilePathInContainer)
            finalCmdLine = [ '/bin/bash', '-c', original_cmd_as_escaped_str]

        _logger.debug('Command line inside container:\n{}'.format(
            pprint.pformat(finalCmdLine)))

        # Finally create the container
        try:
            _logger.debug('Final bindings: {}'.format(pprint.pformat(bindings)))
            _logger.debug('Extra container args: {}'.format(pprint.pformat(extraContainerArgs)))
            self._container = self._dc.create_container(
                image=self._dockerImage['Id'],
                command=finalCmdLine,
                environment=envVars,
                working_dir=self.workingDirectoryInternal,
                volumes=list(bindings.keys()),
                host_config=hostCfg,
                # The default. When all containers are created this way they will all
                # get the same proportion of CPU cycles.
                cpu_shares=0,
                **extraContainerArgs
            )
            _logger.info('Created container:\n{}'.format(
                pprint.pformat(self._container['Id'])))
            if self._container['Warnings'] != None:
                _logger.warning('Warnings emitted when creating container:{}'.format(
                    self._container['Warnings']))
        except Exception as e:
            _logger.error('Exception raised when trying to create container: {}'.format(str(e)))
            _logger.error(traceback.format_exc())
            self.kill()
            raise e

        exitCode = None
        startTime = time.perf_counter()
        self._endTime = 0
        try:
            self._dc.start(container=self._container['Id'])
            timeoutArg = {}
            if self.timeLimit > 0:
                timeoutArg['timeout'] = self.timeLimit
                _logger.info('Using timeout {} seconds'.format(self.timeLimit))
            exitCode = self._dc.wait(
                container=self._container['Id'], **timeoutArg)
            if exitCode == -1:
                # FIXME: Does this even happen? Docker-py's documentation is
                # unclear.
                outOfTime = True
                _logger.info('Timeout occurred')
                exitCode = None
        except requests.exceptions.ReadTimeout as e:
            _logger.info('Timeout occurred')
            outOfTime = True
        except docker.errors.NotFound as e:
            _logger.error(
                'Failed to start/wait on container "{}".\nReason: {}'.format(self._container['Id'], str(e)))
        except Exception as e:
            _logger.error('Unexpected exception raised while running container: {}'.format(str(e)))
            _logger.error(traceback.format_exc())
        finally:
            self.kill()

        runTime = self._endTime - startTime
        userCPUTime = None
        sysCPUTime = None

        if self._dockerStatsOnExitShimBinary:
            # Try to extract the needed stats
            try:
                with open(self.dockerStatsLogFileHost, 'r') as f:
                    stats = json.load(f)
                    userCPUTime = float(stats['cgroups']['cpu_stats']['cpu_usage'][
                                        'usage_in_usermode']) / (10**9)
                    sysCPUTime = float(stats['cgroups']['cpu_stats']['cpu_usage'][
                                       'usage_in_kernelmode']) / (10**9)
            except Exception as e:
                _logger.error('Failed to retrieve stats from "{}"'.format(
                    self.dockerStatsLogFileHost))
                _logger.error(str(e))
                _logger.error(traceback.format_exc())

        return BackendResult(exitCode=exitCode,
                             runTime=runTime,
                             oot=outOfTime,
                             oom=self._outOfMemory,
                             userCpuTime=userCPUTime,
                             sysCpuTime=sysCPUTime)

    def kill(self):
        try:
            self._killLock.acquire()
            self._endTime = time.perf_counter()
            if self._container != None:
                _logger.info('Stopping container:{}'.format(
                    self._container['Id']))
                try:
                    containerStatus = self._dc.inspect_container(
                        self._container['Id'])
                    if containerStatus["State"]["Running"]:
                        self._dc.kill(self._container['Id'])
                # FIXME: Should use tighter exceptions
                #except docker.errors.APIError as e:
                except Exception as e:
                    _logger.error('Failed to kill container:"{}".\n{}'.format(
                        self._container['Id'], str(e)))
                    _logger.error(traceback.format_exc())

                def write_log(path, stdout, stderr):
                    with open(path, 'wb') as f:
                        logData = self._dc.logs(container=self._container['Id'],
                                                stdout=stdout, stderr=stderr,
                                                timestamps=False,
                                                tail='all', stream=False)
                        _logger.info('Writing {}{} log to {}'.format(
                            'stdout' if stdout else '',
                            'stderr' if stderr else '',
                            f.name))
                        f.write(logData)
                if not self._stdout_and_stderr_bypass:
                    # Write logs to file (note we get binary in Python 3, not sure
                    # about Python 2) using Docker's logging mechanism
                    write_log(self._stdoutLogFilePath, stdout=True, stderr=False)
                    write_log(self._stderrLogFilePath, stdout=False, stderr=True)
                else:
                    # The stdout/stderr is logged to files by bash so we don't
                    # need to do that here. However bash itself might emit
                    # stuff on stdout/stderr so log that.
                    _logger.info('Dumping internal stdout/stderr:')
                    write_log(self._stdoutLogFilePath + '.internal.txt', stdout=True, stderr=False)
                    write_log(self._stderrLogFilePath + '.internal.txt', stdout=False, stderr=True)

                # Record if OOM occurred
                try:
                    containerInfo = self._dc.inspect_container(
                        container=self._container['Id'])
                    self._outOfMemory = containerInfo['State']['OOMKilled']
                    assert isinstance(self._outOfMemory, bool)
                # FIXME: Should use tighter exceptions
                except Exception as e:
                    _logger.error('Failed to determine OOM for container "{}":{}'.format(
                        self._container['Id'], str(e)))
                    _logger.error(traceback.format_exc())
                    self._outOfMemory = None

                try:
                    _logger.info('Destroying container:{}'.format(
                        self._container['Id']))
                    # Note setting `v=True` is very important. This removes
                    # the volumes associated with the container. Otherwise
                    # we'll leave loads of stray volumes lying around.
                    self._dc.remove_container(
                        container=self._container['Id'], v=True, force=True)
                # FIXME: Should use tighter exceptions
                #except docker.errors.APIError as e:
                except Exception as e:
                    _logger.error('Failed to remove container:"{}".\n{}'.format(
                        self._container['Id'], str(e)))
                    _logger.error(traceback.format_exc())
                self._container = None
        finally:
            if self._dc is not None:
                self._resource_pool.release_docker_client(self._dc)
            self._dc = None
            if self.resource_pinning and self._grabbed_cpus is not None:
                self._resource_pool.release_cpus(self._grabbed_cpus)
                self._grabbed_cpus = None
            self._killLock.release()

    def programPath(self):
        return '/tmp/{}'.format(os.path.basename(self.hostProgramPath))

    def checkToolExists(self, toolPath):
        if self._skipToolExistsCheck:
            _logger.info('Skipping tool check')
            return
        assert os.path.isabs(toolPath)
        # HACK: Is there a better way to do this?
        _logger.debug('Checking tool "{}" exists in image'.format(toolPath))
        tempContainer = self._dc.create_container(image=self._dockerImage['Id'],
                                                  command=['ls', toolPath])
        _logger.debug('Created temporary container: {}'.format(
            tempContainer['Id']))
        self._dc.start(container=tempContainer['Id'])
        exitCode = self._dc.wait(container=tempContainer['Id'])
        self._dc.remove_container(container=tempContainer['Id'], force=True)
        if exitCode != 0:
            raise DockerBackendException(
                'Tool "{}" does not exist in Docker image'.format(toolPath))

    @property
    def workingDirectoryInternal(self):
        # Return the path to the working directory that will be used inside the
        # container
        return self._workDirInsideContainer

    def addFileToBackend(self, path, read_only):
        if not os.path.isabs(path):
            raise DockerBackendException('path must be absolute')
        fileName = os.path.basename(path)

        if not os.path.exists(path):
            raise DockerBackendException(
                'File "{}" does not exist'.format(path))

        if not isinstance(read_only, bool):
            raise DockerBackendException('"read_only" must be boolean')

        # FIXME: This mapping is lame. We could do something more sophisticated
        # to avoid this limitation.
        if fileName in self._usedFileMapNames:
            raise DockerBackendException(
                'Mapping identicaly named file is not supported')
        self._additionalHostContainerFileMaps[
            path] = ( os.path.join('/tmp', fileName), read_only)
        _logger.debug('Adding mapping "{}" => "{}"'.format(
            path,
            self._additionalHostContainerFileMaps[path])
        )
        for _, props in self._extra_volume_mounts.items():
            if self._additionalHostContainerFileMaps[path] == props['bind']:
                raise DockerBackendException(
                    'Cannot add path "{}". It is already in use by "{}"'.format(
                        path, self._extra_volume_mounts))
        self._usedFileMapNames.add(fileName)

    def getFilePathInBackend(self, hostPath):
        try:
            file_path, _ = self._additionalHostContainerFileMaps[hostPath]
            return file_path
        except KeyError as e:
            raise DockerBackendException(
                '"{}" was not given to addFileToBackend()'.format(hostPath))


def get():
    return DockerBackend
