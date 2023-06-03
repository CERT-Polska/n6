# Copyright (c) 2022-2023 NASK. All rights reserved.

import unittest

from n6datasources.parsers.cesnet_cz import (
    CesnetCzWardenParser,
)
from n6datasources.parsers.base import BaseParser
from n6datasources.tests.parsers._parser_test_mixin import ParserTestMixin


class TestCesnetCzWardenParser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'cesnet-cz.warden'
    PARSER_CLASS = CesnetCzWardenParser
    PARSER_BASE_CLASS = BaseParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'low',
    }

    def cases(self):
        # 0 events
        yield (
            b'''
            []
            ''',
            []
        )
        # 1 event
        yield (
            b'''
            [
                {
                    "DetectTime": "2000-01-01T00:00:00Z",
                    "Category": ["Attempt.Login"],
                    "Source": [{"IP4": ["1.1.1.1"]}]
                }
            ]
            ''',
            [
                dict(
                    time='2000-01-01 00:00:00',
                    category='server-exploit',
                    address=[{'ip': '1.1.1.1'}],
                ),
            ]
        )
        # 2 events
        yield (
            b'''
            [
                {
                    "DetectTime": "2000-01-01T00:00:00Z",
                    "Category": ["Attempt.Login"],
                    "Source": [{"IP4": ["1.1.1.1"]}]
                },
                {
                    "DetectTime": "2000-01-02T00:00:00Z",
                    "Category": ["Recon.Scanning"],
                    "Source": [{"IP4": ["1.1.1.1"]}]
                }
            ]
            ''',
            [
                dict(
                    time='2000-01-01 00:00:00',
                    category='server-exploit',
                    address=[{'ip': '1.1.1.1'}],
                ),
                dict(
                    time='2000-01-02 00:00:00',
                    category='scanning',
                    address=[{'ip': '1.1.1.1'}],
                ),
            ]
        )
        # 2 categories in event
        yield (
            b'''
            [
                {
                    "DetectTime": "2000-01-01T00:00:00Z",
                    "Category": ["Attempt.Login", "Recon.Scanning"],
                    "Source": [{"IP4": ["1.1.1.1"]}]
                }
            ]
            ''',
            [
                dict(
                    time='2000-01-01 00:00:00',
                    category='server-exploit',
                    address=[{'ip': '1.1.1.1'}],
                ),
                dict(
                    time='2000-01-01 00:00:00',
                    category='scanning',
                    address=[{'ip': '1.1.1.1'}],
                ),
            ]
        )
        # NO_MAPPING category
        yield (
            b'''
            [
                {
                    "DetectTime": "2000-01-01T00:00:00Z",
                    "Category": ["Information.UnauthorizedModification"],
                    "Source": [{"IP4": ["1.1.1.1"]}]
                }
            ]
            ''',
            []
        )
        # not existing category
        yield (
            b'''
            [
                {
                    "DetectTime": "2000-01-01T00:00:00Z",
                    "Category": ["some string"],
                    "Source": [{"IP4": ["1.1.1.1"]}]
                }
            ]
            ''',
            []
        )
        # no Source.IP4 or Source.IP
        yield (
            b'''
            [
                {
                    "DetectTime": "2000-01-01T00:00:00Z",
                    "Category": ["Malware"]
                }
            ]
            ''',
            []
        )
        # "Malware" category
        yield (
            b'''
            [
                {
                  "DetectTime": "2022-04-28T12:35:45.718318Z",
                  "Category": [
                    "Malware"
                  ],
                  "Format": "IDEA0",
                  "Node": [
                    {
                      "SW": [
                        "SW1"
                      ],
                      "Type": [
                        "Connection",
                        "Auth",
                        "Honeypot"
                      ],
                      "Name": "Name1"
                    }
                  ],
                  "Note": "Malware download during honeypot session",
                  "Source": [
                    {
                      "URL": [
                        "http://1.1.1.1/x/1sh"
                      ],
                      "Type": [
                        "Malware"
                      ],
                      "Port": [
                        1111
                      ],
                      "IP4": [
                        "1.1.1.1"
                      ],
                      "Proto": [
                        "tcp",
                        "http"
                      ]
                    }
                  ],
                  "ID": "1a1a1a1a-1111-1a1a-1a11-1a1a1a1a1a1a",
                  "Attach": [
                    {
                      "Content": "base64-encoded",
                      "Hash": [
                        "sha1:1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a"
                      ],
                      "ContentEncoding": "base64",
                      "Note": "Some probably malicious code downloaded during honeypot SSH session",
                      "FileName": [
                        "1sh"
                      ],
                      "Type": [
                        "ShellCode"
                      ],
                      "ExternalURI": [
                        "http://1.1.1.1/x/1sh"
                      ],
                      "Size": 1655
                    }
                  ]
                }
            ]
            ''',
            [
                dict(
                    time='2022-04-28 12:35:45.718318',
                    category='malurl',
                    address=[{'ip': '1.1.1.1'}],
                    dport=1111,
                    proto='tcp',
                    name='Malware download during honeypot session',
                    url='http://1.1.1.1/x/1sh',
                ),
            ]
        )
        # "Abusive.Spam" category
        yield (
            b'''
            [
                {
                  "DetectTime": "2022-04-28 13:08:46+02:00",
                  "Category": [
                    "Abusive.Spam"
                  ],
                  "Description": "Blacklisted host",
                  "Format": "IDEA0",
                  "_CESNET": {
                    "Impact": "IP was blacklisted, list will be used for email filtering"
                  },
                  "ID": "1a1a1a1a-1111-1a1a-1a11-1a1a1a1a1a1a",
                  "Note": "IP was blacklisted, because it is listed on more than 2 public blacklists. Block duration: 7 days.",
                  "Source": [
                    {
                      "IP": [
                        "1.1.1.1"
                      ],
                      "Type": [
                        "Spam"
                      ],
                      "Proto": [
                        "tcp",
                        "smtp"
                      ]
                    }
                  ],
                  "CreateTime": "2022-04-28 13:08:47+02:00",
                  "Node": [
                    {
                      "Type": [
                        "Relay"
                      ],
                      "Name": "Name1"
                    },
                    {
                      "Type": [
                        "Log",
                        "Statistical"
                      ],
                      "SW": [
                        "SW1"
                      ],
                      "Name": "Name2"
                    }
                  ]
                }
            ]
            ''',
            [
                dict(
                    time='2022-04-28 11:08:46',
                    category='spam',
                    address=[{'ip': '1.1.1.1'}],
                    proto='tcp',
                    name='Blacklisted host',
                ),
            ]
        )
        # "Abusive.Spam" category with no Source
        yield (
            b'''
            [
                {
                  "DetectTime": "2022-04-28 13:08:46+02:00",
                  "Category": [
                    "Abusive.Spam"
                  ],
                  "Description": "Blacklisted host",
                  "Format": "IDEA0",
                  "_CESNET": {
                    "Impact": "IP was blacklisted, list will be used for email filtering"
                  },
                  "ID": "1a1a1a1a-1111-1a1a-1a11-1a1a1a1a1a1a",
                  "Note": "IP was blacklisted, because it is listed on more than 2 public blacklists. Block duration: 7 days.",
                  "CreateTime": "2022-04-28 13:08:47+02:00",
                  "Node": [
                    {
                      "Type": [
                        "Relay"
                      ],
                      "Name": "Name1"
                    },
                    {
                      "Type": [
                        "Log",
                        "Statistical"
                      ],
                      "SW": [
                        "SW1"
                      ],
                      "Name": "Name2"
                    }
                  ]
                }
            ]
            ''',
            []
        )
        # "Anomaly.Traffic" category
        yield (
            b'''
            [
                {
                  "Category": [
                    "Anomaly.Traffic"
                  ],
                  "WinStartTime": "2022-04-26T18:52:55+02:00",
                  "FlowCountDropped": 0,
                  "Note": "1.1.1.1/32 (Src-IP) - 'TCP SYN against internal IP address ranges from outside, sources' - DETECTED,  PacketCount and ByteCount are extrapolated from sampled data and might be inaccurate.",
                  "Source": [
                    {
                      "Proto": [
                        "tcp"
                      ],
                      "PortCount": 64,
                      "ProtoCount": 1,
                      "Note": "Counts are measured up to 64 distinct values - incomplete list.",
                      "Interface": [
                        402,
                        405
                      ],
                      "BitMask": [
                        "32"
                      ],
                      "IP4": [
                        "1.1.1.1"
                      ],
                      "InterfaceCount": 2,
                      "Router": [
                        "1347"
                      ],
                      "IP4Count": 1,
                      "Type": [
                        "Incomplete"
                      ],
                      "Port": [
                        11111,
                        22222
                      ]
                    }
                  ],
                  "PacketCount": 17730,
                  "EndTime": "2022-04-26T18:53:10+02:00",
                  "Node": [
                    {
                      "Type": [
                        "Relay"
                      ],
                      "Name": "Name1"
                    },
                    {
                      "Type": [
                        "Flow"
                      ],
                      "SW": [
                        "SW1"
                      ],
                      "Name": "Name2"
                    }
                  ],
                  "ByteCountDropped": 0,
                  "Description": "TCP SYN against internal IP address ranges from outside, sources - DETECTED",
                  "AvgPacketSize": 44,
                  "Format": "IDEA0",
                  "PacketCountDropped": 0,
                  "ByteCount": 786383,
                  "FlowCount": 298,
                  "DetectTime": "2022-04-26T18:54:23+02:00",
                  "Target": [
                    {
                      "Proto": [
                        "tcp"
                      ],
                      "PortCount": 1,
                      "ProtoCount": 1,
                      "Note": "Counts are measured up to 64 distinct values - incomplete list.",
                      "Interface": [
                        156
                      ],
                      "IP4": [
                        "2.2.2.2",
                        "3.3.3.3"
                      ],
                      "InterfaceCount": 1,
                      "IP4Count": 64,
                      "Type": [
                        "Incomplete"
                      ],
                      "Port": [
                        3333
                      ]
                    }
                  ],
                  "WinEndTime": "2022-04-26T18:53:10+02:00",
                  "ID": "redacted",
                  "Attach": [
                    {
                      "Note": "Traffic sample (up to 20 records)",
                      "Content": "redacted",
                      "ContentType": "text/csv"
                    }
                  ],
                  "StartTime": "2022-04-26T18:52:55+02:00",
                  "Duration": 15,
                  "CreateTime": "2022-04-26T18:54:23+02:00"
                }
            ]
            ''',
            [
                dict(
                    time='2022-04-26 16:54:23',
                    category='flow-anomaly',
                    address=[{'ip': '1.1.1.1'}],
                    dport=3333,
                    proto='tcp',
                    name='TCP SYN against internal IP address ranges from outside, sources - DETECTED',
                ),
            ]
        )
        # "Intrusion.UserCompromise" category - flavor 1
        yield (
            b'''
            [
                {
                  "Category": [
                    "Intrusion.UserCompromise"
                  ],
                  "DetectTime": "2022-04-26T05:12:22.827517+00:00",
                  "EventTime": "2022-04-26T05:12:22.827517+00:00",
                  "Description": "SSH login on honeypot (HaaS)",
                  "Format": "IDEA0",
                  "CeaseTime": "2022-04-26T05:13:23.026299+00:00",
                  "CreateTime": "2022-04-27T01:30:03Z",
                  "Note": "Extracted from data of REDACTED project",
                  "Source": [
                    {
                      "IP4": [
                        "1.1.1.1"
                      ],
                      "Proto": [
                        "tcp",
                        "ssh"
                      ]
                    }
                  ],
                  "ID": "1a1a1a1a-1111-1a1a-1a11-1a1a1a1a1a1a",
                  "Node": [
                    {
                      "Note": "A script converting daily HaaS data dumps from REDACTED",
                      "Type": [
                        "Connection",
                        "Auth",
                        "Honeypot"
                      ],
                      "SW": [
                        "SW1"
                      ],
                      "Name": "Name1"
                    }
                  ],
                  "Attach": [
                    {
                      "Note": "commands",
                      "Content": "[]",
                      "Type": [
                        "ShellCode"
                      ],
                      "ContentType": "application/json"
                    }
                  ]
                }
            ]
            ''',
            [
                dict(
                    time='2022-04-26 05:12:22.827517',
                    category='server-exploit',
                    address=[{'ip': '1.1.1.1'}],
                    proto='tcp',
                    name='SSH login on honeypot (HaaS)',
                ),
            ]
        )
        # "Intrusion.UserCompromise" category - flavor 2
        yield (
            b'''
            [
                {
                  "DetectTime": "2022-04-26T18:08:02.547234Z",
                  "Category": [
                    "Intrusion.UserCompromise"
                  ],
                  "Target": [
                    {
                      "Port": [
                        2222
                      ],
                      "IP4": [
                        "2.2.2.2"
                      ],
                      "Proto": [
                        "tcp",
                        "ssh"
                      ]
                    }
                  ],
                  "Format": "IDEA0",
                  "Node": [
                    {
                      "SW": [
                        "SW2"
                      ],
                      "Type": [
                        "Connection",
                        "Auth",
                        "Honeypot"
                      ],
                      "Name": "Name2"
                    }
                  ],
                  "Note": "SSH successful login",
                  "Source": [
                    {
                      "Port": [
                        11111
                      ],
                      "IP4": [
                        "1.1.1.1"
                      ],
                      "Proto": [
                        "tcp",
                        "ssh"
                      ]
                    }
                  ],
                  "ID": "1a1a1a1a-1111-1a1a-1a11-1a1a1a1a1a1a"
                }
            ]
            ''',
            [
                dict(
                    time='2022-04-26 18:08:02.547234',
                    category='server-exploit',
                    address=[{'ip': '1.1.1.1'}],
                    dip='2.2.2.2',
                    sport=11111,
                    dport=2222,
                    proto='tcp',
                    name='SSH successful login',
                ),
            ]
        )
        # "Recon.Scanning" category - flavor 1
        yield (
            b'''
            [
                {
                  "DetectTime": "2022-04-26T14:36:01Z",
                  "Node": [
                    {
                      "Type": [
                        "Relay"
                      ],
                      "Name": "Name1"
                    },
                    {
                      "Type": [
                        "Flow",
                        "Statistical"
                      ],
                      "SW": [
                        "SW1",
                        "SW2"
                      ],
                      "Name": "Name2"
                    }
                  ],
                  "EventTime": "2022-04-26T14:31:00Z",
                  "Description": "Horizontal port scan",
                  "ConnCount": 2041,
                  "CeaseTime": "2022-04-26T14:35:59Z",
                  "Format": "IDEA0",
                  "Category": [
                    "Recon.Scanning"
                  ],
                  "ID": "1a1a1a1a-1111-1a1a-1a11-1a1a1a1a1a1a",
                  "Source": [
                    {
                      "IP4": [
                        "1.1.1.1"
                      ],
                      "Proto": [
                        "tcp"
                      ]
                    }
                  ],
                  "FlowCount": 2041,
                  "CreateTime": "2022-04-26T14:36:01Z"
                }
            ]
            ''',
            [
                dict(
                    time='2022-04-26 14:36:01',
                    category='scanning',
                    address=[{'ip': '1.1.1.1'}],
                    proto='tcp',
                    name='Horizontal port scan',
                ),
            ]
        )
        # "Recon.Scanning" category - flavor 2
        yield (
            b'''
            [
                {
                  "DetectTime": "2022-04-26T15:05:38Z",
                  "Category": [
                    "Recon.Scanning"
                  ],
                  "EventTime": "2022-04-26T14:13:04Z",
                  "Description": "Block portscan using TCP SYN",
                  "CeaseTime": "2022-04-26T15:05:38Z",
                  "Format": "IDEA0",
                  "ID": "1a1a1a1a-1111-1a1a-1a11-1a1a1a1a1a1a",
                  "Source": [
                    {
                      "IP4": [
                        "1.1.1.1"
                      ],
                      "Proto": [
                        "tcp"
                      ]
                    }
                  ],
                  "FlowCount": 50000,
                  "CreateTime": "2022-04-26T15:06:11Z",
                  "Node": [
                    {
                      "Type": [
                        "Relay"
                      ],
                      "Name": "Name1"
                    },
                    {
                      "AggrWin": "00:05:00",
                      "Type": [
                        "Flow",
                        "Statistical"
                      ],
                      "SW": [
                        "SW1",
                        "SW2"
                      ],
                      "Name": "Name2"
                    }
                  ],
                  "Target": [
                    {
                      "IP4": [
                        "2.2.2.2",
                        "3.3.3.3"
                      ],
                      "Proto": [
                        "tcp"
                      ]
                    }
                  ]
                }
            ]
            ''',
            [
                dict(
                    time='2022-04-26 15:05:38',
                    category='scanning',
                    address=[{'ip': '1.1.1.1'}],
                    proto='tcp',
                    name='Block portscan using TCP SYN',
                ),
            ]
        )
        # "Recon.Scanning" category - flavor 3
        yield (
            b'''
            [
                {
                  "DetectTime": "2022-04-26T14:29:21Z",
                  "Node": [
                    {
                      "Type": [
                        "Relay"
                      ],
                      "Name": "Name1"
                    },
                    {
                      "Type": [
                        "Flow",
                        "Statistical"
                      ],
                      "SW": [
                        "SW1",
                        "SW2"
                      ],
                      "Name": "Name2"
                    }
                  ],
                  "EventTime": "2022-04-26T14:24:20Z",
                  "Description": "Horizontal port scan",
                  "ConnCount": 5880,
                  "CeaseTime": "2022-04-26T14:29:20Z",
                  "Format": "IDEA0",
                  "Category": [
                    "Recon.Scanning"
                  ],
                  "ID": "1a1a1a1a-1111-1a1a-1a11-1a1a1a1a1a1a",
                  "Source": [
                    {
                      "IP4": [
                        "1.1.1.1"
                      ],
                      "Proto": [
                        "tcp"
                      ]
                    }
                  ],
                  "FlowCount": 5880,
                  "CreateTime": "2022-04-26T14:29:21Z"
                }
            ]
            ''',
            [
                dict(
                    time='2022-04-26 14:29:21',
                    category='scanning',
                    address=[{'ip': '1.1.1.1'}],
                    proto='tcp',
                    name='Horizontal port scan',
                ),
            ]
        )
        # "Recon.Scanning" category - flavor 4
        yield (
            b'''
            [
                {
                  "DetectTime": "2022-04-26T15:34:25Z",
                  "Category": [
                    "Recon.Scanning"
                  ],
                  "EventTime": "2022-04-26T15:33:15Z",
                  "Description": "Vertical scan using TCP SYN",
                  "CeaseTime": "2022-04-26T15:34:25Z",
                  "Format": "IDEA0",
                  "ID": "1a1a1a1a-1111-1a1a-1a11-1a1a1a1a1a1a",
                  "Source": [
                    {
                      "IP4": [
                        "1.1.1.1"
                      ],
                      "Proto": [
                        "tcp"
                      ]
                    }
                  ],
                  "FlowCount": 100,
                  "CreateTime": "2022-04-26T15:35:31Z",
                  "Node": [
                    {
                      "Type": [
                        "Relay"
                      ],
                      "Name": "Name1"
                    },
                    {
                      "AggrWin": "00:05:00",
                      "Type": [
                        "Flow",
                        "Statistical"
                      ],
                      "SW": [
                        "SW1",
                        "SW2"
                      ],
                      "Name": "Name2"
                    }
                  ],
                  "Target": [
                    {
                      "IP4": [
                        "2.2.2.2"
                      ],
                      "Proto": [
                        "tcp"
                      ]
                    }
                  ]
                }
            ]
            ''',
            [
                dict(
                    time='2022-04-26 15:34:25',
                    category='scanning',
                    address=[{'ip': '1.1.1.1'}],
                    dip='2.2.2.2',
                    proto='tcp',
                    name='Vertical scan using TCP SYN',
                ),
            ]
        )
        # "Recon.Scanning" category - flavor 5
        yield (
            b'''
            [
                {
                  "DetectTime": "2022-04-26T15:34:41.717979+00:00",
                  "Category": [
                    "Recon.Scanning"
                  ],
                  "EventTime": "2022-04-26T14:57:52.004638+00:00",
                  "Description": "Port scan detected from firewall logs",
                  "ConnCount": 2,
                  "CeaseTime": "2022-04-26T14:57:53.503507+00:00",
                  "Format": "IDEA0",
                  "Node": [
                    {
                      "SW": [
                        "SW1"
                      ],
                      "Type": [
                        "Log",
                        "Statistical"
                      ],
                      "Name": "Name1"
                    }
                  ],
                  "Source": [
                    {
                      "IP4": [
                        "1.1.1.1"
                      ]
                    }
                  ],
                  "ID": "1a1a1a1a-1111-1a1a-1a11-1a1a1a1a1a1a",
                  "Target": [
                    {
                      "Hostname": [
                        "example1.com",
                        "example2.com"
                      ],
                      "Port": [
                        2222
                      ],
                      "IP4": [
                        "2.2.2.2",
                        "3.3.3.3"
                      ]
                    }
                  ]
                }
            ]
            ''',
            [
                dict(
                    time='2022-04-26 15:34:41.717979',
                    category='scanning',
                    address=[{'ip': '1.1.1.1'}],
                    dport=2222,
                    name='Port scan detected from firewall logs',
                ),
            ]
        )
        # "Attempt.Login" category - flavor 1
        yield (
            b'''
            [
                {
                  "DetectTime": "2022-04-26T17:38:00Z",
                  "Node": [
                    {
                      "Type": [
                        "Relay"
                      ],
                      "Name": "Name1"
                    },
                    {
                      "Type": [
                        "Flow",
                        "Statistical"
                      ],
                      "SW": [
                        "SW1",
                        "SW2"
                      ],
                      "Name": "Name2"
                    }
                  ],
                  "EventTime": "2022-04-26T17:32:54Z",
                  "Description": "SSH dictionary/bruteforce attack",
                  "ConnCount": 121,
                  "CeaseTime": "2022-04-26T17:37:59Z",
                  "Format": "IDEA0",
                  "Category": [
                    "Attempt.Login"
                  ],
                  "ID": "1a1a1a1a-1111-1a1a-1a11-1a1a1a1a1a1a",
                  "Source": [
                    {
                      "IP4": [
                        "1.1.1.1"
                      ]
                    }
                  ],
                  "FlowCount": 242,
                  "CreateTime": "2022-04-26T17:38:00Z",
                  "Target": [
                    {
                      "Port": [
                        2222
                      ],
                      "Proto": [
                        "tcp",
                        "ssh"
                      ]
                    }
                  ]
                }
            ]
            ''',
            [
                dict(
                    time='2022-04-26 17:38:00',
                    category='server-exploit',
                    address=[{'ip': '1.1.1.1'}],
                    dport=2222,
                    proto='tcp',
                    name='SSH dictionary/bruteforce attack',
                ),
            ]
        )
        # "Attempt.Login" category - flavor 2
        yield (
            b'''
            [
                {
                  "DetectTime": "2022-04-26T16:59:01Z",
                  "Node": [
                    {
                      "Type": [
                        "Relay"
                      ],
                      "Name": "Name1"
                    },
                    {
                      "Type": [
                        "Flow",
                        "Statistical"
                      ],
                      "SW": [
                        "SW1",
                        "SW2"
                      ],
                      "Name": "Name2"
                    }
                  ],
                  "EventTime": "2022-04-26T16:54:00Z",
                  "Description": "SSH dictionary/bruteforce attack",
                  "ConnCount": 79,
                  "CeaseTime": "2022-04-26T16:58:57Z",
                  "Format": "IDEA0",
                  "Category": [
                    "Attempt.Login"
                  ],
                  "ID": "1a1a1a1a-1111-1a1a-1a11-1a1a1a1a1a1a",
                  "Source": [
                    {
                      "IP4": [
                        "1.1.1.1"
                      ]
                    }
                  ],
                  "FlowCount": 158,
                  "CreateTime": "2022-04-26T16:59:01Z",
                  "Target": [
                    {
                      "Port": [
                        2222
                      ],
                      "Proto": [
                        "tcp",
                        "ssh"
                      ]
                    }
                  ]
                }
            ]
            ''',
            [
                dict(
                    time='2022-04-26 16:59:01',
                    category='server-exploit',
                    address=[{'ip': '1.1.1.1'}],
                    dport=2222,
                    proto='tcp',
                    name='SSH dictionary/bruteforce attack',
                ),
            ]
        )
        # "Attempt.Login" category - flavor 3
        yield (
            b'''
            [
                {
                  "Category": [
                    "Attempt.Login"
                  ],
                  "DetectTime": "2022-04-26T10:21:41.677787+00:00",
                  "EventTime": "2022-04-26T10:21:41.677787+00:00",
                  "Description": "Unsuccessful SSH login attempt on honeypot (HaaS)",
                  "Format": "IDEA0",
                  "CeaseTime": "2022-04-26T10:21:42.688382+00:00",
                  "CreateTime": "2022-04-27T01:30:05Z",
                  "Note": "Extracted from data of REDACTED HaaS project",
                  "Source": [
                    {
                      "IP4": [
                        "1.1.1.1"
                      ],
                      "Proto": [
                        "tcp",
                        "ssh"
                      ]
                    }
                  ],
                  "ID": "1a1a1a1a-1111-1a1a-1a11-1a1a1a1a1a1a",
                  "Node": [
                    {
                      "Note": "A script converting daily HaaS data dumps from REDACTED",
                      "Type": [
                        "Connection",
                        "Auth",
                        "Honeypot"
                      ],
                      "SW": [
                        "SW1"
                      ],
                      "Name": "Name1"
                    }
                  ]
                }
            ]
            ''',
            [
                dict(
                    time='2022-04-26 10:21:41.677787',
                    category='server-exploit',
                    address=[{'ip': '1.1.1.1'}],
                    proto='tcp',
                    name='Unsuccessful SSH login attempt on honeypot (HaaS)',
                ),
            ]
        )
        # "Attempt.Login" category - flavor 4
        yield (
            b'''
            [
                {
                  "DetectTime": "2022-04-26T18:24:43.979218+00:00",
                  "Category": [
                    "Attempt.Login"
                  ],
                  "EventTime": "2022-04-26T17:16:21.294196+00:00",
                  "Description": "Unsuccessful login attempts (SSHD)",
                  "ConnCount": 30,
                  "CeaseTime": "2022-04-26T18:03:08.204561+00:00",
                  "Format": "IDEA0",
                  "Node": [
                    {
                      "SW": [
                        "SW1"
                      ],
                      "Type": [
                        "Log",
                        "Statistical"
                      ],
                      "Name": "Name1"
                    }
                  ],
                  "Source": [
                    {
                      "IP4": [
                        "1.1.1.1"
                      ],
                      "Proto": [
                        "tcp",
                        "ssh"
                      ]
                    }
                  ],
                  "ID": "1a1a1a1a-1111-1a1a-1a11-1a1a1a1a1a1a",
                  "Attach": [
                    {
                      "Note": "Usernames",
                      "Content": "root (123qwerty)\\nfoo\\nbar\\nwhatever\\n",
                      "ContentType": "text/plain"
                    }
                  ],
                  "Target": [
                    {
                      "Hostname": [
                        "example.com"
                      ],
                      "Port": [
                        2222
                      ],
                      "IP4": [
                        "2.2.2.2"
                      ],
                      "Proto": [
                        "tcp",
                        "ssh"
                      ]
                    }
                  ]
                }
            ]
            ''',
            [
                dict(
                    time='2022-04-26 18:24:43.979218',
                    category='server-exploit',
                    address=[{'ip': '1.1.1.1'}],
                    dip='2.2.2.2',
                    dport=2222,
                    proto='tcp',
                    name='Unsuccessful login attempts (SSHD)',
                ),
            ]
        )
        # "Attempt.Login" category - flavor 5
        yield (
            b'''
            [
                {
                  "DetectTime": "2022-04-26T17:47:49.871850Z",
                  "Category": [
                    "Attempt.Login"
                  ],
                  "Target": [
                    {
                      "IP4": [
                        "2.2.2.2"
                      ],
                      "Proto": [
                        "tcp",
                        "ssh"
                      ]
                    }
                  ],
                  "ConnCount": 2,
                  "Format": "IDEA0",
                  "Node": [
                    {
                      "AggrWin": "00:05:00",
                      "SW": [
                        "SW1"
                      ],
                      "Type": [
                        "Connection",
                        "Auth",
                        "Honeypot"
                      ],
                      "Name": "Name1"
                    }
                  ],
                  "Note": "SSH login attempt",
                  "Source": [
                    {
                      "IP4": [
                        "1.1.1.1"
                      ],
                      "Proto": [
                        "tcp",
                        "ssh"
                      ]
                    }
                  ],
                  "WinStartTime": "2022-04-26T17:42:49.871850Z",
                  "WinEndTime": "2022-04-26T17:47:49.871850Z",
                  "ID": "1a1a1a1a-1111-1a1a-1a11-1a1a1a1a1a1a"
                }
            ]
            ''',
            [
                dict(
                    time='2022-04-26 17:47:49.871850',
                    category='server-exploit',
                    address=[{'ip': '1.1.1.1'}],
                    dip='2.2.2.2',
                    proto='tcp',
                    name='SSH login attempt',
                ),
            ]
        )
        # "Attempt.Login" category - flavor 6
        yield (
            b'''
            [
                {
                  "DetectTime": "2022-12-05T11:03:01Z",
                  "Node": [
                    {
                      "Type": [
                        "Relay"
                      ],
                      "Name": "Name1"
                    },
                    {
                      "Type": [
                        "Flow",
                        "Statistical"
                      ],
                      "SW": [
                        "SW1",
                        "SW2"
                      ],
                      "Name": "Name2"
                    }
                  ],
                  "EventTime": "2022-12-05T10:57:52Z",
                  "Description": "SSH dictionary/bruteforce attack",
                  "ConnCount": 65,
                  "CeaseTime": "2022-12-05T11:02:42Z",
                  "Format": "IDEA0",
                  "Category": [
                    "Attempt.Login"
                  ],
                  "ID": "1a1a1a1a-1111-1a1a-1a11-1a1a1a1a1a1a",
                  "FlowCount": 130,
                  "CreateTime": "2022-12-05T11:03:01Z",
                  "Target": [
                    {
                      "Port": [
                        22
                      ],
                      "IP4": [
                        "1.1.1.1"
                      ],
                      "Proto": [
                        "tcp",
                        "ssh"
                      ]
                    }
                  ]
                }
            ]
            ''',
            []
        )
        # Invalid JSON
        yield (
            b'Invalid',
            ValueError
        )
