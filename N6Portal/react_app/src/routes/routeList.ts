const routeList = {
  login: '/',
  forgotPassword: '/password-reset',
  signUp: '/sign-up',
  account: '/account',
  settings: '/settings',
  userSettings: '/user-settings',
  userSettingsMfaConfig: '/user-settings/mfa-configuration',
  incidents: '/incidents',
  organization: '/organization',
  knowledgeBase: '/knowledge_base',
  knowledgeBaseArticle: `/knowledge_base/articles/:articleId`,
  knowledgeBaseSearchResults: '/knowledge_base/search',
  notFound: '/page-not-found',
  noAccess: '/no-access'
};

export default routeList;
