import { AxiosError } from 'axios';
import { useQuery, UseQueryOptions, UseQueryResult } from 'react-query';
import { controllers, dataController, customAxios } from 'api';
import { TBarChart } from 'api/services/barChart/types';

export const getBarChart = async (): Promise<TBarChart> => {
  try {
    const payload = await customAxios.get(`${dataController}${controllers.services.barChart}`);
    return payload.data;
  } catch (reason) {
    throw reason;
  }
};

export const useBarChart = (
  options?: Omit<UseQueryOptions<TBarChart, AxiosError>, 'queryKey' | 'queryFn'>
): UseQueryResult<TBarChart, AxiosError> => {
  return useQuery('barChart', (): Promise<TBarChart> => getBarChart(), options);
};
