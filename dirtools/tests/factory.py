import asyncio
import math
import os
import shutil
import stat
import string
import subprocess
import tempfile
from datetime import datetime, timedelta
from random import choices, choice, randrange
from sys import platform

from dirtools import utils

FOLDER_CHMOD = stat.S_IRUSR + stat.S_IWUSR + stat.S_IXUSR


class DummyFolderFactory(object):
    total_items = 0
    cleanup = True

    _FILE_PER_FOLDER = 5

    _root = None
    _total_size = None
    _items = None
    _loop = None
    _tasks = None
    _completed = None
    _tasks_birthtime_flags = None
    _desired_size = 0
    _total_files = 0
    _level = 0
    _max_depth = 3

    def __init__(self, total_items, total_size, **kwargs):
        # Pick a random folder name
        # under OS dependent temporary space if no "_root" keyword is given
        self._root = '{root}/dirtools3-{rand}'.format(
            root=kwargs.get('_root', tempfile.gettempdir()),
            rand=self._gen_rand_str(3))

        # Save configs
        self.total_items = int(total_items)
        self._desired_size = utils.human2bytes(total_size)
        self._level = int(kwargs.get('level', self._level))
        assert self._level <= (self.total_items // 4), \
            'Level cannot be more than a 4rd of total_items: {0:d}'.format(self.total_items)
        self._max_depth = int(kwargs.get('max_depth', self._max_depth))
        assert self._max_depth >= 0, 'Max depth cannot be negative.'
        self.cleanup = bool(kwargs.get('cleanup', self.cleanup))

    def __enter__(self):
        def does_level_match(path):
            level_by_sep = os.path.relpath(path, self._root).count(os.sep) + 1
            return path != self._root and level_by_sep >= self._level

        self._total_size = 0
        self._items = list()
        self._tasks = list()
        self._tasks_birthtime_flags = list()
        self._completed = False
        self._loop = asyncio.get_event_loop()

        # Create the dummy test folder
        try:
            os.mkdir(self._root, mode=FOLDER_CHMOD)
        except FileExistsError:
            raise FileExistsError(
                'Dummy testing folder should not exist: {0}'.format(self._root))

        # We may requested to create an empty folder; total_items=0
        if self.total_items == 0:
            return self

        # Create parent base folders (such as category, genre etc)
        bases = tuple()
        if self._level > 0:
            bases = self._create_recursive(
                self._root, self._level + 1, prefix='level_')
            bases[:] = filter(does_level_match, bases)

        # Create items based on self.total_items
        for d in self._random_depths():
            item_size = round(self._desired_size / self.total_items)
            base = choice(bases) if bases else self._root
            self._tasks.append(asyncio.ensure_future(
                self._create_item(base, d, item_size), loop=self._loop))
        return self

    @property
    def path(self):
        self._block()
        return self._root

    @property
    def total_size(self):
        self._block()
        return self._total_size

    @property
    def items(self):
        self._block()
        return iter(self._items)

    def _block(self):
        if self._completed is True:
            return
        elif self.total_items > 0:
            self._loop.run_until_complete(asyncio.wait(self._tasks))

            # __enter__ was never initiated
            if len(self._items) == 0:
                raise RuntimeError(
                    '{0} must be initiated with "with context statement"'.format(
                        self.__class__.__name__))

        self._completed = True

    @staticmethod
    def _gen_rand_str(size, chars=string.ascii_lowercase + string.digits):
        return ''.join(choices(chars, k=size))

    def _random_depths(self):
        # Pick a random depth
        middle = (self._max_depth // 2) + 1
        weight = self._max_depth + 1
        population = range(weight)
        cum_weights = list()
        cumulative = 0.8
        for d in population:
            # first value 0 (zero) will start with default weight
            if d <= middle:
                cumulative += d
                cum_weights.append(cumulative)
            else:
                cumulative += weight - d
                cum_weights.append(cumulative)
        return choices(population, cum_weights=cum_weights, k=self.total_items)

    @staticmethod
    def get_rand_time_pair():
        """
        This function will return a random datetime between two datetime 
        objects.
        """
        delta = datetime.now() - datetime(1970, 1, 1)
        int_delta = (delta.days * 24 * 60 * 60) + delta.seconds

        random_sec1 = randrange(int_delta)
        random_sec2 = randrange(random_sec1, int_delta)
        return (int(timedelta(seconds=random_sec1).total_seconds()),
                int(timedelta(seconds=random_sec2).total_seconds()))

    def _create_dummy_file(self, base, size):
        filepath = '{base}/{name}.dat'.format(base=base, name=self._gen_rand_str(5))

        with open(filepath, 'wb') as f:
            f.truncate(size)

        # Change file creation and modification to random time
        atime, mtime = self.get_rand_time_pair()
        os.utime(filepath, times=(atime, mtime))
        # Change st_birthtime on MacOS
        if platform == 'darwin':
            created_str = datetime.fromtimestamp(atime).strftime('%m/%d/%Y %H:%M:%S')
            # subprocess.run with list arguments and shell=False behaves very strange
            # and sets its st_birthtime to earlier than given timestamp very weirdly
            command = 'SetFile -d "{0}" {1}'.format(created_str, filepath)
            process = subprocess.Popen(command,
                                       shell=True, close_fds=True,
                                       stderr=subprocess.PIPE,
                                       stdout=subprocess.PIPE)
            self._tasks_birthtime_flags.append(process)

        self._total_size += size
        return filepath, atime, mtime

    def _create_sub_folder(self, base, length, prefix=''):
        name = '{prefix}{name}'.format(
            prefix=prefix, name=self._gen_rand_str(length))
        full_path = '{base}/{name}'.format(base=base, name=name)
        os.mkdir(full_path, mode=FOLDER_CHMOD)
        return full_path

    def _create_recursive(self, base, depth, prefix='sub_'):
        """Create sub folders under given base as many as Nth triangle number
        of (depth - 1), which means sum of all the numbers lower than
        _level. For example for depth = 2, there will be only a single sub
        folder. However for depth = 4, there will be 3 + 2 + 1 = 6 sub
        folders.

        :param base: Base path to create sub folders.
        :param depth:
        :return:
        """
        _all_subs = list()
        for d in range(depth, -1, -1):
            if d == depth:
                _all_subs.append(base)
                continue

            for _ in range(d):
                _sub = self._create_sub_folder(base, length=6, prefix=prefix)
                _all_subs.extend(
                    self._create_recursive(_sub, depth - 1, prefix=prefix))

        return _all_subs

    def _wait_birthtime_tasks(self):
        try:
            while True:
                process = self._tasks_birthtime_flags.pop(0)
                assert process.wait() == 0
        except IndexError:
            pass

    async def _create_item(self, base, depth, item_size):
        # - FUNCTION BEGINS -
        # Depth is zero, means create a single file and return
        if depth == 0:
            item_path, created_at, modified_at = self._create_dummy_file(base, item_size)
            self._items.append({
                'name': os.path.relpath(item_path, self._root),
                'size': item_size,
                'depth': depth,
                'num_of_files': 1,
                'created_at': created_at,
                'modified_at': modified_at})
            self._wait_birthtime_tasks()
            return

        # Depth >= 1, we will create some sub folders
        # First create the item folder itself and init values
        item_path = self._create_sub_folder(base, length=4, prefix='item_')
        sub_folders = self._create_recursive(item_path, depth)

        # Create dummy files in sub folders
        num_of_files = self._FILE_PER_FOLDER * len(sub_folders)
        file_size = round(item_size / num_of_files)
        item_size = 0
        created_at = math.inf
        modified_at = 0

        for f in range(num_of_files):
            _, _created_at, _modified_at = self._create_dummy_file(choice(sub_folders), file_size)
            created_at = min(created_at, _created_at)
            modified_at = max(modified_at, _modified_at)
            item_size += file_size

        self._items.append({
            'name': os.path.relpath(item_path, self._root),
            'size': item_size,
            'depth': depth,
            'num_of_files': num_of_files,
            'created_at': created_at,
            'modified_at': modified_at})
        self._wait_birthtime_tasks()

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Because of pytest limitation, exceptions not raised with
        # yield context so exc_type will be always None :(
        # http://pytest.org/dev/yieldfixture.html
        if self.cleanup is True:
            shutil.rmtree(self._root)
