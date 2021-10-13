// The list of objects describing available dashboard categories

let categories = [
  {
    id: 'amplifier',
    label: 'DDoS amplifier',
    help: 'A misconfigured server that can be abused for a distributed reflected denial of service (DRDoS).',
  },
  {
    id: 'bots',
    label: 'Bot',
    help: 'A computer or other device infected by malware.',
  },
  {
    id: 'backdoor',
    label: 'Backdoor',
    help: 'An address of a web shell or another type of backdoor installed on a compromised server.',
  },
  {
    id: 'cnc',
    label: 'C&C server',
    help: 'A command and Control (C2) server of malware.',
  },
  {
    id: 'deface',
    label: 'Deface',
    help: 'A defaced website.',
  },
  {
    id: 'dns-query',
    label: 'DNS query',
    help: 'DNS query',
  },
  {
    id: 'dos-attacker',
    label: 'DoS source',
    help: 'An address of a denial of service attack traffic.',
  },
  {
    id: 'dos-victim',
    label: 'DoS victim',
    help: 'An address that was a victim of a denial of service attack.',
  },
  {
    id: 'flow',
    label: 'Network flow',
    help: 'Network flow',
  },
  {
    id: 'flow-anomaly',
    label: 'A flow anomaly',
    help: 'A flow anomaly',
  },
  {
    id: 'fraud',
    label: 'Fraud',
    help: 'An activity or entity related to financial fraud.',
  },
  {
    id: 'leak',
    label: 'Data leak',
    help: 'Leaked credentials or personal data.',
  },
  {
    id: 'malurl',
    label: 'Malicious URL',
    help: 'A URL related to distribution of malware.',
  },
  {
    id: 'malware-action',
    label: 'Malware action',
    help: 'An action that malware is configured to make on infected machines.',
  },
  {
    id: 'other',
    label: 'Other',
    help: 'Other',
  },
  {
    id: 'phish',
    label: 'Phishing',
    help: 'An address related to a phishing campaign.',
  },
  {
    id: 'proxy',
    label: 'Proxy server',
    help: 'An open proxy server.',
  },
  {
    id: 'sandbox-url',
    label: 'Sandbox connection',
    help: 'Any URL contacted by malware, can be malicious or benign.',
  },
  {
    id: 'scam',
    label: 'Scam site',
    help: 'Scam site',
  },
  {
    id: 'scanning',
    label: 'Port scanning',
    help: 'A host performing port scanning.',
  },
  {
    id: 'server-exploit',
    label: 'Network attack',
    help: 'An active attempt to exploit a network service.',
  },
  {
    id: 'spam',
    label: 'Spam',
    help: 'An address sending spam.',
  },
  {
    id: 'spam-url',
    label: 'URL in spam',
    help: 'An address occuring in spam, without determining if it is malicious or benign.',
  },
  {
    id: 'tor',
    label: 'Tor node',
    help: 'Tor node',
  },
  {
    id: 'vulnerable',
    label: 'Vulnerable service',
    help: 'An address of a vulnerable device or service.',
  },
  {
    id: 'webinject',
    label: 'Webinject',
    help: 'An inject used by banking trojans or similar malware.',
  },
  {
    id: 'all_remaining',
    label: 'Remaining',
    help: 'Other security events/threats.',
  },
];

export default categories;
