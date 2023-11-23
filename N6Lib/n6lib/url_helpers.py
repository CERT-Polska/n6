# Copyright (c) 2019-2023 NASK. All rights reserved.

import collections
import re
import ipaddress

from n6lib.common_helpers import (
    as_bytes,
    as_unicode,
    limit_str,
    replace_surrogate_pairs_with_proper_codepoints,
)



#
# Public constants
#

# (based on RFCs 3986 and 3987)
URL_SCHEME_AND_REST_REGEX = re.compile(r'\A'
                                       r'(?P<scheme>[a-zA-Z][\-+.0-9a-zA-Z]*)'
                                       r'(?P<rest>:.*)',
                                       re.ASCII)

# (similar to `URL_SCHEME_AND_REST_REGEX`, but slightly less strict;
# used -- among others -- in n6lib.record_dict.RecordDict.adjust_url;
# NOTE: typically, it should *not* be used in a new code;
# instead of it, use `URL_SCHEME_AND_REST_REGEX` defined above!)
URL_SCHEME_AND_REST_LEGACY_REGEX = re.compile(r'\A'
                                              r'(?P<scheme>[\-+.0-9a-zA-Z]+)'
                                              r'(?P<rest>:.*)',
                                              re.ASCII)

# (based on various sources, mainly on some RFCs, but not only...)
URL_SCHEME_TO_DEFAULT_PORT = {
    'ftp': 21,
    'gopher': 70,
    'http': 80,
    'https': 443,
    'imap': 143,
    'ldap': 389,
    'ldaps': 636,
    'news': 119,
    'nntp': 119,
    'snews': 563,
    'snntp': 563,
    'telnet': 23,
    'ws': 80,
    'wss': 443,
}

# (based on RFC 3490
# as well as https://www.unicode.org/reports/tr46/#TableDerivationStep1)
DOMAIN_LABEL_SEPARATOR_REGEX = re.compile('[.\u3002\uff0e\uff61]')
DOMAIN_LABEL_SEPARATOR_UTF8_BYTES_REGEX = re.compile(br'(?:'
                                                     br'\.'
                                                     br'|'
                                                     br'\343\200\202'
                                                     br'|'
                                                     br'\357\274\216'
                                                     br'|'
                                                     br'\357\275\241'
                                                     br')')


# *EXPERIMENTAL* (likely to be changed or removed in the future
# without any warning/deprecation/etc.)
PROVISIONAL_URL_SEARCH_KEY_PREFIX = 'SY:'



#
# Public functions
#

def does_look_like_url(s):
    """
    Check (very roughly) whether the given string looks like a URL.

    It only checks whether the given string starts with some letter,
    optionally followed by letter|digit|dot|plus|minus characters,
    separated with a colon from the rest of the string which can
    contain anything.

    >>> does_look_like_url('http://www.example.com')
    True
    >>> does_look_like_url('MAILTO:www.example.com')
    True
    >>> does_look_like_url('foo.BAR+Spam-4-you:www.example.com')
    True

    >>> does_look_like_url('www.example.com')
    False
    >>> does_look_like_url('www.example.com/http://foo.bar.pl')
    False
    >>> does_look_like_url('4ttp://www.example.com')
    False
    >>> does_look_like_url('http//www.example.com')
    False
    """
    return (URL_SCHEME_AND_REST_REGEX.search(s) is not None)


# TODO: tests
def does_look_like_http_url_without_prefix(s):
    """
    Try to guess (using some heuristics) whether the given string (or
    binary data blob) may be an incomplete HTTP URL starting with the
    host part, i.e., an HTTP URL unprovided with the `http://` prefix.
    """
    if isinstance(s, (bytes, bytearray)):
        s = as_unicode(s, 'surrogatepass')
    return bool(_INCOMPLETE_HTTP_URL_CANDIDATE_STARTING_WITH_HOST_REGEX.search(s))


