Installation
------------
You can install the package by pip from pypi that has no dependency as a library::

    pip install dirtools3


Alternatively, you can also install :doc:`CLI` dependencies (see below) by passing
the extras flag for setuptools::

    pip install dirtools3[cli]

Dependencies
------------
There is no dependency other than Python 3.6+ for using it as a library
(by importing within your application for example). However one must install
Python `tabulate package <https://bitbucket.org/astanin/python-tabulate>`_
and `click package <http://click.pocoo.org/5/>`_ if planning to call the
:doc:`CLI`. If you haven't installed already with ``dirtools3[cli]`` you can
manually install them by::

    pip install tabulate click



