# Copyright (c) 2013-2023 NASK. All rights reserved.

import bz2
import datetime
import email
import email.contentmanager
import email.errors
import email.message
import email.policy
import enum
import gzip
import logging
import os
import pathlib
import re
from collections.abc import (
    Callable,
    Iterator,
    Mapping,
    Sequence,
    Set,
)
from typing import (
    Any,
    AnyStr,
    ClassVar,
    Literal,
    Optional,
    Protocol,
    Union,
)

from n6lib.common_helpers import (
    ascii_str,
    as_unicode,
    make_exc_ascii_str,
    read_file,
    splitlines_asc,
)
from n6lib.datetime_helpers import (
    datetime_utc_normalize,
    timestamp_from_datetime,
)
from n6lib.log_helpers import get_logger
from n6lib.typing_helpers import (
    FilePath,
    SupportsRead,
)
from n6lib.unpacking_helpers import iter_unzip_from_bytes


LOGGER = get_logger(__name__)


#
# Auxiliary static typing stuff
#

class ContentManagerLike(Protocol):

    """
    See: https://docs.python.org/3/library/email.policy.html#email.policy.EmailPolicy.content_manager
    as well as relevant stuff provided by `email.policy.EmailPolicy`...
    """

    def get_content(
            self,
            msg: email.message.Message,
            *args: Any,
            **kwargs: Any,
            ) -> Any:
        ...

    def set_content(
            self,
            msg: email.message.Message,
            obj: Any,
            *args: Any,
            **kwargs: Any,
            ) -> Any:
        ...


class OutputContentAdjuster(Protocol):

    """
    See the `output_content_adjuster` keyword argument accepted by the
    `ContentManagerAdjustableWrapper`'s constructor (defined in this
    module).
    """

    def __call__(
            self,
            msg: email.message.Message,
            *args: Any,
            orig_output_content: Any,
            **kwargs: Any,
            ) -> Any:

        # (actual implementations may process it in any way...)
        return orig_output_content


_BinRegex = Union[re.Pattern[bytes], bytes]
_TextRegex = Union[re.Pattern[str], str]
_Regex = Union[_BinRegex, _TextRegex]

ContentTypeCriteria = Union[str, 'ExtractFrom', Sequence[Union[str, 'ExtractFrom']]]
ContentRegexCriteria = Union[_Regex, Sequence[_Regex]]
FilenameRegexCriteria = Union[_TextRegex, Sequence[_TextRegex]]
ForcedTypeIndication = Union[type[bytes], type[str], Literal['bytes', 'str']]

Content = Union[bytes, str]


#
# Actual helpers provided by this module
#

class ExtractFrom(enum.Enum):

    """
    Each of the members of this enumeration can be used as a special
    form of a `content_type` filtering criterion, indicating that stuff
    extracted from any message components in the corresponding format
    (ZIP, *gzip* or *bzip2*) should be considered for inclusion
    (see the `ParsedEmailMessage`'s methods: `find_content()` and
    `find_filename_content_pairs()`).
    """

    ZIP = 'ZIP'
    GZIP = '*gzip*'
    BZIP2 = '*bzip2*'

    def __str__(self):
        return self.value

    def __repr__(self):
        return f'{type(self).__qualname__}.{self.name}'


