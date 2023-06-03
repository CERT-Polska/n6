# Copyright (c) 2013-2023 NASK. All rights reserved.

import email.generator
import email.message
import email.policy
import enum
import io
import re
import tempfile
import unittest
from collections.abc import Iterator

from unittest_expander import (
    expand,
    foreach,
    param,
    paramseq,
)

from n6lib.common_helpers import (
    as_bytes,
    as_unicode,
)
from n6lib.mail_parsing_helpers import (
    ExtractFrom,
    LOGGER as module_logger,
    ParsedEmailMessage,
    parsed_email_policy,
)
from n6lib.tests.test_mail_parsing_helpers__data import (
    ALL_EXTRACTED_FILES_SELECTION,
    ALL_LEAF_COMPONENTS_SELECTION,
    ALL_RESULTS_SELECTION,
    ALL_WARNINGS_SELECTION,
    EXPECTED_CONTENT_TYPE,
    EXPECTED_HEADERS,
    EXPECTED_MSG_PARSING_LOG_WARN_REGEXES,
    EXPECTED_NUMBER_OF_ALL_EXTRACTED_FILES,
    EXPECTED_NUMBER_OF_ALL_LEAF_COMPONENTS,
    EXPECTED_NUMBER_OF_ALL_LEAF_COMPONENTS_AND_EXTRACTED_FILES,
    EXPECTED_SUBJECT_UNNORMALIZED,
    EXPECTED_SUBJECT_WITH_NORMALIZED_WHITESPACE,
    EXPECTED_TIMESTAMP,
    EXPECTED_UTC_DATETIME,
    RAW_MSG_SOURCE,
    TEST_MSG_KEYS,
    select_expected_results,
    select_expected_warn_regexes,
)
from n6lib.unit_test_helpers import TestCaseMixin


class _BaseTestCase(TestCaseMixin, unittest.TestCase):

    def setUp(self):
        self.ALL_EXTRACT_MARKERS: list = list(ExtractFrom.__members__.values())
        assert self.ALL_EXTRACT_MARKERS == [
            ExtractFrom.ZIP,
            ExtractFrom.GZIP,
            ExtractFrom.BZIP2,
        ]


class TestExtractFrom(_BaseTestCase):

    def test_enum_basics(self):
        assert issubclass(ExtractFrom, enum.Enum)
        assert all(isinstance(exf, ExtractFrom) for exf in self.ALL_EXTRACT_MARKERS)
        assert {exf: (exf.name, exf.value) for exf in self.ALL_EXTRACT_MARKERS} == {
            ExtractFrom.ZIP: ('ZIP', 'ZIP'),
            ExtractFrom.GZIP: ('GZIP', '*gzip*'),
            ExtractFrom.BZIP2: ('BZIP2', '*bzip2*'),
        }

    def test_str(self):
        assert {exf: str(exf) for exf in self.ALL_EXTRACT_MARKERS} == {
            ExtractFrom.ZIP: 'ZIP',
            ExtractFrom.GZIP: '*gzip*',
            ExtractFrom.BZIP2: '*bzip2*',
        }

    def test_repr(self):
        assert {exf: repr(exf) for exf in self.ALL_EXTRACT_MARKERS} == {
            ExtractFrom.ZIP: 'ExtractFrom.ZIP',
            ExtractFrom.GZIP: 'ExtractFrom.GZIP',
            ExtractFrom.BZIP2: 'ExtractFrom.BZIP2',
        }


# Note: many `TestParsedEmailMessage_*` tests, apart from testing
# functionalities provided by `ParsedEmailMessage` itself, test also
# (indirectly) most important functionalities of `ParsedEmailPolicy`,
# `ContentManagerAdjustableWrapper`, `first_regex_search()` and
# `iter_regex_searches()`.

@expand
class TestParsedEmailMessage__constructors_and_basics(_BaseTestCase):  # noqa

    @foreach(
        param(),
        param(
            constructor_args=[
                parsed_email_policy,
            ],
        ),
        param(
            constructor_args=[
                email.policy.default,
            ],
        ),
        param(
            constructor_kwargs=dict(
                policy=parsed_email_policy.clone(linesep='\r\n'),
            ),
        ),
        param(
            constructor_kwargs=dict(
                policy=email.policy.SMTP,
            ),
        ),
    )
    def test_standard_constructor_and_basics(self, constructor_args=(), constructor_kwargs=None):
        if constructor_kwargs is None:
            constructor_kwargs = {}
        expected_warn_regexes = []
        expected_policy_type = type(
            constructor_args[0] if constructor_args
            else constructor_kwargs.get('policy', parsed_email_policy))

        with self.assertLogWarningRegexes(module_logger, expected_warn_regexes):
            msg = ParsedEmailMessage(*constructor_args, **constructor_kwargs)

        assert (issubclass(ParsedEmailMessage, email.message.Message)
                and issubclass(ParsedEmailMessage, email.message.EmailMessage))
        assert (isinstance(msg, email.message.Message)
                and isinstance(msg, email.message.EmailMessage)
                and isinstance(msg, ParsedEmailMessage))
        assert isinstance(msg.policy, expected_policy_type)
        assert msg.raw_message_source is None


    @paramseq
    def _invocations_of_our_parsing_constructors():  # noqa
        def from_binary_file_passing_stream(raw_message_source):
            stream = io.BytesIO(raw_message_source)
            return ParsedEmailMessage.from_binary_file(stream)

        def from_binary_file_passing_path(raw_message_source, temp_binary_file):
            temp_binary_file.write(raw_message_source)
            temp_binary_file.flush()
            path = temp_binary_file.name
            return ParsedEmailMessage.from_binary_file(path)

        return [
            param(invoke_constructor=ParsedEmailMessage.from_bytes)
              .label('from_bytes(...)'),

            param(invoke_constructor=from_binary_file_passing_stream)
              .label('from_binary_file(stream)'),

            param(invoke_constructor=from_binary_file_passing_path)
              .context(tempfile.NamedTemporaryFile, 'wb')
              .label('from_binary_file(path)'),
        ]

    @foreach(_invocations_of_our_parsing_constructors)
    @foreach(TEST_MSG_KEYS)
    def test_parsing_constructors(self, key, invoke_constructor, context_targets):
        expected_warn_regexes = EXPECTED_MSG_PARSING_LOG_WARN_REGEXES[key]

        with self.assertLogWarningRegexes(module_logger, expected_warn_regexes):
            msg = invoke_constructor(RAW_MSG_SOURCE[key], *context_targets)

        assert (isinstance(msg, email.message.Message)
                and isinstance(msg, email.message.EmailMessage)
                and isinstance(msg, ParsedEmailMessage))
        assert msg.raw_message_source == RAW_MSG_SOURCE[key]
        assert list(msg.find_filename_content_pairs(
            content_type=['*'] + self.ALL_EXTRACT_MARKERS,   # <- match everything
        )) == select_expected_results(key, **ALL_RESULTS_SELECTION)


    @foreach(TEST_MSG_KEYS)
    def test_some_of_operations_provided_by_base_classes(self, key):
        msg = ParsedEmailMessage.from_bytes(RAW_MSG_SOURCE[key])
        expected_warn_regexes = []

        # Testing selected standard operations (provided
        # by `email.message.EmailMessage` et consortes):

        with self.assertLogWarningRegexes(module_logger, expected_warn_regexes):
            assert msg.get_content_type() == EXPECTED_CONTENT_TYPE[key]

            msg_header_names = msg.keys()
            for i, (header_name, expected_value) in enumerate(EXPECTED_HEADERS[key]):
                assert header_name.lower() == msg_header_names[i].lower()
                assert msg[header_name] == expected_value
            assert len(msg_header_names) == len(EXPECTED_HEADERS[key])

            for component_msg in msg.walk():
                assert isinstance(component_msg, ParsedEmailMessage)


    @foreach(TEST_MSG_KEYS)
    def test_basics_of_rfc_compliant_flattening(self, key):
        raw_message_source = RAW_MSG_SOURCE[key]
        msg = ParsedEmailMessage.from_bytes(raw_message_source)
        bytes_io = io.BytesIO()
        gen = email.generator.BytesGenerator(
            bytes_io,
            policy=msg.policy.clone(linesep='\r\n'))  # (requesting RFC-compliant line separators)

        gen.flatten(msg)
        result = bytes_io.getvalue()

        if key == 'SIMPLE':
            assert result == raw_message_source
        assert (len(re.findall(rb'\r\n', result))   # (indeed, line separators are RFC-compliant)
                == len(re.findall(rb'\r', result))
                == len(re.findall(rb'\n', result)))


@expand
class TestParsedEmailMessage__simple_methods(_BaseTestCase):  # noqa

    # In this test class, we test simple methods provided by
    # `ParsedEmailMessage`.

    @foreach(TEST_MSG_KEYS)
    def test_get_utc_datetime(self, key):
        msg = ParsedEmailMessage.from_bytes(RAW_MSG_SOURCE[key])
        expected_warn_regexes = []

        with self.assertLogWarningRegexes(module_logger, expected_warn_regexes):
            result = msg.get_utc_datetime()

        assert result == EXPECTED_UTC_DATETIME[key]


    @foreach(TEST_MSG_KEYS)
    def test_get_timestamp(self, key):
        msg = ParsedEmailMessage.from_bytes(RAW_MSG_SOURCE[key])
        expected_warn_regexes = []

        with self.assertLogWarningRegexes(module_logger, expected_warn_regexes):
            result = msg.get_timestamp()

        assert result == EXPECTED_TIMESTAMP[key]


    @foreach(
        param(
            kwargs=dict(),
            key_to_expected_result=EXPECTED_SUBJECT_WITH_NORMALIZED_WHITESPACE,
        ),

        param(
            kwargs=dict(normalize_whitespace=True),
            key_to_expected_result=EXPECTED_SUBJECT_WITH_NORMALIZED_WHITESPACE,
        ),

        param(
            kwargs=dict(normalize_whitespace=False),
            key_to_expected_result=EXPECTED_SUBJECT_UNNORMALIZED,
        ),
    )
    @foreach(TEST_MSG_KEYS)
    def test_get_subject(self, key, kwargs, key_to_expected_result):
        msg = ParsedEmailMessage.from_bytes(RAW_MSG_SOURCE[key])
        expected_warn_regexes = []

        with self.assertLogWarningRegexes(module_logger, expected_warn_regexes):
            result = msg.get_subject(**kwargs)

        assert result == key_to_expected_result[key]