# TODO: more tests...
def normalize_url(url,
                  *,
                  unicode_str=False,
                  merge_surrogate_pairs=False,
                  empty_path_slash=False,
                  remove_ipv6_zone=False,
                  norm_brief=None):
    r"""
    Apply to the given string (or binary data blob) as much of the basic
    URL/IRI normalization as possible, provided that no semantic changes
    are made (i.e., the intent is that the resultant URL/IRI is
    semantically equivalent to the given one).

    Args (required):
        `url` (str or bytes/bytearray):
            The URL (or URI, or IRI) to be normalized.

    Kwargs (optional):
        `unicode_str` (bool; default: False):
            Whether, *before* the actual URL normalization, the `url`,
            if given as a `bytes`/`bytearray`, should be coerced to
            `str` using the `utf-8` codec with the `surrogatepass`
            error handler.

            This flag is supposed to be used only in the case of URLs
            which were originally obtained as `str` instances (which
            later, for some reasons, might be encoded to `bytes` or
            `bytearray` using the `surrogatepass` error handler); if
            garbage bytes are encountered then a `UnicodeDecodeError`
            is raised.

        `merge_surrogate_pairs` (bool; default: False):
            Whether, *before* the actual URL normalization but *after*
            `unicode_str`-flag-related processing (if any), the `url`
            should be:

            * if given as a `bytes`/`bytearray` and `unicode_str` is
              false -- processed in the following way: first try to
              decode it using the `utf-8` codec with the `surrogatepass`
              error handler; it that fails then the original `url`
              argument, intact, becomes the result (only coerced to
              `bytes` if it was given as a `bytearray`); otherwise,
              apply `replace_surrogate_pairs_with_proper_codepoints()`
              to the decoded content (to ensure that representation of
              non-BMP characters is consistent...) and encode the result
              using the `utf-8` codec with the `surrogatepass` error
              handler; the resultant value is a `bytes` object;

            * otherwise (`url` given as a `str`, or `unicode_str` is
              true => so, effectively, `url` is a `str`) -- processed by
              applying `replace_surrogate_pairs_with_proper_codepoints()`
              (to ensure that representation of non-BMP characters is
              consistent...); the resultant value is a `str` object.

        `empty_path_slash` (bool; default: False):
            Whether the *path* component of the given URL should be
            replaced with `/` if the `url`'s *scheme* is `http`, `https`
            or `ftp` *and* the *path* is empty (note that, generally,
            this normalization step does not change the URL semantics,
            with the exception of an URL being the request target of an
            `OPTIONS` HTTP request; see RFC 7230, section 2.7.3).

        `remove_ipv6_zone` (bool; default: False):
            Whether the IPv6 zone identifier being a part of an IPv6
            address in the `url`'s *host* component should be removed
            (note that, generally, IPv6 zone identifier has no meaning
            outside the local system it is related to; see RFC 6874,
            section 1).

        `norm_brief` (iterable or None; default: None):
            If not `None`, it should be a string (or another iterable
            yielding strings of length 1) whose items are first letters
            of any (zero or more) of the other keyword-only argument
            names -- equivalent to setting the corresponding arguments
            to `True` (useful in contexts where brevity is important).
            If given, no other keyword arguments can be set to `True`.

    Returns:
        A `str` object (`if a `str` was given) or a `bytes` object (if a
        `bytes` or `bytearray` object was given *and* `unicode_str` was
        false) representing the URL after a *best effort* but *keeping
        semantic equivalence* normalization (see below: the description
        of the algorithm).

    Raises:
        * `TypeError` -- if:

          * `url` is not a `str`/`bytes`/`bytearray`,
          * `norm_brief` is given when (an)other keyword-only argument(s)
            is/are also given;

        * `UnicodeDecodeError` -- if `unicode_str` is true and `url` is
          such a `bytes`/`bytearray` that is not decodable to `str` using
          the `utf-8` codec with the `surrogatepass` error handler;

        * `ValueError` (other than `UnicodeDecodeError`) -- if:

          * `norm_brief` contains any value not being the first letter
            of another keyword-only argument;
          * `norm_brief` contains duplicate values.

    ***

    The algorithm of normalization consists of the following steps:

    [Note #1: the `+` operator in this description means *string
    concatenation*. Note #2: if a `bytes` object is processed, it is
    treated as if it was a string; the UTF-8 encoding is then assumed
    for character recognition and regular expression matching.]

    0. Optional `url` decoding/recoding (see the above description of
       the `unicode_str` and `merge_surrogate_pairs` arguments).

    1. Try to split the `url` into two parts: the `scheme` component
       (matching the `scheme` group of the regular expression
       `URL_SCHEME_AND_REST_REGEX`) and `rest` (the rest of the URL).

    2. If no `scheme` could be singled out in step 1 then stop here --
       returning the whole `url`; otherwise proceed to step 3.

    3. Convert `scheme` to *lowercase*.

    4. Try to split `rest` into the following parts:

       * `before host` (i.e., the "://" separator, optionally followed
         by any number of non-"/?#@" characters which, if present, are
         obligatorily followed by exactly one "@"),
       * `host` (see below: steps 6 to 13...),
       * optional `port` (i.e., ":<decimal number>" or just ":"),
       * optional `path` (i.e., "/" + optionally any number of
         non-"?#" characters),
       * optional `after path` (that is: "?" or "#", optionally
         followed by any number of any characters).

    5. If `rest` could not be split in step 4 then stop here --
       returning `scheme` + `rest`; otherwise proceed to step 6.

    6. If `host` consists of "[" + `ipv6` + optional `ipv6 zone` + "]"
       -- where `ipv6` (consisting of hexadecimal digits and ":"
       characters, with optional suffix in the IPv4 four-octets format)
       is a supposed IPv6 address (see RFC 3986) and `ipv6 zone`
       (consisting, if present, of one "%" character followed by some
       non-"/?#[]" characters) is a supposed IPv6 zone identifier (see
       RFC 6874) -- then proceed to step 7, otherwise skip to step 12.

    7. Convert `ipv6` to the normalized IPv6 format which:

       * uses only *lowercase* hexadecimal digits, and `:` characters
         as separators (in particular, the last 32 bits of the address
         are *not* represented using the IPv4 four-octets format),

       * is *condensed*, i.e., non-zero hexadecimal segments are
         formatted without leading zeros, and the `::` marker (if
         applicable) is used to replace the leftmost of the longest
         sequences of '0' segments (see RFC 5952, Section 4.2).

    8. If normalization in step 7 was impossible because of syntactic
       incorrectness (i.e., `ipv6` could not be parsed as a valid IPv6
       address) then leave `ipv6` intact.

    9. If `ipv6 zone` is *not* present, or the `remove_ipv6_zone`
       argument is true, then set `ipv6 zone` to an empty string and
       skip to step 11; otherwise proceed to step 10.

    10. If `ipv6 zone` consists only of ASCII characters then convert
        it to *lowercase*; otherwise leave it intact.

    11. Set `host` to "[" + `ipv6` + `ipv6 zone` + "]"; then skip to
        step 14.

    12. Split `host` (consisting of some non-":/?#" characters,
        presumably representing some hostname or IPv4/IPv[Future]
        address; see RFC 3986...) into *labels*, using dot characters
        defined by the `DOMAIN_LABEL_SEPARATOR_..._REGEX` constants
        as the delimiter (in such a way that *labels* do not include
        delimiter dots); for each such a `label` do the following:
        if `label` consists only of ASCII characters then convert
        it to *lowercase*, otherwise leave it intact.

    13. Set `host` to the result of concatenation of the *labels* from
        step 12 (each of them converted to *lowercase* if ASCII-only)
        interleaved with ".".

    14. If `port` is *not* present, or `port` is ":", or ":" followed
        by the known *default port number* for the particular `scheme`
        (according to the mapping `URL_SCHEME_TO_DEFAULT_PORT`; e.g.,
        80 for the "http" value of `scheme`), then set `port` to an
        empty string; otherwise leave `port` intact.

    15. If `path` is present then leave it intact and skip to step 17;
        otherwise proceed to step 16.

    16. If the `empty_path_slash` argument is true and `scheme` is one
        of: "http", "https", "ftp" -- then set `path` to "/"; otherwise
        set `path` to an empty string.

    17. If `after path` is *not* present then set it to an empty
        string.

    18. Stop here -- returning `scheme` + `before host` + `host` +
        `port` + `path` + `after path`.


    Ad 0:

    >>> normalize_url('\U0010ffff')
    '\U0010ffff'
    >>> normalize_url('\U0010ffff', merge_surrogate_pairs=True)
    '\U0010ffff'
    >>> normalize_url('\U0010ffff', unicode_str=True)
    '\U0010ffff'
    >>> normalize_url('\U0010ffff', unicode_str=True, merge_surrogate_pairs=True)
    '\U0010ffff'
    >>> normalize_url(b'\xf4\x8f\xbf\xbf')
    b'\xf4\x8f\xbf\xbf'
    >>> normalize_url(b'\xf4\x8f\xbf\xbf', merge_surrogate_pairs=True)
    b'\xf4\x8f\xbf\xbf'
    >>> normalize_url(b'\xf4\x8f\xbf\xbf', unicode_str=True)
    '\U0010ffff'
    >>> normalize_url(b'\xf4\x8f\xbf\xbf', unicode_str=True, merge_surrogate_pairs=True)
    '\U0010ffff'
    >>> normalize_url('\udbff\udfff')
    '\udbff\udfff'
    >>> normalize_url('\udbff\udfff', merge_surrogate_pairs=True)
    '\U0010ffff'
    >>> normalize_url('\udbff\udfff', unicode_str=True)
    '\udbff\udfff'
    >>> normalize_url('\udbff\udfff', unicode_str=True, merge_surrogate_pairs=True)
    '\U0010ffff'
    >>> normalize_url(b'\xed\xaf\xbf\xed\xbf\xbf')
    b'\xed\xaf\xbf\xed\xbf\xbf'
    >>> normalize_url(b'\xed\xaf\xbf\xed\xbf\xbf', merge_surrogate_pairs=True)
    b'\xf4\x8f\xbf\xbf'
    >>> normalize_url(b'\xed\xaf\xbf\xed\xbf\xbf', unicode_str=True)
    '\udbff\udfff'
    >>> normalize_url(b'\xed\xaf\xbf\xed\xbf\xbf', unicode_str=True, merge_surrogate_pairs=True)
    '\U0010ffff'
    >>> normalize_url('\udfff\udbff\udfff\udbff')
    '\udfff\udbff\udfff\udbff'
    >>> normalize_url('\udfff\udbff\udfff\udbff', merge_surrogate_pairs=True)
    '\udfff\U0010ffff\udbff'
    >>> normalize_url('\udfff\udbff\udfff\udbff', unicode_str=True)
    '\udfff\udbff\udfff\udbff'
    >>> normalize_url('\udfff\udbff\udfff\udbff', unicode_str=True, merge_surrogate_pairs=True)
    '\udfff\U0010ffff\udbff'
    >>> normalize_url(b'\xed\xbf\xbf\xed\xaf\xbf\xed\xbf\xbf\xed\xaf\xbf')
    b'\xed\xbf\xbf\xed\xaf\xbf\xed\xbf\xbf\xed\xaf\xbf'
    >>> normalize_url(b'\xed\xbf\xbf\xed\xaf\xbf\xed\xbf\xbf\xed\xaf\xbf',
    ...               merge_surrogate_pairs=True)
    b'\xed\xbf\xbf\xf4\x8f\xbf\xbf\xed\xaf\xbf'
    >>> normalize_url(b'\xed\xbf\xbf\xed\xaf\xbf\xed\xbf\xbf\xed\xaf\xbf',
    ...               unicode_str=True)
    '\udfff\udbff\udfff\udbff'
    >>> normalize_url(b'\xed\xbf\xbf\xed\xaf\xbf\xed\xbf\xbf\xed\xaf\xbf',
    ...               unicode_str=True,
    ...               merge_surrogate_pairs=True)
    '\udfff\U0010ffff\udbff'
    >>> normalize_url(b'\xed')  # (non-UTF-8 garbage)
    b'\xed'
    >>> normalize_url(b'\xed', merge_surrogate_pairs=True)
    b'\xed'
    >>> normalize_url(b'\xed', unicode_str=True)  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    UnicodeDecodeError: ...
    >>> normalize_url(b'\xed',
    ...               unicode_str=True,
    ...               merge_surrogate_pairs=True)  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    UnicodeDecodeError: ...
    >>> normalize_url(b'\xed\xed\xbf\xbf\xed\xaf\xbf\xed\xbf\xbf\xed\xaf\xbf')
    b'\xed\xed\xbf\xbf\xed\xaf\xbf\xed\xbf\xbf\xed\xaf\xbf'
    >>> normalize_url(b'\xed\xed\xbf\xbf\xed\xaf\xbf\xed\xbf\xbf\xed\xaf\xbf',
    ...               merge_surrogate_pairs=True)
    b'\xed\xed\xbf\xbf\xed\xaf\xbf\xed\xbf\xbf\xed\xaf\xbf'
    >>> normalize_url(b'\xed\xed\xbf\xbf\xed\xaf\xbf\xed\xbf\xbf\xed\xaf\xbf',
    ...               unicode_str=True)  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    UnicodeDecodeError: ...
    >>> normalize_url(b'\xed\xed\xbf\xbf\xed\xaf\xbf\xed\xbf\xbf\xed\xaf\xbf',
    ...               unicode_str=True,
    ...               merge_surrogate_pairs=True)  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    UnicodeDecodeError: ...


    Ad 0-2:

    >>> normalize_url(b'Blabla-bla!@#$ %^&\xc4\x85\xcc')
    b'Blabla-bla!@#$ %^&\xc4\x85\xcc'
    >>> normalize_url(b'Blabla-bla!@#$ %^&\xc4\x85\xcc',
    ...               merge_surrogate_pairs=True)
    b'Blabla-bla!@#$ %^&\xc4\x85\xcc'
    >>> normalize_url(b'Blabla-bla!@#$ %^&\xc4\x85\xed\xb3\x8c',
    ...               merge_surrogate_pairs=True)
    b'Blabla-bla!@#$ %^&\xc4\x85\xed\xb3\x8c'
    >>> normalize_url(b'Blabla-bla!@#$ %^&\xc4\x85\xed\xb3\x8c',
    ...               unicode_str=True)
    'Blabla-bla!@#$ %^&\u0105\udccc'
    >>> normalize_url(b'Blabla-bla!@#$ %^&\xc4\x85\xed\xb3\x8c',
    ...               unicode_str=True,
    ...               merge_surrogate_pairs=True)
    'Blabla-bla!@#$ %^&\u0105\udccc'
    >>> normalize_url('Blabla-bla!@#$ %^&\u0105\udccc')
    'Blabla-bla!@#$ %^&\u0105\udccc'


    Ad 0-1 + 3 + 5:

    >>> normalize_url(b'Some-Scheme:Blabla-bla!@#$ %^&\xc4\x85\xcc')
    b'some-scheme:Blabla-bla!@#$ %^&\xc4\x85\xcc'
    >>> normalize_url(b'Some-Scheme:Blabla-bla!@#$ %^&\xc4\x85\xcc',
    ...               merge_surrogate_pairs=True)
    b'some-scheme:Blabla-bla!@#$ %^&\xc4\x85\xcc'
    >>> normalize_url(b'Some-Scheme:Blabla-bla!@#$ %^&\xc4\x85\xed\xb3\x8c',
    ...               merge_surrogate_pairs=True)
    b'some-scheme:Blabla-bla!@#$ %^&\xc4\x85\xed\xb3\x8c'
    >>> normalize_url(b'SOME-scheme:Blabla-bla!@#$ %^&\xc4\x85\xed\xb3\x8c',
    ...               unicode_str=True)
    'some-scheme:Blabla-bla!@#$ %^&\u0105\udccc'
    >>> normalize_url(b'SOME-scheme:Blabla-bla!@#$ %^&\xc4\x85\xed\xb3\x8c',
    ...               unicode_str=True,
    ...               merge_surrogate_pairs=True)
    'some-scheme:Blabla-bla!@#$ %^&\u0105\udccc'
    >>> normalize_url('somE-sCHEmE:Blabla-bla!@#$ %^&\u0105\udccc')
    'some-scheme:Blabla-bla!@#$ %^&\u0105\udccc'


    Ad 0-1 + 3-4 + 6-11 + 14-18:

    >>> normalize_url(b'HtTP://[2001:0DB8:85A3:0000:0000:8A2E:0370:7334]')
    b'http://[2001:db8:85a3::8a2e:370:7334]'
    >>> normalize_url(b'HtTP://[2001:0DB8:85A3:0000:0000:8A2E:0370:7334FAB]')
    b'http://[2001:0DB8:85A3:0000:0000:8A2E:0370:7334FAB]'
    >>> normalize_url(b'HtTP://[2001:0DB8:85A3:0000:0000:8A2E:3.112.115.52%25en1]')
    b'http://[2001:db8:85a3::8a2e:370:7334%25en1]'
    >>> normalize_url(b'HtTP://[2001:0DB8:85A3::8A2E:0370:7334]/fooBAR',
    ...               empty_path_slash=True)
    b'http://[2001:db8:85a3::8a2e:370:7334]/fooBAR'
    >>> normalize_url(b'HtTP://[2001:0DB8:85A3:0000:0000:8A2E:3.112.115.52]:80')
    b'http://[2001:db8:85a3::8a2e:370:7334]'
    >>> normalize_url(b'HtTP://[2001:0DB8:85A3:0000:0000:8A2E:0370:7334%25en1]:80',
    ...               empty_path_slash=True)
    b'http://[2001:db8:85a3::8a2e:370:7334%25en1]/'
    >>> normalize_url(b'HtTP://[2001:DB8:85A3::8A2E:3.112.115.52]',
    ...               remove_ipv6_zone=True)
    b'http://[2001:db8:85a3::8a2e:370:7334]'
    >>> normalize_url(b'HtTP://[2001:0db8:85a3:0000:0000:8a2e:0370:7334%25EN1]',
    ...               remove_ipv6_zone=True)
    b'http://[2001:db8:85a3::8a2e:370:7334]'
    >>> normalize_url(b'HtTP://[2001:0DB8:85A3:0000:0000:8A2E:3.112.115.52%25en1]',
    ...               remove_ipv6_zone=True,
    ...               empty_path_slash=True)
    b'http://[2001:db8:85a3::8a2e:370:7334]/'
    >>> normalize_url(b'HtTP://[2001:0DB8:85A3::8A2E:0370:7334%25en1]:80',
    ...               remove_ipv6_zone=True)
    b'http://[2001:db8:85a3::8a2e:370:7334]'
    >>> normalize_url(b'HtTP://[2001:DB8:85A3:0000:0000:8A2E:3.112.115.52%25en1]:80',
    ...               remove_ipv6_zone=True,
    ...               empty_path_slash=True)
    b'http://[2001:db8:85a3::8a2e:370:7334]/'
    >>> normalize_url(b'HtTP://[2001:DB8:85A3::0123%25En1]:80#\xed\xaf\xbf\xed\xbf\xbf')
    b'http://[2001:db8:85a3::123%25en1]#\xed\xaf\xbf\xed\xbf\xbf'
    >>> normalize_url(b'HtTP://[2001:DB8:85A3::0123%25En1]:80#\xed\xaf\xbf\xed\xbf\xbf',
    ...               remove_ipv6_zone=True)
    b'http://[2001:db8:85a3::123]#\xed\xaf\xbf\xed\xbf\xbf'
    >>> normalize_url(b'HtTP://[2001:DB8:85A3::0123%25En1]:80#\xed\xaf\xbf\xed\xbf\xbf',
    ...               empty_path_slash=True)
    b'http://[2001:db8:85a3::123%25en1]/#\xed\xaf\xbf\xed\xbf\xbf'
    >>> normalize_url(b'HtTP://[2001:DB8:85A3::0123%25En1]:80#\xed\xaf\xbf\xed\xbf\xbf',
    ...               remove_ipv6_zone=True,
    ...               empty_path_slash=True)
    b'http://[2001:db8:85a3::123]/#\xed\xaf\xbf\xed\xbf\xbf'
    >>> normalize_url(b'HtTP://[2001:DB8:85A3::0123%25En1]:80#\xed\xaf\xbf\xed\xbf\xbf',
    ...               merge_surrogate_pairs=True,
    ...               remove_ipv6_zone=True,
    ...               empty_path_slash=True)
    b'http://[2001:db8:85a3::123]/#\xf4\x8f\xbf\xbf'
    >>> normalize_url(b'HtTP://[2001:DB8:85A3::0123%25En1]:80#\xed\xaf\xbf\xed\xbf\xbf',
    ...               unicode_str=True,
    ...               remove_ipv6_zone=True,
    ...               empty_path_slash=True)
    'http://[2001:db8:85a3::123]/#\udbff\udfff'
    >>> normalize_url(b'HtTP://[2001:DB8:85A3::0123%25En1]:80#\xed\xaf\xbf\xed\xbf\xbf',
    ...               unicode_str=True,
    ...               merge_surrogate_pairs=True,
    ...               remove_ipv6_zone=True,
    ...               empty_path_slash=True)
    'http://[2001:db8:85a3::123]/#\U0010ffff'
    >>> normalize_url('HtTP://[2001:0DB8:85A3:0000:0000:8A2E:3.112.115.52]')
    'http://[2001:db8:85a3::8a2e:370:7334]'
    >>> normalize_url('HtTP://[2001:0db8:85a3::8a2e:370:7334%25EN1]')
    'http://[2001:db8:85a3::8a2e:370:7334%25en1]'
    >>> normalize_url('HtTP://[2001:0DB8:85A3:0000:0000:8A2E:0370:7334FAB%25eN1]',
    ...               empty_path_slash=True)
    'http://[2001:0DB8:85A3:0000:0000:8A2E:0370:7334FAB%25en1]/'
    >>> normalize_url('HtTP://[2001:0DB8:85A3:0000:0000:8a2e:3.112.115.52]',
    ...               empty_path_slash=True)
    'http://[2001:db8:85a3::8a2e:370:7334]/'
    >>> normalize_url('HtTP://[2001:0DB8:85A3:0000:0000:8A2E:0370:7334]:80')
    'http://[2001:db8:85a3::8a2e:370:7334]'
    >>> normalize_url('HtTP://[2001:0DB8:85A3::8A2E:3.112.115.52%25en1]:80',
    ...               empty_path_slash=True)
    'http://[2001:db8:85a3::8a2e:370:7334%25en1]/'
    >>> normalize_url('HtTP://[2001:db8:85a3:0000:0000:8A2E:0370:7334]',
    ...               remove_ipv6_zone=True)
    'http://[2001:db8:85a3::8a2e:370:7334]'
    >>> normalize_url('HtTP://[2001:0DB8:85A3:0000:0000:8A2E:3.112.115.52%25en1]/fooBAR',
    ...               remove_ipv6_zone=True)
    'http://[2001:db8:85a3::8a2e:370:7334]/fooBAR'
    >>> normalize_url('HtTP://[2001:0DB8:85A3::8A2E:0370:7334%25en1]',
    ...               remove_ipv6_zone=True,
    ...               empty_path_slash=True)
    'http://[2001:db8:85a3::8a2e:370:7334]/'
    >>> normalize_url('HtTP://[2001:0DB8:85A3:0000:0000:8A2E:3.112.115.52%25en1]:80',
    ...               remove_ipv6_zone=True)
    'http://[2001:db8:85a3::8a2e:370:7334]'
    >>> normalize_url('HtTP://[2001:0DB8:85A3:0000:0000:8A2E:0370:7334%25en1]:80',
    ...               remove_ipv6_zone=True,
    ...               empty_path_slash=True)
    'http://[2001:db8:85a3::8a2e:370:7334]/'
    >>> normalize_url('HtTP://[2001:DB8:85A3::0123%25En1]:80#\udbff\udfff',
    ...               remove_ipv6_zone=True,
    ...               empty_path_slash=True)
    'http://[2001:db8:85a3::123]/#\udbff\udfff'
    >>> normalize_url('HtTP://[2001:DB8:85A3::0123%25En1]:80#\udbff\udfff',
    ...               merge_surrogate_pairs=True,
    ...               remove_ipv6_zone=True,
    ...               empty_path_slash=True)
    'http://[2001:db8:85a3::123]/#\U0010ffff'
    >>> normalize_url('HtTP://[2001:DB8:85A3::0123%25En1]:80#\udbff\udfff',
    ...               unicode_str=True,
    ...               remove_ipv6_zone=True,
    ...               empty_path_slash=True)
    'http://[2001:db8:85a3::123]/#\udbff\udfff'
    >>> normalize_url('HtTP://[2001:DB8:85A3::0123%25En1]:80#\udbff\udfff',
    ...               unicode_str=True,
    ...               merge_surrogate_pairs=True,
    ...               remove_ipv6_zone=True,
    ...               empty_path_slash=True)
    'http://[2001:db8:85a3::123]/#\U0010ffff'
    >>> normalize_url(b'HtTPS://[2001:DB8:85A3:0000:0000:8A2E:3.112.115.52%25En1]:80')
    b'https://[2001:db8:85a3::8a2e:370:7334%25en1]:80'
    >>> normalize_url(b'HtTPS://[2001:DB8:85A3:0000:0000:8A2E:3.112.115.52%25en1]:80',
    ...               remove_ipv6_zone=True)
    b'https://[2001:db8:85a3::8a2e:370:7334]:80'
    >>> normalize_url(b'HtTPS://[2001:0db8:85a3::8a2E:3.112.115.52%25en1]:443',
    ...               remove_ipv6_zone=True)
    b'https://[2001:db8:85a3::8a2e:370:7334]'
    >>> normalize_url(b'HtTPS://[2001:DB8:85A3:0000:0000:8A2E:0370:7334%25eN\xc4\x851]:80',
    ...               empty_path_slash=True)
    b'https://[2001:db8:85a3::8a2e:370:7334%25eN\xc4\x851]:80/'
    >>> normalize_url('HtTPS://[2001:0db8:85a3::8a2E:3.112.115.52%25En1]:443')
    'https://[2001:db8:85a3::8a2e:370:7334%25en1]'
    >>> normalize_url('HtTPS://[2001:0DB8:85A3:0000:0000:8A2E:3.112.115.52%25eN\xc4\x851]:443',
    ...               empty_path_slash=True)
    'https://[2001:db8:85a3::8a2e:370:7334%25eN\xc4\x851]/'
    >>> normalize_url('HtTPS://[2001:0DB8:85A3::8A2E:0370:7334%25eN1]:80',
    ...               remove_ipv6_zone=True,
    ...               empty_path_slash=True)
    'https://[2001:db8:85a3::8a2e:370:7334]:80/'
    >>> normalize_url('HtTPS://[2001:0DB8:85A3::8A2E:370:7334%25eN1]:443',
    ...               remove_ipv6_zone=True,
    ...               empty_path_slash=True)
    'https://[2001:db8:85a3::8a2e:370:7334]/'


    Ad 0-1 + 3-4 + 12-18:

    >>> normalize_url(b'HTTP://WWW.XyZ-\xc4\x85\xcc.eXamplE.com',
    ...               empty_path_slash=True)
    b'http://www.XyZ-\xc4\x85\xcc.example.com/'
    >>> normalize_url(b'HTTP://WWW.XyZ-\xc4\x85\xcc.eXamplE.com',
    ...               empty_path_slash=True,
    ...               merge_surrogate_pairs=True)
    b'http://www.XyZ-\xc4\x85\xcc.example.com/'
    >>> normalize_url(b'HTTP://WWW.XyZ-\xc4\x85\xcc.eXamplE.com',
    ...               merge_surrogate_pairs=True)
    b'http://www.XyZ-\xc4\x85\xcc.example.com'
    >>> normalize_url(b'HTTP://WWW.XyZ-\xc4\x85\xcc.eXamplE.com',
    ...               unicode_str=True)  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    UnicodeDecodeError: ...
    >>> normalize_url(b'HTTP://WWW.XyZ-\xc4\x85.eXamplE.com:80/fooBAR')
    b'http://www.XyZ-\xc4\x85.example.com/fooBAR'
    >>> normalize_url(b'HtTP://WWW.XyZ-\xc4\x85.eXamplE.com:80',
    ...               empty_path_slash=True)
    b'http://www.XyZ-\xc4\x85.example.com/'
    >>> normalize_url(b'HtTP://WWW.XyZ-\xc4\x85.eXamplE.com:80/fooBAR',
    ...               empty_path_slash=True)
    b'http://www.XyZ-\xc4\x85.example.com/fooBAR'
    >>> normalize_url(b'HTTP://WWW.XyZ-\xc4\x85\xcc.eXamplE.com',
    ...               merge_surrogate_pairs=True)
    b'http://www.XyZ-\xc4\x85\xcc.example.com'
    >>> normalize_url(b'HTTP://WWW.XyZ-\xc4\x85\xcc.eXamplE.com',
    ...               unicode_str=True)  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    UnicodeDecodeError: ...
    >>> normalize_url('HTtp://WWW.XyZ-\u0105\udccc.eXamplE.com:80')
    'http://www.XyZ-\u0105\udccc.example.com'
    >>> normalize_url('HTtp://WWW.XyZ-\u0105.eXamplE.com:80/')
    'http://www.XyZ-\u0105.example.com/'
    >>> normalize_url('hTTP://WWW.XyZ-\u0105.eXamplE.com:80',
    ...               empty_path_slash=True)
    'http://www.XyZ-\u0105.example.com/'
    >>> normalize_url(b'HTTPS://WWW.XyZ-\xc4\x85.eXamplE.com:80')
    b'https://www.XyZ-\xc4\x85.example.com:80'
    >>> normalize_url(b'HTTPS://WWW.XyZ-\xc4\x85.eXamplE.com:80/fooBAR')
    b'https://www.XyZ-\xc4\x85.example.com:80/fooBAR'
    >>> normalize_url(b'HTTPs://WWW.XyZ-\xc4\x85.eXamplE.com:443',
    ...               empty_path_slash=True)
    b'https://www.XyZ-\xc4\x85.example.com/'
    >>> normalize_url(b'HTTPs://WWW.XyZ-\xc4\x85.eXamplE.com:443',
    ...               empty_path_slash=True,
    ...               merge_surrogate_pairs=True)
    b'https://www.XyZ-\xc4\x85.example.com/'
    >>> normalize_url(b'HTTPs://WWW.XyZ-\xc4\x85.eXamplE.com:443',
    ...               empty_path_slash=True,
    ...               unicode_str=True)
    'https://www.XyZ-\u0105.example.com/'
    >>> normalize_url('httpS://WWW.XyZ-\u0105.eXamplE.com:80',
    ...               empty_path_slash=True)
    'https://www.XyZ-\u0105.example.com:80/'
    >>> normalize_url('httpS://WWW.XyZ-\u0105.eXamplE.com:80/fooBAR',
    ...               empty_path_slash=True)
    'https://www.XyZ-\u0105.example.com:80/fooBAR'
    >>> normalize_url('hTtpS://WWW.XyZ-\u0105.eXamplE.com:443')
    'https://www.XyZ-\u0105.example.com'
    >>> normalize_url('httpS://WWW.XyZ-\u0105.eXamplE.com:80/fooBAR',
    ...               empty_path_slash=True,
    ...               merge_surrogate_pairs=True)
    'https://www.XyZ-\u0105.example.com:80/fooBAR'
    >>> normalize_url('httpS://WWW.XyZ-\u0105.eXamplE.com:80/fooBAR',
    ...               empty_path_slash=True,
    ...               unicode_str=True)
    'https://www.XyZ-\u0105.example.com:80/fooBAR'

    Ad use of the `norm_brief` keyword argument:

    >>> normalize_url(b'HtTP://[2001:DB8:85A3::0123%25En1]:80#\xed\xaf\xbf\xed\xbf\xbf',
    ...               norm_brief='')
    b'http://[2001:db8:85a3::123%25en1]#\xed\xaf\xbf\xed\xbf\xbf'
    >>> normalize_url(b'HtTP://[2001:DB8:85A3::0123%25En1]:80#\xed\xaf\xbf\xed\xbf\xbf',
    ...               norm_brief='r')
    b'http://[2001:db8:85a3::123]#\xed\xaf\xbf\xed\xbf\xbf'
    >>> normalize_url(b'HtTP://[2001:DB8:85A3::0123%25En1]:80#\xed\xaf\xbf\xed\xbf\xbf',
    ...               norm_brief='e')
    b'http://[2001:db8:85a3::123%25en1]/#\xed\xaf\xbf\xed\xbf\xbf'
    >>> normalize_url(b'HtTP://[2001:DB8:85A3::0123%25En1]:80#\xed\xaf\xbf\xed\xbf\xbf',
    ...               norm_brief='er')
    b'http://[2001:db8:85a3::123]/#\xed\xaf\xbf\xed\xbf\xbf'
    >>> normalize_url(b'HtTP://[2001:DB8:85A3::0123%25En1]:80#\xed\xaf\xbf\xed\xbf\xbf',
    ...               norm_brief=['r', 'e'])
    b'http://[2001:db8:85a3::123]/#\xed\xaf\xbf\xed\xbf\xbf'
    >>> normalize_url(b'HtTP://[2001:DB8:85A3::0123%25En1]:80#\xed\xaf\xbf\xed\xbf\xbf',
    ...               norm_brief=iter(['r', 'e', 'm']))
    b'http://[2001:db8:85a3::123]/#\xf4\x8f\xbf\xbf'
    >>> normalize_url(b'HtTP://[2001:DB8:85A3::0123%25En1]:80#\xed\xaf\xbf\xed\xbf\xbf',
    ...               norm_brief='uer')
    'http://[2001:db8:85a3::123]/#\udbff\udfff'
    >>> normalize_url(b'HtTP://[2001:DB8:85A3::0123%25En1]:80#\xed\xaf\xbf\xed\xbf\xbf',
    ...               norm_brief='emru')
    'http://[2001:db8:85a3::123]/#\U0010ffff'

    >>> normalize_url(b'HtTP://[2001:DB8:85A3::0123%25En1]:80#\xed\xaf\xbf\xed\xbf\xbf',
    ...               unicode_str=True,
    ...               norm_brief='emru')
    Traceback (most recent call last):
      ...
    TypeError: when `norm_brief` is given, no other keyword arguments can be set to true

    >>> normalize_url(b'HtTP://[2001:DB8:85A3::0123%25En1]:80#\xed\xaf\xbf\xed\xbf\xbf',
    ...               norm_brief='ueMqrb')
    Traceback (most recent call last):
      ...
    ValueError: unknown flags in `norm_brief`: 'M', 'q', 'b'

    >>> normalize_url(b'HtTP://[2001:DB8:85A3::0123%25En1]:80#\xed\xaf\xbf\xed\xbf\xbf',
    ...               norm_brief='rueummur')
    Traceback (most recent call last):
      ...
    ValueError: duplicate flags in `norm_brief`: 'r', 'u', 'm'
    """
    if norm_brief is not None:
        if unicode_str or merge_surrogate_pairs or empty_path_slash or remove_ipv6_zone:
            raise TypeError(
                'when `norm_brief` is given, no other '
                'keyword arguments can be set to true')
        (unicode_str,
         merge_surrogate_pairs,
         empty_path_slash,
         remove_ipv6_zone) = _parse_norm_brief(norm_brief)

    if isinstance(url, bytearray):
        url = bytes(url)
    if unicode_str and isinstance(url, bytes):
        url = as_unicode(url, 'surrogatepass')
    if merge_surrogate_pairs:
        url = _merge_surrogate_pairs(url)
    scheme = _get_scheme(url)
    if scheme is None:
        # does not look like a URL at all
        # -> no normalization
        return url
    rest = url[len(scheme):]
    regex = (
        _AFTER_SCHEME_COMPONENTS_OF_URL_WITH_AUTHORITY_BYTES_REGEX if isinstance(url, bytes)
        else _AFTER_SCHEME_COMPONENTS_OF_URL_WITH_AUTHORITY_REGEX)
    match = regex.search(rest)
    if match is None:
        # probably a URL without the *authority* component
        # -> the only normalized component is *scheme*
        return scheme + rest
    before_host = _get_before_host(match)
    host = _get_host(match, remove_ipv6_zone)
    port = _get_port(match, scheme)
    path = _get_path(match, scheme, empty_path_slash)
    after_path = _get_after_path(match)
    return scheme + before_host + host + port + path + after_path


