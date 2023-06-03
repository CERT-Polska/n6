# Copyright (c) 2013-2023 NASK. All rights reserved.

import dataclasses
import datetime
import re
from collections.abc import (
    Callable,
    Mapping,
    Sequence,
    Set,
)
from typing import (
    Optional,
    Union,
)

from n6lib.mail_parsing_helpers import (
    Content,
    ExtractFrom,
)


#
# Keys used in tests and test data to distinguish e-mail message cases
#

TEST_MSG_KEYS = [
    'SIMPLE',
    'STRANGE',
    'SHORTENED',
    'QUITE-COMPLEX',
    'WITH-BROKEN-BOUNDARY',
    'WITH-DEFECTIVE-BASE64-CTE',
]


#
# Actual test data: raw messages to be parsed by `ParsedEmailMessage.from_...()`
#

RAW_MSG_SOURCE = dict()


RAW_MSG_SOURCE['SIMPLE'] = (
b'''Date: Sun, 28 May 2023 07:08:09 -0000
From: Cardinal Biggles <nobody.expects@example.pl>
To: whoever@example.net
Organization: The Spanish Inquisition
Subject: A simple message

I confess!
I confess!!
I confess!!!
'''.replace(b'\n', b'\r\n'))


RAW_MSG_SOURCE['STRANGE'] = (
# Note: `\n` (instead of `\r\n`) as line endings.
b'''to:     somebody@example.org
date:Wed, 28 May 2023 07:08:09 -0130
From:Cardinal Biggles <nobody.expects@example.pl>

Cut text''')


RAW_MSG_SOURCE['SHORTENED'] = (
b'''from: nobody.expects@example.pl
to: somebody@example.org'''.replace(b'\n', b'\r\n'))


