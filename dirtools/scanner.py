import asyncio
import math
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

    >>> from dirtools import FolderScan, SortBy
    >>>
    >>> scan = FolderScan('/path/to/scan', SortBy.OLDEST)
    >>> for item in scan.items():
    >>>     print(item)
    >>> scan.resort(SortBy.LARGEST)
    >>> # etc..
    """

    #: Oldest created items first.
    OLDEST = 1
    #: Newest created items first.
    NEWEST = 2
    #: Least recent modified, in other word _coldest_ items first.
    COLDEST = 3
    #: Most recent modified, in other word _hottest_ items first.
    HOTTEST = 4
    #: Smallest in size items first whether it's a file or folder.
    SMALLEST = 5
    #: Largest in size items first whether it's a file or folder.
    LARGEST = 6

    #: The items with the least number of files first.
    LEAST_FILES = 7
    #: The items with the most number of files first.
    MOST_FILES = 8

    #: The folder that have the deepest sub folders first.
    LEAST_DEPTH = 9
    #: The folder that have the shallowest sub folders first.
    MOST_DEPTH = 10

    def __str__(self):
        return self.name

    def __int__(self):
        return self.value


class FolderScan(object):
    """The main class behind the magic that takes care of scanning an entire
    folder and its sub folders, recursively in the asynchronous manner.

    It is highly suggested that you instantiate your object from this class
    at the earliest step of your programme, as it will start doing its job
    in background. Once you require to access one of its public method, it
    will then block until the scanning is complete or will deliver the
    result straight away if it's already done. For example:

    .. code-block::python

        from dirtools.scanner import FolderScan, SortBy
        scan = FolderScan('/path/to/scan', SortBy.OLDEST)

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
        the `size`, `created_at` and `modified_at` attributes of each item. 
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
        
        >>> folder = FolderScan('/path/to/Python-3.6.0-source')
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
        humanised['created_at'] = time.strftime(cls._time_format, time.gmtime(item['created_at']))
        humanised['modified_at'] = time.strftime(cls._time_format, time.gmtime(item['modified_at']))
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

    def _get_attributes(self, item: os.DirEntry) -> Tuple[int, int, int, int, int]:
        """Parses entire item and subdirectories and returns:

        * Total size in bytes
        * Maximum folder depth of item
        * Total number of files this item contains
        * Creation timestamp
        * Latest modification timestamp

        in the same order as tuple.

        :param item: DirEntry object
        :type item: posix.DirEntry
        :return: (size, depth, num_of_files, created_at, modified_at)
        :rtype: (int, int, int, int, int)
        """
        # it's a file or symlink, size is already on item stat
        if not item.is_dir(follow_symlinks=False):
            stat = item.stat(follow_symlinks=False)
            return (stat.st_size, self._get_depth(item.path) - self._level, 1,
                    utils.parse_created_at(stat), int(stat.st_mtime))

        # It is a folder, recursive size check
        else:
            total_size = num_of_files = modified_at = depth = 0
            created_at = math.inf

            with os.scandir(item.path) as directory:
                for i in directory:
                    _size, _depth, _files, _created, _modified = self._get_attributes(i)
                    total_size += _size
                    num_of_files += _files
                    created_at = min(created_at, _created)
                    modified_at = max(modified_at, _modified)
                    depth = max(depth, _depth)

            # Folder size and timestamps are calculated
            if created_at is not math.inf:
                return total_size, depth, num_of_files, created_at, modified_at

            # Completely empty folder, use its own stat
            stat = item.stat(follow_symlinks=False)
            return (total_size, depth, num_of_files,
                    utils.parse_created_at(stat), int(stat.st_mtime))

    @staticmethod
    def _get_item_sort_key(sort_by: SortBy) -> Tuple[str, bool]:
        """Internal static method to find the item key and ascending/descending
        flag based on the given `sort_by` parameter.

        It is a `TypeError` to give anything other than :class:`SortBy` defined
        attributes.

        :param sort_by: SortBy enum attribute
        :type sort_by: SortBy
        :return: (item key to sort, ascending/descending)
        :rtype: (str, bool)
        :exception: Throws `TypeError` if not a :class:`SortBy` enum element.
        """
        if sort_by is SortBy.OLDEST:
            return 'created_at', False
        elif sort_by is SortBy.NEWEST:
            return 'created_at', True
        elif sort_by is SortBy.COLDEST:
            return 'modified_at', False
        elif sort_by is SortBy.HOTTEST:
            return 'modified_at', True
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
        attributes = self._get_attributes(item)
        summary = {'name': os.path.relpath(item.path, self._root),
                   'size': attributes[0],
                   'depth': attributes[1],
                   'num_of_files': attributes[2],
                   'created_at': attributes[3],
                   'modified_at': attributes[4]}

        index = self._find_index(summary, sort_by)
        # logger.debug('Inserting #{0:d}: {1}'.format(index, summary['name']))
        self._total_size += summary['size']
        self._items_len += 1
        self._items.insert(index, summary)

    def resort(self, sort_by: SortBy) -> None:
        """Re orders the internal `_items` list based on given `sort_by`
        parameter. This method is also called at the end of async scanning
        process to fix the async ordering glitches by :meth:`._insert_sorted`.

        You can sort a :class:`FolderScan` object as many times as you like, it
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
