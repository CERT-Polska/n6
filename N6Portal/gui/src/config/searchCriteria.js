// List of available search criteria

import sortBy from 'lodash-es/sortBy';

function dateWeekAgo() {
  // Get current date
  let date = new Date();
  // Subtract 7 days
  date.setUTCDate(date.getUTCDate() - 7);
  // Reset time to midnight
  date.setUTCHours(0, 0, 0, 0);
  return date;
}

let criteria = [
  {
    label: 'Max results',
    id: 'opt.limit',
    type: 'select',
    required: true,
    defaultValue: 100,
    possibleOptions: [
      {
        value: 10,
        label: '10',
      },
      {
        value: 50,
        label: '50',
      },
      {
        value: 100,
        label: '100',
      },
      {
        value: 200,
        label: '200',
      },
      {
        value: 500,
        label: '500',
      },
      {
        value: 1000,
        label: '1000',
      },
    ],
  },

  {
    label: 'Start date',
    id: 'time.min',
    type: 'datetime',
    required: true,
    get defaultValue() {
      return dateWeekAgo();
    },
  },

  {
    label: 'End date',
    id: 'time.max',
    type: 'datetime',
    get defaultValue() {
      return new Date();
    },
  },

  {
    label: 'Category',
    id: 'category',
    type: 'multiSelect',
    possibleOptions: [
      {
        value: 'amplifier',
        label: 'Amplifier',
      },
      {
        value: 'bots',
        label: 'Bots',
      },
      {
        value: 'backdoor',
        label: 'Backdoor',
      },
      {
        value: 'cnc',
        label: 'CNC',
      },
      {
        value: 'deface',
        label: 'Deface',
      },
      {
        value: 'dns-query',
        label: 'DNS query',
      },
      {
        value: 'dos-attacker',
        label: 'DoS attacker',
      },
      {
        value: 'dos-victim',
        label: 'DoS victim',
      },
      {
        value: 'flow',
        label: 'Flow',
      },
      {
        value: 'flow-anomaly',
        label: 'Flow anomaly',
      },
      {
        value: 'fraud',
        label: 'Fraud',
      },
      {
        value: 'leak',
        label: 'Leak',
      },
      {
        value: 'malurl',
        label: 'MalURL',
      },
      {
        value: 'malware-action',
        label: 'Malware action',
      },
      {
        value: 'phish',
        label: 'Phish',
      },
      {
        value: 'proxy',
        label: 'Proxy',
      },
      {
        value: 'sandbox-url',
        label: 'Sandbox URL',
      },
      {
        value: 'scam',
        label: 'Scam',
      },
      {
        value: 'scanning',
        label: 'Scanning',
      },
      {
        value: 'server-exploit',
        label: 'Server exploit',
      },
      {
        value: 'spam',
        label: 'Spam',
      },
      {
        value: 'spam-url',
        label: 'Spam URL',
      },
      {
        value: 'tor',
        label: 'Tor',
      },
      {
        value: 'webinject',
        label: 'Web injection',
      },
      {
        value: 'vulnerable',
        label: 'Vulnerable',
      },
      {
        value: 'other',
        label: 'Other',
      },
    ],
  },

  {
    label: 'Name',
    id: 'name',
    type: 'text',
  },

  {
    label: 'Target',
    id: 'target',
    type: 'text',
  },

  {
    label: 'Domain',
    id: 'fqdn',
    type: 'text',
  },

  {
    label: 'Domain part',
    id: 'fqdn.sub',
    type: 'text',
  },

  {
    label: 'URL',
    id: 'url',
    type: 'text',
  },

  {
    label: 'URL part',
    id: 'url.sub',
    type: 'text',
  },

  {
    label: 'IP',
    id: 'ip',
    type: 'text',
  },

  {
    label: 'IP net (CIDR)',
    id: 'ip.net',
    type: 'text',
  },

  {
    label: 'ASN',
    id: 'asn',
    type: 'text',
  },

  {
    label: 'Country',
    id: 'cc',
    type: 'text',
  },

  {
    label: 'Protocol',
    id: 'proto',
    type: 'multiSelect',
    possibleOptions: [
      {
        value: 'tcp',
        label: 'TCP',
      },
      {
        value: 'udp',
        label: 'UDP',
      },
      {
        value: 'icmp',
        label: 'ICMP',
      },
    ],
  },

  {
    label: 'Source port',
    id: 'sport',
    type: 'text',
  },

  {
    label: 'Destination port',
    id: 'dport',
    type: 'text',
  },

  {
    label: 'MD5',
    id: 'md5',
    type: 'text',
  },

  {
    label: 'SHA1',
    id: 'sha1',
    type: 'text',
  },
];

// Sort criteria alphabetically
criteria = sortBy(criteria, ['label']);

export default criteria;
