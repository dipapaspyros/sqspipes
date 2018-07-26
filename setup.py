from distutils.core import setup

setup(
    # Application name
    name="pypipes",

    # Version number
    version="0.0.1",

    # Application author details
    author="Dimitris Papaspyros",
    author_email="dimitris@orfium.com",

    # Packages
    packages=["pypipes"],

    # Include additional files into the package
    include_package_data=True,

    # Details
    url="https://github.com/dipapaspyros/pypipes",
    license="LICENSE",
    description="A multi-worker pipe mechanism that uses AWS SQS",

    # Dependent packages (distributions)
    install_requires=[
        'boto3'
    ],
)
