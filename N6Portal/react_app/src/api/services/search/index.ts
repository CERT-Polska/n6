import { dataController, jsonDataFormat, customAxios } from 'api';
import { TAvailableResources } from 'api/services/info/types';
import { IRequestParams, IResponse } from 'api/services/globalTypes';

export interface IFilterResponse {
  target: TAvailableResources;
  data: IResponse[];
}

export const getSearch = async (params: IRequestParams, controller: TAvailableResources): Promise<IFilterResponse> => {
  try {
    const payload = await customAxios.get(`${dataController}${controller}${jsonDataFormat}`, {
      params
    });
    return { target: controller, data: payload.data };
  } catch (reason) {
    throw reason;
  }
};
