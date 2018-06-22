# -*- coding: utf-8 -*-

# Copyright (c) 2013-2016 NASK. All rights reserved.
#
# For some parts of the source code of the provide_surrogateescape() function:
# Copyright (c) 2011-2013 Victor Stinner. All rights reserved.
# (For more information -- see the provide_surrogateescape()'s docstring.)


import string


class AsciiMixIn(object):

    r"""
    A mix-in class that provides the :meth:`__str__`, :meth:`__unicode__`
    and :meth:`__format__` special methods based on :func:`ascii_str`.

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
    >>> unicode(obj)
    u'Co\\u015btam-co\\u015btam'
    >>> format(obj)
    'N\\xf3 i '

    >>> 'Oto {0:ś}'.format(obj)
    'Oto N\\xf3 i \\u015b'
    >>> u'Oto {0:\\u015b}'.format(obj)  # unicode format string
    u'Oto N\\xf3 i \\u015b'
    >>> 'Oto {0!s}'.format(obj)
    'Oto Co\\u015btam-co\\u015btam'

    >>> 'Oto %s' % obj
    'Oto Co\\u015btam-co\\u015btam'
    >>> u'Oto %s' % obj                 # unicode format string
    u'Oto Co\\u015btam-co\\u015btam'
    """

    def __str__(self):
        return ascii_str(super(AsciiMixIn, self).__str__())

    def __unicode__(self):
        try:
            super_meth = super(AsciiMixIn, self).__unicode__
        except AttributeError:
            super_meth = super(AsciiMixIn, self).__str__
        return ascii_str(super_meth()).decode('ascii')

    def __format__(self, fmt):
        return ascii_str(super(AsciiMixIn, self).__format__(ascii_str(fmt)))


def ascii_str(obj):

    r"""
    Safely convert the given object to an ASCII-only :class:`str`.

    This function does its best to obtain a pure-ASCII string
    representation (possibly :class:`str`/:func:`unicode`-like, though
    :func:`repr` can also be used as the last-resort fallback) -- *not
    raising* any encoding/decoding exceptions.

    The result is an ASCII str, with non-ASCII characters escaped using
    Python literal notation (``\x...``, ``\u...``, ``\U...``).

    >>> ascii_str('')
    ''
    >>> ascii_str(u'')
    ''
    >>> ascii_str('Ala ma kota\nA kot?\n2=2 ')   # pure ASCII str => unchanged
    'Ala ma kota\nA kot?\n2=2 '
    >>> ascii_str(u'Ala ma kota\nA kot?\n2=2 ')
    'Ala ma kota\nA kot?\n2=2 '

    >>> ascii_str(ValueError('Ech, ale błąd!'))  # UTF-8 str => decoded
    'Ech, ale b\\u0142\\u0105d!'
    >>> ascii_str(ValueError(u'Ech, ale b\u0142\u0105d!'))
    'Ech, ale b\\u0142\\u0105d!'

    >>> ascii_str('\xee\xdd \t jaźń')  # non-UTF-8 str => using surrogateescape
    '\\udcee\\udcdd \t ja\\u017a\\u0144'
    >>> ascii_str(u'\udcee\udcdd \t ja\u017a\u0144')
    '\\udcee\\udcdd \t ja\\u017a\\u0144'

    >>> class Nasty(object):
    ...     def __str__(self): raise UnicodeError
    ...     def __unicode__(self): raise UnicodeError
    ...     def __repr__(self): return 'really nas\xc5\xa7y! \xaa'
    ...
    >>> ascii_str(Nasty())
    'really nas\\u0167y! \\udcaa'
    """

    if not isinstance(obj, unicode):
        try:
            s = str(obj)
        except ValueError:
            try:
                obj = unicode(obj)
            except ValueError:
                obj = repr(obj).decode('utf-8', 'surrogateescape')
        else:
            obj = s.decode('utf-8', 'surrogateescape')
    return obj.encode('ascii', 'backslashreplace')


