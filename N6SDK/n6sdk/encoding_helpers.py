# Copyright (c) 2013-2025 NASK. All rights reserved.
#
# For some parts of the source code of the
# `provide_custom_unicode_error_handlers()` function:
# Copyright (c) 2011-2013 Victor Stinner. All rights reserved.
# (For more information -- see the docstring of that function.)

import re
from typing import Union


class AsciiMixIn(object):

    r"""
    A mix-in class that provides the :meth:`__str__` and
    :meth:`__format__` special methods based on :func:`ascii_str`.

    >>> class SomeBase(object):
    ...     def __str__(self):
    ...         return 'Cośtam-cośtam'
    ...     def __format__(self, fmt):
    ...         return 'Nó i ' + fmt
    ...
    >>> class MyClass(AsciiMixIn, SomeBase):
    ...     pass
    ...
    >>> obj = MyClass()

    >>> str(obj)
    'Co\\u015btam-co\\u015btam'
    >>> format(obj)
    'N\\xf3 i '

    >>> 'Oto {0:ś}'.format(obj)
    'Oto N\\xf3 i \\u015b'
    >>> 'Oto {0!s}'.format(obj)
    'Oto Co\\u015btam-co\\u015btam'

    >>> 'Oto %s' % obj
    'Oto Co\\u015btam-co\\u015btam'
    """

    def __str__(self):
        return ascii_str(super(AsciiMixIn, self).__str__())

    def __format__(self, fmt):
        return ascii_str(super(AsciiMixIn, self).__format__(fmt))


def ascii_str(obj):

    r"""
    Safely convert the given object to an ASCII-only :class:`str`.

    This function does its best to obtain a string representation
    (possibly :class:`str`-like or :class:`bytes`-like converted to str,
    though :func:`repr` can also be used as the last-resort fallback)
    and then escaping any non-ASCII characters -- *not raising* any
    encoding/decoding exceptions.

    The result is an ASCII :class:`str`, with non-ASCII characters escaped
    using Python literal notation (``\x...``, ``\u...``, ``\U...``).

    >>> ascii_str('')
    ''
    >>> ascii_str(b'')
    ''
    >>> ascii_str('Ala ma kota\nA kot?\n2=2 ')   # pure ASCII str => unchanged
    'Ala ma kota\nA kot?\n2=2 '
    >>> ascii_str(b'Ala ma kota\nA kot?\n2=2 ')
    'Ala ma kota\nA kot?\n2=2 '

    >>> ascii_str('Ech, ale b\u0142\u0105d!')       # non-pure-ASCII-str => escaped
    'Ech, ale b\\u0142\\u0105d!'
    >>> ascii_str(b'Ech, ale b\xc5\x82\xc4\x85d!')   # UTF-8 bytes => decoded + escaped
    'Ech, ale b\\u0142\\u0105d!'

    >>> ascii_str(ValueError('Ech, ale b\u0142\u0105d!'))
    'Ech, ale b\\u0142\\u0105d!'
    >>> ascii_str(42)
    '42'

    >>> ascii_str('\udcee\udcdd \tja\u017a\u0144')
    '\\udcee\\udcdd \tja\\u017a\\u0144'
    >>> # Non-UTF-8 bytes: decoded using utf8_surrogatepass_and_surrogateescape + escaped.
    >>> ascii_str(b'\xee\xdd \tja\xc5\xba\xc5\x84')
    '\\udcee\\udcdd \tja\\u017a\\u0144'
    >>> ascii_str(bytearray(b'\xee\xdd \tja\xc5\xba\xc5\x84'))
    '\\udcee\\udcdd \tja\\u017a\\u0144'
    >>> ascii_str(memoryview(b'\xee\xdd \tja\xc5\xba\xc5\x84'))
    '\\udcee\\udcdd \tja\\u017a\\u0144'

    >>> class Nasty1(object):
    ...     def __str__(self): raise UnicodeError
    ...     def __repr__(self): return u'quite nas\u0167y \udcaa'
    ...
    >>> ascii_str(Nasty1())
    'quite nas\\u0167y \\udcaa'

    >>> class Nasty2(object):
    ...     def __str__(self): raise UnicodeError
    ...     def __bytes__(self): return b'more nas\xc5\xa7y! \xaa'
    ...
    >>> ascii_str(Nasty2())
    'more nas\\u0167y! \\udcaa'

    >>> class Nasty3(object):
    ...     def __str__(self): raise ValueError
    ...     def __bytes__(self): raise ValueError
    ...     def __repr__(self): return u'really nas\u0167y!!! \udcaa'
    ...
    >>> ascii_str(Nasty3())
    'really nas\\u0167y!!! \\udcaa'
    """
    if isinstance(obj, str):
        s = obj
    else:
        if isinstance(obj, memoryview):
            obj = bytes(obj)
        if isinstance(obj, (bytes, bytearray)):
            s = obj.decode('utf-8', 'utf8_surrogatepass_and_surrogateescape')
        else:
            try:
                s = str(obj)
            except ValueError:
                if getattr(type(obj), '__bytes__', None) is not None:
                    try:
                        s = bytes(obj).decode('utf-8', 'utf8_surrogatepass_and_surrogateescape')
                    except ValueError:
                        s = repr(obj)
                else:
                    s = repr(obj)
    return s.encode('ascii', 'backslashreplace').decode('ascii')


def verified_as_ascii_str(obj):

    r"""
    Verify that the given object is an ASCII-only :class:`str`, and return it.

    Raises:
        :exc:`~exceptions.TypeError`:
            if the object is not an instance of :class:`str`.
        :exc:`~exceptions.ValueError`:
            if the object is a :class:`str` that contains some non-ASCII
            characters.

    >>> verified_as_ascii_str('')
    ''
    >>> verified_as_ascii_str('foo bar Spam \n \r\n !@#^&*')
    'foo bar Spam \n \r\n !@#^&*'

    >>> verified_as_ascii_str(b'foo bar Spam \n \r\n !@#^&*')  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...

    >>> verified_as_ascii_str(42)                               # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...

    >>> verified_as_ascii_str('zażółć gęślą jaźń')              # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...
    """
    if not isinstance(obj, str):
        raise TypeError('{!a} is not a str'.format(obj))
    if not obj.isascii():
        raise ValueError('{!a} contains some non-ASCII characters'.format(obj)) from None
    return obj


