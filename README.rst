sqspipes
========

A multi-worker pipe mechanism that uses AWS SQS.

Instructions
------------

1. Install the latest version of the package: ``pip install sqspipes``

2. Create a client

   .. code:: python

      from sqspipes import TaskClient
      client = TaskClient(
          domain='my-app',
          aws_key='YOUR_AWS_KEY',
          aws_secret='YOUR_AWS_SECRET',
          aws_region='us-west-2'
      )

   Make sure that the ``aws_key`` provided has full access to the SQS
   service, since it needs to be able to create & delete queues.

   Also ensure that the ``aws_region`` provided is either ``us-west-2``
   or ``us-east-2``, since other regions do not support FIFO queues
   which are used by this package.

3. Define the tasks you may have:

   .. code:: python

      import os
      import sys
      import random
      import string
      import time

      def _generate(max_size):
          return ''.join(random.choice(string.ascii_lowercase) for _ in range(random.randint(1, max_size)))


      def _reduce(value, keep='vowels'):
          vowels = ['a', 'e', 'i', 'o', 'u', ]

          result = [v for v in value if (v in vowels) == (keep == 'vowels')]

          return value, ''.join(result)


      def _count(data):
          value, vowels = data

          return value, len(vowels)

   In this example we have a simple flow that looks like this:

   generate word -> reduce word to only its vowels -> count the reduced
   word

   This is similar to a map-reduce algorithm, however using this module
   you might have many layers where each transforms the original data in
   a different way. These layers (``tasks``) are then combined like bash
   pipes, where the output from a task is the input to the next one.

   Notice the few things:

   1) The first argument of each ``task`` is going to be fed with the
      output from the previous one, with the obvious exception of the
      first task.

   2) The output of each task should be json serializable.

   3) You may return ``None`` from a task if you do not want it to
      continue further in the processing line. This could be done e.g
      because your tasks are picked from a database, so you could return
      ``None`` if that database is empty. If for any reason you want to
      process ``None`` like a normal task output/input, you can pass
      ``ignore_none=False`` as a parameter to the ``TaskClient``
      constructor. In that case, you can use the following to return an
      empty task output.

   .. code:: python

      from sqspipes import EmptyTaskOutput

      def my_task()
          # your task's logic here

          return EmptyTaskOutput()  # for some reason, None is a valid task output

      # later in your code...

      TaskClient(
          domain='my-app',
          aws_key='YOUR_AWS_KEY',
          aws_secret='YOUR_AWS_SECRET',
          aws_region='us-west-2',
          ignore_none=False
      )
4. Register the tasks

   Now that you have created the various ``tasks``, you simply have to
   define their order & other runtime parameters, like this:

   .. code:: python

      client.register_tasks([
          {'method': _generate, 'workers': 32, 'interval': 0.1},
          {'method': _reduce, 'workers': 2},
          {'method': _count, 'workers': 16}
      ])

   The following keys are supported for each task:

   ::

       `method`:
           A callable object. This is the function that will actually be executed.
           For all tasks except for the first one, the first argument of this method
           will be the result of the previous task's method.

       `name`:
           The name of this tasks.
           If no name is provided, the method's name is automatically used.

       `workers`:
           The number of worker threads that will be processing messages in parallel.
           Defaults to 1.

       `priorities`:
           The number of different priority levels, where 0 is the lowest possible priority.
           Defaults to 1, maximum value is 16.

       `interval`:
           Only applies to the first task.
           Number of seconds to wait between each execution.
           Can either be an number, or a callable that returns an number (e.g `lambda: random.random() * 5`)
           Defaults to 0.

5. Execute the tasks

   A script that would execute the tasks we described would look like
   this:

   .. code:: python

      # script.py file
      import sys

      def generate(workers):
          for res in client.run('_generate', args=(10, ), iterate=True, workers=workers):
              print(res)


      def reduce(workers):
          for res in client.run('_reduce', iterate=True, workers=workers):
              print('%s -> %s' % res)


      def count(workers):
          for result in client.run('_count', iterate=True, workers=workers):
              print('%s -> %d' % result)


      try:
          n_workers = int(sys.argv[2])
      except ValueError:
          n_workers = None

      try:
          if sys.argv[1] == 'generate':
              generate(n_workers)
          elif sys.argv[1] == 'reduce':
              reduce(n_workers)
          elif sys.argv[1] == 'count':
              count(n_workers)
          else:
              raise ValueError('Invalid argument: must be one of generate, reduce or count')
      except IndexError:
          raise ValueError('Script argument is required')

   In this example, we have a script which, based on the provided
   argument, executes one of the three tasks defined in the previous
   step. Notice that you can have the following setup:

   1. A machine M1 running the command ``python script.py generate 8``
      that would create 8 workers which would submit new words for
      processing.

   2. A machine M2 running the command ``python script.py reduce 16``
      that would create 16 workers that would reduce words only to their
      vowels.

   3. A machine in this example could be a different node (VM, physical
      computer etc.), but tasks could of course run on the same
      infrastructure as well.

   4. An unhandled exception on one of the tasks will bring down the
      entire task runner. This is intentional, since otherwise if
      unhandled exceptions were “swallowed”, it would be much harder to
      debug issues, or even identify and track down those “lost”
      packages. It is up to you to handle any exceptions you want in any
      possible manner.
