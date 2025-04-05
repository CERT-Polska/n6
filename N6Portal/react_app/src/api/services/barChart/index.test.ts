import { QueryClientProviderTestWrapper } from 'utils/testWrappers';
import { getBarChart, useBarChart } from './index';
import { TBarChart } from './types';
import { renderHook, waitFor } from '@testing-library/react';
import { controllers, customAxios, dataController } from 'api';

describe('getBarChart', () => {
  it('calls /daily_events_counts GET method and returns payloads data', async () => {
    const getBarChartMockedData: TBarChart = {
      datasets: {
        amplifier: [],
        backdoor: [],
        bots: [],
        cnc: [],
        deface: [],
        'dns-query': [],
        'dos-attacker': [],
        'dos-victim': [],
        flow: [],
        'flow-anomaly': [],
        fraud: [],
        leak: [],
        malurl: [],
        'malware-action': [],
        phish: [],
        proxy: [],
        'sandbox-url': [],
        scam: [],
        scanning: [],
        'server-exploit': [],
        spam: [],
        'spam-url': [],
        tor: [],
        webinject: [],
        vulnerable: [],
        other: []
      },
      days: []
    };
    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.resolve({ data: getBarChartMockedData }));
    const payloadData: Promise<TBarChart> = getBarChart();
    waitFor(() => {
      expect(payloadData).not.toBe(null);
    });
    expect(payloadData).resolves.toStrictEqual(getBarChartMockedData);
    expect(customAxios.get).toHaveBeenCalledWith(`${dataController}${controllers.services.barChart}`);
  });

  it('throws error upon breaking a try-catch clause', async () => {
    const err = new Error('test error message');
    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.reject(err));
    const payloadData: Promise<TBarChart> = getBarChart();
    waitFor(() => {
      expect(payloadData).not.toBe(null);
    });
    expect(payloadData).rejects.toStrictEqual(err);
  });
});

describe('useBarChart', () => {
  it('returns reactQuery containing backend data regarding daily events counts', async () => {
    const useBarChartMockedData: TBarChart[] = [];

    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.resolve({ data: useBarChartMockedData }));

    const useBarChartRenderingResult = renderHook(() => useBarChart(), { wrapper: QueryClientProviderTestWrapper });
    await waitFor(() => {
      expect(useBarChartRenderingResult.result.current.isSuccess).toBe(true);
    });

    expect(customAxios.get).toHaveBeenCalledWith(`${dataController}${controllers.services.barChart}`);
    expect(useBarChartRenderingResult.result.current.isSuccess).toBe(true);
    expect(useBarChartRenderingResult.result.current.data).toStrictEqual(useBarChartMockedData);
  });
});
