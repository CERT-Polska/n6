import { render, screen } from '@testing-library/react';
import ChapterCollapse from './ChapterCollapse';
import { IChapter } from 'api/services/kb/types';
import { LanguageProviderTestWrapper } from 'utils/testWrappers';
import { BrowserRouter } from 'react-router-dom';
import userEvent from '@testing-library/user-event';

describe('<ChapterCollapse />', () => {
  it('renders clickable chevron with chapter name which reveals contained articles', async () => {
    const chapter: IChapter = {
      id: 1,
      title: {
        pl: 'test_chapter_name_pl',
        en: 'test_chapter_name_en'
      },
      articles: [
        {
          id: 1,
          url: 'test_article_url_1',
          title: {
            pl: 'test_article_title_pl_1',
            en: 'test_article_title_en_1'
          }
        },
        {
          id: 2,
          url: 'test_article_url_2',
          title: {
            pl: 'test_article_title_pl_1',
            en: 'test_article_title_en_1'
          }
        }
      ]
    };

    render(
      <BrowserRouter>
        <LanguageProviderTestWrapper>
          <ChapterCollapse chapter={chapter} />
        </LanguageProviderTestWrapper>
      </BrowserRouter>
    );
    const chevronButton = screen.getByRole('button');
    expect(chevronButton).toHaveTextContent(chapter.title.en);
    const collapseElement = screen.getByRole('list');
    expect(collapseElement).toHaveClass('kb-chapter collapse'); // no "show" className hides contents of list
    expect(collapseElement.childNodes).toHaveLength(chapter.articles.length);

    const linksToArticles = screen.getAllByRole('link');
    expect(linksToArticles).toHaveLength(chapter.articles.length);
    linksToArticles.forEach((link, index) => {
      expect(link).toHaveTextContent(chapter.articles[index].title.en);
      expect(link).toHaveAttribute('href', `/${chapter.articles[index].url}`);
    });

    await userEvent.click(chevronButton);
    expect(collapseElement).toHaveClass('kb-chapter collapse show'); // "show" className allows user to see articles
  });
});
