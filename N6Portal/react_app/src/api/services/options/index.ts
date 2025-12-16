import { UseQueryOptions, UseQueryResult, useQuery } from 'react-query';
import { AxiosError } from 'axios';
import { controllers, customAxios, dataController, jsonDataFormat } from 'api';
import { TAvailableResources } from 'api/services/info/types';

export const getAvailableSources = async (resource: TAvailableResources): Promise<string[]> => {
  try {
    const payload = await customAxios.get<string[]>(
      `${dataController}${controllers.sources[resource]}${jsonDataFormat}`
    );
    return payload.data;
  } catch (reason) {
    throw reason;
  }
};

export const useAvailableSources = (
  resource: TAvailableResources,
  options?: Omit<UseQueryOptions<string[], AxiosError>, 'queryKey' | 'queryFn'>
): UseQueryResult<string[], AxiosError> => {
  return useQuery(`availableSources-${resource}`, (): Promise<string[]> => getAvailableSources(resource), options);
};
