# vim: set sw=4 ts=4 softtabstop=4 expandtab:
import logging
import pkgutil
import importlib
import threading
import os

_logger = logging.getLogger(__name__)


class RunnerContext:
    def __init__(self, num_parallel_jobs):
        self._context_global_objects = dict()
        self._num_parallel_jobs = num_parallel_jobs
        self._lock = threading.Lock()
        assert isinstance(self._num_parallel_jobs, int)
        assert self._num_parallel_jobs > 0
        pass

    @property
    def num_parallel_jobs(self):
        return self._num_parallel_jobs

    def get_object(self, name):
        with self._lock:
            if name in self._context_global_objects:
                return (self._context_global_objects[name], True)
            else:
                return (None, False)

    def add_object(self, name, obj):
        with self._lock:
            if name in self._context_global_objects:
                return False
            else:
                self._context_global_objects[name] = obj
                return True
