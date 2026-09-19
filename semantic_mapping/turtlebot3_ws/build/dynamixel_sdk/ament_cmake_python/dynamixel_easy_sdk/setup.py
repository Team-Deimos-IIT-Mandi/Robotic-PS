from setuptools import find_packages
from setuptools import setup

setup(
    name='dynamixel_easy_sdk',
    version='4.0.3',
    packages=find_packages(
        include=('dynamixel_easy_sdk', 'dynamixel_easy_sdk.*')),
)
