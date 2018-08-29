// List of columns displayed in search table with their configuration

import sortBy from 'lodash-es/sortBy';

let columns = [
  {
    key: 'time',
    label: 'Time',
    type: 'datetime',
    checked: true,
  },

  {
    key: 'category',
    label: 'Category',
    type: 'text',
    checked: true,
  },

  {
    key: 'name',
    label: 'Name',
    type: 'text',
    checked: true,
  },

  {
    key: 'ip',
    label: 'IP',
    type: 'text',
    checked: true,
    array: true,
    parent: 'address',
  },

  {
    key: 'asn',
    label: 'ASN',
    type: 'number',
    checked: true,
    array: true,
    parent: 'address',
  },

  {
    key: 'cc',
    label: 'Country',
    type: 'text',
    checked: true,
    array: true,
    parent: 'address',
  },

  {
    key: 'fqdn',
    label: 'FQDN',
    type: 'text',
    checked: true,
  },

  {
    key: 'source',
    label: 'Source',
    type: 'text',
    checked: true,
  },

  {
    key: 'confidence',
    label: 'Confidence',
    type: 'text',
    checked: true,
  },

  {
    key: 'url',
    label: 'URL',
    type: 'text',
    checked: true,
  },

  {
    key: 'origin',
    label: 'Origin',
    type: 'text',
    checked: false,
  },

  {
    key: 'proto',
    label: 'Protocol',
    type: 'text',
    checked: false,
  },

  {
    key: 'sport',
    label: 'Src.port',
    type: 'number',
    checked: false,
  },

  {
    key: 'dport',
    label: 'Dest.port',
    type: 'number',
    checked: false,
  },

  {
    key: 'dip',
    label: 'Dest.IP',
    type: 'text',
    checked: false,
  },

  {
    key: 'md5',
    label: 'MD5',
    type: 'text',
    checked: false,
  },

  {
    key: 'sha1',
    label: 'SHA1',
    type: 'text',
    checked: false,
  },

  {
    key: 'target',
    label: 'Target',
    type: 'text',
    checked: false,
  },

  {
    key: 'status',
    label: 'Status',
    type: 'text',
    checked: false,
  },

  {
    key: 'until',
    label: 'Until',
    type: 'datetime',
    checked: false,
  },

  {
    key: 'count',
    label: 'Count',
    type: 'number',
    checked: false,
  },
];

// Sort alphabetically
let columnsSorted = sortBy(columns, ['label']);

export {
  columns as default,
  columnsSorted,
};
