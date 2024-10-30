import { AxiosError } from 'axios';
import { useQuery, UseQueryOptions, UseQueryResult } from 'react-query';
import { controllers, customAxios, dataController } from 'api';
import { IArticle, IArticlesList } from 'api/services/kb/types';

export const getArticles = async (): Promise<IArticlesList> => {
  try {
    const payload = await customAxios.get<IArticlesList>(`${dataController}${controllers.services.articlesList}`);
    return payload.data;
  } catch (reason) {
    throw reason;
  }
};

export const getArticle = async (articleId: string): Promise<IArticle> => {
  try {
    const payload = await customAxios.get<IArticle>(`${dataController}${controllers.services.articles}/${articleId}`);
    return payload.data;
  } catch (reason) {
    throw reason;
  }
};

export const useArticle = (
  articleId: string,
  options?: Omit<UseQueryOptions<IArticle, AxiosError>, 'queryKey' | 'queryFn'>
): UseQueryResult<IArticle, AxiosError> => {
  return useQuery(
    `${controllers.services.articles}/${articleId}`,
    (): Promise<IArticle> => getArticle(articleId),
    options
  );
};

export const useArticles = (
  options?: Omit<UseQueryOptions<IArticlesList, AxiosError>, 'queryKey' | 'queryFn'>
): UseQueryResult<IArticlesList, AxiosError> => {
  return useQuery(`articlesList`, (): Promise<IArticlesList> => getArticles(), options);
};
