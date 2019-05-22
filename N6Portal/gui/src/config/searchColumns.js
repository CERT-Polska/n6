// List of columns displayed in search table with their configuration

import sortBy from 'lodash-es/sortBy';

let columns = [
  {
    key: 'time',
    label: 'Time',
    type: 'datetime',
    checked: true,
    tooltip: 'Time of the event',
  },

  {
    key: 'category',
    label: 'Category',
    type: 'text',
    checked: true,
    tooltip: 'Category of the event',
  },

  {
    key: 'name',
    label: 'Name',
    type: 'text',
    checked: true,
    tooltip: 'Name of the threat/problem',
  },

  {
    key: 'ip',
    label: 'IP',
    type: 'text',
    checked: true,
    tooltip: 'IP address associated with the event',
    array: true,
    parent: 'address',
  },

  {
    key: 'asn',
    label: 'ASN',
    type: 'number',
    checked: true,
    tooltip: 'Autonomous System Number',
    array: true,
    parent: 'address',
  },

  {
    key: 'cc',
    label: 'Country',
    type: 'text',
    checked: true,
    tooltip: 'Country (geolocation)',
    array: true,
    parent: 'address',
  },

  {
    key: 'fqdn',
    label: 'FQDN',
    type: 'text',
    checked: true,
    tooltip: 'Fully-qualified domain name',
  },

  {
    key: 'source',
    label: 'Source',
    type: 'text',
    checked: true,
    tooltip: 'Identifier of the information provider',
  },

  {
    key: 'confidence',
    label: 'Confidence',
    type: 'text',
    checked: true,
    tooltip: 'Estimated confidence of the information',
  },

  {
    key: 'url',
    label: 'URL',
    type: 'text',
    checked: true,
    tooltip: 'Complete URL associated with the event',
  },

  {
    key: 'origin',
    label: 'Origin',
    type: 'text',
    checked: false,
    tooltip: 'How the information was obtained',
  },

  {
    key: 'proto',
    label: 'Protocol',
    type: 'text',
    checked: false,
    tooltip: 'Protocol',
  },

  {
    key: 'sport',
    label: 'Src.port',
    type: 'number',
    checked: false,
    tooltip: 'Source TCP/UDP port',
  },

  {
    key: 'dport',
    label: 'Dest.port',
    type: 'number',
    checked: false,
    tooltip: 'Destination TCP/UDP port',
  },

  {
    key: 'dip',
    label: 'Dest.IP',
    type: 'text',
    checked: false,
    tooltip: 'Destination IP address',
  },

  {
    key: 'md5',
    label: 'MD5',
    type: 'text',
    checked: false,
    tooltip: 'MD5 hash of the associated sample',
  },

  {
    key: 'sha1',
    label: 'SHA1',
    type: 'text',
    checked: false,
    tooltip: 'SHA1 hash of the associated sample',
  },

  {
    key: 'target',
    label: 'Target',
    type: 'text',
    checked: false,
    tooltip: 'Organization or brand targetted by the attack',
  },

  {
    key: 'status',
    label: 'Status',
    type: 'text',
    checked: false,
    tooltip: 'Is the threat still reported as active',
  },

  {
    key: 'until',
    label: 'Until',
    type: 'datetime',
    checked: false,
    tooltip: 'Time when the blacklist entry expires',
  },

  {
    key: 'count',
    label: 'Count',
    type: 'number',
    checked: false,
    tooltip: 'Number of occurences',
  },
];

// Sort alphabetically
let columnsSorted = sortBy(columns, ['label']);

export {
  columns as default,
  columnsSorted,
};
