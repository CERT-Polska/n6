import { expect, Page, test } from '@playwright/test';
import { MockedApi } from './utils/mockedApi';
import { listOfUsers, MockedUser } from './utils/mockedUsers';
import { TestRunner } from './utils/TestRunner';
import { expectToBeVisibleAndEnabled } from './utils/tools';
import { IArticle, IArticlesList } from '../src/api/services/kb/types';
import { dictionary } from '../src/dictionary';

const mockedKnowledgeBaseResponse: IArticlesList = {
  title: {
    pl: 'Spis treści',
    en: 'Table of contents'
  },
  chapters: [
    {
      id: 1,
      title: {
        pl: 'Nazwa rozdziału 1',
        en: 'Name of chapter 1'
      },
      articles: [
        {
          id: 1,
          url: '/knowledge_base/articles/1',
          title: {
            pl: 'Artykuł 1',
            en: 'Article 1'
          }
        },
        {
          id: 2,
          url: '/knowledge_base/articles/2',
          title: {
            pl: 'Artykuł 2',
            en: 'Article 2'
          }
        }
      ]
    },
    {
      id: 2,
      title: {
        pl: 'Nazwa rozdziału 2',
        en: 'Name of chapter 2'
      },
      articles: [
        {
          id: 3,
          url: '/knowledge_base/articles/3',
          title: {
            pl: 'Artykuł 3',
            en: 'Article 3'
          }
        }
      ]
    }
  ]
};

const mockedKnowledgeBaseArticleResponse: IArticle = {
  id: 1,
  chapter_id: 1,
  content: {
    pl: '# TytułArtykułuMarkdown \n\n TreśćArtykułuMarkdown',
    en: '# ArticleTitleMarkdown \n\n ArticleContentMarkdown'
  }
};

const mockedKnowledgeBaseArticle2Response: IArticle = {
  id: 2,
  chapter_id: 1,
  content: {
    pl: '# TytułArtykułuMarkdown2 \n\n TreśćArtykułuMarkdown2',
    en: '# ArticleTitleMarkdown2 \n\n ArticleContentMarkdown2'
  }
};

const emptyKnowledgeBaseResponse: IArticlesList = {
  title: undefined,
  chapters: []
};

async function setupKnowledgeBaseResponse(page: Page, user: MockedUser, response: IArticlesList) {
  await page.reload();
  await MockedApi.getUserInfo(page, user);
  await MockedApi.mockApiRoute(page, '/api/knowledge_base/contents', response);
  await page.waitForTimeout(1000);
}

async function switchLanguage(page: Page, language: 'PL' | 'EN') {
  await page.getByTestId('userMenuNavBtn').click();
  await page.waitForSelector(`[data-testid="languagePicker${language}"]`, { state: 'visible' });
  await page.getByTestId(`languagePicker${language}`).click();
  await page.waitForTimeout(500);
}

async function expectArticlePlaceholderToContainText(page: Page, expectedText: string) {
  await expect(page.getByTestId('kb-article-placeholder')).toBeVisible();
  await expect(page.getByTestId('kb-article-placeholder-subtitle')).toBeVisible();
  await expect(page.getByTestId('kb-article-placeholder-subtitle')).toContainText(expectedText);
}