def as_unicode(obj, decode_error_handling='strict'):  # TODO: rename to `as_str`

    r"""
    Convert the given object to a :class:`str` (possibly containing
    various **non**-ASCII characters).

    The function requires that the given object is one of the following:

    * a :class:`str` or any other object that is *not* an instance of
      :class:`bytes`, :class:`bytearray` or :class:`memoryview`, which
      can be converted with :class:`str` or :func:`repr` (the conversions
      will be tried in this order);

    * a :class:`bytes`/:class:`bytearray`/:class:`memoryview` object,
      whose binary data encoding is *UTF-8*; if it is not strict *UTF-8*
      then, by default, :exc:`~exceptions.UnicodeDecodeError` is raised;
      you can modify this behavior by specifying the optional argument
      `decode_error_handling` (which will be passed as the second
      argument to the `:meth:`~bytes.decode` method).

    Unlike :func:`ascii_str`, this function does not do its best to be
    decoding-error-proof, does not apply any escaping by itself, and
    does not try :class:`bytes` conversions on arbitrary objects with
    `__bytes__()`-support (i.e., when it comes to decoding binary data,
    only the three aforementioned binary types are supported).

    >>> as_unicode('')
    ''
    >>> as_unicode(b'')
    ''

    >>> as_unicode('O\u0142\xf3wek') == 'O\u0142\xf3wek'
    True
    >>> as_unicode(ValueError('O\u0142\xf3wek')) == 'O\u0142\xf3wek'
    True

    >>> as_unicode(b'O\xc5\x82\xc3\xb3wek') == 'O\u0142\xf3wek'
    True
    >>> as_unicode(bytearray(b'O\xc5\x82\xc3\xb3wek')) == 'O\u0142\xf3wek'
    True
    >>> as_unicode(memoryview(b'O\xc5\x82\xc3\xb3wek')) == 'O\u0142\xf3wek'
    True

    >>> as_unicode('\udcdd') == '\udcdd'
    True
    >>> as_unicode(b'\xdd', decode_error_handling='surrogateescape') == '\udcdd'
    True
    >>> as_unicode(b'\xdd') == '\udcdd'                        # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    UnicodeDecodeError: ...

    >>> as_unicode(42) == '42'
    True
    >>> as_unicode([{True: bytearray(b'abc')}]) == "[{True: bytearray(b'abc')}]"
    True

    >>> class Hard(object):
    ...     def __str__(self): raise UnicodeError
    ...     def __bytes__(self): return b'never used'
    ...     def __repr__(self): return 'foo'
    ...
    >>> as_unicode(Hard()) == 'foo'
    True
    """

    if isinstance(obj, memoryview):
        obj = bytes(obj)
    if isinstance(obj, (bytes, bytearray)):
        s = obj.decode('utf-8', decode_error_handling)
    else:
        try:
            s = str(obj)
        except ValueError:
            s = repr(obj)
    return s


def as_str_with_minimum_esc(obj):
    r"""
    Similar to `as_unicode`, except that:

    * if a :class:`bytes`/:class:`bytearray`/:class:`memoryview`
      object is given then it is always decoded to `str` using the
      `backslashreplace` error handler, i.e., any non-UTF-8 bytes
      (including those belonging to encoded surrogate codepoints)
      are escaped using the `\x...` notation;

    * if a :class:`str` or any other object is given then the string
      obtained by calling `as_unicode()` is additionally processed in
      such a way that any surrogates it contains are escaped using the
      `\u...` notation;

    * additionaly, in both cases, any backslashes present in the
      original text are escaped -- by doubling them (i.e., each `\`
      becomes `\\`).

    >>> as_str_with_minimum_esc('')
    ''
    >>> as_str_with_minimum_esc(b'')
    ''

    >>> as_str_with_minimum_esc('\\Wy\u0142\xf3w \udcdd!') == '\\\\Wy\u0142\xf3w \\udcdd!'
    True
    >>> as_str_with_minimum_esc(ValueError('Wy\u0142\xf3w \udcdd!')) == 'Wy\u0142\xf3w \\udcdd!'
    True

    >>> as_str_with_minimum_esc(b'\\Wy\xc5\x82\xc3\xb3w \xdd!') == '\\\\Wy\u0142\xf3w \\xdd!'
    True
    >>> as_str_with_minimum_esc(bytearray(b'\xc5\x82\xc3\xb3w \xdd!')) == '\u0142\xf3w \\xdd!'
    True
    >>> as_str_with_minimum_esc(memoryview(b'\\Wy \xdd!')) == '\\\\Wy \\xdd!'
    True

    >>> as_str_with_minimum_esc(42) == '42'
    True
    >>> as_str_with_minimum_esc([{True: bytearray(b'abc')}]) == "[{True: bytearray(b'abc')}]"
    True
    >>> as_str_with_minimum_esc('\\') == r'\\'
    True
    >>> as_str_with_minimum_esc(b'\\') == r'\\'
    True
    >>> as_str_with_minimum_esc(['\\']) == r"['\\\\']"
    True
    >>> as_str_with_minimum_esc([b'\\']) == r"[b'\\\\']"
    True
    >>> str([''' '" ''']) == r'''[' \'" ']'''
    True
    >>> as_str_with_minimum_esc([''' '" ''']) == r'''[' \\'" ']'''
    True
    >>> str([b''' '" ''']) == r'''[b' \'" ']'''
    True
    >>> as_str_with_minimum_esc([b''' '" ''']) == r'''[b' \\'" ']'''
    True

    >>> class Hard(object):
    ...     def __str__(self): raise UnicodeError
    ...     def __bytes__(self): return b'never used'
    ...     def __repr__(self): return 'foo \udcdd bar \\ spam \udbff\udfff'
    ...
    >>> as_str_with_minimum_esc(Hard()) == 'foo \\udcdd bar \\\\ spam \\udbff\\udfff'
    True
    """
    if isinstance(obj, memoryview):
        obj = bytes(obj)
    if isinstance(obj, (bytes, bytearray)):
        bin = obj.replace(b'\\', b'\\\\')
        s = bin.decode('utf-8', 'backslashreplace')
    else:
        s = as_unicode(obj)
        s = s.replace('\\', '\\\\')
        bin = s.encode('utf-8', 'backslashreplace')
        s = bin.decode('utf-8')
    return s


