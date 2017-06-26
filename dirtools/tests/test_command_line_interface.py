import os
from unittest.mock import Mock

from click.testing import CliRunner
from tabulate import tabulate
from typing import Iterator

from dirtools import SortBy
from dirtools.tests.factory import DummyFolderFactory
from dirtools.utils import human2bytes, bytes2human


class TestDirtCLI(object):
    """Test group for dirt command line interface to dirtools3.
    """
    dirt = None
    runner = CliRunner()
    _BIN_BASE = os.path.abspath(os.path.join(os.path.basename(__file__), '../bin'))
    _BIN_INIT = os.path.join(_BIN_BASE, '__init__.py')
    _BIN_DIRT = os.path.join(_BIN_BASE, 'dirt')
    _BIN_DIRT_PY = os.path.join(_BIN_BASE, 'dirt.py')

    _DEFAULTS = {
        'sort_by': SortBy.NEWEST,
        'output': 'simple',
        'precision': 2,
        'depth': 0,
        'nohuman': False,
    }

    @classmethod
    def setup_class(cls):
        # Create files to make bin directory a python module
        with open(os.path.join(cls._BIN_INIT), 'a') as f:
            f.close()
        os.symlink(cls._BIN_DIRT, cls._BIN_DIRT_PY)

        from bin import dirt
        cls.dirt = dirt

    @classmethod
    def teardown_class(cls):
        os.unlink(cls._BIN_INIT)
        os.unlink(cls._BIN_DIRT_PY)

    @staticmethod
    def assert_items_in_output(items: Iterator, output: str, is_csv: bool = False):
        lines = output.rstrip().split(os.linesep)
        items = tuple(items)

        # items + header
        if is_csv:
            headers = 1
        # items + (header + head_line + info_line)
        else:
            headers = 2
        info_line = -1

        assert len(lines) == len(items) + headers + 1
        for i, line in enumerate(lines[headers:info_line]):
            item = items[i]
            if is_csv:
                name = '"{0}",'.format(item['name'])
                size = '"{0}",'.format(item['size'])
                depth = '{0},'.format(item['depth'])
                num_of_files = '{0},'.format(item['num_of_files'])
                created_at = '"{0}",'.format(item['created_at'])
                modified_at = '"{0}"'.format(item['modified_at'])
            else:
                name = item['name']
                size = item['size']
                depth = str(item['depth'])
                num_of_files = str(item['num_of_files'])
                created_at = item['created_at']
                modified_at = item['modified_at']

            # name
            assert line.startswith(name)
            line = line.replace(name, '', 1).lstrip()
            # size
            assert line.startswith(size)
            line = line.replace(size, '', 1).lstrip()
            # depth
            assert line.startswith(depth)
            line = line.replace(depth, '', 1).lstrip()
            # num_of_files
            assert line.startswith(num_of_files)
            line = line.replace(num_of_files, '', 1).lstrip()
            # created_at
            assert line.startswith(created_at)
            line = line.replace(created_at, '', 1).lstrip()
            # modified_at
            assert line == modified_at

    def test_check_table_headers_constant_defined_in_same_item_keys_order(self, tmp_folder):
        """Test to check TABLE_HEADERS constant constructed with the same key
        order.
        
        :param tmp_folder: Test params and dummy test folder factory fixture pair.
        :type tmp_folder: (dict, dirtools.tests.factory.DummyFolderFactory)
        :return: 
        """
        params, factory = tmp_folder
        if params['total_items'] == 0:
            return
        item = next(factory.items)
        assert tuple(self.dirt.TABLE_HEADERS.keys()) == tuple(item.keys())

    def test_check_default_option_values_used_for_scanner_and_tabulate(
            self, monkeypatch, tmp_folder, clone_factory):
        """
        :param monkeypatch: pytest monkey patch fixture
        :type monkeypatch: _pytest.monkeypatch.MonkeyPatch
        :param tmp_folder: Test params and dummy test folder factory fixture pair.
        :type tmp_folder: (dict, dirtools.tests.factory.DummyFolderFactory)
        :param clone_factory: Factory to create `FolderScan` clone instance.
        :type clone_factory: dirtools.tests.conftest.clone_factory._factory
        :return: 
        """
        params, factory = tmp_folder

        # Create a scanner mock from the factory
        scan = clone_factory(factory.path)
        FolderScanMock = Mock(return_value=scan)
        monkeypatch.setattr(self.dirt, 'FolderScan', FolderScanMock)

        _tabulate = Mock(side_effect=tabulate)
        monkeypatch.setattr(self.dirt, 'tabulate', _tabulate)

        result = self.runner.invoke(self.dirt.invoke_dirtools3, [factory.path])

        # Check calls done with defaults
        assert result.exception is None
        FolderScanMock.assert_called_once_with(factory.path,
                                               self._DEFAULTS['sort_by'],
                                               level=self._DEFAULTS['depth'])
        assert _tabulate.call_args[1]['tablefmt'] == self._DEFAULTS['output']
        scan.items.assert_called_once_with(humanise=not self._DEFAULTS['nohuman'],
                                           precision=self._DEFAULTS['precision'])

        # Check output
        self.assert_items_in_output(scan.items(), result.output)

    def test_check_each_sort_by_option_passed_to_scanner_correctly(
            self, monkeypatch, tmp_folder, clone_factory):
        """
        :param monkeypatch: pytest monkey patch fixture
        :type monkeypatch: _pytest.monkeypatch.MonkeyPatch
        :param tmp_folder: Test params and dummy test folder factory fixture pair.
        :type tmp_folder: (dict, dirtools.tests.factory.DummyFolderFactory)
        :param clone_factory: Factory to create `FolderScan` clone instance.
        :type clone_factory: dirtools.tests.conftest.clone_factory._factory
        :return:
        """
        params, factory = tmp_folder
        # Create a scanner mock from the factory
        scan = clone_factory(factory.path)
        FolderScanMock = Mock()
        monkeypatch.setattr(self.dirt, 'FolderScan', FolderScanMock)

        scan._await()
        for sort_by in SortBy:
            # Modify return value with new sorting
            scan.resort(sort_by)
            FolderScanMock.return_value = scan

            # Invoke with sorting
            args = [factory.path, '-s', str(sort_by).lower()]
            result = self.runner.invoke(self.dirt.invoke_dirtools3, args)
            assert result.exception is None

            # Check results
            FolderScanMock.assert_called_once_with(
                factory.path, sort_by, level=self._DEFAULTS['depth'])
            FolderScanMock.reset_mock()
            self.assert_items_in_output(scan.items(), result.output)

    def test_check_custom_csv_formatting_works_correctly(
            self, monkeypatch, tmp_folder, clone_factory):
        """
        :param monkeypatch: pytest monkey patch fixture
        :type monkeypatch: _pytest.monkeypatch.MonkeyPatch
        :param tmp_folder: Test params and dummy test folder factory fixture pair.
        :type tmp_folder: (dict, dirtools.tests.factory.DummyFolderFactory)
        :param clone_factory: Factory to create `FolderScan` clone instance.
        :type clone_factory: dirtools.tests.conftest.clone_factory._factory
        :return:
        """
        params, factory = tmp_folder
        # Create a scanner mock from the factory
        scan = clone_factory(factory.path)
        FolderScanMock = Mock(return_value=scan)
        monkeypatch.setattr(self.dirt, 'FolderScan', FolderScanMock)

        _tabulate = Mock(side_effect=tabulate)
        monkeypatch.setattr(self.dirt, 'tabulate', _tabulate)

        result = self.runner.invoke(
            self.dirt.invoke_dirtools3,
            [factory.path, '-o', 'csv', '-s', str(params['sort_by']).lower()])

        assert result.exception is None
        _tabulate.assert_not_called()
        self.assert_items_in_output(scan.items(), result.output, is_csv=True)

    def test_invoke_trimming_down_instead_of_listing(
            self, monkeypatch, tmp_folder, clone_factory):
        """
        :param monkeypatch: pytest monkey patch fixture
        :type monkeypatch: _pytest.monkeypatch.MonkeyPatch
        :param tmp_folder: Test params and dummy test folder factory fixture pair.
        :type tmp_folder: (dict, dirtools.tests.factory.DummyFolderFactory)
        :param clone_factory: Factory to create `FolderScan` clone instance.
        :type clone_factory: dirtools.tests.conftest.clone_factory._factory
        :return:
        """
        params, _factory = tmp_folder
        if params['total_items'] == 0:
            return

        trim_down = int(human2bytes(params['total_size']) / 2)
        trim_down_human = bytes2human(trim_down)
        # Use another factory folder that is not shared with other tests
        with DummyFolderFactory(params['total_items'], params['total_size'],
                                level=params['level']) as factory:
            # Create a scanner mock from the factory
            scan = clone_factory(factory.path, params['sort_by'], level=params['level'])
            FolderScanMock = Mock(return_value=scan)
            monkeypatch.setattr(self.dirt, 'FolderScan', FolderScanMock)

            # Give only numeric trim-down value that shouldn't be accepted
            result = self.runner.invoke(
                self.dirt.invoke_dirtools3,
                [factory.path, '-s', str(params['sort_by']).lower(), '--trim-down', str(trim_down)])
            assert result.exception is None
            assert '--trim-down value cannot be only numeric' in result.output

            result = self.runner.invoke(
                self.dirt.invoke_dirtools3,
                [factory.path, '-s', str(params['sort_by']).lower(),
                 '--trim-down', trim_down_human])
            assert result.exception is None
            scan.items.assert_not_called()
            scan.cleanup_items.assert_called_once_with(trim_down_human,
                                                       humanise=not self._DEFAULTS['nohuman'],
                                                       precision=self._DEFAULTS['precision'])


