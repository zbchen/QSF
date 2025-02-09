# vim: set sw=4 ts=4 softtabstop=4 expandtab:
from . BackendBase import *
import logging
import os
import pprint
import psutil
import subprocess
import threading
import time
import sys

_logger = logging.getLogger(__name__)

if sys.version_info < (3, 3):
    # HACK: We need newer python so subprocess.Popen.wait()
    # supports a timeout.
    raise Exception('Need Python >= 3.3')

# FIXME: This is ripped out of the Docker backend. They should
# be refactored to make two different pools so that we can share
# the cpu pool implementation.
class ResourcePool:
    """
        Resource pool for DockerBackend. It contains a set of resources
        that can be acquired and returned. These resources include

        * CPUs
    """
    def __init__(self, num_jobs, available_cpu_ids, cpus_per_job, use_memset_of_nearest_node):
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

        # CPU and memset data structures
        self._numa_nodes = dict() # Maps NUMA node to set of CPU ids
        self._numa_node_pool = dict() # Maps NUMa node to set of available CPU ids

        self._lock = threading.Lock()

        # Sanity check
        if cpus_per_job is not None and available_cpu_ids is not None:
            assert (num_jobs * cpus_per_job) <= len(available_cpu_ids)

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


class PythonPsUtilBackendException(BackendException):
    pass