def ascii_py_identifier_str(obj):
    r"""
    Convert the given object to a pure-ASCII :class:'str' being a
    valid Python identifier.

    If the given object is not a :class:`str` it is first converted
    using :func:`ascii_str`.

    The result is a :class:`str` with each series of non-ASCII or
    non-Python-identifier characters (i.e., other than ASCII letters,
    ASCII decimal digits and underscore) --

    * removed if such a series was at the beginning or at the end of the
      input string,

    * otherwise replaced with a single underscore

    -- with the proviso that:

    * if the resultant string is empty or starts with a digit then a
      single underscore is added at the beginning of the string.

    >>> ascii_py_identifier_str('Ala ma kota!')
    'Ala_ma_kota'
    >>> ascii_py_identifier_str(' Ala  ma \t kota ! ')
    'Ala_ma_kota'
    >>> ascii_py_identifier_str(b' Ala  ma \t kota ! ')
    'Ala_ma_kota'
    >>> ascii_py_identifier_str(dict(xyz=' Ala  ma \t kota ! '))
    'xyz_Ala_ma_t_kota'
    >>> ascii_py_identifier_str('__foo_bAR___42__')
    '__foo_bAR___42__'
    >>> ascii_py_identifier_str(' __foo bAR _ 42 _')
    '__foo_bAR___42__'
    >>> ascii_py_identifier_str(b' __foo_bAR\xc5\x9b_  \n.) 42__ \xdd')
    '__foo_bAR_u015b__42___udcdd'
    >>> ascii_py_identifier_str(bytearray(b' __foo_bAR\xc5\x9b_  \n.) 42__ \xdd'))
    '__foo_bAR_u015b__42___udcdd'
    >>> ascii_py_identifier_str(memoryview(b' __foo_bAR\xc5\x9b_  \n.) 42__ \xdd'))
    '__foo_bAR_u015b__42___udcdd'
    >>> ascii_py_identifier_str(' __foo_bAR\u015b_  \n.) 42__ \udcdd')
    '__foo_bAR___42__'
    >>> ascii_py_identifier_str(' __foo_bAR\xc5\x9b_  \n.) 42__ \udcdd')
    '__foo_bAR___42__'
    >>> ascii_py_identifier_str(ValueError('__foo_bAR\xc5\x9b_\n.) 42_ \udcdd'))
    '__foo_bAR_xc5_x9b__42__udcdd'
    >>> ascii_py_identifier_str([' _foo_bAR\u015b_', 42, '_ '])
    '_foo_bAR_u015b__42__'
    >>> ascii_py_identifier_str([b' __foo_bAR\xc5\x9b_', 42, b'_ '])
    'b___foo_bAR_xc5_x9b__42_b__'
    >>> ascii_py_identifier_str('x42')
    'x42'
    >>> ascii_py_identifier_str('!x42')
    'x42'
    >>> ascii_py_identifier_str('_x42')
    '_x42'
    >>> ascii_py_identifier_str('42')
    '_42'
    >>> ascii_py_identifier_str('!42')
    '_42'
    >>> ascii_py_identifier_str('_42')
    '_42'
    >>> ascii_py_identifier_str('a,b,c,d,E,f')
    'a_b_c_d_E_f'
    >>> ascii_py_identifier_str(',a\u0105b,,c,,,d,,,,E,,,,,f,,,,,')
    'a_b_c_d_E_f'
    >>> ascii_py_identifier_str(b',a\xc4\x85b,,c,,,d,,,,E,,,,,f,,,,,')
    'a_u0105b_c_d_E_f'
    >>> ascii_py_identifier_str(',1,2, 3 , 4   ,5 , , 6, , , ')
    '_1_2_3_4_5_6'
    >>> ascii_py_identifier_str('')
    '_'
    >>> ascii_py_identifier_str(b'')
    '_'
    >>> ascii_py_identifier_str('\udcdd')
    '_'
    >>> ascii_py_identifier_str(b'\xdd')
    'udcdd'
    >>> ascii_py_identifier_str('!')
    '_'
    >>> ascii_py_identifier_str(b'!!!')
    '_'
    >>> ascii_py_identifier_str('!@#$%^')
    '_'
    >>> ascii_py_identifier_str('! @ # $ \n % \t ^')
    '_'
    >>> ascii_py_identifier_str('_')
    '_'
    >>> ascii_py_identifier_str('! @ # $ _ \n % \t ^')
    '_'
    >>> ascii_py_identifier_str('___')
    '___'
    >>> ascii_py_identifier_str('! @ # $ _ \n % _ \t ^')
    '___'
    >>> ascii_py_identifier_str('__!@#__$%^__')
    '________'
    """
    if isinstance(obj, str):
        s = obj
    else:
        s = ascii_str(obj)
    s = _ASCII_PY_IDENTIFIER_INVALID_CHAR.sub(' ', s)
    s = '_'.join(s.split())
    if not s or s[0].isdigit():
        s = '_' + s
    return s

_ASCII_PY_IDENTIFIER_INVALID_CHAR = re.compile(r'[^0-9a-zA-Z_]', re.ASCII)


