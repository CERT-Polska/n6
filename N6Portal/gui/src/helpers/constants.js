// Common constants that can be used across the application

export const FLASH_MESSAGE_LABELS = Object.freeze({
  cert_avail_label: 'cert_avail_msg',
});

export const API_RESOURCES = {
  '/search/events': {
    selectValue: 'events',
    selectText: 'Events',
  },
  '/report/inside': {
    selectValue: 'threats-inside',
    selectText: 'Threats inside network',
  },
  '/report/threats': {
    selectValue: 'threats-other',
    selectText: 'Other threats',
  },
};