def as_unicode(obj):

    r"""
    Convert the given object to a :class:`unicode` string.

    Unlike :func:`ascii_str`, this function is not decoding-error-proof and
    does not apply any escaping.

    The function requires that the given object is one of the following:

    * a :class:`unicode` string,
    * a UTF-8-decodable :class:`str` string,
    * an object that produces one of the above kinds of strings when
      converted using :class:`unicode` or :class:`str`, or :func:`repr`
      (the conversions are tried in this order);

    if not -- :exc:`~exceptions.UnicodeDecodeError` is raised.

    >>> as_unicode(u'')
    u''
    >>> as_unicode('')
    u''

    >>> as_unicode(u'O\u0142\xf3wek') == u'O\u0142\xf3wek'
    True
    >>> as_unicode('O\xc5\x82\xc3\xb3wek') == u'O\u0142\xf3wek'
    True
    >>> as_unicode(ValueError(u'O\u0142\xf3wek')) == u'O\u0142\xf3wek'
    True
    >>> as_unicode(ValueError('O\xc5\x82\xc3\xb3wek')) == u'O\u0142\xf3wek'
    True

    >>> class Hard(object):
    ...     def __str__(self): raise UnicodeError
    ...     def __unicode__(self): raise UnicodeError
    ...     def __repr__(self): return 'foo'
    ...
    >>> as_unicode(Hard())
    u'foo'

    >>> as_unicode('\xdd')  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    UnicodeDecodeError: ...
    """

    if isinstance(obj, str):
        u = obj.decode('utf-8')
    else:
        try:
            u = unicode(obj)
        except ValueError:
            try:
                u = str(obj).decode('utf-8')
            except ValueError:
                u = repr(obj).decode('utf-8')
    return u


_PYIDENT = string.ascii_letters + string.digits + '_'
_NONPYIDENT = ''.join(set(map(chr, xrange(256))).difference(_PYIDENT))
_TRANS_NONPYIDENT_TO_SPC = string.maketrans(_NONPYIDENT, len(_NONPYIDENT) * ' ')