def compute_str_index_from_utf8_bytes_index(
    s: str,
    utf8_bytes_index: int,
) -> Union[int, None]:
    r"""
    Given a Unicode string (`str`) and an index (non-negative `int`)
    that could point to some element of a `bytes` result of encoding
    the Unicode string to UTF-8 (with the `surrogatepass` encoding
    error handler), compute the index (non-negative `int`) of the
    corresponding element (character) of the Unicode string itself.
    But return `None` if the resultant index had to be greater than
    or equal to the length of the given Unicode string.

    Perform the computation reasonably quickly and without unnecessary
    memory overhead (in particular, without actually encoding the given
    Unicode string to `bytes`).

    >>> s1 = 'abc'  # (trivial case: ASCII only)
    >>> len(s1) == len(s1.encode('utf-8')) == 3
    True
    >>> compute_str_index_from_utf8_bytes_index(s1, 0)
    0
    >>> compute_str_index_from_utf8_bytes_index(s1, 1)
    1
    >>> compute_str_index_from_utf8_bytes_index(s1, 2)
    2
    >>> compute_str_index_from_utf8_bytes_index(s1, 3)  # max. index exceeded => None
    >>> compute_str_index_from_utf8_bytes_index(s1, 4)
    >>> compute_str_index_from_utf8_bytes_index(s1, 5)
    >>> compute_str_index_from_utf8_bytes_index(s1, 11)
    >>> compute_str_index_from_utf8_bytes_index(s1, 12)
    >>> compute_str_index_from_utf8_bytes_index(s1, 13)
    >>> compute_str_index_from_utf8_bytes_index(s1, 1_000_000_000_000)

    >>> s2 = 'Aleś \U0001f340 zapodał!'
    >>> len(s2)
    15
    >>> len(s2.encode('utf-8', 'surrogatepass'))
    20
    >>> compute_str_index_from_utf8_bytes_index(s2, 0)
    0
    >>> compute_str_index_from_utf8_bytes_index(s2, 1)
    1
    >>> compute_str_index_from_utf8_bytes_index(s2, 2)
    2
    >>> compute_str_index_from_utf8_bytes_index(s2, 3)  # 1st byte of 2-bytes codepoint
    3
    >>> compute_str_index_from_utf8_bytes_index(s2, 4)  # 2nd byte of 2-bytes codepoint
    3
    >>> compute_str_index_from_utf8_bytes_index(s2, 5)
    4
    >>> compute_str_index_from_utf8_bytes_index(s2, 6)  # 1st byte of 4-bytes codepoint
    5
    >>> compute_str_index_from_utf8_bytes_index(s2, 7)  # 2nd byte of 4-bytes codepoint
    5
    >>> compute_str_index_from_utf8_bytes_index(s2, 8)  # 3rd byte of 4-bytes codepoint
    5
    >>> compute_str_index_from_utf8_bytes_index(s2, 9)  # 4th byte of 4-bytes codepoint
    5
    >>> compute_str_index_from_utf8_bytes_index(s2, 10)
    6
    >>> compute_str_index_from_utf8_bytes_index(s2, 11)
    7
    >>> compute_str_index_from_utf8_bytes_index(s2, 12)
    8
    >>> compute_str_index_from_utf8_bytes_index(s2, 13)
    9
    >>> compute_str_index_from_utf8_bytes_index(s2, 14)
    10
    >>> compute_str_index_from_utf8_bytes_index(s2, 15)
    11
    >>> compute_str_index_from_utf8_bytes_index(s2, 16)
    12
    >>> compute_str_index_from_utf8_bytes_index(s2, 17)  # 1st byte of 2-bytes codepoint
    13
    >>> compute_str_index_from_utf8_bytes_index(s2, 18)  # 2nd byte of 2-bytes codepoint
    13
    >>> compute_str_index_from_utf8_bytes_index(s2, 19)
    14
    >>> compute_str_index_from_utf8_bytes_index(s2, 20)  # max. index exceeded => None
    >>> compute_str_index_from_utf8_bytes_index(s2, 21)
    >>> compute_str_index_from_utf8_bytes_index(s2, 22)
    >>> compute_str_index_from_utf8_bytes_index(s2, 23)
    >>> compute_str_index_from_utf8_bytes_index(s2, 59)
    >>> compute_str_index_from_utf8_bytes_index(s2, 60)
    >>> compute_str_index_from_utf8_bytes_index(s2, 61)
    >>> compute_str_index_from_utf8_bytes_index(s2, 1_000_000_000_000)

    >>> s3 = ' ń\ud83c\udf40\U0001f340'
    >>> len(s3)
    5
    >>> len(s3.encode('utf-8', 'surrogatepass'))
    13
    >>> compute_str_index_from_utf8_bytes_index(s3, 0)
    0
    >>> compute_str_index_from_utf8_bytes_index(s3, 1)
    1
    >>> compute_str_index_from_utf8_bytes_index(s3, 2)
    1
    >>> compute_str_index_from_utf8_bytes_index(s3, 3)
    2
    >>> compute_str_index_from_utf8_bytes_index(s3, 4)
    2
    >>> compute_str_index_from_utf8_bytes_index(s3, 5)
    2
    >>> compute_str_index_from_utf8_bytes_index(s3, 6)
    3
    >>> compute_str_index_from_utf8_bytes_index(s3, 7)
    3
    >>> compute_str_index_from_utf8_bytes_index(s3, 8)
    3
    >>> compute_str_index_from_utf8_bytes_index(s3, 9)
    4
    >>> compute_str_index_from_utf8_bytes_index(s3, 10)
    4
    >>> compute_str_index_from_utf8_bytes_index(s3, 11)
    4
    >>> compute_str_index_from_utf8_bytes_index(s3, 12)
    4
    >>> compute_str_index_from_utf8_bytes_index(s3, 13)  # max. index exceeded => None
    >>> compute_str_index_from_utf8_bytes_index(s3, 14)
    >>> compute_str_index_from_utf8_bytes_index(s3, 15)
    >>> compute_str_index_from_utf8_bytes_index(s3, 16)
    >>> compute_str_index_from_utf8_bytes_index(s3, 17)
    >>> compute_str_index_from_utf8_bytes_index(s3, 18)
    >>> compute_str_index_from_utf8_bytes_index(s3, 19)
    >>> compute_str_index_from_utf8_bytes_index(s3, 20)
    >>> compute_str_index_from_utf8_bytes_index(s3, 21)
    >>> compute_str_index_from_utf8_bytes_index(s3, 1_000_000_000_000)

    >>> s4 = ''.join(reversed(s3))
    >>> len(s4)
    5
    >>> len(s4.encode('utf-8', 'surrogatepass'))
    13
    >>> compute_str_index_from_utf8_bytes_index(s4, 0)
    0
    >>> compute_str_index_from_utf8_bytes_index(s4, 1)
    0
    >>> compute_str_index_from_utf8_bytes_index(s4, 2)
    0
    >>> compute_str_index_from_utf8_bytes_index(s4, 3)
    0
    >>> compute_str_index_from_utf8_bytes_index(s4, 4)
    1
    >>> compute_str_index_from_utf8_bytes_index(s4, 5)
    1
    >>> compute_str_index_from_utf8_bytes_index(s4, 6)
    1
    >>> compute_str_index_from_utf8_bytes_index(s4, 7)
    2
    >>> compute_str_index_from_utf8_bytes_index(s4, 8)
    2
    >>> compute_str_index_from_utf8_bytes_index(s4, 9)
    2
    >>> compute_str_index_from_utf8_bytes_index(s4, 10)
    3
    >>> compute_str_index_from_utf8_bytes_index(s4, 11)
    3
    >>> compute_str_index_from_utf8_bytes_index(s4, 12)
    4
    >>> compute_str_index_from_utf8_bytes_index(s4, 13)  # max. index exceeded => None
    >>> compute_str_index_from_utf8_bytes_index(s4, 14)
    >>> compute_str_index_from_utf8_bytes_index(s4, 15)
    >>> compute_str_index_from_utf8_bytes_index(s4, 16)
    >>> compute_str_index_from_utf8_bytes_index(s4, 17)
    >>> compute_str_index_from_utf8_bytes_index(s4, 18)
    >>> compute_str_index_from_utf8_bytes_index(s4, 19)
    >>> compute_str_index_from_utf8_bytes_index(s4, 20)
    >>> compute_str_index_from_utf8_bytes_index(s4, 21)
    >>> compute_str_index_from_utf8_bytes_index(s4, 1_000_000_000_000)

    >>> s5 = '\U0001f340ń \ud83cń\udf40 ń\U0001f340'
    >>> len(s5)
    9
    >>> len(s5.encode('utf-8', 'surrogatepass'))
    22
    >>> compute_str_index_from_utf8_bytes_index(s5, 0)
    0
    >>> compute_str_index_from_utf8_bytes_index(s5, 1)
    0
    >>> compute_str_index_from_utf8_bytes_index(s5, 2)
    0
    >>> compute_str_index_from_utf8_bytes_index(s5, 3)
    0
    >>> compute_str_index_from_utf8_bytes_index(s5, 4)
    1
    >>> compute_str_index_from_utf8_bytes_index(s5, 5)
    1
    >>> compute_str_index_from_utf8_bytes_index(s5, 6)
    2
    >>> compute_str_index_from_utf8_bytes_index(s5, 7)
    3
    >>> compute_str_index_from_utf8_bytes_index(s5, 8)
    3
    >>> compute_str_index_from_utf8_bytes_index(s5, 9)
    3
    >>> compute_str_index_from_utf8_bytes_index(s5, 10)
    4
    >>> compute_str_index_from_utf8_bytes_index(s5, 11)
    4
    >>> compute_str_index_from_utf8_bytes_index(s5, 12)
    5
    >>> compute_str_index_from_utf8_bytes_index(s5, 13)
    5
    >>> compute_str_index_from_utf8_bytes_index(s5, 14)
    5
    >>> compute_str_index_from_utf8_bytes_index(s5, 15)
    6
    >>> compute_str_index_from_utf8_bytes_index(s5, 16)
    7
    >>> compute_str_index_from_utf8_bytes_index(s5, 17)
    7
    >>> compute_str_index_from_utf8_bytes_index(s5, 18)
    8
    >>> compute_str_index_from_utf8_bytes_index(s5, 19)
    8
    >>> compute_str_index_from_utf8_bytes_index(s5, 20)
    8
    >>> compute_str_index_from_utf8_bytes_index(s5, 21)
    8
    >>> compute_str_index_from_utf8_bytes_index(s5, 22)  # max. index exceeded => None
    >>> compute_str_index_from_utf8_bytes_index(s5, 23)
    >>> compute_str_index_from_utf8_bytes_index(s5, 24)
    >>> compute_str_index_from_utf8_bytes_index(s5, 25)
    >>> compute_str_index_from_utf8_bytes_index(s5, 26)
    >>> compute_str_index_from_utf8_bytes_index(s5, 27)
    >>> compute_str_index_from_utf8_bytes_index(s5, 28)
    >>> compute_str_index_from_utf8_bytes_index(s5, 29)
    >>> compute_str_index_from_utf8_bytes_index(s5, 30)
    >>> compute_str_index_from_utf8_bytes_index(s5, 31)
    >>> compute_str_index_from_utf8_bytes_index(s5, 32)
    >>> compute_str_index_from_utf8_bytes_index(s5, 33)
    >>> compute_str_index_from_utf8_bytes_index(s5, 34)
    >>> compute_str_index_from_utf8_bytes_index(s5, 35)
    >>> compute_str_index_from_utf8_bytes_index(s5, 36)
    >>> compute_str_index_from_utf8_bytes_index(s5, 37)
    >>> compute_str_index_from_utf8_bytes_index(s5, 1_000_000_000_000)

    Edge cases are also handled properly:

    >>> compute_str_index_from_utf8_bytes_index('', 0)  # max. index exceeded => None
    >>> compute_str_index_from_utf8_bytes_index('', 1)
    >>> compute_str_index_from_utf8_bytes_index('', 1_000_000_000_000)

    >>> compute_str_index_from_utf8_bytes_index('x', 0)
    0
    >>> compute_str_index_from_utf8_bytes_index('x', 1)  # max. index exceeded => None
    >>> compute_str_index_from_utf8_bytes_index('x', 2)
    >>> compute_str_index_from_utf8_bytes_index('x', 3)
    >>> compute_str_index_from_utf8_bytes_index('x', 4)
    >>> compute_str_index_from_utf8_bytes_index('x', 5)
    >>> compute_str_index_from_utf8_bytes_index('x', 1_000_000_000_000)

    >>> compute_str_index_from_utf8_bytes_index('ń', 0)
    0
    >>> compute_str_index_from_utf8_bytes_index('ń', 1)
    0
    >>> compute_str_index_from_utf8_bytes_index('ń', 2)  # max. index exceeded => None
    >>> compute_str_index_from_utf8_bytes_index('ń', 3)
    >>> compute_str_index_from_utf8_bytes_index('ń', 4)
    >>> compute_str_index_from_utf8_bytes_index('ń', 5)
    >>> compute_str_index_from_utf8_bytes_index('ń', 1_000_000_000_000)

    >>> compute_str_index_from_utf8_bytes_index('\uabcd', 0)
    0
    >>> compute_str_index_from_utf8_bytes_index('\uabcd', 1)
    0
    >>> compute_str_index_from_utf8_bytes_index('\uabcd', 2)
    0
    >>> compute_str_index_from_utf8_bytes_index('\uabcd', 3)  # max. index exceeded => None
    >>> compute_str_index_from_utf8_bytes_index('\uabcd', 4)
    >>> compute_str_index_from_utf8_bytes_index('\uabcd', 5)
    >>> compute_str_index_from_utf8_bytes_index('\uabcd', 1_000_000_000_000)

    >>> compute_str_index_from_utf8_bytes_index('\U0001f340', 0)
    0
    >>> compute_str_index_from_utf8_bytes_index('\U0001f340', 1)
    0
    >>> compute_str_index_from_utf8_bytes_index('\U0001f340', 2)
    0
    >>> compute_str_index_from_utf8_bytes_index('\U0001f340', 3)
    0
    >>> compute_str_index_from_utf8_bytes_index('\U0001f340', 4)  # max. index exceeded => None
    >>> compute_str_index_from_utf8_bytes_index('\U0001f340', 5)
    >>> compute_str_index_from_utf8_bytes_index('\U0001f340', 1_000_000_000_000)
    """
    str_length = len(s)
    if utf8_bytes_index >= 4 * str_length:
        # (fast path: `utf8_bytes_index` is big enough...)
        return None

    bytes_countdown = utf8_bytes_index
    str_index = 0

    def repl(chunk_match: re.Match) -> str:
        nonlocal bytes_countdown, str_index

        if bytes_countdown <= 0:
            return ''

        for n in (1, 2, 3, 4):
            assert chunk_match.start(n) == str_index

            if not (str_portion := chunk_match.group(n)):
                continue

            str_step = len(str_portion)
            str_index += str_step
            bytes_countdown -= n * str_step
            if bytes_countdown <= 0:
                str_index += bytes_countdown // n
                break

        # (only the collected counts are important,
        # *not* any string substitutions)
        return ''

    _UNICODE_CHUNK_REGEX_FOR_COUNTING_UTF8_BYTES.sub(repl, s)

    if str_index >= str_length:
        assert str_index == str_length
        return None

    assert 0 <= str_index < str_length
    return str_index