RAW_MSG_SOURCE['QUITE-COMPLEX'] = (
b'''Return-Path: <nobody.expects@example.pl>
Received: from krasoola.example.pl (xyz.example.pl [203.0.113.91])
\tby whatahost.example.net  with ESMTP id q87GKi62gsd800\x20\x20\x20
\tfor <whoever@example.com>; Mon, 29 May 2023 16:05:21 +0200 (CEST)
Date: Mon, 29 May 2023 16:05:19 +0200
From: "Cardinal Biggles" <nobody.expects@example.pl>
To: "Whoever"
  <whoever@example.net>
Subject:  \t =?ISO-8859-2?B?U2ll5g==?=    \t    relacji\t\x20
Message-ID: <20230529160519.12345678@krasoola.example.pl>
Organization: Naukowa i Akademicka =?ISO-8859-2?B?U2ll5g==?= Komputerowa
X-Mailer: Claws Mail 3.8.1 (raczej stary)
Mime-Version: 1.0
Content-Type: Multipart/Mixed; boundary="MP_/kobylaMaMalyBok01234567"
X-Bogosity: \t\x20\t\tNo, \t tests=bogofilter, \t\x20\t\t
   spamicity=0.0021, version=33.22.11\t\x20

--MP_/kobylaMaMalyBok01234567
Content-Type: text/plain; charset=ISO-8859-2
Content-Transfer-Encoding: quoted-printable
Content-Disposition: inline

Tu jest jaka=B6 sobie tre=B6=E6.
Tralala.

--MP_/kobylaMaMalyBok01234567
Content-Type: application/octet-stream; name=pickled_datetime.bin
Content-Transfer-Encoding: base64
Content-Disposition: attachment; filename=pickled_datetime.bin

gASVMwAAAAAAAAB9lIwDbm93lIwIZGF0ZXRpbWWUjAhkYXRldGltZZSTlEMKB+YIGQ8ILwwFYpSF
lFKUcy4=

--MP_/kobylaMaMalyBok01234567
Content-Type: application/zip
Content-Transfer-Encoding: base64
Content-Disposition: attachment; filename=test.compressed-you-now

UEsDBBQAAAAIAPFbsEKYXqpGLwAAADYAAAAMABwAbjYvLmhnaWdub3JlVVQJAAN1p5RReaeUUXV4
CwABBOgDAAAE6AMAACuuzCtJrLBSSM/JT+Li0tIrqEzm0isoys9KTS4BMipTUsvgvOLUkpLMvPRi
Li4AUEsDBAoAAAAAAN18r0I8JokxBAAAAAQAAAAJABwAbjYvUkVBRE1FVVQJAAPxj5NRKp+TUXV4
CwABBOgDAAAE6AMAAG42LgpQSwECHgMUAAAACADxW7BCmF6qRi8AAAA2AAAADAAYAAAAAAABAAAA
pIEAAAAAbjYvLmhnaWdub3JlVVQFAAN1p5RRdXgLAAEE6AMAAAToAwAAUEsBAh4DCgAAAAAA3Xyv
QjwmiTEEAAAABAAAAAkAGAAAAAAAAQAAAKSBdQAAAG42L1JFQURNRVVUBQAD8Y+TUXV4CwABBOgD
AAAE6AMAAFBLBQYAAAAAAgACAKEAAAC8AAAAAAA=

--MP_/kobylaMaMalyBok01234567
Content-Type: Application/Octet-Stream; name=README
Content-Transfer-Encoding: base64
Content-Disposition: attachment

bjYuCg==

--MP_/kobylaMaMalyBok01234567
Content-Type: Text/X-Python
Content-Transfer-Encoding: 7bit
Content-Disposition: attachment

print('Hello world!')
print("I printed ''Hello world!'!")

--MP_/kobylaMaMalyBok01234567
Content-Type: application/x-bzip2
Content-Transfer-Encoding: base64
Content-Disposition: attachment; filename="README.bz2/"

QlpoOTFBWSZTWXj/p3AAAAHZAAAQAAEBAAABIAAhmmgzTQy8XckU4UJB4/6dwA==

--MP_/kobylaMaMalyBok01234567
Content-Type: message/rfc822
Content-Disposition: attachment

Return-Path: <nobody.expects@example.pl>
Received: from some-proxy.example.pl (LHLO some-proxy.example.pl)
 (198.51.100.98) by mailbox.example.pl with LMTP; Sat, 8 Apr 2023
 15:32:42 +0200 (CEST)
Received: from localhost (localhost [127.0.0.1])
\tby some-proxy.example.pl (Postfix) with ESMTP id ABCD1234;
\tSat,  8 Apr 2023 15:32:42 +0200 (CEST)
Date: Sat, 8 Apr 2023 15:32:42 +0200 (CEST)
From: Cardinal Biggles <nobody.expects@example.pl>
To: Cardinal Biggles <nobody.expects@example.pl>
Cc: =?utf-8?B?S3RvxZs=?= Inny <who@example.com>
Message-ID: <01.02.03.SpammishInquisition.foo@example.pl>
Subject: =?utf-8?Q?Fwd:_Za=C5=82=C4=85cznik?=
MIME-Version: 1.0
Content-Type: multipart/mixed;\x20
\tboundary="----=_Part_12345678_098765432.1234567890987"
X-Originating-IP: [10.20.30.40]

------=_Part_12345678_098765432.1234567890987
Content-Type: multipart/alternative;\x20
\tboundary="=_72022f91-b495-4ca5-bcbf-5ce51b021d03"

--=_72022f91-b495-4ca5-bcbf-5ce51b021d03
Content-Type: Text/Plain; charset=utf-8
Content-Transfer-Encoding: 8bit

Za\xc5\x82\xc4\x85czam za\xc5\x82\xc4\x85czone...

--=_72022f91-b495-4ca5-bcbf-5ce51b021d03
Content-Type: Text/HTML; charset=utf-8
Content-Transfer-Encoding: quoted-printable

<html><body><div style=3D"font-family: arial, helvetica, sans-serif; font-s=
ize: 12pt; color: #000000"><div>Za=C5=82=C4=85czam za=C5=82=C4=85czone...<b=
r data-mce-bogus=3D"1"></div></div></body></html>
--=_72022f91-b495-4ca5-bcbf-5ce51b021d03--

------=_Part_12345678_098765432.1234567890987
Content-Type: Message/RFC822
Content-Disposition: attachment

Return-Path: <nobody.expects@example.pl>
Received: from some-proxy.example.pl (LHLO some-proxy.example.pl)
 (198.51.100.98) by mailbox.example.pl with LMTP; Sat, 8 Apr 2023
 15:30:12 +0200 (CEST)
Received: from localhost (localhost [127.0.0.1])
\tby some-proxy.example.pl (Postfix) with ESMTP id 11223344556;
\tSat,  8 Apr 2023 15:30:12 +0200 (CEST)
Date: Sat, 8 Apr 2023 15:30:12 +0200 (CEST)
From: Cardinal Biggles <nobody.expects@example.pl>
To: nobody.expects@example.pl
Cc: =?utf-8?B?S3RvxZs=?= Inny <who@example.com>
Message-ID: <01.02.04.SpammishInquisition.foo@example.pl>
Subject: =?utf-8?Q?Za=C5=82=C4=85cznik?=
MIME-Version: 1.0
Content-Type: multipart/MIXED;\x20
\tboundary="----=_Part_23432123_4567890987.6543212345678"
X-Originating-IP: [10.20.30.40]

------=_Part_23432123_4567890987.6543212345678
Content-Type: TEXT/plain; charset=utf-8
Content-Transfer-Encoding: quoted-printable

(w za=C5=82=C4=85czeniu, jak to za=C5=82=C4=85cznik)
------=_Part_23432123_4567890987.6543212345678
Content-Type: text/x-readme; name=README
Content-Disposition: attachment; filename="/home/somebody/README"
Content-Transfer-Encoding: base64

bjYuCg==
------=_Part_23432123_4567890987.6543212345678
Content-Type: application/GZIP
Content-Transfer-Encoding: base64
Content-Disposition: attachment; filename=with_wrong_suffix.Zip

H4sICPGPk1EAA1JFQURNRQDLM9PjAgA8JokxBAAAAA==
------=_Part_23432123_4567890987.6543212345678--

------=_Part_12345678_098765432.1234567890987
Content-Type: MESSAGE/RFC822
Content-Disposition: attachment

Date: Sat, 8 Apr 2023 15:30:12 +0200 (CEST)
From: Cardinal Biggles <nobody.expects@example.pl>
To: whoever@example.info
Cc: =?utf-8?B?S3RvxZs=?= Inny <who@example.com>
Message-ID: <01.02.04.SpammishInquisition.foo@example.pl>
Subject: =?utf-8?Q?Za=C5=82=C4=85cznik?=
MIME-Version: 1.0
Content-Type: multipart/mixed;\t
\tboundary="----=_Part_23432123_4567890987.6543212345678"
X-Originating-IP: [10.20.30.40]

------=_Part_23432123_4567890987.6543212345678
Content-Type: text/plain; charset=utf-8
Content-Transfer-Encoding: quoted-printable

(w za=C5=82=C4=85czeniu, jak to za=C5=82=C4=85cznik)
------=_Part_23432123_4567890987.6543212345678
Content-Disposition: attachment; filename=README.zip
Content-Transfer-Encoding: base64

bjYuCg==
------=_Part_23432123_4567890987.6543212345678
Content-Type: TEXT/X-README; name=README.GZiP
Content-Disposition: attachment; filename=README.Gzip
Content-Transfer-Encoding: base64

H4sICPGPk1EAA1JFQURNRQDLM9PjAgA8JokxBAAAAA==
------=_Part_23432123_4567890987.6543212345678--

------=_Part_12345678_098765432.1234567890987--

--MP_/kobylaMaMalyBok01234567
Content-Type: application/x-NOBODY-knows
Content-Transfer-Encoding: base64
Content-Disposition: attachment; filename="ala/ma/kota/README.GZ"

H4sICPGPk1EAA1JFQURNRQDLM9PjAgA8JokxBAAAAA==

--MP_/kobylaMaMalyBok01234567
Content-Type: Application/GZip
Content-Transfer-Encoding: base64
Content-Disposition: attachment; filename="cut/gzip/content"

H4sICPGPk1EAA1JFQURN

--MP_/kobylaMaMalyBok01234567
Content-Type: Application/Gzip
Content-Transfer-Encoding: base64
Content-Disposition: attachment; filename=""

H4sICPGPk1EAA1JFQURNRQDLM9PjAgA8JokxBAAAAA==

--MP_/kobylaMaMalyBok01234567
Content-Type: APPLICATION/OCTET-STREAM; name=With-Wrong-Suffix.ZIP
Content-Transfer-Encoding: base64
Content-Disposition: attachment

H4sICPGPk1EAA1JFQURNRQDLM9PjAgA8JokxBAAAAA==

--MP_/kobylaMaMalyBok01234567
Content-Type: APPLICATION/OCTET-STREAM; name=README.gz
Content-Transfer-Encoding: base64
Content-Disposition: attachment

H4sICPGPk1EAA1JFQURNRQDLM9PjAgA8JokxBAAAAA==

--MP_/kobylaMaMalyBok01234567
Content-Type: application/octet-stream
Content-Transfer-Encoding: base64
Content-Disposition: attachment

H4sICPGPk1EAA1JFQURNRQDLM9PjAgA8JokxBAAAAA==

--MP_/kobylaMaMalyBok01234567
Content-Type: APPlication/x-gZIP
Content-Transfer-Encoding: base64
Content-Disposition: attachment

H4sICPGPk1EAA1JFQURNRQDLM9PjAgA8JokxBAAAAA==

--MP_/kobylaMaMalyBok01234567--
'''.replace(b'\n', b'\r\n'))