def py_identifier_str(obj):
    r"""
    Convert the given object to a :class:`str` being a valid Python identifier.

    If the given object is not a string (:class:`str` or
    :class:`unicode`) it is first converted using :func:`ascii_str`.

    The result is a :class:`str` with each series of
    non-Python-identifier characters (i.e., other than ASCII letters,
    ASCII decimal digits and underscore) --

    * removed if such a series is at the beginning or at the end of the
      input string,

    * otherwise replaced with a single underscore

    -- with the proviso that:

    * if the resultant string is empty or starts with a digit another
      single underscore is added at the beginning of the string.

    >>> py_identifier_str('Ala ma kota!')
    'Ala_ma_kota'
    >>> py_identifier_str(' Ala  ma \t kota ! ')
    'Ala_ma_kota'
    >>> py_identifier_str(u' Ala  ma \t kota ! ')
    'Ala_ma_kota'
    >>> py_identifier_str(dict(xyz=' Ala  ma \t kota ! '))
    'xyz_Ala_ma_t_kota'
    >>> py_identifier_str('__foo_bAR___42__')
    '__foo_bAR___42__'
    >>> py_identifier_str(' __foo bAR _ 42 _')
    '__foo_bAR___42__'
    >>> py_identifier_str(' __foo_bAR\xc5\x9b_  \n.) 42__ \xdd')
    '__foo_bAR___42__'
    >>> py_identifier_str(u' __foo_bAR\u015b_  \n.) 42__ \udcdd')
    '__foo_bAR___42__'
    >>> py_identifier_str(ValueError('__foo_bAR\xc5\x9b_\n.) 42_ \xdd'))
    '__foo_bAR_u015b__42__udcdd'
    >>> py_identifier_str([' __foo_bAR\xc5\x9b_', 42, '_ '])
    '__foo_bAR_xc5_x9b__42__'
    >>> py_identifier_str([u' _foo_bAR\u015b_', 42, u'_ '])
    'u__foo_bAR_u015b__42_u__'
    >>> py_identifier_str('x42')
    'x42'
    >>> py_identifier_str('!x42')
    'x42'
    >>> py_identifier_str('_x42')
    '_x42'
    >>> py_identifier_str('42')
    '_42'
    >>> py_identifier_str('!42')
    '_42'
    >>> py_identifier_str('_42')
    '_42'
    >>> py_identifier_str('a,b,c,d,E,f')
    'a_b_c_d_E_f'
    >>> py_identifier_str(',a\xc4\x85b,,c,,,d,,,,E,,,,,f,,,,,')
    'a_b_c_d_E_f'
    >>> py_identifier_str(u',a\u0105b,,c,,,d,,,,E,,,,,f,,,,,')
    'a_b_c_d_E_f'
    >>> py_identifier_str(',1,2, 3 , 4   ,5 , , 6, , , ')
    '_1_2_3_4_5_6'
    >>> py_identifier_str('')
    '_'
    >>> py_identifier_str(u'')
    '_'
    >>> py_identifier_str('\xdd')
    '_'
    >>> py_identifier_str(u'\udcdd')
    '_'
    >>> py_identifier_str('!')
    '_'
    >>> py_identifier_str(u'!!!')
    '_'
    >>> py_identifier_str('!@#$%^')
    '_'
    >>> py_identifier_str('! @ # $ \n % \t ^')
    '_'
    >>> py_identifier_str('_')
    '_'
    >>> py_identifier_str('! @ # $ _ \n % \t ^')
    '_'
    >>> py_identifier_str('___')
    '___'
    >>> py_identifier_str('! @ # $ _ \n % _ \t ^')
    '___'
    >>> py_identifier_str('__!@#__$%^__')
    '________'
    """
    if isinstance(obj, str):
        s = obj
    elif isinstance(obj, unicode):
        s = obj.encode('ascii', 'replace')
    else:
        s = ascii_str(obj)
    s = s.translate(_TRANS_NONPYIDENT_TO_SPC)
    s = '_'.join(s.split())
    if not s or s[0] in string.digits:
        s = '_' + s
    return s