_UNICODE_CHUNK_REGEX_FOR_COUNTING_UTF8_BYTES = re.compile(
    # (we limit the length of each processed portion to max. 2000 characters,
    # so that we can handle even a huge string in a memory efficient manner)
    r'''
        # Unicode codepoints:              Num of bytes per codepoint in UTF-8:
        ([\x00-\x7f]{,2000})               # 1
        ([\x80-\u07ff]{,2000})             # 2
        ([\u0800-\uffff]{,2000})           # 3
        ([\U00010000-\U0010ffff]{,2000})   # 4
    ''',
    re.VERBOSE,
)


def replace_surrogate_pairs_with_proper_codepoints(
    s: str,
    replace_unpaired_surrogates_with_fffd: bool = False,
):
    r"""
    Make representation of non-BMP characters consistent, by replacing
    surrogate pairs with the actual corresponding non-BMP codepoints.
    Unpaired (lone) surrogates are left intact, unless the flag
    `replace_unpaired_surrogates_with_fffd` is set -- then each
    unpaired surrogate is replaced with the Unicode replacement
    character ('\ufffd')'.

    >>> s = '\ud83c' + '\udf40'
    >>> print(ascii(s))
    '\ud83c\udf40'
    >>> res = replace_surrogate_pairs_with_proper_codepoints(s)
    >>> print(ascii(res))
    '\U0001f340'
    >>> res2 = replace_surrogate_pairs_with_proper_codepoints(
    ...     s,
    ...     replace_unpaired_surrogates_with_fffd=True)
    >>> print(ascii(res2))
    '\U0001f340'

    >>> s = '\ud800' + '\udc00' + '\ud800' + '\udfff' + '\udbff' + '\udc00' + '\udbff' + '\udfff'
    >>> print(ascii(s))
    '\ud800\udc00\ud800\udfff\udbff\udc00\udbff\udfff'
    >>> res = replace_surrogate_pairs_with_proper_codepoints(s)
    >>> print(ascii(res))
    '\U00010000\U000103ff\U0010fc00\U0010ffff'
    >>> res2 = replace_surrogate_pairs_with_proper_codepoints(
    ...     s,
    ...     replace_unpaired_surrogates_with_fffd=True)
    >>> print(ascii(res2))
    '\U00010000\U000103ff\U0010fc00\U0010ffff'

    Any already-non-BMP codepoints are, obviously, left intact:

    >>> s = '\U0001f340'
    >>> print(ascii(s))
    '\U0001f340'
    >>> res = replace_surrogate_pairs_with_proper_codepoints(s)
    >>> print(ascii(res))
    '\U0001f340'
    >>> res2 = replace_surrogate_pairs_with_proper_codepoints(
    ...     s,
    ...     replace_unpaired_surrogates_with_fffd=True)
    >>> print(ascii(res2))
    '\U0001f340'

    Lone/not-properly-paired surrogates are either left intact or replaced
    with '\ufffd', depending on the `replace_unpaired_surrogates_with_fffd`
    flag:

    >>> s = '\ud83c'
    >>> print(ascii(s))
    '\ud83c'
    >>> res = replace_surrogate_pairs_with_proper_codepoints(s)
    >>> print(ascii(res))
    '\ud83c'
    >>> res2 = replace_surrogate_pairs_with_proper_codepoints(
    ...     s,
    ...     replace_unpaired_surrogates_with_fffd=True)
    >>> print(ascii(res2))
    '\ufffd'

    >>> s = '\udf40' + '\ud83c'  # not a proper surrogate pair (wrong order)
    >>> print(ascii(s))
    '\udf40\ud83c'
    >>> res = replace_surrogate_pairs_with_proper_codepoints(s)
    >>> print(ascii(res))
    '\udf40\ud83c'
    >>> res2 = replace_surrogate_pairs_with_proper_codepoints(
    ...     s,
    ...     replace_unpaired_surrogates_with_fffd=True)
    >>> print(ascii(res2))
    '\ufffd\ufffd'

    >>> s = 'asdfghj' + '\ud83c' + '\udf40' + '\udf40' + '\ud83c' + '\U0001f340' + 'qwertyu'
    >>> print(ascii(s))
    'asdfghj\ud83c\udf40\udf40\ud83c\U0001f340qwertyu'
    >>> res = replace_surrogate_pairs_with_proper_codepoints(s)
    >>> print(ascii(res))
    'asdfghj\U0001f340\udf40\ud83c\U0001f340qwertyu'
    >>> res2 = replace_surrogate_pairs_with_proper_codepoints(
    ...     s,
    ...     replace_unpaired_surrogates_with_fffd=True)
    >>> print(ascii(res2))
    'asdfghj\U0001f340\ufffd\ufffd\U0001f340qwertyu'
    """
    if not isinstance(s, str):
        raise TypeError(f'{s!a} is not a `str`')
    decode_error_handling = 'replace' if replace_unpaired_surrogates_with_fffd else 'surrogatepass'
    res = s.encode('utf-16', 'surrogatepass').decode('utf-16', decode_error_handling)
    assert not _PROPER_SURROGATE_PAIR.search(res)
    return res

