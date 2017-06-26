#!/usr/bin/env python3
from setuptools import setup, find_packages

import dirtools

setup(
    name='dirtools',
    version=dirtools.__version__,
    packages=find_packages(),
    scripts=['bin/dirt'],
    extras_require={
        'cli': ['click', 'tabulate'],
        'test': ['pytest', 'click', 'tabulate'],
        'dev': ['ipython', 'Sphinx', 'pytest', 'click', 'tabulate'],
    },
    # metadata that uploads to PyPI
    author='Roy Enjoy',
    author_email='kirpit [at] gmail [dot] com',
    description="""dirtools3 is a utility package that helps you to scan file system folders to
collect statistical information about their sub contents (size, file count,
creation time, modification time etc. for each sub folder or file). It also
provides cleanup method to reduce their total size by removing low-redundant
items in given order. It is written in Python and currently supports only
Python version 3.6 or higher.""",
    license='GNU General Public License v3',
    keywords='dirtools, file system, folder size, trimming',
    url='https://github.com/kirpit/dirtools3',
    zip_safe=True,
)

