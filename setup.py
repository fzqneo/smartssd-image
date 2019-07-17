#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The setup script."""

from setuptools import setup, find_packages

with open('README.md') as readme_file:
    readme = readme_file.read()

requirements = []

setup_requirements = ['pytest-runner', ]

test_requirements = ['pytest', ]

setup(
    author="Ziqiang Feng",
    author_email='zf@cs.cmu.edu',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Natural Language :: English',
        "Programming Language :: Python :: 2",
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
    description="Smart SSD/Disk Experiments",
    install_requires=requirements,
    license="Apache Software License 2.0",
    long_description=readme + '\n\n',
    include_package_data=True,
    keywords='s3dexp',
    name='s3dexp',
    packages=find_packages(),
    setup_requires=setup_requirements,
    url='https://github.com/fzqneo/smartssd-image',
    version='0.0.1',
    zip_safe=False,
)
