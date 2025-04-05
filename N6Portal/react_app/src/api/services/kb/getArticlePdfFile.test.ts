import { controllers, customAxios, dataController } from 'api';
import { getArticlePdfFile } from './getArticlePdfFile';
import { waitFor } from '@testing-library/react';

describe('getArticlePdfFile', () => {
  it('calls /knowledge_base/articles/{id} GET method and returns payloads data', async () => {
    const getArticlePdfFileMockedData = new Blob();
    const articleId = '1';
    const lang = 'en';
    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.resolve({ data: getArticlePdfFileMockedData }));
    const payloadData: Promise<Blob> = getArticlePdfFile(articleId, lang);
    waitFor(() => {
      expect(payloadData).not.toBe(null);
    });
    expect(payloadData).resolves.toStrictEqual(getArticlePdfFileMockedData);
    expect(customAxios.get).toHaveBeenCalledWith(
      `${dataController}${controllers.services.articles}/${articleId}/${lang}/pdf`,
      { responseType: 'blob' }
    );
  });

  it('throws error upon breaking a try-catch clause', async () => {
    const err = new Error('test error message');
    const articleId = '1';
    const lang = 'en';
    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.reject(err));
    const payloadData: Promise<Blob> = getArticlePdfFile(articleId, lang);
    waitFor(() => {
      expect(payloadData).not.toBe(null);
    });
    expect(payloadData).rejects.toStrictEqual(err);
  });
});