# *EXPERIMENTAL* (likely to be changed or removed in the future
# without any warning/deprecation/etc.)
def prepare_norm_brief(*,
                      unicode_str=False,
                      merge_surrogate_pairs=False,
                      empty_path_slash=False,
                      remove_ipv6_zone=False):
    r"""
    A convenience helper: prepare the `normalize_url()`'s `norm_brief`
    keyword argument value based on any other `normalize_url()`'s
    keyword-only arguments (see the docs of `normalize_url()`...).

    It is guaranteed that characters in the returned string are sorted
    and unique.

    >>> prepare_norm_brief()
    ''
    >>> prepare_norm_brief(unicode_str=True)
    'u'
    >>> prepare_norm_brief(remove_ipv6_zone=True, empty_path_slash=True)
    'er'
    >>> prepare_norm_brief(unicode_str=True, merge_surrogate_pairs=True, empty_path_slash=True)
    'emu'

    >>> raw_url = b'HtTP://[2001:DB8:85A3::0123%25En1]:80#\xed\xaf\xbf\xed\xbf\xbf'
    >>> a = normalize_url(
    ...     raw_url,
    ...     unicode_str=True,
    ...     merge_surrogate_pairs=True,
    ...     remove_ipv6_zone=True,
    ...     empty_path_slash=True)
    >>> my_norm_brief = prepare_norm_brief(
    ...     unicode_str=True,
    ...     merge_surrogate_pairs=True,
    ...     remove_ipv6_zone=True,
    ...     empty_path_slash=True)
    >>> b = normalize_url(raw_url, norm_brief=my_norm_brief)
    >>> a == b == 'http://[2001:db8:85a3::123]/#\U0010ffff'
    True
    >>> my_norm_brief
    'emru'
    """
    def gen():
        if unicode_str:
            yield 'u'
        if merge_surrogate_pairs:
            yield 'm'
        if empty_path_slash:
            yield 'e'
        if remove_ipv6_zone:
            yield 'r'
    norm_brief = ''.join(sorted(gen()))
    assert norm_brief == ''.join(sorted(frozenset(norm_brief)))  # sorted and unique
    return norm_brief


