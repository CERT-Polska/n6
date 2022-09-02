import { FC } from 'react';
import get from 'lodash/get';
import ArticleSearchForm from 'components/pages/knowledgeBase/ArticleSearchForm';
import { useTypedIntl } from 'utils/useTypedIntl';
import { useArticles } from 'api/services/kb';
import ApiLoader from 'components/loading/ApiLoader';
import ChapterCollapse from 'components/pages/knowledgeBase/ChapterCollapse';

const ArticlesList: FC = () => {
  const { data, status, error } = useArticles();

  const { locale } = useTypedIntl();

  const knowledgeBaseTitle: string | undefined = get(data, `title.${locale}`, undefined);
  return (
    <ApiLoader status={status} error={error}>
      {data && (
        <aside className="kb-articles-list-wrapper">
          <ArticleSearchForm />
          {knowledgeBaseTitle && <h2 className="h4 mb-3">{knowledgeBaseTitle}</h2>}
          <nav className="kb-articles-list">
            {data.chapters.map((chapter) => (
              <ChapterCollapse key={chapter.id} chapter={chapter} />
            ))}
          </nav>
        </aside>
      )}
    </ApiLoader>
  );
};

export default ArticlesList;
