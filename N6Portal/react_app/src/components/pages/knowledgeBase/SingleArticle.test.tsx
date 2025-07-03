import { render, screen } from '@testing-library/react';
import { LanguageProviderTestWrapper, QueryClientProviderTestWrapper } from 'utils/testWrappers';
import SingleArticle from './SingleArticle';
import { BrowserRouter, useParams } from 'react-router-dom';
import * as SingleArticlePlaceholderModule from './SingleArticlePlaceholder';
import { dictionary } from 'dictionary';
import * as useArticleModule from 'api/services/kb';
import { IArticle } from 'api/services/kb/types';
import { UseQueryResult } from 'react-query';
import { AxiosError } from 'axios';
import * as LoaderModule from 'components/loading/Loader';
import * as ReactMarkdownModule from 'react-markdown';
import remarkGfm from 'remark-gfm';
import * as getArticlePdfFileModule from 'api/services/kb/getArticlePdfFile';
import FileSaver from 'file-saver';
import userEvent from '@testing-library/user-event';

jest.mock('remark-gfm', () => () => {}); // to resolve styling module import error
jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useParams: jest.fn()
}));
const useParamsMock = useParams as jest.Mock;

describe('<SingleArticle />', () => {
  it('renders placeholder article page when no/invalid article ID was provided in location query', () => {
    const SingleArticlePlaceholderSpy = jest.spyOn(SingleArticlePlaceholderModule, 'default').mockReturnValue(null); // so to check if there is nothing else except placeholder
    useParamsMock.mockReturnValue({ articleId: undefined });
    const { container } = render(
      <BrowserRouter>
        <QueryClientProviderTestWrapper>
          <LanguageProviderTestWrapper>
            <SingleArticle />
          </LanguageProviderTestWrapper>
        </QueryClientProviderTestWrapper>
      </BrowserRouter>
    );
    expect(container).toBeEmptyDOMElement(); // because only placeholder was rendered in place of article
    expect(SingleArticlePlaceholderSpy).toHaveBeenCalledWith(
      {
        subtitle: dictionary['en']['knowledge_base_invalid_article_id']
      },
      {}
    );
  });

  it('renders placeholder article page when there is no article with provided ID', () => {
    const SingleArticlePlaceholderSpy = jest.spyOn(SingleArticlePlaceholderModule, 'default').mockReturnValue(null); // so to check if there is nothing else except placeholder
    useParamsMock.mockReturnValue({ articleId: 1 });

    const useArticleReturnValue = { isLoading: false } as UseQueryResult<IArticle, AxiosError>;
    jest.spyOn(useArticleModule, 'useArticle').mockReturnValue(useArticleReturnValue);

    const { container } = render(
      <BrowserRouter>
        <QueryClientProviderTestWrapper>
          <LanguageProviderTestWrapper>
            <SingleArticle />
          </LanguageProviderTestWrapper>
        </QueryClientProviderTestWrapper>
      </BrowserRouter>
    );

    expect(container).toBeEmptyDOMElement(); // because only placeholder was rendered in place of article
    expect(SingleArticlePlaceholderSpy).toHaveBeenCalledWith(
      {
        subtitle: dictionary['en']['knowledge_base_request_error']
      },
      {}
    );
  });

  it('renders loader during article fetching', () => {
    useParamsMock.mockReturnValue({ articleId: 1 });
    const useArticleReturnValue = { isLoading: true } as UseQueryResult<IArticle, AxiosError>;
    jest.spyOn(useArticleModule, 'useArticle').mockReturnValue(useArticleReturnValue);
    const LoaderSpy = jest.spyOn(LoaderModule, 'default');

    const { container } = render(
      <BrowserRouter>
        <QueryClientProviderTestWrapper>
          <LanguageProviderTestWrapper>
            <SingleArticle />
          </LanguageProviderTestWrapper>
        </QueryClientProviderTestWrapper>
      </BrowserRouter>
    );

    expect(container).not.toBeEmptyDOMElement();
    expect(LoaderSpy).toHaveBeenCalled();
  });

  it('renders placeholder article page when error occurs during fetching of data', () => {
    const SingleArticlePlaceholderSpy = jest.spyOn(SingleArticlePlaceholderModule, 'default').mockReturnValue(null); // so to check if there is nothing else except placeholder
    useParamsMock.mockReturnValue({ articleId: 1 });

    const useArticleReturnValue = { isError: true, error: { response: { status: 404 } } } as UseQueryResult<
      IArticle,
      AxiosError
    >;
    jest.spyOn(useArticleModule, 'useArticle').mockReturnValue(useArticleReturnValue);

    const { container } = render(
      <BrowserRouter>
        <QueryClientProviderTestWrapper>
          <LanguageProviderTestWrapper>
            <SingleArticle />
          </LanguageProviderTestWrapper>
        </QueryClientProviderTestWrapper>
      </BrowserRouter>
    );

    expect(container).toBeEmptyDOMElement(); // because only placeholder was rendered in place of article
    expect(SingleArticlePlaceholderSpy).toHaveBeenCalledWith(
      {
        subtitle: dictionary['en']['knowledge_base_article_not_found']
      },
      {}
    );
  });

  it('renders article page with provided content', async () => {
    const exampleContent = 'test example content of the article';
    const articleData: IArticle = {
      id: 0,
      chapter_id: 0,
      content: {
        pl: exampleContent,
        en: exampleContent
      }
    };
    const useArticleReturnValue = { data: articleData } as UseQueryResult<IArticle, AxiosError>;
    const articleId = 1;
    const stubDownloadPayload = new Blob();

    const ReactMarkdownSpy = jest.spyOn(ReactMarkdownModule, 'default');
    const getArticlePdfFileSpy = jest
      .spyOn(getArticlePdfFileModule, 'getArticlePdfFile')
      .mockResolvedValue(stubDownloadPayload);
    const FileSaverSaveAsSpy = jest.spyOn(FileSaver, 'saveAs').mockImplementation(() => {});
    jest.spyOn(useArticleModule, 'useArticle').mockReturnValue(useArticleReturnValue);
    useParamsMock.mockReturnValue({ articleId: articleId });
    Element.prototype.scrollIntoView = jest.fn();

    const { container } = render(
      <BrowserRouter>
        <QueryClientProviderTestWrapper>
          <LanguageProviderTestWrapper>
            <SingleArticle />
          </LanguageProviderTestWrapper>
        </QueryClientProviderTestWrapper>
      </BrowserRouter>
    );

    expect(ReactMarkdownSpy).toHaveBeenCalledWith(
      {
        children: exampleContent,
        className: 'md-content',
        remarkPlugins: [remarkGfm],
        components: { code: expect.any(Function) }
      },
      {}
    );

    const downloadPdfButton = screen.getByRole('button');
    expect(container.querySelector('svg-download-mock')?.parentElement?.parentElement).toBe(downloadPdfButton);
    expect(downloadPdfButton).toHaveTextContent('Download PDF');

    await userEvent.click(downloadPdfButton);
    expect(getArticlePdfFileSpy).toHaveBeenCalledWith(articleId, 'en');
    expect(FileSaverSaveAsSpy).toHaveBeenCalledWith(stubDownloadPayload, `article-${articleId}-en.pdf`);
  });
});
