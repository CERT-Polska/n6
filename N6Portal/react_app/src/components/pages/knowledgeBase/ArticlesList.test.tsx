import { render, screen } from '@testing-library/react';
import ArticlesList from './ArticlesList';
import { LanguageProviderTestWrapper, QueryClientProviderTestWrapper } from 'utils/testWrappers';
import * as useArticlesModule from 'api/services/kb';
import * as ApiLoaderModule from 'components/loading/ApiLoader';
import * as ChapterCollapseModule from './ChapterCollapse';
import * as ArticleSearchFormModule from './ArticleSearchForm';
import { IArticlesList } from 'api/services/kb/types';
import { AxiosError } from 'axios';
import { UseQueryResult } from 'react-query';

describe('<ArticlesList />', () => {
  it('renders left-side column of knowledge base page containing  search bar and collapsable chapters', () => {
    const ApiLoaderSpy = jest.spyOn(ApiLoaderModule, 'default');

    const articlesList: IArticlesList = {
      title: {
        pl: 'test_title_pl',
        en: 'test_title_en'
      },
      chapters: [
        {
          id: 1,
          title: {
            pl: 'test_chapter_pl',
            en: 'test_chapter_en'
          },
          articles: [
            {
              id: 10,
              url: 'test_url',
              title: {
                pl: 'test_article_pl',
                en: 'test_article_en'
              }
            }
          ]
        },
        {
          id: 2,
          title: {
            pl: 'test_chapter_2_pl',
            en: 'test_chapter_2_en'
          },
          articles: []
        }
      ]
    };
    const mockUseArticlesValue = { data: articlesList, status: 'success', error: null } as UseQueryResult<
      IArticlesList,
      AxiosError
    >;
    jest.spyOn(useArticlesModule, 'useArticles').mockReturnValue(mockUseArticlesValue);

    const ArticleSearchFormSpy = jest
      .spyOn(ArticleSearchFormModule, 'default')
      .mockReturnValue(<h6 className="mock-article-search-spy" />);
    const ChapterCollapseSpy = jest
      .spyOn(ChapterCollapseModule, 'default')
      .mockImplementation(({ chapter }) => <div className={`mock-chapter-collapse-${chapter?.title?.en}`} />);
    render(
      <QueryClientProviderTestWrapper>
        <LanguageProviderTestWrapper>
          <ArticlesList />
        </LanguageProviderTestWrapper>
      </QueryClientProviderTestWrapper>
    );

    expect(ApiLoaderSpy).toHaveBeenCalledWith(expect.objectContaining({ status: 'success', error: null }), {});
    expect(ArticleSearchFormSpy).toHaveBeenCalled();
    expect(screen.getByRole('heading', { level: 6 })).toBeInTheDocument(); // as per ArticleSearchForm mocking value
    expect(ChapterCollapseSpy).toHaveBeenCalledTimes(2);
    expect(ChapterCollapseSpy).toHaveBeenNthCalledWith(1, { chapter: articlesList.chapters[0] }, {});
    expect(ChapterCollapseSpy).toHaveBeenNthCalledWith(2, { chapter: articlesList.chapters[1] }, {});

    expect(screen.getByRole('navigation').childNodes).toHaveLength(articlesList.chapters.length);
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent(articlesList?.title?.en || '');
  });
});
