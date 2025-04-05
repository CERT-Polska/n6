import { controllers, customAxios, dataController } from 'api';
import { getSearchArticles, useSearchArticles } from './search';
import { IArticle, IArticlesList } from './types';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClientProviderTestWrapper } from 'utils/testWrappers';

describe('getSearchArticles', () => {
  it('calls /knowledge_base/search GET method with given locale and query params and returns payloads data', async () => {
    const getSearchArticlesMockedData: IArticlesList = {
      chapters: [
        {
          id: 1,
          title: {
            pl: 'test_chapter_pl_title',
            en: 'test_chapter_en_title'
          },
          articles: [
            {
              id: 2,
              url: 'test_article_url',
              title: {
                pl: 'test_article_pl_title',
                en: 'test_article_en_title'
              }
            }
          ]
        }
      ],
      title: {
        en: 'test_en_title',
        pl: 'test_pl_title'
      }
    };
    const lang = 'en';
    const query = 'test_query';
    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.resolve({ data: getSearchArticlesMockedData }));
    const payloadData: Promise<IArticlesList> = getSearchArticles(lang, query);
    waitFor(() => {
      expect(payloadData).not.toBe(null);
    });
    expect(payloadData).resolves.toStrictEqual(getSearchArticlesMockedData);
    expect(customAxios.get).toHaveBeenCalledWith(
      `${dataController}${controllers.services.articlesSearch}?lang=en&q=test_query`
    );
  });

  it('throws error upon breaking a try-catch clause', async () => {
    const err = new Error('test error message');
    const lang = 'en';
    const query = 'test_query';
    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.reject(err));
    const payloadData: Promise<IArticlesList> = getSearchArticles(lang, query);
    waitFor(() => {
      expect(payloadData).not.toBe(null);
    });
    expect(payloadData).rejects.toStrictEqual(err);
  });
});

describe('useSearchArticles', () => {
  it('returns reactQuery containing backend data regarding searched article list', async () => {
    const useSearchArticlesMockedData: IArticle[] = [];
    const lang = 'en';
    const query = 'test_query';

    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.resolve({ data: useSearchArticlesMockedData }));

    const useSearchArticlesRenderingResult = renderHook(() => useSearchArticles(lang, query), {
      wrapper: QueryClientProviderTestWrapper
    });
    await waitFor(() => {
      expect(useSearchArticlesRenderingResult.result.current.isSuccess).toBe(true);
    });

    expect(customAxios.get).toHaveBeenCalledWith(
      `${dataController}${controllers.services.articlesSearch}?lang=en&q=test_query`
    );
    expect(useSearchArticlesRenderingResult.result.current.isSuccess).toBe(true);
    expect(useSearchArticlesRenderingResult.result.current.data).toStrictEqual(useSearchArticlesMockedData);
  });
});