RAW_MSG_SOURCE['WITH-BROKEN-BOUNDARY'] = (
b'''Date: Sat, 8 Apr 2023 13:30:12 +0000 (CEST)
From: Francisco J. de Cisneros <nobody.expects@example.pl>
To: nobody.expects@example.pl
Subject:   =?utf-8?Q?Za=C5=82=C4=85cznik?=
MIME-Version: 1.0
Content-Type: multipart/mixed;\x20
\tboundary="----=_Part_23432123_4567890987.6543212345678.broken"

------=_Part_23432123_4567890987.6543212345678
Content-Type: text/plain; charset=utf-8
Content-Transfer-Encoding: quoted-printable

(w za=C5=82=C4=85czeniu, jak to za=C5=82=C4=85cznik)
------=_Part_23432123_4567890987.6543212345678
Content-Type: text/x-readme; name=README
Content-Disposition: attachment; filename="/home/somebody/README"
Content-Transfer-Encoding: base64

bjYuCg==
------=_Part_23432123_4567890987.6543212345678
Content-Type: application/gzip
Content-Transfer-Encoding: base64
Content-Disposition: attachment; filename=with_wrong_suffix.Zip

H4sICPGPk1EAA1JFQURNRQDLM9PjAgA8JokxBAAAAA==
------=_Part_23432123_4567890987.6543212345678--
'''.replace(b'\n', b'\r\n'))


RAW_MSG_SOURCE['WITH-DEFECTIVE-BASE64-CTE'] = (
b'''Return-Path: asdfg@hjkl.pl
Content-Type: multipart/mixed;
 boundary="===============7777777777777777777=="
Subject:  My  eXample  thing\x20
From: asdfg@hjkl.pl
Date: Mon, 12 Aug 2019 00:01:00 +0200
To: asdfg@hjkl.pl
X-Foo-Bar: Spam, Ham!

--===============7777777777777777777==
Content-Type: text/plain; charset="utf-8"
MIME-Version: 1.0
Content-Transfer-Encoding: base64

QWxhIG1hIGtvdGEuCkEg.a290IG1hIHBzYS4gCg

--===============7777777777777777777==--\
'''.replace(b'\n', b'\r\n'))


assert b'\r' not in RAW_MSG_SOURCE['STRANGE']
assert all(
    (raw_msg_source.count(b'\r\n')
     == raw_msg_source.count(b'\r')
     == raw_msg_source.count(b'\n'))
    for key, raw_msg_source in RAW_MSG_SOURCE.items()
    if key != 'STRANGE')


#
# Expected outcomes of `ParsedEmailMessage`'s operations
#

#
# * Expected outcomes of the parsing process:

EXPECTED_MSG_PARSING_LOG_WARN_REGEXES = {
    'SIMPLE': [],
    'STRANGE': [],
    'SHORTENED': [],
    'QUITE-COMPLEX': [],
    'WITH-BROKEN-BOUNDARY': [
        r'message defect.*StartBoundaryNotFoundDefect',
        r'message defect.*MultipartInvariantViolationDefect',
    ],
    'WITH-DEFECTIVE-BASE64-CTE': [],
}

EXPECTED_CONTENT_TYPE = {
    'SIMPLE': 'text/plain',
    'STRANGE': 'text/plain',
    'SHORTENED': 'text/plain',
    'QUITE-COMPLEX': 'multipart/mixed',
    'WITH-BROKEN-BOUNDARY': 'multipart/mixed',
    'WITH-DEFECTIVE-BASE64-CTE': 'multipart/mixed',
}

