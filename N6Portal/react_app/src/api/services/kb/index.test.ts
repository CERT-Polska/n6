/**
 * @jest-environment jsdom
 */

import { queryClientTestHookWrapper } from 'utils/createTestHookWrapper';
import { getArticle, getArticles, useArticle, useArticles } from './index';
import { IArticle, IArticlesList } from './types';
import { renderHook, waitFor } from '@testing-library/react';
import { controllers, customAxios, dataController } from 'api';

describe('getArticle', () => {
  it('calls /knowledge_base/articles/{id} GET method and returns payloads data', async () => {
    const getArticleMockedData: IArticle = {
      id: 0,
      chapter_id: 0,
      content: {
        pl: '',
        en: ''
      }
    };
    const articleId = '1';
    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.resolve({ data: getArticleMockedData }));
    const payloadData: Promise<IArticle> = getArticle(articleId);
    waitFor(() => {
      expect(payloadData).not.toBe(null);
    });
    expect(payloadData).resolves.toStrictEqual(getArticleMockedData);
    expect(customAxios.get).toHaveBeenCalledWith(`${dataController}${controllers.services.articles}/${articleId}`);
  });

  it('throws error upon breaking a try-catch clause', async () => {
    const err = new Error('test error message');
    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.reject(err));
    const payloadData: Promise<IArticle> = getArticle('');
    waitFor(() => {
      expect(payloadData).not.toBe(null);
    });
    expect(payloadData).rejects.toStrictEqual(err);
  });
});

describe('useArticle', () => {
  it('returns reactQuery containing backend data regarding particular article', async () => {
    const useArticleMockedData: IArticle[] = [];
    const articleId = '1';

    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.resolve({ data: useArticleMockedData }));

    const useArticleRenderingResult = renderHook(() => useArticle(articleId), {
      wrapper: queryClientTestHookWrapper()
    });
    await waitFor(() => {
      expect(useArticleRenderingResult.result.current.isSuccess).toBe(true);
    });

    expect(customAxios.get).toHaveBeenCalledWith(`${dataController}${controllers.services.articles}/${articleId}`);
    expect(useArticleRenderingResult.result.current.isSuccess).toBe(true);
    expect(useArticleRenderingResult.result.current.data).toStrictEqual(useArticleMockedData);
  });
});

describe('getArticles', () => {
  it('calls /knowledge_base/contents GET method and returns payloads data', async () => {
    const getArticlesMockedData: IArticle = {
      id: 0,
      chapter_id: 0,
      content: {
        pl: '',
        en: ''
      }
    };
    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.resolve({ data: getArticlesMockedData }));
    const payloadData: Promise<IArticlesList> = getArticles();
    waitFor(() => {
      expect(payloadData).not.toBe(null);
    });
    expect(payloadData).resolves.toStrictEqual(getArticlesMockedData);
    expect(customAxios.get).toHaveBeenCalledWith(`${dataController}${controllers.services.articlesList}`);
  });

  it('throws error upon breaking a try-catch clause', async () => {
    const err = new Error('test error message');
    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.reject(err));
    const payloadData: Promise<IArticlesList> = getArticles();
    waitFor(() => {
      expect(payloadData).not.toBe(null);
    });
    expect(payloadData).rejects.toStrictEqual(err);
  });
});

describe('useArticles', () => {
  it('returns reactQuery containing backend data regarding article list', async () => {
    const useArticlesMockedData: IArticle[] = [];

    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.resolve({ data: useArticlesMockedData }));

    const useArticlesRenderingResult = renderHook(() => useArticles(), { wrapper: queryClientTestHookWrapper() });
    await waitFor(() => {
      expect(useArticlesRenderingResult.result.current.isSuccess).toBe(true);
    });

    expect(customAxios.get).toHaveBeenCalledWith(`${dataController}${controllers.services.articlesList}`);
    expect(useArticlesRenderingResult.result.current.isSuccess).toBe(true);
    expect(useArticlesRenderingResult.result.current.data).toStrictEqual(useArticlesMockedData);
  });
});