# *EXPERIMENTAL* (likely to be changed or removed in the future
# without any warning/deprecation/etc.)
def make_provisional_url_search_key(url_orig):
    r"""
    >>> mk = make_provisional_url_search_key
    >>> mk('http://\u0106ma.eXample.COM:80/\udcdd\ud800Ala-ma-kota\U0010FFFF\udccc')
    'SY:http://\u0106ma.example.com/\ufffdAla-ma-kota\ufffd'
    >>> mk('http://\u0106ma.eXample.COM:80/\ud800\udcddAla-ma-kota\U0010FFFF\udccc')
    'SY:http://\u0106ma.example.com/\ufffdAla-ma-kota\ufffd'
    >>> mk(b'HTTP://\xc4\x86ma.eXample.COM:/\xdd\xffAla-ma-kota\xf4\x8f\xbf\xbf\xcc')
    'SY:http://\u0106ma.example.com/\ufffdAla-ma-kota\ufffd'
    >>> mk(b'HTTP://\xc4\x86ma.eXample.COM/\xddAla-ma-kota\xf4\x8f\xbf\xbf\xed\xb3\x8c')
    'SY:http://\u0106ma.example.com/\ufffdAla-ma-kota\ufffd'
    >>> mk(b'HTTP://\xc4\x86ma.eXample.COM:/\xed\xa0\x80\xed\xb3\x9dAla-ma-kota\xef\xbf\xbd\xcc')
    'SY:http://\u0106ma.example.com/\ufffdAla-ma-kota\ufffd\ufffd'

    >>> mk('')
    Traceback (most recent call last):
      ...
    ValueError: given value is empty

    >>> mk(b'')
    Traceback (most recent call last):
      ...
    ValueError: given value is empty
    """
    if not isinstance(url_orig, (str, bytes, bytearray)):
        raise TypeError(f'{url_orig!a} is neither `str` nor `bytes`/`bytearray`')
    if not url_orig:
        raise ValueError('given value is empty')

    common_norm_options = dict(
        empty_path_slash=True,
        remove_ipv6_zone=True,
    )
    try:
        url_proc = normalize_url(
            url_orig,
            unicode_str=True,
            merge_surrogate_pairs=True,
            **common_norm_options)
    except UnicodeDecodeError:
        # here we have *neither* the strict UTF-8 encoding *nor*
        # a more "liberal" variant of it that allows surrogates
        # -> let's replace all non-compliant bytes with lone
        #    surrogates (considering that below they will be
        #    replaced with `REPLACEMENT CHARACTER` anyway...)
        url_proc = normalize_url(
            as_unicode(url_orig, 'surrogateescape'),
            **common_norm_options)

    # Let's get rid of surrogate and non-BMP code points -- because of:
    #
    # * the mess with the MariaDB's "utf8" 3-bytes encoding,
    #
    # * the mess with surrogates (including those produced by the
    #   `surrogateescape` error handler to "smuggle" non-compliant
    #   bytes, also those which could themselves represent a part
    #   of an already encoded surrogate...).
    #
    # Historically, we used to want to avoid also:
    #
    # * the mess with differences in handling of surrogates between
    #   Python versions (especially, 2.7 vs. modern 3.x),
    #
    # * the mess with UCS-2 vs. UCS-4 builds of Python 2.7.
    #
    # Every series of surrogate and/or non-BMP character code points is
    # replaced with exactly one `REPLACEMENT CHARACTER` (Unicode U+FFFD).
    url_proc = _SURROGATE_OR_NON_BMP_CHARACTERS_SEQ_REGEX.sub('\ufffd', url_proc)
    url_proc = limit_str(url_proc, char_limit=500)
    url_proc = PROVISIONAL_URL_SEARCH_KEY_PREFIX + url_proc

    assert isinstance(url_proc, str)
    return url_proc



