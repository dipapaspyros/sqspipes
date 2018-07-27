import json
import random
import time
import traceback
import uuid

import boto3
from botocore.errorfactory import ClientError
from multiprocessing import Lock

from .utils.task_pool import TaskPool, TaskError


class EmptyTaskOutput(object):
    pass


class TaskRunner(object):

    def __init__(self, fn, in_queue_names, config):
        self.fn = fn
        self.in_queue_names = in_queue_names
        self.results = []
        self._result_mutex = Lock()
        self.out_queues = []
        self._out_queue_names = None

        self.domain = config['domain']
        self.name = config['name']
        self.aws_config = config['aws_config']
        self.workers = config.get('workers', 1)
        self.priority_levels = list(reversed(range(config.get('priorities', 1))))
        self.final = config.get('final', False)
        self.interval = config.get('interval', 0)
        self.ignore_none = config.get('ignore_none', True)

    def queue_name(self, priority):
        base_name = '%s-%s' % (self.domain, self.name)

        if not priority:
            return '%s.fifo' % base_name

        return '%s--p%d.fifo' % (base_name, priority)

    @property
    def out_queue_names(self):
        if self.final:
            return []

        if self._out_queue_names is not None:
            return self._out_queue_names

        self._out_queue_names = [self.queue_name(priority) for priority in self.priority_levels]

        return self._out_queue_names

    def set_workers(self, workers):
        self.workers = workers

    def in_queues(self):
        # no input queues?
        if not self.in_queue_names:
            return []

        sqs = self.sqs()

        retrieved = False
        retries = 0
        while not retrieved:
            in_queues = []
            try:
                for in_queue_name in self.in_queue_names:
                    in_queues.append(sqs.get_queue_by_name(QueueName=in_queue_name))
                    retrieved = True
            except ClientError as e:
                # only handle non-existing queue error
                if e.response.get('Error', {}).get('Code', '') != 'AWS.SimpleQueueService.NonExistentQueue':
                    raise

                # wait until input queues are created
                retrieved = False
                retries += 1
                if retries == 1:
                    print('Waiting for input queues...')

                time.sleep(2)

        if retries > 0:
            print('OK')

        return in_queues

    def sqs(self):
        return boto3.resource(
            'sqs',
            self.aws_config['region'],
            aws_access_key_id=self.aws_config['key'],
            aws_secret_access_key=self.aws_config['secret'],
        )

    def setup(self):
        sqs = self.sqs()

        self.out_queues = []
        for queue_name in self.out_queue_names:
            try:
                q = sqs.get_queue_by_name(QueueName=queue_name)
            except ClientError as e:
                # only handle non-existing queue error
                if e.response.get('Error', {}).get('Code', '') != 'AWS.SimpleQueueService.NonExistentQueue':
                    raise

                q = sqs.create_queue(QueueName=queue_name, Attributes={
                    'FifoQueue': 'true',
                    'VisibilityTimeout': '120',
                })

            self.out_queues = [q] + self.out_queues

    def _on_task_finish(self, task_meta, task_output):
        # add to results
        self._result_mutex.acquire()
        self.results.append(task_output)

        if (task_output is None and (not self.ignore_none)) or \
                (isinstance(task_output, EmptyTaskOutput)):
            # do nothing
            pass
        else:
            if (not self.final) and (type(task_output) != TaskError):
                # also write to queues for next task to pick up
                try:
                    self.out_queues[task_meta['priority']].send_message(
                        MessageBody=json.dumps({
                            'meta': task_meta,
                            'value': task_output
                        }),
                        MessageDeduplicationId=str(uuid.uuid4()),
                        MessageGroupId='-'
                    )
                except:
                    traceback.print_exc()

        self._result_mutex.release()

    def _run(self, args, priority=0):
        # create the thread pool
        pool = TaskPool(self.workers, callback=self._on_task_finish)

        # get input queues
        in_queues = self.in_queues()

        while True:
            # receive messages
            messages = []
            for in_queue in in_queues:
                messages += in_queue.receive_messages(MaxNumberOfMessages=min(self.workers, 10))

            if not in_queues:
                pool.run_task(self.fn, args, meta={
                    'priority': priority
                })

                # interval could either be a function or a number
                if callable(self.interval):
                    _interval = self.interval()
                else:
                    _interval = self.interval

                time.sleep(_interval)

            elif messages:
                # get payloads from messages & delete them from sqs
                payloads = []
                for message in messages:
                    payloads.append(json.loads(message.body))
                    message.delete()

                # run tasks
                for payload in payloads:
                    pool.run_task(self.fn, (payload['value'], ) + args, payload['meta'])

            # yield any available results
            if self.results:
                self._result_mutex.acquire()

                _error = None
                for result in self.results:
                    if type(result) == TaskError:

                        _error = result.error
                    else:
                        yield result

                if _error:
                    raise _error

                self.results = []
                self._result_mutex.release()

            # if no messages were found, wait for a while
            if in_queues and (not messages):
                time.sleep(random.randint(10, 50) / 10.0)

    def run(self, args, priority=0, iterate=False):
        if iterate:
            return self._run(args, priority=priority)

        for _ in self._run(args, priority=priority):
            pass
