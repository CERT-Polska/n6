import { render, screen } from '@testing-library/react';
import ArticleSearchResults from './ArticleSearchResults';
import { LanguageProviderTestWrapper, QueryClientProviderTestWrapper } from 'utils/testWrappers';
import { BrowserRouter, useLocation } from 'react-router-dom';
import { dictionary } from 'dictionary';
import * as useSearchArticlesModule from 'api/services/kb/search';
import { UseQueryResult } from 'react-query';
import { IArticlesList } from 'api/services/kb/types';
import { AxiosError } from 'axios';
import { searchRegex } from 'components/forms/validation/validationRegexp';

jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useLocation: jest.fn()
}));
const useLocationMock = useLocation as jest.Mock;

describe('<ArticleSearchResults />', () => {
  it('renders message about no results from invalid query', () => {
    useLocationMock.mockReturnValue({ search: '' }); // query param
    render(
      <BrowserRouter>
        <QueryClientProviderTestWrapper>
          <LanguageProviderTestWrapper>
            <ArticleSearchResults />
          </LanguageProviderTestWrapper>
        </QueryClientProviderTestWrapper>
      </BrowserRouter>
    );
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('No results found in English');
    expect(screen.getByText(dictionary['en']['knowledge_base_search_results_empty_info'])).toHaveRole('paragraph');
  });

  it('renders message about no results from missing results', () => {
    const locationMockValue = 'aaa';
    expect(locationMockValue).toMatch(searchRegex);
    const mockResolvedValue = { data: null, status: 'success', error: null } as unknown as UseQueryResult<
      IArticlesList,
      AxiosError
    >;
    jest.spyOn(useSearchArticlesModule, 'useSearchArticles').mockReturnValue(mockResolvedValue);
    useLocationMock.mockReturnValue({ search: `q=${locationMockValue}` }); // query param
    render(
      <BrowserRouter>
        <QueryClientProviderTestWrapper>
          <LanguageProviderTestWrapper>
            <ArticleSearchResults />
          </LanguageProviderTestWrapper>
        </QueryClientProviderTestWrapper>
      </BrowserRouter>
    );
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('No results found in English');
    expect(screen.getByText(dictionary['en']['knowledge_base_search_results_empty_info'])).toHaveRole('paragraph');
  });

  it('renders list of article links returned by search query', () => {
    const articlesData: IArticlesList = {
      title: {
        en: 'test_article_list_title_en',
        pl: 'test_article_list_title_pl'
      },
      chapters: [
        {
          id: 1,
          title: {
            pl: 'test_chapter_1_title_pl',
            en: 'test_chapter_1_title_en'
          },
          articles: [
            {
              id: 10,
              url: 'test_article_10_url',
              title: {
                pl: 'test_article_10_title_pl',
                en: 'test_article_10_title_en'
              }
            },
            {
              id: 20,
              url: 'test_article_20_url',
              title: {
                pl: 'test_article_20_title_pl',
                en: 'test_article_20_title_en'
              }
            }
          ]
        },
        {
          id: 2,
          title: {
            pl: 'test_chapter_2_title_pl',
            en: 'test_chapter_2_title_en'
          },
          articles: [
            {
              id: 30,
              url: 'test_article_30_url',
              title: {
                pl: 'test_article_30_title_pl',
                en: 'test_article_30_title_en'
              }
            }
          ]
        }
      ]
    };
    const locationMockValue = 'aaa';
    expect(locationMockValue).toMatch(searchRegex);
    const mockResolvedValue = { data: articlesData, status: 'success', error: null } as UseQueryResult<
      IArticlesList,
      AxiosError
    >;
    jest.spyOn(useSearchArticlesModule, 'useSearchArticles').mockReturnValue(mockResolvedValue);
    useLocationMock.mockReturnValue({ search: `q=${locationMockValue}` }); // query param
    const { container } = render(
      <BrowserRouter>
        <QueryClientProviderTestWrapper>
          <LanguageProviderTestWrapper>
            <ArticleSearchResults />
          </LanguageProviderTestWrapper>
        </QueryClientProviderTestWrapper>
      </BrowserRouter>
    );

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(`Search results in language en (3)`);

    const linksToArticles = screen.getAllByRole('link');
    const rightArrows = container.querySelectorAll('svg-right-arrow-mock');
    expect(linksToArticles).toHaveLength(3);
    expect(rightArrows).toHaveLength(linksToArticles.length);
    linksToArticles.forEach((link, index) => {
      expect(link).toHaveAttribute('href', `/test_article_${index + 1}0_url`);
      expect(link.firstChild).toBe(rightArrows[index]);
      const linkAttachedParagraph = link.parentElement?.parentElement?.firstChild;
      expect(linkAttachedParagraph).toHaveTextContent(`test_article_${index + 1}0_title_en`);
    });
  });
});
