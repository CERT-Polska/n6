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
}

const CollapseToggleButton: FC<ICollapseToggleButton> = ({ children, handleChange, active }) => {
  return (
    <button className="kb-collapse-button" onClick={handleChange} aria-expanded={active}>
      <Chevron className={classNames('articles-list-chapter-chevron mr-2', { open: active })} />
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
    <div className="text-break kb-collapse">
      <CollapseToggleButton active={!isCollapsed} handleChange={() => setCollapsed((prevState) => !prevState)}>
        {chapter.title[locale]}
      </CollapseToggleButton>
      {!!chapter.articles.length && (
        <Collapse in={!isCollapsed}>
          <ul className="kb-chapter">
            {chapter.articles.map((article) => (
              <li className="kb-chapter-item" key={article.id}>
                <NavLink to={article.url} className="kb-chapter-link" activeClassName="active">
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