#
# Non-public local constants
#

# (based, mainly, on RFC 3986 as well as RFCs: 1738, 3987, 6874 and 7230)
_AFTER_SCHEME_COMPONENTS_OF_URL_WITH_AUTHORITY_REGEX = re.compile(
    r'''
        \A
        (?P<before_host>
            ://
            (?:
                # user_info
                [^/?#@]+
                @
            )?
        )
        (?P<host>
            (?P<before_ipv6_addr>
                \[
            )
            (?P<ipv6_addr>
                (?P<ipv6_main_part>
                    [:0-9A-Fa-f]+
                )
                (?P<ipv6_suffix_in_ipv4_format>
                    (?<=
                        :
                    )
                    (?:
                        (?:
                            25[0-5]       # 250..255
                        |
                            2[0-4][0-9]   # 200..249
                        |
                            1[0-9][0-9]   # 100..199
                        |
                            [1-9]?[0-9]   # 0..99
                        )
                        (?:
                            \.            # dot
                            (?=           # followed by next octet...
                                [0-9]
                            )
                        |                 # or just nothing
                            (?=           # followed by character after address
                                [%\]]     # (see group `after_ipv6_addr` below)
                            )
                        )
                    ){4}
                )?
            )
            (?P<after_ipv6_addr>
                (?:
                    # IPv6 zone info
                    %
                    [^/?#\[\]]+
                )?
                \]
            )
        |
            (?P<hostname_or_ip>
                [^:/?#]+
            )
        )
        (?P<port>
            :
            [0-9]*
        )?
        (?P<path>
            /
            [^?#]*
        )?
        (?P<after_path>
            [?#]
            .*
        )?
        \Z
    ''', re.ASCII | re.VERBOSE)

