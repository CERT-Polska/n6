export interface IMfaConfig {
  mfa_config?: {
    secret_key: string;
    secret_key_qr_code_url: string;
  };
}

export interface ILogin extends IMfaConfig {
  token: string;
}

export interface IForgottenPasswordData {
  login: string;
}

export interface IApiKey {
  api_key: string | null;
}
