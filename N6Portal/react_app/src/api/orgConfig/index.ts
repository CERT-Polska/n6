import { AxiosError } from 'axios';
import { useQuery, UseQueryOptions, UseQueryResult } from 'react-query';
import { controllers, customAxios, dataController } from 'api';
import { IOrgConfig } from 'api/orgConfig/types';

export const getOrgConfig = async (): Promise<IOrgConfig> => {
  try {
    const payload = await customAxios.get<IOrgConfig>(`${dataController}${controllers.orgConfig.orgConfigEndpoint}`);
    return payload.data;
  } catch (reason) {
    throw reason;
  }
};

export const useOrgConfig = (
  options?: Omit<UseQueryOptions<IOrgConfig, AxiosError>, 'queryKey' | 'queryFn'>
): UseQueryResult<IOrgConfig, AxiosError> => {
  return useQuery('orgConfig', (): Promise<IOrgConfig> => getOrgConfig(), options);
};

export const postOrgConfig = async (data: FormData): Promise<IOrgConfig> => {
  try {
    const payload = await customAxios.post(`${dataController}${controllers.orgConfig.orgConfigEndpoint}`, data);
    return payload.data;
  } catch (reason) {
    throw reason;
  }
};
