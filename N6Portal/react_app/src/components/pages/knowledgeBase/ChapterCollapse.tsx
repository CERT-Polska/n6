import { FC, useState, useEffect } from 'react';
import { NavLink } from 'react-router-dom';
import { Collapse } from 'react-bootstrap';
import classNames from 'classnames';
import { ReactComponent as Chevron } from 'images/chevron.svg';
import { IChapter } from 'api/services/kb/types';
import { useTypedIntl } from 'utils/useTypedIntl';
import useChapterCollapseContext from 'context/ChapterCollapseContext';

interface IProps {
  chapter: IChapter;
}

interface ICollapseToggleButton {
  active: boolean;
  handleChange: () => void;
  children: React.ReactNode;
  dataTestId?: string;
}

const CollapseToggleButton: FC<ICollapseToggleButton> = ({ children, handleChange, active, dataTestId }) => {
  return (
    <button className="kb-collapse-button" onClick={handleChange} aria-expanded={active} data-testid={dataTestId}>
      <Chevron className={classNames('articles-list-chapter-chevron me-2', { open: active })} />
      {children}
    </button>
  );
};

const ChapterCollapse: FC<IProps> = ({ chapter }) => {
  const { locale } = useTypedIntl();

  const { activeArticleId } = useChapterCollapseContext();
  const [isCollapsed, setCollapsed] = useState(true);

  const chapterContainsActiveArticle = chapter.articles.some((article) => article.id.toString() === activeArticleId);

  useEffect(() => {
    if (chapterContainsActiveArticle) {
      setCollapsed(false);
    }
  }, [chapterContainsActiveArticle]);

  return (
    <div className="text-break kb-collapse" data-testid={`kb-chapter-collapse-${chapter.id}`}>
      <CollapseToggleButton
        active={!isCollapsed}
        handleChange={() => setCollapsed((prevState) => !prevState)}
        dataTestId={`kb-chapter-collapse-button-${chapter.id}`}
      >
        {chapter.title[locale]}
      </CollapseToggleButton>
      {!!chapter.articles.length && (
        <Collapse in={!isCollapsed}>
          <ul className="kb-chapter" data-testid={`kb-chapter-${chapter.id}`}>
            {chapter.articles.map((article) => (
              <li className="kb-chapter-item" key={article.id}>
                <NavLink
                  to={article.url}
                  className="kb-chapter-link"
                  activeClassName="active"
                  data-testid={`kb-chapter-${chapter.id}-link-${article.id}`}
                >
                  {article.title[locale]}
                </NavLink>
              </li>
            ))}
          </ul>
        </Collapse>
      )}
    </div>
  );
};

export default ChapterCollapse;
