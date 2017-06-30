import asyncio
import os
import shutil
import time
from collections import deque, AsyncIterable
from enum import Enum
from functools import partial

from typing import Iterator, Tuple

from dirtools import utils
from dirtools.loggers import logger


class SortBy(Enum):
    """Helper class to be given one of its following constants as the sorting
    option to the :class:`FolderScan`.

    >>> from dirtools import Folder, SortBy
    >>>
    >>> scan = Folder('/path/to/scan', SortBy.CTIME_ASC)
    >>> for item in scan.items():
    >>>     print(item)
    >>> scan.resort(SortBy.LARGEST)
    >>> # etc..
    """

    #: Access time ascending
    ATIME_ASC = 1
    #: Access time descending
    ATIME_DESC = 2
    #: Modify time ascending
    MTIME_ASC = 3
    #: Modify time descending
    MTIME_DESC = 4
    #: Change time ascending
    CTIME_ASC = 5
    #: Change time descending
    CTIME_DESC = 6

    #: Smallest in size items first whether it's a file or folder.
    SMALLEST = 7
    #: Largest in size items first whether it's a file or folder.
    LARGEST = 8
    #: The items with the least number of files first.
    LEAST_FILES = 9
    #: The items with the most number of files first.
    MOST_FILES = 10
    #: The folder that have the deepest sub folders first.
    LEAST_DEPTH = 11
    #: The folder that have the shallowest sub folders first.
    MOST_DEPTH = 12

    def __str__(self):
        return self.name

    def __int__(self):
        return self.value


