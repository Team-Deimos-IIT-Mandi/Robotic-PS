from setuptools import find_packages
from setuptools import setup

setup(
    name='dynamixel_sdk',
    version='4.0.3',
    packages=find_packages(
        include=('dynamixel_sdk', 'dynamixel_sdk.*')),
)
