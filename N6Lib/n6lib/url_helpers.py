# -*- coding: utf-8 -*-

# Copyright (c) 2019 NASK. All rights reserved.

import re

import ipaddr

from n6lib.common_helpers import (
    is_pure_ascii,
    limit_string,
    lower_if_pure_ascii,
)



#
# Public constants
#

# (based on RFCs 3986 and 3987)
URL_SCHEME_AND_REST_REGEX = re.compile(r'\A'
                                       r'(?P<scheme>[a-zA-Z][\-+.0-9a-zA-Z]*)'
                                       r'(?P<rest>:.*)')

# (similar to `URL_SCHEME_AND_REST_REGEX`, but slightly less strict;
# used -- among others -- in n6lib.record_dict.RecordDict.adjust_url;
# NOTE: typically, it should *not* be used in a new code;
# instead of it, use `URL_SCHEME_AND_REST_REGEX` defined above!)
URL_SCHEME_AND_REST_LEGACY_REGEX = re.compile(r'\A'
                                              r'(?P<scheme>[\-+.0-9a-zA-Z]+)'
                                              r'(?P<rest>:.*)')

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
DOMAIN_LABEL_SEPARATOR_UNICODE_REGEX = re.compile(u'[.\u3002\uff0e\uff61]')
DOMAIN_LABEL_SEPARATOR_UTF8_BYTES_REGEX = re.compile(r'(?:'
                                                     r'\.'
                                                     r'|'
                                                     r'\343\200\202'
                                                     r'|'
                                                     r'\357\274\216'
                                                     r'|'
                                                     r'\357\275\241'
                                                     r')')


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
    separated with a colon from the rest of the string.

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
    Try to guess (using some heuristics) whether the given string may
    be an incomplete HTTP URL starting with the host part, i.e., an
    HTTP URL unprovided with the `http://` prefix.
    """
    return bool(_INCOMPLETE_HTTP_URL_CANDIDATE_STARTING_WITH_HOST_REGEX.search(s))


# TODO: more tests...
def normalize_url(url,
                  transcode1st=False,
                  epslash=False,
                  rmzone=False):
    r"""
    Apply to the given string as much of the basic URL/IRI normalization
    as possible, provided that no semantic changes are made (i.e., the
    intent is that the resultant URL/IRI is semantically equivalent to
    the given one).

    Args (required):
        `url` (str or unicode):
            The URL (or URI, or IRI) to be normalized.

    Kwargs (optional):
        `transcode1st` (bool; default: False):
            Whether, before the actual URL normalization (see the
            description in the steps 1-18 below...), the given `url`
            should be:
            * if given as a str instance: decoded using the 'utf-8'
              codec with the 'surrogateescape' error handler, and
            * otherwise (assuming a unicode instance): encoded using
              the 'utf-8' codec and then decoded using the 'utf-8'
              codec (to ensure that representation of non-BMP
              characters is consistent...).
        `epslash` (bool; default: False):
            Whether the *path* component of the given URL should be
            replaced with `/` if the `url`'s *scheme* is `http`, `https`
            or `ftp` *and* the *path* is empty (not that, generally,
            this normalization step does not change the URL semantics,
            with the exception of an URL being the request target of an
            `OPTIONS` HTTP request; see RFC 7230, section 2.7.3).
        `rmzone` (bool; default: False):
            Whether the IPv6 zone identifier being a part of an IPv6
            address in the `url`'s *host* component should be removed
            (note that, generally, IPv6 zone identifier has no meaning
            outside the local system it is related to; see RFC 6874,
            section 1).

    Raises:
        `TypeError` if `url` is not a str or unicode instance.

    The algorithm of normalization consists of the following steps [the
    `+` operator in this description means *string concatenation*]:

    0. Optional `url` transcoding (see the above description of the
       `transcode1st` argument).

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

    9. If `ipv6 zone` is *not* present, or the `rmzone` argument is
       true, then set `ipv6 zone` to an empty string and skip to step
       11; otherwise proceed to step 10.

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

    16. If the `epslash` argument is true and `scheme` is one of:
        "http", "https", "ftp" -- then set `path` to "/"; otherwise
        set `path` to an empty string.

    17. If `after path` is *not* present then set it to an empty
        string.

    18. Stop here -- returning `before host` + `host` + `port` +
        `path` + `after path`.


    Ad 0:

    >>> normalize_url('\xf4\x8f\xbf\xbf')
    '\xf4\x8f\xbf\xbf'
    >>> normalize_url('\xf4\x8f\xbf\xbf', transcode1st=True)
    u'\U0010ffff'
    >>> normalize_url(u'\udbff\udfff')  # look at this!
    u'\udbff\udfff'
    >>> normalize_url(u'\udbff\udfff', transcode1st=True)
    u'\U0010ffff'
    >>> normalize_url(u'\U0010ffff')
    u'\U0010ffff'
    >>> normalize_url(u'\U0010ffff', transcode1st=True)
    u'\U0010ffff'


    Ad 0-2:

    >>> normalize_url('Blabla-bla!@#$ %^&\xc4\x85\xcc')
    'Blabla-bla!@#$ %^&\xc4\x85\xcc'
    >>> normalize_url('Blabla-bla!@#$ %^&\xc4\x85\xcc', transcode1st=True)
    u'Blabla-bla!@#$ %^&\u0105\udccc'
    >>> normalize_url(u'Blabla-bla!@#$ %^&\u0105\udccc')
    u'Blabla-bla!@#$ %^&\u0105\udccc'


    Ad 0-1 + 3 + 5:

    >>> normalize_url('SOME-scheme:Blabla-bla!@#$ %^&\xc4\x85\xcc')
    'some-scheme:Blabla-bla!@#$ %^&\xc4\x85\xcc'
    >>> normalize_url('SOME-scheme:Blabla-bla!@#$ %^&\xc4\x85\xcc', transcode1st=True)
    u'some-scheme:Blabla-bla!@#$ %^&\u0105\udccc'
    >>> normalize_url(u'somE-sCHEmE:Blabla-bla!@#$ %^&\u0105\udccc')
    u'some-scheme:Blabla-bla!@#$ %^&\u0105\udccc'


    Ad 0-1 + 3-4 + 6-11 + 14-18:

    >>> normalize_url('HtTP://[2001:0DB8:85A3:0000:0000:8A2E:0370:7334]')
    'http://[2001:db8:85a3::8a2e:370:7334]'
    >>> normalize_url('HtTP://[2001:0DB8:85A3:0000:0000:8A2E:0370:7334FAB]')
    'http://[2001:0DB8:85A3:0000:0000:8A2E:0370:7334FAB]'
    >>> normalize_url('HtTP://[2001:0DB8:85A3:0000:0000:8A2E:3.112.115.52%25en1]')
    'http://[2001:db8:85a3::8a2e:370:7334%25en1]'
    >>> normalize_url('HtTP://[2001:0DB8:85A3::8A2E:0370:7334]/fooBAR',
    ...               epslash=True)
    'http://[2001:db8:85a3::8a2e:370:7334]/fooBAR'
    >>> normalize_url('HtTP://[2001:0DB8:85A3:0000:0000:8A2E:3.112.115.52]:80')
    'http://[2001:db8:85a3::8a2e:370:7334]'
    >>> normalize_url('HtTP://[2001:0DB8:85A3:0000:0000:8A2E:0370:7334%25en1]:80',
    ...               epslash=True)
    'http://[2001:db8:85a3::8a2e:370:7334%25en1]/'
    >>> normalize_url('HtTP://[2001:DB8:85A3::8A2E:3.112.115.52]',
    ...               rmzone=True)
    'http://[2001:db8:85a3::8a2e:370:7334]'
    >>> normalize_url('HtTP://[2001:0db8:85a3:0000:0000:8a2e:0370:7334%25EN1]',
    ...               rmzone=True)
    'http://[2001:db8:85a3::8a2e:370:7334]'
    >>> normalize_url('HtTP://[2001:0DB8:85A3:0000:0000:8A2E:3.112.115.52%25en1]',
    ...               rmzone=True, epslash=True)
    'http://[2001:db8:85a3::8a2e:370:7334]/'
    >>> normalize_url('HtTP://[2001:0DB8:85A3::8A2E:0370:7334%25en1]:80',
    ...               rmzone=True)
    'http://[2001:db8:85a3::8a2e:370:7334]'
    >>> normalize_url('HtTP://[2001:DB8:85A3:0000:0000:8A2E:3.112.115.52%25en1]:80',
    ...               rmzone=True, epslash=True)
    'http://[2001:db8:85a3::8a2e:370:7334]/'
    >>> normalize_url(u'HtTP://[2001:0DB8:85A3:0000:0000:8A2E:3.112.115.52]')
    u'http://[2001:db8:85a3::8a2e:370:7334]'
    >>> normalize_url(u'HtTP://[2001:0db8:85a3::8a2e:370:7334%25EN1]')
    u'http://[2001:db8:85a3::8a2e:370:7334%25en1]'
    >>> normalize_url(u'HtTP://[2001:0DB8:85A3:0000:0000:8A2E:0370:7334FAB%25eN1]',
    ...               epslash=True)
    u'http://[2001:0DB8:85A3:0000:0000:8A2E:0370:7334FAB%25en1]/'
    >>> normalize_url(u'HtTP://[2001:0DB8:85A3:0000:0000:8a2e:3.112.115.52]',
    ...               epslash=True)
    u'http://[2001:db8:85a3::8a2e:370:7334]/'
    >>> normalize_url(u'HtTP://[2001:0DB8:85A3:0000:0000:8A2E:0370:7334]:80')
    u'http://[2001:db8:85a3::8a2e:370:7334]'
    >>> normalize_url(u'HtTP://[2001:0DB8:85A3::8A2E:3.112.115.52%25en1]:80',
    ...               epslash=True)
    u'http://[2001:db8:85a3::8a2e:370:7334%25en1]/'
    >>> normalize_url(u'HtTP://[2001:db8:85a3:0000:0000:8A2E:0370:7334]',
    ...               rmzone=True)
    u'http://[2001:db8:85a3::8a2e:370:7334]'
    >>> normalize_url(u'HtTP://[2001:0DB8:85A3:0000:0000:8A2E:3.112.115.52%25en1]/fooBAR',
    ...               rmzone=True)
    u'http://[2001:db8:85a3::8a2e:370:7334]/fooBAR'
    >>> normalize_url(u'HtTP://[2001:0DB8:85A3::8A2E:0370:7334%25en1]',
    ...               rmzone=True, epslash=True)
    u'http://[2001:db8:85a3::8a2e:370:7334]/'
    >>> normalize_url(u'HtTP://[2001:0DB8:85A3:0000:0000:8A2E:3.112.115.52%25en1]:80',
    ...               rmzone=True)
    u'http://[2001:db8:85a3::8a2e:370:7334]'
    >>> normalize_url(u'HtTP://[2001:0DB8:85A3:0000:0000:8A2E:0370:7334%25en1]:80',
    ...               rmzone=True, epslash=True)
    u'http://[2001:db8:85a3::8a2e:370:7334]/'
    >>> normalize_url('HtTPS://[2001:DB8:85A3:0000:0000:8A2E:3.112.115.52%25En1]:80')
    'https://[2001:db8:85a3::8a2e:370:7334%25en1]:80'
    >>> normalize_url('HtTPS://[2001:DB8:85A3:0000:0000:8A2E:3.112.115.52%25en1]:80',
    ...               rmzone=True)
    'https://[2001:db8:85a3::8a2e:370:7334]:80'
    >>> normalize_url('HtTPS://[2001:0db8:85a3::8a2E:3.112.115.52%25en1]:443',
    ...               rmzone=True)
    'https://[2001:db8:85a3::8a2e:370:7334]'
    >>> normalize_url('HtTPS://[2001:DB8:85A3:0000:0000:8A2E:0370:7334%25eN\xc4\x851]:80',
    ...               epslash=True)
    'https://[2001:db8:85a3::8a2e:370:7334%25eN\xc4\x851]:80/'
    >>> normalize_url(u'HtTPS://[2001:0db8:85a3::8a2E:3.112.115.52%25En1]:443')
    u'https://[2001:db8:85a3::8a2e:370:7334%25en1]'
    >>> normalize_url(u'HtTPS://[2001:0DB8:85A3:0000:0000:8A2E:3.112.115.52%25eN\xc4\x851]:443',
    ...               epslash=True)
    u'https://[2001:db8:85a3::8a2e:370:7334%25eN\xc4\x851]/'
    >>> normalize_url(u'HtTPS://[2001:0DB8:85A3::8A2E:0370:7334%25eN1]:80',
    ...               rmzone=True, epslash=True)
    u'https://[2001:db8:85a3::8a2e:370:7334]:80/'
    >>> normalize_url(u'HtTPS://[2001:0DB8:85A3::8A2E:370:7334%25eN1]:443',
    ...               rmzone=True, epslash=True)
    u'https://[2001:db8:85a3::8a2e:370:7334]/'


    Ad 0-1 + 3-4 + 12-18:

    >>> normalize_url('HTTP://WWW.XyZ-\xc4\x85\xcc.eXamplE.com', epslash=True)
    'http://www.XyZ-\xc4\x85\xcc.example.com/'
    >>> normalize_url('HTTP://WWW.XyZ-\xc4\x85\xcc.eXamplE.com', transcode1st=True)
    u'http://www.XyZ-\u0105\udccc.example.com'
    >>> normalize_url('HTTP://WWW.XyZ-\xc4\x85.eXamplE.com:80/fooBAR')
    'http://www.XyZ-\xc4\x85.example.com/fooBAR'
    >>> normalize_url('HtTP://WWW.XyZ-\xc4\x85.eXamplE.com:80', epslash=True)
    'http://www.XyZ-\xc4\x85.example.com/'
    >>> normalize_url('HtTP://WWW.XyZ-\xc4\x85.eXamplE.com:80/fooBAR', epslash=True)
    'http://www.XyZ-\xc4\x85.example.com/fooBAR'
    >>> normalize_url('HTTP://WWW.XyZ-\xc4\x85\xcc.eXamplE.com', transcode1st=True)
    u'http://www.XyZ-\u0105\udccc.example.com'
    >>> normalize_url(u'HTtp://WWW.XyZ-\u0105\udccc.eXamplE.com:80')
    u'http://www.XyZ-\u0105\udccc.example.com'
    >>> normalize_url(u'HTtp://WWW.XyZ-\u0105.eXamplE.com:80/')
    u'http://www.XyZ-\u0105.example.com/'
    >>> normalize_url(u'hTTP://WWW.XyZ-\u0105.eXamplE.com:80', epslash=True)
    u'http://www.XyZ-\u0105.example.com/'
    >>> normalize_url('HTTPS://WWW.XyZ-\xc4\x85.eXamplE.com:80')
    'https://www.XyZ-\xc4\x85.example.com:80'
    >>> normalize_url('HTTPS://WWW.XyZ-\xc4\x85.eXamplE.com:80/fooBAR')
    'https://www.XyZ-\xc4\x85.example.com:80/fooBAR'
    >>> normalize_url('HTTPs://WWW.XyZ-\xc4\x85.eXamplE.com:443', epslash=True)
    'https://www.XyZ-\xc4\x85.example.com/'
    >>> normalize_url('HTTPs://WWW.XyZ-\xc4\x85.eXamplE.com:443', epslash=True, transcode1st=True)
    u'https://www.XyZ-\u0105.example.com/'
    >>> normalize_url(u'httpS://WWW.XyZ-\u0105.eXamplE.com:80', epslash=True)
    u'https://www.XyZ-\u0105.example.com:80/'
    >>> normalize_url(u'httpS://WWW.XyZ-\u0105.eXamplE.com:80/fooBAR', epslash=True)
    u'https://www.XyZ-\u0105.example.com:80/fooBAR'
    >>> normalize_url(u'hTtpS://WWW.XyZ-\u0105.eXamplE.com:443')
    u'https://www.XyZ-\u0105.example.com'
    >>> normalize_url(u'httpS://WWW.XyZ-\u0105.eXamplE.com:80/fooBAR', epslash=True,
    ...               transcode1st=True)
    u'https://www.XyZ-\u0105.example.com:80/fooBAR'
    """
    if transcode1st:
        url = _transcode(url)
    scheme = _get_scheme(url)
    if scheme is None:
        # does not look like a URL at all
        # -> no normalization
        return url
    rest = url[len(scheme):]
    match = _AFTER_SCHEME_COMPONENTS_OF_URL_WITH_AUTHORITY_REGEX.search(rest)
    if match is None:
        # probably a URL without the *authority* component
        # -> the only normalized component is *scheme*
        return scheme + rest
    before_host = _get_before_host(match)
    host = _get_host(match, rmzone)
    port = _get_port(match, scheme)
    path = _get_path(match, scheme, epslash)
    after_path = _get_after_path(match)
    return scheme + before_host + host + port + path + after_path


# *EXPERIMENTAL* (likely to be changed or removed in the future
# without any warning/deprecation/etc.)
def make_provisional_url_search_key(url_orig):
    r"""
    >>> mk = make_provisional_url_search_key
    >>> mk(u'http://\u0106ma.eXample.COM:80/\udcdd\ud800Ala-ma-kota\U0010FFFF\udccc')
    u'SY:http://\u0106ma.example.com/\ufffdAla-ma-kota\ufffd'
    >>> mk('HTTP://\xc4\x86ma.eXample.COM:/\xdd\xffAla-ma-kota\xf4\x8f\xbf\xbf\xcc')
    u'SY:http://\u0106ma.example.com/\ufffdAla-ma-kota\ufffd'
    >>> mk('HTTP://\xc4\x86ma.eXample.COM/\xddAla-ma-kota\xf4\x8f\xbf\xbf\xed\xb3\x8c')
    u'SY:http://\u0106ma.example.com/\ufffdAla-ma-kota\ufffd'
    """
    if not isinstance(url_orig, basestring):
        raise TypeError('{!r} is neither `str` nor `unicode`'.format(url_orig))
    if not url_orig:
        raise ValueError('given string is empty')
    url_proc = url_orig
    url_proc = normalize_url(url_proc, transcode1st=True, epslash=True, rmzone=True)
    assert isinstance(url_proc, unicode)
    # (let's get rid of surrogates and non-BMP characters -- because of
    # the mess with MariaDB's "utf-8" 3-bytes encoding as well as with
    # UTC-2 vs. UTC-4 Python builds...)
    url_proc = _SURROGATE_OR_NON_BMP_CHARACTERS_SEQ_REGEX.sub(u'\ufffd', url_proc)
    url_proc = limit_string(url_proc, char_limit=500)
    url_proc = PROVISIONAL_URL_SEARCH_KEY_PREFIX + url_proc
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
    ''', re.VERBOSE)

_LAST_9_CHARS_OF_EXPLODED_IPV6_REGEX = re.compile(r'\A[0-9a-f]{4}:[0-9a-f]{4}\Z')

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
    ''', re.VERBOSE)


_SURROGATE_OR_NON_BMP_CHARACTERS_SEQ_REGEX = re.compile(u'[^'
                                                        u'\u0000-\ud7ff'
                                                        u'\ue000-\uffff'
                                                        u']+')



#
# Non-public local helpers
#

def _transcode(url):
    if isinstance(url, str):
        url = url.decode('utf-8', 'surrogateescape')
    else:
        # to ensure that representation of non-BMP characters is consistent
        url = url.encode('utf-8').decode('utf-8')
    return url


def _get_scheme(url):
    simple_match = URL_SCHEME_AND_REST_REGEX.search(url)
    if simple_match is None:
        return None
    scheme = simple_match.group('scheme')
    assert scheme and is_pure_ascii(scheme)
    scheme = scheme.lower()
    return scheme


def _get_before_host(match):
    before_host = match.group('before_host')
    assert before_host
    return before_host


def _get_host(match, rmzone):
    assert match.group('host')
    if match.group('ipv6_addr'):
        before_ipv6_addr = _get_before_ipv6_addr(match)
        ipv6_addr = _get_ipv6_addr(match)
        after_ipv6_addr = _get_after_ipv6_addr(match, rmzone)
        host = before_ipv6_addr + ipv6_addr + after_ipv6_addr
    else:
        host = _get_hostname_or_ip(match)
    return host


def _get_before_ipv6_addr(match):
    before_ipv6_addr = match.group('before_ipv6_addr')
    assert before_ipv6_addr == '['
    return before_ipv6_addr


def _get_ipv6_addr(match):
    ipv6_main_part = match.group('ipv6_main_part')
    assert ipv6_main_part
    ipv6_suffix_in_ipv4_format = match.group('ipv6_suffix_in_ipv4_format')
    try:
        if ipv6_suffix_in_ipv4_format:
            assert ipv6_main_part.endswith(':')
            ipv6_suffix = _convert_ipv4_to_ipv6_suffix(ipv6_suffix_in_ipv4_format)
        else:
            assert ipv6_main_part == match.group('ipv6_addr')
            ipv6_suffix = ''
        ipv6_addr = ipaddr.IPv6Address(ipv6_main_part + ipv6_suffix).compressed
    except ipaddr.AddressValueError:
        ipv6_addr = match.group('ipv6_addr')
    assert is_pure_ascii(ipv6_addr)
    return ipv6_addr


def _convert_ipv4_to_ipv6_suffix(ipv6_suffix_in_ipv4_format):
    """
    >>> _convert_ipv4_to_ipv6_suffix('192.168.0.1')
    'c0a8:0001'
    """
    as_ipv4 = ipaddr.IPv4Address(ipv6_suffix_in_ipv4_format)
    as_int = int(as_ipv4)
    as_ipv6 = ipaddr.IPv6Address(as_int)
    ipv6_suffix = as_ipv6.exploded[-9:]
    assert _LAST_9_CHARS_OF_EXPLODED_IPV6_REGEX.search(ipv6_suffix)
    return ipv6_suffix


def _get_after_ipv6_addr(match, rmzone):
    after_ipv6_addr = match.group('after_ipv6_addr')
    assert after_ipv6_addr and after_ipv6_addr.endswith(']')
    if rmzone:
        return ']'
    return lower_if_pure_ascii(after_ipv6_addr)


def _get_hostname_or_ip(match):
    hostname_or_ip = match.group('hostname_or_ip')
    assert hostname_or_ip
    sep_regex = (DOMAIN_LABEL_SEPARATOR_UTF8_BYTES_REGEX if isinstance(hostname_or_ip, str)
                 else DOMAIN_LABEL_SEPARATOR_UNICODE_REGEX)
    return '.'.join(lower_if_pure_ascii(label)  # <- we do not want to touch non-pure-ASCII labels
                    for label in sep_regex.split(hostname_or_ip))


def _get_port(match, scheme):
    port = match.group('port')
    if (port is None
          or port == ':'
          or port == ':{}'.format(URL_SCHEME_TO_DEFAULT_PORT.get(scheme))):
        port = ''
    return port


def _get_path(match, scheme, epslash):
    path = match.group('path') or ''
    if (epslash
          and scheme in ('http', 'https', 'ftp')
          and not path):
        path = '/'
    return path


def _get_after_path(match):
    return match.group('after_path') or ''


if __name__ == "__main__":
    import doctest
    doctest.testmod()