class Folder(object):
    """The main class behind the magic that takes care of scanning an entire
    folder and its sub folders, recursively in the asynchronous manner.

    It is highly suggested that you instantiate your object from this class
    at the earliest step of your programme, as it will start doing its job
    in background. Once you require to access one of its public method, it
    will then block until the scanning is complete or will deliver the
    result straight away if it's already done. For example:

    .. code-block::python

        from dirtools.scanner import Folder, SortBy
        scan = Folder('/path/to/scan', SortBy.CTIME_ASC)

        # do a lot of other work here...

        # and when you just need it:
        for item in scan.items:
            # do something with the item
            pass

    Following methods and properties are available:

        * :meth:`.__len__`
        * :attr:`.total_size`
        * :meth:`.items`
        * :meth:`.cleanup_items`
        * :meth:`.resort`

    :param path: Actual path on disk to be scanned.
    :type path: str
    :param sort_by: SortBy enum value
    :type sort_by: SortBy
    :param level: The sub level (sub folder depth) to be considered as
        categorising folders. Defaults to 0 (zero).

        For example if your folder structure is like `{artist}/the-song.mp3`
        and you want to list _entire_ mp3 files your parameter should be
        `level=1`. Leaving it to default value 0 (zero) will list each
        _artist_ folder in the results rather than their mp3s.

        Moreover the same logic, if you have your _artist_ folders in
        different _genre_s, such as `{genre}/{artist}/the-song.mp3` and you
        still like to display / clean up them (see :meth:`cleanup_items`)
        in by the _artist_ items, your parameter is perhaps still `level=1`
        to scan under the `{genre}` folders.
    :type level: int
    :param time_format: Optional date/time parsing format for _humanising_
        the `size`, `atime`, `mtime` and `ctime` attributes of each item. 
        Defaults to :attr:`._time_format`. See details for customising 
        this parameter:

        https://docs.python.org/3/library/datetime.html#strftime-strptime-behavior
    :type time_format: str
    """
    #: Public property that will be calculated and set to total processing time
    #: once the parallel scanning has been finished.
    exec_took = None

    #: The default date/time humanising format.
    _time_format = '%Y %b %d %H:%M'
    _items_len = 0
    _items = None
    _total_size = None
    _root = None
    _level = None
    _scanning = None

    def __init__(self, path: str, sort_by: SortBy,
                 level: int = 0, time_format: str = _time_format):
        self.exec_took = time.time()
        self._total_size = 0
        self._items = deque()
        self._scanning = asyncio.ensure_future(self._scan(sort_by))
        self._root = os.path.abspath(path)
        self._level = level
        self._time_format = time_format

    def __len__(self) -> int:
        """Direct integer representation of the current items' length. Blocks until the scanning 
        operation has been completed on first access.
        
        >>> folder = Folder('/path/to/Python-3.6.0-source')
        >>> assert len(folder) == 40 

        :return: Length of the items (sub-directories or files) inside the scanned folder.
        :rtype: int
        """
        self._await()
        return self._items_len

    @property
    def total_size(self) -> int:
        """Returns the calculated total size of whole items, in bytes. Use
        :func:`dirtools.utils.bytes2human` for converting human readable format.

        Blocks until the scanning operation has been completed on first access.

        :return: Total size of given directory in bytes.
        :rtype: int
        """
        self._await()
        return self._total_size

    def items(self, humanise: bool=True, precision: int=2) -> Iterator[dict]:
        """Returns an iterator for scanned items list. It doesn't return the
        internal _items list because we don't want it to be modified outside.

        Blocks until the scanning operation has been completed on first access.

        :param humanise: Humanise flag to format results (defaults to True)
        :type humanise: bool
        :param precision: The floating precision of the human-readable size format (defaults to 2).
        :type precision: int
        :return: Iterator for the internal _items list.
        :rtype: iterator
        """
        self._await()

        # Don't humanise
        if humanise is False:
            return iter(self._items)

        # Humanise
        humanise_item = partial(self._humanise_item, precision=precision)
        return map(humanise_item, self._items)

    @classmethod
    def _humanise_item(cls, item: dict, precision: int) -> dict:
        humanised = item.copy()
        humanised['size'] = utils.bytes2human(item['size'], precision=precision)
        humanised['atime'] = time.strftime(cls._time_format, time.gmtime(item['atime']))
        humanised['mtime'] = time.strftime(cls._time_format, time.gmtime(item['mtime']))
        humanised['ctime'] = time.strftime(cls._time_format, time.gmtime(item['ctime']))
        return humanised

    def cleanup_items(self, max_total_size: str, humanise: bool=True, precision: int=2) -> Iterator[dict]:
        """Completely removes every item starting from the first in given
        sorting order until it reaches to ``max_total_size`` parameter. Returns
        empty generator if the given ``max_total_size`` parameter is equal or greater
        than entire total size. Otherwise removes and yields every deleted item.

        Blocks until the scanning operation has been completed on first access.

        .. warning::

            Result of this method is to DELETE the physical files / folders
            on your disk until the given size matches the actual size
            and there is NO UNDO for this operation.

        :param max_total_size: Human representation of total desired size.
                See: :func:``dirtools.utils.human2bytes``.
        :type max_total_size: str
        :param humanise: Humanise flag (required, no default value).
        :type humanise: bool
        :param precision: The floating precision of the human-readable size format (defaults to 2).
        :type precision: int
        :return: iterator
        """
        self._await()

        # Start deleting in the sorted order
        old_len = self._items_len
        old_size = self._total_size
        max_total_size = utils.human2bytes(max_total_size)
        while self._total_size > max_total_size:
            item = self._items.popleft()
            self._total_size -= item['size']
            self._items_len -= 1
            item_path = os.path.abspath(os.path.join(self._root, item['name']))

            # REMOVE THE ITEM PERMANENTLY
            try:
                shutil.rmtree(item_path)
            except NotADirectoryError:
                os.remove(item_path)

            # yield removed item
            yield self._humanise_item(item, precision) if humanise else item

        # Reduced to desired size
        logger.debug('{del_len:d} items with total of {del_size} data has been deleted.'.format(
            del_len=old_len - self._items_len,
            del_size=utils.bytes2human(old_size - self._total_size)))

    def _await(self) -> None:
        if self._scanning.done() is False:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self._scanning)

    def _get_depth(self, path: str) -> int:
        return os.path.relpath(path, self._root).count(os.sep)

    async def _iter_items(self, path: str) -> AsyncIterable:
        with os.scandir(path) as directory:
            for item in directory:
                current_level = self._get_depth(item.path)

                # happy scenario, we are in the exact level of requested
                # so return whatever it is, a folder, a file or a symlink.
                if current_level == self._level:
                    yield item
                    continue

                # we did't reach the requested sub level yet
                # so send recursive _scan inside if this is a folder.
                elif current_level < self._level and item.is_dir():
                    async for e in self._iter_items(item.path):
                        yield e

                # and ignore any other scenario including ignoring files and
                # symlinks, if the level is not reached yet.
                continue

    def _get_attributes(self, item: os.DirEntry) -> dict:
        """Parses entire item and subdirectories and returns:

        * Total size in bytes
        * Maximum folder depth of item
        * Total number of files this item contains
        * Access timestamp
        * Modification timestamp
        * Change timestamp

        in the same order as tuple.

        :param item: DirEntry object
        :type item: posix.DirEntry
        :return: Dictionary of {size, depth, num_of_files, atime, mtime, ctime}
        :rtype: dict
        """
        # it's a file or symlink, size is already on item stat
        if not item.is_dir(follow_symlinks=False):
            stat = item.stat(follow_symlinks=False)
            return {'size': stat.st_size,
                    'depth': self._get_depth(item.path) - self._level,
                    'num_of_files': 1,
                    'atime': int(stat.st_atime),
                    'mtime': int(stat.st_mtime),
                    'ctime': int(stat.st_ctime)}

        # It is a folder, recursive size check
        else:
            total_size = num_of_files = depth = 0
            atime = mtime = ctime = 0

            with os.scandir(item.path) as directory:
                for i in directory:
                    attrs = self._get_attributes(i)
                    total_size += attrs['size']
                    num_of_files += attrs['num_of_files']
                    atime = max(atime, attrs['atime'])
                    mtime = max(mtime, attrs['mtime'])
                    ctime = max(ctime, attrs['ctime'])
                    depth = max(depth, attrs['depth'])

            return {'size': total_size,
                    'depth': depth,
                    'num_of_files': num_of_files,
                    'atime': atime,
                    'mtime': mtime,
                    'ctime': ctime}

    @staticmethod
    def _get_item_sort_key(sort_by: SortBy) -> Tuple[str, bool]:
        """Internal static method to find the item key and ascending/descending
        flag based on the given `sort_by` parameter.

        It is a `TypeError` to give anything other than :class:`SortBy` defined
        attributes.

        :param sort_by: SortBy enum attribute
        :type sort_by: SortBy
        :return: (item key to sort, reverse)
        :rtype: (str, bool)
        :exception: Throws `TypeError` if not a :class:`SortBy` enum element.
        """
        if sort_by is SortBy.ATIME_ASC:
            return 'atime', False
        elif sort_by is SortBy.ATIME_DESC:
            return 'atime', True
        elif sort_by is SortBy.MTIME_ASC:
            return 'mtime', False
        elif sort_by is SortBy.MTIME_DESC:
            return 'mtime', True
        elif sort_by is SortBy.CTIME_ASC:
            return 'ctime', False
        elif sort_by is SortBy.CTIME_DESC:
            return 'ctime', True
        elif sort_by is SortBy.SMALLEST:
            return 'size', False
        elif sort_by is SortBy.LARGEST:
            return 'size', True
        elif sort_by is SortBy.LEAST_FILES:
            return 'num_of_files', False
        elif sort_by is SortBy.MOST_FILES:
            return 'num_of_files', True
        elif sort_by is SortBy.LEAST_DEPTH:
            return 'depth', False
        elif sort_by is SortBy.MOST_DEPTH:
            return 'depth', True

        raise TypeError('Given sort by parameter is invalid: {0!r}'.format(sort_by))

    def _find_index(self, summary: dict, sort_by: SortBy) -> int:
        """Internal method to find the desired index to insert the given item,
        based on `sort_by` parameter.

        Remember this methods runs whilst the scanning process so the returned
        index might not be absolute and may return with little error. This issue
        is fixed at the end of scanning with the help of :meth:`.resort`.

        :param summary: Item object that is not within the internal list yet.
        :type summary: dict
        :param sort_by: SortBy enum attribute
        :type sort_by: SortBy
        :return: The closest local index that the given item should be inserted.
        :rtype: int
        """
        index = 0
        sort_key, reverse = self._get_item_sort_key(sort_by)

        for index, item in enumerate(self._items):
            if not reverse and summary[sort_key] <= item[sort_key]:
                return index
            elif reverse and summary[sort_key] >= item[sort_key]:
                return index

        # it is an empty _items list or going to be appended as last item
        return index if index == 0 else index + 1

    def _insert_sorted(self, item: os.DirEntry, sort_by: SortBy) -> None:
        """Internal method to insert every scanned item into the local `_items`
        list on-the-fly by the given `sort_by` parameter.

        :param item: DirEntry object from `_iter_items()` async iteration
                within the async parallel scanning.
        :type item: posix.DirEntry
        :param sort_by: SortBy enum attribute
        :type sort_by: SortBy
        :rtype: None
        """
        attrs = self._get_attributes(item)

        # It is an empty folder, grab folder timestamps
        if attrs['atime'] == 0 and attrs['mtime'] == 0 and attrs['ctime'] == 0:
            stat = item.stat(follow_symlinks=False)
            attrs['atime'] = int(stat.st_atime)
            attrs['mtime'] = int(stat.st_mtime)
            attrs['ctime'] = int(stat.st_ctime)

        summary = {'name': os.path.relpath(item.path, self._root),
                   'size': attrs['size'],
                   'depth': attrs['depth'],
                   'num_of_files': attrs['num_of_files'],
                   'atime': attrs['atime'],
                   'mtime': attrs['mtime'],
                   'ctime': attrs['ctime']}

        index = self._find_index(summary, sort_by)
        self._total_size += summary['size']
        self._items_len += 1
        self._items.insert(index, summary)

    def resort(self, sort_by: SortBy) -> None:
        """Re orders the internal `_items` list based on given `sort_by`
        parameter. This method is also called at the end of async scanning
        process to fix the async ordering glitches by :meth:`._insert_sorted`.

        You can sort a :class:`Folder` object as many times as you like, it
        will not scan the directory again, instead it will re-order the already
        scanned internal `_items` list. However;

        .. note::

            This method does NOT :meth:`_await` unlike the other public methods
            (yet). The reason behind this design logic is that it brings
            complexity into blocking approach because it is also called within
            async loop, therefore the internal list will be actually _reverted_
            to default sorting anyway at the end of async scanning process.

            It is highly suggested that you should use this method after calling
            at least once, _any_ of the other public methods, for performance
            reasons.

        :param sort_by: SortBy enum attribute
        :type sort_by: SortBy
        :rtype: None
        """
        sort_key, reverse = self._get_item_sort_key(sort_by)
        self._items = deque(sorted(self._items,
                                   key=lambda i: i[sort_key], reverse=reverse))

    async def _scan(self, sort_by: SortBy) -> None:
        """Internal async process that has been initialised at the time of
        object instantiation. It triggers bunch of other blocking / non-blocking
        methods and calculates the final :attr:`.exec_took`.
        
        Public methods should use :meth:`_await` to wait for this internal 
        scanning to be completed.

        :param sort_by: SortBy enum attribute
        :type sort_by: SortBy
        :rtype: None
        """
        logger.debug('Scanning initialised')

        # those 2 lines are pretty much the BOTTLENECK of entire app.
        async for item in self._iter_items(self._root):
            self._insert_sorted(item, sort_by)

        self.resort(sort_by)
        self.exec_took = round(time.time() - self.exec_took, 3)
        logger.debug(
            'Scanning completed for {len:d} items with {size} of data; took {exec} second(s).'.format(
                len=self._items_len,
                size=utils.bytes2human(self._total_size),
                exec=self.exec_took))
