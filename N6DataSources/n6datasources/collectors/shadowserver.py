# Copyright (c) 2014-2023 NASK. All rights reserved.

"""
The `shadowserver.*` mail collector.
"""

import re

from n6datasources.collectors.base import (
    BaseDownloadingCollector,
    BaseSimpleEmailCollector,
    add_collector_entry_point_functions,
)
from n6lib.common_helpers import make_exc_ascii_str
from n6lib.config import (
    ConfigError,
    combined_config_spec,
)
from n6lib.log_helpers import get_logger
from n6lib.mail_parsing_helpers import first_regex_search


LOGGER = get_logger(__name__)


class ShadowserverMailCollector(BaseDownloadingCollector, BaseSimpleEmailCollector):

    config_spec_pattern = combined_config_spec('''
        [{collector_class_name}]

        # A regular expression whose first capturing group matches the
        # *pure subject* part (i.e., the important, distinct part) of
        # an e-mail message's subject:
        subject_pattern

        # A regular expression whose first capturing group matches,
        # within an e-mail message's body, the URL to download data
        # from:
        item_url_pattern

        # A Python dictionary that maps *pure subjects* (see above) to
        # the corresponding *source channels* (note that this collector
        # collaborates with multiple parsers...):
        subject_to_channel :: py

        # A Python dictionary that maps, for all corresponding parsers,
        # *source channels* to *raw format version tags* (`str`) or
        # `None` values (the latter if the given parser does not have
        # a *raw format version tag*):
        channel_to_raw_format_version_tag :: py
    ''')

    raw_type = 'file'
    content_type = 'text/csv'

    #
    # Initialization

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._subject_pattern = self._get_minimum_1_group_regex_pattern('subject_pattern')
        self._item_url_pattern = self._get_minimum_1_group_regex_pattern('item_url_pattern')
        self._subject_to_channel = self.config['subject_to_channel']
        self._channel_to_raw_format_version_tag = self.config['channel_to_raw_format_version_tag']
        self._source_channel = self._get_source_channel()
        self.raw_format_version_tag = self._get_raw_format_version_tag()  # for BaseCollector stuff

    def _get_minimum_1_group_regex_pattern(self, option_name):
        pattern = self.config[option_name]
        try:
            _regex_obj = re.compile(pattern)
        except re.error as exc:
            raise ConfigError(
                f'malformed `{option_name}` regex ({pattern!a}) (could '
                f'not compile it: {make_exc_ascii_str})') from exc
        if _regex_obj.groups < 1:
            raise ConfigError(
                f'wrong `{option_name}` regex ({pattern!a}): '
                f'it does not contain any capture group')
        return pattern

    def _get_source_channel(self):
        email_msg_subject = self._get_email_msg_subject()
        pure_subject = self._get_pure_subject(email_msg_subject)
        return self._get_channel(pure_subject)

    def _get_email_msg_subject(self):
        email_msg_subject = self.email_msg.get_subject()
        if email_msg_subject is None:
            raise ValueError('unsupported e-mail format: no subject found')
        return email_msg_subject

    def _get_pure_subject(self, email_msg_subject):
        subject_match = first_regex_search(self._subject_pattern, email_msg_subject)
        if subject_match is None:
            raise ValueError(
                f'unsupported e-mail format: the `subject_pattern` '
                f'regex ({self._subject_pattern!a}) does not match '
                f'the message subject ({email_msg_subject!a})')
        return subject_match.group(1)

    def _get_channel(self, pure_subject):
        channel = self._subject_to_channel.get(pure_subject)
        if channel is None:
            raise ConfigError(
                f'wrong `subject_to_channel` mapping: no source '
                f'channel for the pure subject {pure_subject!a}')
        return channel

    def _get_raw_format_version_tag(self):
        try:
            return self._channel_to_raw_format_version_tag[self._source_channel]
        except KeyError:
            raise ConfigError(
                f'wrong `channel_to_raw_format_version_tag` '
                f'mapping: missing data for the source channel '
                f'{self._source_channel!a}') from None

    #
    # Customization of hook methods provided by superclasses...

    def get_source(self, **processed_data):
        return f'shadowserver.{self._source_channel}'

    def obtain_data_body(self):
        url = self._extract_url_from_email_msg()
        return self.download(url)

    def _extract_url_from_email_msg(self):
        email_msg_body = self.email_msg.find_content(
            content_type='text/plain',
            content_regex=self._item_url_pattern,
            ignore_extra_matches=True)
        if email_msg_body is None:
            raise ValueError(
                f'no URL found in the e-mail message '
                f'(`iter_url_pattern`, which is set to '
                f'{self._item_url_pattern!a}, did not match...)')
        url_match = first_regex_search(self._item_url_pattern, email_msg_body)
        assert url_match is not None
        return url_match.group(1)


add_collector_entry_point_functions(__name__)