@expand
class TestParsedEmailMessage_find_content(_BaseTestCase):  # noqa

    @foreach([key for key in TEST_MSG_KEYS if key != 'QUITE-COMPLEX'])
    def test_without_arguments__exactly_one_match(self, key):
        assert EXPECTED_NUMBER_OF_ALL_LEAF_COMPONENTS[key] == 1, 'test code expectation'
        msg = ParsedEmailMessage.from_bytes(RAW_MSG_SOURCE[key])
        expected_warn_regexes = select_expected_warn_regexes(
            key,
            by_substring={
                'WITH-BROKEN-BOUNDARY': 'when trying to get the content of',
                'WITH-DEFECTIVE-BASE64-CTE': {
                    'InvalidBase64CharactersDefect',
                    'InvalidBase64PaddingDefect',
                },
            })

        with self.assertLogWarningRegexes(module_logger, expected_warn_regexes):
            result = msg.find_content()

        assert result == select_expected_results(
            key,
            **ALL_LEAF_COMPONENTS_SELECTION,
            get_contents_only=True)[0]


    def test_without_arguments__multiple_matches(self):
        key = 'QUITE-COMPLEX'
        assert EXPECTED_NUMBER_OF_ALL_LEAF_COMPONENTS[key] > 1, 'test code expectation'
        msg = ParsedEmailMessage.from_bytes(RAW_MSG_SOURCE[key])

        with self.assertRaisesRegex(ValueError, r'^multiple components'):
            msg.find_content()


    @foreach(TEST_MSG_KEYS)
    def test_without_arguments_except_flag_ignore_extra_matches(self, key):
        assert (EXPECTED_NUMBER_OF_ALL_LEAF_COMPONENTS[key] > 1 if key == 'QUITE-COMPLEX'
                else EXPECTED_NUMBER_OF_ALL_LEAF_COMPONENTS[key] == 1), 'test code expectation'
        msg = ParsedEmailMessage.from_bytes(RAW_MSG_SOURCE[key])
        expected_warn_regexes = select_expected_warn_regexes(
            key,
            by_substring={
                'WITH-BROKEN-BOUNDARY': 'when trying to get the content of',
                'WITH-DEFECTIVE-BASE64-CTE': {
                    'InvalidBase64CharactersDefect',
                    'InvalidBase64PaddingDefect',
                },
            })

        with self.assertLogWarningRegexes(module_logger, expected_warn_regexes):
            result = msg.find_content(ignore_extra_matches=True)

        assert result == select_expected_results(
            key,
            **ALL_LEAF_COMPONENTS_SELECTION,
            get_contents_only=True)[0]


    @foreach(
        param(
            key='SIMPLE',
            filtering_criteria_related_kwargs=dict(
                content_type='text/plain',
                filename_regex=r'^$',
            ),
            expected_result_selection_tag='main body',
        ),

        param(
            key='QUITE-COMPLEX',
            filtering_criteria_related_kwargs=dict(
                content_type='text/plain',
                filename_regex=r'README[.]zip',
                content_regex=r'N6[.]$(?!.)',       # (would not match if flags weren't customized)
                default_regex_flags=re.IGNORECASE,  # <----------------------------------'
            ),
            expected_result_selection_tag='without explicit content type',
        ),

        param(
            key='QUITE-COMPLEX',
            filtering_criteria_related_kwargs=dict(
                content_type=ExtractFrom.ZIP,
                filename_regex=r'^test\.compressed-you-now/\.hgignore',
            ),
            expected_result_selection_tag='extracted from zip #1',
            expected_warn_regex_selection=dict(
                by_substring='Could not unpack',  # (from `gzip with wrong suffix`...)
            ),
        ),

        param(
            key='QUITE-COMPLEX',
            filtering_criteria_related_kwargs=dict(
                content_type=ExtractFrom.ZIP,
                filename_regex=r'^test\.compressed-you-now/README',
            ),
            expected_result_selection_tag='extracted from zip #2',
            expected_warn_regex_selection=dict(
                by_substring='Could not unpack',  # (from `gzip with wrong suffix`...)
            ),
        ),

        param(
            key='WITH-BROKEN-BOUNDARY',
            filtering_criteria_related_kwargs=dict(
                filename_regex=r'^$',
                content_regex=(
                    rb'^Content-Disposition: attachment; '
                    rb'filename=with_wrong_suffix\.Zip\r$'),
            ),
            expected_result_selection_tag='broken unparsed',
            expected_warn_regex_selection=dict(
                by_substring='when trying to get the content of',
            ),
        ),

        param(
            key='WITH-BROKEN-BOUNDARY',
            filtering_criteria_related_kwargs=dict(
                content_type='multipart/*',
                content_regex=(
                    r'^Content-Disposition: attachment; '
                    r'filename=with_wrong_suffix\.Zip\r$'),
                force_content_as=str,
            ),
            expected_result_selection_tag='broken unparsed',
            expected_result_coercion=lambda s: as_unicode(s, 'strict'),
            expected_warn_regex_selection=dict(
                by_substring='when trying to get the content of',
            ),
        ),
    )
    def test_with_some_filtering_criteria__exactly_one_match(
        self,
        key,
        filtering_criteria_related_kwargs,
        expected_result_selection_tag,
        expected_result_coercion=None,
        expected_warn_regex_selection=None,
    ):
        msg = ParsedEmailMessage.from_bytes(RAW_MSG_SOURCE[key])
        expected_warn_regexes = (
            select_expected_warn_regexes(key, **expected_warn_regex_selection)
            if expected_warn_regex_selection is not None
            else [])

        with self.assertLogWarningRegexes(module_logger, expected_warn_regexes):
            result = msg.find_content(**filtering_criteria_related_kwargs)

        assert result == select_expected_results(
            key,
            by_tag=expected_result_selection_tag,
            content_coercion=expected_result_coercion,
            get_contents_only=True)[0]


    @foreach(
        param(
            filtering_criteria_related_kwargs=dict(
                content_type='text/*',
                filename_regex=r'README',
                content_regex=r'N6[.]$(?!.)',       # (would not match if flags weren't customized)
                default_regex_flags=re.IGNORECASE,  # <----------------------------------'
            ),
        ),

        param(
            filtering_criteria_related_kwargs=dict(
                content_type=ExtractFrom.ZIP,
            ),
        ),

        param(
            filtering_criteria_related_kwargs=dict(
                content_type=ExtractFrom.ZIP,
                filename_regex=r'^test\.compressed-you-now/',
            ),
        ),
    )
    def test_with_some_filtering_criteria__multiple_matches(
        self,
        filtering_criteria_related_kwargs,
    ):
        key = 'QUITE-COMPLEX'
        msg = ParsedEmailMessage.from_bytes(RAW_MSG_SOURCE[key])

        with self.assertRaisesRegex(ValueError, r'^multiple components'):
            msg.find_content(**filtering_criteria_related_kwargs)


    @foreach(
        param(
            key='SIMPLE',
            filtering_criteria_related_kwargs=dict(
                content_type='text/plain',
                filename_regex=r'^$',
            ),
            expected_result_selection_tag='main body',
        ),

        param(
            key='QUITE-COMPLEX',
            filtering_criteria_related_kwargs=dict(
                content_type='text/*',
                filename_regex=r'README',
                content_regex=r'N6[.]$(?!.)',       # (would not match if flags weren't customized)
                default_regex_flags=re.IGNORECASE,  # <----------------------------------'
            ),
            expected_result_selection_tag='x-readme',
        ),

        param(
            key='QUITE-COMPLEX',
            filtering_criteria_related_kwargs=dict(
                content_type='text/plain',
                filename_regex=r'README[.]zip',
                content_regex=r'N6[.]$(?!.)',       # (would not match if flags weren't customized)
                default_regex_flags=re.IGNORECASE,  # <----------------------------------'
            ),
            expected_result_selection_tag='without explicit content type',
        ),

        param(
            key='QUITE-COMPLEX',
            filtering_criteria_related_kwargs=dict(
                content_type=ExtractFrom.ZIP,
            ),
            expected_result_selection_tag='extracted from zip #1',
        ),

        param(
            key='QUITE-COMPLEX',
            filtering_criteria_related_kwargs=dict(
                content_type=ExtractFrom.ZIP,
                filename_regex=r'^test\.compressed-you-now/',
            ),
            expected_result_selection_tag='extracted from zip #1',
        ),

        param(
            key='QUITE-COMPLEX',
            filtering_criteria_related_kwargs=dict(
                content_type=ExtractFrom.ZIP,
                filename_regex=r'^test\.compressed-you-now/\.hgignore',
            ),
            expected_result_selection_tag='extracted from zip #1',
        ),

        param(
            key='QUITE-COMPLEX',
            filtering_criteria_related_kwargs=dict(
                content_type=ExtractFrom.ZIP,
                filename_regex=r'^test\.compressed-you-now/README',
            ),
            expected_result_selection_tag='extracted from zip #2',
        ),

        param(
            key='WITH-BROKEN-BOUNDARY',
            filtering_criteria_related_kwargs=dict(
                filename_regex=r'^$',
                content_regex=(
                    rb'^Content-Disposition: attachment; '
                    rb'filename=with_wrong_suffix\.Zip\r$'),
            ),
            expected_result_selection_tag='broken unparsed',
            expected_warn_regex_selection=dict(
                by_substring='when trying to get the content of',
            ),
        ),

        param(
            key='WITH-BROKEN-BOUNDARY',
            filtering_criteria_related_kwargs=dict(
                content_type='multipart/*',
                content_regex=(
                    r'^Content-Disposition: attachment; '
                    r'filename=with_wrong_suffix\.Zip\r$'),
                force_content_as=str,
            ),
            expected_result_selection_tag='broken unparsed',
            expected_result_coercion=lambda s: as_unicode(s, 'strict'),
            expected_warn_regex_selection=dict(
                by_substring='when trying to get the content of',
            ),
        ),
    )
    def test_with_some_filtering_criteria__with_flag_ignore_extra_matches(
        self,
        key,
        filtering_criteria_related_kwargs,
        expected_result_selection_tag,
        expected_result_coercion=None,
        expected_warn_regex_selection=None,
    ):
        msg = ParsedEmailMessage.from_bytes(RAW_MSG_SOURCE[key])
        expected_warn_regexes = (
            select_expected_warn_regexes(key, **expected_warn_regex_selection)
            if expected_warn_regex_selection is not None
            else [])

        with self.assertLogWarningRegexes(module_logger, expected_warn_regexes):
            result = msg.find_content(
                **filtering_criteria_related_kwargs,
                ignore_extra_matches=True)

        assert result == select_expected_results(
            key,
            by_tag=expected_result_selection_tag,
            content_coercion=expected_result_coercion,
            get_contents_only=True)[0]


    @foreach(
        param(
            kwargs=dict(
                content_type='something/not-present',
            ),
        ),

        param(
            kwargs=dict(
                content_type=ExtractFrom.ZIP,
                filename_regex=r'something-not-present',
            ),
            expected_warn_regex_selection=dict(
                by_substring={'QUITE-COMPLEX': 'Could not unpack'},
            ),
        ),

        param(
            kwargs=dict(
                # (all 6 parameters specified here)
                content_type=['*', *ExtractFrom.__members__.values()],  # <- match everything...
                filename_regex=r'README',                               # <- then, narrow down...
                content_regex=[r'something not present # :-)'],         # <- finally, match nothing
                default_regex_flags=re.ASCII | re.VERBOSE,
                force_content_as=str,
                ignore_extra_matches=True,    # (<- the parameter value is irrelevant in this case)
            ),
            expected_warn_regex_selection=ALL_WARNINGS_SELECTION,
        ),
    )
    @foreach(TEST_MSG_KEYS)
    def test_no_matches(
        self,
        key,
        kwargs,
        expected_warn_regex_selection=None,
    ):
        msg = ParsedEmailMessage.from_bytes(RAW_MSG_SOURCE[key])
        expected_warn_regexes = (
            select_expected_warn_regexes(key, **expected_warn_regex_selection)
            if expected_warn_regex_selection is not None
            else [])

        with self.assertLogWarningRegexes(module_logger, expected_warn_regexes):
            result = msg.find_content(**kwargs)

        assert result is None


    @foreach(
        param(
            key='SIMPLE',
            kwargs=dict(
                filename_regex=b'wrong',
            ),
            expected_exc_message_regex=r'cannot use a bytes pattern on a string-like object',
        ),
        param(
            key='SIMPLE',
            kwargs=dict(
                filename_regex=['good', b'wrong'],
            ),
            expected_exc_message_regex=r'cannot use a bytes pattern on a string-like object',
        ),
        param(
            key='SIMPLE',
            kwargs=dict(
                filename_regex=re.compile(b'wrong'),
            ),
            expected_exc_message_regex=r'cannot use a bytes pattern on a string-like object',
        ),
        param(
            key='SIMPLE',
            kwargs=dict(
                filename_regex=['good', re.compile(b'wrong'), re.compile('also good')],
            ),
            expected_exc_message_regex=r'cannot use a bytes pattern on a string-like object',
        ),
        param(
            key='SIMPLE',
            kwargs=dict(
                content_regex='wrong',
                force_content_as=bytes,
            ),
            expected_exc_message_regex=r'cannot use a string pattern on a bytes-like object',
        ),
        param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=['wrong', re.compile(b'good')],
                force_content_as=bytes,
            ),
            expected_exc_message_regex=r'cannot use a string pattern on a bytes-like object',
        ),
        param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=re.compile('wrong'),
                force_content_as=bytes,
            ),
            expected_exc_message_regex=r'cannot use a string pattern on a bytes-like object',
        ),
        param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=[re.compile(b'good'), re.compile('wrong'), b'also good'],
                force_content_as=bytes,
            ),
            expected_exc_message_regex=r'cannot use a string pattern on a bytes-like object',
        ),
        param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=b'wrong',
                force_content_as=str,
            ),
            expected_exc_message_regex=r'cannot use a bytes pattern on a string-like object',
        ),
        param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=[b'wrong', 'good', 'zupa good'],
                force_content_as=str,
            ),
            expected_exc_message_regex=r'cannot use a bytes pattern on a string-like object',
        ),
        param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=re.compile(b'wrong'),
                force_content_as=str,
            ),
            expected_exc_message_regex=r'cannot use a bytes pattern on a string-like object',
        ),
        param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=[re.compile('good'), re.compile(b'wrong'), 'good'],
                force_content_as=str,
            ),
            expected_exc_message_regex=r'cannot use a bytes pattern on a string-like object',
        ),
        param(
            key='SIMPLE',
            kwargs=dict(
                force_content_as=int,
            ),
            expected_exc_message_regex=r'force_content_as=.*should be None, bytes or str',
        ),
    )
    def test_TypeError_cases(
        self,
        key,
        kwargs,
        expected_exc_message_regex,
    ):
        msg = ParsedEmailMessage.from_bytes(RAW_MSG_SOURCE[key])

        with self.assertRaisesRegex(TypeError, expected_exc_message_regex):
            msg.find_content(**kwargs)


    @foreach(
        param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=b'wrong',
            ),
            expected_warn_regexes=[
                r'cannot use a bytes pattern on a string-like object',
            ],
        ),
        param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=[b'wrong', b'also wrong'],
            ),
            expected_warn_regexes=[
                r'cannot use a bytes pattern on a string-like object',
                r'cannot use a bytes pattern on a string-like object',
            ],
        ),
        param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=re.compile(b'wrong'),
            ),
            expected_warn_regexes=[
                r'cannot use a bytes pattern on a string-like object',
            ],
        ),
        param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=[re.compile(b'wrong'), 'good'],
            ),
            expected_warn_regexes=[
                r'cannot use a bytes pattern on a string-like object',
            ],
        ),
        param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex='wrong',
            ),
            expected_warn_regexes=[
                *select_expected_warn_regexes(
                    'WITH-BROKEN-BOUNDARY',
                    by_substring='when trying to get the content of'),
                r'cannot use a string pattern on a bytes-like object',
            ],
        ),
        param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex=['wrong', b'good', 'wrong again', 'and again'],
            ),
            expected_warn_regexes=[
                *select_expected_warn_regexes(
                    'WITH-BROKEN-BOUNDARY',
                    by_substring='when trying to get the content of'),
                r'cannot use a string pattern on a bytes-like object',
                r'cannot use a string pattern on a bytes-like object',
                r'cannot use a string pattern on a bytes-like object',
            ],
        ),
        param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex=re.compile('wrong'),
            ),
            expected_warn_regexes=[
                *select_expected_warn_regexes(
                    'WITH-BROKEN-BOUNDARY',
                    by_substring='when trying to get the content of'),
                r'cannot use a string pattern on a bytes-like object',
            ],
        ),
        param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex=[re.compile('wrong'), b'good', re.compile('again wrong')],
            ),
            expected_warn_regexes=[
                *select_expected_warn_regexes(
                    'WITH-BROKEN-BOUNDARY',
                    by_substring='when trying to get the content of'),
                r'cannot use a string pattern on a bytes-like object',
                r'cannot use a string pattern on a bytes-like object',
            ],
        ).label('e'),
    )
    def test_skipped_and_logged_TypeError_cases(
        self,
        key,
        kwargs,
        expected_warn_regexes,
    ):
        msg = ParsedEmailMessage.from_bytes(RAW_MSG_SOURCE[key])

        with self.assertLogWarningRegexes(module_logger, expected_warn_regexes):
            msg.find_content(**kwargs)