_URL_SCHEME_AND_REST_BYTES_REGEX = re.compile(URL_SCHEME_AND_REST_REGEX.pattern.encode('ascii'))

_AFTER_SCHEME_COMPONENTS_OF_URL_WITH_AUTHORITY_BYTES_REGEX = re.compile(
    _AFTER_SCHEME_COMPONENTS_OF_URL_WITH_AUTHORITY_REGEX.pattern.encode('ascii'),
    re.VERBOSE)

_LAST_9_CHARS_OF_EXPLODED_IPV6_REGEX = re.compile(r'\A[0-9a-f]{4}:[0-9a-f]{4}\Z', re.ASCII)

# (intended to represent some -- hopefully reasonable -- heuristics...)
_INCOMPLETE_HTTP_URL_CANDIDATE_STARTING_WITH_HOST_REGEX = re.compile(
    r'''
        \A
        (?:
        # host
            # IPv6 candidate
            \[
                [:0-9A-Fa-f]+
                (?:
                    # optional IPv6 suffix in IPv4 format
                    (?<=
                        :
                    )
                    (?:
                        (?:
                            25[0-5]       # 250..255
                        |
                            2[0-4][0-9]   # 200..249
                        |
                            1[0-9][0-9]   # 100..199
                        |
                            [1-9]?[0-9]   # 0..99
                        )
                        (?:
                            \.            # dot
                            (?=           # followed by next octet...
                                [0-9]
                            )
                        |                 # or just nothing
                            (?=           # followed by character after address
                                [%\]]     # (first character or IPv6 zone info or closing ']')
                            )
                        )
                    ){4}
                )?
                (?:
                    # optional IPv6 zone info
                    %
                    [^/?#\[\]]+
                )?
            \]
        |
            # hostname or IPv4 in some form... (may include non-ASCII characters)
            (?:
                (?!
                    -
                )
                [^
                    \0-\054
                    \056-\057
                    \072-\100
                    \133-\140
                    \173-\177
                ]{1,300}
                (?<!
                    -
                )
                \.?
            ){2,}
        )
        (?:
        # port
            (?<!
                \.  # something like `example.com.:80` does not look like a good candidate
            )
            :
            \d{1,5}
        )?
        (?:
            [/?#]
            .*
        )?
        \Z
    ''', re.ASCII | re.VERBOSE)


