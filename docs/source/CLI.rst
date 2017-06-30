Command line interface (dirt)
=============================

Once you installed ``dirtools3`` successfully, the ``dirt`` command will be
available in your environment executables that you can invoke from any path
within your command line.

This command gives you nothing more than invoking every functionality of
:class:`dirtools.scanner.Folder` and displaying it nicely.

``dirt --help`` is pretty much self explanatory::

    Usage: dirt [OPTIONS] PATH

      Command line interface to the dirtools package.

    Options:
      -s, --sortby [atime_asc|atime_desc|mtime_asc|mtime_desc|ctime_asc|ctime_desc|smallest|largest|least_files|most_files|least_depth|most_depth]
                                      Sorting parameter to display the items in
                                      desired order. Defaults to "atime_desc" that
                                      shows recently accessed items at the
                                      beginning, which is opposite of "atime_asc".
                                      To display newly modified ones use
                                      "mtime_desc" and "mtime_asc" for vice versa.
      -o, --output [csv|simple|plain|grid|fancy_grid|pipe|orgtbl|jira|psql|rst|mediawiki|moinmoin|html|latex|latex_booktabs|tsv|textile]
                                      This option is passed directly to python-
                                      tabulate package as the "tablefmt"
                                      parameter, with the exception of manual
                                      "csv" output. Defaults to "simple". Check
                                      the current table formats from;
                                      https://bitbucket.org/astanin/python-
                                      tabulate.
      -p, --precision INTEGER RANGE   The floating precision of the human-readable
                                      size format. Does not have any affect if
                                      --nohuman is given. Integer value between 0
                                      to 11 and defaults to 2.
      -d, --depth INTEGER RANGE       The depth of sub folders you want to list,
                                      trim down, etc. Maximum allowed depth is 3
                                      sub-folders inside, limited only for the
                                      CLI. Integer value between 0 to 2 and
                                      defaults to 0 (zero).
      -nh, --nohuman                  Display only raw values such as file size in
                                      bytes, creation time in timestamp etc.
      --trim-down TEXT                The size to be trimmed down instead of
                                      listing, in human readable format. For
                                      example; "900mb".

                                      WARNING: --trim-down
                                      action DELETES your files and cannot be
                                      undo!
      -h, --help                      Show this message and exit.


Sort By
-------
One of the member of :class:`dirtools.scanner.SortBy` enum name, in lower-case string.


Output
------

You can display the folder items with different output other than ``simple`` that is
given to ``tabulate`` package to format. One handy output type could be ``csv``, combined with
``--nohuman`` flag if you need to export raw data to a flat file::

    $ dirt -o csv -nh /path/to/Python-3.6.0-source > py36-folder-items.csv
    # cat py36-folder-items.csv
    "Name","Size","Depth","Files","Created At","Modified At"
    "python.exe",2923572,0,1,1486429611,1486429611
    "pybuilddir.txt",33,0,1,1486429611,1486429611
    "build",13692866,10,183,1486429611,1486429662
    # ... etc


Precision
---------

If you need more precision for item sizes in human readable format, you can pass ``-p``
or ``--precision`` option to specify the floating decimal points::

    $ dirt -p 4 /path/to/Python-3.6.0-source
                 Name         Size    Depth    Files         Created At        Modified At
    -----------------  -----------  -------  -------  -----------------  -----------------
           python.exe    2.7881 Mb        0        1  2017 Feb 07 01:06  2017 Feb 07 01:06
       pybuilddir.txt      33 Byte        0        1  2017 Feb 07 01:06  2017 Feb 07 01:06
                build   13.0585 Mb       10      183  2017 Feb 07 01:06  2017 Feb 07 01:07
      libpython3.6m.a    9.4331 Mb        0        1  2017 Feb 07 01:06  2017 Feb 07 01:06
         Makefile.pre   57.4102 Kb        0        1  2017 Feb 06 23:55  2017 Feb 06 23:55
    # ... etc


Depth
-----
This is the ``level`` keyword parameter of :class:`dirtools.scanner.Folder` class.
Please refer to its documentation for different use cases such as the items are not in
the root folder but in ``N`` number of _levels_ inside the given folder.

No Human
--------
If you need to display the items in raw format for some reason, meaning the sizes will
be in bytes (integer), access, modify and change time metadata in timestamp, you may
pass the ``-nh`` or ``--nohuman`` flag option to do so.

Trimming Down
-------------

This is the equivalent of calling :meth:`dirtools.scanner.Folder.cleanup_items`
instead of :meth:`dirtools.scanner.Folder.items`.

.. warning::

    Result of this method is to DELETE the physical files / folders
    on your disk until the given size matches the actual size
    and there is NO UNDO for this operation.

Displaying output will be the items that were actually deleted from your storage.
Therefore, invoking this option with the same parameter for the second time on the
same folder, probably will do nothing.