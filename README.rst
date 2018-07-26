sqspipes
========

A multi-worker pipe mechanism that uses AWS SQS.

Instructions
------------

1. Install the latest version of the package: ``pip install sqspipes``

2. Create a client

   .. code:: python

      from sqspipes.client import TaskClient
      client = TaskClient(domain='my-app', aws_key='YOUR_AWS_KEY', aws_secret='YOUR_AWS_SECRET', aws_region='us-west-2')

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