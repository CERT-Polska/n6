/**
 * @jest-environment jsdom
 */

import { renderHook, waitFor } from '@testing-library/react';
import { controllers, customAxios, dataController } from 'api';
import { IAgreement, getAgreements, getOrgAgreements, postOrgAgreements, useAgreements, useOrgAgreements } from '.';
import { queryClientTestHookWrapper } from 'utils/createTestHookWrapper';

describe('getAgreements', () => {
  it('calls /agreements GET endpoint and returns payloads data', () => {
    const mockedGetAgreementsData: IAgreement[] = [
      {
        label: '',
        pl: '',
        en: '',
        default_consent: false
      }
    ];
    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.resolve({ data: mockedGetAgreementsData }));
    const payloadData: Promise<IAgreement[]> = getAgreements();
    waitFor(() => expect(payloadData).not.toBe(null));
    expect(customAxios.get).toHaveBeenCalledWith(`${dataController}${controllers.services.agreements}`);
  });

  it('throws error on try-catch clause break', async () => {
    const err = new Error('test error message');
    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.reject(err));
    return expect(getAgreements()).rejects.toStrictEqual(err);
  });
});

describe('useAgreements', () => {
  it('returns reactQuery containing backend data regarding agreements', async () => {
    const mockedGetAgreementsData: IAgreement[] = [
      {
        label: '',
        pl: '',
        en: '',
        default_consent: false
      }
    ];

    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.resolve({ data: mockedGetAgreementsData }));

    const useAgreementsRenderingResult = renderHook(() => useAgreements(), { wrapper: queryClientTestHookWrapper() });
    await waitFor(() => {
      expect(useAgreementsRenderingResult.result.current.isSuccess).toBe(true);
    });

    expect(customAxios.get).toHaveBeenCalledWith(`${dataController}${controllers.services.agreements}`);
    expect(useAgreementsRenderingResult.result.current.isSuccess).toBe(true);
    expect(useAgreementsRenderingResult.result.current.data).toStrictEqual(mockedGetAgreementsData);
  });
});

describe('getOrgAgreements', () => {
  it('calls /org_agreements GET endpoint and returns payloads data', () => {
    const mockedGetOrgAgreementsData: string[] = ['test_string'];
    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.resolve({ data: mockedGetOrgAgreementsData }));
    const payloadData: Promise<string[]> = getOrgAgreements();
    waitFor(() => expect(payloadData).not.toBe(null));
    expect(customAxios.get).toHaveBeenCalledWith(`${dataController}${controllers.orgConfig.orgAgreementsEndpoint}`);
  });

  it('throws error on try-catch clause break', async () => {
    const err = new Error('test error message');
    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.reject(err));
    return expect(getOrgAgreements()).rejects.toStrictEqual(err);
  });
});

describe('useOrgAgreements', () => {
  it('returns reactQuery containing backend data regarding org_agreements', async () => {
    const mockedGetOrgAgreementsData: string[] = ['test_string'];

    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.resolve({ data: mockedGetOrgAgreementsData }));

    const useOrgAgreementsRenderingResult = renderHook(() => useOrgAgreements(), {
      wrapper: queryClientTestHookWrapper()
    });
    await waitFor(() => {
      expect(useOrgAgreementsRenderingResult.result.current.isSuccess).toBe(true);
    });

    expect(customAxios.get).toHaveBeenCalledWith(`${dataController}${controllers.orgConfig.orgAgreementsEndpoint}`);
    expect(useOrgAgreementsRenderingResult.result.current.isSuccess).toBe(true);
    expect(useOrgAgreementsRenderingResult.result.current.data).toStrictEqual(mockedGetOrgAgreementsData);
  });
});

describe('postOrgAgreements', () => {
  it('calls /org_agreements POST endpoint and returns payloads data', async () => {
    const mockedPostOrgAgreementsPayloadData: string[] = ['test_return_string'];
    const postOrgAgreementsData: string[] = ['test_input_string'];
    jest
      .spyOn(customAxios, 'post')
      .mockImplementation(() => Promise.resolve({ data: mockedPostOrgAgreementsPayloadData }));
    const payloadData: Promise<string[]> = postOrgAgreements(postOrgAgreementsData);
    waitFor(() => expect(payloadData).toBe(mockedPostOrgAgreementsPayloadData));
    const formData = new FormData();
    formData.append('agreements', postOrgAgreementsData.join());
    expect(customAxios.post).toHaveBeenCalledWith(
      `${dataController}${controllers.orgConfig.orgAgreementsEndpoint}`,
      formData
    );
  });

  it('throws error on try-catch clause break', async () => {
    const err = new Error('test error message');
    jest.spyOn(customAxios, 'post').mockImplementation(() => Promise.reject(err));
    return expect(postOrgAgreements([])).rejects.toStrictEqual(err);
  });
});
