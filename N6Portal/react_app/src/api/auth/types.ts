export interface IMfaConfig {
  mfa_config?: {
    secret_key: string;
    secret_key_qr_code_url: string;
  };
}

export interface IOIDCParams {
  auth_url: string;
  state: string;
}

export interface ILogin extends IMfaConfig {
  token: string;
}

export interface ICallbackKeycloak {
  access_token: string;
  refresh_token: string;
  id_token: string;
}

export interface ILoginKeycloak {
  status: string | null;
}

export interface IForgottenPasswordData {
  login: string;
}

export interface IApiKey {
  api_key: string | null;
}