class ParsedEmailMessage(email.message.EmailMessage):

    """
    A subclass of `email.message.EmailMessage` (see the official
    documentation at https://docs.python.org/3/library/email.html
    to learn about its possibilities).

    This subclass adds a few convenience constructors and helper
    methods as well as a few auxiliary attributes.

    The additional constructors are:

    * `from_bytes()` -- parsing a `bytes` object;

    * `from_binary_file()` -- parsing the content of a binary file.

    When a `ParsedEmailMessage` instance is created by calling
    any of these constructors, it gets an additional attribute:
    `raw_message_source`; it is a `bytes` object representing the
    original input data. In other cases, `raw_message_source` is
    left as `None`.

    The additional helper methods are:

    * `get_timestamp()` --
      get the `Date` header of the e-mail message as a UNIX timestamp
      (represented by a `float` number);

    * `get_utc_datetime()` --
      get the `Date` header of the e-mail message as a UTC date+time
      (represented by a "naive" `datetime.datetime` object);

    * `get_subject()` --
      get the `Subject` header of the e-mail message (as a `str`;
      by default, with normalized whitespace characters);

    * `find_content()` --
      get the content of exactly one component of the e-mail message --
      such one that matches the given filtering criteria (each optional):
      content type(s) and/or content/filename regexes; there is also a
      possibility to get stuff extracted from an attachment in the ZIP,
      *gzip* or *bzip2* format;

    * `find_filename_content_pairs()` --
      iterate over `(filename, content)` pairs from those "leaf"
      components of the e-mail message that match the given filtering
      criteria (each optional): content type(s) and/or content/filename
      regexes; there is also a possibility to include stuff extracted
      from attachments in the ZIP, *gzip* and/or *bzip2* format(s);

    For more information, see the signatures and docs of these methods.

    ***

    An important note: whenever you choose a non-default *policy* (see:
    https://docs.python.org/3/library/email.policy.html) to be used with
    `ParsedEmailMessage` or its instances -- for example, when passing a
    `policy` keyword argument to the `ParsedEmailMessage` constructor --
    then you should *always* use such a *policy* whose `message_factory`
    produces instances of (a subclass of) the standard *modern* message
    class `email.message.EmailMessage` (note that `ParsedEmailMessage`
    *is* such a subclass).

    Obviously, `n6lib.mail_parsing_helpers.parsed_email_policy` (which
    is the `ParsedEmailMessage`'s default *policy*) meets that
    requirement.

    Note: that requirement is not directly checked (doing that would not
    be trivial), but the effects of using a *policy* which does not meet
    it are undefined, i.e., errors may occur or incorrect behaviors may
    be observed (either immediately or -- more likely -- when some
    further operations are attempted...). *You have been warned.*

    ***

    A note about the *content manager* offered by the default *policy*
    of `ParsedEmailMessage`: that manager is the object provided by this
    module as `newline_normalizing_wrapper_of_raw_data_manager`; it
    wraps the standard `raw_data_manager` object to provide additional
    adjustment of all *textual* (but not *binary!*) contents -- when
    they are obtained with such message methods as `get_content()` (a
    standard one) or `find_content()`/`find_filename_content_pairs()`
    (these two are provided by this class), but *not* with the standard
    *message flattening* (raw message generation) machinery (accessible
    via the `email.generator` module as well as the `__bytes__()` method
    of a message object).

    That adjustment is just normalization of *newlines*: regardless what
    style was used -- `\n`, `\r` or `\r\n` -- only `\n` will appear in
    output contents (including *textual* contents being subject to
    `content_regex`-based filtering -- when it comes to the methods
    `find_content()` and `find_filename_content_pairs()` provided by
    this class).

    Note that this functionality is fully customizable (via a *policy*
    with its `content_manager` attribute...). To learn more about the
    concept of *content managers* -- see:

    * https://docs.python.org/3/library/email.policy.html#email.policy.EmailPolicy.content_manager
    * https://docs.python.org/3/library/email.message.html#email.message.EmailMessage.get_content
    * https://docs.python.org/3/library/email.contentmanager.html

    However, note also that `<content manager instance>.get_content()`'s
    return values are expected (by the `ParsedEmailMessage`'s machinery)
    to be a `str` or `bytes`; otherwise a `NotImplementedError` is raised.
    """


    #
    # Constant attributes
    #

    ZIP: ClassVar[ExtractFrom] = ExtractFrom.ZIP
    GZIP: ClassVar[ExtractFrom] = ExtractFrom.GZIP
    BZIP2: ClassVar[ExtractFrom] = ExtractFrom.BZIP2

    EXTRACTABLE_CONTENT_TYPES: ClassVar[Mapping[ExtractFrom, Set]] = dict()
    EXTRACTABLE_FILENAME_EXTENSIONS: ClassVar[Mapping[ExtractFrom, Set]] = dict()

    EXTRACTABLE_CONTENT_TYPES[ZIP] = frozenset([                        # noqa
        'application/zip',
        'application/x-zip',
        'application/x-zip-compressed',
    ])
    EXTRACTABLE_FILENAME_EXTENSIONS[ZIP] = frozenset([                  # noqa
        '.zip',
    ])

    EXTRACTABLE_CONTENT_TYPES[GZIP] = frozenset([                       # noqa
        'application/gzip',
        'application/gzip-compressed',
        'application/gzipped',
        'application/x-gunzip',
        'application/x-gzip',
        'application/x-gzip-compressed',
        'gzip/document',
    ])
    EXTRACTABLE_FILENAME_EXTENSIONS[GZIP] = frozenset([                 # noqa
        '.gzip',
        '.gz',
    ])

    EXTRACTABLE_CONTENT_TYPES[BZIP2] = frozenset([                      # noqa
        'application/bzip2',
        'application/x-bzip2',
        'application/x-bz2',
    ])
    EXTRACTABLE_FILENAME_EXTENSIONS[BZIP2] = frozenset([                # noqa
        '.bzip2',
        '.bz2',
    ])


    #
    # Initialization + additional attribute
    #

    def __init__(
            self,
            policy: Optional[email.policy.Policy] = None):

        if policy is None:
            policy = parsed_email_policy
        super().__init__(policy=policy)

    raw_message_source: Optional[bytes] = None


    #
    # Additional public constructors
    #

    @classmethod
    def from_bytes(
            cls,
            raw_message_source: bytes,
            ) -> 'ParsedEmailMessage':

        msg = email.message_from_bytes(raw_message_source, policy=parsed_email_policy)
        msg.raw_message_source = raw_message_source
        assert isinstance(msg, ParsedEmailMessage)
        return msg


    @classmethod
    def from_binary_file(
            cls,
            stream_or_path: Union[SupportsRead[bytes], FilePath],
            ) -> 'ParsedEmailMessage':

        raw_message_source = cls.__read_bytes_from(stream_or_path)
        return cls.from_bytes(raw_message_source)


    #
    # Additional public helper methods
    #

    def get_utc_datetime(self) -> Optional[datetime.datetime]:
        """
        Get the *Date* of the message converted to a "naive"
        `datetime.datetime` representing a UTC date+time (if
        *Date* is present; otherwise `None` will be returned).
        """
        header = self['Date']
        if header is None:
            return None
        return datetime_utc_normalize(header.datetime)


    def get_timestamp(self) -> Optional[float]:
        """
        Get the *Date* of the message, converted to a `float`
        representing a UNIX timestamp (if *Date* is present;
        otherwise `None` will be returned).
        """
        header = self['Date']
        if header is None:
            return None
        return timestamp_from_datetime(header.datetime)


    def get_subject(self, *, normalize_whitespace: bool = True) -> Optional[str]:
        """
        Get the *Subject* of the message, as a `str` (if present;
        otherwise `None` will be returned).

        If the `normalize_whitespace` argument is true (it is by default)
        then any leading/trailing whitespace characters are removed and
        any other series of whitespace characters are normalized to single
        spaces.
        """
        header = self['Subject']
        if header is None:
            return None
        if normalize_whitespace:
            return ' '.join(header.split())
        return str(header)


    def find_content(
            self,
            *,
            content_type: Optional[ContentTypeCriteria] = '*',
            filename_regex: Optional[FilenameRegexCriteria] = None,
            content_regex: Optional[ContentRegexCriteria] = None,
            default_regex_flags: re.RegexFlag = (re.MULTILINE | re.DOTALL),
            force_content_as: Optional[ForcedTypeIndication] = None,
            ignore_extra_matches: bool = False,
            ) -> Optional[Content]:

        """
        Try to find (recursively) exactly one "leaf" (non-composite)
        component of the e-mail message -- such one that matches all
        specified filtering criteria. You can specify them with the
        following keyword arguments, each optional:

        * `content_type` -- being a `str` specifying a MIME content
          type, such as `"text/plain"` (the subtype part can be a
          wildcard, as in `"text/*"`; there can also be given a general
          wildcard, `"*"`, which matches all MIME content types -- and
          this is the default), or a member of the `ExtractFrom` enum
          (see the docs of the `find_filename_content_pairs()` method...);
          multiple alternatives can be given as a list;

        * `filename_regex` -- being a `str`-based regular expression
          (i.e., either a `re.Pattern` based on a `str`, or just a bare
          `str`), to be matched against filenames of message components;
          multiple alternatives can be given as a list; if not given at
          all, there will be no filename-regex-based filtering;

          note that a message component may have no filename associated
          with it -- then the filename will be considered empty (so, for
          example, the `^$` regex will match it);

        * `content_regex` -- being a `str`-or-`bytes`-based regular
          expression (i.e., either a `str`/`bytes`-based `re.Pattern`,
          or just a bare `str` or `bytes` object), to be matched against
          contents (*aka* payloads) of message components; multiple
          alternatives can be given as a list; if not given at all,
          there will be no content-regex-based filtering;

          it should be emphasized that an attempt to match a `str`-based
          regex against a `bytes` content, or to match a `bytes`-based
          regex against a `str` content *can never be successful*
          (what happens in such cases depends on the value of the
          `force_content_as` argument -- see the relevant parts of
          the docs of the method `find_filename_content_pairs()`...).

        Flags specified as `default_regex_flags` will be used to compile
        any regular expressions given in a non-compiled form (that is,
        specified as bare `str` or `bytes` objects).

        ***

        This method returns the content (*aka* payload) of the matching
        message component. The returned value is a `bytes` or `str`
        object, or `None`.

        More precisely: the `find_filename_content_pairs()` method is
        called, and the first item yielded by the resultant iterator is
        taken into consideration; that item is supposed to be a pair
        (2-tuple). The second element of that pair -- being the content
        of the found component -- becomes the final output; it may be a
        `bytes` or `str` object (for more information, see those parts
        of the docs of the `find_filename_content_pairs()` method which
        describe the `force_content_as` argument...).

        If no matching component is found, `None` is the output.

        If there are more matching components than one, a `ValueError`
        is raised -- unless the `ignore_extra_matches` argument has been
        explicitly set to `True` (then the content of the first matching
        component is returned).
        """

        items = self.find_filename_content_pairs(
            content_type=content_type,
            filename_regex=filename_regex,
            content_regex=content_regex,
            default_regex_flags=default_regex_flags,
            force_content_as=force_content_as)

        _, content = next(items, (None, None))

        if (not ignore_extra_matches) and next(items, None) is not None:
            raise ValueError(  # TODO: introduce a specific subclass of `ValueError`...
                f'multiple components of the message match '
                f'the following criteria: {content_type=!a}, '
                f'{filename_regex=!a} {content_regex=!a}, '
                f'(this error has been raised because '
                f'{ignore_extra_matches=!a})')

        return content


    def find_filename_content_pairs(
            self,
            *,
            content_type: Optional[ContentTypeCriteria] = '*',
            filename_regex: Optional[FilenameRegexCriteria] = None,
            content_regex: Optional[ContentRegexCriteria] = None,
            default_regex_flags: re.RegexFlag = (re.MULTILINE | re.DOTALL),
            force_content_as: Optional[ForcedTypeIndication] = None,
            ) -> Iterator[tuple[str, Content]]:

        """
        Find recursively those "leaf" (non-composite) components of the
        e-mail message which match all specified filtering criteria.
        You can specify them with the following keyword arguments, each
        optional:

        * `content_type` -- being a `str` specifying a MIME content
          type, such as `"text/plain"` (the subtype part can be a
          wildcard, as in `"text/*"`; there can also be given a general
          wildcard, `"*"`, which matches all MIME content types -- and
          this is the default), or a member of the `ExtractFrom` enum
          (see below...); multiple alternatives can be given as a list;

        * `filename_regex` -- being a `str`-based regular expression
          (i.e., either a `re.Pattern` based on a `str`, or just a bare
          `str`), to be matched against filenames of message components;
          multiple alternatives can be given as a list; if not given at
          all, there will be no filename-regex-based filtering;

          note that a message component may have no filename associated
          with it -- then the filename will be considered empty (so, for
          example, the `^$` regex will match it);

        * `content_regex` -- being a `str`-or-`bytes`-based regular
          expression (i.e., either a `str`/`bytes`-based `re.Pattern`,
          or just a bare `str` or `bytes` object), to be matched against
          contents (*aka* payloads) of message components; multiple
          alternatives can be given as a list; if not given at all,
          there will be no content-regex-based filtering;

          it should be emphasized that an attempt to match a `str`-based
          regex against a `bytes` content, or to match a `bytes`-based
          regex against a `str` content *can never be successful*
          (what happens in such cases depends on the value of the
          `force_content_as` argument -- see below...).

        Flags specified as `default_regex_flags` will be used to compile
        any regular expressions given in a non-compiled form (that is,
        specified as bare `str` or `bytes` objects).

        ***

        This method returns an iterator that yields zero or more output
        items, representing those "leaf" components which match the
        specified filtering criteria. Each of the output items is an
        `(<filename>, <content>)` pair -- where:

        * `<filename>` is a `str`;

          **note:** it will be empty if no filename is associated with
          the represented message component;

          also, **note** that filenames are *not* sanitized/escaped in
          any way; they may contain arbitrary characters, in particular
          those having a special meaning in filesystem paths or shell
          scripts; **beware** maliciously formed filenames, especially
          if the e-mail being parsed originates from an untrusted
          source: remember to sanitize them before engaging them in
          any actual filesystem or shell-related operations;

        * `<content>` is just the content (*aka* payload) of the
          represented message component; it is an instance of:

          * `bytes` or `str`, adequately for the component's MIME
            content type (`bytes` for binary ones, `str` for textual)

            -- if the `force_content_as` argument is `None` which is its
            default value

            (in this case, any content-type-specific processing, e.g.,
            the `text/*`-specific newline normalization provided by the
            default policy's `content_manager`, is applied appropriately;
            any `content_regex`-based filtering is attempted *only
            after* those transformations);

          * always `bytes`

            -- if the `force_content_as` argument is `bytes`;

            (**warning:** in this case, *all* contents are retrieved as
            raw binary data, i.e., *without* any content-type-specific
            processing, in particular *without* engaging the policy's
            `content_manager` at all; *CTE*-decoding is being done, but
            not much more...);

          * always `str`

            -- if the `force_content_as` argument is `str`

            (in this case, **first**, any content-type-specific
            processing, including appropriate processing provided
            by the policy's `content_manager`, is applied as usual;
            **then, however**, if the component's content type is
            a *binary* one, i.e., *not* a textual one, the `utf-8`
            encoding with the *lossy* `replace` error handler is used
            to decode the content from `bytes` to `str`; *note* that
            any `content_regex`-based filtering is attempted *only
            after* those transformations).

        *Important:* if the `force_content_as` argument is *not* `None`,
        the regular expression(s) specified as `content_regex` (if
        given) must be based on the appropriate type (`str`-based for
        `str`; `bytes`-based for `bytes`) -- otherwise a `TypeError`
        will be raised when regex matching is attempted. On the other
        hand, if `force_content_as` is `None` (which is the default),
        only a warning will be logged (and the particular regex match
        will be deemed unsuccessful) when such a *content-vs-regex*
        type discrepancy is encountered.

        *Another thing to note:* if no filtering criteria are specified
        (that is, `content_type`, `filename_regex` and `content_regex`
        are not given at all), the output will include *all* "leaf"
        components of the message.

        ***

        The `content_type` argument, apart from being (or containing) a
        `str` specifying a MIME content type, can also be (or contain)
        an `ExtractFrom` enum member -- as a special marker.

        Note that if `content_type` is a list, it can contain any number
        of markers of that kind (and, obviously, also any number of
        strings specifying MIME content types).

        If such an `ExtractFrom` marker is...

        * ...`ExtractFrom.ZIP`, then all files are unpacked from *every*
          message component qualified as a ZIP archive (on the grounds
          of its MIME content type or, possibly, its filename suffix,
          regardless of any specified filtering criteria or nesting
          level). Each of the unpacked (extracted) files is included as
          a separate candidate for an output item -- being subject to
          `filename_regex`/`content_regex`-based filtering; its filename
          is derived from the original ZIP archive component's filename
          *and* the individual name extracted from the archive (for the
          details, see the relevant code comments in this module...).
          Also, note that each of the unpacked files is treated as if
          it was a binary message component, no matter what its content
          actually represents.

        * ...`ExtractFrom.GZIP` or `ExtractFrom.BZIP2`, then
          *every* message component qualified -- respectively -- as
          *gzip*-ed or *bzip2*-ed data (on the grounds of its MIME
          content type or, possibly, its filename suffix, regardless
          of any specified filtering criteria or nesting level) is
          decompressed. The result of decompression is included as
          a separate candidate for an output item -- being subject to
          `filename_regex`/`content_regex`-based filtering; its filename
          is derived from the original *gzip*-ed or *bzip2*-ed data
          component's filename (for details see the relevant code
          comments in this module...); also, note that it is treated
          as if it was a binary message component, no matter what its
          content actually represents.

        Any unpacking/decompression errors are logged as warnings and
        skipped.

        If the `content_type` argument is not given, *no extraction*
        from ZIP/*gzip*/*bzip2* message components is attempted at all
        (in other words, extraction needs to be requested explicitly).
        """

        (content_type_alternatives,
         allowed_to_extract_from) = self.__split_content_type_requirements(content_type)

        results = (
            (filename, content)
            for msg in self.walk()
                for filename, content in self.__generate_from_msg(
                    msg,
                    content_type_alternatives,
                    allowed_to_extract_from,
                    force_content_as))

        if filename_regex is not None:
            results = self.__filter_by_filename_regex(
                results,
                filename_regex,
                default_regex_flags)

        if content_regex is not None:
            results = self.__filter_by_content_regex(
                results,
                content_regex,
                default_regex_flags,
                raise_type_error=(force_content_as is not None))

        yield from results


    #
    # Internal constants and helpers
    #

    _DECOMPRESSION_FUNCTIONS: ClassVar[Mapping[ExtractFrom, Callable[[bytes], bytes]]] = {
        GZIP: gzip.decompress,
        BZIP2: bz2.decompress,
    }


    @staticmethod
    def __read_bytes_from(
            stream_or_path: Union[SupportsRead[AnyStr], FilePath],
            ) -> bytes:

        if isinstance(stream_or_path, (str, bytes, os.PathLike)):
            return read_file(stream_or_path, 'rb')
        else:
            return b''.join(iter(stream_or_path.read, b''))


    @staticmethod
    def __split_content_type_requirements(
            content_type: Optional[ContentTypeCriteria],
            ) -> tuple[Sequence[str], Set[ExtractFrom]]:

        if content_type is None:
            # For interface consistency, we accept `None` as equivalent
            # to passing the default value `"*"` which is a content type
            # wildcard symbol: any MIME content types will be *included*
            # (but that does not extend to requesting *extraction* from
            # ZIP, *gzip* or *bzip2* -- that needs to be specified
            # explicitly with `ExtractFrom` marker object(s)).
            content_type = '*'

        seq = (
            (content_type,) if isinstance(content_type, (str, ExtractFrom))

            # Let's explicitly convert it to a sequence (just in case some
            # client code passed a one-time-use iterable, e.g., an iterator).
            else tuple(content_type))

        content_type_alternatives = [ctp for ctp in seq if not isinstance(ctp, ExtractFrom)]
        allowed_to_extract_from = {exf for exf in seq if isinstance(exf, ExtractFrom)}

        return content_type_alternatives, allowed_to_extract_from


    @classmethod
    def __generate_from_msg(
            cls,
            msg: email.message.EmailMessage,
            content_type_alternatives: Sequence[str],
            allowed_to_extract_from: Set[ExtractFrom],
            force_content_as: Optional[ForcedTypeIndication],
            ) -> Iterator[tuple[str, Content]]:

        if msg.is_multipart():
            return

        if not isinstance(msg, email.message.EmailMessage):
            # (we require this because we use some parts
            # of the `EmailMessage`'s modern interface)
            raise TypeError(
                f'object {msg!a} is not an instance of '
                f'{email.message.EmailMessage.__qualname__}')

        for filename, content in cls.__generate_raw_from_msg(
            msg,
            content_type_alternatives,
            allowed_to_extract_from,
            force_content_as,
        ):
            if force_content_as in (str, 'str'):
                content = as_unicode(content, decode_error_handling='replace')   # maybe TODO: change to `surrogateescape`?

            assert isinstance(filename, str)
            assert (force_content_as is None and isinstance(content, (bytes, str))
                    or force_content_as in (bytes, 'bytes') and isinstance(content, bytes)
                    or force_content_as in (str, 'str') and isinstance(content, str))

            LOGGER.debug('Yielding an item with filename=%a...', filename)
            yield filename, content


    @classmethod
    def __generate_raw_from_msg(
            cls,
            msg: email.message.EmailMessage,
            content_type_alternatives: Sequence[str],
            allowed_to_extract_from: Set[ExtractFrom],
            force_content_as: Optional[ForcedTypeIndication],
            ) -> Iterator[tuple[str, Content]]:

        msg_content_type = msg.get_content_type()
        assert (isinstance(msg_content_type, str)
                and msg_content_type == msg_content_type.lower())

        content_type_matches = cls.__does_msg_content_type_match(
            msg_content_type,
            content_type_alternatives)

        msg_content_maintype = msg.get_content_maintype()
        assert (isinstance(msg_content_maintype, str)
                and msg_content_type.startswith(f'{msg_content_maintype}/'))

        msg_filename = msg.get_filename() or ''
        assert isinstance(msg_filename, str)

        try_to_extract_from = set()
        if allowed_to_extract_from and msg_content_maintype != 'text':
            msg_filename_extension = cls.__get_filename_extension(msg_filename)
            try_to_extract_from.update(
                exf for exf in allowed_to_extract_from
                if (msg_content_type in cls.EXTRACTABLE_CONTENT_TYPES[exf]
                    or msg_filename_extension in cls.EXTRACTABLE_FILENAME_EXTENSIONS[exf]))

        if content_type_matches or try_to_extract_from:
            msg_content = cls.__get_msg_content(msg, force_content_as)

            if try_to_extract_from:
                assert isinstance(msg_content, bytes)

                if cls.ZIP in try_to_extract_from:
                    yield from cls.__extract_from_zip(
                        msg_filename,
                        msg_content)

                for exf, decompression_func in cls._DECOMPRESSION_FUNCTIONS.items():
                    if exf in try_to_extract_from:
                        yield from cls.__extract_from_compressed(
                            msg_filename,
                            msg_content,
                            exf,
                            decompression_func)

            if content_type_matches:
                yield msg_filename, msg_content


    @staticmethod
    def __does_msg_content_type_match(
            msg_content_type: str,
            content_type_alternatives: Sequence[str],
            ) -> bool:

        assert msg_content_type == msg_content_type.lower()
        msg_maintype, _, msg_subtype = msg_content_type.partition('/')

        for ctp in content_type_alternatives:
            if ctp in ('*', '*/', '*/*'):
                return True
            maintype, _, subtype = ctp.lower().partition('/')
            if maintype == msg_maintype and subtype in ('', '*', msg_subtype):
                return True

        return False


    @classmethod
    def __get_msg_content(
            cls,
            msg: email.message.EmailMessage,
            force_content_as: Optional[ForcedTypeIndication],
            ) -> Content:

        assert not msg.is_multipart()  # (already ensured in `__generate_from_msg()`)

        if force_content_as in (bytes, 'bytes'):
            msg_content = msg.get_payload(decode=True)
            assert isinstance(msg_content, bytes)

        elif force_content_as is None or force_content_as in (str, 'str'):
            try:
                msg_content = msg.get_content()
            except KeyError as err:
                LOGGER.warning(
                    'Got an error (%s) when trying to get the content '
                    'of the message component %a (one of the possible '
                    'causes is that some multipart-boundary-related '
                    'stuff in the original raw message is malformed). '
                    'Falling back to getting it as binary data...',
                    make_exc_ascii_str(err), msg)
                msg_content = msg.get_payload(decode=True)
                assert isinstance(msg_content, bytes)
            else:
                tp = type(msg_content)
                if msg.get_content_maintype() == 'text':
                    if not issubclass(tp, str):
                        raise NotImplementedError(
                            f"the message's content type is *textual* "
                            f"({msg.get_content_type()!a}) and the "
                            f"method `get_content()` returned an object "
                            f"*not* being a str instance (its type is: "
                            f"{tp.__qualname__}; do you use a message "
                            f"policy with a custom content manager?); "
                            f"unfortunately, that's not supported by "
                            f"the current implementation of "
                            f"{cls.__qualname__}'")
                elif not issubclass(tp, bytes):
                    raise NotImplementedError(
                        f"the message's content type "
                        f"({msg.get_content_type()!a}) is not textual, "
                        f"so it is considered a *binary* one, and the "
                        f"method `get_content()` returned an object "
                        f"*not* being a bytes instance (its type is: "
                        f"{tp.__qualname__}; do you use a message "
                        f"policy with a custom content manager?); "
                        f"unfortunately, that's not supported by "
                        f"the current implementation of "
                        f"{cls.__qualname__}'")

            # Note: if `msg_content` is an instance of `bytes` and
            # `force_content_as` is `str` (or `"str"`) then coercion of
            # `msg_content` to `str` will be done in `__generate_from_msg()`
            # (*after* possible content extraction from ZIP/*gzip*/*bzip2*).
            assert isinstance(msg_content, (bytes, str))

        else:
            raise TypeError(f'{force_content_as=!a} (should be None, bytes or str')

        return msg_content


    @classmethod
    def __extract_from_zip(
            cls,
            msg_filename: str,
            msg_content: bytes,
            ) -> Iterator[tuple[str, bytes]]:

        msg_filename_repr = (
            ascii(msg_filename) if msg_filename
            else '<with unspecified or empty filename>')

        try:
            names_and_contents = sorted(iter_unzip_from_bytes(msg_content))
        except Exception as err:  # noqa
            LOGGER.warning(
                'Could not unpack content from the ZIP archive %s (%s).',
                msg_filename_repr, make_exc_ascii_str(err))
        else:
            if names_and_contents:
                # All files from the archive are yielded -- with their base
                # names (i.e., names without directory parts) prefixed with
                # the archive filename + '/' (or with `_ZIP/` if the archive's
                # filename was unspecified/empty). The resultant `(filename,
                # content)` pairs are sorted, that is, they are yielded in
                # the lexicographic order.
                filename_prefix = (msg_filename or '_ZIP') + '/'
                for name, content in names_and_contents:
                    filename = filename_prefix + name
                    yield filename, content
            else:
                LOGGER.warning(
                    'No files in the ZIP archive %s.',
                    msg_filename_repr)


    @classmethod
    def __extract_from_compressed(
            cls,
            msg_filename: str,
            msg_content: bytes,
            compression_format: ExtractFrom,
            decompression_func: Callable[[bytes], bytes],
            ) -> Iterator[tuple[str, bytes]]:

        msg_filename_repr = (
            ascii(msg_filename) if msg_filename
            else '<with unspecified or empty filename>')

        try:
            decompressed_content = decompression_func(msg_content)
        except Exception as err:  # noqa
            LOGGER.warning(
                f'Could not decompress {compression_format}'
                f'-compressed content of part %s (%s).',
                msg_filename_repr, make_exc_ascii_str(err))
        else:
            filename = cls.__format_filename_for_decompressed(msg_filename, compression_format)
            yield filename, decompressed_content


    @classmethod
    def __format_filename_for_decompressed(
            cls,
            msg_filename: str,
            compression_format: ExtractFrom,
            ) -> str:

        # If the filename includes a suffix (extension) which is
        # specific to the compression format, return the same name with
        # that suffix *removed*; otherwise, return the same name with
        # *prepended* `_<compression format label>_DECOMPRESSED_` (e.g.,
        # `_GZIP_DECOMPRESSED_some_name`).
        extension = cls.__get_filename_extension(msg_filename)
        if extension in cls.EXTRACTABLE_FILENAME_EXTENSIONS[compression_format]:
            return cls.__get_filename_with_removed_extension(msg_filename, extension)
        return f'_{compression_format.name}_DECOMPRESSED_{msg_filename}'


    @staticmethod
    def __get_filename_extension(
            filename: str,
            ) -> str:

        if filename:
            suffix = pathlib.PurePosixPath(filename).suffix
            # (let's guard against certain corner
            # cases: a name with trailing `/`, etc.)
            if suffix and filename.endswith(suffix):
                assert (suffix.startswith('.')
                        and len(filename) > len(suffix))
                return suffix.lower()

        return ''


    @staticmethod
    def __get_filename_with_removed_extension(
            filename: str,
            extension: str,
            ) -> str:

        assert (filename
                and extension.startswith('.'))

        suffix = pathlib.PurePosixPath(filename).suffix
        assert (suffix.lower() == extension
                and filename.endswith(suffix)
                and len(filename) > len(suffix))

        return filename[:-len(suffix)]


    @staticmethod
    def __filter_by_filename_regex(
            filename_content_pairs: Iterator[tuple[str, Content]],
            filename_regex: FilenameRegexCriteria,
            default_regex_flags: re.RegexFlag,
            ) -> Iterator[tuple[str, Content]]:

        filename_regex_seq = (
            # Note: a `bytes` object will later cause a `TypeError` anyway,
            # but here we want to prevent it from being converted to a tuple.
            (filename_regex,) if isinstance(filename_regex, (str, bytes, re.Pattern))

            # Let's explicitly convert it to a sequence (just in case some
            # client code passed a one-time-use iterable, e.g., an iterator).
            else tuple(filename_regex))

        for filename, content in filename_content_pairs:
            if first_regex_search(
                filename_regex_seq,
                filename,
                default_regex_flags,
                raise_type_error=True,
            ):
                yield filename, content


    @staticmethod
    def __filter_by_content_regex(
            filename_content_pairs: Iterator[tuple[str, Content]],
            content_regex: ContentRegexCriteria,
            default_regex_flags: re.RegexFlag,
            raise_type_error: bool,
            ) -> Iterator[tuple[str, Content]]:

        content_regex_seq = (
            (content_regex,) if isinstance(content_regex, (str, bytes, re.Pattern))

            # Let's explicitly convert it to a sequence (just in case some
            # client code passed a one-time-use iterable, e.g., an iterator).
            else tuple(content_regex))

        for filename, content in filename_content_pairs:
            if first_regex_search(
                content_regex_seq,
                content,
                default_regex_flags,
                raise_type_error=raise_type_error,
            ):
                yield filename, content


