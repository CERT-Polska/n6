export interface IUpdateInfo {
  update_request_time: string;
  requesting_user: string | null;
  additional_comment?: string;
  actual_name?: string | null;
  asns?: number[];
  fqdns?: string[];
  ip_networks?: string[];
  notification_enabled?: boolean;
  notification_language?: string | null;
  notification_times?: string[];
  notification_addresses?: string[]; // equals to the notification_emails from IOrgConfig
}

export interface IOrgConfig {
  org_id: string;
  actual_name: string | null;
  asns: number[];
  fqdns: string[];
  ip_networks: string[];
  notification_enabled: boolean;
  notification_language: string | null;
  notification_emails: string[];
  notification_times: string[];
  post_accepted: null;
  update_info: IUpdateInfo | null;
}
