from types import FunctionType

from .task import TaskRunner


class TaskConfig(object):

    def __init__(self, config, aws_key, aws_secret, aws_region):
        # must be us-west-2 or us-east-2
        # TODO validate
        self.aws_region = aws_region
        self.aws_key = aws_key
        self.aws_secret = aws_secret

        self.domain = config['domain']

        # initialize tasks
        self.tasks = []
        prev_task = None
        for idx, t in enumerate(config['tasks']):
            task = self.parse_tasks(
                t, idx,
                in_queue_names=prev_task.out_queue_names if prev_task else [],
                final=idx == len(config['tasks']) - 1
            )
            self.tasks.append(task)
            prev_task = task

    def parse_tasks(self, task, idx, in_queue_names=None, final=False):
        if type(task) == FunctionType:
            task = {
                'fn': task,
            }

        return TaskRunner(
            domain=self.domain,
            fn=task['fn'],
            name=task.get('name', 'task-%d' % idx),
            in_queue_names=in_queue_names,
            workers=task.get('workers', 1),
            aws_config={
                'region': self.aws_region,
                'key': self.aws_key,
                'secret': self.aws_secret,
            },
            priorities=task.get('priorities', 0),
            final=final
        )

    def get_task_by_name(self, task_name):
        if type(task_name) == int:
            return self.tasks[task_name]

        return [t for t in self.tasks if t.name == task_name][0]

    def run(self, task_name, args=None, priority=0, iterate=False):
        if args is None:
            args = ()

        # find task
        task = self.get_task_by_name(task_name)

        # setup queues & other utils
        task.setup()

        # run the task
        return task.run(args, priority=priority, iterate=iterate)