EXPECTED_HEADERS = {
    'SIMPLE': [
        ('Date', 'Sun, 28 May 2023 07:08:09 -0000'),
        ('From', 'Cardinal Biggles <nobody.expects@example.pl>'),
        ('To', 'whoever@example.net'),
        ('Organization', 'The Spanish Inquisition'),
        ('Subject', 'A simple message'),
    ],
    'STRANGE': [
        ('To', 'somebody@example.org'),
        ('Date', 'Sun, 28 May 2023 07:08:09 -0130'),
        ('From', 'Cardinal Biggles <nobody.expects@example.pl>'),
    ],
    'SHORTENED': [
        ('From', 'nobody.expects@example.pl'),
        ('To', 'somebody@example.org'),
    ],
    'QUITE-COMPLEX': [
        ('Return-Path', '<nobody.expects@example.pl>'),
        ('Received', (
            'from krasoola.example.pl (xyz.example.pl [203.0.113.91])'
            '\tby whatahost.example.net  with ESMTP id q87GKi62gsd800   '
            '\tfor <whoever@example.com>; Mon, 29 May 2023 16:05:21 +0200 (CEST)')),
        ('Date', 'Mon, 29 May 2023 16:05:19 +0200'),
        ('From', 'Cardinal Biggles <nobody.expects@example.pl>'),
        ('To', 'Whoever <whoever@example.net>'),
        ('Subject', 'Sieć    \t    relacji\t '),
        ('Message-ID', '<20230529160519.12345678@krasoola.example.pl>'),
        ('Organization', 'Naukowa i Akademicka Sieć Komputerowa'),
        ('X-Mailer', 'Claws Mail 3.8.1 (raczej stary)'),
        ('Mime-Version', '1.0'),
        ('Content-Type', 'Multipart/Mixed; boundary="MP_/kobylaMaMalyBok01234567"'),
        ('X-Bogosity', 'No, \t tests=bogofilter, \t \t\t   spamicity=0.0021, version=33.22.11\t '),
    ],
    'WITH-BROKEN-BOUNDARY': [
        ('Date', 'Sat, 08 Apr 2023 13:30:12 +0000'),
        ('From', '"Francisco J. de Cisneros" <nobody.expects@example.pl>'),
        ('To', 'nobody.expects@example.pl'),
        ('Subject', 'Załącznik'),
        ('MIME-Version', '1.0'),
        ('Content-Type', (
            'multipart/mixed; '
            'boundary="----=_Part_23432123_4567890987.6543212345678.broken"')),
    ],
    'WITH-DEFECTIVE-BASE64-CTE': [
        ('Return-Path', 'asdfg@hjkl.pl'),
        ('Content-Type', 'multipart/mixed; boundary="===============7777777777777777777=="'),
        ('Subject', 'My  eXample  thing '),
        ('From', 'asdfg@hjkl.pl'),
        ('Date', 'Mon, 12 Aug 2019 00:01:00 +0200'),
        ('To', 'asdfg@hjkl.pl'),
        ('X-Foo-Bar', 'Spam, Ham!'),
    ],
}

EXPECTED_UTC_DATETIME = {
    'SIMPLE': datetime.datetime(2023, 5, 28, 7, 8, 9),
    'STRANGE': datetime.datetime(2023, 5, 28, 8, 38, 9),
    'SHORTENED': None,
    'QUITE-COMPLEX': datetime.datetime(2023, 5, 29, 14, 5, 19),
    'WITH-BROKEN-BOUNDARY': datetime.datetime(2023, 4, 8, 13, 30, 12),
    'WITH-DEFECTIVE-BASE64-CTE': datetime.datetime(2019, 8, 11, 22, 1, 0),
}

EXPECTED_TIMESTAMP = {
    key: (
        dt.replace(tzinfo=datetime.timezone.utc).timestamp()
        if dt is not None else None)
    for key, dt in EXPECTED_UTC_DATETIME.items()}

EXPECTED_SUBJECT_WITH_NORMALIZED_WHITESPACE = {
    'SIMPLE': 'A simple message',
    'STRANGE': None,
    'SHORTENED': None,
    'QUITE-COMPLEX': 'Sieć relacji',
    'WITH-BROKEN-BOUNDARY': 'Załącznik',
    'WITH-DEFECTIVE-BASE64-CTE': 'My eXample thing',
}

EXPECTED_SUBJECT_UNNORMALIZED = {
    'SIMPLE': 'A simple message',
    'STRANGE': None,
    'SHORTENED': None,
    'QUITE-COMPLEX': 'Sieć    \t    relacji\t ',
    'WITH-BROKEN-BOUNDARY': 'Załącznik',
    'WITH-DEFECTIVE-BASE64-CTE': 'My  eXample  thing ',
}


#
# * Helpers to select expected outcomes of `ParsedEmailMessage.find_...()` operations:

_SUBSTRING_OF_EVERYTHING = ''

_WarnRegexSel = Union[str, Set[str]]

def select_expected_warn_regexes(key: str,
                                 by_substring: Union[_WarnRegexSel, Mapping[str, _WarnRegexSel]],
                                 ) -> Sequence[str]:

    if isinstance(by_substring, Mapping):
        by_substring = by_substring.get(key, set())
    by_substring = (
        {by_substring} if isinstance(by_substring, str)
        else set(by_substring))

    matched_substrings = set()
    selected = []

    _sorted_substrings = sorted(by_substring)
    for warn_regex in _EXPECTED_LOG_WARNING_REGEXES[key]:
        for substr in _sorted_substrings:
            if substr in warn_regex:
                matched_substrings.add(substr)
                selected.append(warn_regex)
                break

    assert bool(selected) is bool(by_substring), (
        f'test code expectation unsatisfied! '
        f'{key=!a} {by_substring=!a}, {selected=!a}')

    useless_substrings = by_substring - matched_substrings
    assert not useless_substrings, (
        f'test code expectation unsatisfied! {useless_substrings=!a}')

    return selected


