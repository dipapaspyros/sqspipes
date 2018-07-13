import boto3

from .utils.task_pool import TaskPool


class TaskRunner(object):

    def __init__(self, fn, in_queue_names, domain, name, aws_config, workers=1, priorities=0):
        self.fn = fn
        self.in_queues = in_queue_names
        self.domain = domain
        self.name = name
        self.in_queue_names = in_queue_names
        self._out_queue_names = None
        self.workers = workers
        self.aws_config = aws_config
        self.priority_levels = list(reversed(range(priorities + 1)))

    def queue_name(self, priority):
        base_name = '%s-%s' % (self.domain, self.name)

        if not priority:
            return base_name

        return '%s-%d' % (base_name, priority)

    @property
    def out_queue_names(self):
        if self._out_queue_names is not None:
            return self._out_queue_names

        self._out_queue_names = [self.queue_name(priority) for priority in self.priority_levels]

        return self._out_queue_names

    def sqs(self):
        return boto3.resource(
            self.aws_config['region'],
            'us-west-2',
            aws_access_key_id=self.aws_config['key'],
            aws_secret_access_key=self.aws_config['secret'],
        )

    def setup(self):
        sqs = self.sqs()

        for queue_name in self.out_queue_names:
            q = sqs.get_queue_by_name(QueueName=queue_name)
            import pdb; pdb.set_trace()

    def run(self, args):
        # create the thread pool
        pool = TaskPool(self.workers)

        # initialize boto service
        sqs = self.sqs()

        # get input queues
        in_queues = []
        for in_queue_name in self.in_queue_names:
            in_queues.append(sqs.get_queue_by_name(QueueName=in_queue_name))

        #
        pool.run_task(self.fn, args)