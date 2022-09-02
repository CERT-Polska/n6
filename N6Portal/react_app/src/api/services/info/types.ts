export type TAvailableResources = '/report/threats' | '/search/events' | '/report/inside';

export interface IInfo {
  authenticated: boolean;
  available_resources?: TAvailableResources[];
  org_id?: string;
  org_actual_name?: string;
  full_access?: boolean;
  api_key_auth_enabled?: boolean;
  knowledge_base_enabled?: boolean;
}

interface IIpMinMaxSeq {
  max_ip: string;
  min_ip: string;
}

export interface IInfoConfig {
  available_resources: TAvailableResources[];
  user_id: string;
  org_id: string;
  org_actual_name?: string;
  email_notifications?: {
    email_notification_times?: string[];
    email_notification_addresses?: string[];
    email_notification_language?: string;
    email_notification_business_days_only?: boolean;
  };
  inside_criteria?: {
    cc_seq?: string[];
    fqdn_seq?: string[];
    url_seq?: string[];
    asn_seq?: number[];
    ip_min_max_seq?: IIpMinMaxSeq[];
  };
}