# Common tag regexes (can be used as `select_expected_results()`'s 2nd arg):
_ALL_LEAF_COMPONENTS_TAG_REGEX = r'^(?!extracted from )'
_ALL_EXTRACTED_FILES_TAG_REGEX = r'^extracted from .*'
_ALL_RESULTS_TAG_REGEX = r'.*'

_Sel = Union[str, Set[str]]

def select_expected_results(key: str,
                            by_tag_regex: Union[_Sel, Mapping[str, _Sel]] = frozenset(),
                            *,
                            by_tag: _Sel = frozenset(),
                            content_coercion: Optional[Callable[[Content], Content]] = None,
                            get_contents_only: bool = False,
                            ) -> Union[
                                    Sequence[Content],
                                    Sequence[tuple[str, Content]]]:

    if isinstance(by_tag_regex, Mapping):
        by_tag_regex = by_tag_regex.get(key, set())
    by_tag_regex = (
        {by_tag_regex} if isinstance(by_tag_regex, str)
        else set(by_tag_regex))

    by_tag = (
        {by_tag} if isinstance(by_tag, str)
        else set(by_tag))
    assert by_tag.issubset(_EXPECTED_RESULTS_DATA_TAGS[key]), 'test helper expectation'
    by_tag_regex.update(
        rf'\A{re.escape(tag)}\Z'
        for tag in by_tag)

    matched_tag_regexes = set()
    selected = []

    _sorted_tag_regexes = sorted(by_tag_regex)
    for obj in _EXPECTED_RESULTS_DATA[key]:
        for regex in _sorted_tag_regexes:
            if re.search(regex, obj.tag):
                matched_tag_regexes.add(regex)
                content = obj.content
                if content_coercion is not None:
                    content = content_coercion(obj.content)
                selected.append(
                    content
                    if get_contents_only
                    else (obj.filename, content))
                break

    assert bool(selected) is bool(by_tag_regex), (
        f'test code expectation unsatisfied! '
        f'{key=!a} {by_tag_regex=!a}, {selected=!a}')

    useless_tag_regexes = by_tag_regex - matched_tag_regexes
    assert not useless_tag_regexes, (
        f'test code expectation unsatisfied! {useless_tag_regexes=!a}')

    return selected


#
# * The data for the selection helpers defined above:

_EXPECTED_LOG_WARNING_REGEXES = {
    'SIMPLE': [],
    'STRANGE': [],
    'SHORTENED': [],
    'QUITE-COMPLEX': [
        # (see the expected result data with the tag:
        # `gzip with wrong suffix`)
        r'Could not unpack content from the ZIP archive',

        # (see the expected result data with the tag:
        # `truncated gzip`)
        r'Could not decompress \*gzip\*-compressed content',

        # (see the expected result data with the tag:
        # `gzip with wrong suffix and content type`)
        r'Could not unpack content from the ZIP archive',
    ],
    'WITH-BROKEN-BOUNDARY': [
        # (see the expected result data with the tag:
        # `broken unparsed`)
        (r'Got an error .* when trying to get the content of '
         r'the message component .* multipart-boundary-related '
         r'.* Falling back to getting it as binary data'),
    ],
    'WITH-DEFECTIVE-BASE64-CTE': [
        # (see the expected result data with the tag:
        # `broken base64`)
        (r'An e-mail message defect has been found.*'
         r'\bInvalidBase64CharactersDefect\b'),

        (r'An e-mail message defect has been found.*'
         r'\bInvalidBase64PaddingDefect\b'),
    ],
}

@dataclasses.dataclass
class _ExpectedResultData:
    tag: str                                      # for selection (see `select_expected_results()`)
    content_type_or_exf: Union[str, ExtractFrom]  # content type string or *extracted-from* marker
    filename: str                                 # component's/extracted file's filename (if any)
    content: Union[str, bytes]                    # component's/extracted file's content

