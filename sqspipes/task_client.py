from collections import Iterable
from types import FunctionType

import boto3

from .task import TaskRunner


class TaskClientError(ValueError):
    pass


class TaskClient(object):

    SQS_FIFO_AVAILABLE_AT = ('us-west-2', 'us-east-2', )

    def __init__(self, domain, aws_key, aws_secret, aws_region='us-west-2'):
        """
        :param domain: A unique identifier of the application that uses the client (e.g my_awesome_app)
        :param aws_key: The AWS key that will be used. Should have full access to the SQS service.
        :param aws_secret: The AWS secret for the key used.
        :param aws_region: The AWS region. Defaults to us-west-2
        """

        if aws_region not in self.SQS_FIFO_AVAILABLE_AT:
            raise TaskClientError(
                '`aws_region` must be one of %s - FIFO queues are not supported on other regions.' %
                ','.join(self.SQS_FIFO_AVAILABLE_AT)
            )

        self.aws_region = aws_region
        self.aws_key = aws_key
        self.aws_secret = aws_secret

        if not domain:
            raise TaskClientError('`domain` field is required.')

        self.domain = domain

        # tasks are initially empty
        self.tasks = []

    def register_tasks(self, tasks):
        """
        :param tasks: Registers the tasks. Each task might be of the following form:
            {
                'method':
                    A callable object. This is the function that will actually be executed.
                    For all tasks except for the first one, the first argument of this method
                    will be the result of the previous task's method.

                'name':
                    The name of this tasks. Tasks can later be retrieved by their name.
                    If no name is provided, the method's name is automatically used.

                'workers':
                    The number of worker threads that will be processing messages in parallel.
                    Defaults to 1.

                'priorities':
                    The number of different priority levels, where 0 is the lowest possible priority.
                    Defaults to 1, maximum value is 16.

                'interval':
                    Number of seconds to wait between each execution.
                    This only applies to the first task.
                    Defaults to 0.
            }

            For clarity, if the defaults are used, instead of the dictionary described above,
            a method might only be passed instead for each one of the tasks.
        :return:
        """
        if not tasks:
            raise TaskClientError('`tasks` field is required.')

        if not isinstance(tasks, list):
            raise TaskClientError('`tasks` field must be a list of task configurations.')

        # initialize tasks
        self.tasks = []
        prev_task = None
        for idx, t in enumerate(tasks):
            task = self._parse_tasks(
                t,
                in_queue_names=prev_task.out_queue_names if prev_task else [],
                final=idx == len(tasks) - 1
            )
            self.tasks.append(task)
            prev_task = task

    def _parse_tasks(self, task, in_queue_names=None, final=False):
        if type(task) == FunctionType:
            task = {
                'method': task,
            }

        if not task.get('name'):
            task['name'] = task['method'].__name__

        return TaskRunner(
            domain=self.domain,
            fn=task['method'],
            name=task['name'],
            in_queue_names=in_queue_names,
            workers=task.get('workers', 1),
            aws_config={
                'region': self.aws_region,
                'key': self.aws_key,
                'secret': self.aws_secret,
            },
            priorities=min(task.get('priorities', 0), 16),
            interval=task.get('interval', 0),
            final=final
        )

    def get_task_by_name(self, task_name):
        """
        :param task_name: Retrieves a task by its name. The tasks index can also be used.
        :return:
        """
        if type(task_name) == int:
            return self.tasks[task_name]

        return [t for t in self.tasks if t.name == task_name][0]

    @property
    def sqs_client(self):
        """
        :return: An SQS client
        """
        return boto3.client(
            'sqs',
            self.aws_region,
            aws_access_key_id=self.aws_key,
            aws_secret_access_key=self.aws_secret,
        )

    @property
    def queues(self):
        """
        :return: A list of the queues created for this domain
        """
        return self.sqs_client.list_queues(
            QueueNamePrefix=self.domain
        ).get('QueueUrls', [])

    def delete(self):
        """
        :return: Deletes all of the queues for this particular domain
        """
        for queue in self.queues:
            self.sqs_client.delete_queue(
                QueueUrl=queue
            )

    def purge(self):
        """
        :return: Empties all of the queues for this particular domain
        """
        for queue in self.queues:
            self.sqs_client.purge_queue(
                QueueUrl=queue
            )

    def run(self, task_name, args=None, priority=0, iterate=False):
        """
        Executes a specific task from its configuration
        :param task_name: The name of the task to execute (or it's index for unnamed tasks)
        :param args: Arguments for the executed tasks
        :param priority: Use one of the task's priority levels to prioritize before other executions
        :param iterate: If set to true, it returns an iterator that yields the results while the task is running
        :return: An iterator if iterate is set to True, None otherwise (should never stop unless interrupted)
        """

        if not self.tasks:
            raise TaskClientError('Tasks have not been initialized.')

        if args is None:
            args = ()

        # find task
        task = self.get_task_by_name(task_name)

        # setup queues & other utils
        task.setup()

        # run the task
        return task.run(args, priority=priority, iterate=iterate)