class PythonPsUtilBackend(BackendBaseClass):

    def __init__(self, hostProgramPath, workingDirectory, timeLimit, memoryLimit, stackLimit, ctx, **kwargs):
        super().__init__(hostProgramPath, workingDirectory,
                         timeLimit, memoryLimit, stackLimit, ctx, **kwargs)
        memoryLimitTimePeriodKey = 'memory_limit_poll_time_period'
        # default
        self.memoryLimitPollTimePeriodInSeconds = 0.5
        self.resource_pinning = False

        for key, value in kwargs.items():
            if key == memoryLimitTimePeriodKey:
                self.memoryLimitPollTimePeriodInSeconds = kwargs[
                    memoryLimitTimePeriodKey]
                if memoryLimit == 0:
                    raise PythonPsUtilBackendException(
                            'Cannot have "{}" specified with no memory limit'.format(
                        memoryLimitTimePeriodKey))
                if not (isinstance(self.memoryLimitPollTimePeriodInSeconds, float) and
                        self.memoryLimitPollTimePeriodInSeconds > 0.0):
                    raise PythonPsUtilBackendException(
                        '{} must be a float > 0.0'.format(memoryLimitTimePeriodKey))
            elif key == 'resource_pinning':
                self.resource_pinning = True
                if not isinstance(value, dict):
                    raise PythonPsUtilBackendException(
                    'resource_pinning should map to a dictionary')
                if 'cpu_ids' not in value:
                    raise PythonPsUtilBackendException(
                    'cpu_ids key must be present in resource_pinning')
                self._available_cpu_ids = value['cpu_ids']
                if not isinstance(self._available_cpu_ids, list):
                    raise PythonPsUtilBackendException(
                    'cpu_ids must be a list')
                # Turn into a set
                self._available_cpu_ids = set(self._available_cpu_ids)
                if len(self._available_cpu_ids) == 0:
                    raise PythonPsUtilBackendException(
                    'cpu_ids must not be empty')
                if 'cpus_per_job' not in value:
                    raise PythonPsUtilBackendException(
                    'cpus_per_job key must be present in resource_pinning')
                self._cpus_per_job = value['cpus_per_job']
                if not isinstance(self._cpus_per_job, int):
                    raise PythonPsUtilBackendException(
                    'cpus_per_job must be an integer')
                if self._cpus_per_job < 1:
                    raise PythonPsUtilBackendException(
                    'cpus_per_job >= 1')
                self._use_memset_of_nearest_node = False # Default
                if 'use_memset_of_nearest_node' in value:
                    self._use_memset_of_nearest_node = value['use_memset_of_nearest_node']
                    if not isinstance(self._use_memset_of_nearest_node, bool):
                        raise PythonPsUtilBackendException(
                        'cpus_per_job >= 1')
                # Sanity check
                if (self.ctx.num_parallel_jobs * self._cpus_per_job) > len(self._available_cpu_ids):
                    raise PythonPsUtilBackendException(
                    'Number of cpus required exceeds number of available CPUs')
            else:
                raise PythonPsUtilBackendException('Unknow kwarg "{}"'.format(key))

        self._process = None
        self._eventObj = None
        self._resource_pool = None
        self.resource_pool_init()

    @property
    def name(self):
        return "PythonPsUtil"

    def kill(self):
        if self._process != None:
            try:
                if self._process.is_running():
                    self._terminateProcess(self._process, 0.0)
            except psutil.NoSuchProcess:
                pass

    def programPath(self):
        # We run directly on the host so nothing special here
        return self.hostProgramPath

    def resource_pool_init(self):
        if not self.resource_pinning:
            return
        try:
            self._resource_pool, success = self.ctx.get_object(
                'PythonPsUtilBackend.ResourcePool')
            if not success:
                # There is no existing resource pool. Make one
                self._resource_pool = ResourcePool(
                    num_jobs=self.ctx.num_parallel_jobs,
                    available_cpu_ids=self._available_cpu_ids,
                    cpus_per_job=self._cpus_per_job,
                    use_memset_of_nearest_node=self._use_memset_of_nearest_node
                )
                success = self.ctx.add_object(
                    'PythonPsUtilBackend.ResourcePool', self._resource_pool)
                # Handle race. If someone managed to make a resource pool before we did
                # use theirs instead
                if not success:
                    self._resource_pool, success = self.ctx.get_object(
                        'PythonPsUtilBackend.ResourcePool')
                    if not success:
                        raise PythonPsUtilBackendException('Failed to setup resource pool')
        except Exception as e:
            _logger.error('Failed to get resource pool')
            _logger.error(e)
            raise PythonPsUtilBackendException(
                'Failed to get resource pool')

    #def run(self, cmdLine, logFilePath, envVars):
    def run(self, cmdLine, stdoutLogFilePath, stderrLogFilePath, envVars):
        self._outOfMemory = False

        cmdLineCopy = cmdLine.copy()

        if self.resource_pinning:
            # Use taskset and numactl to pin
            cpu_memset_tuples = self._resource_pool.get_cpus()
            self._grabbed_cpus = set(map(lambda t: t[0], cpu_memset_tuples))
            grabbed_cpu_strs = set(map(lambda c:str(c), self._grabbed_cpus))
            cpu_set_string=",".join(grabbed_cpu_strs)
            _logger.info('Pinning to CPUs "{}"'.format(cpu_set_string))
            prefixCmd = [
                'taskset', '--cpu-list', cpu_set_string,
                'numactl', '--physcpubind={}'.format(cpu_set_string)]
            if self._use_memset_of_nearest_node:
                mem_set_to_use = None
                for _, mem_set in cpu_memset_tuples:
                    mem_set_to_use = mem_set
                    break
                _logger.info('Using NUMA node {}'.format(mem_set_to_use))
                prefixCmd.append('--membind={}'.format(mem_set_to_use))
            cmdLineCopy = prefixCmd + cmdLineCopy
        
        # Note we do not propagate the variables of the current environment.
        _logger.info('Running:\n{}\nwith env:{}'.format(
            pprint.pformat(cmdLineCopy),
            pprint.pformat(envVars)))

        # Run the tool
        exitCode = None
        self._process = None
        startTime = time.perf_counter()
        pollThread = None
        self._outOfMemory = False
        outOfTime = False
        runTime = 0.0
        with open(stdoutLogFilePath, 'w') as stdoutLogFile:
            with open(stderrLogFilePath, 'w') as stderrLogFile:
                try:
                    _logger.debug('writing to stdout log file {}'.format(stdoutLogFile.name))
                    _logger.debug('writing to stderr log file {}'.format(stderrLogFile.name))
                    preExecFn = None
                    if self.stackLimit != None:
                        preExecFn = self._setStacksize
                        _logger.info('Using stacksize limit: {} KiB'.format(
                            'unlimited' if self.stackLimit == 0 else self.stackLimit))
                    # HACK: Use subprocess.Popen and then create the psutil wrapper
                    # around it because it returns the wrong exit code.
                    # This is a workaround for https://github.com/giampaolo/psutil/issues/960
                    self._subprocess_process = subprocess.Popen(cmdLineCopy,
                                                 cwd=self.workingDirectory,
                                                 stdout=stdoutLogFile,
                                                 stderr=stderrLogFile,
                                                 env=envVars,
                                                 preexec_fn=preExecFn)
                    try:
                        self._process = psutil.Process(pid=self._subprocess_process.pid)
                    except psutil.NoSuchProcess as e:
                        # HACK: Catch case where process has already died
                        pass

                    if self.memoryLimit > 0:
                        pollThread = self._memoryLimitPolling(self._process)

                    _logger.info(
                        'Running with timeout of {} seconds'.format(self.timeLimit))
                    exitCode = self._subprocess_process.wait(timeout=self.timeLimit)
                except subprocess.TimeoutExpired as e:
                    outOfTime = True
                    # Note the code in the finally block will sort out clean up
                finally:
                    self.kill()
                    if self.resource_pinning:
                        self._resource_pool.release_cpus(self._grabbed_cpus)

                    # This is a sanity check to make sure that the memory polling thread exits
                    # before this method exits
                    if pollThread != None:
                        if self._eventObj != None:
                            self._eventObj.set()  # Wake up polling thread if it's blocked on eventObj
                        _logger.debug('Joining memory polling thread START')
                        try:
                            pollThread.join()
                            _logger.debug('Joining memory polling thread FINISHED')
                        except RuntimeError:
                            _logger.error(
                                'RuntimeError waiting for memory polling thread to terminate')
                    self._process = None

                    endTime = time.perf_counter()
                    runTime = endTime - startTime

        return BackendResult(exitCode=exitCode,
                             runTime=runTime,
                             oot=outOfTime,
                             oom=self._outOfMemory,
                             userCpuTime=None,  # FIXME: Find a way to record this
                             sysCpuTime=None)  # FIXME: Find a way to record this

    def _setStacksize(self):
        """
          Designed to be called subprocess.POpen() after fork.
          It will set any limits as appropriate.
          Note do not try to use the _logger here are the file descriptors have been changed.
        """
        assert self.stackLimit != None
        assert isinstance(self.stackLimit, int)
        import resource
        if self.stackLimit == 0:
            resource.setrlimit(resource.RLIMIT_STACK,
                               (resource.RLIM_INFINITY, resource.RLIM_INFINITY))
        else:
            resource.setrlimit(resource.RLIMIT_STACK,
                               (self.stackLimit, self.stackLimit))

    def _getProcessMemoryUsageInMiB(self, process):
        # use Virtual memory size rather than resident set
        return process.memory_info()[1] / (2**20)

    def _terminateProcess(self, process, pause):
        assert isinstance(pause, float)
        assert pause >= 0.0
        # Gently terminate
        _logger.debug('Trying to terminate PID:{}'.format(process.pid))
        children = process.children(recursive=True)
        process.terminate()
        for child in children:
            try:
                _logger.debug(
                    'Trying to terminate child process PID:{}'.format(child.pid))
                child.terminate()
            except psutil.NoSuchProcess:
                pass

        # If requested give the process time to clean up after itself
        # if it is still running
        if self._processIsRunning(process) and pause > 0.0:
            time.sleep(pause)

        # Now aggresively kill
        _logger.info('Trying to kill PID:{}'.format(process.pid))
        children = process.children(recursive=True)
        process.kill()
        for child in children:
            try:
                _logger.info(
                    'Trying to kill child process PID:{}'.format(child.pid))
                child.kill()
            except psutil.NoSuchProcess:
                pass

    def _processIsRunning(self, process):
        return process.is_running() and not process.status() == psutil.STATUS_ZOMBIE

    def _memoryLimitPolling(self, process):
        """
          This function launches a new thread that will periodically
          poll the total memory usage of the tool that is being run.
          If it goes over the limit will kill it
        """
        assert self.memoryLimitPollTimePeriodInSeconds > 0
        assert self._outOfMemory == False

        # Other parts of the runner can can set on this to prevent this thread
        # from waiting on this Event object.
        self._eventObj = threading.Event()
        self._eventObj.clear()

        def threadBody():
            _logger.info('Launching memory limit polling thread for PID {} with polling time period of {} seconds'.format(
                process.pid, self.memoryLimitPollTimePeriodInSeconds))
            try:
                while self._processIsRunning(process):
                    self._eventObj.wait(
                        self.memoryLimitPollTimePeriodInSeconds)
                    totalMemoryUsage = 0
                    totalMemoryUsage += self._getProcessMemoryUsageInMiB(
                        process)

                    # The process might of forked so add the memory usage of
                    # its children too
                    childCount = 0
                    for childProc in process.children(recursive=True):
                        try:
                            totalMemoryUsage += self._getProcessMemoryUsageInMiB(
                                childProc)
                            childCount += 1
                        except psutil.NoSuchProcess:
                            _logger.warning(
                                'Child process disappeared whilst examining it\'s memory use')

                    _logger.debug(
                        'Total memory usage in MiB:{}'.format(totalMemoryUsage))
                    _logger.debug(
                        'Total number of children: {}'.format(childCount))

                    if totalMemoryUsage > self.memoryLimit:
                        _logger.warning('Memory limit reached (recorded {} MiB). Killing tool with PID {}'.format(
                            totalMemoryUsage, process.pid))
                        self._outOfMemory = True
                        # Give the tool a chance to clean up after itself
                        # before aggressively killing it
                        self._terminateProcess(process, pause=1.0)
                        break
            except psutil.NoSuchProcess:
                _logger.warning('Main process no longer available')

        newThreadName = 'memory_poller-{}'.format(process.pid)
        thread = threading.Thread(
            target=threadBody, name=newThreadName, daemon=True)
        thread.start()
        return thread

    def checkToolExists(self, toolPath):
        assert os.path.isabs(toolPath)
        if not os.path.exists(toolPath):
            raise PythonPsUtilBackendException(
                'Tool "{}" does not exist'.format(toolPath))

    @property
    def workingDirectoryInternal(self):
        # Nothing special here. We work directly on the host
        return self.workingDirectory

    def addFileToBackend(self, path, read_only):
        """
          PythonPsUtilBackend runs directly on the host
          so this is a no-op
        """
        if read_only:
            _logger.warning('Cannot enforce that "{}" is read only'.format(path))
        pass

    def getFilePathInBackend(self, hostPath):
        """
          PythonPsUtilBackend runs directly on the host
          so all files are available so just return
          the requested `hostPath`.
        """
        return hostPath


def get():
    return PythonPsUtilBackend
