import { getReportInside, getReportThreats, useReportInside, useReportThreats } from '.';
import { renderHook, waitFor } from '@testing-library/react';
import { IRequestParams, IResponse } from '../globalTypes';
import { QueryClientProviderTestWrapper } from 'utils/testWrappers';
import { controllers, customAxios, dataController, jsonDataFormat } from 'api';

describe('getReportThreats', () => {
  it('calls /report/threats GET endpoint and returns payloads data', async () => {
    const mockedResponseData: IResponse[] = [
      {
        id: '',
        source: '',
        confidence: 'low',
        category: 'proxy',
        time: JSON.stringify(new Date())
      }
    ];
    const params: IRequestParams = {
      'time.min': new Date()
    };
    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.resolve({ data: mockedResponseData }));
    const payloadData: Promise<IResponse[]> = getReportThreats(params);
    waitFor(() => expect(payloadData).toBe(mockedResponseData));
    expect(customAxios.get).toHaveBeenCalledWith(
      `${dataController}${controllers.services.reportThreats}${jsonDataFormat}`,
      { params: params }
    );
  });

  it('throws error on try-catch clause break', async () => {
    const err = new Error('test error message');
    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.reject(err));
    return expect(getReportThreats({} as IRequestParams)).rejects.toStrictEqual(err);
  });
});

describe('useReportThreats', () => {
  it('returns reactQuery containing backend data regarding threats report', async () => {
    const params: IRequestParams = {
      'time.min': new Date()
    };
    const mockedResponseData: IResponse[] = [
      {
        id: 'test_id',
        source: 'test_source',
        confidence: 'low',
        category: 'bots',
        time: JSON.stringify(new Date())
      }
    ];

    const customAxiosGetSpy = jest
      .spyOn(customAxios, 'get')
      .mockReturnValue(Promise.resolve({ data: mockedResponseData }));

    const useReportThreatsRenderingResult = renderHook(() => useReportThreats(params), {
      wrapper: QueryClientProviderTestWrapper
    });
    await waitFor(() => {
      expect(useReportThreatsRenderingResult.result.current.isSuccess).toBe(true);
    });

    expect(customAxiosGetSpy).toHaveBeenCalledWith(
      `${dataController}${controllers.services.reportThreats}${jsonDataFormat}`,
      { params: params }
    );
    expect(useReportThreatsRenderingResult.result.current.isSuccess).toBe(true);
    expect(useReportThreatsRenderingResult.result.current.data).toStrictEqual(mockedResponseData);
  });
});

describe('getReportInside', () => {
  it('calls /report/threats GET endpoint and returns payloads data', async () => {
    const mockedResponseData: IResponse[] = [
      {
        id: '',
        source: '',
        confidence: 'low',
        category: 'proxy',
        time: JSON.stringify(new Date())
      }
    ];
    const params: IRequestParams = {
      'time.min': new Date()
    };
    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.resolve({ data: mockedResponseData }));
    const payloadData: Promise<IResponse[]> = getReportInside(params);
    waitFor(() => expect(payloadData).toBe(mockedResponseData));
    expect(customAxios.get).toHaveBeenCalledWith(
      `${dataController}${controllers.services.reportInside}${jsonDataFormat}`,
      { params: params }
    );
  });

  it('throws error on try-catch clause break', async () => {
    const err = new Error('test error message');
    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.reject(err));
    return expect(getReportInside({} as IRequestParams)).rejects.toStrictEqual(err);
  });
});

describe('useReportInside', () => {
  it('returns reactQuery containing backend data regarding threats report', async () => {
    const params: IRequestParams = {
      'time.min': new Date()
    };
    const mockedResponseData: IResponse[] = [
      {
        id: 'test_id',
        source: 'test_source',
        confidence: 'low',
        category: 'bots',
        time: JSON.stringify(new Date())
      }
    ];

    const customAxiosGetSpy = jest
      .spyOn(customAxios, 'get')
      .mockReturnValue(Promise.resolve({ data: mockedResponseData }));

    const useReportInsideRenderingResult = renderHook(() => useReportInside(params), {
      wrapper: QueryClientProviderTestWrapper
    });
    await waitFor(() => {
      expect(useReportInsideRenderingResult.result.current.isSuccess).toBe(true);
    });

    expect(customAxiosGetSpy).toHaveBeenCalledWith(
      `${dataController}${controllers.services.reportInside}${jsonDataFormat}`,
      { params: params }
    );
    expect(useReportInsideRenderingResult.result.current.isSuccess).toBe(true);
    expect(useReportInsideRenderingResult.result.current.data).toStrictEqual(mockedResponseData);
  });
});
// is further testing even needed, when this hook (and useReportInside) isn't explicitly used?
