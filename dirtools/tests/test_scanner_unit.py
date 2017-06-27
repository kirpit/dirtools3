import asyncio
import os
import time
from unittest.mock import Mock, call

import builtins
import pytest
import types

from dirtools import scanner
from dirtools.loggers import logger
from dirtools.scanner import FolderScan, SortBy
from dirtools.tests.factory import DummyFolderFactory
from dirtools.utils import human2bytes, bytes2human


class TestFolderScanner(object):
    """Test group to make sure FolderScan class has been done and functioning
    properly.
    """

    @classmethod
    def setup_class(cls):
        """Setup before all the tests in this class."""
        pass

    @classmethod
    def teardown_class(cls):
        """Teardown after all the tests have been run."""
        pass

    def test_scan_makes_proper_internal_calls_and_logs_to_async_logger(
            self, monkeypatch, tmp_folder, clone_factory):
        """Check the entire async scanning process logic.
        Testing for: async _scan(self, sort_by) method.

        :param monkeypatch: pytest monkey patch fixture
        :type monkeypatch: _pytest.monkeypatch.MonkeyPatch
        :param tmp_folder: Test params and dummy test folder factory fixture pair.
        :type tmp_folder: (dict, dirtools.tests.factory.DummyFolderFactory)
        :param clone_factory: Factory to create `FolderScan` clone instance.
        :type clone_factory: dirtools.tests.conftest.clone_factory._factory
        """

        async def scanner_coro(_sort_by):
            await scanner_coro_ori(scan, _sort_by)

            # Assert logger and internal calls
            assert logger_debug.call_count == 2
            assert call(scan._root) in scan._iter_items.call_args_list

            # Calculate folder count based on our factory recursive sub creator
            assert scan._iter_items.call_count >= 1
            assert scan._iter_items.call_count > sum(range(scan._level + 1))

            # ._insert_sorted()
            assert scan._insert_sorted.call_count == len(scan._items)
            scan.resort.assert_called_once_with(_sort_by)
            assert isinstance(exec_started, float)
            assert isinstance(scan.exec_took, float)
            exec_late = round(time.time() - exec_started, 3)
            assert exec_late >= scan.exec_took > 0

        params, factory = tmp_folder
        # Mock of ._scan() method
        scanner_mock = Mock(side_effect=scanner_coro)
        scanner_coro_ori = FolderScan._scan

        # Create a scanner class mock from the factory
        scan = clone_factory(factory.path, params['sort_by'], params['level'],
                             _scan=scanner_mock)
        exec_started = scan.exec_took

        # Mock logger debugging
        logger_debug = Mock()
        monkeypatch.setattr(logger, 'debug', logger_debug)

        # Internal calls will be asserted inside the mocked coro,
        # after the original scanning is done.
        scanner_mock.assert_called_once_with(params['sort_by'])
        assert len(list(scan.items())) == params['total_items']

    def test_public_methods_should_block_before_processing(self, monkeypatch, tmp_folder):
        """Make sure public methods and properties blocks until scanning
        finishes.

        :param monkeypatch: pytest monkey patch fixture
        :type monkeypatch: _pytest.monkeypatch.MonkeyPatch
        :param tmp_folder: Test params and dummy test folder factory fixture pair.
        :type tmp_folder: (dict, dirtools.tests.factory.DummyFolderFactory)
        """
        params, factory = tmp_folder
        # Mock the _await internal function first
        scan = FolderScan(factory.path, params['sort_by'], params['level'])
        _ = scan.items()

        blocker = Mock()
        monkeypatch.setattr(scan, '_await', blocker)

        # len(scan)
        assert len(scan) == factory.total_items
        blocker.assert_called_once()
        blocker.reset_mock()

        # .total_size
        assert scan.total_size == factory.total_size
        blocker.assert_called_once()
        blocker.reset_mock()

        # .items
        _ = scan.items()
        blocker.assert_called_once()
        blocker.reset_mock()

        # .cleanup_items() calls human2bytes once
        _human2bytes = Mock(side_effect=human2bytes)
        monkeypatch.setattr('dirtools.utils.human2bytes', _human2bytes)
        factory_size_human = bytes2human(factory.total_size, precision=11)
        with pytest.raises(StopIteration):
            next(scan.cleanup_items(factory_size_human))
        _human2bytes.assert_called_once_with(factory_size_human)
        blocker.assert_called_once()
        blocker.reset_mock()

        # So give -1 to make it block actually, run only for >0 sizes
        if factory.total_size > 0:
            sh_rmtree = Mock()
            os_remove = Mock()
            monkeypatch.setattr('shutil.rmtree', sh_rmtree)
            monkeypatch.setattr(os, 'remove', os_remove)
            # Attempt to remove single item
            next(scan.cleanup_items(bytes2human(factory.total_size - 1, precision=11)))
            blocker.assert_called_once()
            blocker.reset_mock()
            assert sh_rmtree.called or os_remove.called

        # .resort() called at the end of async loop, so it shouldn't _await
        scan.resort(params['sort_by'])
        blocker.assert_not_called()
        blocker.reset_mock()

    def test_total_size_calculated_correctly(self, tmp_folder):
        """Check if directory scanning calculates the item sizes correctly.
        Testing for: @property def total_size(self).

        :param tmp_folder: Test params and dummy test folder factory fixture pair.
        :type tmp_folder: (dict, dirtools.tests.factory.DummyFolderFactory)
        """
        params, factory = tmp_folder
        scan = FolderScan(factory.path, params['sort_by'], params['level'])
        items_len = len(list(scan.items()))

        # For an empty folder
        if factory.total_items == 0:
            assert factory._level == 0
            assert factory.total_size == 0
            assert scan.total_size == 0
            assert items_len == 0

        # Compare with the testing factory testing desired_size param
        assert scan.total_size == sum([i['size'] for i in scan.items(humanise=False)])
        assert scan.total_size == factory.total_size
        assert items_len == factory.total_items

        # Because the factory class does not create at exact size
        assert scan.total_size == factory.total_size
        assert scan.total_size >= 0.9 * human2bytes(params['total_size'])
        assert scan.total_size <= 1.1 * human2bytes(params['total_size'])

    def test_each_item_has_been_scanned_correctly(self, monkeypatch, tmp_folder):
        """Compare every scanned item to the testing factory class.

        :param monkeypatch: pytest monkey patch fixture
        :type monkeypatch: _pytest.monkeypatch.MonkeyPatch
        :param tmp_folder: Test params and dummy test folder factory fixture pair.
        :type tmp_folder: (dict, dirtools.tests.factory.DummyFolderFactory)
        """
        params, factory = tmp_folder
        scan = FolderScan(factory.path, params['sort_by'], params['level'])
        _humanise_item = Mock(side_effect=scan._humanise_item)
        monkeypatch.setattr(scan, '_humanise_item', _humanise_item)

        factory_items = list(factory.items)
        scanned_human = list(scan.items(humanise=True))
        scanned_nonhuman = list(scan.items(humanise=False))
        _humanise_item.assert_has_calls(call(s, precision=2) for s in scanned_nonhuman)
        _humanise_item.reset_mock()

        assert len(factory_items) == len(scanned_nonhuman) == len(scan) == scan._items_len

        for item in factory_items:
            raw = next(i for i in scanned_nonhuman if i['name'] == item['name'])
            human = next(i for i in scanned_human if i['name'] == item['name'])

            assert tuple(raw.keys()) == tuple(human.keys()) == tuple(item.keys())
            assert raw['size'] == item['size']
            assert human['size'] == bytes2human(item['size'])
            assert raw['depth'] == item['depth']
            assert raw['num_of_files'] == item['num_of_files']

            # There is sometimes a second difference because
            # our factory was just created
            assert raw['created_at'] == item['created_at']
            assert raw['modified_at'] == item['modified_at']

    def test_internal_block_waits_for_loop_completion(self, monkeypatch, tmp_folder):
        """Make sure internal _await() waits until loop complete.
        Testing for: def _await(self):

        :param monkeypatch: pytest monkey patch fixture
        :type monkeypatch: _pytest.monkeypatch.MonkeyPatch
        :param tmp_folder: Test params and dummy test folder factory fixture pair.
        :type tmp_folder: (dict, dirtools.tests.factory.DummyFolderFactory)
        """
        params, factory = tmp_folder
        scan = FolderScan(factory.path, params['sort_by'], params['level'])

        # Mock the desired functions that shall be called
        is_done = Mock(return_value=False)
        monkeypatch.setattr(scan._scanning, 'done', is_done)

        until_complete = Mock()
        get_event_loop = Mock(
            return_value=Mock(run_until_complete=until_complete))
        monkeypatch.setattr('asyncio.get_event_loop', get_event_loop)

        # And so if all was called
        scan._await()
        is_done.assert_called_once()
        get_event_loop.assert_called_once()
        until_complete.assert_called_once_with(scan._scanning)

    def test_internal_async_item_iteration_yields_all_items(self, tmp_folder):
        """Make sure item paths from async _iter_items() are matching the
        scanned items. Testing for: async def _iter_items(self, path).

        :param tmp_folder: Test params and dummy test folder factory fixture pair.
        :type tmp_folder: (dict, dirtools.tests.factory.DummyFolderFactory)
        """

        async def _iter_item_paths(_scan):
            return [i.path async for i in _scan._iter_items(_scan._root)]

        params, factory = tmp_folder
        scan = FolderScan(factory.path, params['sort_by'], params['level'])

        loop = asyncio.get_event_loop()
        collected_paths = loop.run_until_complete(_iter_item_paths(scan))
        scanned_paths = [os.path.join(scan._root, i['name']) for i in scan.items()]

        for path in scanned_paths:
            assert path in collected_paths

    def test_internal_dir_entry_parsing_returns_attributes_correctly(self, tmp_folder):
        async def _get_dir_entries(_scan):
            return [i async for i in _scan._iter_items(_scan._root)]

        params, factory = tmp_folder
        scan = FolderScan(factory.path, params['sort_by'], params['level'])
        loop = asyncio.get_event_loop()
        entries = loop.run_until_complete(_get_dir_entries(scan))

        for entry in entries:
            attrs = scan._get_attributes(entry)
            item = next(i for i in scan.items(humanise=False) if entry.path.endswith(i['name']))

            assert item['size'] == attrs[0]
            assert item['depth'] == attrs[1]
            assert item['num_of_files'] == attrs[2]
            assert item['created_at'] == attrs[3]
            assert item['modified_at'] == attrs[4]

    def test_internal_get_item_sort_key_functions_correctly_and_called_as_many_items(self,
                                                                                     monkeypatch,
                                                                                     tmp_folder):
        """Check the static item sorting key function returns correct keys and
        pairs, also check if it was called as many times needed for a scanning.
        Testing for: @staticmethod def _get_item_sort_key(sort_by).

        :param monkeypatch: pytest monkey patch fixture
        :type monkeypatch: _pytest.monkeypatch.MonkeyPatch
        :param tmp_folder: Test params and dummy test folder factory fixture pair.
        :type tmp_folder: (dict, dirtools.tests.factory.DummyFolderFactory)
        """
        with pytest.raises(TypeError):
            FolderScan._get_item_sort_key('foo')

        params, factory = tmp_folder
        try:
            item = next(factory.items)
        except StopIteration:
            pass

        for sort_by in SortBy:
            pair = FolderScan._get_item_sort_key(sort_by=sort_by)
            assert isinstance(pair, tuple) and len(pair) == 2 \
                   and isinstance(pair[0], str) and isinstance(pair[1], bool)

            if params['total_items'] != 0:
                assert pair[0] in item.keys()

        scan = FolderScan(factory.path, params['sort_by'], params['level'])
        get_item_sort_key = Mock(
            return_value=FolderScan._get_item_sort_key(params['sort_by']))
        monkeypatch.setattr(scan, '_get_item_sort_key', get_item_sort_key)

        items = list(scan.items())
        # It is also called once on .resort() at the end of scanning
        call_count = len(items) + 1
        assert call_count == get_item_sort_key.call_count
        assert get_item_sort_key.call_args_list == call_count * [call(params['sort_by'])]

    def test_internal_find_index_called_for_each_item(self, monkeypatch, tmp_folder):
        """Internal finding an index number whilst scanning only called within
        _insert_sorted() method during async scanning. So it should be called
        only per item. Testing for: def _find_index(self, summary, sort_by).

        :param monkeypatch: pytest monkey patch fixture
        :type monkeypatch: _pytest.monkeypatch.MonkeyPatch
        :param tmp_folder: Test params and dummy test folder factory fixture pair.
        :type tmp_folder: (dict, dirtools.tests.factory.DummyFolderFactory)
        """
        params, factory = tmp_folder
        scan = FolderScan(factory.path, params['sort_by'], params['level'])
        find_index = Mock(return_value=0)
        monkeypatch.setattr(scan, '_find_index', find_index)

        for item in scan.items(humanise=False):
            assert call(item, params['sort_by']) in find_index.call_args_list

    def test_internal_insert_sorted_called_for_each_item_and_makes_proper_external_calls(self,
                                                                                         monkeypatch,
                                                                                         tmp_folder):
        """Check internal _insert_sorted() and its every internal/external
        calls, call counts etc. Testing for: def _insert_sorted(self, item, sort_by).

        :param monkeypatch: pytest monkey patch fixture
        :type monkeypatch: _pytest.monkeypatch.MonkeyPatch
        :param tmp_folder: Test params and dummy test folder factory fixture pair.
        :type tmp_folder: (dict, dirtools.tests.factory.DummyFolderFactory)
        """
        params, factory = tmp_folder
        scan = FolderScan(factory.path, params['sort_by'], params['level'])

        # Mock internal and external calls
        insert_sorted = Mock(side_effect=scan._insert_sorted)
        monkeypatch.setattr(scan, '_insert_sorted', insert_sorted)

        get_attrs = Mock(side_effect=scan._get_attributes)
        monkeypatch.setattr(scan, '_get_attributes', get_attrs)

        relpath = Mock(side_effect=os.path.relpath)
        monkeypatch.setattr(os.path, 'relpath', relpath)

        find_index = Mock(return_value=0)
        monkeypatch.setattr(scan, '_find_index', find_index)

        # Let the scan finish
        items_len = len(list(scan.items()))

        # Assert internal call counts compared to items length
        assert insert_sorted.call_count == items_len
        assert find_index.call_count == items_len
        if params['total_items'] == 0:
            assert get_attrs.call_count == items_len == 0
        else:
            assert get_attrs.call_count >= items_len

        for item in scan.items(humanise=False):
            relpath_call = call(os.path.join(scan._root, item['name']), scan._root)
            assert relpath_call in relpath.call_args_list
            assert call(item, params['sort_by']) in find_index.call_args_list

    def test_internal_humanise_item_makes_proper_internal_calls(self, monkeypatch, tmp_folder):
        """Check internal item humaniser makes necessary external calls. 

        :param monkeypatch: pytest monkey patch fixture
        :type monkeypatch: _pytest.monkeypatch.MonkeyPatch
        :param tmp_folder: Test params and dummy test folder factory fixture pair.
        :type tmp_folder: (dict, dirtools.tests.factory.DummyFolderFactory)
        """
        params, factory = tmp_folder

        # Mock the helper functions for humanising
        _bytes2human = Mock(side_effect=bytes2human)
        monkeypatch.setattr('dirtools.utils.bytes2human', _bytes2human)
        strftime = Mock()
        monkeypatch.setattr('time.strftime', strftime)
        gmtime = Mock()
        monkeypatch.setattr('time.gmtime', gmtime)

        # Test if all these humanising functions called
        for item in factory.items:
            # Check for each precision
            for p in range(12):
                result = FolderScan._humanise_item(item, precision=p)

                assert result is not item
                assert tuple(result.keys()) == tuple(item.keys())
                assert result != item
                _bytes2human.assert_called_once_with(item['size'], precision=p)
                assert strftime.call_count == 2
                assert gmtime.call_count == 2

                _bytes2human.reset_mock()
                strftime.reset_mock()
                gmtime.reset_mock()

    def test_public_resort_gets_item_sort_key_and_calls_list_sort_on_items(self, monkeypatch,
                                                                           tmp_folder):
        """Check resorting internal calls and call counts.
        Testing for: def resort(self, sort_by).

        :param monkeypatch: pytest monkey patch fixture
        :type monkeypatch: _pytest.monkeypatch.MonkeyPatch
        :param tmp_folder: Test params and dummy test folder factory fixture pair.
        :type tmp_folder: (dict, dirtools.tests.factory.DummyFolderFactory)
        """
        params, factory = tmp_folder
        scan = FolderScan(factory.path, params['sort_by'], params['level'])

        # .resort()
        resort = Mock(side_effect=scan.resort)
        monkeypatch.setattr(scan, 'resort', resort)

        # Check if it's called at the end of async process.
        _ = scan.items()
        resort.assert_called_once_with(params['sort_by'])
        # Also check if raises TypeError comes from _get_item_sort_key()
        with pytest.raises(TypeError):
            scan.resort('foo')
        resort.reset_mock()

        # ._get_item_sort_key()
        sort_key, reverse = scan._get_item_sort_key(params['sort_by'])
        get_item_sort_key = Mock(return_value=(sort_key, reverse))
        monkeypatch.setattr(scan, '_get_item_sort_key', get_item_sort_key)

        # deque()
        deque_func = Mock(side_effect=scanner.deque)
        monkeypatch.setattr(scanner, 'deque', deque_func)

        # sorted()
        sorted_func = Mock(side_effect=sorted)
        monkeypatch.setattr(builtins, 'sorted', sorted_func)

        # Let's resort
        scan.resort(params['sort_by'])
        get_item_sort_key.assert_called_once_with(params['sort_by'])
        deque_func.assert_called_once()
        sorted_func.assert_called_once()

    def test_cleanup_items_removes_and_yields_items_as_necessary(self, monkeypatch, tmp_folder):
        """Test ``cleanup_items()`` if it successfully removes every item.
        
        :param monkeypatch: pytest monkey patch fixture
        :type monkeypatch: _pytest.monkeypatch.MonkeyPatch
        :param tmp_folder: Test params and dummy test folder factory fixture pair.
        :type tmp_folder: (dict, dirtools.tests.factory.DummyFolderFactory)
        """
        params, _factory = tmp_folder
        if params['total_items'] == 0:
            return

        # Use another factory folder that is not shared with other tests
        with DummyFolderFactory(params['total_items'], params['total_size'],
                                level=params['level']) as factory:
            scan = FolderScan(factory.path, params['sort_by'], level=params['level'])
            _humanise_item = Mock(side_effect=scan._humanise_item)
            monkeypatch.setattr(scan, '_humanise_item', _humanise_item)

            # cleanup must return a generator even the same (or greater) total size given
            result = scan.cleanup_items(bytes2human(scan.total_size, precision=11))
            assert isinstance(result, types.GeneratorType)
            with pytest.raises(StopIteration):
                next(result)
            _humanise_item.assert_not_called()

            # Get a copy of items and remove one by one
            items = tuple(scan.items(humanise=False))
            _humanise_item.assert_not_called()
            for item in items:
                last_total = scan.total_size
                last_items_len = scan._items_len
                mines_one_byte = bytes2human(scan.total_size - 1, precision=11)
                full_path = os.path.abspath(os.path.join(factory.path, item['name']))
                assert os.path.exists(full_path)

                # attempt to remove single item
                deleted = next(scan.cleanup_items(mines_one_byte, humanise=False))

                _humanise_item.assert_not_called()
                assert deleted == item
                assert scan.total_size == (last_total - deleted['size'])
                assert scan._items_len == last_items_len - 1
                assert not os.path.exists(full_path)
