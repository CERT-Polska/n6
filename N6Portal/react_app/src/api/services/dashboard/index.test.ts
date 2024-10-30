/**
 * @jest-environment jsdom
 */

import { queryClientTestHookWrapper } from 'utils/createTestHookWrapper';
import { getDashboard, useDashboard } from './index';
import { IDashboardResponse } from './types';
import { renderHook, waitFor } from '@testing-library/react';
import { controllers, customAxios, dataController } from 'api';

describe('getDashboard', () => {
  it('calls /dashboard GET method and returns payloads data', async () => {
    const getDashboardMockedData: IDashboardResponse = {
      at: '',
      time_range_in_days: 0,
      counts: {}
    };
    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.resolve({ data: getDashboardMockedData }));
    const payloadData: Promise<IDashboardResponse> = getDashboard();
    waitFor(() => {
      expect(payloadData).not.toBe(null);
    });
    expect(payloadData).resolves.toStrictEqual(getDashboardMockedData);
    expect(customAxios.get).toHaveBeenCalledWith(`${dataController}${controllers.services.dashboard}`);
  });

  it('throws error upon breaking a try-catch clause', async () => {
    const err = new Error('test error message');
    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.reject(err));
    const payloadData: Promise<IDashboardResponse> = getDashboard();
    waitFor(() => {
      expect(payloadData).not.toBe(null);
    });
    expect(payloadData).rejects.toStrictEqual(err);
  });
});

describe('useDashboard', () => {
  it('returns reactQuery containing backend data regarding dashboard', async () => {
    const useDashboardMockedData: IDashboardResponse[] = [];

    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.resolve({ data: useDashboardMockedData }));

    const useDashboardRenderingResult = renderHook(() => useDashboard(), { wrapper: queryClientTestHookWrapper() });
    await waitFor(() => {
      expect(useDashboardRenderingResult.result.current.isSuccess).toBe(true);
    });

    expect(customAxios.get).toHaveBeenCalledWith(`${dataController}${controllers.services.dashboard}`);
    expect(useDashboardRenderingResult.result.current.isSuccess).toBe(true);
    expect(useDashboardRenderingResult.result.current.data).toStrictEqual(useDashboardMockedData);
  });
});