def provide_surrogateescape():

    r"""
    Provide the ``surrogateescape`` error handler for bytes-to-unicode
    decoding.

    The source code of the function has been copied from
    https://bitbucket.org/haypo/misc/src/d76f4ff5d27c746c883d40160c8b4fb0891e79f2/python/surrogateescape.py?at=default
    and then adjusted, optimized and commented.  Original code was created by
    Victor Stinner and released by him under the Python license and the BSD
    2-clause license.

    The ``surrogateescape`` error handler is provided out-of-the-box in
    Python 3 but not in Python 2.  It can be used to convert arbitrary
    binary data to Unicode in a practically non-destructive way.

    .. seealso::

       https://www.python.org/dev/peps/pep-0383.

    This implementation (for Python 2) covers only the decoding part of
    the handler, i.e. the :class:`str`-to-:class:`unicode` conversion.
    The encoding (:class:`unicode`-to-:class:`str`) part is not
    implemented.  Note, however, that once we transformed a binary data
    into a *surrogate-escaped* Unicode data we can (in Python 2) freely
    encode/decode it (:class:`unicode`-to/from-:class:`str`), not using
    ``surrogateescape`` anymore, e.g.:

    >>> # We assume that the function has already been called --
    >>> # as it is imported and called in N6SDK/n6sdk/__init__.py
    >>> b = 'ołówek \xee\xdd'          # utf-8 text + some non-utf-8 mess
    >>> b
    'o\xc5\x82\xc3\xb3wek \xee\xdd'
    >>> u = b.decode('utf-8', 'surrogateescape')
    >>> u
    u'o\u0142\xf3wek \udcee\udcdd'
    >>> b2 = u.encode('utf-8')
    >>> b2                             # now all stuff is utf-8 encoded
    'o\xc5\x82\xc3\xb3wek \xed\xb3\xae\xed\xb3\x9d'
    >>> u2 = b2.decode('utf-8')
    >>> u2 == u
    True

    >>> u.encode('latin2',             # doctest: +IGNORE_EXCEPTION_DETAIL
    ...          'surrogateescape')    # does not work for *encoding*
    Traceback (most recent call last):
      ...
    TypeError: don't know how to handle UnicodeEncodeError in error callback

    This function is idempotent (i.e., it can be called safely multiple
    times -- because if the handler is already registered the function
    does not try to register it again) though it is not thread-safe
    (typically it does not matter as the function is supposed to be
    called somewhere at the beginning of program execution).

    .. note::

       This function is called automatically on first import of
       :mod:`n6sdk` module or any of its submodules.

    .. warning::

       In Python 3 (if you were using a Python-3-based application or
       script to handle data produced with Python 2), the ``utf-8``
       codec (as well as other ``utf-...`` codecs) does not decode
       *surrogate-escaped* data encoded to bytes with the Python 2's
       ``utf-8`` codec unless the ``surrogatepass`` error handler is
       used for decoding (on the Python 3 side).

    """

    def surrogateescape(exc,
                        # to avoid namespace dict lookups:
                        isinstance=isinstance,
                        UnicodeDecodeError=UnicodeDecodeError,
                        ord=ord,
                        unichr=unichr,
                        unicode_join=u''.join):
        if isinstance(exc, UnicodeDecodeError):
            decoded = []
            append_to_decoded = decoded.append
            for ch in exc.object[exc.start:exc.end]:
                code = ord(ch)
                if 0x80 <= code <= 0xFF:
                    append_to_decoded(unichr(0xDC00 + code))
                elif code <= 0x7F:
                    append_to_decoded(unichr(code))
                else:
                    raise exc
            decoded = unicode_join(decoded)
            return (decoded, exc.end)
        else:
            raise TypeError("don't know how to handle {} in error callback"
                            .format(type(exc).__name__))
    import codecs
    try:
        codecs.lookup_error('surrogateescape')
    except LookupError:
        codecs.register_error('surrogateescape', surrogateescape)


def string_to_bool(s):
    """
    Return True or False, given one of the known strings (see examples below).

    >>> string_to_bool('1')
    True
    >>> string_to_bool('y')
    True
    >>> string_to_bool('yes')
    True
    >>> string_to_bool('Yes')  # note: checks are case-insensitive
    True
    >>> string_to_bool('t')
    True
    >>> string_to_bool('true')
    True
    >>> string_to_bool('on')
    True

    >>> string_to_bool('0')
    False
    >>> string_to_bool('n')
    False
    >>> string_to_bool('nO')
    False
    >>> string_to_bool('f')
    False
    >>> string_to_bool('false')
    False
    >>> string_to_bool('off')
    False

    Other string values cause ValueError:

    >>> string_to_bool('unknown')        # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...
    >>> string_to_bool('')               # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...

    Non-string values cause TypeError:

    >>> string_to_bool(True)             # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...
    >>> string_to_bool(None)             # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...
    >>> string_to_bool(1)                # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...
    """
    if not isinstance(s, basestring):
        raise TypeError('{!r} is not a string'.format(s))
    s_lowercased = s.lower()
    try:
        return string_to_bool.LOWERCASE_TO_BOOL[s_lowercased]
    except KeyError:
        raise ValueError(string_to_bool.PUBLIC_MESSAGE_PATTERN.format(
            ascii_str(s)).rstrip('.'))

string_to_bool.LOWERCASE_TO_BOOL = {
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

string_to_bool.PUBLIC_MESSAGE_PATTERN = (
    '"{}" is not a valid YES/NO flag (expected one of: %s; or a '
    'variant of any of them with some letters uppercased).' % (
        ', '.join('"{}"'.format(k) for k, v in sorted(
            string_to_bool.LOWERCASE_TO_BOOL.iteritems(),
            key=lambda item: (item[1], item[0])))))
