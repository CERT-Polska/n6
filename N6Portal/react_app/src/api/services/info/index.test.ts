/**
 * @jest-environment jsdom
 */

import { queryClientTestHookWrapper } from 'utils/createTestHookWrapper';
import { getInfo, getInfoConfig, useInfo, useInfoConfig } from './index';
import { IInfo, IInfoConfig } from './types';
import { renderHook, waitFor } from '@testing-library/react';
import { controllers, customAxios, dataController } from 'api';

describe('getInfo', () => {
  it('calls /info GET method and returns payloads data', async () => {
    const getInfoMockedData: IInfo = {
      authenticated: false
    };
    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.resolve({ data: getInfoMockedData }));
    const payloadData: Promise<IInfo> = getInfo();
    waitFor(() => {
      expect(payloadData).not.toBe(null);
    });
    expect(payloadData).resolves.toStrictEqual(getInfoMockedData);
    expect(customAxios.get).toHaveBeenCalledWith(`${dataController}${controllers.services.info}`);
  });

  it('throws error upon breaking a try-catch clause', async () => {
    const err = new Error('test error message');
    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.reject(err));
    const payloadData: Promise<IInfo> = getInfo();
    waitFor(() => {
      expect(payloadData).not.toBe(null);
    });
    expect(payloadData).rejects.toStrictEqual(err);
  });
});

describe('useInfo', () => {
  it('returns reactQuery containing backend data regarding org config', async () => {
    const useInfoMockedData: IInfo[] = [];

    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.resolve({ data: useInfoMockedData }));

    const useInfoRenderingResult = renderHook(() => useInfo(), { wrapper: queryClientTestHookWrapper() });
    await waitFor(() => {
      expect(useInfoRenderingResult.result.current.isSuccess).toBe(true);
    });

    expect(customAxios.get).toHaveBeenCalledWith(`${dataController}${controllers.services.info}`);
    expect(useInfoRenderingResult.result.current.isSuccess).toBe(true);
    expect(useInfoRenderingResult.result.current.data).toStrictEqual(useInfoMockedData);
  });
});

describe('getInfoConfig', () => {
  it('calls /info/config GET method and returns payloads data', async () => {
    const getInfoConfigMockedData: IInfoConfig = {
      available_resources: [],
      user_id: '',
      org_id: ''
    };
    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.resolve({ data: getInfoConfigMockedData }));
    const payloadData: Promise<IInfoConfig> = getInfoConfig();
    waitFor(() => {
      expect(payloadData).not.toBe(null);
    });
    expect(payloadData).resolves.toStrictEqual(getInfoConfigMockedData);
    expect(customAxios.get).toHaveBeenCalledWith(`${dataController}${controllers.services.infoConfig}`);
  });

  it('throws error upon breaking a try-catch clause', async () => {
    const err = new Error('test error message');
    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.reject(err));
    const payloadData: Promise<IInfoConfig> = getInfoConfig();
    waitFor(() => {
      expect(payloadData).not.toBe(null);
    });
    expect(payloadData).rejects.toStrictEqual(err);
  });
});

describe('useInfoConfig', () => {
  it('returns reactQuery containing backend data regarding org config', async () => {
    const useInfoConfigMockedData: IInfoConfig[] = [];

    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.resolve({ data: useInfoConfigMockedData }));

    const useInfoConfigRenderingResult = renderHook(() => useInfoConfig(), { wrapper: queryClientTestHookWrapper() });
    await waitFor(() => {
      expect(useInfoConfigRenderingResult.result.current.isSuccess).toBe(true);
    });

    expect(customAxios.get).toHaveBeenCalledWith(`${dataController}${controllers.services.infoConfig}`);
    expect(useInfoConfigRenderingResult.result.current.isSuccess).toBe(true);
    expect(useInfoConfigRenderingResult.result.current.data).toStrictEqual(useInfoConfigMockedData);
  });
});
