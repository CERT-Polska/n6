# Copyright (c) 2021-2023 NASK. All rights reserved.

"""
Collectors: `dataplane.dnsrd`, `dataplane.dnsrdany`, `dataplane.dnsversion`,
`dataplane.sipinvitation`, `dataplane.sipquery`, `dataplane.sipregistration`,
`dataplane.smtpdata`, `dataplane.smtpgreet`, `dataplane.sshclient`,
`dataplane.sshpwauth`, `dataplane.telnetlogin`, `dataplane.vncrfb`.
"""

from n6datasources.collectors.base import (
    BaseSimpleCollector,
    BaseDownloadingCollector,
    add_collector_entry_point_functions,
)
from n6lib.class_helpers import attr_required
from n6lib.config import combined_config_spec
from n6lib.log_helpers import get_logger


LOGGER = get_logger(__name__)


class _BaseDataplaneCollector(BaseDownloadingCollector,
                              BaseSimpleCollector):

    config_spec_pattern = combined_config_spec('''
        [{collector_class_name}]
        url :: str
    ''')

    # to be set in concrete collector classes
    source_channel = None

    raw_type = "blacklist"
    content_type = "text/plain"

    @attr_required('source_channel')
    def get_source(self, **processed_data):
        return f'dataplane.{self.source_channel}'

    def obtain_data_body(self) -> bytes:
        return self.download(self.config["url"])


class DataplaneDnsrdCollector(_BaseDataplaneCollector):

    source_channel = "dnsrd"


class DataplaneDnsrdanyCollector(_BaseDataplaneCollector):

    source_channel = "dnsrdany"


class DataplaneDnsversionCollector(_BaseDataplaneCollector):

    source_channel = "dnsversion"


class DataplaneSipinvitationCollector(_BaseDataplaneCollector):

    source_channel = "sipinvitation"


class DataplaneSipqueryCollector(_BaseDataplaneCollector):

    source_channel = "sipquery"


class DataplaneSipregistrationCollector(_BaseDataplaneCollector):

    source_channel = "sipregistration"


class DataplaneSmtpdataCollector(_BaseDataplaneCollector):

    source_channel = "smtpdata"


class DataplaneSmtpgreetCollector(_BaseDataplaneCollector):

    source_channel = "smtpgreet"


class DataplaneSshclientCollector(_BaseDataplaneCollector):

    source_channel = "sshclient"


class DataplaneSshpwauthCollector(_BaseDataplaneCollector):

    source_channel = "sshpwauth"


class DataplaneTelnetloginCollector(_BaseDataplaneCollector):

    source_channel = "telnetlogin"


class DataplaneVncrfbCollector(_BaseDataplaneCollector):

    source_channel = "vncrfb"


add_collector_entry_point_functions(__name__)
