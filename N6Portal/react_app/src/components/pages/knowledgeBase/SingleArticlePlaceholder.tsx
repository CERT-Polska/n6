import { FC } from 'react';
import { ReactComponent as Book } from 'images/kb-book.svg';
import { useTypedIntl } from 'utils/useTypedIntl';

interface IProps {
  subtitle?: string;
}

const SingleArticlePlaceholder: FC<IProps> = ({ subtitle }) => {
  const { messages } = useTypedIntl();

  return (
    <article className="kb-article" data-testid="kb-article-placeholder">
      <div className="kb-article-book">
        <Book data-testid="kb-article-placeholder-book-icon" />
      </div>
      <div className="kb-article-default">
        <h1 data-testid="kb-article-placeholder-title">{messages['knowledge_base_default_header']}</h1>
        <p data-testid="kb-article-placeholder-subtitle">{subtitle ?? messages['knowledge_base_default_subtitle']}</p>
      </div>
    </article>
  );
};

export default SingleArticlePlaceholder;