function execKnowledgeBaseTests(user: MockedUser) {
  test.beforeEach(async ({ page }) => {
    await page.getByTestId('navKnowledgeBase').click();
    await page.waitForURL('https://localhost/knowledge_base');
    await expect(page.getByTestId('knowledge-base-wrapper')).toBeVisible();
  });

  test(`${user.name}: Two columns layout is visible`, async ({ page }) => {
    await expect(page.getByTestId('kb-articles-column')).toBeVisible();
    await expect(page.getByTestId('kb-main-column')).toBeVisible();
  });

  test.describe('Layout and basic elements', () => {
    test.describe('Article placeholder', () => {
      test('is visible with all elements', async ({ page }) => {
        const placeholder = page.getByTestId('kb-article-placeholder');
        await expect(placeholder).toBeVisible();
        await expect(page.getByTestId('kb-article-placeholder-book-icon')).toBeVisible();
        await expect(page.getByTestId('kb-article-placeholder-title')).toBeVisible();
        await expect(page.getByTestId('kb-article-placeholder-subtitle')).toBeVisible();
      });
    });
  });

  test.describe('Articles list', () => {
    test('articles list container is visible', async ({ page }) => {
      await expect(page.getByTestId('kb-articles-list-container')).toBeVisible();
    });

    test('articles list has correct title', async ({ page }) => {
      await expect(page.getByTestId('kb-articles-list-title')).toBeVisible();
      await expect(page.getByText('Table of contents')).toBeVisible();
    });

    test('articles list is populated with chapters and articles', async ({ page }) => {
      const articlesListNav = page.getByTestId('kb-articles-list-nav');
      await expect(articlesListNav).toBeVisible();

      const hasChildren = await articlesListNav.evaluate((node) => node.children.length > 0);
      expect(hasChildren).toBe(true);

      await expect(page.getByText('Name of chapter 1')).toBeVisible();
      await expect(page.getByText('Name of chapter 2')).toBeVisible();
    });

    test('articles list is empty when no articles are available', async ({ page }) => {
      await setupKnowledgeBaseResponse(page, user, emptyKnowledgeBaseResponse);

      const articlesListNav = page.getByTestId('kb-articles-list-nav');
      await expect(articlesListNav).not.toBeVisible();

      const hasChildren = await articlesListNav.evaluate((node) => node.children.length > 0);
      expect(hasChildren).toBe(false);
    });

    test.describe('Chapters', () => {
      test('chapter collapse buttons are visible and functional', async ({ page }) => {
        await expect(page.getByTestId('kb-chapter-collapse-button-1')).toBeVisible();
        await expect(page.getByTestId('kb-chapter-collapse-button-2')).toBeVisible();
      });

      test('chapter reveals articles when clicked', async ({ page }) => {
        // First chapter
        await page.getByTestId('kb-chapter-collapse-button-1').click();
        await expect(page.getByTestId('kb-chapter-1-link-1')).toBeVisible();
        await expect(page.getByTestId('kb-chapter-1-link-2')).toBeVisible();
        await expect(page.getByTestId('kb-chapter-1-link-1')).toContainText('Article 1');
        await expect(page.getByTestId('kb-chapter-1-link-2')).toContainText('Article 2');

        // Second chapter
        await page.getByTestId('kb-chapter-collapse-button-2').click();
        await expect(page.getByTestId('kb-chapter-2-link-3')).toBeVisible();
        await expect(page.getByTestId('kb-chapter-2-link-3')).toContainText('Article 3');
      });

      test('chapter hides articles when clicked again', async ({ page }) => {
        await page.getByTestId('kb-chapter-collapse-button-1').click();
        await expect(page.getByTestId('kb-chapter-1-link-1')).toBeVisible();
        await expect(page.getByTestId('kb-chapter-1-link-2')).toBeVisible();

        await page.getByTestId('kb-chapter-collapse-button-1').click();
        await expect(page.getByTestId('kb-chapter-1-link-1')).not.toBeVisible();
        await expect(page.getByTestId('kb-chapter-1-link-2')).not.toBeVisible();
      });

      test('chapter article links navigate to the correct article', async ({ page }) => {
        await MockedApi.mockApiRoute(page, '/api/knowledge_base/articles/1', mockedKnowledgeBaseArticleResponse);
        await page.getByTestId('kb-chapter-collapse-button-1').click();
        await page.getByTestId('kb-chapter-1-link-1').click();

        await expect(page).toHaveURL('/knowledge_base/articles/1');
        await expect(page.getByText('ArticleTitleMarkdown')).toBeVisible();
      });

      test('multiple chapters can be open simultaneously', async ({ page }) => {
        await page.getByTestId('kb-chapter-collapse-button-1').click();
        await page.getByTestId('kb-chapter-collapse-button-2').click();

        await expect(page.getByTestId('kb-chapter-1-link-1')).toBeVisible();
        await expect(page.getByTestId('kb-chapter-1-link-2')).toBeVisible();
        await expect(page.getByTestId('kb-chapter-2-link-3')).toBeVisible();
      });
    });
  });

  test.describe('Search functionality', () => {
    test.describe('Search form', () => {
      test('search form and button are visible and enabled', async ({ page }) => {
        await expectToBeVisibleAndEnabled(page.getByTestId('kb-article-search-form'));
        await expectToBeVisibleAndEnabled(page.getByTestId('kb-article-search-form-button'));
      });

      test.describe('Search form validation', () => {
        test('shows error when no search query is provided', async ({ page }) => {
          await page.getByTestId('kb-article-search-form-button').click();
          await expect(page.getByTestId('form-render-error-msg')).toBeVisible();
        });

        test('shows error when search query is too short', async ({ page }) => {
          await page.getByTestId('kb-article-search-form').fill('a');
          await page.getByTestId('kb-article-search-form-button').click();
          await expect(page.getByTestId('form-render-error-msg')).toBeVisible();
        });

        test('accepts valid search query', async ({ page }) => {
          await page.getByTestId('kb-article-search-form').fill('test');
          await page.getByTestId('kb-article-search-form-button').click();
          await expect(page.getByTestId('form-render-error-msg')).not.toBeVisible();
        });

        test('trims whitespace from search query', async ({ page }) => {
          await MockedApi.mockApiRoute(
            page,
            '/api/knowledge_base/search?lang=en&q=example',
            mockedKnowledgeBaseResponse
          );

          await page.getByTestId('kb-article-search-form').fill('  example  ');
          await page.getByTestId('kb-article-search-form-button').click();

          await expect(page.getByTestId('kb-search-results')).toBeVisible();
        });
      });
    });

    test.describe('Search results', () => {
      const performSearch = async (page: Page, query: string) => {
        await page.getByTestId('kb-article-search-form').fill(query);
        await page.getByTestId('kb-article-search-form-button').click();
      };

      test('non-existent search results are handled properly', async ({ page }) => {
        const query = 'nonexistent';
        await MockedApi.mockApiRoute(page, `/api/knowledge_base/search?lang=en&q=${query}`, emptyKnowledgeBaseResponse);

        await performSearch(page, query);

        await expect(page.getByTestId('kb-search-results-empty-title')).toBeVisible();
        await expect(page.getByTestId('kb-search-results-empty-info')).toBeVisible();
      });

      test.beforeEach(async ({ page }) => {
        const query = 'example';
        await MockedApi.mockApiRoute(
          page,
          `/api/knowledge_base/search?lang=en&q=${query}`,
          mockedKnowledgeBaseResponse
        );
        await performSearch(page, query);
        await page.waitForSelector('[data-testid="kb-search-results"]', { state: 'visible' });
      });

      test('search results container is visible', async ({ page }) => {
        await expect(page.getByTestId('kb-search-results')).toBeVisible();
      });

      test('search results title is visible', async ({ page }) => {
        await expect(page.getByTestId('kb-search-results-title')).toBeVisible();
      });

      test('search results show all matching articles', async ({ page }) => {
        const articleLink1 = page.getByTestId('kb-search-results-item-link-1');
        const articleLink2 = page.getByTestId('kb-search-results-item-link-2');
        const articleLink3 = page.getByTestId('kb-search-results-item-link-3');

        await expect(articleLink1).toBeVisible();
        await expect(articleLink2).toBeVisible();
        await expect(articleLink3).toBeVisible();

        await expect(page.getByTestId('kb-search-results-item-title-1')).toBeVisible();
        await expect(page.getByTestId('kb-search-results-item-title-2')).toBeVisible();
        await expect(page.getByTestId('kb-search-results-item-title-3')).toBeVisible();
      });

      test('search result link redirects to the correct article', async ({ page }) => {
        await MockedApi.mockApiRoute(page, '/api/knowledge_base/articles/1', mockedKnowledgeBaseArticleResponse);
        await page.getByTestId('kb-search-results-item-link-1').click();

        await expect(page).toHaveURL('/knowledge_base/articles/1');
        await expect(page.getByText('ArticleTitleMarkdown')).toBeVisible();
      });

      test('can perform a new search from results page', async ({ page }) => {
        const mockedSearchResponse = {
          title: { pl: 'Wyniki wyszukiwania', en: 'Search results' },
          chapters: [
            {
              id: 1,
              title: { pl: 'Wyniki', en: 'Results' },
              articles: [
                {
                  id: 2,
                  url: '/knowledge_base/articles/2',
                  title: { pl: 'Artykuł 2', en: 'Article 2' }
                }
              ]
            }
          ]
        };
        const newQuery = 'test';
        await MockedApi.mockApiRoute(page, `/api/knowledge_base/search?lang=en&q=${newQuery}`, mockedSearchResponse);

        await performSearch(page, newQuery);

        const articleLink2 = page.getByTestId('kb-search-results-item-link-2');
        const articleTitle2 = page.getByTestId('kb-search-results-item-title-2');
        const articleTitle1 = page.getByTestId('kb-search-results-item-title-1');
        const articleTitle3 = page.getByTestId('kb-search-results-item-title-3');

        await expect(articleLink2).toBeVisible();
        await expect(articleTitle2).toBeVisible();
        await expect(articleTitle1).not.toBeVisible();
        await expect(articleTitle3).not.toBeVisible();
      });
    });
  });

  test.describe('Article viewing', () => {
    test.describe('Single article', () => {
      test.beforeEach(async ({ page }) => {
        await MockedApi.mockApiRoute(page, '/api/knowledge_base/articles/1', mockedKnowledgeBaseArticleResponse);
        await page.getByTestId('kb-chapter-collapse-button-1').click();
        await page.getByTestId('kb-chapter-1-link-1').click();
        await page.waitForSelector('[data-testid="kb-article"]', { state: 'visible' });
      });

      test('is visible with all elements', async ({ page }) => {
        await expect(page.getByTestId('kb-article')).toBeVisible();
        await expect(page.getByTestId('kb-article-markdown')).toBeVisible();
      });

      test('article has correct markdown content', async ({ page }) => {
        await expect(page.getByTestId('kb-article-markdown')).toBeVisible();
        const titleElement = await page.getByText('ArticleTitleMarkdown');
        await expect(titleElement).toBeVisible();
        await expect(titleElement.evaluate((el) => el.tagName)).resolves.toBe('H1');
        const contentElement = page.getByText('ArticleContentMarkdown');
        await expect(contentElement).toBeVisible();
        await expect(contentElement.evaluate((el) => el.tagName)).resolves.toBe('P');
      });

      test('can navigate to a different article', async ({ page }) => {
        await MockedApi.mockApiRoute(page, '/api/knowledge_base/articles/2', mockedKnowledgeBaseArticle2Response);
        await page.getByTestId('kb-chapter-1-link-2').click();
        await page.waitForSelector('[data-testid="kb-article"]', { state: 'visible' });

        await expect(page.getByText('ArticleTitleMarkdown2')).toBeVisible();
        await expect(page.getByText('ArticleContentMarkdown2')).toBeVisible();
      });

      test.describe('PDF download functionality', () => {
        async function downloadArticleAndCheckFilename(page: Page, articleId: string, language: string) {
          await MockedApi.mockPdfDownload(page, articleId, language, true);
          const downloadPromise = page.waitForEvent('download');
          await page.getByTestId('kb-article-download-pdf-button').click();
          const download = await downloadPromise;
          expect(download.suggestedFilename()).toContain(`article-${articleId}-${language}.pdf`);
        }

        test('download pdf button is visible and enabled', async ({ page }) => {
          await expectToBeVisibleAndEnabled(page.getByTestId('kb-article-download-pdf-button'));
        });

        test('download pdf button has correct accessibility attributes', async ({ page }) => {
          const downloadButton = page.getByTestId('kb-article-download-pdf-button');

          await expect(downloadButton).toContainText('Download PDF file');
          await expect(page.getByTestId('kb-article-download-pdf-icon')).toBeVisible();
          await expect(downloadButton).toHaveAttribute('type', 'button');
        });

        test('download button is keyboard accessible', async ({ page }) => {
          await MockedApi.mockPdfDownload(page, '1', 'en', true);

          const downloadPromise = page.waitForEvent('download');

          await page.getByTestId('kb-article-download-pdf-button').focus();
          await page.keyboard.press('Enter');

          const download = await downloadPromise;

          expect(download.suggestedFilename()).toContain('article-1-en.pdf');
        });

        test('successfully downloads article as PDF', async ({ page }) => {
          await downloadArticleAndCheckFilename(page, '1', 'en');
          await expect(page.getByTestId('kb-article-download-pdf-error')).not.toBeVisible();
        });

        test('shows error message when PDF download fails', async ({ page }) => {
          await MockedApi.mockPdfDownload(page, '1', 'en', false);

          await page.getByTestId('kb-article-download-pdf-button').click();

          await expect(page.getByTestId('kb-article-download-pdf-error')).toBeVisible();
          await expect(page.getByText('Failed to download PDF file')).toBeVisible();
        });

        test('downloads PDF in the current language', async ({ page }) => {
          await downloadArticleAndCheckFilename(page, '1', 'en');

          // Switch to Polish
          await switchLanguage(page, 'PL');

          await downloadArticleAndCheckFilename(page, '1', 'pl');
        });

        test('downloads PDF from different articles', async ({ page }) => {
          await MockedApi.mockApiRoute(page, '/api/knowledge_base/articles/2', mockedKnowledgeBaseArticle2Response);

          await downloadArticleAndCheckFilename(page, '1', 'en');

          // Navigate to article 2
          await page.getByTestId('kb-chapter-1-link-2').click();
          await page.waitForSelector('[data-testid="kb-article"]', { state: 'visible' });

          await downloadArticleAndCheckFilename(page, '2', 'en');
        });
      });
    });

    test.describe('Error handling', () => {
      test('handles article not found error', async ({ page }) => {
        await MockedApi.mockApiRoute(page, '/api/knowledge_base/articles/3', {}, 404);

        await page.getByTestId('kb-chapter-collapse-button-2').click();
        await page.getByTestId('kb-chapter-2-link-3').click();

        await expect(page.getByTestId('kb-article-placeholder')).toBeVisible();
        await expect(page.getByTestId('kb-article-placeholder-subtitle')).toBeVisible();
        await expect(page.getByTestId('kb-article-placeholder-subtitle')).toContainText(
          dictionary.en['knowledge_base_article_not_found']
        );
      });

      test('handles invalid article ID', async ({ page }) => {
        await page.goto('/knowledge_base/articles/invalid');

        await expect(page.getByTestId('kb-article-placeholder')).toBeVisible();
        await expect(page.getByTestId('kb-article-placeholder-subtitle')).toBeVisible();
        await expect(page.getByTestId('kb-article-placeholder-subtitle')).toContainText(
          dictionary.en['knowledge_base_invalid_article_id']
        );
      });

      test('handles network errors', async ({ page }) => {
        await page.route('/api/knowledge_base/articles/3', (route) => route.abort('failed'));

        await page.getByTestId('kb-chapter-collapse-button-2').click();
        await page.getByTestId('kb-chapter-2-link-3').click();

        await expect(page.getByTestId('kb-article-placeholder')).toBeVisible();
        await expect(page.getByTestId('kb-article-placeholder-subtitle')).toBeVisible();
        await expect(page.getByTestId('kb-article-placeholder-subtitle')).toContainText(
          dictionary.en['knowledge_base_request_error']
        );
      });

      test.describe('API error handling', () => {
        const errorTypes = [
          { status: 400, description: 'Bad Request', message: 'knowledge_base_request_error' },
          { status: 401, description: 'Unauthorized', message: 'knowledge_base_request_error' },
          { status: 403, description: 'Forbidden', message: 'knowledge_base_request_error' },
          { status: 404, description: 'Not Found', message: 'knowledge_base_article_not_found' },
          { status: 500, description: 'Internal Server Error', message: 'knowledge_base_request_error' },
          { status: 503, description: 'Service Unavailable', message: 'knowledge_base_request_error' }
        ];

        for (const { status, description, message } of errorTypes) {
          test(`displays correct error for ${description} (${status})`, async ({ page }) => {
            await MockedApi.mockApiRoute(page, '/api/knowledge_base/articles/1', { error: description }, status);
            await page.goto('/knowledge_base/articles/1');
            await expect(page.getByTestId('kb-article-placeholder')).toBeVisible();
            await expect(page.getByTestId('kb-article-placeholder-subtitle')).toBeVisible();
            await expect(page.getByTestId('kb-article-placeholder-subtitle')).toContainText(dictionary.en[message]);
          });
        }
      });

      test.describe('Direct URL navigation to articles', () => {
        test('handles direct navigation to non-existent article', async ({ page }) => {
          await MockedApi.mockApiRoute(page, '/api/knowledge_base/articles/999', {}, 404);
          await page.goto('/knowledge_base/articles/999');

          await expectArticlePlaceholderToContainText(page, dictionary.en['knowledge_base_article_not_found']);
        });

        test('handles direct navigation to article with invalid ID format', async ({ page }) => {
          await page.goto('/knowledge_base/articles/abc');

          await expectArticlePlaceholderToContainText(page, dictionary.en['knowledge_base_invalid_article_id']);
        });

        test('handles direct navigation to article with server error', async ({ page }) => {
          await MockedApi.mockApiRoute(page, '/api/knowledge_base/articles/1', {}, 500);
          await page.goto('/knowledge_base/articles/1');

          await expectArticlePlaceholderToContainText(page, dictionary.en['knowledge_base_request_error']);
        });

        test('error messages are correctly localized when language is changed', async ({ page }) => {
          await MockedApi.mockApiRoute(page, '/api/knowledge_base/articles/999', {}, 404);

          await page.goto('/knowledge_base/articles/999');

          await expectArticlePlaceholderToContainText(page, dictionary.en['knowledge_base_article_not_found']);

          await switchLanguage(page, 'PL');

          await expectArticlePlaceholderToContainText(page, dictionary.pl['knowledge_base_article_not_found']);

          await switchLanguage(page, 'EN');

          await expectArticlePlaceholderToContainText(page, dictionary.en['knowledge_base_article_not_found']);
        });

        test('invalid article ID error is correctly localized', async ({ page }) => {
          await page.goto('/knowledge_base/articles/abc');

          await expectArticlePlaceholderToContainText(page, dictionary.en['knowledge_base_invalid_article_id']);

          await switchLanguage(page, 'PL');

          await expectArticlePlaceholderToContainText(page, dictionary.pl['knowledge_base_invalid_article_id']);
        });

        test('request error message is correctly localized', async ({ page }) => {
          await MockedApi.mockApiRoute(page, '/api/knowledge_base/articles/1', {}, 500);
          await page.goto('/knowledge_base/articles/1');

          await expectArticlePlaceholderToContainText(page, dictionary.en['knowledge_base_request_error']);

          await switchLanguage(page, 'PL');

          await expectArticlePlaceholderToContainText(page, dictionary.pl['knowledge_base_request_error']);
        });
      });
    });
  });

  test.describe('Localization', () => {
    test('switches article content language when language is changed', async ({ page }) => {
      await MockedApi.mockApiRoute(page, '/api/knowledge_base/articles/1', mockedKnowledgeBaseArticleResponse);

      await page.getByTestId('kb-chapter-collapse-button-1').click();
      await page.getByTestId('kb-chapter-1-link-1').click();

      await expect(page.getByText('ArticleTitleMarkdown')).toBeVisible();

      await switchLanguage(page, 'PL');

      await expect(page.getByText('TytułArtykułuMarkdown')).toBeVisible();
      await expect(page.getByText('TreśćArtykułuMarkdown')).toBeVisible();

      await switchLanguage(page, 'EN');

      await expect(page.getByText('ArticleTitleMarkdown')).toBeVisible();
    });

    test('switches chapter and article titles when language is changed', async ({ page }) => {
      await expect(page.getByText('Name of chapter 1')).toBeVisible();
      await expect(page.getByText('Name of chapter 2')).toBeVisible();

      await page.getByTestId('kb-chapter-collapse-button-1').click();

      await expect(page.getByTestId('kb-chapter-1-link-1')).toContainText('Article 1');

      await switchLanguage(page, 'PL');

      await expect(page.getByText('Nazwa rozdziału 1')).toBeVisible();
      await expect(page.getByText('Nazwa rozdziału 2')).toBeVisible();
      await expect(page.getByTestId('kb-chapter-1-link-1')).toContainText('Artykuł 1');
    });

    test('search results update when language is changed', async ({ page }) => {
      await MockedApi.mockApiRoute(page, '/api/knowledge_base/search?lang=en&q=test', mockedKnowledgeBaseResponse);
      await MockedApi.mockApiRoute(page, '/api/knowledge_base/search?lang=pl&q=test', mockedKnowledgeBaseResponse);

      await page.getByTestId('kb-article-search-form').fill('test');
      await page.getByTestId('kb-article-search-form-button').click();
      await page.waitForSelector('[data-testid="kb-search-results"]', { state: 'visible' });

      await expect(page.getByTestId('kb-search-results-item-title-1')).toContainText('Article 1');

      await switchLanguage(page, 'PL');
      await page.waitForTimeout(500);

      await expect(page.getByTestId('kb-search-results-item-title-1')).toContainText('Artykuł 1');

      await switchLanguage(page, 'EN');
      await page.waitForTimeout(500);

      await expect(page.getByTestId('kb-search-results-item-title-1')).toContainText('Article 1');
    });
  });
}

const runner = TestRunner.builder
  .withTestName('Knowledge Base Tests')
  .withUsers(listOfUsers)
  .withBeforeEach(async (page, user) => {
    await MockedApi.getUserInfo(page, user);
    await page.goto('/');
    await MockedApi.getUserInfo(page, user);
    await MockedApi.mockApiRoute(page, '/api/knowledge_base/contents', mockedKnowledgeBaseResponse);
  })
  .withTests((user) => {
    if (user.knowledgeBaseEnabled) {
      execKnowledgeBaseTests(user);
    } else {
      test(`${user.name}: Knowledge Base is disabled`, async ({ page }) => {
        await expect(page.getByTestId('navKnowledgeBase')).not.toBeVisible();
      });
    }
  })
  .build();

runner.runTests();
