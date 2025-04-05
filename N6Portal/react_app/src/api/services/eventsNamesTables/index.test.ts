import { QueryClientProviderTestWrapper } from 'utils/testWrappers';
import { getEventsNamesTables, useEventsNamesTables, TEventsNamesTables } from './index';
import { renderHook, waitFor } from '@testing-library/react';
import { controllers, customAxios, dataController } from 'api';

describe('getEventsNamesTables', () => {
  it('calls /names_ranking GET method and returns payloads data', async () => {
    const getEventsNamesTablesMockedData: TEventsNamesTables = {};
    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.resolve({ data: getEventsNamesTablesMockedData }));
    const payloadData: Promise<TEventsNamesTables> = getEventsNamesTables();
    waitFor(() => {
      expect(payloadData).not.toBe(null);
    });
    expect(payloadData).resolves.toStrictEqual(getEventsNamesTablesMockedData);
    expect(customAxios.get).toHaveBeenCalledWith(`${dataController}${controllers.services.eventsNamesTables}`);
  });

  it('throws error upon breaking a try-catch clause', async () => {
    const err = new Error('test error message');
    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.reject(err));
    const payloadData: Promise<TEventsNamesTables> = getEventsNamesTables();
    waitFor(() => {
      expect(payloadData).not.toBe(null);
    });
    expect(payloadData).rejects.toStrictEqual(err);
  });
});

describe('useEventsNamesTables', () => {
  it('returns reactQuery containing backend data regarding names ranking', async () => {
    const useEventsNamesTablesMockedData: TEventsNamesTables[] = [];

    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.resolve({ data: useEventsNamesTablesMockedData }));

    const useEventsNamesTablesRenderingResult = renderHook(() => useEventsNamesTables(), {
      wrapper: QueryClientProviderTestWrapper
    });
    await waitFor(() => {
      expect(useEventsNamesTablesRenderingResult.result.current.isSuccess).toBe(true);
    });

    expect(customAxios.get).toHaveBeenCalledWith(`${dataController}${controllers.services.eventsNamesTables}`);
    expect(useEventsNamesTablesRenderingResult.result.current.isSuccess).toBe(true);
    expect(useEventsNamesTablesRenderingResult.result.current.data).toStrictEqual(useEventsNamesTablesMockedData);
  });
});