_PROPER_SURROGATE_PAIR = re.compile('[\uD800-\uDBFF][\uDC00-\uDFFF]')


def provide_custom_unicode_error_handlers(
        isinstance=isinstance,
        UnicodeDecodeError=UnicodeDecodeError,
        chr=chr,
        len=len,
        str_join=u''.join):

    r"""
    Provide *n6*'s custom encoding/decoding error handlers.

    For now this function provides an error handler for bytes-to-unicode
    decoding: ``utf8_surrogatepass_and_surrogateescape``.

    The *n6*'s ``utf8_surrogatepass_and_surrogateescape`` error handler
    is supposed to mimic the behavior of the custom ``surrogateescape``
    error handler in Python 2 (where `utf-8` included surrogate code
    points).

    ***

    The initial version of the code of this function was copied from
    https://bitbucket.org/haypo/misc/src/d76f4ff5d27c746c883d40160c8b4fb0891e79f2/python/surrogateescape.py?at=default
    -- the original code of a pure-Python ``surrogateescape`` error
    handler by Victor Stinner, released by him under the Python license
    and the BSD 2-clause license.

    Later, many changes to the code were applied by us.

    ***

    This function is idempotent (i.e., it can be called safely multiple
    times -- because if the handler is already registered the function
    does not try to register it again) though it is not thread-safe
    (typically that does not matter as the function is supposed to be
    called somewhere at the beginning of program execution).

    .. note::

       Typically, this function is called automatically on first import
       of the :mod:`n6sdk` module (or any of its submodules).

    ***

    A few examples:

    >>> provide_custom_unicode_error_handlers()
    >>> b = b'o\xc5\x82\xc3\xb3wek \xee\xdd'            # utf-8 text + some non-utf-8 mess
    >>> u = b.decode('utf-8', 'utf8_surrogatepass_and_surrogateescape')
    >>> u == u'o\u0142\xf3wek \udcee\udcdd'
    True
    >>> b2 = u.encode('utf-8', 'surrogatepass')
    >>> b2 == b'o\xc5\x82\xc3\xb3wek \xed\xb3\xae\xed\xb3\x9d'
    True
    >>> u2 = b2.decode('utf-8', 'surrogatepass')
    >>> u3 = b2.decode('utf-8', 'utf8_surrogatepass_and_surrogateescape')
    >>> u == u2 == u3
    True
    >>> u.encode(                                       # doctest: +IGNORE_EXCEPTION_DETAIL
    ...     'utf-8',
    ...     'utf8_surrogatepass_and_surrogateescape')   # does not work for *encoding*
    Traceback (most recent call last):
      ...
    TypeError: don't know how to handle UnicodeEncodeError in error callback

    >>> u = u'\udcdd'
    >>> b1 = b'\xdd'
    >>> b2 = b'\xed\xb3\x9d'
    >>> u == b1.decode('utf-8', 'utf8_surrogatepass_and_surrogateescape')
    True
    >>> u == b2.decode('utf-8', 'utf8_surrogatepass_and_surrogateescape')
    True

    >>> b = b'\xed\xa0\x80\xed\xaf\xbf\xed\xb0\x80\xed\xbf\xbf'
    >>> u = b.decode('utf-8', 'utf8_surrogatepass_and_surrogateescape')
    >>> u == u'\ud800\udbff\udc00\udfff'
    True

    >>> b = (
    ...     b'\xdd\xed\xed\xb2'  # mess
    ...     b'\xed\xb2\xb1'  # encoded surrogate '\udcb1'
    ...     b'\xed\xb2'      # mess
    ...     b'\xed'          # mess
    ...     b'B'             # encoded proper code point (ascii 'B')
    ...     b'\xed\x9f\xbf'  # encoded proper code point '\ud7ff' (smaller than smallest surrogate)
    ...     b'\xed\xa0'      # mess
    ...     b'\x7f'          # encoded proper code point (ascii DEL)
    ...     b'\xed\xa0\x80'  # encoded surrogate '\ud800' (smallest one)
    ...     b'\xed\xbf\xbf'  # encoded surrogate '\udfff' (biggest one)
    ...     b'\xee\xbf\xc0'  # mess
    ...     b'\xee\x80\x80'  # encoded proper code point '\ue000' (bigger than biggest surrogate)
    ...     b'\xe6'          # mess
    ...     b'\xed'          # mess
    ...     b'\xed\xb3'      # mess
    ...     b'\xed\xb3\xa6'  # encoded surrogate '\udce6'
    ...     b'\x80'          # mess
    ...     b'#'             # encoded proper code point (ascii '#')
    ...     b'\xf0'          # mess
    ...     b'\xf0\x90'      # mess
    ...     b'\xf0\x90\x8f'  # mess
    ...     b'\xf0\x90\x8f\xbf'  # encoded proper code point '\U000103ff' (non-BMP one)
    ...     b'\xf0\x90\x8f'  # mess
    ...     b' '             # encoded proper code point (ascii ' ')
    ...     b'\xed\xb3')     # mess (starts like a proper surrogate but is too short)
    >>> u = b.decode('utf-8', 'utf8_surrogatepass_and_surrogateescape')
    >>> u == (
    ...     u'\udcdd\udced\udced\udcb2'  # mess converted to surrogates
    ...     u'\udcb1'        # surrogate '\udcb1'
    ...     u'\udced\udcb2'  # mess converted to surrogates
    ...     u'\udced'        # mess converted to surrogate
    ...     u'B'             # proper code point (ascii 'B')
    ...     u'\ud7ff'        # proper code point '\ud7ff' (smaller than smallest surrogate)
    ...     u'\udced\udca0'  # mess converted to surrogates
    ...     u'\x7f'          # proper code point (ascii DEL)
    ...     u'\ud800'        # surrogate '\ud800' (smallest one)
    ...     u'\udfff'        # surrogate '\udfff' (biggest one) [note: *not* merged with one above]
    ...     u'\udcee\udcbf\udcc0'  # mess converted to surrogates
    ...     u'\ue000'        # proper code point '\ue000' (bigger than biggest surrogate)
    ...     u'\udce6'        # mess converted to surrogate
    ...     u'\udced'        # mess converted to surrogate
    ...     u'\udced\udcb3'  # mess converted to surrogates
    ...     u'\udce6'        # surrogate '\udce6'
    ...     u'\udc80'        # mess converted to surrogate
    ...     u'#'             # proper code point (ascii '#')
    ...     u'\udcf0'        # mess converted to surrogate
    ...     u'\udcf0\udc90'  # mess converted to surrogates
    ...     u'\udcf0\udc90\udc8f'  # mess converted to surrogates
    ...     u'\U000103ff'    # proper code point '\U000103ff' (non-BMP one)
    ...     u'\udcf0\udc90\udc8f'  # mess converted to surrogates
    ...     u' '             # proper code point (ascii ' ')
    ...     u'\udced\udcb3')  # mess converted to surrogates
    True
    """

    ENCODED_SURROGATE_LENGTH = 3
    ENCODED_SURROGATE_MIN = b'\xed\xa0\x80'
    ENCODED_SURROGATE_MAX = b'\xed\xbf\xbf'

    def utf8_surrogatepass_and_surrogateescape(exc):
        if isinstance(exc, UnicodeDecodeError):
            decoded = []
            append_to_decoded = decoded.append
            raw = exc.object
            i = exc.start
            while i < exc.end:
                code = raw[i]
                if code == 0xED:
                    b = raw[i : i+ENCODED_SURROGATE_LENGTH]
                    if (len(b) == ENCODED_SURROGATE_LENGTH
                          and ENCODED_SURROGATE_MIN <= b <= ENCODED_SURROGATE_MAX):
                        try:
                            s = b.decode('utf-8', 'surrogatepass')
                        except UnicodeDecodeError:
                            pass
                        else:
                            append_to_decoded(s)
                            i += ENCODED_SURROGATE_LENGTH
                            continue
                if 0x80 <= code <= 0xFF:
                    append_to_decoded(chr(0xDC00 + code))
                    i += 1
                elif code <= 0x7F:
                    append_to_decoded(chr(code))
                    i += 1
                else:
                    raise exc
            decoded = str_join(decoded)
            return (decoded, i)
        else:
            raise TypeError("don't know how to handle {} in error callback"
                            .format(type(exc).__name__))

    import codecs
    try:
        codecs.lookup_error('utf8_surrogatepass_and_surrogateescape')
    except LookupError:
        codecs.register_error('utf8_surrogatepass_and_surrogateescape',
                              utf8_surrogatepass_and_surrogateescape)


