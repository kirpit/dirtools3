from unittest.mock import Mock

import pytest

from dirtools import SortBy, Folder
from dirtools.tests.factory import DummyFolderFactory

TEST_PARAMS = (
    # Empty test folder:
    {'total_items': 0, 'level': 0, 'total_size': '0 Byte', 'sort_by': SortBy.CTIME_ASC},
    # And by levels up to 4
    {'total_items': 5, 'level': 0, 'total_size': '10 Kb', 'sort_by': SortBy.CTIME_DESC},
    {'total_items': 10, 'level': 1, 'total_size': '20 Kb', 'sort_by': SortBy.ATIME_ASC},
    {'total_items': 20, 'level': 2, 'total_size': '50 Kb', 'sort_by': SortBy.ATIME_DESC},
    {'total_items': 30, 'level': 3, 'total_size': '100 Kb', 'sort_by': SortBy.SMALLEST},
    {'total_items': 50, 'level': 4, 'total_size': '200 Kb', 'sort_by': SortBy.LARGEST},
)


@pytest.fixture(scope='session', params=TEST_PARAMS)
def tmp_folder(request):
    """Create a dummy folder based on given test parameters."""
    # TODO: Find a way to disable cleanup on assert errors
    # Check DummyFolderFactory.__exit__ for details
    with DummyFolderFactory(request.param['total_items'],
                            request.param['total_size'],
                            level=request.param['level']) as factory:
        yield request.param, factory


@pytest.fixture(scope='function')
def clone_factory(monkeypatch):
    scan_methods = [func.__name__ for attr, func in Folder.__dict__.items() if callable(func)]

    def _factory(path: str, sort_by: SortBy = SortBy.ATIME_DESC, level: int = 0, **kwargs):
        # How to clone a python class?
        # http://stackoverflow.com/a/13379957/797334
        FolderClone = type('FolderClone',
                           Folder.__bases__,
                           dict(Folder.__dict__))
        # Then patch the given method mocks
        for method_name, mock in kwargs.items():
            if method_name not in scan_methods:
                raise RuntimeError('Incorrect method name: {0}'.format(method_name))
            elif mock.side_effect is None:
                raise RuntimeError('Mock must have side_effect defined: {0}'.format(method_name))
            monkeypatch.setattr(FolderClone, method_name, mock)

        scan = FolderClone(path, sort_by, level)
        for method_name in scan_methods:
            original_method = getattr(scan, method_name)
            monkeypatch.setattr(scan, method_name, Mock(side_effect=original_method))
        return scan

    return _factory
