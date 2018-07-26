import os
import sys
import random
import string
import time

from sqspipes.task_client import TaskClient

try:
    AWS_KEY = os.environ['AWS_KEY']
    AWS_SECRET = os.environ['AWS_SECRET']
    AWS_REGION = os.environ.get('AWS_REGION', 'us-west-2')
except KeyError:
    from sqspipes.tests_env import *


def _generate(max_size):
    return ''.join(random.choice(string.ascii_lowercase) for _ in range(random.randint(1, max_size)))


def _reduce(value, keep='vowels'):
    vowels = ['a', 'e', 'i', 'o', 'u', ]
    if keep == 'vowels':
        result = [v for v in value if v in vowels]
    else:
        result = [v for v in value if v not in vowels]

    return value, ''.join(result)


def _count(data):
    value, vowels = data

    return value, len(vowels)


client = TaskClient(domain='word-counter', aws_key=AWS_KEY, aws_secret=AWS_SECRET, aws_region=AWS_REGION)

client.register_tasks([
    {'method': _generate, 'workers': 32, 'interval': 0.1},
    {'method': _reduce, 'workers': 2},
    {'method': _count, 'workers': 16}
])


def generate():
    for res in client.run('_generate', args=(10, ), iterate=True):
        print(res)


def reduce():
    for res in client.run('_reduce', iterate=True):
        print('%s -> %s' % res)


def count():
    for result in client.run('_count', iterate=True):
        print('%s -> %d' % result)


try:
    if sys.argv[1] == 'generate':
        generate()
    elif sys.argv[1] == 'reduce':
        reduce()
    elif sys.argv[1] == 'count':
        count()
    else:
        raise ValueError('Invalid argument: must be one of generate, reduce or count')
except IndexError:
    raise ValueError('Script argument is required')
