#!/usr/bin/env python

from setuptools import setup

setup(
    name='angler', version='0.2',
    url='http://packages.integralws.com/angler',
    author='Ryan Marquardt',
    author_email='ryan@integralws.com',
    packages=['angler'],
    package_data={
        'angler': ['modules/*.*'],
    },
    scripts=['bin/angler-shell'],
)
