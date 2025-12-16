import { render, screen } from '@testing-library/react';
import KnowledgeBase from './KnowledgeBase';
import * as ArticlesListModule from './ArticlesList';
import * as ArticleSearchResultsModule from './ArticleSearchResults';
import * as SingleArticlePlaceholderModule from './SingleArticlePlaceholder';
import * as SingleArticleModule from './SingleArticle';
import { BrowserRouter, Redirect } from 'react-router-dom';
import { AuthContext, IAuthContext } from 'context/AuthContext';
import { LanguageProviderTestWrapper } from 'utils/testWrappers';
import routeList from 'routes/routeList';

jest.mock('remark-gfm', () => () => {}); // to resolve styling module import error
jest.mock('rehype-autolink-headings', () => () => {});
jest.mock('unist-util-visit', () => ({
  visit: jest.fn()
}));
jest.mock('hast-util-to-string', () => ({
  toString: jest.fn()
}));
jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  Redirect: jest.fn()
}));
const RedirectMock = Redirect as jest.Mock;

describe('<KnowledgeBase />', () => {
  it.each([
    { locationMockedValue: routeList.knowledgeBase, expectedTextMock: 'SingleArticlePlaceholder' },
    { locationMockedValue: routeList.knowledgeBaseSearchResults, expectedTextMock: 'ArticleSearchResults' },
    { locationMockedValue: routeList.knowledgeBase + '/articles/1', expectedTextMock: 'SingleArticle' }
  ])(
    'renders ArticlesList with article content, placeholder, search result \
    or redirect depending on current route context',
    ({ locationMockedValue, expectedTextMock }) => {
      const ArticlesListSpy = jest
        .spyOn(ArticlesListModule, 'default')
        .mockReturnValue(<h6 className="mock-articles-list" />);
      jest.spyOn(SingleArticlePlaceholderModule, 'default').mockReturnValue(<h5>SingleArticlePlaceholder</h5>);
      jest.spyOn(SingleArticleModule, 'default').mockReturnValue(<h5>SingleArticle</h5>);
      jest.spyOn(ArticleSearchResultsModule, 'default').mockReturnValue(<h5>ArticleSearchResults</h5>);

      window.history.pushState({}, 'test location', locationMockedValue);
      render(
        <LanguageProviderTestWrapper>
          <AuthContext.Provider value={{ knowledgeBaseEnabled: true } as IAuthContext}>
            <BrowserRouter>
              <KnowledgeBase />
            </BrowserRouter>
          </AuthContext.Provider>
        </LanguageProviderTestWrapper>
      );

      expect(ArticlesListSpy).toHaveBeenCalled();
      expect(screen.getByRole('heading', { level: 6 })).toBeInTheDocument();
      expect(screen.getByText(expectedTextMock)).toBeInTheDocument();
      expect(RedirectMock).not.toHaveBeenCalled();
    }
  );

  it('redirects to /not-found if knowledge base is not enabled', () => {
    render(
      <LanguageProviderTestWrapper>
        <AuthContext.Provider value={{ knowledgeBaseEnabled: false } as IAuthContext}>
          <BrowserRouter>
            <KnowledgeBase />
          </BrowserRouter>
        </AuthContext.Provider>
      </LanguageProviderTestWrapper>
    );
    expect(RedirectMock).toHaveBeenCalledWith({ to: routeList.notFound }, {});
  });

  it('redirects to /not-found if provided location is not valid', () => {
    const mockFailingRoute = routeList.knowledgeBase + '/test_fail_switch_case';
    window.history.pushState({}, 'test location', mockFailingRoute);
    jest.spyOn(ArticlesListModule, 'default').mockReturnValue(<h6 className="mock-articles-list" />);
    render(
      <LanguageProviderTestWrapper>
        <AuthContext.Provider value={{ knowledgeBaseEnabled: true } as IAuthContext}>
          <BrowserRouter>
            <KnowledgeBase />
          </BrowserRouter>
        </AuthContext.Provider>
      </LanguageProviderTestWrapper>
    );
    expect(RedirectMock).toHaveBeenCalledWith(expect.objectContaining({ to: routeList.notFound }), {});
  });
});
