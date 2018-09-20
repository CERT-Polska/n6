// List of available search criteria

import sortBy from 'lodash-es/sortBy';
import {
  alpha,
  integer,
  ipAddress,
  minLength,
  maxLength,
  required,
} from 'vuelidate/lib/validators';

import { weekAgo } from '../helpers/dates';
import {
  cidr,
  domain,
  domainPart,
  hexadecimal,
  url,
} from '../helpers/validators';

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
    validations: {
      required,
    },
  },

  {
    label: 'Start date',
    id: 'time.min',
    type: 'datetime',
    required: true,
    get defaultValue() {
      return weekAgo();
    },
    validations: {
      required,
    },
  },

  {
    label: 'End date',
    id: 'time.max',
    type: 'datetime',
    get defaultValue() {
      return new Date();
    },
    validations: {
      required,
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
    validations: {
      required,
    },
  },

  {
    label: 'Name',
    id: 'name',
    type: 'text',
    validations: {
      required,
    },
  },

  {
    label: 'Target',
    id: 'target',
    type: 'text',
    validations: {
      required,
    },
  },

  {
    label: 'Domain',
    id: 'fqdn',
    type: 'text',
    validations: {
      required,
      $each: {
        domain: domain,
      },
    },
  },

  {
    label: 'Domain part',
    id: 'fqdn.sub',
    type: 'text',
    validations: {
      required,
      $each: {
        domainPart,
      },
    },
  },

  {
    label: 'URL',
    id: 'url',
    type: 'text',
    validations: {
      required,
      $each: {
        url: url,
      },
    },
  },

  {
    label: 'URL part',
    id: 'url.sub',
    type: 'text',
    validations: {
      required,
    },
  },

  {
    label: 'IP',
    id: 'ip',
    type: 'text',
    validations: {
      required,
      $each: {
        ipAddress,
      },
    },
  },

  {
    label: 'IP net (CIDR)',
    id: 'ip.net',
    type: 'text',
    validations: {
      required,
      $each: {
        cidr: cidr,
      },
    },
  },

  {
    label: 'ASN',
    id: 'asn',
    type: 'text',
    validations: {
      required,
      $each: {
        integer,
      },
    },
  },

  {
    label: 'Country',
    id: 'cc',
    type: 'text',
    validations: {
      $each: {
        alpha,
        minLength: minLength(2),
        maxLength: maxLength(2),
      },
      required,
    },
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
    validations: {
      required,
      $each: {
        integer,
        minLength: minLength(0),
        maxLength: maxLength(65535), // 2^16 - 1
      },
    },
  },

  {
    label: 'Destination port',
    id: 'dport',
    type: 'text',
    validations: {
      required,
      $each: {
        integer,
        minLength: minLength(0),
        maxLength: maxLength(65535), // 2^16 - 1
      },
    },
  },

  {
    label: 'MD5',
    id: 'md5',
    type: 'text',
    validations: {
      required,
      $each: {
        hexadecimal,
        minLength: minLength(32),
        maxLength: maxLength(32),
      },
    },
  },

  {
    label: 'SHA1',
    id: 'sha1',
    type: 'text',
    validations: {
      hexadecimal,
      $each: {
        required,
        minLength: minLength(40),
        maxLength: maxLength(40),
      },
    },
  },
];

// Sort criteria alphabetically
criteria = sortBy(criteria, ['label']);

export default criteria;
