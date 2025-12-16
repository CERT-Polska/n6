import { QueryClientProviderTestWrapper } from 'utils/testWrappers';
import { getInfo, getInfoConfig, getInfoOIDC, useInfo, useInfoConfig, useInfoOIDC } from './index';
import { IInfo, IInfoConfig, IInfoOIDC } from './types';
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

    const useInfoRenderingResult = renderHook(() => useInfo(), { wrapper: QueryClientProviderTestWrapper });
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

    const useInfoConfigRenderingResult = renderHook(() => useInfoConfig(), { wrapper: QueryClientProviderTestWrapper });
    await waitFor(() => {
      expect(useInfoConfigRenderingResult.result.current.isSuccess).toBe(true);
    });

    expect(customAxios.get).toHaveBeenCalledWith(`${dataController}${controllers.services.infoConfig}`);
    expect(useInfoConfigRenderingResult.result.current.isSuccess).toBe(true);
    expect(useInfoConfigRenderingResult.result.current.data).toStrictEqual(useInfoConfigMockedData);
  });
});

describe('getInfoOIDC', () => {
  it('calls /info/oidc GET method and returns payloads data', async () => {
    const getInfoOIDCMockedData: IInfoOIDC = {
      enabled: false,
      auth_url: 'test_auth_url',
      state: 'test_state',
      logout_uri: 'http://localhost:1234/logout',
      logout_redirect_uri: 'https://localhost'
    };
    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.resolve({ data: getInfoOIDCMockedData }));
    const payloadData: Promise<IInfoOIDC> = getInfoOIDC();
    waitFor(() => {
      expect(payloadData).not.toBe(null);
    });
    expect(payloadData).resolves.toStrictEqual(getInfoOIDCMockedData);
    expect(customAxios.get).toHaveBeenCalledWith(`${dataController}${controllers.services.infoOIDC}`);
  });

  it('throws error upon breaking a try-catch clause', async () => {
    const err = new Error('test error message');
    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.reject(err));
    const payloadData: Promise<IInfoOIDC> = getInfoOIDC();
    waitFor(() => {
      expect(payloadData).not.toBe(null);
    });
    expect(payloadData).rejects.toStrictEqual(err);
  });
});

describe('useInfoOIDC', () => {
  it('returns reactQuery containing backend data regarding org OIDC', async () => {
    const useInfoOIDCMockedData: IInfoOIDC[] = [];

    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.resolve({ data: useInfoOIDCMockedData }));

    const useInfoOIDCRenderingResult = renderHook(() => useInfoOIDC(), { wrapper: QueryClientProviderTestWrapper });
    await waitFor(() => {
      expect(useInfoOIDCRenderingResult.result.current.isSuccess).toBe(true);
    });

    expect(customAxios.get).toHaveBeenCalledWith(`${dataController}${controllers.services.infoOIDC}`);
    expect(useInfoOIDCRenderingResult.result.current.isSuccess).toBe(true);
    expect(useInfoOIDCRenderingResult.result.current.data).toStrictEqual(useInfoOIDCMockedData);
  });
});
