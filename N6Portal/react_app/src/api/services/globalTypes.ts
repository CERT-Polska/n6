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
  client?: string;
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
  client?: string[];
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
  dip?: string;
}

export interface ICustomResponse {
  action?: string;
  additional_data?: string;
  alternative_fqdns?: string;
  artemis_uuid?: string;
  block?: string;
  botid?: string;
  cert_length?: string;
  channel?: string;
  count_actual?: string;
  dataset?: string;
  description?: string;
  detected_since?: string;
  device_id?: string;
  device_model?: string;
  device_type?: string;
  device_vendor?: string;
  device_version?: string;
  dns_version?: string;
  email?: string;
  enriched?: string;
  expired?: string;
  facebook_id?: string;
  filename?: string;
  first_seen?: string;
  gca_specific?: string;
  handshake?: string;
  header?: string;
  iban?: string;
  injects?: string;
  intelmq?: string;
  internal_ip?: string;
  ip_network?: string;
  ipmi_version?: string;
  mac_address?: string;
  method?: string;
  min_amplification?: string;
  misp_eventdid?: string;
  misp_attr_uuid?: string;
  misp_event_uuid?: string;
  phone?: string;
  product?: string;
  product_code?: string;
  proxy_type?: string;
  referer?: string;
  registrar?: string;
  request?: string;
  revision?: string;
  rt?: string;
  sender?: string;
  snitch_uuid?: string;
  status?: string;
  subject_common_name?: string;
  sysdesc?: string;
  tags?: string;
  url_pattern?: string;
  urls_matched?: string;
  user_agent?: string;
  username?: string;
  vendor?: string;
  version?: string;
  visible_databases?: string;
  x509fp_sha1?: string;
  x509issuer?: string;
  x509subject?: string;
  adip?: string;
}

// as type because of Table.tsx error: Type 'IResponseTableData' is not assignable to type 'Record<string, unknown>'. Index signature is missing in type 'IResponseTableData'
export type IResponseParsedAddress = {
  ip?: string;
  cc?: string;
  asn?: string;
};

export type IResponseTableData = IResponseParsedAddress &
  ICustomResponse &
  Omit<IResponse, 'time' | 'address' | 'client'> & { time: string; client?: string };
