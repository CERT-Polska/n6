import { FC } from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import { useTypedIntl } from 'utils/useTypedIntl';
import routeList from 'routes/routeList';
import useMatchMediaContext from 'context/MatchMediaContext';
import Logo from 'images/logo_n6.svg';
import UserMenuNavigation from 'components/navigation/UserMenuNavigation';
import MobileNavigation from 'components/navigation/MobileNavigation';
import useAuthContext from 'context/AuthContext';

const Header: FC = () => {
  const { isLg, isXl } = useMatchMediaContext();
  const { availableResources, isAuthenticated, knowledgeBaseEnabled } = useAuthContext();
  const { messages } = useTypedIntl();
  const { pathname } = useLocation();
  const pathsWithHeader = [
    routeList.organization,
    routeList.incidents,
    routeList.account,
    routeList.userSettings,
    routeList.userSettingsMfaConfig,
    routeList.settings,
    routeList.agreementsSettings
  ];
  const hasInsideAccess = availableResources.includes('/report/inside');

  const isKnowledgeBasePage = pathname.includes(routeList.knowledgeBase);
  if ((!pathsWithHeader.includes(pathname) && !isKnowledgeBasePage) || !isAuthenticated) return null;

  return (
    <header className="page-header">
      <div className="page-header-nav content-wrapper d-flex justify-content-between align-items-center">
        <Link to={routeList.incidents} data-testid="n6Logo">
          <img src={Logo} alt={`${messages.logo_alt}`} className="header-logo" />
        </Link>
        {!hasInsideAccess && (
          <ul className="header-links">
            <li className="font-bigger font-weight-medium">
              <NavLink
                to={routeList.incidents}
                className="header-link"
                activeClassName="active"
                data-testid="navIncidents"
              >
                {messages.header_nav_incidents}
              </NavLink>
            </li>
            {knowledgeBaseEnabled && (
              <li className="font-bigger font-weight-medium">
                <NavLink
                  to={routeList.knowledgeBase}
                  data-testid="navKnowledgeBase"
                  className="header-link"
                  activeClassName="active"
                >
                  {messages.header_nav_knowledge_base}
                </NavLink>
              </li>
            )}
          </ul>
        )}
        {hasInsideAccess &&
          (isLg || isXl ? (
            <ul className="header-links">
              <li className="font-bigger font-weight-medium">
                <NavLink
                  data-testid="navOrganization"
                  to={routeList.organization}
                  className="header-link"
                  activeClassName="active"
                >
                  {messages.header_nav_organization}
                </NavLink>
              </li>
              <li className="font-bigger font-weight-medium">
                <NavLink
                  data-testid="navIncidents"
                  to={routeList.incidents}
                  className="header-link"
                  activeClassName="active"
                >
                  {messages.header_nav_incidents}
                </NavLink>
              </li>
              {knowledgeBaseEnabled && (
                <li className="font-bigger font-weight-medium">
                  <NavLink
                    data-testid="navKnowledgeBase"
                    to={routeList.knowledgeBase}
                    className="header-link"
                    activeClassName="active"
                  >
                    {messages.header_nav_knowledge_base}
                  </NavLink>
                </li>
              )}
            </ul>
          ) : (
            <MobileNavigation />
          ))}
        <UserMenuNavigation />
      </div>
    </header>
  );
};

export default Header;