_EXPECTED_RESULTS_DATA = {
    'SIMPLE': [
        _ExpectedResultData(
            tag='main body',
            content_type_or_exf='text/plain',
            filename='',
            content='I confess!\nI confess!!\nI confess!!!\n',
        ),
    ],

    'STRANGE': [
        _ExpectedResultData(
            tag='main body',
            content_type_or_exf='text/plain',
            filename='',
            content='Cut text',
        ),
    ],

    'SHORTENED': [
        _ExpectedResultData(
            tag='main body',
            content_type_or_exf='text/plain',
            filename='',
            content='',
        ),
    ],

    'QUITE-COMPLEX': [
        _ExpectedResultData(
            tag='main body',
            content_type_or_exf='text/plain',
            filename='',
            content='Tu jest jakaś sobie treść.\nTralala.\n',
        ),
        _ExpectedResultData(
            tag='pickled',
            content_type_or_exf='application/octet-stream',
            filename='pickled_datetime.bin',
            content=(
                b'\x80\x04\x953\x00\x00\x00\x00\x00\x00\x00}\x94\x8c\x03'
                b'now\x94\x8c\x08datetime\x94\x8c\x08datetime\x94\x93\x94'
                b'C\n\x07\xe6\x08\x19\x0f\x08/\x0c\x05b\x94\x85\x94R\x94s.'),
        ),
        _ExpectedResultData(
            tag='extracted from zip #1',
            content_type_or_exf=ExtractFrom.ZIP,
            filename='test.compressed-you-now/.hgignore',
            content=b'syntax: glob\n\n*.pyc\n.project\n.pydevproject\n.settings\n\n',
        ),
        _ExpectedResultData(
            tag='extracted from zip #2',
            content_type_or_exf=ExtractFrom.ZIP,
            filename='test.compressed-you-now/README',
            content=b'n6.\n',
        ),
        _ExpectedResultData(
            tag='zip',
            content_type_or_exf='application/zip',
            filename='test.compressed-you-now',
            content=(
                b'PK\x03\x04\x14\x00\x00\x00\x08\x00\xf1[\xb0B\x98^\xaaF/\x00\x00'
                b'\x006\x00\x00\x00\x0c\x00\x1c\x00n6/.hgignoreUT\t\x00\x03u\xa7'
                b'\x94Qy\xa7\x94Qux\x0b\x00\x01\x04\xe8\x03\x00\x00\x04\xe8\x03'
                b'\x00\x00+\xae\xcc+I\xac\xb0RH\xcf\xc9O\xe2\xe2\xd2\xd2+\xa8L'
                b'\xe6\xd2+(\xca\xcfJM.\x012*SR\xcb\xe0\xbc\xe2\xd4\x92\x92\xcc'
                b'\xbc\xf4b..\x00PK\x03\x04\n\x00\x00\x00\x00\x00\xdd|\xafB<&'
                b'\x891\x04\x00\x00\x00\x04\x00\x00\x00\t\x00\x1c\x00n6/READMEUT'
                b'\t\x00\x03\xf1\x8f\x93Q*\x9f\x93Qux\x0b\x00\x01\x04\xe8\x03\x00'
                b'\x00\x04\xe8\x03\x00\x00n6.\nPK\x01\x02\x1e\x03\x14\x00\x00\x00'
                b'\x08\x00\xf1[\xb0B\x98^\xaaF/\x00\x00\x006\x00\x00\x00\x0c\x00'
                b'\x18\x00\x00\x00\x00\x00\x01\x00\x00\x00\xa4\x81\x00\x00\x00'
                b'\x00n6/.hgignoreUT\x05\x00\x03u\xa7\x94Qux\x0b\x00\x01\x04\xe8'
                b'\x03\x00\x00\x04\xe8\x03\x00\x00PK\x01\x02\x1e\x03\n\x00\x00'
                b'\x00\x00\x00\xdd|\xafB<&\x891\x04\x00\x00\x00\x04\x00\x00\x00'
                b'\t\x00\x18\x00\x00\x00\x00\x00\x01\x00\x00\x00\xa4\x81u\x00\x00'
                b'\x00n6/READMEUT\x05\x00\x03\xf1\x8f\x93Qux\x0b\x00\x01\x04\xe8'
                b'\x03\x00\x00\x04\xe8\x03\x00\x00PK\x05\x06\x00\x00\x00\x00\x02'
                b'\x00\x02\x00\xa1\x00\x00\x00\xbc\x00\x00\x00\x00\x00'),
        ),
        _ExpectedResultData(
            tag='readme as binary data',
            content_type_or_exf='application/octet-stream',
            filename='README',
            content=b'n6.\n',
        ),
        _ExpectedResultData(
            tag='python code',
            content_type_or_exf='text/x-python',
            filename='',
            content=(
                "print('Hello world!')\n"
                "print(\"I printed ''Hello world!'!\")\n"),
        ),
        _ExpectedResultData(
            tag='extracted from bzip2',
            content_type_or_exf=ExtractFrom.BZIP2,
            filename='_BZIP2_DECOMPRESSED_README.bz2/',
            content=b'n6.\n',
        ),
        _ExpectedResultData(
            tag='bzip2',
            content_type_or_exf='application/x-bzip2',
            filename='README.bz2/',
            content=(
                b'BZh91AY&SYx\xff\xa7p\x00\x00\x01\xd9\x00\x00\x10\x00\x01\x01'
                b'\x00\x00\x01 \x00!\x9ah3M\x0c\xbc]\xc9\x14\xe1BA\xe3\xfe\x9d\xc0'),
        ),
        _ExpectedResultData(
            tag='8bit text',
            content_type_or_exf='text/plain',
            filename='',
            content='Załączam załączone...\n',
        ),
        _ExpectedResultData(
            tag='html',
            content_type_or_exf='text/html',
            filename='',
            content=(
                '<html><body><div style="font-family: arial, helvetica, '
                'sans-serif; font-size: 12pt; color: #000000"><div>'
                'Załączam załączone...<br data-mce-bogus="1"></div>'
                '</div></body></html>'),
        ),
        _ExpectedResultData(
            tag='nested text zz #1',
            content_type_or_exf='text/plain',
            filename='',
            content='(w załączeniu, jak to załącznik)',
        ),
        _ExpectedResultData(
            tag='x-readme',
            content_type_or_exf='text/x-readme',
            filename='/home/somebody/README',
            content='n6.\n',
        ),
        _ExpectedResultData(
            tag='extracted from gzip with wrong suffix',
            content_type_or_exf=ExtractFrom.GZIP,
            filename='_GZIP_DECOMPRESSED_with_wrong_suffix.Zip',
            content=b'n6.\n',
        ),
        _ExpectedResultData(
            # (encountering it causes logging of the warning:
            # `Could not unpack content from the ZIP archive...`)
            tag='gzip with wrong suffix',
            content_type_or_exf='application/gzip',
            filename='with_wrong_suffix.Zip',
            content=(
                b'\x1f\x8b\x08\x08\xf1\x8f\x93Q\x00\x03README\x00\xcb'
                b'3\xd3\xe3\x02\x00<&\x891\x04\x00\x00\x00'),
        ),
        _ExpectedResultData(
            tag='nested text zz #2',
            content_type_or_exf='text/plain',
            filename='',
            content='(w załączeniu, jak to załącznik)',
        ),
        _ExpectedResultData(
            tag='without explicit content type',
            content_type_or_exf='text/plain',
            filename='README.zip',  # (efficient content type is textual => no unpacking!)
            content='n6.\n',  # (yes, actually it was *not* packed/compressed)
        ),
        _ExpectedResultData(
            tag='gzip with wrongly textual content type',
            content_type_or_exf='text/x-readme',
            filename='README.Gzip',  # (content type is textual => no decompression!)
            content=(
                # (because of the wrong content type, we get garbage)
                '\x1f\ufffd\x08\x08\ufffd\ufffd\ufffdQ\x00\x03README\x00\ufffd'
                '3\ufffd\ufffd\x02\x00<&\ufffd1\x04\x00\x00\x00'),
        ),
        _ExpectedResultData(
            tag='extracted from gzip recognized by filename suffix',
            content_type_or_exf=ExtractFrom.GZIP,
            filename='ala/ma/kota/README',  # (suffix was correct, so it has been just removed)
            content=b'n6.\n',
        ),
        _ExpectedResultData(
            tag='gzip recognized by filename suffix',
            content_type_or_exf='application/x-nobody-knows',
            filename='ala/ma/kota/README.GZ',
            content=(
                b'\x1f\x8b\x08\x08\xf1\x8f\x93Q\x00\x03README\x00\xcb'
                b'3\xd3\xe3\x02\x00<&\x891\x04\x00\x00\x00'),
        ),
        _ExpectedResultData(
            # (encountering it causes logging of the warning:
            # `Could not decompress *gzip*-compressed content...`)
            tag='truncated gzip',
            content_type_or_exf='application/gzip',
            filename='cut/gzip/content',
            content=b'\x1f\x8b\x08\x08\xf1\x8f\x93Q\x00\x03READM',
        ),
        _ExpectedResultData(
            tag='extracted from gzip recognized by standard content type',
            content_type_or_exf=ExtractFrom.GZIP,
            filename='_GZIP_DECOMPRESSED_',
            content=b'n6.\n',
        ),
        _ExpectedResultData(
            tag='gzip recognized by standard content type',
            content_type_or_exf='application/gzip',
            filename='',
            content=(
                b'\x1f\x8b\x08\x08\xf1\x8f\x93Q\x00\x03README\x00\xcb'
                b'3\xd3\xe3\x02\x00<&\x891\x04\x00\x00\x00'),
        ),
        _ExpectedResultData(
            # (encountering it causes logging of the warning:
            # `Could not unpack content from the ZIP archive...`)
            tag='gzip with wrong suffix and content type',  # (not decompressed/unpacked at all)
            content_type_or_exf='application/octet-stream',
            filename='With-Wrong-Suffix.ZIP',
            content=(
                b'\x1f\x8b\x08\x08\xf1\x8f\x93Q\x00\x03README\x00\xcb'
                b'3\xd3\xe3\x02\x00<&\x891\x04\x00\x00\x00'),
        ),
        _ExpectedResultData(
            tag='extracted from gzip recognized by suffix of filename from ct `name`',
            content_type_or_exf=ExtractFrom.GZIP,
            filename='README',  # (suffix was correct, so it has been just removed)
            content=b'n6.\n',
        ),
        _ExpectedResultData(
            tag='gzip recognized by suffix of filename from ct `name`',
            content_type_or_exf='application/octet-stream',
            filename='README.gz',
            content=(
                b'\x1f\x8b\x08\x08\xf1\x8f\x93Q\x00\x03README\x00\xcb'
                b'3\xd3\xe3\x02\x00<&\x891\x04\x00\x00\x00'),
        ),
        _ExpectedResultData(
            tag='gzip with no filename and wrong content type',  # (not decompressed at all)
            content_type_or_exf='application/octet-stream',
            filename='',
            content=(
                b'\x1f\x8b\x08\x08\xf1\x8f\x93Q\x00\x03README\x00\xcb'
                b'3\xd3\xe3\x02\x00<&\x891\x04\x00\x00\x00'),
        ),
        _ExpectedResultData(
            tag='extracted from gzip recognized by `x-` content type',
            content_type_or_exf=ExtractFrom.GZIP,
            filename='_GZIP_DECOMPRESSED_',
            content=b'n6.\n',
        ),
        _ExpectedResultData(
            tag='gzip recognized by `x-` content type',
            content_type_or_exf='application/x-gzip',
            filename='',
            content=(
                b'\x1f\x8b\x08\x08\xf1\x8f\x93Q\x00\x03README\x00\xcb'
                b'3\xd3\xe3\x02\x00<&\x891\x04\x00\x00\x00'),
        ),
    ],

    'WITH-BROKEN-BOUNDARY': [
        _ExpectedResultData(
            # (encountering it causes logging of the warning:
            # `Got an error... when trying to get the content of...`)
            tag='broken unparsed',
            content_type_or_exf='multipart/mixed',
            filename='',
            content=(
b'''------=_Part_23432123_4567890987.6543212345678
Content-Type: text/plain; charset=utf-8
Content-Transfer-Encoding: quoted-printable

(w za=C5=82=C4=85czeniu, jak to za=C5=82=C4=85cznik)
------=_Part_23432123_4567890987.6543212345678
Content-Type: text/x-readme; name=README
Content-Disposition: attachment; filename="/home/somebody/README"
Content-Transfer-Encoding: base64

bjYuCg==
------=_Part_23432123_4567890987.6543212345678
Content-Type: application/gzip
Content-Transfer-Encoding: base64
Content-Disposition: attachment; filename=with_wrong_suffix.Zip

H4sICPGPk1EAA1JFQURNRQDLM9PjAgA8JokxBAAAAA==
------=_Part_23432123_4567890987.6543212345678--
'''.replace(b'\n', b'\r\n')),
        ),
    ],

    'WITH-DEFECTIVE-BASE64-CTE': [
        _ExpectedResultData(
            # (encountering it causes logging of the warning:
            # `XXX`)
            tag='broken base64',
            content_type_or_exf='text/plain',
            filename='',
            content='Ala ma kota.\nA kot ma psa. \n',
        ),
    ],
}

