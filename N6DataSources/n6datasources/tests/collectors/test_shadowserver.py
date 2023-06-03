# Copyright (c) 2022-2023 NASK. All rights reserved.

import datetime
from unittest.mock import call

from n6datasources.collectors.base import (
    BaseDownloadingCollector,
    BaseSimpleEmailCollector,
)
from n6datasources.collectors.shadowserver import ShadowserverMailCollector
from n6datasources.tests.collectors._collector_test_helpers import BaseSimpleEmailCollectorTestCase
from n6lib.config import ConfigError


_SHADOWSERVER_MAIL_COLLECTOR_EXAMPLE_RAW_EMAIL_MSG = (
b'''Return-Path: example@example.com'
Date: Sun, 23 Apr 2023 20:01:23 -0700
From: send@shadowserver.org
To: recv@example.org
Subject: [Poland] Shadowserver Poland Accessible Android Debug Bridge
\tReport: 2023-04-23
X-Mailman-Version: 3.4.5
MIME-Version: 1.0
Content-Type: multipart/mixed;
 boundary="=-jakies-=-tam-=-boundary-=-12345678990-="

This is a multi-part message in MIME format.

--=-jakies-=-tam-=-boundary-=-12345678990-=
Content-Type: text/plain; charset=us-ascii
Content-Disposition: inline
Content-ID: <20230423200123.WHATEVER-etc@shadowserver.org>

The report content can be obtained from the following link:
https://dl.shadowserver.org/aBcD12345-_qwertyuiopASDfgh\x20
The report is 1.2M bytes and contains 123 events.
For more information on this report go to: https://www.shadowserver.org/wiki/etc/itd/itp

--=-jakies-=-tam-=-boundary-=-12345678990-=
Content-Type: text/plain; charset="us-ascii"
MIME-Version: 1.0
Content-Transfer-Encoding: 7bit
Content-Disposition: inline

_______________________________________________
This or That mailing list
Where@mail.example.org
https://mail.shadowserver.org/mailman/etc/itd/itp

--=-jakies-=-tam-=-boundary-=-12345678990-=--
''')


_SHADOWSERVER_MAIL_COLLECTOR_EXAMPLE_CONFIG_CONTENT = (
r'''
[ShadowserverMailCollector]

subject_pattern = Shadowserver (.+) Report

item_url_pattern = (https?://dl.shadowserver.org/[?a-zA-Z0-9_-]+)

subject_to_channel = {
    "Poland Spam URL": "spam-url",
    "Poland Accessible Android Debug Bridge": "adb",
    "Poland Accessible AMQP": "amqp",
  }

channel_to_raw_format_version_tag = {
    "adb": "202204",
    "amqp": None,
  }

download_retries = 10
base_request_headers = {}
''')


