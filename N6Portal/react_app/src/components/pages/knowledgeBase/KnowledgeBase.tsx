import { FC } from 'react';
import { Redirect } from 'react-router-dom';
import { Route, Switch } from 'react-router';
import { Row, Col } from 'react-bootstrap';
import ArticleSearchResults from 'components/pages/knowledgeBase/ArticleSearchResults';
import routeList from 'routes/routeList';
import SingleArticlePlaceholder from 'components/pages/knowledgeBase/SingleArticlePlaceholder';
import SingleArticle from 'components/pages/knowledgeBase/SingleArticle';
import ArticlesList from 'components/pages/knowledgeBase/ArticlesList';
import { CollapseChapterContextProvider } from 'context/ChapterCollapseContext';
import useAuthContext from 'context/AuthContext';
import { KBSearchContextProvider } from 'context/KBSearchContext';

const KnowledgeBase: FC = () => {
  const { knowledgeBaseEnabled } = useAuthContext();

  if (!knowledgeBaseEnabled) {
    return <Redirect to={routeList.notFound} />;
  }

  return (
    <KBSearchContextProvider>
      <CollapseChapterContextProvider>
        <div className="content-wrapper kb-wrapper">
          <Row className="no-gutters">
            <Col xs={12} lg={3}>
              <ArticlesList />
            </Col>
            <Col xs={12} lg={9}>
              <Switch>
                <Route exact path={routeList.knowledgeBaseArticle}>
                  <SingleArticle />
                </Route>
                <Route exact path={routeList.knowledgeBase}>
                  <SingleArticlePlaceholder />
                </Route>
                <Route exact path={routeList.knowledgeBaseSearchResults}>
                  <ArticleSearchResults />
                </Route>
                <Redirect to={routeList.notFound} />
              </Switch>
            </Col>
          </Row>
        </div>
      </CollapseChapterContextProvider>
    </KBSearchContextProvider>
  );
};

export default KnowledgeBase;
