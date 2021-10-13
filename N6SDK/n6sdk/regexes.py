# Copyright (c) 2013-2021 NASK. All rights reserved.

"""
This module contains several regular expression objects (most of
them are used in other parts of the *n6sdk* library).
"""


import re


#: Two-character country code.
#:
#: Used by :class:`n6sdk.data_spec.fields.CCField`.
CC_SIMPLE_REGEX = re.compile(r'\A[A-Z][A-Z12]\Z', re.ASCII)


#: Domain name -- with the underscore character allowed
#: (as life is more eventful than RFCs, especially when it
#: comes to maliciously constructed domain names).
#:
#: Used by :class:`n6sdk.data_spec.fields.DomainNameField`
#: and :class:`n6sdk.data_spec.fields.DomainNameSubstringField`.
DOMAIN_ASCII_LOWERCASE_REGEX = re.compile(r'''
    \A
    (?:
        [\-0-9a-z_]{1,63}
        \.
    )*
    (?!\d+\Z)         # top-level label cannot consist of digits only
    [\-0-9a-z_]{1,63}
    \Z
''', re.ASCII | re.VERBOSE)


#: Domain name -- more strict (hopefully RFC-compliant) variant.
DOMAIN_ASCII_LOWERCASE_STRICT_REGEX = re.compile(r'''
    \A
    (?:
        [0-9a-z]      # label is not allowed to start with '-'
        (?:
            [\-0-9a-z]{0,61}
            [0-9a-z]  # label is not allowed to end with '-'
        )?
        \.
    )*
    (?!\d+\Z)         # top-level label cannot consist of digits only
    [0-9a-z]          # label is not allowed to start with '-'
    (?:
        [\-0-9a-z]{0,61}
        [0-9a-z]      # label is not allowed to end with '-'
    )?
    \Z
''', re.ASCII | re.VERBOSE)


#: IPv4 address in decimal dotted-quad notation.
#:
#: Used by :class:`n6sdk.data_spec.fields.IPv4Field`.
IPv4_STRICT_DECIMAL_REGEX = re.compile(r'''
    \A
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
        |                 # or
            (?=           # termination
                \Z
            )
        )
    ){4}
    \Z
''', re.ASCII | re.VERBOSE)


#: Anonymized IPv4 address.
#:
#: Used by :class:`n6sdk.data_spec.fields.AnonymizedIPv4Field`.
IPv4_ANONYMIZED_REGEX = re.compile(r'''
    \A
    (?=
        x                 # *at least* first octet should be anonymized
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
        |
            x             # anonymized octet placeholder
        )
        (?:
            \.            # dot
            (?=           # followed by next octet...
                [0-9x]
            )
        |                 # or
            (?=           # termination
                \Z
            )
        )
    ){4}
    \Z
''', re.ASCII | re.VERBOSE)


#: IPv4 network specification in CIDR notation.
#:
#: Used by :class:`n6sdk.data_spec.fields.IPv4NetField`.
IPv4_CIDR_NETWORK_REGEX = re.compile(r'''
    \A
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
        |                 # or
            (?=           # slash (beginning netmask specification)
                /
            )
        )
    ){4}
                          # netmask specification
    /
    (?:
        3[0-2]       # 30..32
    |
        [12]?[0-9]   # 0..29
    )
    \Z
''', re.ASCII | re.VERBOSE)


# values of the `source` field must match this
SOURCE_REGEX = re.compile(r'\A[\-0-9a-z]+\.[\-0-9a-z]+\Z', re.ASCII)


PY_IDENTIFIER_REGEX = re.compile(r'\A[a-zA-Z_][a-zA-Z0-9_]*\Z', re.ASCII)


#: E-mail address (very rough validation).
#:
#: Used by :class:`n6sdk.data_spec.fields.EmailSimplifiedField`.
EMAIL_SIMPLIFIED_REGEX = re.compile(r'''
    \A
    [^@\s]+
    @
    [^@\s]+
    \Z
''', re.UNICODE | re.VERBOSE)


#: International Bank Account Number.
#:
#: Used by :class:`n6sdk.data_spec.fields.IBANSimplifiedField`.
IBAN_REGEX = re.compile(r'''
    \A
    [A-Z]{2}
    [0-9]{2}
    [0-9A-Z]{8,30}
    \Z
''', re.ASCII | re.VERBOSE)


ISO_DATE_REGEX = re.compile(
    # here we don't check ranges of particular values (e.g. that month is
    # in 01..12) because it is better to do it in functions that use this
    # regex (-> better debug information in case of incorrect input data)

    r'''
    \A
    (?P<year>
        \d{4}
    )
    -?
    (?:
        (?P<month>
            \d{2}
        )
        -?
        (?P<day>
            \d{2}
        )
    |
        W
        (?P<isoweek>
            \d{2}
        )
        -?
        (?P<isoweekday>
            \d
        )
    |
        (?P<ordinalday>
            \d{3}
        )
    )
    \Z
    ''', re.ASCII | re.VERBOSE)


ISO_TIME_REGEX = re.compile(
    # here we don't check ranges of particular values (e.g. that minute is
    # in 00..59) because it is better to do it in functions that use this
    # regex (-> better debug information in case of incorrect input data)

    r'''
    \A
    (?P<hour>
        \d{2}
    )
    :?
    (?P<minute>
        \d{2}
    )
    (?:
        :?
        (?P<second>
            \d{2}
        )
        (?:
            \.
            (?P<secondfraction>
                \d+
            )
        )?
    )?
    (?:
        Z
    |
        (?:
            (?P<tzhour>
                [+-]
                \d{2}
            )
            (?:
                :?
                (?P<tzminute>
                    \d{2}
                )
            )?
        )
    )?
    \Z
    ''', re.ASCII | re.VERBOSE)


ISO_DATETIME_REGEX = re.compile(
    r'{date}[T\s]{time}'.format(date=ISO_DATE_REGEX.pattern.rstrip('Z\\ \r\n'),
                                time=ISO_TIME_REGEX.pattern.lstrip('A\\ \r\n')),
    re.ASCII | re.VERBOSE)