_SURROGATE_OR_NON_BMP_CHARACTERS_SEQ_REGEX = re.compile('[^'
                                                        '\u0000-\ud7ff'
                                                        '\ue000-\uffff'
                                                        ']+')



#
# Non-public local helpers
#

def _parse_norm_brief(norm_brief):
    opt_seq = tuple(norm_brief)
    opts = dict.fromkeys(opt_seq, True)
    if len(opts) < len(opt_seq):
        duplicates = [opt for opt, n in collections.Counter(opt_seq).items() if n > 1]
        raise ValueError(
            f"duplicate flags in `norm_brief`: "
            f"{', '.join(map(ascii, duplicates))}")
    unicode_str = opts.pop('u', False)
    merge_surrogate_pairs = opts.pop('m', False)
    empty_path_slash = opts.pop('e', False)
    remove_ipv6_zone = opts.pop('r', False)
    if opts:
        raise ValueError(
            f"unknown flags in `norm_brief`: "
            f"{', '.join(map(ascii, opts))}")
    return unicode_str, merge_surrogate_pairs, empty_path_slash, remove_ipv6_zone


def _merge_surrogate_pairs(url):
    if isinstance(url, bytes):
        try:
            decoded = as_unicode(url, 'surrogatepass')
        except UnicodeDecodeError:
            # here we have *neither* the strict UTF-8 encoding *nor*
            # a more "liberal" variant of it that allows surrogates
            # -> let's return the given `url` intact
            pass
        else:
            # let's ensure that representation of non-BMP characters is
            # consistent (note: any unpaired surrogates are left intact)
            with_surrogate_pairs_merged = replace_surrogate_pairs_with_proper_codepoints(decoded)
            url = as_bytes(with_surrogate_pairs_merged, 'surrogatepass')
        assert isinstance(url, bytes)
    else:
        # let's ensure that representation of non-BMP characters is
        # consistent (note: any unpaired surrogates are left intact)
        url = replace_surrogate_pairs_with_proper_codepoints(url)
        assert isinstance(url, str)
    return url


