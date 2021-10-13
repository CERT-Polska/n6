import { AxiosError } from 'axios';
import { UseQueryOptions, UseQueryResult, useQuery } from 'react-query';
import { controllers, dataController, jsonDataFormat, customAxios } from 'api';
import { IRequestParams, IResponse } from 'api/services/globalTypes';

const getReportThreats = async (params: IRequestParams): Promise<IResponse[]> => {
  try {
    const payload = await customAxios.get(`${dataController}${controllers.services.reportThreats}${jsonDataFormat}`, {
      params
    });
    return payload.data;
  } catch (reason) {
    throw reason;
  }
};

const getReportInside = async (params: IRequestParams): Promise<IResponse[]> => {
  try {
    const payload = await customAxios.get(`${dataController}${controllers.services.reportInside}${jsonDataFormat}`, {
      params
    });
    return payload.data;
  } catch (reason) {
    throw reason;
  }
};

export const useReportThreats = (
  params: IRequestParams,
  options?: UseQueryOptions<IResponse[], AxiosError>
): UseQueryResult<IResponse[], AxiosError> => {
  return useQuery(['reportThreats', params], (): Promise<IResponse[]> => getReportThreats(params), options);
};

export const useReportInside = (
  params: IRequestParams,
  options?: UseQueryOptions<IResponse[], AxiosError>
): UseQueryResult<IResponse[], AxiosError> => {
  return useQuery(['reportInside', params], (): Promise<IResponse[]> => getReportInside(params), options);
};
