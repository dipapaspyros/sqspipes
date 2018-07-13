from .task import TaskRunner


class TaskConfig(object):

    def __init__(self, config):
        self.key = 'AKIAIASBFLLJI7A233RA'
        self.secret = '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'
        self.domain = config['domain']

        # initialize tasks
        self.tasks = []
        prev_task = None
        for idx, t in enumerate(config['tasks']):
            task = self.parse_tasks(t, idx, in_queue_names=prev_task.out_queue_names if prev_task else [])
            self.tasks.append(task)
            prev_task = task

    def parse_tasks(self, task, idx, in_queue_names=None):
        if type(task) == function:
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
                'key': self.key,
                'secret': self.secret,
            },
            priorities=task.get('priorities', 0),
        )

    def get_task_by_name(self, task_name):
        if type(task_name) == int:
            return self.tasks[task_name]

        return [t for t in self.tasks if t.name == task_name][0]

    def run(self, task_name, args):
        # find task
        task = self.get_task_by_name(task_name)

        # setup queues & other utils
        task.setup()

        # run the task
        task.run(args)
