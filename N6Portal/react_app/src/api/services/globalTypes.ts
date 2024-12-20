type TConfidence = 'low' | 'medium' | 'high';
export type TProto = 'tcp' | 'udp' | 'icmp';
type TStatus = 'active' | 'delisted' | 'expired' | 'replaced';
export type TRestriction = 'public' | 'need-to-know' | 'internal';
type TName =
  | 'zeus'
  | 'feodo'
  | 'zeroaccess'
  | 'tdss'
  | 'irc-bot'
  | 'torpig'
  | 'palevo'
  | 'virut'
  | 'kelihos'
  | 'zeus-p2p'
  | 'conficker'
  | 'spyeye'
  | 'citadel';

export type TCategory =
  | 'amplifier'
  | 'backdoor'
  | 'bots'
  | 'cnc'
  | 'deface'
  | 'dns-query'
  | 'dos-attacker'
  | 'dos-victim'
  | 'flow'
  | 'flow-anomaly'
  | 'fraud'
  | 'leak'
  | 'malurl'
  | 'malware-action'
  | 'phish'
  | 'proxy'
  | 'sandbox-url'
  | 'scam'
  | 'scanning'
  | 'server-exploit'
  | 'spam'
  | 'spam-url'
  | 'tor'
  | 'webinject'
  | 'vulnerable'
  | 'other';

type TOrigin =
  | 'c2'
  | 'dropzone'
  | 'proxy'
  | 'p2p-crawler'
  | 'p2p-drone'
  | 'sinkhole'
  | 'sandbox'
  | 'honeypot'
  | 'darknet'
  | 'av'
  | 'ids'
  | 'waf';

export interface IAddress {
  ip: string;
  cc?: string;
  asn?: number;
}

export interface IRequestParams {
  'time.min': Date;
  asn?: string;
  category?: string;
  cc?: string;
  dport?: string;
  fqdn?: string;
  'fqdn.sub'?: string;
  id?: string;
  ip?: string;
  'ip.net'?: string;
  md5?: string;
  name?: string | TName;
  'opt.limit'?: number;
  proto?: string;
  restriction?: string;
  sha1?: string;
  source?: string;
  sport?: string;
  target?: string;
  'time.max'?: Date;
  url?: string;
  'url.sub'?: string;
}

export interface IBlacklist {
  status?: TStatus;
}

export interface IResponse {
  id: string;
  source: string;
  origin?: TOrigin;
  confidence: TConfidence;
  category: TCategory;
  time: string;
  name?: TName;
  md5?: string;
  sha1?: string;
  proto?: TProto;
  restriction?: TRestriction;
  address?: IAddress[];
  sport?: number;
  dport?: number;
  url?: string;
  fqdn?: string;
  target?: string;
  adip?: string;
  dip?: string;
}

// as type because of Table.tsx error: Type 'IResponseTableData' is not assignable to type 'Record<string, unknown>'. Index signature is missing in type 'IResponseTableData'
export type IResponseParsedAddress = {
  ip?: string;
  cc?: string;
  asn?: string;
};

export type IResponseTableData = IResponseParsedAddress & Omit<IResponse, 'time' | 'address'> & { time: string };
