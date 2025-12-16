import { AxiosError } from 'axios';
import { useQuery, UseQueryOptions, UseQueryResult } from 'react-query';
import qs from 'qs';
import { dataController, controllers, customAxios } from 'api';
import {
  IApiKey,
  ICallbackKeycloak,
  IForgottenPasswordData,
  ILogin,
  ILoginKeycloak,
  IMfaConfig,
  IOIDCParams
} from 'api/auth/types';

export const getLogout = async (): Promise<void> => {
  try {
    await customAxios.get(`${dataController}${controllers.auth.logout}`);
  } catch (reason) {
    throw reason;
  }
};

export const getMfaConfig = async (): Promise<IMfaConfig | null> => {
  try {
    const payload = await customAxios.get<IMfaConfig>(`${dataController}${controllers.auth.mfaConfig}`);
    return payload.data;
  } catch (reason: any) {
    if (reason.response?.status === 403) {
      // do not respond with 403 response to avoid resetting the auth
      // state and falling into the infinite loop
      return null;
    }
    throw reason;
  }
};

export const useMfaConfig = (
  options?: Omit<UseQueryOptions<IMfaConfig | null, AxiosError>, 'queryKey' | 'queryFn'>
): UseQueryResult<IMfaConfig | null, AxiosError> => {
  return useQuery('mfaConfig', (): Promise<IMfaConfig | null> => getMfaConfig(), options);
};

export const getApiKey = async (): Promise<IApiKey> => {
  try {
    const payload = await customAxios.get<IApiKey>(`${dataController}${controllers.auth.apiKey}`);
    return payload.data;
  } catch (reason) {
    throw reason;
  }
};

export const useApiKey = (
  options?: Omit<UseQueryOptions<IApiKey, AxiosError>, 'queryKey' | 'queryFn'>
): UseQueryResult<IApiKey, AxiosError> => {
  return useQuery('apiKey', (): Promise<IApiKey> => getApiKey(), options);
};

export const postApiKey = async (): Promise<IApiKey> => {
  try {
    const payload = await customAxios.post<IApiKey>(`${dataController}${controllers.auth.apiKey}`);
    return payload.data;
  } catch (reason) {
    throw reason;
  }
};

export const deleteApiKey = async (): Promise<Record<string, never>> => {
  try {
    const payload = await customAxios.delete<Record<string, never>>(`${dataController}${controllers.auth.apiKey}`);
    return payload.data;
  } catch (reason) {
    throw reason;
  }
};

export const postOIDCInfo = async (): Promise<IOIDCParams> => {
  try {
    const payload = await customAxios.post(`${dataController}${controllers.auth.infoOIDC}`);
    return payload.data;
  } catch (reason) {
    throw reason;
  }
};

export const postLogin = async (data: Record<string, string>): Promise<ILogin> => {
  try {
    const encodedData = qs.stringify(data);
    const payload = await customAxios.post(`${dataController}${controllers.auth.login}`, encodedData);
    return payload.data;
  } catch (reason) {
    throw reason;
  }
};

export const postOIDCCallback = async (data: Record<string, string>): Promise<ICallbackKeycloak> => {
  try {
    const encodedData = qs.stringify(data);
    const payload = await customAxios.post(`${dataController}${controllers.auth.oidcCallback}`, encodedData);
    return payload.data;
  } catch (reason) {
    throw reason;
  }
};

export const postLoginKeycloak = async (): Promise<ILoginKeycloak> => {
  try {
    const payload = await customAxios.post(`${dataController}${controllers.auth.loginKeycloak}`);
    return payload.data;
  } catch (reason) {
    throw reason;
  }
};

export const postOIDCRefreshToken = async (data: Record<string, string>): Promise<ICallbackKeycloak> => {
  try {
    const encodedData = qs.stringify(data);
    const payload = await customAxios.post(`${dataController}${controllers.auth.oidcRefreshToken}`, encodedData);
    return payload.data;
  } catch (reason) {
    throw reason;
  }
};

export const postMfaConfig = async (): Promise<ILogin> => {
  try {
    const payload = await customAxios.post(`${dataController}${controllers.auth.mfaConfig}`);
    return payload.data;
  } catch (reason) {
    throw reason;
  }
};

export const postMfaConfigConfirm = async (data: Record<string, string>): Promise<void> => {
  try {
    const encodedData = qs.stringify(data);
    await customAxios.post(`${dataController}${controllers.auth.mfaConfigConfirm}`, encodedData);
  } catch (reason) {
    throw reason;
  }
};

export const postEditMfaConfigConfirm = async (data: Record<string, string>): Promise<void> => {
  try {
    const encodedData = qs.stringify(data);
    await customAxios.post(`${dataController}${controllers.auth.editMfaConfigConfirm}`, encodedData);
  } catch (reason) {
    throw reason;
  }
};

export const postMfaLogin = async (data: Record<string, string>): Promise<void> => {
  try {
    const encodedData = qs.stringify(data);
    await customAxios.post(`${dataController}${controllers.auth.mfaLogin}`, encodedData);
  } catch (reason) {
    throw reason;
  }
};

export const postForgottenPassword = async (data: IForgottenPasswordData): Promise<void> => {
  try {
    const encodedData = qs.stringify(data);
    await customAxios.post(`${dataController}${controllers.auth.forgottenPassword}`, encodedData);
  } catch (reason) {
    throw reason;
  }
};

export const postResetPassword = async (data: Record<string, string>): Promise<void> => {
  try {
    const encodedData = qs.stringify(data);
    await customAxios.post(`${dataController}${controllers.auth.resetPassword}`, encodedData);
  } catch (reason) {
    throw reason;
  }
};
