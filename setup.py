from distutils.core import setup

try:
    long_description = open('README.rst', encoding='utf8').read()
except IOError:
    long_description = ''
except TypeError:
    long_description = ''


setup(
    # Application name
    name="sqspipes",

    # Version number
    version="0.1.2",

    # Application author details
    author="Dimitris Papaspyros",
    author_email="dimitris@orfium.com",

    # Packages
    packages=["sqspipes", "sqspipes/utils"],

    # Include additional files into the package
    include_package_data=True,

    # Details
    url="https://github.com/dipapaspyros/sqspipes",
    license="LICENSE",
    description="A multi-worker pipe mechanism that uses AWS SQS",
    long_description=long_description,

    # Dependent packages (distributions)
    install_requires=[
        'boto3',
        'botocore',
    ],
)
