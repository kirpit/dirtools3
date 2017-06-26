from unittest.mock import Mock

import pytest

from dirtools import utils


#: Valid human strings that should convert to according bytes value
#: human, byte_val
VALID_HUMAN2BYTES = (
    # Bytes
    ('123', 123),
    ('123byte', 123),
    ('123.5', 123),
    ('123.6 byte', 123),
    # Kilobytes
    ('2 kb', 2048),
    ('2.0Kb', 2048),
    ('2.0 KB', 2048),
    ('2.4 kb', 2457),
    # Megabytes
    ('3Mb', 3145728),
    ('3 mb', 3145728),
    ('3.6Mb', 3774873),
    ('3.6 mB', 3774873),
    # Gigabytes
    ('4GB', 4294967296),
    ('4 gb', 4294967296),
    ('4.1Gb', 4402341478),
    ('4.1 gB', 4402341478),
    # Yetta bytes
    ('5YB', 6044629098073145873530880),
    ('5 yb', 6044629098073145873530880),
    ('5.4Yb', 6528199425918997972910080),
    ('5.4 yB', 6528199425918997972910080),
)


#: Valid human strings that should convert to according bytes value
#: byte_val, human
VALID_BYTES2HUMAN = (
    # Bytes
    (123, '123 Byte'),
    (1023, '1023 Byte'),

    # Kilobytes
    (2048, '2 Kb'),
    (2456, '2.3984375 Kb'),
    (38400, '37.5 Kb'),
    (1023979, '999.9794921875 Kb'),
    (1048565, '1023.9892578125 Kb'),

    # Megabytes
    (3145728, '3 Mb'),
    (3932160, '3.75 Mb'),
    (1048565514, '999.98999977112 Mb'),
    (1073741710, '1023.99989128113 Mb'),

    # Yetta bytes
    (3022314549036572936765440, '2.5 Yb'),
    (6044629098073145873530880, '5 Yb'),
    (12077168937950145713012736, '9.99 Yb'),
)


def test_human2bytes_raises_expected_errors():
    # Check TypeError(s)
    for invalid in (None, 123, 123.0, [1, 2, 3]):
        with pytest.raises(TypeError):
            utils.human2bytes(invalid)

    # Check ValueErrors(s)
    for invalid in ('123 bytes', '123 foo', '123 m'):
        with pytest.raises(ValueError):
            utils.human2bytes(invalid)


def test_human2bytes_calculates_correct_values_to_bytes():
    for human, byte_val in VALID_HUMAN2BYTES:
        assert utils.human2bytes(human) == byte_val


def test_bytes2human_raises_expected_errors():
    # Check TypeError(s)
    for invalid in (None, '123', [1, 2, 3], 5-3j):
        with pytest.raises(TypeError):
            utils.bytes2human(invalid)

    # Check ValueErrors(s)
    for invalid in (-9.99, -7.5, -1, -0.4):
        with pytest.raises(ValueError):
            utils.bytes2human(invalid)


def test_bytes2human_calculates_correct_bytes_to_human():
    for byte_val, human in VALID_BYTES2HUMAN:
        # Also assert well-formatted human value to bytes
        assert byte_val == utils.human2bytes(human)
        assert utils.bytes2human(byte_val, precision=11) == human


def test_parse_created_at_func_returns_prefered_stat_attr():
    atime_val = 1.0
    mtime_val = 2.0
    ctime_val = 3.0
    btime_val = 4.0

    def _raise_attr_error(raise_error=True):
        if raise_error is True:
            class AttrErrorRaiser(object):
                def __lt__(self, other):
                    raise AttributeError()
            return AttrErrorRaiser()
        else:
            return btime_val

    # Create stat mock without st_birthtime on mac
    stat = Mock(st_atime=atime_val, st_mtime=mtime_val,
                st_ctime=ctime_val, st_birthtime=_raise_attr_error())
    with pytest.raises(AttributeError):
        utils.parse_created_at(stat)

    stat.st_birthtime = _raise_attr_error(raise_error=False)
    result = utils.parse_created_at(stat)
    assert type(result) is int
    assert result == atime_val

