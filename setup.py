from distutils.core import setup

setup(
    # Application name
    name="orfium_earnings_dashboard_sdk",

    # Version number
    version="0.3.1",

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
    description="A pipe mechanism for python tasks that uses AWS SQS",

    # Dependent packages (distributions)
    install_requires=[
        'boto3'
    ],
)
