import { TCategory } from 'api/services/globalTypes';

export type TBarChart = {
  datasets: Record<TCategory, number[]>;
  days: string[];
  days_range?: number;
  empty_dataset?: boolean;
};

export const categoryColor: Record<TCategory, string> = {
  amplifier: '#091540',
  backdoor: '#e3e40d',
  bots: '#c5283d',
  cnc: '#6a4dfb',
  deface: '#5fa00d',
  'dns-query': '#c3f6dd',
  'dos-attacker': '#d1157c',
  'dos-victim': '#0ba7f7',
  exposed: '#24721a',
  flow: '#1b2939',
  'flow-anomaly': '#cbe655',
  fraud: '#a16174',
  leak: '#f208d1',
  malurl: '#8f78f5',
  'malware-action': '#c5ec36',
  other: '#FF0000',
  phish: '#946a89',
  proxy: '#56c74d',
  'sandbox-url': '#59c88e',
  scam: '#3556a3',
  scanning: '#5c1778',
  'server-exploit': '#d83b50',
  spam: '#21a4f0',
  'spam-url': '#79fa45',
  tor: '#d5c41e',
  vulnerable: '#1eff02',
  webinject: '#24c856'
};

export const categories = Object.keys(categoryColor) as TCategory[];
