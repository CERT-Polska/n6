import { QueryClientProviderTestWrapper } from 'utils/testWrappers';
import { getOrgConfig, postOrgConfig, useOrgConfig } from './index';
import { IOrgConfig } from './types';
import { renderHook, waitFor } from '@testing-library/react';
import { controllers, customAxios, dataController } from 'api';

describe('getOrgConfig', () => {
  it('calls /org_config GET method and returns payloads data', async () => {
    const getOrgConfigMockedData: IOrgConfig = {
      org_id: 'test_org_id',
      actual_name: 'Test Org Id',
      asns: [],
      fqdns: [],
      ip_networks: [],
      notification_enabled: false,
      notification_language: 'en',
      notification_emails: [],
      notification_times: [],
      post_accepted: null,
      update_info: null,
      org_user_logins: []
    };
    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.resolve({ data: getOrgConfigMockedData }));
    const payloadData: Promise<IOrgConfig> = getOrgConfig();
    waitFor(() => {
      expect(payloadData).not.toBe(null);
    });
    expect(payloadData).resolves.toStrictEqual(getOrgConfigMockedData);
    expect(customAxios.get).toHaveBeenCalledWith(`${dataController}${controllers.orgConfig.orgConfigEndpoint}`);
  });

  it('throws error upon breaking a try-catch clause', async () => {
    const err = new Error('test error message');
    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.reject(err));
    const payloadData: Promise<IOrgConfig> = getOrgConfig();
    waitFor(() => {
      expect(payloadData).not.toBe(null);
    });
    expect(payloadData).rejects.toStrictEqual(err);
  });
});

describe('useOrgConfig', () => {
  it('returns reactQuery containing backend data regarding org config', async () => {
    const useOrgConfigMockedData: IOrgConfig[] = [
      {
        org_id: 'test org id',
        actual_name: 'Test Org Id',
        asns: [],
        fqdns: [],
        ip_networks: [],
        notification_enabled: false,
        notification_language: 'en',
        notification_emails: [],
        notification_times: [],
        post_accepted: null,
        update_info: null,
        org_user_logins: []
      }
    ];

    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.resolve({ data: useOrgConfigMockedData }));

    const useOrgConfigRenderingResult = renderHook(() => useOrgConfig(), { wrapper: QueryClientProviderTestWrapper });
    await waitFor(() => {
      expect(useOrgConfigRenderingResult.result.current.isSuccess).toBe(true);
    });

    expect(customAxios.get).toHaveBeenCalledWith(`${dataController}${controllers.orgConfig.orgConfigEndpoint}`);
    expect(useOrgConfigRenderingResult.result.current.isSuccess).toBe(true);
    expect(useOrgConfigRenderingResult.result.current.data).toStrictEqual(useOrgConfigMockedData);
  });
});

describe('postOrgConfig', () => {
  it('calls /org_config POST method and returns payloads data', async () => {
    const postOrgConfigMockedData: IOrgConfig = {
      org_id: 'test_org_id',
      actual_name: 'Test Org Id',
      asns: [],
      fqdns: [],
      ip_networks: [],
      notification_enabled: false,
      notification_language: 'en',
      notification_emails: [],
      notification_times: [],
      post_accepted: null,
      update_info: null,
      org_user_logins: []
    };

    jest.spyOn(customAxios, 'post').mockImplementation(() => Promise.resolve({ data: postOrgConfigMockedData }));
    const payloadData: Promise<IOrgConfig> = postOrgConfig({} as FormData);
    waitFor(() => {
      expect(payloadData).toBe(postOrgConfigMockedData);
    });
    expect(payloadData).resolves.toStrictEqual(postOrgConfigMockedData);
    expect(customAxios.post).toHaveBeenCalledWith(`${dataController}${controllers.orgConfig.orgConfigEndpoint}`, {});
  });

  it('throws error upon breaking a try-catch clause', async () => {
    const err = new Error('test error message');
    jest.spyOn(customAxios, 'post').mockImplementation(() => Promise.reject(err));
    const payloadData: Promise<IOrgConfig> = postOrgConfig({} as FormData);
    waitFor(() => {
      expect(payloadData).not.toBe(null);
    });
    expect(payloadData).rejects.toStrictEqual(err);
  });
});