_EXPECTED_RESULTS_DATA_TAGS = {
    key: {obj.tag for obj in seq}
    for key, seq in _EXPECTED_RESULTS_DATA.items()}


#
# * Auxiliary constants:

# (can be passed as `**kwargs` to `select_expected_warn_regexes()`)
ALL_WARNINGS_SELECTION = dict(
    by_substring={
        'QUITE-COMPLEX': _SUBSTRING_OF_EVERYTHING,
        'WITH-BROKEN-BOUNDARY': _SUBSTRING_OF_EVERYTHING,
        'WITH-DEFECTIVE-BASE64-CTE': _SUBSTRING_OF_EVERYTHING,
    },
)

# (each can be passed as `**kwargs` to `select_expected_results()`)
ALL_LEAF_COMPONENTS_SELECTION = dict(
    by_tag_regex=_ALL_LEAF_COMPONENTS_TAG_REGEX,
)
ALL_EXTRACTED_FILES_SELECTION = dict(
    by_tag_regex={'QUITE-COMPLEX': _ALL_EXTRACTED_FILES_TAG_REGEX}
)
ALL_RESULTS_SELECTION = dict(
    by_tag_regex=_ALL_RESULTS_TAG_REGEX,
)


EXPECTED_NUMBER_OF_ALL_LEAF_COMPONENTS = {
    key: len(select_expected_results(key, **ALL_LEAF_COMPONENTS_SELECTION))
    for key in TEST_MSG_KEYS}

