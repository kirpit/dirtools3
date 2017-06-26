import math
import os

#: Storage size symbols
SYM_NAMES = ('Byte', 'Kb', 'Mb', 'Gb', 'Tb', 'Pb', 'Xb', 'Zb', 'Yb')


def human2bytes(value: str) -> int:
    """ Attempts to guess the string format based on default symbols set and
    return the corresponding bytes as an integer. When unable to recognize
    the format ValueError is raised.

    Function itself is case-insensitive means 'gb' = 'Gb' = 'GB' for gigabyte. It does
    not support bytes (as in 300b) and any numeric value will be considered as
    megabyte. Supported file sizes are:

    * Kb: Kilobyte
    * Mb: Megabyte
    * Gb: Gigabyte
    * Tb: Terabyte
    * Pb: Petabyte
    * Xb: Exabyte
    * Zb: Zettabyte
    * Yb: Yottabyte

      >>>  human2bytes('400') == human2bytes('400 byte') == 400
      True
      >>> human2bytes('2 Kb')
      2048
      >>> human2bytes('2.4 kb')
      2457
      >>> human2bytes('1.1 MB')
      1153433
      >>> human2bytes('1 Gb')
      1073741824
      >>> human2bytes('1 Tb')
      1099511627776

      >>> human2bytes('12 x')
      Traceback (most recent call last):
          ...
      ValueError: Cannot convert to float: '12 x'

    :param value: Human readable value to represent a size
    :type value: str
    :return: Integer value representation in bytes
    :rtype: int
    :raises TypeError: If other than string given
    :raises ValueError: If cannot parse the human-readable string
    """

    def _get_float(val: str) -> float:
        try:
            return float(val)
        except ValueError:
            raise ValueError('Cannot convert to float: {0}'.format(value))

    # Assume a 2-digit symbol was given
    try:
        sym = value[-2:].capitalize()
    except (TypeError, AttributeError):
        raise TypeError('Expected string, given: {0}.'.format(type(value)))

    if sym in SYM_NAMES:
        # size symbol is correct
        index = SYM_NAMES.index(sym)
        num = _get_float(value[:-2])
        return int(num * (1 << index * 10))

    # "Byte" special condition
    elif value[-4:].lower() == 'byte':
        return int(_get_float(value[:-4]))

    # incorrect or no symbol given, will try to parse float so will raise value error
    else:
        return int(_get_float(value))


def bytes2human(value: int or float, precision: int=2) -> str:
    """Converts integer byte values to human readable name. For example:

      >>> bytes2human(0.9 * 1024)
      '922 Byte'
      >>> bytes2human(0.99 * 1024)
      '1014 Byte'
      >>> bytes2human(0.999 * 1024)
      '1023 Byte'
      >>> bytes2human(1024)
      '1 Kb'
      >>> bytes2human(1024 + 512)
      '1.5 Kb'
      >>> bytes2human(85.70 * 1024 * 1024)
      '85.7 Mb'
      >>> bytes2human(28.926 * 1024 * 1024 * 1024)
      '28.93 Gb'

    This function does NOT check the argument type.
      >>> bytes2human('foo')
      Traceback (most recent call last):
          ...
      TypeError: type str doesn't define __round__ method

    :param value: Byte(s) value in integer.
    :type value: int or float
    :param precision: Floating precision of human-readable format (default 2).
    :type precision: int
    :return: Human representation of bytes
    :rtype: str
    :raises TypeError: If other than integer or float given
    :raises ValueError: If negative number is given.
    """
    try:
        byte_val = round(value)
    except TypeError as exc:
        raise exc
    else:
        if value < 0:
            raise ValueError('Given value cannot be negative: {0.real}'.format(value))

    # value is less than a kilobyte, so it's simply byte
    if byte_val < 1024:
        return '{0:d} Byte'.format(byte_val)

    # do reverse loop on size indexes
    for i in range(len(SYM_NAMES), 0, -1):
        index = i * 10
        size = byte_val >> index
        # not that big for this size index
        if size == 0:
            continue
        # maximum usable size found. add the decimal value as well.
        digit_in_bytes = size << index
        remaining = float(byte_val - digit_in_bytes) / (1 << index)
        size = round(size + remaining, precision)

        if size.is_integer():
            return '{0:d} {1}'.format(int(size), SYM_NAMES[i])
        else:
            return '{0.real} {1}'.format(size, SYM_NAMES[i])


def parse_created_at(stat):
    """Attempts to guess creation time from os.stat() based on whichever date
    is the oldest.

    :param stat: DirEntry.stat() or os.stat_result()
    :type stat: os.stat_result
    :return: Guessed creation timestamp
    :rtype: int
    """
    # stat.
    return int(min(stat.st_atime, stat.st_mtime, stat.st_ctime,
                   getattr(stat, 'st_birthtime', math.inf)))