@expand
class TestParsedEmailMessage_find_filename_content_pairs(_BaseTestCase):  # noqa

    @foreach(TEST_MSG_KEYS)
    def test_without_arguments(self, key):
        msg = ParsedEmailMessage.from_bytes(RAW_MSG_SOURCE[key])
        expected_warn_regexes = select_expected_warn_regexes(
            key,
            by_substring={
                'WITH-BROKEN-BOUNDARY': 'when trying to get the content of',
                'WITH-DEFECTIVE-BASE64-CTE': {
                    'InvalidBase64CharactersDefect',
                    'InvalidBase64PaddingDefect',
                },
            })

        with self.assertLogWarningRegexes(module_logger, expected_warn_regexes):
            results_iter = msg.find_filename_content_pairs()
            results = list(results_iter)

        assert isinstance(results_iter, Iterator)
        assert len(results) == EXPECTED_NUMBER_OF_ALL_LEAF_COMPONENTS[key]
        assert results == select_expected_results(
            key,
            **ALL_LEAF_COMPONENTS_SELECTION)


    @foreach(TEST_MSG_KEYS)
    def test_matching_all_extracted_files_if_any(self, key):
        msg = ParsedEmailMessage.from_bytes(RAW_MSG_SOURCE[key])
        expected_warn_regexes = select_expected_warn_regexes(
            key,
            by_substring={'QUITE-COMPLEX': {'Could not unpack', 'Could not decompress'}})

        with self.assertLogWarningRegexes(module_logger, expected_warn_regexes):
            results_iter = msg.find_filename_content_pairs(
                content_type=self.ALL_EXTRACT_MARKERS)
            results = list(results_iter)

        assert isinstance(results_iter, Iterator)
        assert len(results) == EXPECTED_NUMBER_OF_ALL_EXTRACTED_FILES[key]
        assert results == select_expected_results(
            key,
            **ALL_EXTRACTED_FILES_SELECTION)


    @foreach(TEST_MSG_KEYS)
    def test_matching_everything(self, key):
        msg = ParsedEmailMessage.from_bytes(RAW_MSG_SOURCE[key])
        expected_warn_regexes = select_expected_warn_regexes(
            key,
            **ALL_WARNINGS_SELECTION)

        with self.assertLogWarningRegexes(module_logger, expected_warn_regexes):
            results_iter = msg.find_filename_content_pairs(
                content_type=['*'] + self.ALL_EXTRACT_MARKERS)
            results = list(results_iter)

        assert isinstance(results_iter, Iterator)
        assert len(results) == EXPECTED_NUMBER_OF_ALL_LEAF_COMPONENTS_AND_EXTRACTED_FILES[key]
        assert results == select_expected_results(
            key,
            **ALL_RESULTS_SELECTION)


    @foreach(
        param(
            kwargs=dict(
                content_type='application/*',
                filename_regex=r'something-not-present',
            ),
        ),

        param(
            kwargs=dict(
                content_type=ExtractFrom.GZIP,
                filename_regex=r'something-not-present',
            ),
            expected_warn_regex_selection=dict(
                by_substring={'QUITE-COMPLEX': 'Could not decompress'},
            ),
        ),

        param(
            kwargs=dict(
                content_type=['*', *ExtractFrom.__members__.values()],  # <- match everything...
                filename_regex=r'/',                                    # <- then, narrow down...
                content_regex=[rb'something not present # :-)'],        # <- finally, match nothing
                default_regex_flags=re.ASCII | re.VERBOSE,
                force_content_as=bytes,
            ),
            expected_warn_regex_selection=dict(
                by_substring={
                    'QUITE-COMPLEX': {
                        'Could not unpack',
                        'Could not decompress',
                    },
                    'WITH-DEFECTIVE-BASE64-CTE': {
                        'InvalidBase64CharactersDefect',
                        'InvalidBase64PaddingDefect',
                    },
                },
            ),
        ),
    )
    @foreach(TEST_MSG_KEYS)
    def test_no_matches(
        self,
        key,
        kwargs,
        expected_warn_regex_selection=None,
    ):
        msg = ParsedEmailMessage.from_bytes(RAW_MSG_SOURCE[key])
        expected_warn_regexes = (
            select_expected_warn_regexes(key, **expected_warn_regex_selection)
            if expected_warn_regex_selection is not None
            else [])

        with self.assertLogWarningRegexes(module_logger, expected_warn_regexes):
            results_iter = msg.find_filename_content_pairs(**kwargs)
            results = list(results_iter)

        assert isinstance(results_iter, Iterator)
        assert results == []


    @foreach({

        #
        # By `content_type` set to a *MIME content type identifier*

        'SIMPLE, by simple `content_type`': param(
            key='SIMPLE',
            kwargs=dict(
                content_type='text/plain',
            ),
            expected_results_selection=dict(
                by_tag='main body',
            ),
        ),

        'SIMPLE, by simple `content_type`, not found': param(
            key='SIMPLE',
            kwargs=dict(
                content_type='application/gzip',
            ),
            expected_results_selection=None,
        ),

        'QUITE-COMPLEX, by simple `content_type` ("text/plain")': param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='text/plain',
            ),
            expected_results_selection=dict(
                by_tag={
                    'main body',
                    '8bit text',
                    'nested text zz #1',
                    'nested text zz #2',
                    'without explicit content type',
                },
            ),
        ),

        'QUITE-COMPLEX, by simple `content_type` ("TEXT/plain")': param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='TEXT/plain',
            ),
            expected_results_selection=dict(
                by_tag={
                    'main body',
                    '8bit text',
                    'nested text zz #1',
                    'nested text zz #2',
                    'without explicit content type',
                },
            ),
        ),

        'QUITE-COMPLEX, by simple `content_type` ("text/PLAIN")': param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='text/PLAIN',
            ),
            expected_results_selection=dict(
                by_tag={
                    'main body',
                    '8bit text',
                    'nested text zz #1',
                    'nested text zz #2',
                    'without explicit content type',
                },
            ),
        ),

        'QUITE-COMPLEX, by simple `content_type` ("TEXT/PLAIN")': param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='text/plain',
            ),
            expected_results_selection=dict(
                by_tag={
                    'main body',
                    '8bit text',
                    'nested text zz #1',
                    'nested text zz #2',
                    'without explicit content type',
                },
            ),
        ),

        'QUITE-COMPLEX, by simple `content_type` ("application/octet-stream")': param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='application/octet-stream',
            ),
            expected_results_selection=dict(
                by_tag={
                    'pickled',
                    'readme as binary data',
                    'gzip with wrong suffix and content type',
                    'gzip recognized by suffix of filename from ct `name`',
                    'gzip with no filename and wrong content type',
                },
            ),
        ),

        'QUITE-COMPLEX, by simple `content_type` ("APPLICATION/OCTET-STREAM")': param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='Application/Octet-Stream',
            ),
            expected_results_selection=dict(
                by_tag={
                    'pickled',
                    'readme as binary data',
                    'gzip with wrong suffix and content type',
                    'gzip recognized by suffix of filename from ct `name`',
                    'gzip with no filename and wrong content type',
                },
            ),
        ),

        'QUITE-COMPLEX, by simple `content_type` ("Application/Octet-Stream")': param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='Application/Octet-Stream',
            ),
            expected_results_selection=dict(
                by_tag={
                    'pickled',
                    'readme as binary data',
                    'gzip with wrong suffix and content type',
                    'gzip recognized by suffix of filename from ct `name`',
                    'gzip with no filename and wrong content type',
                },
            ),
        ),

        'QUITE-COMPLEX, by simple `content_type` ("applIcatIon/x-nObOdy-knOws")': param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='applIcatIon/x-nObOdy-knOws',
            ),
            expected_results_selection=dict(
                by_tag={
                    'gzip recognized by filename suffix',
                },
            ),
        ),

        #
        # By `content_type` set to a MIME content type's *subtype wildcard*

        'SIMPLE, by subtype wildcard `content_type`': param(
            key='SIMPLE',
            kwargs=dict(
                content_type='text/*',
            ),
            expected_results_selection=dict(
                by_tag='main body',
            ),
        ),

        'SIMPLE, by subtype wildcard `content_type`, not found': param(
            key='SIMPLE',
            kwargs=dict(
                content_type='application/*',
            ),
            expected_results_selection=None,
        ),

        'QUITE-COMPLEX, by subtype wildcard `content_type` ("text/*")': param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='text/*',
            ),
            expected_results_selection=dict(
                by_tag={
                    'main body',
                    'python code',
                    '8bit text',
                    'html',
                    'nested text zz #1',
                    'x-readme',
                    'nested text zz #2',
                    'without explicit content type',
                    'gzip with wrongly textual content type',
                },
            ),
        ),

        'QUITE-COMPLEX, by subtype wildcard `content_type` ("TEXT/*")': param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='TEXT/*',
            ),
            expected_results_selection=dict(
                by_tag={
                    'main body',
                    'python code',
                    '8bit text',
                    'html',
                    'nested text zz #1',
                    'x-readme',
                    'nested text zz #2',
                    'without explicit content type',
                    'gzip with wrongly textual content type',
                },
            ),
        ),

        'QUITE-COMPLEX, by subtype wildcard `content_type` ("text/")': param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='text/',
            ),
            expected_results_selection=dict(
                by_tag={
                    'main body',
                    'python code',
                    '8bit text',
                    'html',
                    'nested text zz #1',
                    'x-readme',
                    'nested text zz #2',
                    'without explicit content type',
                    'gzip with wrongly textual content type',
                },
            ),
        ),

        'QUITE-COMPLEX, by subtype wildcard `content_type` ("tEXt/")': param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='tEXt/',
            ),
            expected_results_selection=dict(
                by_tag={
                    'main body',
                    'python code',
                    '8bit text',
                    'html',
                    'nested text zz #1',
                    'x-readme',
                    'nested text zz #2',
                    'without explicit content type',
                    'gzip with wrongly textual content type',
                },
            ),
        ),

        'QUITE-COMPLEX, by subtype wildcard `content_type` ("text")': param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='text',
            ),
            expected_results_selection=dict(
                by_tag={
                    'main body',
                    'python code',
                    '8bit text',
                    'html',
                    'nested text zz #1',
                    'x-readme',
                    'nested text zz #2',
                    'without explicit content type',
                    'gzip with wrongly textual content type',
                },
            ),
        ),

        'QUITE-COMPLEX, by subtype wildcard `content_type` ("Text")': param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='Text',
            ),
            expected_results_selection=dict(
                by_tag={
                    'main body',
                    'python code',
                    '8bit text',
                    'html',
                    'nested text zz #1',
                    'x-readme',
                    'nested text zz #2',
                    'without explicit content type',
                    'gzip with wrongly textual content type',
                },
            ),
        ),

        'QUITE-COMPLEX, by subtype wildcard `content_type` ("application")': param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='application',
            ),
            expected_results_selection=dict(
                by_tag={
                    'pickled',
                    'zip',
                    'readme as binary data',
                    'bzip2',
                    'gzip with wrong suffix',
                    'gzip recognized by filename suffix',
                    'truncated gzip',
                    'gzip recognized by standard content type',
                    'gzip with wrong suffix and content type',
                    'gzip recognized by suffix of filename from ct `name`',
                    'gzip with no filename and wrong content type',
                    'gzip recognized by `x-` content type',
                },
            ),
        ),

        'QUITE-COMPLEX, by subtype wildcard `content_type` ("APPLiCATiON")': param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='application',
            ),
            expected_results_selection=dict(
                by_tag={
                    'pickled',
                    'zip',
                    'readme as binary data',
                    'bzip2',
                    'gzip with wrong suffix',
                    'gzip recognized by filename suffix',
                    'truncated gzip',
                    'gzip recognized by standard content type',
                    'gzip with wrong suffix and content type',
                    'gzip recognized by suffix of filename from ct `name`',
                    'gzip with no filename and wrong content type',
                    'gzip recognized by `x-` content type',
                },
            ),
        ),

        # By `content_type` set to a MIME content type *general wildcard*

        'SIMPLE, by general wildcard `content_type`': param(
            key='SIMPLE',
            kwargs=dict(
                content_type='*',
            ),
            expected_results_selection=dict(
                by_tag='main body',
            ),
        ),

        'QUITE-COMPLEX, by general wildcard `content_type` ("*")': param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='*',
            ),
            expected_results_selection=ALL_LEAF_COMPONENTS_SELECTION,
        ),

        'QUITE-COMPLEX, by general wildcard `content_type` ("*/")': param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='*/',
            ),
            expected_results_selection=ALL_LEAF_COMPONENTS_SELECTION,
        ),

        'QUITE-COMPLEX, by general wildcard `content_type` ("*/*")': param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='*/*',
            ),
            expected_results_selection=ALL_LEAF_COMPONENTS_SELECTION,
        ),

        #
        # By `content_type` set to a `ExtractFrom` special marker

        'SIMPLE, by ExtractFrom `content_type`, not found': param(
            key='SIMPLE',
            kwargs=dict(
                content_type=ExtractFrom.ZIP,
            ),
            expected_results_selection=None,
        ),

        'QUITE-COMPLEX, by ExtractFrom `content_type` (ZIP)': param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type=ExtractFrom.ZIP,
            ),
            expected_results_selection=dict(
                by_tag={
                    'extracted from zip #1',
                    'extracted from zip #2',
                },
            ),
        ),

        'QUITE-COMPLEX, by ExtractFrom `content_type` (GZIP)': param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type=ExtractFrom.GZIP,
            ),
            expected_results_selection=dict(
                by_tag={
                    'extracted from gzip with wrong suffix',
                    'extracted from gzip recognized by filename suffix',
                    'extracted from gzip recognized by standard content type',
                    'extracted from gzip recognized by suffix of filename from ct `name`',
                    'extracted from gzip recognized by `x-` content type',
                },
            ),
        ),

        'QUITE-COMPLEX, by ExtractFrom `content_type` (BZIP2)': param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type=ExtractFrom.BZIP2,
            ),
            expected_results_selection=dict(
                by_tag={
                    'extracted from bzip2',
                },
            ),
        ),

        #
        # By `content_type` set to a distort `content_type` identifier or wildcard

        ('QUITE-COMPLEX, by distort `content_type` ("text/plai<CUT>"), '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='text/plai',
            ),
            expected_results_selection=None,
        ),

        ('QUITE-COMPLEX, by distort `content_type` ("text/<CUT>lain"), '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='text/lain',
            ),
            expected_results_selection=None,
        ),

        ('QUITE-COMPLEX, by distort `content_type` ("tex<CUT>/plain"), '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='tex/plain',
            ),
            expected_results_selection=None,
        ),

        ('QUITE-COMPLEX, by distort `content_type` ("<CUT>ext/plain"), '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='ext/plain',
            ),
            expected_results_selection=None,
        ),

        ('QUITE-COMPLEX, by distort `content_type` ("text/plain<EXTRA LETTER>"), '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='text/plains',
            ),
            expected_results_selection=None,
        ),

        ('QUITE-COMPLEX, by distort `content_type` ("text/<EXTRA LETTER>plain"), '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='text/splain',
            ),
            expected_results_selection=None,
        ),

        ('QUITE-COMPLEX, by distort `content_type` ("text<EXTRA LETTER>/plain"), '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='texts/plain',
            ),
            expected_results_selection=None,
        ),

        ('QUITE-COMPLEX, by distort `content_type` ("<EXTRA LETTER>text/plain"), '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='stext/plain',
            ),
            expected_results_selection=None,
        ),

        ('QUITE-COMPLEX, by distort `content_type` ("text/plain<SP>"), '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='text/plain ',
            ),
            expected_results_selection=None,
        ),

        ('QUITE-COMPLEX, by distort `content_type` ("text/<SP>plain"), '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='text/ plain',
            ),
            expected_results_selection=None,
        ),

        ('QUITE-COMPLEX, by distort `content_type` ("text<SP>/plain"), '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='text /plain',
            ),
            expected_results_selection=None,
        ),

        ('QUITE-COMPLEX, by distort `content_type` ("<SP>text/plain"), '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type=' text/plain',
            ),
            expected_results_selection=None,
        ),

        ('QUITE-COMPLEX, by distort subtype wildcard `content_type` ("applicatio<CUT>"), '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='applicatio',
            ),
            expected_results_selection=None,
        ),

        ('QUITE-COMPLEX, by distort subtype wildcard `content_type` ("<CUT>pplication"), '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='pplication',
            ),
            expected_results_selection=None,
        ),

        ('QUITE-COMPLEX, by distort subtype wildcard `content_type` ("application<SP>"), '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='application ',
            ),
            expected_results_selection=None,
        ),

        ('QUITE-COMPLEX, by distort subtype wildcard `content_type` ("application<SP>/*"), '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='application /*',
            ),
            expected_results_selection=None,
        ),

        ('QUITE-COMPLEX, by distort subtype wildcard `content_type` ("<SP>application/*"), '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type=' application/*',
            ),
            expected_results_selection=None,
        ),

        ('QUITE-COMPLEX, by distort general wildcard `content_type` ("*<SP>"), '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='* ',
            ),
            expected_results_selection=None,
        ),

        ('QUITE-COMPLEX, by distort general wildcard `content_type` ("<SP>*"), '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type=' *',
            ),
            expected_results_selection=None,
        ),

        ('QUITE-COMPLEX, by distort general wildcard `content_type` ("*/<SP>"), '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='*/ ',
            ),
            expected_results_selection=None,
        ),

        ('QUITE-COMPLEX, by distort general wildcard `content_type` ("*<SP>/"), '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='* /',
            ),
            expected_results_selection=None,
        ),

        ('QUITE-COMPLEX, by distort general wildcard `content_type` ("<SP>*/"), '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type=' */',
            ),
            expected_results_selection=None,
        ),

        ('QUITE-COMPLEX, by distort general wildcard `content_type` ("*/*<SP>"), '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='*/* ',
            ),
            expected_results_selection=None,
        ),

        ('QUITE-COMPLEX, by distort general wildcard `content_type` ("*/<SP>*"), '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='*/ *',
            ),
            expected_results_selection=None,
        ),

        ('QUITE-COMPLEX, by distort general wildcard `content_type` ("*<SP>/*"), '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='* /*',
            ),
            expected_results_selection=None,
        ),

        ('QUITE-COMPLEX, by distort general wildcard `content_type` ("<SP>*/*"), '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type=' */*',
            ),
            expected_results_selection=None,
        ),

        ('QUITE-COMPLEX, by distort `content_type` ("text/plain/superfluous"), '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='text/plain/superfluous',
            ),
            expected_results_selection=None,
        ),

        ('QUITE-COMPLEX, by distort `content_type` ("text/superfluous/plain"), '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='text/superfluous/plain',
            ),
            expected_results_selection=None,
        ),

        ('QUITE-COMPLEX, by distort `content_type` ("superfluous/text/plain"), '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='superfluous/text/plain',
            ),
            expected_results_selection=None,
        ),

        ('QUITE-COMPLEX, by distort `content_type` ("text/plain/"), '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='text/plain/',
            ),
            expected_results_selection=None,
        ),

        ('QUITE-COMPLEX, by distort `content_type` ("text//plain"), '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='text//plain',
            ),
            expected_results_selection=None,
        ),

        ('QUITE-COMPLEX, by distort `content_type` ("/text/plain"), '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='/text/plain',
            ),
            expected_results_selection=None,
        ),

        ('QUITE-COMPLEX, by distort `content_type` ("text/plain/*"), '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='text/plain/*',
            ),
            expected_results_selection=None,
        ),

        ('QUITE-COMPLEX, by distort `content_type` ("text/*/plain"), '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='text/*/plain',
            ),
            expected_results_selection=None,
        ),

        ('QUITE-COMPLEX, by distort `content_type` ("*/text/plain"), '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='*/text/plain',
            ),
            expected_results_selection=None,
        ),

        ('QUITE-COMPLEX, by distort `content_type` ("text/*/*"), '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='text/*/*',
            ),
            expected_results_selection=None,
        ),

        ('QUITE-COMPLEX, by distort `content_type` ("*/text/*"), '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='*/text/*',
            ),
            expected_results_selection=None,
        ),

        ('QUITE-COMPLEX, by distort `content_type` ("*/plain/*"), '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='*/plain/*',
            ),
            expected_results_selection=None,
        ),

        ('QUITE-COMPLEX, by distort `content_type` ("*/*/plain"), '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='*/*/plain',
            ),
            expected_results_selection=None,
        ),

        ('QUITE-COMPLEX, by distort `content_type` ("*/*/*"), '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='*/*/*',
            ),
            expected_results_selection=None,
        ),

        ('QUITE-COMPLEX, by distort `content_type` ("*/plain"), '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='*/plain',
            ),
            expected_results_selection=None,
        ),

        ('QUITE-COMPLEX, by distort `content_type` ("plain"), '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='plain',
            ),
            expected_results_selection=None,
        ),

        ('QUITE-COMPLEX, by distort `content_type` ("plain/text"), '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='plain/text',
            ),
            expected_results_selection=None,
        ),

        ('QUITE-COMPLEX, by distort `content_type` ("*/text"), '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='*/text',
            ),
            expected_results_selection=None,
        ),

        ('QUITE-COMPLEX, by distort `content_type` ("plain/*"), '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type='plain/*',
            ),
            expected_results_selection=None,
        ),

        #
        # By `content_type` set to a sequence of alternatives...

        'QUITE-COMPLEX, by `content_type` seq ("text/plain", "application/ZIP")': param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type=[
                    'text/plain',
                    'application/ZIP',
                ]
            ),
            expected_results_selection=dict(
                by_tag={
                    # selected with "text/plain":
                    'main body',
                    '8bit text',
                    'nested text zz #1',
                    'nested text zz #2',
                    'without explicit content type',

                    # selected with "application/ZIP":
                    'zip',
                },
            ),
        ),

        'QUITE-COMPLEX, by `content_type` seq ("text/plain", "APPlication")': param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type=[
                    'text/plain',
                    'APPlication',
                ]
            ),
            expected_results_selection=dict(
                by_tag={
                    # selected with "text/plain":
                    'main body',
                    '8bit text',
                    'nested text zz #1',
                    'nested text zz #2',
                    'without explicit content type',

                    # selected with "APPlication":
                    'pickled',
                    'zip',
                    'readme as binary data',
                    'bzip2',
                    'gzip with wrong suffix',
                    'gzip recognized by filename suffix',
                    'truncated gzip',
                    'gzip recognized by standard content type',
                    'gzip with wrong suffix and content type',
                    'gzip recognized by suffix of filename from ct `name`',
                    'gzip with no filename and wrong content type',
                    'gzip recognized by `x-` content type',
                },
            ),
        ),

        'QUITE-COMPLEX, by `content_type` seq ("text/*", "APPLICATION/*")': param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type=[
                    'text/*',
                    'APPLICATION/*',
                ]
            ),
            expected_results_selection=dict(
                by_tag={
                    # selected with "text/*":
                    'main body',
                    'python code',
                    '8bit text',
                    'html',
                    'nested text zz #1',
                    'x-readme',
                    'nested text zz #2',
                    'without explicit content type',
                    'gzip with wrongly textual content type',

                    # selected with "APPLICATION/*":
                    'pickled',
                    'zip',
                    'readme as binary data',
                    'bzip2',
                    'gzip with wrong suffix',
                    'gzip recognized by filename suffix',
                    'truncated gzip',
                    'gzip recognized by standard content type',
                    'gzip with wrong suffix and content type',
                    'gzip recognized by suffix of filename from ct `name`',
                    'gzip with no filename and wrong content type',
                    'gzip recognized by `x-` content type',
                },
            ),
        ),

        'QUITE-COMPLEX, by `content_type` seq ("application/ZIP", ExtractFrom.ZIP)': param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type=[
                    'application/ZIP',
                    ExtractFrom.ZIP,
                ]
            ),
            expected_results_selection=dict(
                by_tag={
                    # selected with "application/ZIP":
                    'zip',

                    # selected with ExtractFrom.ZIP:
                    'extracted from zip #1',
                    'extracted from zip #2',
                },
            ),
        ),

        'QUITE-COMPLEX, by `content_type` seq (ExtractFrom.GZIP, "text/*", ExtractFrom.BZIP2)':
                                                                                         param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type=[
                    ExtractFrom.GZIP,
                    'text/*',
                    'something/not/present/and/even/not/valid! :-|',  # (just matches nothing)
                    ExtractFrom.BZIP2,
                ]
            ),
            expected_results_selection=dict(
                by_tag={
                    # selected with ExtractFrom.GZIP:
                    'extracted from gzip with wrong suffix',
                    'extracted from gzip recognized by filename suffix',
                    'extracted from gzip recognized by standard content type',
                    'extracted from gzip recognized by suffix of filename from ct `name`',
                    'extracted from gzip recognized by `x-` content type',

                    # selected with "text/*":
                    'main body',
                    'python code',
                    '8bit text',
                    'html',
                    'nested text zz #1',
                    'x-readme',
                    'nested text zz #2',
                    'without explicit content type',
                    'gzip with wrongly textual content type',

                    # selected with ExtractFrom.BZIP2:
                    'extracted from bzip2',
                },
            ),
        ),

        'QUITE-COMPLEX, by `content_type` seq ("Text/XML", "Video/X-Whatever"), not found': param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type=['Text/XML', 'Video/X-Whatever']
            ),
            expected_results_selection=None,
        ),

        'QUITE-COMPLEX, by `content_type` seq ("AUDIO/*", "video/x-whatever"), not found': param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type=['AUDIO/*', 'video/x-whatever']
            ),
            expected_results_selection=None,
        ),

        'QUITE-COMPLEX, by `content_type` seq ("audio/*", "video/*"), not found': param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type=['audio/*', 'video/*']
            ),
            expected_results_selection=None,
        ),

        'SIMPLE, by `content_type` seq ("application/ZIP", ExtractFrom.ZIP), not found': param(
            key='SIMPLE',
            kwargs=dict(
                content_type=['application/ZIP', ExtractFrom.ZIP]
            ),
            expected_results_selection=None,
        ),

        'SIMPLE, by `content_type` seq (ExtractFrom.GZIP, "application/*"), not found': param(
            key='SIMPLE',
            kwargs=dict(
                content_type=[ExtractFrom.GZIP, 'application/*']
            ),
            expected_results_selection=None,
        ),

        'SIMPLE, by `content_type` seq (ExtractFrom.BZIP2, ExtractFrom.GZIP), not found': param(
            key='SIMPLE',
            kwargs=dict(
                content_type=[ExtractFrom.BZIP2, ExtractFrom.GZIP]
            ),
            expected_results_selection=None,
        ),

        ('QUITE-COMPLEX, by empty `content_type` seq... '
         '+ other stuff which is then irrelevant, '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_type=[],
                content_regex=[
                    re.compile(rb'^n6|readme', re.IGNORECASE),
                    as_bytes(r'Załączam załączone[.]{3}$'),
                    as_bytes(r'\bW ZAŁĄCZENIU, JAK TO ZAŁĄCZNIK\b'),
                ],
                filename_regex=[
                    r'readme',
                    re.compile(r'\.Zip', re.IGNORECASE),
                    r'^cut',
                    re.compile(r'\bcompressed-you-now\b'),
                ],
                default_regex_flags=(re.IGNORECASE | re.MULTILINE),
            ),
            expected_results_selection=None,
        ),

        #
        # By single `filename_regex` (+ possibly with other arguments...)

        'SIMPLE, by `filename_regex` (str), not found': param(
            key='SIMPLE',
            kwargs=dict(
                filename_regex=r'README'
            ),
            expected_results_selection=None,
        ),

        'SIMPLE, by `filename_regex` (compiled), not found': param(
            key='SIMPLE',
            kwargs=dict(
                filename_regex=re.compile(r'README'),
            ),
            expected_results_selection=None,
        ),

        'SIMPLE, by `filename_regex` (str)': param(
            key='SIMPLE',
            kwargs=dict(
                filename_regex=r'^$',
            ),
            expected_results_selection=dict(
                by_tag='main body',
            ),
        ),

        'SIMPLE, by `filename_regex` (compiled)': param(
            key='SIMPLE',
            kwargs=dict(
                filename_regex=re.compile(r'^$'),
            ),
            expected_results_selection=dict(
                by_tag='main body',
            ),
        ),

        'SIMPLE, by empty `filename_regex` (str)': param(
            key='SIMPLE',
            kwargs=dict(
                filename_regex=r'',  # (as if it was not given)
            ),
            expected_results_selection=dict(
                by_tag='main body',
            ),
        ),

        'SIMPLE, by empty `filename_regex` (compiled)': param(
            key='SIMPLE',
            kwargs=dict(
                filename_regex=re.compile(r''),  # (as if it was not given)
            ),
            expected_results_selection=dict(
                by_tag='main body',
            ),
        ),

        'QUITE-COMPLEX, by empty `filename_regex` (str)': param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                filename_regex=r'',  # (as if it was not given)
            ),
            expected_results_selection=ALL_LEAF_COMPONENTS_SELECTION,
        ),

        'QUITE-COMPLEX, by empty `filename_regex` (str) and widest-selection `content_type`':
                                                                                         param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                filename_regex=r'',  # (as if it was not given)
                content_type=['*', *ExtractFrom.__members__.values()],  # (matches everything...)
            ),
            expected_results_selection=ALL_RESULTS_SELECTION,
        ),

        'QUITE-COMPLEX, by `filename_regex` ("^$" compiled)': param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                filename_regex=re.compile(r'^$'),
            ),
            expected_results_selection=dict(
                by_tag={
                    'main body',
                    'python code',
                    '8bit text',
                    'html',
                    'nested text zz #1',
                    'nested text zz #2',
                    'gzip recognized by standard content type',
                    'gzip with no filename and wrong content type',
                    'gzip recognized by `x-` content type',
                },
            ),
        ),

        'QUITE-COMPLEX, by `filename_regex` ("README" str)': param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                filename_regex=r'README',
            ),
            expected_results_selection=dict(
                by_tag={
                    'readme as binary data',
                    'bzip2',
                    'x-readme',
                    'without explicit content type',
                    'gzip with wrongly textual content type',
                    'gzip recognized by filename suffix',
                    'gzip recognized by suffix of filename from ct `name`',
                },
            ),
        ),

        'QUITE-COMPLEX, by `filename_regex` ("README" compiled)': param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                filename_regex=re.compile(r'README'),
            ),
            expected_results_selection=dict(
                by_tag={
                    'readme as binary data',
                    'bzip2',
                    'x-readme',
                    'without explicit content type',
                    'gzip with wrongly textual content type',
                    'gzip recognized by filename suffix',
                    'gzip recognized by suffix of filename from ct `name`',
                },
            ),
        ),

        'QUITE-COMPLEX, by `filename_regex` ("Readme" str), not found': param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                filename_regex=r'Readme',
            ),
            expected_results_selection=None,
        ),

        'QUITE-COMPLEX, by `filename_regex` ("Readme" compiled), not found': param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                filename_regex=re.compile(r'Readme'),
            ),
            expected_results_selection=None,
        ),

        'QUITE-COMPLEX, by `filename_regex` ("Readme" str) + `default_regex_flags=re.IGNORECASE`':
                                                                                         param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                filename_regex=r'Readme',
                default_regex_flags=re.IGNORECASE,
            ),
            expected_results_selection=dict(
                by_tag={
                    'readme as binary data',
                    'bzip2',
                    'x-readme',
                    'without explicit content type',
                    'gzip with wrongly textual content type',
                    'gzip recognized by filename suffix',
                    'gzip recognized by suffix of filename from ct `name`',
                },
            ),
        ),

        'QUITE-COMPLEX, by `filename_regex` ("Readme" compiled with re.IGNORECASE)': param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                filename_regex=re.compile(r'Readme', re.IGNORECASE),
            ),
            expected_results_selection=dict(
                by_tag={
                    'readme as binary data',
                    'bzip2',
                    'x-readme',
                    'without explicit content type',
                    'gzip with wrongly textual content type',
                    'gzip recognized by filename suffix',
                    'gzip recognized by suffix of filename from ct `name`',
                },
            ),
        ),

        'QUITE-COMPLEX, by `filename_regex` ("README" str) + `content_type` seq': param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                filename_regex=r'README',
                content_type=[
                    ExtractFrom.BZIP2,
                    ExtractFrom.ZIP,
                    'application/octet-stream',
                    'Application/X-BZip2',
                ],
            ),
            expected_results_selection=dict(
                by_tag={
                    'extracted from zip #2',
                    'readme as binary data',
                    'extracted from bzip2',
                    'bzip2',
                    'gzip recognized by suffix of filename from ct `name`',
                },
            ),
        ),

        ('QUITE-COMPLEX, by `filename_regex` ("readme" compiled with re.IGNORECASE) '
         '+ `content_type` seq'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                filename_regex=re.compile(r'readme', re.IGNORECASE),
                default_regex_flags=re.ASCII,  # <- note that this is irrelevant in this case
                content_type=[
                    'APPLICATION/OCTET-STREAM',
                    ExtractFrom.BZIP2,
                    'application/x-bzip2',
                    ExtractFrom.ZIP,
                ],
            ),
            expected_results_selection=dict(
                by_tag={
                    'extracted from zip #2',
                    'readme as binary data',
                    'extracted from bzip2',
                    'bzip2',
                    'gzip recognized by suffix of filename from ct `name`',
                },
            ),
        ),

        ('QUITE-COMPLEX, by `filename_regex` ("readme") '
         '+ `default_regex_flags=re.IGNORECASE` '
         '+ `content_type` seq (ExtractFrom-only)'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                filename_regex=r'readme',
                default_regex_flags=re.IGNORECASE,
                content_type=[
                    ExtractFrom.BZIP2,
                    ExtractFrom.ZIP,
                ],
            ),
            expected_results_selection=dict(
                by_tag={
                    'extracted from zip #2',
                    'extracted from bzip2',
                },
            ),
        ),

        #
        # By `filename_regex` set to a sequence of alternatives (+ possibly with other arguments...)

        'QUITE-COMPLEX, by `filename_regex` seq...': param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                filename_regex=[
                    r'readme',  # <- matches nothing
                    re.compile(r'\.Zip'),
                ],
            ),
            expected_results_selection=dict(
                by_tag={
                    'gzip with wrong suffix',
                },
            ),
        ),

        ('QUITE-COMPLEX, by `filename_regex` seq... '
         '+ `default_regex_flags=re.IGNORECASE`'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                filename_regex=[
                    r'readme',  # <- matches some filenames (because of re.IGNORECASE)
                    re.compile(r'\.Zip'),  # <- note: still compiled *without* re.IGNORECASE
                ],
                default_regex_flags=re.IGNORECASE,
            ),
            expected_results_selection=dict(
                by_tag={
                    'readme as binary data',
                    'bzip2',
                    'x-readme',
                    'gzip with wrong suffix',
                    'without explicit content type',
                    'gzip with wrongly textual content type',
                    'gzip recognized by filename suffix',
                    'gzip recognized by suffix of filename from ct `name`',
                },
            ),
        ),

        (r'QUITE-COMPLEX, by `filename_regex` seq... '
         r'+ `default_regex_flags=re.IGNORECASE` '
         r'+ `content_type` seq...'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                filename_regex=[
                    r'readme',
                    re.compile(r'\.Zip'),
                ],
                default_regex_flags=re.IGNORECASE,
                content_type=[
                    'application/*',
                    '*/x-readme',  # <- *not* a valid wildcard, matches *nothing*!
                ],
            ),
            expected_results_selection=dict(
                by_tag={
                    'readme as binary data',
                    'bzip2',
                    'gzip with wrong suffix',
                    'gzip recognized by filename suffix',
                    'gzip recognized by suffix of filename from ct `name`',
                },
            ),
        ),

        (r'QUITE-COMPLEX, by `filename_regex` seq... '
         r'+ `default_regex_flags=re.IGNORECASE` '
         r'+ `content_type` seq... (#2)'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                filename_regex=[
                    r'readme',
                    re.compile(r'\.Zip'),
                ],
                default_regex_flags=re.IGNORECASE,
                content_type=[
                    'application/*',
                    ExtractFrom.ZIP,
                    '*/x-readme',
                ],
            ),
            expected_results_selection=dict(
                by_tag={
                    'extracted from zip #2',
                    'readme as binary data',
                    'bzip2',
                    'gzip with wrong suffix',
                    'gzip recognized by filename suffix',
                    'gzip recognized by suffix of filename from ct `name`',
                },
            ),
        ),

        (r'QUITE-COMPLEX, by `filename_regex` seq... '
         r'+ `default_regex_flags=re.IGNORECASE` '
         r'+ `content_type` seq... (#3)'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                filename_regex=[
                    r'readme',
                    re.compile(r'\.Zip'),
                ],
                default_regex_flags=re.IGNORECASE,
                content_type=[
                    'application/*',
                    ExtractFrom.ZIP,
                    ExtractFrom.GZIP,
                    '*/x-readme',
                ],
            ),
            expected_results_selection=dict(
                by_tag={
                    'extracted from zip #2',
                    'readme as binary data',
                    'bzip2',
                    'extracted from gzip with wrong suffix',
                    'gzip with wrong suffix',
                    'extracted from gzip recognized by filename suffix',
                    'gzip recognized by filename suffix',
                    'extracted from gzip recognized by suffix of filename from ct `name`',
                    'gzip recognized by suffix of filename from ct `name`',
                },
            ),
        ),

        (r'QUITE-COMPLEX, by `filename_regex` seq... '
         r'+ `default_regex_flags=re.IGNORECASE` '
         r'+ `content_type` seq... (#4)'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                filename_regex=[
                    r'readme',
                    re.compile(r'\.Zip'),
                    r'^cut',
                ],
                default_regex_flags=re.IGNORECASE,
                content_type=[
                    'application/*',
                    ExtractFrom.ZIP,
                    ExtractFrom.GZIP,
                    '*/x-readme',
                ],
            ),
            expected_results_selection=dict(
                by_tag={
                    'extracted from zip #2',
                    'readme as binary data',
                    'bzip2',
                    'extracted from gzip with wrong suffix',
                    'gzip with wrong suffix',
                    'extracted from gzip recognized by filename suffix',
                    'gzip recognized by filename suffix',
                    'truncated gzip',
                    'extracted from gzip recognized by suffix of filename from ct `name`',
                    'gzip recognized by suffix of filename from ct `name`',
                },
            ),
        ),

        (r'QUITE-COMPLEX, by `filename_regex` seq... '
         r'+ `default_regex_flags=re.IGNORECASE` '
         r'+ `content_type` seq... (#5)'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                filename_regex=[
                    r'readme',
                    re.compile(r'\.Zip'),
                    r'^cut',
                ],
                default_regex_flags=re.IGNORECASE,
                content_type=[
                    'application/*',
                    ExtractFrom.ZIP,
                    ExtractFrom.GZIP,
                    'text/x-readme',  # (now, it is valid and matches something...)
                ],
            ),
            expected_results_selection=dict(
                by_tag={
                    'extracted from zip #2',
                    'readme as binary data',
                    'bzip2',
                    'x-readme',
                    'extracted from gzip with wrong suffix',
                    'gzip with wrong suffix',
                    'gzip with wrongly textual content type',
                    'extracted from gzip recognized by filename suffix',
                    'gzip recognized by filename suffix',
                    'truncated gzip',
                    'extracted from gzip recognized by suffix of filename from ct `name`',
                    'gzip recognized by suffix of filename from ct `name`',
                },
            ),
        ),

        (r'QUITE-COMPLEX, by `filename_regex` seq... '
         r'+ `default_regex_flags=re.IGNORECASE` '
         r'+ `content_type` seq... (#6)'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                filename_regex=[
                    r'readme',
                    re.compile(r'\.Zip', re.IGNORECASE),  # <- note: now *with* re.IGNORECASE
                    r'^cut',
                    r'$something not present anywhere$',  # (just matches nothing)
                ],
                default_regex_flags=re.IGNORECASE,
                content_type=[
                    'application/*',
                    ExtractFrom.ZIP,
                    ExtractFrom.GZIP,
                    'text/x-readme',
                ],
            ),
            expected_results_selection=dict(
                by_tag={
                    'extracted from zip #2',
                    'readme as binary data',
                    'bzip2',
                    'x-readme',
                    'extracted from gzip with wrong suffix',
                    'gzip with wrong suffix',
                    'gzip with wrongly textual content type',
                    'extracted from gzip recognized by filename suffix',
                    'gzip recognized by filename suffix',
                    'truncated gzip',
                    'gzip with wrong suffix and content type',
                    'extracted from gzip recognized by suffix of filename from ct `name`',
                    'gzip recognized by suffix of filename from ct `name`',
                },
            ),
        ),

        ('QUITE-COMPLEX, by empty `filename_regex` seq... '
         '+ other stuff which is then irrelevant, '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                filename_regex=[],
                default_regex_flags=(re.IGNORECASE | re.MULTILINE),
                content_type=[
                    'application/*',
                    ExtractFrom.ZIP,
                    ExtractFrom.GZIP,
                    'text/x-readme',
                ],
                content_regex=[
                    # Not even tried...
                    re.compile('^n6|readme', re.IGNORECASE),
                    as_bytes(r'Załączam załączone[.]{3}$'),  # ('d cause `TypeError` if was tried)
                ],
                force_content_as='str',
            ),
            expected_results_selection=None,
        ),

        #
        # By single `content_regex`

        # * str-based regex against str contents:

        'SIMPLE, by `content_regex` ("I [a-z]+!!")': param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=r'I [a-z]+!!',
            ),
            expected_results_selection=dict(
                by_tag='main body',
            ),
        ),

        'SIMPLE, by `content_regex` ("I [a-z]+!!" compiled)': param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=re.compile(r'I [a-z]+!!'),
            ),
            expected_results_selection=dict(
                by_tag='main body',
            ),
        ),

        'SIMPLE, by `content_regex` ("i [a-z]+!!"), not found': param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=r'i [a-z]+!!',
            ),
            expected_results_selection=None,
        ),

        'SIMPLE, by `content_regex` ("I [A-Z]+!!" compiled), not found': param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=re.compile(r'I [A-Z]+!!'),
            ),
            expected_results_selection=None,
        ),

        'SIMPLE, by `content_regex` ("I [A-Z]+!!") + `default_regex_flags=re.IGNORECASE`': param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=r'I [A-Z]+!!',
                default_regex_flags=re.IGNORECASE,
            ),
            expected_results_selection=dict(
                by_tag='main body',
            ),
        ),

        'SIMPLE, by `content_regex` ("i [a-z]+!!" compiled with re.IGNORECASE)': param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=re.compile(r'i [a-z]+!!', re.IGNORECASE),
            ),
            expected_results_selection=dict(
                by_tag='main body',
            ),
        ),

        'SIMPLE, by `content_regex` ("^$")': param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=r'^$',  # (matches because of re.MULTILINE)
            ),
            expected_results_selection=dict(
                by_tag='main body',
            ),
        ),

        'SIMPLE, by `content_regex` ("^$" compiled), not found': param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=re.compile(r'^$'),  # (does not match, as there is no re.MULTILINE)
            ),
            expected_results_selection=None,
        ),

        'SIMPLE, by empty `content_regex` (str)': param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=r'',
            ),
            expected_results_selection=dict(
                by_tag='main body',
            ),
        ),

        'SIMPLE, by empty `content_regex` (compiled str)': param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=re.compile(r''),
            ),
            expected_results_selection=dict(
                by_tag='main body',
            ),
        ),

        # * bytes-based regex against str contents (nothing matches!):

        'SIMPLE, by `content_regex` (b"I [a-z]+!!"), not found': param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=rb'I [a-z]+!!',
            ),
            expected_results_selection=None,
        ),

        'SIMPLE, by `content_regex` (b"I [a-z]+!!" compiled), not found': param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=re.compile(rb'I [a-z]+!!'),
            ),
            expected_results_selection=None,
        ),

        'SIMPLE, by `content_regex` (b"i [a-z]+!!"), not found': param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=rb'i [a-z]+!!',
            ),
            expected_results_selection=None,
        ),

        'SIMPLE, by `content_regex` (b"I [A-Z]+!!" compiled), not found': param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=re.compile(rb'I [A-Z]+!!'),
            ),
            expected_results_selection=None,
        ),

        ('SIMPLE, by `content_regex` (b"I [A-Z]+!!") + `default_regex_flags=re.IGNORECASE`, '
         'not found'): param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=rb'I [A-Z]+!!',
                default_regex_flags=re.IGNORECASE,
            ),
            expected_results_selection=None,
        ),

        ('SIMPLE, by `content_regex` (b"i [a-z]+!!" compiled with re.IGNORECASE), '
         'not found'): param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=re.compile(rb'i [a-z]+!!', re.IGNORECASE),
            ),
            expected_results_selection=None,
        ),

        'SIMPLE, by `content_regex` (b"^$"), not found': param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=rb'^$',
            ),
            expected_results_selection=None,
        ),

        'SIMPLE, by `content_regex` (b"^$" compiled), not found': param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=re.compile(rb'^$'),
            ),
            expected_results_selection=None,
        ),

        'SIMPLE, by empty `content_regex` (bytes), not found': param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=rb'',
            ),
            expected_results_selection=None,
        ),

        'SIMPLE, by empty `content_regex` (bytes compiled), not found': param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=re.compile(rb''),
            ),
            expected_results_selection=None,
        ),

        # * str-based regex against str contents (+ irrelevant `force_content_as=str`):

        ('SIMPLE, by `content_regex` ("I [a-z]+!!")'
         '+ `force_content_as=str`'): param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=r'I [a-z]+!!',
                force_content_as=str,
            ),
            expected_results_selection=dict(
                by_tag='main body',
            ),
        ),

        ('SIMPLE, by `content_regex` ("I [a-z]+!!" compiled)'
         '+ `force_content_as=str`'): param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=re.compile(r'I [a-z]+!!'),
                force_content_as=str,
            ),
            expected_results_selection=dict(
                by_tag='main body',
            ),
        ),

        ('SIMPLE, by `content_regex` ("i [a-z]+!!") '
         '+ `force_content_as=str`, '
         'not found'): param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=r'i [a-z]+!!',
                force_content_as=str,
            ),
            expected_results_selection=None,
        ),

        ('SIMPLE, by `content_regex` ("I [A-Z]+!!" compiled) '
         '+ `force_content_as=str`, '
         'not found'): param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=re.compile(r'I [A-Z]+!!'),
                force_content_as=str,
            ),
            expected_results_selection=None,
        ),

        ('SIMPLE, by `content_regex` ("I [A-Z]+!!") '
        '+ `default_regex_flags=re.IGNORECASE` '
        '+ `force_content_as=str`'): param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=r'I [A-Z]+!!',
                default_regex_flags=re.IGNORECASE,
                force_content_as=str,
            ),
            expected_results_selection=dict(
                by_tag='main body',
            ),
        ),

        ('SIMPLE, by `content_regex` ("i [a-z]+!!" compiled with re.IGNORECASE) '
         '+ `default_regex_flags=re.IGNORECASE` '
         '+ `force_content_as=str`'): param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=re.compile(r'i [a-z]+!!', re.IGNORECASE),
                force_content_as=str,
            ),
            expected_results_selection=dict(
                by_tag='main body',
            ),
        ),

        ('SIMPLE, by `content_regex` ("^$")'
         '+ `force_content_as=str`'): param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=r'^$',  # (matches because of re.MULTILINE)
                force_content_as=str,
            ),
            expected_results_selection=dict(
                by_tag='main body',
            ),
        ),

        ('SIMPLE, by `content_regex` ("^$" compiled)'
         '+ `force_content_as=str`, '
         'not found'): param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=re.compile(r'^$'),  # (does not match, as there is no re.MULTILINE)
                force_content_as=str,
            ),
            expected_results_selection=None,
        ),

        ('SIMPLE, by empty `content_regex` (str)'
         '+ `force_content_as=str`'): param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=r'',
                force_content_as=str,
            ),
            expected_results_selection=dict(
                by_tag='main body',
            ),
        ),

        ('SIMPLE, by empty `content_regex` (compiled str)'
         '+ `force_content_as=str`'): param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=re.compile(r''),
                force_content_as=str,
            ),
            expected_results_selection=dict(
                by_tag='main body',
            ),
        ),

        # * bytes-based regex against contents forced to be bytes (`force_content_as=bytes`):

        ('SIMPLE, by `content_regex` (b"I [a-z]+!!")'
         '+ `force_content_as=bytes`'): param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=rb'I [a-z]+!!',
                force_content_as=bytes,
            ),
            expected_results_selection=dict(
                by_tag='main body',
                content_coercion=lambda s: as_bytes(s).replace(b'\n', b'\r\n'),
            ),
        ),

        ('SIMPLE, by `content_regex` (b"I [a-z]+!!" compiled)'
         '+ `force_content_as=bytes`'): param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=re.compile(rb'I [a-z]+!!'),
                force_content_as=bytes,
            ),
            expected_results_selection=dict(
                by_tag='main body',
                content_coercion=lambda s: as_bytes(s).replace(b'\n', b'\r\n'),
            ),
        ),

        ('SIMPLE, by `content_regex` (b"i [a-z]+!!")'
         '+ `force_content_as=bytes`, '
         'not found'): param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=rb'i [a-z]+!!',
                force_content_as=bytes,
            ),
            expected_results_selection=None,
        ),

        ('SIMPLE, by `content_regex` (b"I [A-Z]+!!" compiled)'
         '+ `force_content_as=bytes`, '
         'not found'): param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=re.compile(rb'I [A-Z]+!!'),
                force_content_as=bytes,
            ),
            expected_results_selection=None,
        ),

        ('SIMPLE, by `content_regex` (b"I [A-Z]+!!") + `default_regex_flags=re.IGNORECASE`'
         '+ `force_content_as=bytes`'): param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=rb'I [A-Z]+!!',
                default_regex_flags=re.IGNORECASE,
                force_content_as=bytes,
            ),
            expected_results_selection=dict(
                by_tag='main body',
                content_coercion=lambda s: as_bytes(s).replace(b'\n', b'\r\n'),
            ),
        ),

        ('SIMPLE, by `content_regex` (b"i [a-z]+!!" compiled with re.IGNORECASE) '
         '+ `force_content_as=bytes`'): param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=re.compile(rb'i [a-z]+!!', re.IGNORECASE),
                force_content_as=bytes,
            ),
            expected_results_selection=dict(
                by_tag='main body',
                content_coercion=lambda s: as_bytes(s).replace(b'\n', b'\r\n'),
            ),
        ),

        ('SIMPLE, by `content_regex` (b"^$")'
         '+ `force_content_as=bytes`'): param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=rb'^$',  # (matches because of re.MULTILINE)
                force_content_as=bytes,
            ),
            expected_results_selection=dict(
                by_tag='main body',
                content_coercion=lambda s: as_bytes(s).replace(b'\n', b'\r\n'),
            ),
        ),

        ('SIMPLE, by `content_regex` (b"^$" compiled)'
         '+ `force_content_as=bytes`, '
         'not found'): param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=re.compile(rb'^$'),  # (does not match, as there is no re.MULTILINE)
                force_content_as=bytes,
            ),
            expected_results_selection=None,
        ),

        ('SIMPLE, by empty `content_regex` (bytes)'
         '+ `force_content_as=bytes`'): param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=rb'',
                force_content_as=bytes,
            ),
            expected_results_selection=dict(
                by_tag='main body',
                content_coercion=lambda s: as_bytes(s).replace(b'\n', b'\r\n'),
            ),
        ),

        ('SIMPLE, by empty `content_regex` (bytes compiled)'
         '+ `force_content_as=bytes`'): param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=re.compile(rb''),
                force_content_as=bytes,
            ),
            expected_results_selection=dict(
                by_tag='main body',
                content_coercion=lambda s: as_bytes(s).replace(b'\n', b'\r\n'),
            ),
        ),

        # * bytes-based regex against bytes contents:

        'WITH-BROKEN-BOUNDARY, by `content_regex` (b"-Tr.nsf.r-")': param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex=rb'-Tr.nsf.r-',
            ),
            expected_results_selection=dict(
                by_tag='broken unparsed',
            ),
        ),

        'WITH-BROKEN-BOUNDARY, by `content_regex` (b"-Tr.nsf.r-" compiled)': param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex=re.compile(rb'-Tr.nsf.r-'),
            ),
            expected_results_selection=dict(
                by_tag='broken unparsed',
            ),
        ),

        'WITH-BROKEN-BOUNDARY, by `content_regex` (b"-tr.nsf.r-"), not found': param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex=rb'-tr.nsf.r-',
            ),
            expected_results_selection=None,
        ),

        'WITH-BROKEN-BOUNDARY, by `content_regex` (b"-TR.NSF.R-" compiled), not found': param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex=re.compile(rb'-TR.NSF.R-'),
            ),
            expected_results_selection=None,
        ),

        ('WITH-BROKEN-BOUNDARY, by `content_regex` (b"-TR.NSF.R-") '
         '+ `default_regex_flags=re.IGNORECASE`'): param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex=rb'-TR.NSF.R-',
                default_regex_flags=re.IGNORECASE,
            ),
            expected_results_selection=dict(
                by_tag='broken unparsed',
            ),
        ),

        ('WITH-BROKEN-BOUNDARY, by `content_regex` '
         '(b"-tr.nsf.r-" compiled with re.IGNORECASE)'): param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex=re.compile(rb'-tr.nsf.r-', re.IGNORECASE),
            ),
            expected_results_selection=dict(
                by_tag='broken unparsed',
            ),
        ),

        'WITH-BROKEN-BOUNDARY, by `content_regex` (b"^$")': param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex=rb'^$',  # (matches because of re.MULTILINE)
            ),
            expected_results_selection=dict(
                by_tag='broken unparsed',
            ),
        ),

        'WITH-BROKEN-BOUNDARY, by `content_regex` (b"^$" compiled), not found': param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex=re.compile(rb'^$'),  # (does not match, as there is no re.MULTILINE)
            ),
            expected_results_selection=None,
        ),

        'WITH-BROKEN-BOUNDARY, by empty `content_regex` (bytes)': param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex=rb'',
            ),
            expected_results_selection=dict(
                by_tag='broken unparsed',
            ),
        ),

        'WITH-BROKEN-BOUNDARY, by empty `content_regex` (compiled bytes)': param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex=re.compile(rb''),
            ),
            expected_results_selection=dict(
                by_tag='broken unparsed',
            ),
        ),

        # * str-based regex against bytes contents (nothing matches!):

        'WITH-BROKEN-BOUNDARY, by `content_regex` ("-Tr.nsf.r-"), not found': param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex=r'-Tr.nsf.r-',
            ),
            expected_results_selection=None,
        ),

        'WITH-BROKEN-BOUNDARY, by `content_regex` ("-Tr.nsf.r-" compiled), not found': param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex=re.compile(r'-Tr.nsf.r-'),
            ),
            expected_results_selection=None,
        ),

        'WITH-BROKEN-BOUNDARY, by `content_regex` ("-tr.nsf.r-"), not found': param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex=r'-tr.nsf.r-',
            ),
            expected_results_selection=None,
        ),

        'WITH-BROKEN-BOUNDARY, by `content_regex` ("-TR.NSF.R-" compiled), not found': param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex=re.compile(r'-TR.NSF.R-'),
            ),
            expected_results_selection=None,
        ),

        ('WITH-BROKEN-BOUNDARY, by `content_regex` ("-TR.NSF.R-") '
         '+ `default_regex_flags=re.IGNORECASE`, '
         'not found'): param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex=r'-TR.NSF.R-',
                default_regex_flags=re.IGNORECASE,
            ),
            expected_results_selection=None,
        ),

        ('WITH-BROKEN-BOUNDARY, by `content_regex` '
         '("-tr.nsf.r-" compiled with re.IGNORECASE), '
         'not found'): param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex=re.compile(r'-tr.nsf.r-', re.IGNORECASE),
            ),
            expected_results_selection=None,
        ),

        'WITH-BROKEN-BOUNDARY, by `content_regex` ("^$"), not found': param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex=r'^$',
            ),
            expected_results_selection=None,
        ),

        'WITH-BROKEN-BOUNDARY, by `content_regex` ("^$" compiled), not found': param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex=re.compile(r'^$'),
            ),
            expected_results_selection=None,
        ),

        'WITH-BROKEN-BOUNDARY, by empty `content_regex` (str), not found': param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex=r'',
            ),
            expected_results_selection=None,
        ),

        'WITH-BROKEN-BOUNDARY, by empty `content_regex` (str compiled), not found': param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex=re.compile(r''),
            ),
            expected_results_selection=None,
        ),

        # * bytes-based regex against bytes contents (+ irrelevant `force_content_as=bytes`):

        ('WITH-BROKEN-BOUNDARY, by `content_regex` (b"-Tr.nsf.r-")'
         '+ `force_content_as=bytes`'): param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex=rb'-Tr.nsf.r-',
                force_content_as=bytes,
            ),
            expected_results_selection=dict(
                by_tag='broken unparsed',
            ),
        ),

        ('WITH-BROKEN-BOUNDARY, by `content_regex` (b"-Tr.nsf.r-" compiled)'
         '+ `force_content_as=bytes`'): param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex=re.compile(rb'-Tr.nsf.r-'),
                force_content_as=bytes,
            ),
            expected_results_selection=dict(
                by_tag='broken unparsed',
            ),
        ),

        ('WITH-BROKEN-BOUNDARY, by `content_regex` (b"-tr.nsf.r-")'
         '+ `force_content_as=bytes`, '
         'not found'): param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex=rb'-tr.nsf.r-',
                force_content_as=bytes,
            ),
            expected_results_selection=None,
        ),

        ('WITH-BROKEN-BOUNDARY, by `content_regex` (b"-TR.NSF.R-" compiled)'
         '+ `force_content_as=bytes`, '
         'not found'): param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex=re.compile(rb'-TR.NSF.R-'),
                force_content_as=bytes,
            ),
            expected_results_selection=None,
        ),

        ('WITH-BROKEN-BOUNDARY, by `content_regex` (b"-TR.NSF.R-") '
         '+ `default_regex_flags=re.IGNORECASE` '
         '+ `force_content_as=bytes`'): param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex=rb'-TR.NSF.R-',
                default_regex_flags=re.IGNORECASE,
                force_content_as=bytes,
            ),
            expected_results_selection=dict(
                by_tag='broken unparsed',
            ),
        ),

        ('WITH-BROKEN-BOUNDARY, by `content_regex` (b"-tr.nsf.r-" compiled with re.IGNORECASE) '
         '+ `default_regex_flags=re.IGNORECASE` '
         '+ `force_content_as=bytes`'): param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex=re.compile(rb'-tr.nsf.r-', re.IGNORECASE),
                force_content_as=bytes,
            ),
            expected_results_selection=dict(
                by_tag='broken unparsed',
            ),
        ),

        ('WITH-BROKEN-BOUNDARY, by `content_regex` (b"^$")'
         '+ `force_content_as=bytes`'): param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex=rb'^$',  # (matches because of re.MULTILINE)
                force_content_as=bytes,
            ),
            expected_results_selection=dict(
                by_tag='broken unparsed',
            ),
        ),

        ('WITH-BROKEN-BOUNDARY, by `content_regex` (b"^$" compiled)'
         '+ `force_content_as=bytes`, '
         'not found'): param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex=re.compile(rb'^$'),  # (does not match, as there is no re.MULTILINE)
                force_content_as=bytes,
            ),
            expected_results_selection=None,
        ),

        ('WITH-BROKEN-BOUNDARY, by empty `content_regex` (bytes)'
         '+ `force_content_as=bytes`'): param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex=rb'',
                force_content_as=bytes,
            ),
            expected_results_selection=dict(
                by_tag='broken unparsed',
            ),
        ),

        ('WITH-BROKEN-BOUNDARY, by empty `content_regex` (compiled bytes)'
         '+ `force_content_as=bytes`'): param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex=re.compile(rb''),
                force_content_as=bytes,
            ),
            expected_results_selection=dict(
                by_tag='broken unparsed',
            ),
        ),

        # * str-based regex against contents forced to be str (`force_content_as=str`):

        ('WITH-BROKEN-BOUNDARY, by `content_regex` ("-Tr.nsf.r-")'
         '+ `force_content_as=str`'): param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex=r'-Tr.nsf.r-',
                force_content_as=str,
            ),
            expected_results_selection=dict(
                by_tag='broken unparsed',
                content_coercion=lambda s: as_unicode(s, 'strict'),
            ),
        ),

        ('WITH-BROKEN-BOUNDARY, by `content_regex` ("-Tr.nsf.r-" compiled)'
         '+ `force_content_as=str`'): param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex=re.compile(r'-Tr.nsf.r-'),
                force_content_as=str,
            ),
            expected_results_selection=dict(
                by_tag='broken unparsed',
                content_coercion=lambda s: as_unicode(s, 'strict'),
            ),
        ),

        ('WITH-BROKEN-BOUNDARY, by `content_regex` ("-tr.nsf.r-")'
         '+ `force_content_as=str`, '
         'not found'): param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex=r'-tr.nsf.r-',
                force_content_as=str,
            ),
            expected_results_selection=None,
        ),

        ('WITH-BROKEN-BOUNDARY, by `content_regex` ("-TR.NSF.R-" compiled)'
         '+ `force_content_as=str`, '
         'not found'): param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex=re.compile(r'-TR.NSF.R-'),
                force_content_as=str,
            ),
            expected_results_selection=None,
        ),

        ('WITH-BROKEN-BOUNDARY, by `content_regex` ("-TR.NSF.R-") + `default_regex_flags=re.IGNORECASE`'
         '+ `force_content_as=str`'): param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex=r'-TR.NSF.R-',
                default_regex_flags=re.IGNORECASE,
                force_content_as=str,
            ),
            expected_results_selection=dict(
                by_tag='broken unparsed',
                content_coercion=lambda s: as_unicode(s, 'strict'),
            ),
        ),

        ('WITH-BROKEN-BOUNDARY, by `content_regex` ("-tr.nsf.r-" compiled with re.IGNORECASE) '
         '+ `force_content_as=str`'): param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex=re.compile(r'-tr.nsf.r-', re.IGNORECASE),
                force_content_as=str,
            ),
            expected_results_selection=dict(
                by_tag='broken unparsed',
                content_coercion=lambda s: as_unicode(s, 'strict'),
            ),
        ),

        ('WITH-BROKEN-BOUNDARY, by `content_regex` ("^$")'
         '+ `force_content_as=str`'): param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex=r'^$',  # (matches because of re.MULTILINE)
                force_content_as=str,
            ),
            expected_results_selection=dict(
                by_tag='broken unparsed',
                content_coercion=lambda s: as_unicode(s, 'strict'),
            ),
        ),

        ('WITH-BROKEN-BOUNDARY, by `content_regex` ("^$" compiled)'
         '+ `force_content_as=str`, '
         'not found'): param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex=re.compile(r'^$'),  # (does not match, as there is no re.MULTILINE)
                force_content_as=str,
            ),
            expected_results_selection=None,
        ),

        ('WITH-BROKEN-BOUNDARY, by empty `content_regex` (str)'
         '+ `force_content_as=str`'): param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex=r'',
                force_content_as=str,
            ),
            expected_results_selection=dict(
                by_tag='broken unparsed',
                content_coercion=lambda s: as_unicode(s, 'strict'),
            ),
        ),

        ('WITH-BROKEN-BOUNDARY, by empty `content_regex` (str compiled)'
         '+ `force_content_as=str`'): param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex=re.compile(r''),
                force_content_as=str,
            ),
            expected_results_selection=dict(
                by_tag='broken unparsed',
                content_coercion=lambda s: as_unicode(s, 'strict'),
            ),
        ),

        #
        # By `content_regex` set to a sequence of alternatives (+ possibly with other arguments...)

        r'QUITE-COMPLEX, by `content_regex` seq...': param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_regex=[
                    re.compile(rb'^n6|readme'),
                    r'Załączam załączone[.]{3}$',
                    r'\bW ZAŁĄCZENIU, JAK TO ZAŁĄCZNIK\b',  # (matches *nothing*)
                ],
            ),
            expected_results_selection=dict(
                by_tag={
                    'readme as binary data',
                    '8bit text',
                },
            ),
        ),

        ('QUITE-COMPLEX, by `content_regex` seq... '
         '+ `default_regex_flags=re.IGNORECASE | re.MULTILINE`'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_regex=[
                    re.compile(rb'^n6|readme'),  # <- note: still compiled *without* re.IGNORECASE
                    r'Załączam załączone[.]{3}$',
                    r'\bW ZAŁĄCZENIU, JAK TO ZAŁĄCZNIK\b',  # (matches because of re.IGNORECASE)
                ],
                default_regex_flags=(re.IGNORECASE | re.MULTILINE),
            ),
            expected_results_selection=dict(
                by_tag={
                    'readme as binary data',
                    '8bit text',
                    'nested text zz #1',
                    'nested text zz #2',
                },
            ),
        ),

        ('QUITE-COMPLEX, by `content_regex` seq... '
         '+ `default_regex_flags=re.IGNORECASE | re.MULTILINE` '
         '+ `filename_regex` seq... + `content_type` seq...'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_regex=[
                    re.compile(rb'^n6|readme'),
                    r'Załączam załączone[.]{3}$',
                    r'\bW ZAŁĄCZENIU, JAK TO ZAŁĄCZNIK\b',
                ],
                default_regex_flags=(re.IGNORECASE | re.MULTILINE),
                filename_regex=[
                    r'readme',
                    re.compile(r'\.Zip', re.IGNORECASE),
                    r'^cut',
                ],
                content_type=[
                    'application/*',
                    'text/x-readme',
                ],
            ),
            expected_results_selection=dict(
                by_tag={
                    'readme as binary data',
                },
            ),
        ),

        ('QUITE-COMPLEX, by `content_regex` seq... '
         '+ `default_regex_flags=re.IGNORECASE | re.MULTILINE` '
         '+ `filename_regex` seq... + `content_type` seq... #2'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_regex=[
                    re.compile(rb'^n6|readme', re.IGNORECASE),  # <- note: now *with* re.IGNORECASE
                    r'Załączam załączone[.]{3}$',
                    r'\bW ZAŁĄCZENIU, JAK TO ZAŁĄCZNIK\b',
                ],
                default_regex_flags=(re.IGNORECASE | re.MULTILINE),
                filename_regex=[
                    r'readme',
                    re.compile(r'\.Zip', re.IGNORECASE),
                    r'^cut',
                ],
                content_type=[
                    'application/*',
                    'text/x-readme',
                ],
            ),
            expected_results_selection=dict(
                by_tag={
                    'readme as binary data',
                    'gzip with wrong suffix',
                    'gzip recognized by filename suffix',
                    'gzip with wrong suffix and content type',
                    'gzip recognized by suffix of filename from ct `name`',
                },
            ),
        ),

        ('QUITE-COMPLEX, by `content_regex` seq... '
         '+ `default_regex_flags=re.IGNORECASE | re.MULTILINE` '
         '+ `filename_regex` seq... + `content_type` seq... #3'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_regex=[
                    re.compile(rb'^n6|readme', re.IGNORECASE),
                    r'Załączam załączone[.]{3}$',
                    r'\bW ZAŁĄCZENIU, JAK TO ZAŁĄCZNIK\b',
                ],
                default_regex_flags=(re.IGNORECASE | re.MULTILINE),
                filename_regex=[
                    r'readme',
                    re.compile(r'\.Zip', re.IGNORECASE),
                    r'^cut',
                ],
                content_type=[
                    ExtractFrom.GZIP,
                    'application/*',
                    'text/x-readme',
                    ExtractFrom.ZIP,
                ],
            ),
            expected_results_selection=dict(
                by_tag={
                    'extracted from zip #2',
                    'readme as binary data',
                    'extracted from gzip with wrong suffix',
                    'gzip with wrong suffix',
                    'extracted from gzip recognized by filename suffix',
                    'gzip recognized by filename suffix',
                    'gzip with wrong suffix and content type',
                    'extracted from gzip recognized by suffix of filename from ct `name`',
                    'gzip recognized by suffix of filename from ct `name`',
                },
            ),
        ),

        ('QUITE-COMPLEX, by `content_regex` seq... '
         '+ `default_regex_flags=re.IGNORECASE | re.MULTILINE` '
         '+ `filename_regex` seq... + `content_type` seq... '
         '+ `force_content_as=None`'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_regex=[
                    re.compile(rb'^n6|readme', re.IGNORECASE),
                    r'Załączam załączone[.]{3}$',
                    r'\bW ZAŁĄCZENIU, JAK TO ZAŁĄCZNIK\b',
                ],
                default_regex_flags=(re.IGNORECASE | re.MULTILINE),
                filename_regex=[
                    r'readme',
                    re.compile(r'\.Zip', re.IGNORECASE),
                    r'^cut',
                    re.compile(r'\bcompressed-you-now\b'),
                ],
                content_type=[
                    ExtractFrom.GZIP,
                    'application/*',
                    'text/x-readme',
                    ExtractFrom.ZIP,
                ],
                force_content_as=None,  # <- as if it was not specified
            ),
            expected_results_selection=dict(
                by_tag={
                    'extracted from zip #2',
                    'zip',
                    'readme as binary data',
                    'extracted from gzip with wrong suffix',
                    'gzip with wrong suffix',
                    'extracted from gzip recognized by filename suffix',
                    'gzip recognized by filename suffix',
                    'gzip with wrong suffix and content type',
                    'extracted from gzip recognized by suffix of filename from ct `name`',
                    'gzip recognized by suffix of filename from ct `name`',
                },
            ),
        ),

        ('QUITE-COMPLEX, by `content_regex` seq... '
         '+ `default_regex_flags=re.IGNORECASE | re.MULTILINE` '
         '+ `filename_regex` seq... + `content_type` seq... '
         '+ `force_content_as="str"`'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_regex=[
                    re.compile(r'^n6|readme', re.IGNORECASE),
                    r'Załączam załączone[.]{3}$',
                    r'\bW ZAŁĄCZENIU, JAK TO ZAŁĄCZNIK\b',
                ],
                default_regex_flags=(re.IGNORECASE | re.MULTILINE),
                filename_regex=[
                    r'readme',
                    re.compile(r'\.Zip', re.IGNORECASE),
                    r'^cut',
                    re.compile(r'\bcompressed-you-now\b'),
                ],
                content_type=[
                    ExtractFrom.GZIP,
                    'application/*',
                    'text/x-readme',
                    ExtractFrom.ZIP,
                ],
                force_content_as='str',
            ),
            expected_results_selection=dict(
                by_tag={
                    'extracted from zip #2',
                    'zip',
                    'readme as binary data',
                    'x-readme',
                    'extracted from gzip with wrong suffix',
                    'gzip with wrong suffix',
                    'gzip with wrongly textual content type',
                    'extracted from gzip recognized by filename suffix',
                    'gzip recognized by filename suffix',
                    'gzip with wrong suffix and content type',
                    'extracted from gzip recognized by suffix of filename from ct `name`',
                    'gzip recognized by suffix of filename from ct `name`',
                },
                content_coercion=lambda s: as_unicode(s, 'replace'),
            ),
        ),

        ('QUITE-COMPLEX, by `content_regex` seq... '
         '+ `default_regex_flags=re.IGNORECASE | re.MULTILINE` '
         '+ `filename_regex` seq... + `content_type` seq... '
         '+ `force_content_as="bytes"`'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_regex=[
                    re.compile(rb'^n6|readme', re.IGNORECASE),
                    as_bytes(r'Załączam załączone[.]{3}$'),
                    as_bytes(r'\bW ZAŁĄCZENIU, JAK TO ZAŁĄCZNIK\b'),
                ],
                default_regex_flags=(re.IGNORECASE | re.MULTILINE),
                filename_regex=[
                    r'readme',
                    re.compile(r'\.Zip', re.IGNORECASE),
                    r'^cut',
                    re.compile(r'\bcompressed-you-now\b'),
                ],
                content_type=[
                    ExtractFrom.GZIP,
                    'application/*',
                    'text/x-readme',
                    ExtractFrom.ZIP,
                ],
                force_content_as='bytes',
            ),
            expected_results_selection=dict(
                by_tag={
                    'extracted from zip #2',
                    'zip',
                    'readme as binary data',
                    'x-readme',
                    'extracted from gzip with wrong suffix',
                    'gzip with wrong suffix',
                    'gzip with wrongly textual content type',
                    'extracted from gzip recognized by filename suffix',
                    'gzip recognized by filename suffix',
                    'gzip with wrong suffix and content type',
                    'extracted from gzip recognized by suffix of filename from ct `name`',
                    'gzip recognized by suffix of filename from ct `name`',
                },
                content_coercion=lambda s: (
                    # For the component tagged in test data
                    # as `gzip recognized by filename suffix`,
                    # the content needs to be replaced with:
                    (b'\x1f\x8b\x08\x08\xf1\x8f\x93Q\x00\x03README\x00\xcb'
                     b'3\xd3\xe3\x02\x00<&\x891\x04\x00\x00\x00')

                    if s == (
                        '\x1f\ufffd\x08\x08\ufffd\ufffd\ufffdQ\x00\x03README\x00\ufffd'
                        '3\ufffd\ufffd\x02\x00<&\ufffd1\x04\x00\x00\x00')

                    # For all other components in this case,
                    # text contents do not contain any '\r',
                    # so simple coercion to bytes is enough:
                    else as_bytes(s))
            ),
        ),

        ('QUITE-COMPLEX, by `content_regex` seq... '
         '+ `filename_regex` seq... + ExtractFrom-only `content_type` seq...'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_regex=[
                    rb'\A something not present anywhere \Z',  # (just matches nothing)
                    rb'^n6',
                ],
                filename_regex=[
                    re.compile(r'^(ala/ma/kota/)?readme', re.IGNORECASE),
                    re.compile(r'\.Zip', re.IGNORECASE),
                    r'\bcompressed-you-now\b',
                ],
                content_type=[
                    ExtractFrom.GZIP,
                    ExtractFrom.ZIP,
                ],
            ),
            expected_results_selection=dict(
                by_tag={
                    'extracted from zip #2',
                    'extracted from gzip with wrong suffix',
                    'extracted from gzip recognized by filename suffix',
                    'extracted from gzip recognized by suffix of filename from ct `name`',
                },
            ),
        ),

        ('QUITE-COMPLEX, by `content_regex` seq... '
         '+ single `filename_regex`... + single ExtractFrom `content_type` (GZIP)'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_regex=[
                    rb'\A something not present anywhere \Z',  # (just matches nothing)
                    rb'^n6',
                ],
                filename_regex=re.compile(r'\.zip', re.IGNORECASE),
                content_type=ExtractFrom.GZIP,
            ),
            expected_results_selection=dict(
                by_tag={
                    'extracted from gzip with wrong suffix',
                },
            ),
        ),

        ('QUITE-COMPLEX, by `content_regex` seq... '
         '+ `default_regex_flags=re.IGNORECASE | re.MULTILINE` '
         '+ single `filename_regex`... + `content_type` seq...'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_regex=[
                    r'\bW ZAŁĄCZENIU, JAK TO ZAŁĄCZNIK\b',
                    r'Załączam załączone[.]{3}$|<br.*>',
                    re.compile(rb'^n6|readme', re.IGNORECASE),
                ],
                default_regex_flags=(re.IGNORECASE | re.MULTILINE),
                filename_regex=re.compile(r'\bcompressed-you-now\b|^$'),
                content_type=[
                    ExtractFrom.ZIP,
                    'Application/ZIP',
                    'Text/*',
                ],
            ),
            expected_results_selection=dict(
                by_tag={
                    'extracted from zip #2',
                    'zip',
                    '8bit text',
                    'html',
                    'nested text zz #1',
                    'nested text zz #2',
                },
            ),
        ),

        ('QUITE-COMPLEX, by `content_regex` seq... '
         '+ `default_regex_flags=re.IGNORECASE | re.MULTILINE` '
         '+ `filename_regex` seq... + single str `content_type`...'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_regex=[
                    r'\bW ZAŁĄCZENIU, JAK TO ZAŁĄCZNIK\b',
                    re.compile(r'Załączam załączone[.]{3}$|<br.*>'),
                ],
                default_regex_flags=(re.IGNORECASE | re.MULTILINE),
                filename_regex=[
                    re.compile(r'\bcompressed-you-now\b'),
                    re.compile(r'^$'),
                ],
                content_type=[
                    'Text/*',
                ],
            ),
            expected_results_selection=dict(
                by_tag={
                    '8bit text',
                    'html',
                    'nested text zz #1',
                    'nested text zz #2',
                },
            ),
        ),

        ('QUITE-COMPLEX, by empty `content_regex` seq... '
         '+ other stuff which is then irrelevant, '
         'not found'): param(
            key='QUITE-COMPLEX',
            kwargs=dict(
                content_regex=[],
                default_regex_flags=(re.IGNORECASE | re.MULTILINE),
                filename_regex=[
                    r'readme',
                    re.compile(r'\.Zip', re.IGNORECASE),
                    r'^cut',
                    re.compile(r'\bcompressed-you-now\b'),
                ],
                content_type=[
                    ExtractFrom.GZIP,
                    'application/*',
                    'text/x-readme',
                    ExtractFrom.ZIP,
                ],
                force_content_as='bytes',
            ),
            expected_results_selection=None,
        ),
    })
    def test_various_cases(
        self,
        key,
        kwargs,
        expected_results_selection=None,
    ):
        msg = ParsedEmailMessage.from_bytes(RAW_MSG_SOURCE[key])
        expected_results = (
            select_expected_results(key, **expected_results_selection)
            if expected_results_selection is not None
            else [])

        results_iter = msg.find_filename_content_pairs(**kwargs)
        results = list(results_iter)

        assert isinstance(results_iter, Iterator)
        assert results == expected_results


    @foreach(
        param(
            key='SIMPLE',
            kwargs=dict(
                filename_regex=b'wrong',
            ),
            expected_exc_message_regex=r'cannot use a bytes pattern on a string-like object',
        ),
        param(
            key='SIMPLE',
            kwargs=dict(
                filename_regex=['good', b'wrong'],
            ),
            expected_exc_message_regex=r'cannot use a bytes pattern on a string-like object',
        ),
        param(
            key='SIMPLE',
            kwargs=dict(
                filename_regex=re.compile(b'wrong'),
            ),
            expected_exc_message_regex=r'cannot use a bytes pattern on a string-like object',
        ),
        param(
            key='SIMPLE',
            kwargs=dict(
                filename_regex=['good', re.compile(b'wrong'), re.compile('also good')],
            ),
            expected_exc_message_regex=r'cannot use a bytes pattern on a string-like object',
        ),
        param(
            key='SIMPLE',
            kwargs=dict(
                content_regex='wrong',
                force_content_as=bytes,
            ),
            expected_exc_message_regex=r'cannot use a string pattern on a bytes-like object',
        ),
        param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=['wrong', re.compile(b'good')],
                force_content_as=bytes,
            ),
            expected_exc_message_regex=r'cannot use a string pattern on a bytes-like object',
        ),
        param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=re.compile('wrong'),
                force_content_as=bytes,
            ),
            expected_exc_message_regex=r'cannot use a string pattern on a bytes-like object',
        ),
        param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=[re.compile(b'good'), re.compile('wrong'), b'also good'],
                force_content_as=bytes,
            ),
            expected_exc_message_regex=r'cannot use a string pattern on a bytes-like object',
        ),
        param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=b'wrong',
                force_content_as=str,
            ),
            expected_exc_message_regex=r'cannot use a bytes pattern on a string-like object',
        ),
        param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=[b'wrong', 'good', 'zupa good'],
                force_content_as=str,
            ),
            expected_exc_message_regex=r'cannot use a bytes pattern on a string-like object',
        ),
        param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=re.compile(b'wrong'),
                force_content_as=str,
            ),
            expected_exc_message_regex=r'cannot use a bytes pattern on a string-like object',
        ),
        param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=[re.compile('good'), re.compile(b'wrong'), 'good'],
                force_content_as=str,
            ),
            expected_exc_message_regex=r'cannot use a bytes pattern on a string-like object',
        ),
        param(
            key='SIMPLE',
            kwargs=dict(
                force_content_as=int,
            ),
            expected_exc_message_regex=r'force_content_as=.*should be None, bytes or str',
        ),
    )
    def test_TypeError_cases(
        self,
        key,
        kwargs,
        expected_exc_message_regex,
    ):
        msg = ParsedEmailMessage.from_bytes(RAW_MSG_SOURCE[key])

        with self.assertRaisesRegex(TypeError, expected_exc_message_regex):
            list(msg.find_filename_content_pairs(**kwargs))


    @foreach(
        param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=b'wrong',
            ),
            expected_warn_regexes=[
                r'cannot use a bytes pattern on a string-like object',
            ],
        ),
        param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=[b'wrong', b'also wrong'],
            ),
            expected_warn_regexes=[
                r'cannot use a bytes pattern on a string-like object',
                r'cannot use a bytes pattern on a string-like object',
            ],
        ),
        param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=re.compile(b'wrong'),
            ),
            expected_warn_regexes=[
                r'cannot use a bytes pattern on a string-like object',
            ],
        ),
        param(
            key='SIMPLE',
            kwargs=dict(
                content_regex=[re.compile(b'wrong'), 'good'],
            ),
            expected_warn_regexes=[
                r'cannot use a bytes pattern on a string-like object',
            ],
        ),
        param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex='wrong',
            ),
            expected_warn_regexes=[
                *select_expected_warn_regexes(
                    'WITH-BROKEN-BOUNDARY',
                    by_substring='when trying to get the content of'),
                r'cannot use a string pattern on a bytes-like object',
            ],
        ),
        param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex=['wrong', b'good', 'wrong again', 'and again'],
            ),
            expected_warn_regexes=[
                *select_expected_warn_regexes(
                    'WITH-BROKEN-BOUNDARY',
                    by_substring='when trying to get the content of'),
                r'cannot use a string pattern on a bytes-like object',
                r'cannot use a string pattern on a bytes-like object',
                r'cannot use a string pattern on a bytes-like object',
            ],
        ),
        param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex=re.compile('wrong'),
            ),
            expected_warn_regexes=[
                *select_expected_warn_regexes(
                    'WITH-BROKEN-BOUNDARY',
                    by_substring='when trying to get the content of'),
                r'cannot use a string pattern on a bytes-like object',
            ],
        ),
        param(
            key='WITH-BROKEN-BOUNDARY',
            kwargs=dict(
                content_regex=[re.compile('wrong'), b'good', re.compile('again wrong')],
            ),
            expected_warn_regexes=[
                *select_expected_warn_regexes(
                    'WITH-BROKEN-BOUNDARY',
                    by_substring='when trying to get the content of'),
                r'cannot use a string pattern on a bytes-like object',
                r'cannot use a string pattern on a bytes-like object',
            ],
        ).label('e'),
    )
    def test_skipped_and_logged_TypeError_cases(
        self,
        key,
        kwargs,
        expected_warn_regexes,
    ):
        msg = ParsedEmailMessage.from_bytes(RAW_MSG_SOURCE[key])

        with self.assertLogWarningRegexes(module_logger, expected_warn_regexes):
            list(msg.find_filename_content_pairs(**kwargs))
