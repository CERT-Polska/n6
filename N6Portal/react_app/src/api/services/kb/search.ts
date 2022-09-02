import { AxiosError } from 'axios';
import { useQuery, UseQueryOptions, UseQueryResult } from 'react-query';
import { TUserAgentLocale } from 'context/LanguageProvider';
import { IArticlesList } from 'api/services/kb/types';
import { controllers, customAxios, dataController } from 'api';

export const getSearchArticles = async (lang: TUserAgentLocale, query: string) => {
  try {
    const payload = await customAxios.get<IArticlesList>(
      `${dataController}${controllers.services.articlesSearch}?lang=${lang}&q=${query}`
    );
    return payload.data;
  } catch (reason) {
    throw reason;
  }
};

export const useSearchArticles = (
  lang: TUserAgentLocale,
  query: string,
  options?: Omit<UseQueryOptions<IArticlesList, AxiosError>, 'queryKey' | 'queryFn'>
): UseQueryResult<IArticlesList, AxiosError> => {
  return useQuery(
    ['searchArticles', lang, query],
    (): Promise<IArticlesList> => getSearchArticles(lang, query),
    options
  );
};
