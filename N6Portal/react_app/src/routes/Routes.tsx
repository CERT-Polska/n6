import AsyncLoader from 'components/loading/AsyncLoader';
import routeList from 'routes/routeList';
import { IPrivateRouteElem, IRouteElem } from 'routes/types';

const Account = AsyncLoader(() => import('components/pages/account/Account'));
const EditSettings = AsyncLoader(() => import('components/pages/editSettings/EditSettings'));
const UserSettings = AsyncLoader(() => import('components/pages/userSettings/UserSettings'));
const UserSettingsMfaConfig = AsyncLoader(
  () => import('components/pages/userSettingsMfaConfig/UserSettingsMfaConfigForm')
);
const Incidents = AsyncLoader(() => import('components/pages/incidents/Incidents'));
const Login = AsyncLoader(() => import('components/pages/login/Login'));
const LoginKeycloak = AsyncLoader(() => import('components/pages/login/LoginKeycloak'));
const LoginKeycloakSummary = AsyncLoader(() => import('components/pages/login/LoginKeycloakSummary'));
const ForgotPassword = AsyncLoader(() => import('components/pages/forgotPassword/ForgotPassword'));
const NoAccess = AsyncLoader(() => import('components/pages/noAccess/NoAccess'));
const NotFound = AsyncLoader(() => import('components/pages/notFound/NotFound'));
const Organization = AsyncLoader(() => import('components/pages/organization/Organization'));
const SignUp = AsyncLoader(() => import('components/pages/signUp/SignUp'));
const KnowledgeBase = AsyncLoader(() => import('components/pages/knowledgeBase/KnowledgeBase'));

export const publicRoutes: IRouteElem[] = [
  { path: routeList.login, component: <Login /> },
  { path: routeList.loginKeycloak, component: <LoginKeycloak /> },
  { path: routeList.loginKeycloakSummary, component: <LoginKeycloakSummary /> },
  { path: routeList.forgotPassword, component: <ForgotPassword /> },
  { path: routeList.signUp, component: <SignUp /> },
  { path: routeList.noAccess, component: <NoAccess /> },
  { path: routeList.notFound, component: <NotFound /> }
];

export const privateRoutes: IPrivateRouteElem[] = [
  {
    path: routeList.account,
    component: <Account />,
    redirectPath: routeList.noAccess
  },
  {
    path: routeList.settings,
    component: <EditSettings />,
    redirectPath: routeList.noAccess
  },
  {
    path: routeList.userSettings,
    component: <UserSettings />,
    redirectPath: routeList.noAccess
  },
  {
    path: routeList.userSettingsMfaConfig,
    component: <UserSettingsMfaConfig />,
    redirectPath: routeList.noAccess
  },
  {
    path: routeList.incidents,
    component: <Incidents />,
    redirectPath: routeList.noAccess
  },
  {
    path: routeList.organization,
    component: <Organization />,
    redirectPath: routeList.noAccess
  },
  {
    path: routeList.knowledgeBase,
    component: <KnowledgeBase />,
    redirectPath: routeList.noAccess,
    exact: false
  }
];