class TestShadowserverMailCollector(BaseSimpleEmailCollectorTestCase):

    #
    # Constants and helpers
    #

    RAW_EMAIL_MSG = _SHADOWSERVER_MAIL_COLLECTOR_EXAMPLE_RAW_EMAIL_MSG
    CONFIG_CONTENT = _SHADOWSERVER_MAIL_COLLECTOR_EXAMPLE_CONFIG_CONTENT

    DOWNLOAD_HTTP_LAST_MODIFIED_DT = datetime.datetime(2023, 4, 24, 12, 13, 14)


    def patch_download(self, side_effect=None):
        collector = self.collector  # (<- set by `BaseSimpleEmailCollectorTestCase` machinery)

        if side_effect is None:
            def side_effect(url):
                collector._http_last_modified = self.DOWNLOAD_HTTP_LAST_MODIFIED_DT
                return b'...successful download from %a...' % url

        return self.patch(
            'n6datasources.collectors.base.BaseDownloadingCollector.download',
            side_effect=side_effect)


    #
    # `BaseSimpleEmailCollectorTestCase`-required definitions/declarations
    #

    collector_class = ShadowserverMailCollector
    collector_superclasses = [
        BaseSimpleEmailCollector,
        BaseDownloadingCollector,
    ]
    collector_raw_type = 'file'
    collector_content_type = 'text/csv'


    @classmethod
    def cases(cls):

        #
        # Successful collector runs

        for with_date_in_message in (True, False):
            for with_raw_format_version_tag_in_config in (True, False):

                if with_raw_format_version_tag_in_config:
                    expected_routing_key = 'shadowserver.adb.202204'
                    config_content = cls.CONFIG_CONTENT
                else:
                    expected_routing_key = 'shadowserver.adb'
                    config_content = cls.CONFIG_CONTENT.replace(
                        '"adb": "202204"',
                        '"adb": None',
                    )

                expected_meta_headers = {
                    'http_last_modified': str(cls.DOWNLOAD_HTTP_LAST_MODIFIED_DT),
                    'mail_subject': (
                        '[Poland] Shadowserver Poland Accessible '
                        'Android Debug Bridge Report: 2023-04-23'),
                }
                if with_date_in_message:
                    expected_meta_headers['mail_time'] = '2023-04-24 03:01:23'  # (as UTC)
                    raw_email_msg = cls.RAW_EMAIL_MSG
                else:
                    raw_email_msg = cls.RAW_EMAIL_MSG.replace(
                        b'Date: Sun, 23 Apr 2023 20:01:23 -0700\n',
                        b'',
                    )

                yield cls.SuccessCase(
                    config_content=config_content,
                    raw_email_msg=raw_email_msg,
                    after_init_callbacks=[
                        cls.patch_download,
                    ],
                    expected_publish_output_calls=[
                        call(
                            # routing_key
                            expected_routing_key,

                            # body
                            (b"...successful download from "
                             b"'https://dl.shadowserver.org/aBcD12345-_qwertyuiopASDfgh'..."),

                            # prop_kwargs
                            cls.AutoExpectedPropKwargs(expected_meta_headers),
                        ),
                    ],
                )

        #
        # Errors from collector's `__init__()`

        yield cls.InitErrorCase(
            config_content=cls.CONFIG_CONTENT.replace(
                r'subject_pattern = Shadowserver (.+) Report',
                r'subject_pattern = Shadowserver (.+ Report',
            ),
            raw_email_msg=cls.RAW_EMAIL_MSG,
            expected_exc_type=ConfigError,
            expected_exc_regex=r'malformed `subject_pattern` regex.*could not compile',
        )

        yield cls.InitErrorCase(
            config_content=cls.CONFIG_CONTENT.replace(
                r'subject_pattern = Shadowserver (.+) Report',
                r'subject_pattern = Shadowserver .+ Report',
            ),
            raw_email_msg=cls.RAW_EMAIL_MSG,
            expected_exc_type=ConfigError,
            expected_exc_regex=r'wrong `subject_pattern` regex.*not contain any capture group',
        )

        yield cls.InitErrorCase(
            config_content=cls.CONFIG_CONTENT.replace(
                r'item_url_pattern = (https?://dl.shadowserver.org/[?a-zA-Z0-9_-]+)',
                r'item_url_pattern = https?://dl.shadowserver.org/[?a-zA-Z0-9_-]+)',
            ),
            raw_email_msg=cls.RAW_EMAIL_MSG,
            expected_exc_type=ConfigError,
            expected_exc_regex=r'malformed `item_url_pattern` regex.*could not compile',
        )

        yield cls.InitErrorCase(
            config_content=cls.CONFIG_CONTENT.replace(
                r'item_url_pattern = (https?://dl.shadowserver.org/[?a-zA-Z0-9_-]+)',
                r'item_url_pattern = https?://dl.shadowserver.org/[?a-zA-Z0-9_-]+',
            ),
            raw_email_msg=cls.RAW_EMAIL_MSG,
            expected_exc_type=ConfigError,
            expected_exc_regex=r'wrong `item_url_pattern` regex.*not contain any capture group',
        )

        yield cls.InitErrorCase(
            config_content=cls.CONFIG_CONTENT,
            raw_email_msg=cls.RAW_EMAIL_MSG.replace(
                (b'Subject: [Poland] Shadowserver Poland Accessible '
                 b'Android Debug Bridge\n\tReport: 2023-04-23\n'),
                b'',
            ),
            expected_exc_type=ValueError,
            expected_exc_regex=r'unsupported e-mail format: no subject found',
        )

        yield cls.InitErrorCase(
            config_content=cls.CONFIG_CONTENT,
            raw_email_msg=cls.RAW_EMAIL_MSG.replace(
                (b'Subject: [Poland] Shadowserver Poland Accessible '
                 b'Android Debug Bridge\n\tReport: 2023-04-23\n'),
                b'Subject: And now for something completely different.',
            ),
            expected_exc_type=ValueError,
            expected_exc_regex=r'unsupported e-mail format:.*`subject_pattern`.*does not match',
        )

        yield cls.InitErrorCase(
            config_content=cls.CONFIG_CONTENT.replace(
                '"Poland Accessible Android Debug Bridge": "adb",',
                '',
            ),
            raw_email_msg=cls.RAW_EMAIL_MSG,
            expected_exc_type=ConfigError,
            expected_exc_regex=r'wrong `subject_to_channel` mapping: no source channel for',
        )

        yield cls.InitErrorCase(
            config_content=cls.CONFIG_CONTENT.replace(
                '"adb": "202204",',
                '',
            ),
            raw_email_msg=cls.RAW_EMAIL_MSG,
            expected_exc_type=ConfigError,
            expected_exc_regex=r'wrong `channel_to_raw_format_version_tag` mapping: missing data',
        )

        #
        # Errors from collector's `run_collector()`

        yield cls.RunErrorCase(
            config_content=cls.CONFIG_CONTENT,
            raw_email_msg=cls.RAW_EMAIL_MSG,
            after_init_callbacks=[
                lambda self: self.patch_download(ZeroDivisionError('arbitrary exception example')),
            ],
            expected_exc_type=ZeroDivisionError,
            expected_exc_regex=r'arbitrary exception example',
        )

        yield cls.RunErrorCase(
            config_content=cls.CONFIG_CONTENT,
            raw_email_msg=cls.RAW_EMAIL_MSG.replace(
                b'https://dl.shadowserver',
                b'https://whatever.example',
            ),
            expected_exc_type=ValueError,
            expected_exc_regex=r'no URL found in the e-mail message',
        )
