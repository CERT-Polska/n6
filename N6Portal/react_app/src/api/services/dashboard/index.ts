import { AxiosError } from 'axios';
import { useQuery, UseQueryOptions, UseQueryResult } from 'react-query';
import { controllers, dataController, customAxios } from 'api';
import { IDashboardResponse } from 'api/services/dashboard/types';

const getDashboard = async (): Promise<IDashboardResponse> => {
  try {
    const payload = await customAxios.get(`${dataController}${controllers.services.dashboard}`);
    return payload.data;
  } catch (reason) {
    throw reason;
  }
};

export const useDashboard = (
  options?: Omit<UseQueryOptions<IDashboardResponse, AxiosError>, 'queryKey' | 'queryFn'>
): UseQueryResult<IDashboardResponse, AxiosError> => {
  return useQuery('dashboard', (): Promise<IDashboardResponse> => getDashboard(), options);
};
