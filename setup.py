from distutils.core import setup

try:
    import pypandoc

    long_description = pypandoc.convert('README.md', 'rst')
except(IOError, ImportError):
    long_description = open('README.md').read()

setup(
    # Application name
    name="sqspipes",

    # Version number
    version="0.0.4",

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
