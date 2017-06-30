dirtools3
=========

.. image:: https://travis-ci.org/kirpit/dirtools3.svg?branch=master
    :target: https://travis-ci.org/kirpit/dirtools3

Introduction
------------
dirtools3 is a utility package that helps you to scan file system folders to
collect statistical information about their sub contents (size, file count,
access time, modify time, change time etc. for each sub folder or file). It also
provides cleanup method to reduce their total size by removing low-redundant
items in given order. It is written in Python and currently supports only
Python version 3.6 or higher.

Command Line Usage
------------------

You can use :doc:`CLI` script to invoke the library if you don't need
to process each item individually within another application. The ``dirt``
script is delivered to your environment executable folder when you install
this package. To use ``dirt`` command, you will also need to install Python
``click`` and ``tabulate`` dependencies.

This command line utility is fully capable of displaying items (or trimmed items)
in specified ``tabulate`` format or in ``csv`` with any given sorting option::

    $ dirt -s largest /path/to/Python-3.6.0-source

                 Name       Size    Depth    Files        Access Time        Modify Time        Change Time
    -----------------  ---------  -------  -------  -----------------  -----------------  -----------------
                  Lib   35.81 Mb        7     2184  2017 Apr 09 06:18  2017 Feb 07 01:07  2017 Feb 07 01:07
              Modules   18.18 Mb        5      774  2017 Apr 09 06:18  2017 Feb 07 01:43  2017 Feb 07 01:43
                build   13.06 Mb       10      183  2017 Apr 09 06:18  2017 Feb 07 01:07  2017 Feb 07 01:07
      libpython3.6m.a    9.43 Mb        0        1  2017 Feb 07 01:06  2017 Feb 07 01:06  2017 Feb 07 01:06
                  Doc    9.01 Mb        4      556  2017 Apr 09 06:18  2016 Dec 23 02:21  2017 Feb 06 02:18
    # ...
     python-config.py    2.01 Kb        0        1  2017 Feb 07 01:07  2017 Feb 07 00:09  2017 Feb 07 00:09
        python-config    2.01 Kb        0        1  2017 Feb 07 23:01  2017 Feb 07 00:09  2017 Feb 07 00:09
              .github   346 Byte        1        1  1970 Jan 01 00:00  2016 Dec 23 02:21  2017 Feb 06 02:18
       pybuilddir.txt    33 Byte        0        1  2017 Feb 07 01:06  2017 Feb 07 01:06  2017 Feb 07 01:06
        40 items with total of 121.31 Mb data; took 0.288 second(s).


Default sorting for the ``dirt`` command is :const:`dirtools.scanner.SortBy.ATIME_DESC`.

Library Usage
-------------

There is a scanning instantiating class :class:`dirtools.scanner.Folder`
that takes care of the parallel folder scanning process in the default event loop
under the hood using async generators. Therefore, it is preferred to start and
trigger the scanning process as early as possible. Sample usage of ``Folder``
would be listing a folder by using ``Folder`` class::

    from dirtools import Folder, SortBy
    from dirtools.utils import bytes2human

    path = '/path/to/Python-3.6.0-source'
    # There is no default ``sort_by`` argument within the scanner class
    folder = Folder(path, SortBy.LARGEST)

    # ... do other stuff if possible, path scan is about to start in parallel.

    # next line will actually _block_ and wait for scanning to complete:
    size_human = bytes2human(folder.total_size) # from integer in bytes

    # None of the rest will block anymore as the scanning has been completed
    assert len(folder) == 40
    assert size_human == '121.31 Mb'

    # The items (sub directories and/or flat files) are ready
    # in the given SortBy.LARGEST order:
    largest_item = next(folder.items())
    assert largest_item == {
        'atime': '2017 Apr 09 06:18',
        'ctime': '2017 Feb 07 01:07',
        'depth': 7,
        'mtime': '2017 Feb 07 01:07',
        'name': 'Lib',
        'num_of_files': 2184,
        'size': '35.81 Mb'}

    # If you some reason need the non-human raw values
    # (such as size in bytes, creation and modification time in timestamps)
    largest_item_raw = next(folder.items(humanise=False))
    assert largest_item_raw == {
        'atime': 1491718693,
        'ctime': 1486429664,
        'depth': 7,
        'mtime': 1486429664,
        'name': 'Lib',
        'num_of_files': 2184,
        'size': 37552912}

    # Re-ordering without the whole file system scanning process is possible
    folder.resort(SortBy.SMALLEST)
    smallest_item = next(folder.items())
    assert smallest_item == {
        'atime': '2017 Feb 07 01:06',
        'ctime': '2017 Feb 07 01:06',
        'depth': 0,
        'mtime': '2017 Feb 07 01:06',
        'name': 'pybuilddir.txt',
        'num_of_files': 1,
        'size': '33 Byte'}

Contents
========

.. toctree::
    :maxdepth: 2

    installation
    CLI
    scanner
    utils



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

