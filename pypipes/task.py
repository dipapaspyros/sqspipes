import json
import random
import time
import traceback
import uuid

import boto3
from botocore.errorfactory import ClientError
from multiprocessing import Lock

from .utils.task_pool import TaskPool


class TaskRunner(object):

    def __init__(self, fn, in_queue_names, domain, name, aws_config, workers=1, priorities=0, interval=2, final=False):
        self.fn = fn
        self.domain = domain
        self.name = name
        self.in_queue_names = in_queue_names
        self.out_queues = []
        self._out_queue_names = None
        self.workers = workers
        self.aws_config = aws_config
        self.priority_levels = list(reversed(range(priorities + 1)))
        self.final = final
        self.interval = interval
        self.results = []
        self._result_mutex = Lock()

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

        if not self.final:
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
                messages += in_queue.receive_messages()
                if len(messages) >= self.workers:
                    break

            if not in_queues:
                pool.run_task(self.fn, args, meta={
                    'priority': priority
                })

                time.sleep(self.interval)

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
                for result in self.results:
                    yield result

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
