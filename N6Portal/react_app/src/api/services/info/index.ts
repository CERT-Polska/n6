import { AxiosError } from 'axios';
import { useQuery, UseQueryOptions, UseQueryResult } from 'react-query';
import { controllers, customAxios, dataController } from 'api';
import { IInfo, IInfoConfig } from 'api/services/info/types';

const getInfo = async (): Promise<IInfo> => {
  try {
    const payload = await customAxios.get<IInfo>(`${dataController}${controllers.services.info}`);
    return payload.data;
  } catch (reason) {
    throw reason;
  }
};

const getInfoConfig = async (): Promise<IInfoConfig> => {
  try {
    const payload = await customAxios.get<IInfoConfig>(`${dataController}${controllers.services.infoConfig}`);
    return payload.data;
  } catch (reason) {
    throw reason;
  }
};

export const useInfo = (
  options?: Omit<UseQueryOptions<IInfo, AxiosError>, 'queryKey' | 'queryFn'>
): UseQueryResult<IInfo, AxiosError> => {
  return useQuery('info', (): Promise<IInfo> => getInfo(), options);
};

export const useInfoConfig = (
  options?: Omit<UseQueryOptions<IInfoConfig, AxiosError>, 'queryKey' | 'queryFn'>
): UseQueryResult<IInfoConfig, AxiosError> => {
  return useQuery('infoConfig', (): Promise<IInfoConfig> => getInfoConfig(), options);
};
