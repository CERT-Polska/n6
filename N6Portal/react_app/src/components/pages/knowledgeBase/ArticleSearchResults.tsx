import { FC } from 'react';
import { Link, useLocation } from 'react-router-dom';
import classnames from 'classnames';
import { useSearchArticles } from 'api/services/kb/search';
import { useTypedIntl } from 'utils/useTypedIntl';
import { IChapterArticle } from 'api/services/kb/types';
import { ReactComponent as RightArrow } from 'images/right_arrow.svg';
import ApiLoader from 'components/loading/ApiLoader';
import { searchRegex } from 'components/forms/validation/validationRegexp';
import useKBSearchContext from 'context/KBSearchContext';

const ArticleSearchResults: FC = () => {
  const { isQueryEnabled, disableSearchQuery, queryLang } = useKBSearchContext();

  const { locale, messages } = useTypedIntl();
  const location = useLocation();

  const searchQuery = location.search.split('q=')[1] ?? '';
  const isQueryValid = searchRegex.test(searchQuery);

  const { data, error, status } = useSearchArticles(queryLang, searchQuery, {
    enabled: isQueryValid && isQueryEnabled,
    onSuccess: disableSearchQuery
  });

  const searchedArticles = data?.chapters.reduce<IChapterArticle[]>(
    (prev, chapter) => [...prev, ...chapter.articles],
    []
  );

  const isEmptyView = !isQueryValid || !searchedArticles?.length;
  return (
    <div
      data-testid="kb-search-results"
      className={classnames('kb-search-results', { 'kb-search-results-empty': isEmptyView })}
    >
      <ApiLoader status={isQueryValid ? status : 'success'} error={error}>
        {isEmptyView ? (
          <>
            <h1 data-testid="kb-search-results-empty-title">{`${messages['knowledge_base_search_results_empty']} ${queryLang}`}</h1>
            <p data-testid="kb-search-results-empty-info">{messages['knowledge_base_search_results_empty_info']}</p>
          </>
        ) : (
          <>
            <header className="kb-search-results-header">
              <h1 data-testid="kb-search-results-title" className="h1">
                {`${messages['knowledge_base_search_results']} ${queryLang} (${searchedArticles.length})`}
              </h1>
            </header>
            <section>
              {searchedArticles.map((article) => (
                <div key={article.id} className="kb-search-results-item">
                  <p data-testid={`kb-search-results-item-title-${article.id}`}>{article.title[locale]}</p>
                  <div className="kb-search-results-arrow">
                    <Link
                      to={article.url}
                      data-testid={`kb-search-results-item-link-${article.id}`}
                      className="stretched-link"
                    >
                      <RightArrow data-testid={`kb-search-results-item-link-arrow-${article.id}`} />
                    </Link>
                  </div>
                </div>
              ))}
            </section>
          </>
        )}
      </ApiLoader>
    </div>
  );
};

export default ArticleSearchResults;
