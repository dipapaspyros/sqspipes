import time
import random
import uuid

from multiprocessing.pool import ThreadPool
from multiprocessing import Lock


class TaskError(Exception):

    def __init__(self, error):
        super(TaskError, self).__init__()

        self.error = error


class TaskPool:

    def __init__(self, workers, callback):
        self._n_started = 0
        self.workers = workers if workers > 1 else 1
        self.running = [None for _ in range(0, workers)]
        self.mutex = Lock()
        self._guard_mutex = Lock()
        self.pool = ThreadPool(processes=self.workers)
        self.callback = callback
        self._payloads = {}

    def _is_full(self):
        return self._n_started == self.workers

    def _task_entered(self, task_id, args):
        self._guard_mutex.acquire()
        self._n_started += 1
        self._payloads[task_id] = args
        self._guard_mutex.release()

    def _task_exited(self, task_id, meta, result):
        self._guard_mutex.acquire()
        self._n_started -= 1
        del self._payloads[task_id]
        self._guard_mutex.release()

        if self.callback:
            self.callback(meta, result)

    def _run_task(self, task_id, fn, args, meta):
        self._task_entered(task_id, args)

        try:
            result = fn(*args)
        except Exception as e:
            result = TaskError(error=e)

        self._task_exited(task_id, meta, result)

    def running_payloads(self):
        return [self._payloads[task_id] for task_id in self._payloads.keys()]

    def run_task(self, fn, args, meta):

        # don't overflow the task runner with tasks
        while self._is_full():
            time.sleep(random.randint(5, 15) / 10.0)

        # apply task
        self.pool.apply_async(TaskPool._run_task, (self, str(uuid.uuid4()), fn, args, meta))