def _get_scheme(url):
    r = _URL_SCHEME_AND_REST_BYTES_REGEX if isinstance(url, bytes) else URL_SCHEME_AND_REST_REGEX
    simple_match = r.search(url)
    if simple_match is None:
        return None
    scheme = simple_match.group('scheme')
    assert scheme and scheme.isascii()
    scheme = scheme.lower()
    return scheme


def _get_before_host(match):
    before_host = match.group('before_host')
    assert before_host
    return before_host


def _get_host(match, remove_ipv6_zone):
    assert match.group('host')
    if match.group('ipv6_addr'):
        before_ipv6_addr = _get_before_ipv6_addr(match)
        ipv6_addr = _get_ipv6_addr(match)
        after_ipv6_addr = _get_after_ipv6_addr(match, remove_ipv6_zone)
        host = before_ipv6_addr + ipv6_addr + after_ipv6_addr
    else:
        host = _get_hostname_or_ip(match)
    return host


def _get_before_ipv6_addr(match):
    before_ipv6_addr = match.group('before_ipv6_addr')
    assert before_ipv6_addr == _proper_conv(match)('[')
    return before_ipv6_addr


def _get_ipv6_addr(match):
    conv = _proper_conv(match)
    ipv6_main_part = match.group('ipv6_main_part')
    assert ipv6_main_part
    ipv6_suffix_in_ipv4_format = match.group('ipv6_suffix_in_ipv4_format')
    try:
        if ipv6_suffix_in_ipv4_format:
            assert ipv6_main_part.endswith(conv(':'))
            ipv6_suffix = _convert_ipv4_to_ipv6_suffix(ipv6_suffix_in_ipv4_format)
        else:
            assert ipv6_main_part == match.group('ipv6_addr')
            ipv6_suffix = ''
        ipv6_main_part = as_unicode(ipv6_main_part, 'surrogatepass')
        ipv6_addr = ipaddress.IPv6Address(ipv6_main_part + ipv6_suffix).compressed
        ipv6_addr = conv(ipv6_addr)
    except ipaddress.AddressValueError:
        ipv6_addr = match.group('ipv6_addr')
    assert ipv6_addr.isascii()
    return ipv6_addr


def _convert_ipv4_to_ipv6_suffix(ipv6_suffix_in_ipv4_format):
    """
    >>> _convert_ipv4_to_ipv6_suffix('192.168.0.1')
    'c0a8:0001'
    >>> _convert_ipv4_to_ipv6_suffix(b'192.168.0.1')
    'c0a8:0001'
    """
    ipv6_suffix_in_ipv4_format = as_unicode(ipv6_suffix_in_ipv4_format, 'surrogatepass')
    as_ipv4 = ipaddress.IPv4Address(ipv6_suffix_in_ipv4_format)
    as_int = int(as_ipv4)
    as_ipv6 = ipaddress.IPv6Address(as_int)
    ipv6_suffix = as_ipv6.exploded[-9:]
    assert _LAST_9_CHARS_OF_EXPLODED_IPV6_REGEX.search(ipv6_suffix)
    return ipv6_suffix


def _get_after_ipv6_addr(match, remove_ipv6_zone):
    after_ipv6_addr = match.group('after_ipv6_addr')
    closing_bracket = _proper_conv(match)(']')
    assert after_ipv6_addr and after_ipv6_addr.endswith(closing_bracket)
    if remove_ipv6_zone:
        return closing_bracket
    if after_ipv6_addr.isascii():
        return after_ipv6_addr.lower()
    return after_ipv6_addr


def _get_hostname_or_ip(match):
    hostname_or_ip = match.group('hostname_or_ip')
    assert hostname_or_ip
    sep_regex = (DOMAIN_LABEL_SEPARATOR_UTF8_BYTES_REGEX if isinstance(hostname_or_ip, bytes)
                 else DOMAIN_LABEL_SEPARATOR_REGEX)
    dot = _proper_conv(match)('.')
    return dot.join(
        (label.lower() if label.isascii()  # we do not want to touch non-pure-ASCII labels
         else label)
        for label in sep_regex.split(hostname_or_ip))


def _get_port(match, scheme):
    scheme_key = as_unicode(scheme, 'surrogatepass')
    conv = _proper_conv(match)
    port = match.group('port')
    if (port is None
          or port == conv(':')
          or port == conv(':{}'.format(URL_SCHEME_TO_DEFAULT_PORT.get(scheme_key)))):
        port = conv('')
    return port


def _get_path(match, scheme, empty_path_slash):
    conv = _proper_conv(match)
    path = match.group('path') or conv('')
    if (empty_path_slash
          and as_bytes(scheme) in (b'http', b'https', b'ftp')
          and not path):
        path = conv('/')
    return path


def _get_after_path(match):
    return match.group('after_path') or _proper_conv(match)('')


def _proper_conv(match):
    return (
        as_bytes if isinstance(match.group(0), bytes)
        else lambda part: as_unicode(part, 'surrogatepass'))


if __name__ == "__main__":
    import doctest
    doctest.testmod()