class ContentManagerAdjustableWrapper(ContentManagerLike):

    def __init__(
            self,
            wrapped_manager: ContentManagerLike, *,
            output_content_adjuster: OutputContentAdjuster):

        self._wrapped_manager = wrapped_manager
        self._output_content_adjuster = output_content_adjuster

    def get_content(
            self,
            msg: email.message.Message,
            *args: Any,
            **kwargs: Any,
            ) -> Any:

        orig_output_content = self._wrapped_manager.get_content(msg, *args, **kwargs)
        return self._output_content_adjuster(
            msg, *args, **kwargs,
            orig_output_content=orig_output_content)

    def set_content(
            self,
            msg: email.message.Message,
            obj: Any,
            *args: Any,
            **kwargs: Any,
            ) -> Any:

        return self._wrapped_manager.set_content(msg, obj, *args, **kwargs)

newline_normalizing_wrapper_of_raw_data_manager = ContentManagerAdjustableWrapper(
    wrapped_manager=email.contentmanager.raw_data_manager,
    output_content_adjuster=(
        lambda msg, *_, orig_output_content, **__: (
            '\n'.join(splitlines_asc(orig_output_content, append_empty_ending=True))
            if msg.get_content_maintype() == 'text'
            else orig_output_content)))


class ParsedEmailPolicy(email.policy.EmailPolicy):

    # `email.policy.EmailPolicy`-specific customizable attributes:
    message_factory = ParsedEmailMessage
    content_manager = newline_normalizing_wrapper_of_raw_data_manager

    # This-class-specific customizable attribute:
    defect_log_level: Optional[int] = logging.WARNING

    def register_defect(
            self,
            obj: email.message.Message,
            defect: email.errors.MessageDefect,
            ) -> None:

        super().register_defect(obj, defect)
        if self.defect_log_level is not None:
            LOGGER.log(
                self.defect_log_level,
                'An e-mail message defect has been found (%s).',
                self.__format_defect_repr(defect))

    def __format_defect_repr(
            self,
            defect: email.errors.MessageDefect,
            ) -> str:

        defect_class_name = defect.__class__.__name__
        defect_msg = str(defect)
        return ascii_str(
            f'{defect_class_name}: {defect_msg}' if defect_msg
            else defect_class_name)

parsed_email_policy = ParsedEmailPolicy()


def first_regex_search(
        regex: ContentRegexCriteria,
        content: Content,
        default_regex_flags: re.RegexFlag = re.MULTILINE | re.DOTALL,
        *,
        raise_type_error: bool = True,
        ) -> Optional[re.Match]:

    for match in iter_regex_searches(
        regex,
        content,
        default_regex_flags,
        raise_type_error=raise_type_error,
    ):
        return match
    return None


def iter_regex_searches(
        regex: ContentRegexCriteria,
        content: Content,
        default_regex_flags: re.RegexFlag = re.MULTILINE | re.DOTALL,
        *,
        raise_type_error: bool = True,
        ) -> Iterator[re.Match]:

    if isinstance(regex, (str, bytes, re.Pattern)):
        regex = (regex,)

    for r in regex:
        if isinstance(r, (str, bytes)):
            r = re.compile(r, default_regex_flags)
        try:
            yield from r.finditer(content)
        except TypeError as err:
            if raise_type_error:
                raise
            type_name = ascii_str(type(content).__name__)
            LOGGER.warning(
                'Could not match the regex %a against content being '
                'a %s (%s).', r, type_name, make_exc_ascii_str(err))
