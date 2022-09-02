import { AxiosError } from 'axios';
import { useQuery, UseQueryOptions, UseQueryResult } from 'react-query';
import qs from 'qs';
import { dataController, controllers, customAxios } from 'api';
import { IApiKey, IForgottenPasswordData, ILogin, IMfaConfig } from 'api/auth/types';

export const getLogout = async (): Promise<void> => {
  try {
    await customAxios.get(`${dataController}${controllers.auth.logout}`);
  } catch (reason) {
    throw reason;
  }
};

const getMfaConfig = async (): Promise<IMfaConfig> => {
  try {
    const payload = await customAxios.get<IMfaConfig>(`${dataController}${controllers.auth.mfaConfig}`);
    return payload.data;
  } catch (reason) {
    throw reason;
  }
};

export const useMfaConfig = (
  options?: Omit<UseQueryOptions<IMfaConfig, AxiosError>, 'queryKey' | 'queryFn'>
): UseQueryResult<IMfaConfig, AxiosError> => {
  return useQuery('mfaConfig', (): Promise<IMfaConfig> => getMfaConfig(), options);
};

const getApiKey = async (): Promise<IApiKey> => {
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

export const postLogin = async (data: Record<string, string>): Promise<ILogin> => {
  try {
    const encodedData = qs.stringify(data);
    const payload = await customAxios.post(`${dataController}${controllers.auth.login}`, encodedData);
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