assert EXPECTED_NUMBER_OF_ALL_LEAF_COMPONENTS == {
    'SIMPLE': 1,
    'STRANGE': 1,
    'SHORTENED': 1,
    'QUITE-COMPLEX': 21,
    'WITH-BROKEN-BOUNDARY': 1,
    'WITH-DEFECTIVE-BASE64-CTE': 1,
}


EXPECTED_NUMBER_OF_ALL_EXTRACTED_FILES = {
    key: len(select_expected_results(key, **ALL_EXTRACTED_FILES_SELECTION))
    for key in TEST_MSG_KEYS}

assert EXPECTED_NUMBER_OF_ALL_EXTRACTED_FILES == {
    'SIMPLE': 0,
    'STRANGE': 0,
    'SHORTENED': 0,
    'QUITE-COMPLEX': 8,
    'WITH-BROKEN-BOUNDARY': 0,
    'WITH-DEFECTIVE-BASE64-CTE': 0,
}


EXPECTED_NUMBER_OF_ALL_LEAF_COMPONENTS_AND_EXTRACTED_FILES = {
    key: len(select_expected_results(key, **ALL_RESULTS_SELECTION))
    for key in TEST_MSG_KEYS}

assert EXPECTED_NUMBER_OF_ALL_LEAF_COMPONENTS_AND_EXTRACTED_FILES == {
    'SIMPLE': 1,
    'STRANGE': 1,
    'SHORTENED': 1,
    'QUITE-COMPLEX': 29,
    'WITH-BROKEN-BOUNDARY': 1,
    'WITH-DEFECTIVE-BASE64-CTE': 1,
}


#
# A bunch of internal assertions

assert (_EXPECTED_LOG_WARNING_REGEXES.keys()
        == _EXPECTED_RESULTS_DATA.keys()
        == _EXPECTED_RESULTS_DATA_TAGS.keys()
        == set(TEST_MSG_KEYS))

assert all(
    isinstance(obj, str)
    for seq in _EXPECTED_LOG_WARNING_REGEXES.values()
        for obj in seq)

assert all(
    (key in ALL_WARNINGS_SELECTION['by_substring']
     ) is bool(_EXPECTED_LOG_WARNING_REGEXES[key])
    for key in TEST_MSG_KEYS)

assert all(
    isinstance(obj, _ExpectedResultData)
    and isinstance(obj.tag, str) and obj.tag
    and re.search(_ALL_RESULTS_TAG_REGEX, obj.tag)
    and ((isinstance(obj.content_type_or_exf, ExtractFrom)
          and (ALL_EXTRACTED_FILES_SELECTION['by_tag_regex'].get(key)
               == _ALL_EXTRACTED_FILES_TAG_REGEX)
          and re.search(_ALL_EXTRACTED_FILES_TAG_REGEX, obj.tag)
          and not re.search(_ALL_LEAF_COMPONENTS_TAG_REGEX, obj.tag))
         if obj.tag.startswith('extracted from ')
         else (isinstance(obj.content_type_or_exf, str)
               and obj.content_type_or_exf
               and obj.content_type_or_exf.lower() == obj.content_type_or_exf
               and re.search(_ALL_LEAF_COMPONENTS_TAG_REGEX, obj.tag)
               and not re.search(_ALL_EXTRACTED_FILES_TAG_REGEX, obj.tag)))
    and isinstance(obj.filename, str)
    and (isinstance(obj.content, str)
         if (isinstance(obj.content_type_or_exf, str)
             and obj.content_type_or_exf.startswith('text/'))
         else isinstance(obj.content, bytes))
    for key, seq in _EXPECTED_RESULTS_DATA.items()
        for obj in seq)

assert all(  # (tags are unique within each seq)
    len(seq) == len(_EXPECTED_RESULTS_DATA_TAGS[key])
    for key, seq in _EXPECTED_RESULTS_DATA.items())
