import { UseQueryOptions, UseQueryResult, useQuery } from 'react-query';
import { AxiosError } from 'axios';
import { controllers, customAxios, dataController } from 'api';

export interface IAgreement {
  label: string;
  pl: string;
  en: string;
  url_pl?: string | undefined;
  url_en?: string | undefined;
  default_consent: boolean;
}

export const getAgreements = async (): Promise<IAgreement[]> => {
  try {
    const payload = await customAxios.get<IAgreement[]>(`${dataController}${controllers.services.agreements}`);
    return payload.data;
  } catch (reason) {
    throw reason;
  }
};

export const useAgreements = (
  options?: Omit<UseQueryOptions<IAgreement[], AxiosError>, 'queryKey' | 'queryFn'>
): UseQueryResult<IAgreement[], AxiosError> => {
  return useQuery('agreements', (): Promise<IAgreement[]> => getAgreements(), options);
};

export const postOrgAgreements = async (agreements: string[]): Promise<string[]> => {
  try {
    const formData = new FormData();
    formData.append('agreements', agreements.join(','));
    const payload = await customAxios.post(`${dataController}${controllers.orgConfig.orgAgreementsEndpoint}`, formData);
    return payload.data;
  } catch (reason) {
    throw reason;
  }
};

export const getOrgAgreements = async (): Promise<string[]> => {
  try {
    const payload = await customAxios.get<string[]>(`${dataController}${controllers.orgConfig.orgAgreementsEndpoint}`);
    return payload.data;
  } catch (reason) {
    throw reason;
  }
};

export const useOrgAgreements = (
  options?: Omit<UseQueryOptions<string[], AxiosError>, 'queryKey' | 'queryFn'>
): UseQueryResult<string[], AxiosError> => {
  return useQuery('orgAgreements', (): Promise<string[]> => getOrgAgreements(), options);
};
