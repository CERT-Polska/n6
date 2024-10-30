/**
 * @jest-environment jsdom
 */

import { getSearch, IFilterResponse } from './index';
import { waitFor } from '@testing-library/react';
import { customAxios, dataController, jsonDataFormat } from 'api';
import { TAvailableResources } from '../info/types';
import { IRequestParams } from '../globalTypes';

describe('getSearch', () => {
  it('calls /search/events GET method with filtering params and returns payloads data', async () => {
    const getSearchMockedData: IFilterResponse = {
      target: '/report/threats',
      data: []
    };
    const params: IRequestParams = {
      'time.min': new Date()
    };
    const controller: TAvailableResources = '/search/events';
    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.resolve({ data: getSearchMockedData }));
    const payloadData: Promise<IFilterResponse> = getSearch(params, controller);
    waitFor(() => expect(payloadData).not.toBe(null));
    expect(payloadData).resolves.toStrictEqual({ data: getSearchMockedData, target: controller });
    expect(customAxios.get).toHaveBeenCalledWith(`${dataController}${controller}${jsonDataFormat}`, { params: params });
  });

  it('throws error upon breaking a try-catch clause', async () => {
    const params: IRequestParams = {
      'time.min': new Date()
    };
    const controller: TAvailableResources = '/search/events';
    const err = new Error('test error message');
    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.reject(err));
    const payloadData: Promise<IFilterResponse> = getSearch(params, controller);
    waitFor(() => {
      expect(payloadData).not.toBe(null);
    });
    expect(payloadData).rejects.toStrictEqual(err);
  });
});
