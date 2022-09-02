import { AxiosError } from 'axios';
import { useQuery, UseQueryOptions, UseQueryResult } from 'react-query';
import { controllers, dataController, customAxios } from 'api';
import { TCategory } from 'api/services/globalTypes';

export type TEventsNamesTables = Partial<Record<TCategory, Record<number, Record<string, number>> | null>>;

const getEventsNamesTables = async () => {
  try {
    const data = await customAxios.get<TEventsNamesTables>(
      `${dataController}${controllers.services.eventsNamesTables}`
    );
    return data.data;
  } catch (reason) {
    throw reason;
  }
};

export const useEventsNamesTables = (
  options?: Omit<UseQueryOptions<TEventsNamesTables, AxiosError>, 'queryKey' | 'queryFn'>
): UseQueryResult<TEventsNamesTables, AxiosError> => {
  return useQuery('eventsNamesTables', (): Promise<TEventsNamesTables> => getEventsNamesTables(), options);
};