def str_to_bool(s):
    """
    Return True or False, given one of the known strings (see examples below).

    >>> str_to_bool('1')
    True
    >>> str_to_bool('y')
    True
    >>> str_to_bool('yes')
    True
    >>> str_to_bool('Yes')  # note: checks are case-insensitive
    True
    >>> str_to_bool('t')
    True
    >>> str_to_bool('true')
    True
    >>> str_to_bool('on')
    True

    >>> str_to_bool('0')
    False
    >>> str_to_bool('n')
    False
    >>> str_to_bool('nO')
    False
    >>> str_to_bool('f')
    False
    >>> str_to_bool('false')
    False
    >>> str_to_bool('off')
    False

    Other string values cause ValueError:

    >>> str_to_bool('unknown')        # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...
    >>> str_to_bool('')               # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...

    Non-str values cause TypeError:

    >>> str_to_bool(b'yes')  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...
    >>> str_to_bool(True)             # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...
    >>> str_to_bool(None)             # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...
    >>> str_to_bool(1)                # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...
    """
    if not isinstance(s, str):
        raise TypeError('{!a} is not a str'.format(s))
    s_lowercased = s.lower()
    try:
        return str_to_bool.LOWERCASE_TO_BOOL[s_lowercased]
    except KeyError:
        raise ValueError(str_to_bool.PUBLIC_MESSAGE_PATTERN.format(
            ascii_str(s)).rstrip('.')) from None

str_to_bool.LOWERCASE_TO_BOOL = {
    '1': True,
    'y': True,
    'yes': True,
    't': True,
    'true': True,
    'on': True,

    '0': False,
    'n': False,
    'no': False,
    'f': False,
    'false': False,
    'off': False,
}

str_to_bool.PUBLIC_MESSAGE_PATTERN = (
    '"{}" is not a valid YES/NO flag (expected one of: %s; or a '
    'variant of any of them with some letters upper-cased).' % (
        ', '.join('"{}"'.format(k) for k, v in sorted(
            str_to_bool.LOWERCASE_TO_BOOL.items(),
            key=lambda item: (item[1], item[0])))))
